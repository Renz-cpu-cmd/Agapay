// AGAPAY Day 1: ArduinoJson + PubSubClient compile and telemetry-format check

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

WiFiClient networkClient;
PubSubClient mqttClient(networkClient);

void setup() {
  Serial.begin(115200);
  delay(1000);

  mqttClient.setServer("127.0.0.1", 1883);

  JsonDocument telemetry;
  telemetry["station_id"] = "STATION_001";
  telemetry["sequence_no"] = 1;
  telemetry["water_depth_cm"] = 42.7;
  telemetry["rainfall_mm"] = 0.70;
  telemetry["sensor_quality"] = "valid";
  telemetry["device_uptime_ms"] = millis();
  telemetry["firmware_version"] = "0.1.0";

  Serial.println("Both required libraries compiled successfully.");
  serializeJson(telemetry, Serial);
  Serial.println();
}

void loop() {
  // No broker connection is required for this compile/format test.
}
