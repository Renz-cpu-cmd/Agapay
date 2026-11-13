// Canonical AGAPAY physical-sensor firmware. Calibration is still provisional.
#include <Arduino.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>
#include <ctype.h>
#include <math.h>
#include <stdint.h>
#include <esp_timer.h>
#include <esp_system.h>
#include <esp_wifi.h>
#include <sys/time.h>
#include <time.h>
#include "transport_policy.h"
#include "depth_journal.h"
#include "depth_storage.h"
#ifndef AGAPAY_OLED
#define AGAPAY_OLED 0
#endif
#if AGAPAY_OLED
#include "oled_display.h"
#include "forecast_message.h"
bool forecastSubscribed = false;  // advisory forecast downlink (display-only)
uint32_t lastForecastSubscribeMs = 0;
#endif
#if AGAPAY_RELEASE_BUILD
#include <WiFiClientSecure.h>
#endif

#if AGAPAY_RELEASE_BUILD
#if __has_include("release_secrets.h") && __has_include("transport_secrets.h")
#include "release_secrets.h"
#include "transport_secrets.h"
#else
#error "Release requires protected release_secrets.h and CA transport_secrets.h; development secrets are never used."
#endif
#elif __has_include("secrets.h")
#include "secrets.h"
#else
#error "Copy include/secrets.example.h to include/secrets.h and configure locally."
#endif

#if __has_include("ingest_secrets.h")
#include "ingest_secrets.h"
#else
// Unprovisioned builds keep sensing locally and withhold network publication.
constexpr char STATION_INGEST_TOKEN[] = "";
#endif
#ifndef AGAPAY_DEVICE_ID
#define AGAPAY_DEVICE_ID ""
#endif
#ifndef AGAPAY_CONFIG_VERSION
#define AGAPAY_CONFIG_VERSION 0
#endif

constexpr uint8_t TRIG_PIN = 5;
constexpr uint8_t ECHO_PIN = 18;
constexpr uint8_t RAIN_PIN = 4;
constexpr uint8_t BUZZER_PIN = 25;
constexpr uint8_t LED_GREEN = 26;
constexpr uint8_t LED_YELLOW = 27;
constexpr uint8_t LED_RED = 14;
#if __has_include("station_config.h")
#include "station_config.h"
#elif AGAPAY_RELEASE_BUILD
#error "Release requires the reviewed station_config.h; prototype geometry cannot enter release."
#else
#include "prototype_config.h"
#endif
#if AGAPAY_OLED
#if __has_include("station_config.h")
constexpr bool OLED_PROTOTYPE_GEOMETRY = false;
#else
constexpr bool OLED_PROTOTYPE_GEOMETRY = true;  // unvalidated bench datum; shown on the health page
#endif
#endif
constexpr const char* STATION_ID = CONFIGURED_STATION_ID;
constexpr char FIRMWARE_VERSION[] = "0.4.0";
// 0.70 mm/tip confirmed by the operator on 2026-10-12; verify GPIO4 wiring/voltage before powering.

// DEVELOPMENT calibration only: measure mounting height above the depth datum,
// verify delivered gauge volume per tip, sensor range, and site flood thresholds.
// Use the backend's provisional DEPTH defaults, not the sketch's distance tiers.
// Original cardboard bench positions. Opt-in via Serial; never change telemetry.
constexpr float BENCH_ADVISORY_DISTANCE_CM = 60.0F;
constexpr float BENCH_WARNING_DISTANCE_CM = 35.0F;
constexpr float BENCH_RED_DISTANCE_CM = 25.0F;
constexpr uint8_t BUZZER_ON_LEVEL = LOW;
constexpr uint8_t BUZZER_OFF_LEVEL = HIGH;
// A8 bench evidence (2026-11-13): one manual tip produced a second closure 50-110 ms later
// (bucket rebound / reed bounce), so 50 ms double-counted rainfall. 250 ms still allows
// 4 tips/s, far above any real rain rate for this bucket.
constexpr uint32_t RAIN_DEBOUNCE_US = 250000;
constexpr uint32_t ECHO_TIMEOUT_US = 30000;
constexpr uint32_t SENSOR_INTERVAL_MS = 1000;
constexpr uint32_t PING_SPACING_MS = 60;
constexpr uint32_t PUBLISH_INTERVAL_MS = 2000;
constexpr uint32_t WIFI_RETRY_MS = 10000;
constexpr uint32_t MQTT_RETRY_MS = 5000;
constexpr uint64_t SEQUENCES_PER_BOOT = 1000000ULL;
static_assert(SENSOR_HEIGHT_CM > 0 && SENSOR_HEIGHT_CM <= 1000, "Invalid mounting height");
static_assert(RAIN_MM_PER_TIP > 0, "Rain calibration must be positive");
static_assert(SENSOR_HEIGHT_CM-THRESHOLD_EVACUATE_CM >= MIN_DISTANCE_CM+RANGE_MARGIN_CM+SENSOR_UNCERTAINTY_CM,
    "Critical depth lacks reliable range margin; review physical mounting, range and uncertainty");
static_assert(SENSOR_HEIGHT_CM <= MAX_DISTANCE_CM-RANGE_MARGIN_CM-SENSOR_UNCERTAINTY_CM,
    "Datum lacks far-range margin");
static_assert(THRESHOLD_ADVISORY_CM < THRESHOLD_WARNING_CM &&
    THRESHOLD_WARNING_CM < THRESHOLD_EVACUATE_CM, "Depth thresholds must be ordered");
static_assert(BENCH_RED_DISTANCE_CM > MIN_DISTANCE_CM &&
    BENCH_RED_DISTANCE_CM < BENCH_WARNING_DISTANCE_CM &&
    BENCH_WARNING_DISTANCE_CM < BENCH_ADVISORY_DISTANCE_CM, "Bench positions need valid range margin");

// UNKNOWN means no trustworthy measurement has been obtained since boot.
enum class AlertTier { UNKNOWN, NORMAL, ADVISORY, WARNING, EVACUATE };
#ifndef AGAPAY_LOCAL_BENCH_ALERTS
#define AGAPAY_LOCAL_BENCH_ALERTS 0
#endif
static_assert(AGAPAY_LOCAL_BENCH_ALERTS == 0 || AGAPAY_LOCAL_BENCH_ALERTS == 1, "Invalid local alert profile");
constexpr bool DEFAULT_LOCAL_BENCH_ALERTS = AGAPAY_LOCAL_BENCH_ALERTS == 1;
bool localBenchAlerts = DEFAULT_LOCAL_BENCH_ALERTS; // Runtime overrides are RAM only.
AlertTier currentLocalTier = AlertTier::UNKNOWN;
float lastAcceptedDistanceCm = NAN;
bool localOutputTestActive = false;
uint32_t localOutputTestStartMs = 0;
uint8_t localOutputTestStage = 0;
uint8_t lastDrivenLocalTier = UINT8_MAX;
char localCommand[48] = {};
uint8_t localCommandLength = 0;
bool localCommandOverflow = false;
struct TelemetrySample {
  float waterDepthCm = NAN;
  bool sensorValid = false;
  uint64_t uptimeMs = 0;
  int64_t measuredAtMs = 0;
  const char* sensorFault = "none";
  bool benchProfile = false;
};
bool sensorFaultActive = false;
// Local LED patterns (defense build): ADVISORY steady yellow; WARNING slow yellow blink;
// sensor fault = yellow double flash so a malfunction never looks like a flood tier.
constexpr uint32_t WARNING_BLINK_HALF_MS = 1000;          // 1 s on, 1 s off
constexpr uint32_t FAULT_FLASH_MS = 150;                  // on 150, off 150, on 150, off 1550
constexpr uint32_t FAULT_CYCLE_MS = 2000;
inline bool warningYellowOn(uint32_t sinceMs) { return (sinceMs / WARNING_BLINK_HALF_MS) % 2 == 0; }
inline bool faultYellowOn(uint32_t sinceMs) {
  const uint32_t phase = sinceMs % FAULT_CYCLE_MS;
  return phase < FAULT_FLASH_MS || (phase >= 2 * FAULT_FLASH_MS && phase < 3 * FAULT_FLASH_MS);
}
bool warningPatternActive = false;
uint32_t warningSinceMs = 0;
uint32_t sensorFaultSinceMs = 0;
bool blindZoneSeen = false;
const char* acquisitionFault = "insufficient_echoes";
struct TelemetryReport {
  TelemetrySample sample;
  float rainfallMm;
  uint64_t sequence;
  uint32_t uptimeMs;
  uint32_t bootSequence;
};
struct RainSnapshot {
  uint64_t count;
  uint64_t lastTipUptimeMs;
};

#if AGAPAY_RELEASE_BUILD
static_assert(MQTT_PORT==8883,"Release MQTT requires the reviewed TLS listener on port 8883");
static_assert(transportSame(MQTT_USERNAME,STATION_ID),"Release broker username must equal the commissioned station ID");
static_assert(sizeof(MQTT_PASSWORD)>24,"Provision a unique strong broker password for release");
static_assert(sizeof(MQTT_ROOT_CA)>256,"Release requires the PEM trust anchor, never setInsecure");
static_assert(sizeof(STATION_INGEST_TOKEN)>32 && AGAPAY_CONFIG_VERSION>0 && sizeof(AGAPAY_DEVICE_ID)>3,"Release station identity must be provisioned");
WiFiClientSecure networkClient;
#else
WiFiClient networkClient;
#endif
PubSubClient mqttClient(networkClient);
Preferences preferences;
QueueHandle_t reportQueue = nullptr;
QueueHandle_t rainQueue = nullptr;
QueueHandle_t depthQueue=nullptr, depthReplayQueue=nullptr, depthAckQueue=nullptr;
volatile uint32_t depthHandoffGaps=0;
uint32_t lastDepthQueueMs=0, lastDepthReplayMs=0;
bool depthAckSubscribed=false;
DepthRecord depthInFlight{};
bool depthInFlightReady=false;
Preferences rainPreferences;
volatile uint64_t rainLifetimeTips = 0;
volatile uint64_t rainLastTipUptimeMs = 0;
uint64_t rainBootStartTips = 0;
uint64_t rainPersistedTips = 0;
uint64_t rainAckTips = 0;
uint64_t rainAckUptimeMs = 0;
uint64_t rainPacketSequence = 0;
uint64_t lastRainPublishedCount = UINT64_MAX;
uint32_t lastRainPublishMs = 0;
uint32_t lastRainQueueMs = 0;
bool rainPersistenceReady = false;
bool rainPersistenceWarning = false;
char rainBootId[64] = {};
RainSnapshot networkRainSnapshot{};
bool networkRainReady = false;
portMUX_TYPE rainMux = portMUX_INITIALIZER_UNLOCKED;
volatile uint32_t rainTipCount = 0;
volatile uint32_t lastRainInterruptUs = 0;
volatile bool rainTipSeen = false;
TelemetrySample latestSample;
AlertTier currentTier = AlertTier::UNKNOWN;
uint64_t sequenceNo = 0;
uint64_t sequenceLimit = 0;
bool sequenceReady = false;
uint32_t telemetryBootSequence = 0;
uint32_t lastPublishMs = 0;
uint32_t lastSensorMs = 0;
uint32_t lastPingMs = 0;
uint32_t lastWifiAttemptMs = 0;
uint32_t lastMqttAttemptMs = 0;
constexpr uint32_t NETWORK_DIAGNOSTIC_MS = 10000;
bool wifiAttempted = false;
bool wifiDiscoveryDone = false;
bool wifiPinEligible = false;
bool wifiPinSsidMismatch = false;
bool wifiPinnedAttempt = false;
constexpr uint32_t WIFI_ASSOCIATION_GRACE_MS = 30000;
bool wifiWasConnected = false;
int lastWifiStatus = -1;
uint32_t lastWifiStatusMs = 0;
uint32_t lastWifiReasonMs = 0;
bool wifiReasonLogged = false;
portMUX_TYPE wifiDiagnosticMux = portMUX_INITIALIZER_UNLOCKED;
uint32_t wifiDisconnectEvents = 0;
uint8_t wifiDisconnectReason = 0;
struct WiFiScanEventEvidence {
  uint32_t events=0;
  uint32_t status=0;
  uint8_t number=0;
  uint8_t id=0;
};
WiFiScanEventEvidence wifiScanEventEvidence;
struct WiFiLinkEvidence {
  uint32_t associations=0,ipEvents=0,lostIpEvents=0;
  uint8_t bssid[6]={};
  uint8_t channel=0;
  int authentication=0;
};
WiFiLinkEvidence wifiLinkEvidence;
uint32_t wifiLoggedAssociations=0,wifiLoggedIpEvents=0,wifiLoggedLostIpEvents=0;
bool mqttWasConnected = false;
bool mqttBufferReady = false;
bool rainAckSubscriptionSent = false;
uint32_t lastAckSubscribeMs = 0;
bool telemetryPublished = false;
bool rainPublishAttempted = false;
uint64_t lastRainAttemptedCount = UINT64_MAX;
bool rainAckLogged = false;
uint64_t lastRainAckLoggedCount = UINT64_MAX;
uint32_t lastRainAckLogMs = 0;
uint32_t lastRainPublishLogMs = 0;
bool rainPublishLogged = false;
uint64_t lastRainLoggedCount = UINT64_MAX;
bool lastRainLoggedResult = false;
uint32_t lastNetworkHealthMs = 0;
float distanceSamples[5];
uint8_t attemptedSamples = 0;
uint8_t validSamples = 0;
bool sampling = false;

bool reserveSequenceBlock() {
  if (!preferences.begin("agapay", false)) return false;
  const uint32_t previousBoot = preferences.getUInt("boot_no", 0);
  if (previousBoot == UINT32_MAX) {
    preferences.end();
    return false;
  }
  const uint32_t bootNumber = previousBoot + 1;
  // Never transmit from an unpersisted block: reboot would otherwise reuse IDs.
  const bool saved = preferences.putUInt("boot_no", bootNumber) == sizeof(uint32_t);
  preferences.end();
  if (!saved) return false;
  telemetryBootSequence = bootNumber;
  sequenceNo = static_cast<uint64_t>(bootNumber) * SEQUENCES_PER_BOOT;
  sequenceLimit = sequenceNo + SEQUENCES_PER_BOOT;
  return true;
}

bool nextSequenceNumber(uint64_t& result) {
  if (!sequenceReady) return false;
  if (sequenceNo >= sequenceLimit) {
    sequenceReady = reserveSequenceBlock();
    if (!sequenceReady) return false;
  }
  result = ++sequenceNo;
  return true;
}

void IRAM_ATTR rainTipISR() {
  const uint32_t nowUs = micros();
  portENTER_CRITICAL_ISR(&rainMux);
  if (!rainTipSeen || static_cast<uint32_t>(nowUs - lastRainInterruptUs) >= RAIN_DEBOUNCE_US) {
    ++rainTipCount;
    ++rainLifetimeTips;
    rainLastTipUptimeMs = static_cast<uint64_t>(esp_timer_get_time()) / 1000ULL;
    lastRainInterruptUs = nowUs;
    rainTipSeen = true;
  }
  portEXIT_CRITICAL_ISR(&rainMux);
}

void restoreRainCounter() {
  rainPersistenceReady = rainPreferences.begin("agapay-rain", false);
  if (rainPersistenceReady) rainPersistedTips = rainPreferences.getULong64("lifetime", 0);
  rainBootStartTips = rainPersistedTips;
  rainLifetimeTips = rainPersistedTips;
  rainAckTips = rainBootStartTips;
  snprintf(rainBootId, sizeof(rainBootId), "%llX-%08lX-%08lX", static_cast<unsigned long long>(ESP.getEfuseMac()),
      static_cast<unsigned long>(esp_random()), static_cast<unsigned long>(esp_random()));
  Serial.printf("[RAIN] boot=%s persisted_tips=%llu calibration=%.3f mm/tip\n", rainBootId,
      static_cast<unsigned long long>(rainPersistedTips), RAIN_MM_PER_TIP);
}

void updateRainState(uint32_t now) {
  RainSnapshot snapshot{};
  portENTER_CRITICAL(&rainMux);
  snapshot.count = rainLifetimeTips;
  snapshot.lastTipUptimeMs = rainLastTipUptimeMs;
  portEXIT_CRITICAL(&rainMux);
  const bool changed = snapshot.count != rainPersistedTips;
  if (changed) {
    if (!rainPersistenceReady || rainPreferences.putULong64("lifetime", snapshot.count) != sizeof(uint64_t)) {
      if (!rainPersistenceWarning) Serial.println("[RAIN] NVS failure: counts retained in RAM, publication withheld; reboot would lose unpersisted tips");
      rainPersistenceWarning = true;
      return;
    }
    rainPersistedTips = snapshot.count;
    rainPersistenceWarning = false;
    Serial.printf("[RAIN] physical tips=%llu boot_tips=%llu session_rain=%.3f mm (durable cumulative counter)\n",
        static_cast<unsigned long long>(snapshot.count), static_cast<unsigned long long>(snapshot.count-rainBootStartTips),
        static_cast<double>((snapshot.count-rainBootStartTips)*RAIN_MM_PER_TIP));
  }
  if (rainPersistenceReady && rainQueue != nullptr && (changed || static_cast<uint32_t>(now-lastRainQueueMs)>=100)) {
    lastRainQueueMs=now;
    xQueueOverwrite(rainQueue,&snapshot);
  }
}

void rainAcknowledgement(char* topic, uint8_t* payload, unsigned int length) {
  char expected[96];
  snprintf(expected,sizeof(expected),"agapay/stations/%s/rain-ack",STATION_ID);
  if (strcmp(topic,expected)!=0 || length>512) return;
  JsonDocument doc;
  if (deserializeJson(doc,payload,length)) return;
  if (strcmp(doc["boot_id"] | "",rainBootId)!=0) return;
  const uint64_t count=doc["cumulative_tip_count"] | UINT64_MAX;
  if (count<rainAckTips || count>networkRainSnapshot.count) return;
  rainAckTips=count;
  rainAckUptimeMs=doc["device_uptime_ms"] | rainAckUptimeMs;
  const uint32_t now = millis();
  if (!rainAckLogged || (count != lastRainAckLoggedCount && static_cast<uint32_t>(now-lastRainAckLogMs)>=MQTT_RETRY_MS)) {
    Serial.printf("[RAIN ACK] backend acknowledged count=%llu boot=%s\n",
        static_cast<unsigned long long>(count), rainBootId);
    rainAckLogged = true;
    lastRainAckLoggedCount = count;
    lastRainAckLogMs = now;
  }
}

bool stationCredentialReady() {
  const size_t length = strlen(STATION_INGEST_TOKEN);
  const bool ready = length == 47 && strncmp(STATION_INGEST_TOKEN,"agi_",4)==0 &&
      strspn(STATION_INGEST_TOKEN+4,"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")==43;
  static bool warned = false;
  if (!ready && !warned) {
    Serial.println("[INGEST AUTH] Station is not provisioned; network publication withheld, local sensing continues");
    warned = true;
  }
  return ready;
}

void publishRainSnapshot(uint32_t now) {
  if (rainQueue != nullptr) {
    RainSnapshot queued;
    if (xQueueReceive(rainQueue,&queued,0)==pdTRUE) {networkRainSnapshot=queued;networkRainReady=true;}
  }
  if (!networkRainReady || !mqttClient.connected() || !stationCredentialReady()) return;
  const uint32_t elapsed=static_cast<uint32_t>(now-lastRainPublishMs);
  // A failed new-count publish must not retry every 10 ms and flood Serial/TCP.
  // New persisted tips still publish immediately; same-count retries wait 500 ms.
  if (rainPublishAttempted && networkRainSnapshot.count == lastRainAttemptedCount && elapsed<500) return;
  const bool newCount=networkRainSnapshot.count!=lastRainPublishedCount;
  const bool awaitingAck=networkRainSnapshot.count>rainAckTips;
  if (!newCount && !(awaitingAck && elapsed>=500) && elapsed<5000) return;
  JsonDocument envelope;
  envelope["ingest_token"] = STATION_INGEST_TOKEN;
  JsonObject doc = envelope["rain"].to<JsonObject>();
  doc["schema_version"]=2;doc["calibration_version"]=APPLIED_CONFIG_HASH;doc["quality"]="valid";
  const uint64_t uptime=static_cast<uint64_t>(esp_timer_get_time())/1000ULL;
  doc["station_id"]=STATION_ID;doc["boot_id"]=rainBootId;
  doc["packet_sequence"]=++rainPacketSequence;
  doc["cumulative_tip_count"]=networkRainSnapshot.count;
  doc["boot_start_tip_count"]=rainBootStartTips;
  doc["interval_start_tip_count"]=rainAckTips;
  doc["mm_per_tip"]=RAIN_MM_PER_TIP;
  doc["rainfall_increment_mm"]=(networkRainSnapshot.count-rainAckTips)*RAIN_MM_PER_TIP;
  doc["device_uptime_ms"]=uptime;
  doc["interval_start_uptime_ms"]=rainAckUptimeMs;
  if (networkRainSnapshot.count>rainBootStartTips) doc["last_tip_uptime_ms"]=networkRainSnapshot.lastTipUptimeMs;
  else doc["last_tip_uptime_ms"]=nullptr;
  doc["counter_persisted"]=true;doc["data_source"]="physical_rain_gauge";
  doc["firmware_version"]=FIRMWARE_VERSION;
  char topic[96],payload[1536];
  snprintf(topic,sizeof(topic),"agapay/stations/%s/rain",STATION_ID);
  if (measureJson(envelope)>=sizeof(payload)) {Serial.println("[RAIN] serialization overflow; cumulative counts retained");return;}
  serializeJson(envelope,payload,sizeof(payload));
  const bool published=mqttClient.publish(topic,payload,false);
  rainPublishAttempted = true;
  lastRainAttemptedCount = networkRainSnapshot.count;
  lastRainPublishMs=now;
  if (published) lastRainPublishedCount=networkRainSnapshot.count;
  if (!rainPublishLogged || static_cast<uint32_t>(now-lastRainPublishLogMs)>=NETWORK_DIAGNOSTIC_MS ||
      (published && (!lastRainLoggedResult || networkRainSnapshot.count != lastRainLoggedCount))) {
    Serial.printf("[RAIN MQTT] %s count=%llu state=%d; backend ACK required, counter retained offline\n",
        published?"published (QoS 0 write only)":"retry pending",static_cast<unsigned long long>(networkRainSnapshot.count),mqttClient.state());
    rainPublishLogged=true;lastRainPublishLogMs=now;
    lastRainLoggedCount=networkRainSnapshot.count;lastRainLoggedResult=published;
    if (published && awaitingAck) Serial.println("[RAIN ACK] pending; if absent check broker ACL and backend rejection logs");
  }
}

float snapshotRainfallInterval() {
  // Copy AND reset under the same lock. A tip on either side of this boundary
  // belongs to exactly one interval, including when the other ESP32 core runs.
  portENTER_CRITICAL(&rainMux);
  const uint32_t tips = rainTipCount;
  rainTipCount = 0;
  portEXIT_CRITICAL(&rainMux);
  return tips * RAIN_MM_PER_TIP;
}

bool readDistanceOnce(float& distanceCm) {
  distanceCm = NAN;
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  const unsigned long duration = pulseIn(ECHO_PIN, HIGH, ECHO_TIMEOUT_US);
  if (duration == 0) { acquisitionFault="no_echo";return false; }
  distanceCm = duration * 0.0343F / 2.0F;
  if (distanceCm < MIN_DISTANCE_CM) {blindZoneSeen=true;acquisitionFault="blind_zone";return false;}
  if (distanceCm > MAX_DISTANCE_CM) {acquisitionFault="out_of_range";return false;}
  return isfinite(distanceCm) && distanceCm >= MIN_DISTANCE_CM && distanceCm <= MAX_DISTANCE_CM;
}

bool measureDistanceMedian(float* samples, uint8_t count, float& distanceCm) {
  distanceCm = NAN;
  if (count < 3 || count > 5) return false;
  for (uint8_t i = 0; i < count; ++i) {
    for (uint8_t j = i + 1; j < count; ++j) {
      if (samples[j] < samples[i]) {
        const float temporary = samples[i];
        samples[i] = samples[j];
        samples[j] = temporary;
      }
    }
  }
  // Preserve the physical sketch's upper median when four readings are valid.
  distanceCm = samples[count / 2];
  return true;
}

bool calculateWaterDepth(float distanceCm, float& depthCm) {
  depthCm = NAN;
  if (!isfinite(distanceCm) || distanceCm < MIN_DISTANCE_CM || distanceCm > MAX_DISTANCE_CM) return false;
  const float depth = SENSOR_HEIGHT_CM - distanceCm;
  // Reject negative depths (bad datum/mounting) instead of manufacturing zero.
  if (!isfinite(depth) || depth < 0.0F || depth > SENSOR_HEIGHT_CM || depth > 1000.0F) return false;
  depthCm = depth;
  return true;
}

AlertTier classifyAlert(float depthCm) {
  if (depthCm >= THRESHOLD_EVACUATE_CM) return AlertTier::EVACUATE;
  if (depthCm >= THRESHOLD_WARNING_CM) return AlertTier::WARNING;
  if (depthCm >= THRESHOLD_ADVISORY_CM) return AlertTier::ADVISORY;
  return AlertTier::NORMAL;
}

AlertTier classifyBenchAlert(float distanceCm) {
  if (distanceCm <= BENCH_RED_DISTANCE_CM) return AlertTier::EVACUATE;
  if (distanceCm <= BENCH_WARNING_DISTANCE_CM) return AlertTier::WARNING;
  if (distanceCm <= BENCH_ADVISORY_DISTANCE_CM) return AlertTier::ADVISORY;
  return AlertTier::NORMAL;
}

void writeLocalAlertOutputs(AlertTier tier, const char* source) {
  if (tier == AlertTier::WARNING) {
    if (!warningPatternActive) { warningPatternActive = true; warningSinceMs = millis(); }  // starts ON
  } else {
    warningPatternActive = false;
  }
  digitalWrite(LED_GREEN, tier == AlertTier::NORMAL ? HIGH : LOW);
  digitalWrite(LED_YELLOW, tier == AlertTier::ADVISORY ||
      (tier == AlertTier::WARNING && warningYellowOn(static_cast<uint32_t>(millis() - warningSinceMs))) ? HIGH : LOW);
  digitalWrite(LED_RED, tier == AlertTier::EVACUATE ? HIGH : LOW);
  // MH-FMD active buzzer module: DC LOW=on, HIGH=off; no passive-buzzer tone.
  digitalWrite(BUZZER_PIN, tier == AlertTier::EVACUATE ? BUZZER_ON_LEVEL : BUZZER_OFF_LEVEL);
  if (lastDrivenLocalTier != static_cast<uint8_t>(tier)) {
    lastDrivenLocalTier = static_cast<uint8_t>(tier);
    Serial.printf("[LOCAL OUTPUT] source=%s tier=%u GPIO26=%d GPIO27=%d GPIO14=%d GPIO25=%d (buzzer LOW=ON)\n",
        source, static_cast<unsigned>(tier), digitalRead(LED_GREEN), digitalRead(LED_YELLOW),
        digitalRead(LED_RED), digitalRead(BUZZER_PIN));
  }
}

void applyLocalAlert(AlertTier tier) {
  sensorFaultActive=false;
  currentLocalTier = tier;
  if (localOutputTestActive) {
    // A genuine critical sample always preempts the temporary output test.
    if (tier != AlertTier::EVACUATE) return;
    localOutputTestActive = false;
    Serial.println("[LOCAL TEST] cancelled by critical sensor tier");
  }
  writeLocalAlertOutputs(tier, localBenchAlerts ? "BENCH DISTANCE (demo only)" : "DEPTH");
}

void printLocalAlertStatus() {
  Serial.printf("[APPLIED CONFIG] revision=%u hash=%s; validate mounting/range and rain volume physically\n",INSTALLATION_REVISION,APPLIED_CONFIG_HASH);
  Serial.printf("[LOCAL STATUS] mode=%s local_tier=%u last_valid_distance_cm=%.2f GPIO26=%d GPIO27=%d GPIO14=%d GPIO25=%d test=%u\n",
      localBenchAlerts ? "BENCH DISTANCE (demo only)" : "DEPTH", static_cast<unsigned>(currentLocalTier),
      lastAcceptedDistanceCm, digitalRead(LED_GREEN), digitalRead(LED_YELLOW), digitalRead(LED_RED),
      digitalRead(BUZZER_PIN), localOutputTestActive);
  Serial.printf("[LOCAL CONFIG] height=%.2f valid_distance=[%.2f,%.2f] depth_tiers=[%.2f,%.2f,%.2f] red_requires_distance<=%.2f cm bench_red<=%.2f cm\n",
      SENSOR_HEIGHT_CM, MIN_DISTANCE_CM, MAX_DISTANCE_CM, THRESHOLD_ADVISORY_CM,
      THRESHOLD_WARNING_CM, THRESHOLD_EVACUATE_CM, SENSOR_HEIGHT_CM-THRESHOLD_EVACUATE_CM, BENCH_RED_DISTANCE_CM);
  if (SENSOR_HEIGHT_CM-THRESHOLD_EVACUATE_CM <= MIN_DISTANCE_CM) {
    Serial.println("[LOCAL CONFIG] DEPTH red trigger has no reliable range margin; calibrate height/thresholds. BENCH is a separate local demo, not a flood threshold.");
  }
}

void handleLocalAlertCommand(const char* command, uint32_t now) {
  if (strcmp(command, "ALERT STATUS") == 0) { printLocalAlertStatus(); return; }
  if (strcmp(command, "ALERT TEST") == 0) {
    if (sensorFaultActive || localOutputTestActive || currentLocalTier == AlertTier::EVACUATE) {
      Serial.println("[LOCAL TEST] refused: test running or critical sensor tier active"); return;
    }
    localOutputTestActive = true; localOutputTestStartMs = now; localOutputTestStage = 0;
    Serial.println("[LOCAL TEST] 3-second GPIO-only test: green, yellow, red+buzzer; sensor/MQTT/rain data unchanged");
    writeLocalAlertOutputs(AlertTier::NORMAL, "SELFTEST green");
    return;
  }
  if (strcmp(command, "ALERT STOP") == 0) {
    localOutputTestActive = false;
    if (sensorFaultActive) return;
    writeLocalAlertOutputs(currentLocalTier, localBenchAlerts ? "BENCH restored" : "DEPTH restored");
    Serial.println("[LOCAL TEST] stopped; latest sensor outputs restored"); return;
  }
  if (strcmp(command, "ALERT DEMO ON") == 0 || strcmp(command, "ALERT DEMO OFF") == 0) {
#if AGAPAY_RELEASE_BUILD
    Serial.println("[LOCAL COMMAND] Exercise overrides disabled in release firmware");return;
#else
    localOutputTestActive = false;
    localBenchAlerts = strcmp(command, "ALERT DEMO ON") == 0;
    if (sensorFaultActive) {printLocalAlertStatus();return;}
    float lastDepth;
    if (calculateWaterDepth(lastAcceptedDistanceCm, lastDepth)) {
      applyLocalAlert(localBenchAlerts ? classifyBenchAlert(lastAcceptedDistanceCm) : classifyAlert(lastDepth));
    } else applyLocalAlert(AlertTier::UNKNOWN);
    printLocalAlertStatus(); return;
#endif
  }
  Serial.println("[LOCAL COMMAND] use ALERT STATUS, ALERT TEST, ALERT STOP, ALERT DEMO ON, ALERT DEMO OFF");
}

void serviceLocalAlertDiagnostics(uint32_t now) {
  // Bounded input and no delay: sensor acquisition/rain persistence keep running.
  for (uint8_t n = 0; n < 16 && Serial.available() > 0; ++n) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\r') continue;
    if (c == '\n') {
      if (localCommandOverflow) Serial.println("[LOCAL COMMAND] discarded invalid/oversized input");
      else if (localCommandLength) { localCommand[localCommandLength] = 0; handleLocalAlertCommand(localCommand, now); }
      localCommandLength = 0; localCommandOverflow = false;
    } else if (c < 32 || c > 126 || localCommandLength >= sizeof(localCommand)-1) localCommandOverflow = true;
    else if (!localCommandOverflow) localCommand[localCommandLength++] = c;
  }
  if (!localOutputTestActive) return;
  const uint32_t elapsed = static_cast<uint32_t>(now-localOutputTestStartMs);
  if (elapsed >= 3000) {
    localOutputTestActive = false;
    writeLocalAlertOutputs(currentLocalTier, localBenchAlerts ? "BENCH restored" : "DEPTH restored");
    Serial.println("[LOCAL TEST] complete; latest sensor outputs restored (verify lights/sound physically)");
  } else {
    const uint8_t stage = elapsed / 1000;
    if (stage != localOutputTestStage) {
      localOutputTestStage = stage;
      writeLocalAlertOutputs(stage == 1 ? AlertTier::ADVISORY : AlertTier::EVACUATE,
          stage == 1 ? "SELFTEST yellow" : "SELFTEST red+buzzer");
    }
  }
}

void finishSensorSample() {
  latestSample.benchProfile=localBenchAlerts;
  latestSample.uptimeMs = static_cast<uint64_t>(esp_timer_get_time()) / 1000ULL;
  struct timeval utcTime{};
  gettimeofday(&utcTime, nullptr);
  // No fabricated UTC before SNTP synchronization. Such samples are historical.
  latestSample.measuredAtMs = utcTime.tv_sec >= 1767225600
      ? static_cast<int64_t>(utcTime.tv_sec) * 1000 + utcTime.tv_usec / 1000 : 0;
  float distanceCm = NAN;
  latestSample.sensorValid = measureDistanceMedian(distanceSamples, validSamples, distanceCm)
      && calculateWaterDepth(distanceCm, latestSample.waterDepthCm);
  if (blindZoneSeen) latestSample.sensorValid=false;
  if (latestSample.sensorValid) {
    latestSample.sensorFault="none";
    lastAcceptedDistanceCm = distanceCm;
    currentTier = classifyAlert(latestSample.waterDepthCm);
    applyLocalAlert(localBenchAlerts ? classifyBenchAlert(distanceCm) : currentTier);
  } else {
    latestSample.waterDepthCm = NAN;
    latestSample.sensorFault=blindZoneSeen?"blind_zone":validSamples>=3?"out_of_range":acquisitionFault;
    if (!sensorFaultActive) sensorFaultSinceMs = millis();  // double-flash pattern starts ON
    sensorFaultActive=true;localOutputTestActive=false;
    // Fault is distinct from a measured tier. Preserve an existing critical
    // red/buzzer latch; other states show the yellow double flash and no green.
    digitalWrite(LED_GREEN,LOW);
    digitalWrite(LED_YELLOW,faultYellowOn(static_cast<uint32_t>(millis()-sensorFaultSinceMs))?HIGH:LOW);
    digitalWrite(LED_RED,currentLocalTier==AlertTier::EVACUATE?HIGH:LOW);
    digitalWrite(BUZZER_PIN,currentLocalTier==AlertTier::EVACUATE?BUZZER_ON_LEVEL:BUZZER_OFF_LEVEL);
    Serial.printf("[SENSOR FAULT] %s; hazard latch retained, no inferred recovery\n",latestSample.sensorFault);
  }
  blindZoneSeen=false;
  Serial.printf("[CALIBRATION REQUIRED] distance=%.2f cm depth=%.2f cm valid=%u tier=%u\n",
      distanceCm, latestSample.waterDepthCm, latestSample.sensorValid, static_cast<unsigned>(currentTier));
}

void sampleSensors(uint32_t now) {
  if (!sampling && static_cast<uint32_t>(now - lastSensorMs) >= SENSOR_INTERVAL_MS) {
    lastSensorMs = now;
    attemptedSamples = validSamples = 0;
    blindZoneSeen=false;acquisitionFault="insufficient_echoes";
    sampling = true;
    lastPingMs = now - PING_SPACING_MS;
  }
  if (!sampling || static_cast<uint32_t>(now - lastPingMs) < PING_SPACING_MS) return;
  lastPingMs = now;
  float distanceCm;
  if (readDistanceOnce(distanceCm)) distanceSamples[validSamples++] = distanceCm;
  if (++attemptedSamples == 5) {
    sampling = false;
    finishSensorSample();
  }
}

void serviceWarningBlink(uint32_t now) {
  if (!warningPatternActive || sensorFaultActive || localOutputTestActive || currentLocalTier != AlertTier::WARNING) return;
  digitalWrite(LED_YELLOW, warningYellowOn(static_cast<uint32_t>(now - warningSinceMs)) ? HIGH : LOW);
}

void serviceSensorFault(uint32_t now) {
  if (!sensorFaultActive) return;
  digitalWrite(LED_GREEN,LOW);
  digitalWrite(LED_YELLOW,faultYellowOn(static_cast<uint32_t>(now-sensorFaultSinceMs))?HIGH:LOW);
  digitalWrite(LED_RED,currentLocalTier==AlertTier::EVACUATE?HIGH:LOW);
  digitalWrite(BUZZER_PIN,currentLocalTier==AlertTier::EVACUATE?BUZZER_ON_LEVEL:BUZZER_OFF_LEVEL);
}

const char* wifiStatusName(int status) {
  switch (status) {
    case WL_IDLE_STATUS: return "IDLE";
    case WL_NO_SSID_AVAIL: return "NO_SSID_AVAILABLE";
    case WL_SCAN_COMPLETED: return "SCAN_COMPLETED";
    case WL_CONNECTED: return "CONNECTED";
    case WL_CONNECT_FAILED: return "CONNECT_FAILED";
    case WL_CONNECTION_LOST: return "CONNECTION_LOST";
    case WL_DISCONNECTED: return "DISCONNECTED";
    case WL_NO_SHIELD: return "NO_SHIELD";
    default: return "UNKNOWN";
  }
}

const char* wifiReasonName(uint8_t reason) {
  switch (reason) {
    case 2: return "AUTH_EXPIRE";
    case 15: return "4WAY_HANDSHAKE_TIMEOUT (check password/security/signal)";
    case 200: return "BEACON_TIMEOUT (check hotspot/signal)";
    case 201: return "NO_AP_FOUND (check SSID/2.4 GHz/hotspot)";
    case 202: return "AUTH_FAIL (check password/security)";
    case 203: return "ASSOC_FAIL (check hotspot limits/security)";
    case 204: return "HANDSHAKE_TIMEOUT (check password/security/signal)";
    default: return "see ESP32 Wi-Fi reason code";
  }
}

void wifiDiagnosticEvent(WiFiEvent_t event, WiFiEventInfo_t info) {
  // Framework callback runs on a different task. No Serial or network work here.
  if (event==ARDUINO_EVENT_WIFI_SCAN_DONE) {
    portENTER_CRITICAL(&wifiDiagnosticMux);
    ++wifiScanEventEvidence.events;
    wifiScanEventEvidence.status=info.wifi_scan_done.status;
    wifiScanEventEvidence.number=info.wifi_scan_done.number;
    wifiScanEventEvidence.id=info.wifi_scan_done.scan_id;
    portEXIT_CRITICAL(&wifiDiagnosticMux);
    return;
  }
  if (event==ARDUINO_EVENT_WIFI_STA_CONNECTED || event==ARDUINO_EVENT_WIFI_STA_GOT_IP || event==ARDUINO_EVENT_WIFI_STA_LOST_IP) {
    portENTER_CRITICAL(&wifiDiagnosticMux);
    if (event==ARDUINO_EVENT_WIFI_STA_CONNECTED) {
      ++wifiLinkEvidence.associations;
      memcpy(wifiLinkEvidence.bssid,info.wifi_sta_connected.bssid,6);
      wifiLinkEvidence.channel=info.wifi_sta_connected.channel;
      wifiLinkEvidence.authentication=static_cast<int>(info.wifi_sta_connected.authmode);
    } else if (event==ARDUINO_EVENT_WIFI_STA_GOT_IP) ++wifiLinkEvidence.ipEvents;
    else ++wifiLinkEvidence.lostIpEvents;
    portEXIT_CRITICAL(&wifiDiagnosticMux);
    return;
  }
  if (event != ARDUINO_EVENT_WIFI_STA_DISCONNECTED) return;
  portENTER_CRITICAL(&wifiDiagnosticMux);
  ++wifiDisconnectEvents;
  wifiDisconnectReason = info.wifi_sta_disconnected.reason;
  portEXIT_CRITICAL(&wifiDiagnosticMux);
}

int beginWiFiAssociation();

// Optional access-point pinning comes only from ignored local settings (secrets.h):
//   #define AGAPAY_WIFI_PIN_BSSID 0x00,0x00,0x00,0x00,0x00,0x00   // the verified AP's BSSID
//   #define AGAPAY_WIFI_PIN_CHANNEL 11
// Both or neither. Without them the station associates normally with WIFI_SSID/WIFI_PASSWORD.
// No network name or hardware address is compiled into public source or printed.
#if defined(AGAPAY_WIFI_PIN_BSSID) && defined(AGAPAY_WIFI_PIN_CHANNEL)
constexpr bool WIFI_PIN_CONFIGURED = true;
constexpr uint8_t WIFI_PIN_BSSID[6] = {AGAPAY_WIFI_PIN_BSSID};
constexpr uint8_t WIFI_PIN_CHANNEL = AGAPAY_WIFI_PIN_CHANNEL;
#elif defined(AGAPAY_WIFI_PIN_BSSID) || defined(AGAPAY_WIFI_PIN_CHANNEL)
#error "Define both AGAPAY_WIFI_PIN_BSSID and AGAPAY_WIFI_PIN_CHANNEL in secrets.h, or neither"
#else
constexpr bool WIFI_PIN_CONFIGURED = false;
constexpr uint8_t WIFI_PIN_BSSID[6] = {};
constexpr uint8_t WIFI_PIN_CHANNEL = 0;
#endif
constexpr bool wifiPinBssidValid() {
  // A unicast, non-zero address: multicast bit clear, not all zero, not broadcast.
  return (WIFI_PIN_BSSID[0] & 0x01) == 0 &&
      (WIFI_PIN_BSSID[0] | WIFI_PIN_BSSID[1] | WIFI_PIN_BSSID[2] | WIFI_PIN_BSSID[3] | WIFI_PIN_BSSID[4] | WIFI_PIN_BSSID[5]) != 0;
}
static_assert(!WIFI_PIN_CONFIGURED || (WIFI_PIN_CHANNEL >= 1 && WIFI_PIN_CHANNEL <= 14), "AGAPAY_WIFI_PIN_CHANNEL must be 1-14");
static_assert(!WIFI_PIN_CONFIGURED || wifiPinBssidValid(), "AGAPAY_WIFI_PIN_BSSID must be a unicast, non-zero BSSID");

bool isPinnedBssid(const uint8_t* bssid) {
  return WIFI_PIN_CONFIGURED && memcmp(bssid,WIFI_PIN_BSSID,sizeof(WIFI_PIN_BSSID))==0;
}

const char* wifiPinLabel(const uint8_t* bssid) {
  return !WIFI_PIN_CONFIGURED ? "not-configured" : isPinnedBssid(bssid) ? "match" : "different";
}

void maintainWiFiNonBlocking(uint32_t now) {
  const int status = WiFi.status();
  const bool connected = status == WL_CONNECTED;
  portENTER_CRITICAL(&wifiDiagnosticMux);
  const auto link=wifiLinkEvidence;
  portEXIT_CRITICAL(&wifiDiagnosticMux);
  if (link.associations!=wifiLoggedAssociations) {
    wifiLoggedAssociations=link.associations;
    // The access point's hardware address is never printed; only whether it is the locally pinned one.
    Serial.printf("[WIFI ASSOC] Link established auth_mode=%d channel=%u pinned_bssid=%s; DHCP pending (link success implies authentication completed)\n",
        link.authentication,link.channel,wifiPinLabel(link.bssid));
  }
  if (link.ipEvents!=wifiLoggedIpEvents) {
    wifiLoggedIpEvents=link.ipEvents;
    Serial.printf("[WIFI DHCP] GOT_IP: %s\n",WiFi.localIP().toString().c_str());
  }
  if (link.lostIpEvents!=wifiLoggedLostIpEvents) {
    wifiLoggedLostIpEvents=link.lostIpEvents;
    Serial.println("[WIFI DHCP] LOST_IP; waiting for renewed address");
  }
  if (connected != wifiWasConnected) {
    Serial.println(connected ? "[WIFI] Connected" : "[WIFI] Disconnected; MQTT gated until Wi-Fi returns");
    if (connected) Serial.printf("[WIFI] IP: %s RSSI: %d dBm\n", WiFi.localIP().toString().c_str(),WiFi.RSSI());
    wifiWasConnected = connected;
  }
  if (lastWifiStatus == -1 || (status != lastWifiStatus && static_cast<uint32_t>(now-lastWifiStatusMs)>=NETWORK_DIAGNOSTIC_MS)) {
    Serial.printf("[WIFI] Status: %d (%s) uptime_ms=%lu\n",status,wifiStatusName(status),static_cast<unsigned long>(now));
    lastWifiStatus=status;lastWifiStatusMs=now;
  }
  if (!wifiReasonLogged || static_cast<uint32_t>(now-lastWifiReasonMs)>=NETWORK_DIAGNOSTIC_MS) {
    portENTER_CRITICAL(&wifiDiagnosticMux);
    const uint32_t events=wifiDisconnectEvents;
    const uint8_t reason=wifiDisconnectReason;
    wifiDisconnectEvents=0;
    portEXIT_CRITICAL(&wifiDiagnosticMux);
    if (events) {
      Serial.printf("[WIFI] Disconnect events=%lu last_reason=%u (%s)\n",static_cast<unsigned long>(events),reason,wifiReasonName(reason));
      wifiReasonLogged=true;lastWifiReasonMs=now;
    }
  }
  if (connected || static_cast<uint32_t>(now-lastWifiAttemptMs)<WIFI_RETRY_MS) return;
  if (wifiPinnedAttempt && static_cast<uint32_t>(now-lastWifiAttemptMs)<WIFI_ASSOCIATION_GRACE_MS) return;
  if (wifiPinnedAttempt) Serial.println("[WIFI ASSOC] No IP after 30000 ms; retrying unchanged configured identity");
  const uint32_t elapsed=static_cast<uint32_t>(now-lastWifiAttemptMs);
  Serial.printf("[WIFI] %s to configured SSID (len=%u) uptime_ms=%lu elapsed_ms=%lu retry_ms=%lu\n",
      wifiAttempted?"Retry connecting":"Connecting",static_cast<unsigned>(strlen(WIFI_SSID)),static_cast<unsigned long>(now),
      static_cast<unsigned long>(elapsed),static_cast<unsigned long>(WIFI_RETRY_MS));
  lastWifiAttemptMs=now;wifiAttempted=true;
  const int result=beginWiFiAssociation();
  Serial.printf("[WIFI] begin status=%d (%s); association/DHCP may still be pending\n",result,wifiStatusName(result));
}

const char* mqttStateName(int state) {
  switch (state) {
    case -4: return "MQTT timeout waiting for broker response";
    case -3: return "TCP connection lost";
    case -2: return "TCP connect failed: unreachable/refused/DNS/firewall; state alone cannot distinguish";
    case -1: return "disconnected";
    case 0: return "connected (CONNACK accepted)";
    case 1: return "broker refused protocol";
    case 2: return "broker refused client ID";
    case 3: return "broker unavailable";
    case 4: return "broker refused username/password";
    case 5: return "broker refused connection authorization (topic ACL still separate)";
    default: return "unknown";
  }
}

void maintainRainAckSubscription(uint32_t now) {
  if (rainAckSubscriptionSent || !mqttClient.connected() || static_cast<uint32_t>(now-lastAckSubscribeMs)<MQTT_RETRY_MS) return;
  lastAckSubscribeMs=now;
  char topic[96];snprintf(topic,sizeof(topic),"agapay/stations/%s/rain-ack",STATION_ID);
  rainAckSubscriptionSent=mqttClient.subscribe(topic,1);
  // PubSubClient 2.8 does not expose SUBACK grants. A write is not ACL proof.
  Serial.printf("[MQTT] Rain-ACK subscribe %s topic=%s; %s\n",rainAckSubscriptionSent?"request sent":"FAILED",topic,
      rainAckSubscriptionSent?"broker grant unverified until ACK received":"retry in 5000 ms");
}

void maintainMqttNonBlocking(uint32_t now) {
  const bool connected=mqttClient.connected();
  if (mqttWasConnected && !connected) {
    Serial.printf("[MQTT] Disconnected state=%d (%s); retry_ms=%lu\n",mqttClient.state(),mqttStateName(mqttClient.state()),static_cast<unsigned long>(MQTT_RETRY_MS));
    mqttWasConnected=false;rainAckSubscriptionSent=false;depthAckSubscribed=false;
#if AGAPAY_OLED
    forecastSubscribed=false;
#endif
  }
  if (WiFi.status() != WL_CONNECTED || connected || !mqttBufferReady) return;
  if (static_cast<uint32_t>(now - lastMqttAttemptMs) < MQTT_RETRY_MS) return;
  lastMqttAttemptMs = now;
#if AGAPAY_RELEASE_BUILD
  struct timeval clock{};gettimeofday(&clock,nullptr);
  if(clock.tv_sec<1735689600 || !stationCredentialReady()) {
    Serial.println("[MQTT TLS] Withheld: synchronized UTC and a provisioned identity are required; local sensing continues");return;
  }
#endif
  char clientId[80];
  snprintf(clientId, sizeof(clientId), "AGAPAY_%s_%llX", STATION_ID,
      static_cast<unsigned long long>(ESP.getEfuseMac()));
  Serial.printf("[MQTT] Connecting to %s:%d auth=%s client=%s uptime_ms=%lu retry_ms=%lu\n",MQTT_HOST,MQTT_PORT,
      MQTT_USERNAME[0]!='\0'?"username configured":"anonymous",clientId,static_cast<unsigned long>(now),static_cast<unsigned long>(MQTT_RETRY_MS));
  const bool accepted = MQTT_USERNAME[0] != '\0'
      ? mqttClient.connect(clientId, MQTT_USERNAME, MQTT_PASSWORD)
      : mqttClient.connect(clientId);
  if (accepted) {
    mqttWasConnected=true;telemetryPublished=false;rainAckLogged=false;
    rainAckSubscriptionSent=false;lastAckSubscribeMs=now-MQTT_RETRY_MS;
#if AGAPAY_OLED
    forecastSubscribed=false;lastForecastSubscribeMs=now-MQTT_RETRY_MS;
#endif
    Serial.printf("[MQTT] Connected state=%d (broker accepted CONNACK); topic ACL still requires verification\n",mqttClient.state());
    maintainRainAckSubscription(now);
    rainPublishAttempted=false;
    lastRainPublishedCount=UINT64_MAX;
  } else {
    Serial.printf("[MQTT] Connection failed state=%d (%s) duration_ms=%lu\n",mqttClient.state(),mqttStateName(mqttClient.state()),static_cast<unsigned long>(millis()-now));
  }
}

void buildDepthObservation(JsonObject document,const TelemetryReport& report) {
  document["station_id"] = STATION_ID;
  document["schema_version"] = 3;
  document["applied_config_hash"] = APPLIED_CONFIG_HASH;
  document["local_alert_profile"] = report.sample.benchProfile?"cardboard_bench":"depth";
  document["sensor_fault"] = report.sample.sensorValid?"none":report.sample.sensorFault;
  document["config_version"] = AGAPAY_CONFIG_VERSION;
  document["source_id"] = AGAPAY_DEVICE_ID;
  document["boot_sequence"] = report.bootSequence;
  char bootId[80];
  snprintf(bootId, sizeof(bootId), "%s-%lu", STATION_ID, static_cast<unsigned long>(report.bootSequence));
  document["boot_id"] = bootId;
  if (report.sample.measuredAtMs > 0) {
    const time_t seconds = static_cast<time_t>(report.sample.measuredAtMs / 1000);
    struct tm utcFields{};
    gmtime_r(&seconds, &utcFields);
    char measured[32];
    strftime(measured, sizeof(measured), "%Y-%m-%dT%H:%M:%S", &utcFields);
    char timestamp[40];
    snprintf(timestamp, sizeof(timestamp), "%s.%03uZ", measured,
        static_cast<unsigned>(report.sample.measuredAtMs % 1000));
    document["measured_at"] = timestamp;
  } else document["measured_at"] = nullptr;
  document["sequence_no"] = report.sequence;
  if (report.sample.sensorValid) document["water_depth_cm"] = report.sample.waterDepthCm;
  else document["water_depth_cm"] = nullptr;
  // Rainfall is supplied exclusively by the durable cumulative rain journal.
  // The old copy/reset interval can be dropped offline and is not an observation.
  document["rainfall_mm"] = nullptr;
  document["rainfall_interval"] = nullptr;
  document["sensor_quality"] = report.sample.sensorValid ? "valid" : "invalid";
  document["device_uptime_ms"] = report.sample.uptimeMs;
  document["firmware_version"] = FIRMWARE_VERSION;
}

void publishTelemetry(const TelemetryReport& report) {
  if (!stationCredentialReady() || strlen(AGAPAY_DEVICE_ID) < 3 || AGAPAY_CONFIG_VERSION < 1) return;
  JsonDocument envelope;
  envelope["ingest_token"] = STATION_INGEST_TOKEN;
  JsonObject document = envelope["telemetry"].to<JsonObject>();
  buildDepthObservation(document,report);
  char topic[96];
  snprintf(topic, sizeof(topic), "agapay/stations/%s/telemetry", STATION_ID);
  char payload[1536];
  if (measureJson(envelope) >= sizeof(payload)) {
    Serial.println("Telemetry serialization overflow; interval dropped");
    return;
  }
  serializeJson(envelope, payload, sizeof(payload));
  const bool published = mqttClient.publish(topic, payload, false);
  if (published && !telemetryPublished) {
    Serial.printf("[MQTT] First telemetry publication written topic=%s; QoS 0 requires backend/broker evidence\n",topic);
    telemetryPublished=true;
  }
  if (!published) Serial.printf("[MQTT] Telemetry publication failed state=%d (%s)\n",mqttClient.state(),mqttStateName(mqttClient.state()));
  // The envelope contains a credential: never print its body to Serial/logs.
  Serial.printf("Telemetry %s: station=%s sequence=%llu quality=%s\n",
      published ? "sent (QoS 0; no backend acknowledgement)" : "FAILED; interval dropped",
      STATION_ID,static_cast<unsigned long long>(report.sequence),report.sample.sensorValid ? "valid" : "invalid");
}

void deliverLatestReport() {
  TelemetryReport report;
  if (xQueueReceive(reportQueue, &report, 0) == pdTRUE) {
    // Do not merge an outage's rainfall into a later ten-second interval.
    if (mqttClient.connected() && static_cast<uint32_t>(millis() - report.uptimeMs) < PUBLISH_INTERVAL_MS) {
      publishTelemetry(report);
    } else {
      Serial.println("MQTT offline/stale report: interval dropped; local alerts continue");
    }
  }
}

const char* wifiAuthenticationName(int authentication) {
  switch (authentication) {
    case WIFI_AUTH_OPEN: return "OPEN";
    case WIFI_AUTH_WEP: return "WEP";
    case WIFI_AUTH_WPA_PSK: return "WPA_PSK";
    case WIFI_AUTH_WPA2_PSK: return "WPA2_PSK";
    case WIFI_AUTH_WPA_WPA2_PSK: return "WPA_WPA2_PSK";
    case WIFI_AUTH_WPA2_ENTERPRISE: return "WPA2_ENTERPRISE";
    case WIFI_AUTH_WPA3_PSK: return "WPA3_PSK";
    case WIFI_AUTH_WPA2_WPA3_PSK: return "WPA2_WPA3_PSK";
    default: return "OTHER";
  }
}

int beginWiFiAssociation() {
  // A pinned attempt needs local pin settings plus a trustworthy scan that saw the pinned AP
  // advertising the configured SSID (or a hidden/empty field) on the pinned channel.
  wifiPinnedAttempt=WIFI_PIN_CONFIGURED && wifiPinEligible && !wifiPinSsidMismatch;
  if (wifiPinnedAttempt) {
    Serial.printf("[WIFI ASSOC] Pinned attempt: configured SSID/password unchanged, channel=%u, BSSID from local settings, grace_ms=30000\n",
        static_cast<unsigned>(WIFI_PIN_CHANNEL));
    return WiFi.begin(WIFI_SSID,WIFI_PASSWORD,WIFI_PIN_CHANNEL,WIFI_PIN_BSSID,true);
  }
  return WiFi.begin(WIFI_SSID,WIFI_PASSWORD);
}

size_t boundedSsidLength(const uint8_t* bytes) {
  size_t length=0;
  while (length<32 && bytes[length]!=0) ++length;
  return length;
}

// Network names are compared, never printed. Near misses are classified so that a
// configuration typo (e.g. a missing trailing space, the 2026-10-13 root cause) stays
// diagnosable from the log without disclosing the name itself.
enum class SsidComparison { Exact, Empty, TrailingWhitespaceOnly, CaseOnly, Different };

size_t trimmedSsidLength(const uint8_t* bytes,size_t length) {
  while (length>0 && (bytes[length-1]==' ' || bytes[length-1]=='\t')) --length;
  return length;
}

SsidComparison compareToConfiguredSsid(const uint8_t* bytes) {
  bool allZero=true;
  for (unsigned i=0;i<32;++i) if (bytes[i]!=0) allZero=false;
  if (allZero) return SsidComparison::Empty;
  const auto* configured=reinterpret_cast<const uint8_t*>(WIFI_SSID);
  const size_t length=boundedSsidLength(bytes),configuredLength=strlen(WIFI_SSID);
  if (length==configuredLength && memcmp(bytes,configured,length)==0 && length>0) return SsidComparison::Exact;
  const size_t a=trimmedSsidLength(bytes,length),b=trimmedSsidLength(configured,configuredLength);
  if (a>0 && a==b && memcmp(bytes,configured,a)==0) return SsidComparison::TrailingWhitespaceOnly;
  if (length>0 && length==configuredLength) {
    bool caseOnly=true;
    for (size_t i=0;i<length && caseOnly;++i) caseOnly=tolower(bytes[i])==tolower(configured[i]);
    if (caseOnly) return SsidComparison::CaseOnly;
  }
  return SsidComparison::Different;
}

const char* ssidComparisonName(SsidComparison comparison) {
  switch (comparison) {
    case SsidComparison::Exact: return "EXACT MATCH";
    case SsidComparison::Empty: return "EMPTY/HIDDEN FIELD";
    case SsidComparison::TrailingWhitespaceOnly: return "DIFFERS ONLY BY TRAILING WHITESPACE";
    case SsidComparison::CaseOnly: return "DIFFERS ONLY BY LETTER CASE";
    default: return "DIFFERENT SSID BYTES";
  }
}

void inspectPinnedSsid(const char* label,const wifi_ap_record_t& ap,bool trustworthyScan) {
  const auto comparison=compareToConfiguredSsid(ap.ssid);
  Serial.printf("[WIFI SSID %s] pinned AP: returned_len=%u configured_len=%u classification=%s\n",label,
      static_cast<unsigned>(boundedSsidLength(ap.ssid)),static_cast<unsigned>(strlen(WIFI_SSID)),ssidComparisonName(comparison));
  const bool acceptable=comparison==SsidComparison::Exact || comparison==SsidComparison::Empty;
  if (!acceptable) wifiPinSsidMismatch=true;  // a different name at the pinned AP is never adopted
  if (trustworthyScan && ap.primary==WIFI_PIN_CHANNEL && acceptable) wifiPinEligible=true;
}

WiFiScanEventEvidence snapshotWiFiScanEvent() {
  portENTER_CRITICAL(&wifiDiagnosticMux);
  const auto snapshot=wifiScanEventEvidence;
  portEXIT_CRITICAL(&wifiDiagnosticMux);
  return snapshot;
}

constexpr uint8_t WIFI_DISCOVERY_CHANNEL = WIFI_PIN_CONFIGURED ? WIFI_PIN_CHANNEL : 11;

void runWiFiDiscoveryScan(const char* label, bool passive, uint32_t dwellMs, uint8_t channel) {
  // Only the network task waits. No credentials/SSID/BSSID filters are supplied.
  const int statusBefore=WiFi.status();
  const auto beforeEvent=snapshotWiFiScanEvent();
  Serial.printf("[WIFI SCAN %s] Starting mode=%s channel=%u dwell_ms=%lu before association\n",
      label,passive?"passive":"active",channel,static_cast<unsigned long>(dwellMs));
  const uint32_t started=millis();
  const int16_t result=WiFi.scanNetworks(false,true,passive,dwellMs,channel);
  Serial.printf("[WIFI SCAN %s] result=%d elapsed_ms=%lu wifi_status_before=%d after=%d\n",
      label,result,static_cast<unsigned long>(millis()-started),statusBefore,WiFi.status());
  if (result<0) {
    Serial.printf("[WIFI SCAN %s] %s; discovery unknown (not a zero-network result)\n",
        label,result==WIFI_SCAN_RUNNING?"scan still running":"scan failed or timed out");
    const esp_err_t stopped=esp_wifi_scan_stop();
    Serial.printf("[WIFI SCAN %s] scan_stop=%d (%s)\n",label,static_cast<int>(stopped),esp_err_to_name(stopped));
    // Allow a stopped scan's framework SCAN_DONE handler to finish before the
    // next scan. It clears the Arduino scanning flag and owns result collection.
    for (unsigned waitMs=0;waitMs<250 && WiFi.scanComplete()==WIFI_SCAN_RUNNING;waitMs+=10) {
      vTaskDelay(pdMS_TO_TICKS(10));
    }
    Serial.printf("[WIFI SCAN %s] cleanup_scan_state=%d (-1 means still running)\n",label,WiFi.scanComplete());
  }
  // Arduino signals scan completion before invoking application callbacks.
  // Give that callback a bounded chance to record the raw driver event status.
  for (unsigned waitMs=0;waitMs<100 && snapshotWiFiScanEvent().events==beforeEvent.events;waitMs+=10) {
    vTaskDelay(pdMS_TO_TICKS(10));
  }
  const auto done=snapshotWiFiScanEvent();
  if (done.events!=beforeEvent.events) {
    Serial.printf("[WIFI SCAN %s] completion_events=%lu driver_status=%lu (0=success; nonzero=failure) event_APs=%u scan_id=%u cleanup_requested=%u\n",
        label,static_cast<unsigned long>(done.events-beforeEvent.events),static_cast<unsigned long>(done.status),done.number,done.id,result<0);
    if (done.status!=0) Serial.printf("[WIFI SCAN %s] Results may be partial; absent targets are inconclusive\n",label);
  } else {
    Serial.printf("[WIFI SCAN %s] driver completion event not observed within 100 ms; completion status unknown\n",label);
  }
  if (result>=0) {
    Serial.printf("[WIFI SCAN %s] Networks detected: %d (includes hidden APs)\n",label,result);
    bool ssidFound=false,bssidFound=false,pairFound=false;
    unsigned channelCount=0,missingRecords=0;
    const bool trustworthy=done.events!=beforeEvent.events && done.status==0;
    // getScanInfoByIndex accepts an int, unlike SSID()/RSSI()'s uint8_t index.
    // Inspect every result even if more than 256 AP records are returned.
    for (int i=0;i<result;++i) {
      const auto* ap=static_cast<const wifi_ap_record_t*>(WiFi.getScanInfoByIndex(i));
      if (ap==nullptr) {++missingRecords;continue;}
      Serial.printf("[WIFI SCAN %s] AP #%d channel=%u RSSI=%d dBm\n",label,i+1,ap->primary,ap->rssi);
      if (ap->primary==WIFI_DISCOVERY_CHANNEL) ++channelCount;
      const auto comparison=compareToConfiguredSsid(ap->ssid);
      const bool ssidMatch=comparison==SsidComparison::Exact;
      const bool bssidMatch=isPinnedBssid(ap->bssid);
      if (bssidMatch) inspectPinnedSsid(label,*ap,trustworthy);
      else if (comparison==SsidComparison::TrailingWhitespaceOnly || comparison==SsidComparison::CaseOnly)
        Serial.printf("[WIFI SSID %s] AP #%d near match: %s; never adopted\n",label,i+1,ssidComparisonName(comparison));
      ssidFound|=ssidMatch;bssidFound|=bssidMatch;pairFound|=ssidMatch && bssidMatch;
      if (!ssidMatch && !bssidMatch) continue;
      // Matching records report signal and security only: no name, no hardware address.
      Serial.printf("[WIFI SCAN %s] Configured network record: SSID_match=%u BSSID_match=%s RSSI=%d dBm channel=%u auth=%d (%s)\n",
          label,ssidMatch,WIFI_PIN_CONFIGURED?(bssidMatch?"1":"0"):"n/a",ap->rssi,ap->primary,
          static_cast<int>(ap->authmode),wifiAuthenticationName(ap->authmode));
    }
    Serial.printf("[WIFI SCAN %s] Channel %u APs visible=%u missing_records=%u\n",label,WIFI_DISCOVERY_CHANNEL,channelCount,missingRecords);
    Serial.printf("[WIFI SCAN %s] Configured network: SSID=%s BSSID=%s same_AP=%s\n",label,ssidFound?"FOUND":"NOT SEEN",
        WIFI_PIN_CONFIGURED?(bssidFound?"FOUND":"NOT SEEN"):"NOT PINNED",WIFI_PIN_CONFIGURED?(pairFound?"FOUND":"NOT SEEN"):"n/a");
  }
  WiFi.scanDelete(); // Release diagnostic result memory; never erase NVS.
}

void discoverWiFiOnce(bool stationReady) {
  if (wifiDiscoveryDone) return;
  wifiDiscoveryDone=true;
  Serial.printf("[WIFI SCAN] ESP32 STA MAC: %s\n",WiFi.macAddress().c_str());
  if (!stationReady) {
    Serial.println("[WIFI SCAN] SKIPPED: station initialization failed; discovery unknown");
    return;
  }
  wifi_country_t country{};
  const esp_err_t countryResult=esp_wifi_get_country(&country);
  Serial.printf("[WIFI SCAN] get_country=%d (%s)\n",static_cast<int>(countryResult),esp_err_to_name(countryResult));
  bool channelAllowed=true; // If query fails, the driver still enforces its range.
  if (countryResult==ESP_OK) {
    const unsigned lastChannel=country.nchan?country.schan+country.nchan-1:0;
    channelAllowed=country.nchan && country.schan<=WIFI_DISCOVERY_CHANNEL && lastChannel>=WIFI_DISCOVERY_CHANNEL;
    Serial.printf("[WIFI SCAN] country=%.3s start_channel=%u channel_count=%u last_channel=%u policy=%d (%s) channel%u_in_range=%u\n",
        country.cc,country.schan,country.nchan,lastChannel,static_cast<int>(country.policy),
        country.policy==WIFI_COUNTRY_POLICY_AUTO?"AUTO":"MANUAL",WIFI_DISCOVERY_CHANNEL,channelAllowed);
  }
  // All scans complete before the retry loop and its first WiFi.begin/MQTT call.
  // Sensor work stays on the Arduino task; country/settings are never changed.
  char activeLabel[16],passiveLabel[17];
  snprintf(activeLabel,sizeof(activeLabel),"CH%u-ACTIVE",WIFI_DISCOVERY_CHANNEL);
  snprintf(passiveLabel,sizeof(passiveLabel),"CH%u-PASSIVE",WIFI_DISCOVERY_CHANNEL);
  runWiFiDiscoveryScan("FULL",false,300,0);
  if (channelAllowed) {
    runWiFiDiscoveryScan(activeLabel,false,600,WIFI_DISCOVERY_CHANNEL);
    runWiFiDiscoveryScan(passiveLabel,true,1000,WIFI_DISCOVERY_CHANNEL);
  } else {
    Serial.printf("[WIFI SCAN] Channel %u scans SKIPPED: outside configured country range; settings unchanged\n",WIFI_DISCOVERY_CHANNEL);
  }
  Serial.printf("[WIFI ASSOC] Pinned BSSID diagnostic=%s; nonempty mismatching SSID is never adopted\n",
      !WIFI_PIN_CONFIGURED?"not configured (normal association)":wifiPinEligible && !wifiPinSsidMismatch?"eligible":"withheld");
  Serial.println("[WIFI SCAN] Discovery finished; proceeding to normal connection attempts (no rescan)");
}

void depthAcknowledgement(char*,uint8_t*,unsigned int);

void initializeNetwork() {
  Serial.println("[NET] Network task started on core 0; sensor loop remains independent");
  WiFi.onEvent(wifiDiagnosticEvent);
  // Nonblocking SNTP. Until synchronized, water samples cannot restore LIVE.
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  const bool wifiModeReady=WiFi.mode(WIFI_STA);
  Serial.printf("[WIFI] STA initialization: %s\n",wifiModeReady?"OK":"FAILED; subsequent begin attempts will retry STA enable");
  discoverWiFiOnce(wifiModeReady);
#if AGAPAY_RELEASE_BUILD
  networkClient.setCACert(MQTT_ROOT_CA);
  networkClient.setHandshakeTimeout(5);
  Serial.println("[NET] RELEASE: CA and broker hostname validation required; TLS handshake budget 5s");
#else
  Serial.println("[NET] LOCAL DEVELOPMENT ONLY: plaintext transport; never expose this listener");
#endif
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  mqttBufferReady=mqttClient.setBufferSize(2048);
  Serial.printf("[MQTT] Broker %s:%d buffer=%s callback=depth+rain ACK socket_timeout=1s keepalive=15s\n",
      MQTT_HOST,MQTT_PORT,mqttBufferReady?"1024 bytes":"FAILED (MQTT disabled; check memory)");
  mqttClient.setCallback(depthAcknowledgement);
  mqttClient.setSocketTimeout(1);
  mqttClient.setKeepAlive(15);
  lastWifiAttemptMs = millis() - WIFI_RETRY_MS;
  lastMqttAttemptMs = millis() - MQTT_RETRY_MS;
}

// Runs independently of DNS/TCP/MQTT. The single-item handoff is sampled at
// the declared journal cadence; any missed handoff is counted, never invented.
void depthJournalTask(void*) {
  DepthStorage storage;
  if (!storage.begin()) {
    Serial.println("[DEPTH HISTORY] UNAVAILABLE: filesystem absent/unmounted; no auto-format; sensing continues");
    vTaskDelete(nullptr);return;
  }
  DepthJournal<DepthStorage> journal(storage);journal.restore();
  uint32_t lastStatus=0;
  for (;;) {
    TelemetryReport report;
    if (xQueueReceive(depthQueue,&report,0)==pdTRUE) {
      JsonDocument observation;buildDepthObservation(observation.to<JsonObject>(),report);
      char json[1100];
      if (measureJson(observation)<sizeof(json)) {
        serializeJson(observation,json,sizeof(json));
        journal.append(json,AGAPAY_CONFIG_VERSION,report.bootSequence,report.sequence);
      } else ++journal.writeFailures;
    }
    DepthRecord record{};
    if (xQueueReceive(depthAckQueue,&record,0)==pdTRUE) journal.acknowledge(record);
    if (journal.oldest(record)) xQueueOverwrite(depthReplayQueue,&record);
    if (static_cast<uint32_t>(millis()-lastStatus)>=30000) {
      lastStatus=millis();
      Serial.printf("[DEPTH HISTORY] pending=%u capacity=%u cadence_ms=%lu evicted=%llu corrupt=%llu failed_writes=%llu handoff_gaps=%lu; historical replay only\n",
        journal.pending(),DEPTH_HISTORY_SLOTS,static_cast<unsigned long>(DEPTH_HISTORY_CADENCE_MS),
        static_cast<unsigned long long>(journal.evicted),static_cast<unsigned long long>(journal.corrupt),
        static_cast<unsigned long long>(journal.writeFailures),static_cast<unsigned long>(depthHandoffGaps));
    }
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

#if AGAPAY_OLED
// Advisory forecast for the OLED only. Validated (station, applied configuration hash,
// schema, bounds, expiry) before display; never touches the tier, LEDs, buzzer or telemetry.
void maintainForecastSubscription(uint32_t now) {
  if (forecastSubscribed || !mqttClient.connected() || static_cast<uint32_t>(now-lastForecastSubscribeMs)<MQTT_RETRY_MS) return;
  lastForecastSubscribeMs=now;
  char topic[96];snprintf(topic,sizeof(topic),"agapay/stations/%s/forecast",STATION_ID);
  forecastSubscribed=mqttClient.subscribe(topic,1);
}

bool handleForecastMessage(const char* topic,const uint8_t* payload,unsigned int length) {
  char expected[96];snprintf(expected,sizeof(expected),"agapay/stations/%s/forecast",STATION_ID);
  if (strcmp(topic,expected)!=0) return false;
  struct timeval utc{};gettimeofday(&utc,nullptr);
  const oled::ForecastView view=forecast::parse(payload,length,STATION_ID,APPLIED_CONFIG_HASH,millis(),static_cast<int64_t>(utc.tv_sec));
  oledPublishForecast(view);
  Serial.printf("[FORECAST] advisory status=%s points=%u valid_ms=%lu %s(alarms unaffected)\n",
      view.state==oled::ForecastState::REJECTED?"rejected":view.status,static_cast<unsigned>(view.count),
      static_cast<unsigned long>(view.lifetimeMs),view.state==oled::ForecastState::REJECTED?view.rejected:"");
  return true;
}
#endif

void depthAcknowledgement(char* topic,uint8_t* payload,unsigned int length) {
#if AGAPAY_OLED
  if (handleForecastMessage(topic,payload,length)) return;
#endif
  char expected[100];snprintf(expected,sizeof(expected),"agapay/stations/%s/telemetry-ack",STATION_ID);
  if (strcmp(topic,expected)!=0) {rainAcknowledgement(topic,payload,length);return;}
  if (!depthInFlightReady || length>1536) return;
  JsonDocument ack;if (deserializeJson(ack,payload,length)) return;
  JsonDocument original;if (deserializeJson(original,depthInFlight.json)) return;
  if (!ack["telemetry"].is<JsonObjectConst>() ||
      ack["telemetry"].as<JsonObjectConst>()!=original.as<JsonObjectConst>()) return;
  char bootId[80];snprintf(bootId,sizeof(bootId),"%s-%lu",STATION_ID,static_cast<unsigned long>(depthInFlight.boot));
  if (!ack["persisted"].is<bool>() || !ack["persisted"].as<bool>() ||
      strcmp(ack["station_id"]|"",STATION_ID)!=0 || strcmp(ack["boot_id"]|"",bootId)!=0 ||
      !ack["sequence_no"].is<uint64_t>() || ack["sequence_no"].as<uint64_t>()!=depthInFlight.sequence ||
      !ack["config_version"].is<uint32_t>() || ack["config_version"].as<uint32_t>()!=depthInFlight.config) return;
  if (depthAckQueue) xQueueOverwrite(depthAckQueue,&depthInFlight);
  depthInFlightReady=false;
}

void deliverDepthHistory(uint32_t now) {
  if (!depthReplayQueue || !stationCredentialReady() || !mqttClient.connected()) return;
  if (!depthAckSubscribed) {
    char ackTopic[100];snprintf(ackTopic,sizeof(ackTopic),"agapay/stations/%s/telemetry-ack",STATION_ID);
    depthAckSubscribed=mqttClient.subscribe(ackTopic,1);
    if (!depthAckSubscribed) return;
  }
  // At most 60 replays/min + 30 live/min, below the shared 120/min budget.
  if (static_cast<uint32_t>(now-lastDepthReplayMs)<1000) return;
  lastDepthReplayMs=now;
  if (xQueueReceive(depthReplayQueue,&depthInFlight,0)!=pdTRUE) return;
  JsonDocument envelope;
  JsonDocument observation;
  if (deserializeJson(observation,depthInFlight.json)) return;
  envelope["telemetry"].set(observation);
  envelope["delivery_mode"]="backfill";envelope["ingest_token"]=STATION_INGEST_TOKEN;
  char payload[1536];if (measureJson(envelope)>=sizeof(payload)) return;
  serializeJson(envelope,payload,sizeof(payload));
  char topic[100];snprintf(topic,sizeof(topic),"agapay/stations/%s/telemetry",STATION_ID);
  depthInFlightReady=true;
  mqttClient.publish(topic,payload,false); // Only application ACK removes a slot.
}

void networkTask(void*) {
  // PubSubClient connect()/loop()/publish() are synchronous, even with timed
  // retries. Only this task owns the clients; DNS/TCP/MQTT waits cannot block
  // the sensor loop or local LEDs/buzzer on the main Arduino task.
  initializeNetwork();
  for (;;) {
    maintainWiFiNonBlocking(millis());
    maintainMqttNonBlocking(millis());
    if (mqttClient.connected()) mqttClient.loop();
    maintainRainAckSubscription(millis());
#if AGAPAY_OLED
    maintainForecastSubscription(millis());
#endif
    publishRainSnapshot(millis());
    deliverLatestReport();
    deliverDepthHistory(millis());
    const uint32_t now=millis();
#if AGAPAY_OLED
    static uint32_t lastOledNetworkMs=0;
    if (static_cast<uint32_t>(now-lastOledNetworkMs)>=500) {
      lastOledNetworkMs=now;
      const bool wifiUp=WiFi.status()==WL_CONNECTED;
      char ip[16]="";
      if (wifiUp) {
        const IPAddress address=WiFi.localIP();
        snprintf(ip,sizeof(ip),"%u.%u.%u.%u",address[0],address[1],address[2],address[3]);
      }
      oledPublishNetwork(wifiUp,mqttClient.connected(),static_cast<int16_t>(wifiUp?WiFi.RSSI():0),ip);
    }
#endif
    if (static_cast<uint32_t>(now-lastNetworkHealthMs)>=30000) {
      lastNetworkHealthMs=now;
      Serial.printf("[NET] alive uptime_ms=%lu wifi=%d mqtt=%d state=%d stack_free_bytes=%lu\n",
          static_cast<unsigned long>(now),WiFi.status(),mqttClient.connected(),mqttClient.state(),
          static_cast<unsigned long>(uxTaskGetStackHighWaterMark(nullptr)));
    }
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

void setup() {
  Serial.begin(115200);
  Serial.printf("[BOOT] build=%s %s reset_reason=%d (1=POWERON 3=SW 4=PANIC 6=TASK_WDT 7=WDT 9=BROWNOUT)\n",
      __DATE__,__TIME__,static_cast<int>(esp_reset_reason()));
  pinMode(TRIG_PIN, OUTPUT);
  digitalWrite(TRIG_PIN, LOW);
  pinMode(ECHO_PIN, INPUT);
  // Set OFF before enabling the active-low buzzer output.
  digitalWrite(BUZZER_PIN, BUZZER_OFF_LEVEL);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  applyLocalAlert(currentTier);
  restoreRainCounter();
  pinMode(RAIN_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(RAIN_PIN), rainTipISR, FALLING);
  sequenceReady = reserveSequenceBlock();
  if (!sequenceReady) Serial.println("NVS sequence reservation failed: telemetry disabled, local sensing continues");
  lastPublishMs = millis();
  lastSensorMs = millis() - SENSOR_INTERVAL_MS;
  reportQueue = xQueueCreate(1, sizeof(TelemetryReport));
  rainQueue = xQueueCreate(1,sizeof(RainSnapshot));
  const bool queuesReady=reportQueue != nullptr && rainQueue != nullptr;
  const bool taskReady=queuesReady && xTaskCreatePinnedToCore(networkTask, "agapay-network", 6144, nullptr, 1, nullptr, 0) == pdPASS;
  depthQueue=xQueueCreate(1,sizeof(TelemetryReport));
  depthReplayQueue=xQueueCreate(1,sizeof(DepthRecord));
  depthAckQueue=xQueueCreate(1,sizeof(DepthRecord));
  if (depthQueue && depthReplayQueue && depthAckQueue) {
    if (xTaskCreatePinnedToCore(depthJournalTask,"depth-journal",12288,nullptr,1,nullptr,0)!=pdPASS) {
      vQueueDelete(depthQueue);vQueueDelete(depthReplayQueue);vQueueDelete(depthAckQueue);
      depthQueue=nullptr;depthReplayQueue=nullptr;depthAckQueue=nullptr;
      Serial.println("[DEPTH HISTORY] journal task unavailable; sensing continues");
    }
  } else {
    if(depthQueue) vQueueDelete(depthQueue);
    if(depthReplayQueue) vQueueDelete(depthReplayQueue);
    if(depthAckQueue) vQueueDelete(depthAckQueue);
    depthQueue=nullptr;depthReplayQueue=nullptr;depthAckQueue=nullptr;
    Serial.println("[DEPTH HISTORY] queue allocation failed; sensing continues");
  }
  Serial.printf("[NET] report_queue=%s rain_queue=%s task=%s\n",reportQueue?"OK":"FAILED",rainQueue?"OK":"FAILED",taskReady?"created":"unavailable");
  if (!taskReady) {
    Serial.println("[NET] Queue allocation or network task creation FAILED: local sensing continues");
    if (reportQueue != nullptr) vQueueDelete(reportQueue);
    reportQueue = nullptr;
    if (rainQueue != nullptr) vQueueDelete(rainQueue);
    rainQueue = nullptr;
  }
  Serial.println("AGAPAY 0.2.0 physical sensors: CALIBRATION REQUIRED (height, range, mm/tip, DEPTH thresholds)");
  Serial.printf("Local tiers: UNKNOWN=0 NORMAL=1 ADVISORY=2 WARNING=3 EVACUATE=4; transport=%s\n",AGAPAY_RELEASE_BUILD?"validated TLS":"development plaintext MQTT");
  Serial.printf("[LOCAL PROFILE] boot_mode=%s; runtime overrides reset on reboot; sensor depth and backend thresholds unchanged\n",
      DEFAULT_LOCAL_BENCH_ALERTS ? "BENCH DISTANCE (cardboard demo only)" : "DEPTH");
  Serial.printf("[CADENCE] sensor_ms=%lu telemetry_ms=%lu; physical rain uses its independent cumulative feed\n",
      static_cast<unsigned long>(SENSOR_INTERVAL_MS),static_cast<unsigned long>(PUBLISH_INTERVAL_MS));
  Serial.println("[LOCAL COMMAND] Serial newline: ALERT STATUS / ALERT TEST / ALERT STOP / ALERT DEMO ON / ALERT DEMO OFF");
  printLocalAlertStatus();
#if AGAPAY_OLED
  oledBegin();  // Display task on core 0; sensing and alarms never wait for it.
#endif
}

#if AGAPAY_OLED
// Read-only snapshot for the display: the same tier that drives LEDs/buzzer, the latest
// sample and its fault, the durable rain counter and the compiled configuration.
void publishOled(uint32_t now) {
  static uint64_t lastSampleSeen = 0;
  static bool everValid = false;
  static uint32_t lastValidMs = 0;
  static float lastValidDepthCm = NAN, lastValidDistanceCm = NAN;
  static uint32_t lastPublishOledMs = 0;
  if (latestSample.uptimeMs != lastSampleSeen) {
    lastSampleSeen = latestSample.uptimeMs;
    if (latestSample.sensorValid) {
      everValid = true;
      lastValidMs = static_cast<uint32_t>(latestSample.uptimeMs);
      lastValidDepthCm = latestSample.waterDepthCm;
      lastValidDistanceCm = lastAcceptedDistanceCm;
    }
  }
  if (static_cast<uint32_t>(now - lastPublishOledMs) < 100) return;
  lastPublishOledMs = now;
  oled::Inputs in;
  in.localTier = static_cast<oled::Tier>(static_cast<uint8_t>(currentLocalTier));
  in.benchProfile = localBenchAlerts;
  in.prototypeGeometry = OLED_PROTOTYPE_GEOMETRY;
  in.anySample = latestSample.uptimeMs != 0;
  in.sampleValid = latestSample.sensorValid;
  in.sampleMs = static_cast<uint32_t>(latestSample.uptimeMs);
  in.everValid = everValid;
  in.lastValidMs = lastValidMs;
  in.lastValidDepthCm = lastValidDepthCm;
  in.lastValidDistanceCm = lastValidDistanceCm;
  in.sensorFault = latestSample.sensorFault;
  in.outputSelfTest = localOutputTestActive;
  portENTER_CRITICAL(&rainMux);
  in.rainLifetimeTips = rainLifetimeTips;
  const uint64_t lastTip = rainLastTipUptimeMs;
  portEXIT_CRITICAL(&rainMux);
  in.rainBootTips = rainBootStartTips;
  in.rainPersistenceOk = rainPersistenceReady && !rainPersistenceWarning;
  in.rainTipSinceBoot = in.rainLifetimeTips > rainBootStartTips && lastTip != 0;
  in.rainLastTipMs = static_cast<uint32_t>(lastTip);
  in.stationId = STATION_ID;
  in.firmwareVersion = FIRMWARE_VERSION;
  in.configRevision = INSTALLATION_REVISION;
  in.sensorHeightCm = SENSOR_HEIGHT_CM;
  in.minDistanceCm = MIN_DISTANCE_CM;
  in.advisoryCm = THRESHOLD_ADVISORY_CM;
  in.warningCm = THRESHOLD_WARNING_CM;
  in.evacuateCm = THRESHOLD_EVACUATE_CM;
  in.benchAdvisoryCm = BENCH_ADVISORY_DISTANCE_CM;
  in.benchWarningCm = BENCH_WARNING_DISTANCE_CM;
  in.benchRedCm = BENCH_RED_DISTANCE_CM;
  in.mmPerTip = RAIN_MM_PER_TIP;
  oledPublishLocal(in);
}
#endif

void loop() {
  sampleSensors(millis());
  const uint32_t now = millis();
  updateRainState(now);
  serviceLocalAlertDiagnostics(now);
  serviceSensorFault(now);
  serviceWarningBlink(now);
#if AGAPAY_OLED
  publishOled(now);
#endif
  if (static_cast<uint32_t>(now - lastPublishMs) >= PUBLISH_INTERVAL_MS) {
    lastPublishMs = now;
    TelemetryReport report{};
    report.sample = latestSample;
    report.rainfallMm = snapshotRainfallInterval();
    report.uptimeMs = now;
    // The live two-second stream and the durable ten-second stream have
    // independent retention. Legacy rainfall windows cannot discard water history.
    if (nextSequenceNumber(report.sequence)) {
      report.bootSequence = telemetryBootSequence;
      if (!isfinite(report.rainfallMm) || report.rainfallMm < 0 || report.rainfallMm > 1000) {
        Serial.println("Rain interval outside contract range: live report dropped; depth journal independent");
      } else if (reportQueue) {
        if (uxQueueMessagesWaiting(reportQueue) != 0) Serial.println("Network busy: replacing an unsent interval");
        xQueueOverwrite(reportQueue, &report);
      }
      if (static_cast<uint32_t>(now-lastDepthQueueMs)>=DEPTH_HISTORY_CADENCE_MS) {
        lastDepthQueueMs=now;
        if (depthQueue) {
          if (uxQueueMessagesWaiting(depthQueue)) ++depthHandoffGaps;
          xQueueOverwrite(depthQueue,&report);
        } else ++depthHandoffGaps;
      }
    }
  }
  delay(1); // Yield to ESP32 tasks; no sensor-spacing or reconnect delay loop.
}
