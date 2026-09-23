// Canonical AGAPAY physical-sensor firmware. Calibration is still provisional.
#include <Arduino.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>
#include <math.h>
#include <stdint.h>

#if __has_include("secrets.h")
#include "secrets.h"
#else
#error "Copy include/secrets.example.h to include/secrets.h and configure locally."
#endif

constexpr uint8_t TRIG_PIN = 5;
constexpr uint8_t ECHO_PIN = 18;
constexpr uint8_t RAIN_PIN = 4;
constexpr uint8_t BUZZER_PIN = 25;
constexpr uint8_t LED_GREEN = 26;
constexpr uint8_t LED_YELLOW = 27;
constexpr uint8_t LED_RED = 14;
constexpr char STATION_ID[] = "STATION_001";
constexpr char FIRMWARE_VERSION[] = "0.2.0";

// DEVELOPMENT calibration only: measure mounting height above the depth datum,
// verify delivered gauge volume per tip, sensor range, and site flood thresholds.
constexpr float SENSOR_HEIGHT_CM = 120.0F;
constexpr float MIN_DISTANCE_CM = 20.0F;
constexpr float MAX_DISTANCE_CM = 450.0F;
constexpr float RAIN_MM_PER_TIP = 0.70F;
// Use the backend's provisional DEPTH defaults, not the sketch's distance tiers.
constexpr float THRESHOLD_ADVISORY_CM = 60.0F;
constexpr float THRESHOLD_WARNING_CM = 85.0F;
constexpr float THRESHOLD_EVACUATE_CM = 100.0F;
constexpr uint32_t RAIN_DEBOUNCE_US = 50000;
constexpr uint32_t ECHO_TIMEOUT_US = 30000;
constexpr uint32_t SENSOR_INTERVAL_MS = 1000;
constexpr uint32_t PING_SPACING_MS = 60;
constexpr uint32_t PUBLISH_INTERVAL_MS = 10000;
constexpr uint32_t WIFI_RETRY_MS = 10000;
constexpr uint32_t MQTT_RETRY_MS = 5000;
constexpr uint64_t SEQUENCES_PER_BOOT = 1000000ULL;
static_assert(SENSOR_HEIGHT_CM > 0 && SENSOR_HEIGHT_CM <= 1000, "Invalid mounting height");
static_assert(RAIN_MM_PER_TIP > 0, "Rain calibration must be positive");
static_assert(THRESHOLD_ADVISORY_CM < THRESHOLD_WARNING_CM &&
    THRESHOLD_WARNING_CM < THRESHOLD_EVACUATE_CM, "Depth thresholds must be ordered");

// UNKNOWN means no trustworthy measurement has been obtained since boot.
enum class AlertTier { UNKNOWN, NORMAL, ADVISORY, WARNING, EVACUATE };
struct TelemetrySample {
  float waterDepthCm = NAN;
  bool sensorValid = false;
};
struct TelemetryReport {
  TelemetrySample sample;
  float rainfallMm;
  uint64_t sequence;
  uint32_t uptimeMs;
};

WiFiClient networkClient;
PubSubClient mqttClient(networkClient);
Preferences preferences;
QueueHandle_t reportQueue = nullptr;
portMUX_TYPE rainMux = portMUX_INITIALIZER_UNLOCKED;
volatile uint32_t rainTipCount = 0;
volatile uint32_t lastRainInterruptUs = 0;
volatile bool rainTipSeen = false;
TelemetrySample latestSample;
AlertTier currentTier = AlertTier::UNKNOWN;
uint64_t sequenceNo = 0;
uint64_t sequenceLimit = 0;
bool sequenceReady = false;
uint32_t lastPublishMs = 0;
uint32_t lastSensorMs = 0;
uint32_t lastPingMs = 0;
uint32_t lastWifiAttemptMs = 0;
uint32_t lastMqttAttemptMs = 0;
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
    lastRainInterruptUs = nowUs;
    rainTipSeen = true;
  }
  portEXIT_CRITICAL_ISR(&rainMux);
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
  if (duration == 0) return false;
  distanceCm = duration * 0.0343F / 2.0F;
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

void applyLocalAlert(AlertTier tier) {
  digitalWrite(LED_GREEN, tier == AlertTier::NORMAL ? HIGH : LOW);
  digitalWrite(LED_YELLOW, tier == AlertTier::ADVISORY || tier == AlertTier::WARNING ? HIGH : LOW);
  digitalWrite(LED_RED, tier == AlertTier::EVACUATE ? HIGH : LOW);
  // The installed buzzer is LOW-triggered.
  digitalWrite(BUZZER_PIN, tier == AlertTier::EVACUATE ? LOW : HIGH);
}

void finishSensorSample() {
  float distanceCm = NAN;
  latestSample.sensorValid = measureDistanceMedian(distanceSamples, validSamples, distanceCm)
      && calculateWaterDepth(distanceCm, latestSample.waterDepthCm);
  if (latestSample.sensorValid) {
    currentTier = classifyAlert(latestSample.waterDepthCm);
    applyLocalAlert(currentTier);
  } else {
    latestSample.waterDepthCm = NAN;
    // Keep the previous valid outputs. At boot UNKNOWN stays unlit, not NORMAL.
    Serial.println("[SENSOR] INVALID: retaining previous local state (UNKNOWN if no valid sample)");
  }
  Serial.printf("[CALIBRATION REQUIRED] distance=%.2f cm depth=%.2f cm valid=%u tier=%u\n",
      distanceCm, latestSample.waterDepthCm, latestSample.sensorValid, static_cast<unsigned>(currentTier));
}

void sampleSensors(uint32_t now) {
  if (!sampling && static_cast<uint32_t>(now - lastSensorMs) >= SENSOR_INTERVAL_MS) {
    lastSensorMs = now;
    attemptedSamples = validSamples = 0;
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

void maintainWiFiNonBlocking(uint32_t now) {
  if (WiFi.status() == WL_CONNECTED || static_cast<uint32_t>(now - lastWifiAttemptMs) < WIFI_RETRY_MS) return;
  lastWifiAttemptMs = now;
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

void maintainMqttNonBlocking(uint32_t now) {
  if (WiFi.status() != WL_CONNECTED || mqttClient.connected()) return;
  if (static_cast<uint32_t>(now - lastMqttAttemptMs) < MQTT_RETRY_MS) return;
  lastMqttAttemptMs = now;
  char clientId[80];
  snprintf(clientId, sizeof(clientId), "AGAPAY_%s_%llX", STATION_ID,
      static_cast<unsigned long long>(ESP.getEfuseMac()));
  const bool connected = MQTT_USERNAME[0] != '\0'
      ? mqttClient.connect(clientId, MQTT_USERNAME, MQTT_PASSWORD)
      : mqttClient.connect(clientId);
  Serial.println(connected ? "MQTT connected" : "MQTT unavailable; local sensing continues");
}

void publishTelemetry(const TelemetryReport& report) {
  JsonDocument document;
  document["station_id"] = STATION_ID;
  document["sequence_no"] = report.sequence;
  if (report.sample.sensorValid) document["water_depth_cm"] = report.sample.waterDepthCm;
  else document["water_depth_cm"] = nullptr;
  document["rainfall_mm"] = report.rainfallMm;
  document["sensor_quality"] = report.sample.sensorValid ? "valid" : "invalid";
  document["device_uptime_ms"] = report.uptimeMs;
  document["firmware_version"] = FIRMWARE_VERSION;
  char topic[96];
  snprintf(topic, sizeof(topic), "agapay/stations/%s/telemetry", STATION_ID);
  char payload[384];
  if (measureJson(document) >= sizeof(payload)) {
    Serial.println("Telemetry serialization overflow; interval dropped");
    return;
  }
  serializeJson(document, payload, sizeof(payload));
  const bool published = mqttClient.publish(topic, payload, false);
  Serial.printf("Telemetry %s: %s\n", published ? "sent (QoS 0; no backend acknowledgement)" : "FAILED; interval dropped", payload);
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

void networkTask(void*) {
  // PubSubClient connect()/loop()/publish() are synchronous, even with timed
  // retries. Only this task owns the clients; DNS/TCP/MQTT waits cannot block
  // the sensor loop or local LEDs/buzzer on the main Arduino task.
  WiFi.mode(WIFI_STA);
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  mqttClient.setBufferSize(512);
  mqttClient.setSocketTimeout(1);
  mqttClient.setKeepAlive(15);
  lastWifiAttemptMs = millis() - WIFI_RETRY_MS;
  lastMqttAttemptMs = millis() - MQTT_RETRY_MS;
  for (;;) {
    maintainWiFiNonBlocking(millis());
    maintainMqttNonBlocking(millis());
    if (mqttClient.connected()) mqttClient.loop();
    deliverLatestReport();
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  digitalWrite(TRIG_PIN, LOW);
  pinMode(ECHO_PIN, INPUT);
  // Set OFF before enabling the active-low buzzer output.
  digitalWrite(BUZZER_PIN, HIGH);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  applyLocalAlert(currentTier);
  pinMode(RAIN_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(RAIN_PIN), rainTipISR, FALLING);
  sequenceReady = reserveSequenceBlock();
  if (!sequenceReady) Serial.println("NVS sequence reservation failed: telemetry disabled, local sensing continues");
  lastPublishMs = millis();
  lastSensorMs = millis() - SENSOR_INTERVAL_MS;
  reportQueue = xQueueCreate(1, sizeof(TelemetryReport));
  if (reportQueue == nullptr || xTaskCreatePinnedToCore(networkTask, "agapay-network", 6144, nullptr, 1, nullptr, 0) != pdPASS) {
    Serial.println("Network task unavailable: local sensing continues");
    if (reportQueue != nullptr) vQueueDelete(reportQueue);
    reportQueue = nullptr;
  }
  Serial.println("AGAPAY 0.2.0 physical sensors: CALIBRATION REQUIRED (height, range, mm/tip, DEPTH thresholds)");
  Serial.println("Local tiers: UNKNOWN=0 NORMAL=1 ADVISORY=2 WARNING=3 EVACUATE=4; transport is development plaintext MQTT");
}

void loop() {
  sampleSensors(millis());
  const uint32_t now = millis();
  if (static_cast<uint32_t>(now - lastPublishMs) >= PUBLISH_INTERVAL_MS) {
    lastPublishMs = now;
    TelemetryReport report{};
    report.sample = latestSample;
    report.rainfallMm = snapshotRainfallInterval();
    report.uptimeMs = now;
    // Fixed reporting windows advance even offline. QoS 0 has no durable replay.
    if (!isfinite(report.rainfallMm) || report.rainfallMm < 0 || report.rainfallMm > 1000) {
      Serial.println("Rain interval outside contract range: report dropped; verify gauge/calibration");
    } else if (nextSequenceNumber(report.sequence) && reportQueue != nullptr) {
      if (uxQueueMessagesWaiting(reportQueue) != 0) Serial.println("Network busy: replacing an unsent interval");
      xQueueOverwrite(reportQueue, &report);
    }
  }
  delay(1); // Yield to ESP32 tasks; no sensor-spacing or reconnect delay loop.
}
