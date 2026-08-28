// AGAPAY ESP32 firmware scaffold
// Day 1 uses simulated readings so the software pipeline can be tested safely.

#include <Arduino.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <PubSubClient.h>
#include <WiFi.h>

#if __has_include("secrets.h")
#include "secrets.h"
#else
#error "Copy include/secrets.example.h to include/secrets.h and replace the placeholders."
#endif

// Confirmed AGAPAY GPIO assignments.
constexpr uint8_t TRIG_PIN = 5;
constexpr uint8_t ECHO_PIN = 18;
constexpr uint8_t RAIN_PIN = 4;
constexpr uint8_t BUZZER_PIN = 25;
constexpr uint8_t LED_GREEN = 26;
constexpr uint8_t LED_YELLOW = 27;
constexpr uint8_t LED_RED = 14;

constexpr char STATION_ID[] = "STATION_001";
constexpr char FIRMWARE_VERSION[] = "0.1.0";
constexpr char MQTT_TOPIC[] = "agapay/stations/STATION_001/telemetry";

constexpr float THRESHOLD_ADVISORY_CM = 60.0F;
constexpr float THRESHOLD_WARNING_CM = 85.0F;
constexpr float THRESHOLD_EVACUATE_CM = 100.0F;
constexpr float RAIN_MM_PER_TIP = 0.70F;

constexpr unsigned long PUBLISH_INTERVAL_MS = 10000;
constexpr unsigned long WIFI_RETRY_MS = 10000;
constexpr unsigned long MQTT_RETRY_MS = 5000;

enum class AlertTier { NORMAL, ADVISORY, WARNING, EVACUATE };

struct TelemetrySample {
  float waterDepthCm;
  float rainfallMm;
  bool sensorValid;
};

WiFiClient networkClient;
PubSubClient mqttClient(networkClient);
Preferences preferences;

AlertTier currentTier = AlertTier::NORMAL;
uint64_t sequenceNo = 0;
unsigned long lastPublishMs = 0;
unsigned long lastWifiAttemptMs = 0;
unsigned long lastMqttAttemptMs = 0;

void initializeSequenceNumber() {
  preferences.begin("agapay", false);
  uint32_t bootNumber = preferences.getUInt("boot_no", 0) + 1;
  preferences.putUInt("boot_no", bootNumber);
  preferences.end();

  // Reserve one million sequence numbers per boot. This prevents ordinary
  // restarts from reusing (station_id, sequence_no) database keys.
  sequenceNo = static_cast<uint64_t>(bootNumber) * 1000000ULL;
}

TelemetrySample readSimulatedTelemetry(unsigned long now) {
  const uint32_t step = now / PUBLISH_INTERVAL_MS;
  const uint32_t position = step % 40;
  const float triangle = position <= 20 ? static_cast<float>(position)
                                        : static_cast<float>(40 - position);

  TelemetrySample sample{};
  sample.waterDepthCm = 25.0F + triangle * 4.0F;
  sample.rainfallMm = step % 5 == 0 ? RAIN_MM_PER_TIP : 0.0F;
  sample.sensorValid = step % 29 != 28;

  if (!sample.sensorValid) {
    sample.waterDepthCm = 0.0F;  // Serialized as null; this value is not published.
  }
  return sample;
}

AlertTier classifyTier(float depthCm) {
  if (depthCm >= THRESHOLD_EVACUATE_CM) return AlertTier::EVACUATE;
  if (depthCm >= THRESHOLD_WARNING_CM) return AlertTier::WARNING;
  if (depthCm >= THRESHOLD_ADVISORY_CM) return AlertTier::ADVISORY;
  return AlertTier::NORMAL;
}

void applyLocalAlert(AlertTier tier) {
  digitalWrite(LED_GREEN, tier == AlertTier::NORMAL ? HIGH : LOW);
  digitalWrite(
      LED_YELLOW,
      tier == AlertTier::ADVISORY || tier == AlertTier::WARNING ? HIGH : LOW);
  digitalWrite(LED_RED, tier == AlertTier::EVACUATE ? HIGH : LOW);
  digitalWrite(BUZZER_PIN, tier == AlertTier::EVACUATE ? HIGH : LOW);
}

void maintainWiFiNonBlocking(unsigned long now) {
  if (WiFi.status() == WL_CONNECTED) return;
  if (now - lastWifiAttemptMs < WIFI_RETRY_MS) return;

  lastWifiAttemptMs = now;
  Serial.println("Wi-Fi reconnect attempt");
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

void maintainMqttNonBlocking(unsigned long now) {
  if (WiFi.status() != WL_CONNECTED || mqttClient.connected()) return;
  if (now - lastMqttAttemptMs < MQTT_RETRY_MS) return;

  lastMqttAttemptMs = now;
  const String clientId =
      String("AGAPAY_") + STATION_ID + "_" + String(ESP.getEfuseMac(), HEX);

  bool connected = false;
  if (MQTT_USERNAME[0] != '\0') {
    connected = mqttClient.connect(
        clientId.c_str(), MQTT_USERNAME, MQTT_PASSWORD);
  } else {
    connected = mqttClient.connect(clientId.c_str());
  }

  Serial.println(connected ? "MQTT connected" : "MQTT connection failed");
}

void publishTelemetry(const TelemetrySample& sample) {
  if (!mqttClient.connected()) {
    Serial.println("MQTT offline; local alerting continues");
    return;
  }

  JsonDocument document;
  document["station_id"] = STATION_ID;
  document["sequence_no"] = ++sequenceNo;
  if (sample.sensorValid) {
    document["water_depth_cm"] = sample.waterDepthCm;
  } else {
    document["water_depth_cm"] = nullptr;
  }
  document["rainfall_mm"] = sample.rainfallMm;
  document["sensor_quality"] = sample.sensorValid ? "valid" : "invalid";
  document["device_uptime_ms"] = millis();
  document["firmware_version"] = FIRMWARE_VERSION;
  // battery_pct is intentionally absent until its measurement circuit is validated.

  char payload[384];
  const size_t bytesWritten = serializeJson(document, payload, sizeof(payload));
  const bool published = mqttClient.publish(MQTT_TOPIC, payload, false);

  Serial.printf(
      "Telemetry %s (%u bytes): %s\n",
      published ? "published" : "failed",
      static_cast<unsigned int>(bytesWritten),
      payload);
}

void setup() {
  Serial.begin(115200);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(RAIN_PIN, INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  applyLocalAlert(AlertTier::NORMAL);

  initializeSequenceNumber();
  WiFi.mode(WIFI_STA);
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  mqttClient.setBufferSize(512);

  // Make the first network attempts happen immediately without blocking setup().
  lastWifiAttemptMs = millis() - WIFI_RETRY_MS;
  lastMqttAttemptMs = millis() - MQTT_RETRY_MS;
  Serial.println("AGAPAY firmware 0.1.0 ready in simulated-sensor mode");
}

void loop() {
  const unsigned long now = millis();
  const TelemetrySample sample = readSimulatedTelemetry(now);

  // Local decisions are evaluated whether or not Wi-Fi/MQTT is available.
  if (sample.sensorValid) {
    currentTier = classifyTier(sample.waterDepthCm);
    applyLocalAlert(currentTier);
  }

  maintainWiFiNonBlocking(now);
  maintainMqttNonBlocking(now);
  if (mqttClient.connected()) mqttClient.loop();

  if (now - lastPublishMs >= PUBLISH_INTERVAL_MS) {
    lastPublishMs = now;
    publishTelemetry(sample);
  }

  delay(50);
}
