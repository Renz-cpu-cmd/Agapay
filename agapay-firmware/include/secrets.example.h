#pragma once

// Copy this file to secrets.h, replace every placeholder, and never commit secrets.h.
constexpr char WIFI_SSID[] = "YOUR_WIFI_NAME";
constexpr char WIFI_PASSWORD[] = "YOUR_WIFI_PASSWORD";

// Use localhost/private infrastructure when possible. Public anonymous brokers are
// permitted only for temporary, non-sensitive dummy-data development.
constexpr char MQTT_HOST[] = "YOUR_MQTT_HOST";
constexpr int MQTT_PORT = 1883;
constexpr char MQTT_USERNAME[] = "";
constexpr char MQTT_PASSWORD[] = "";
