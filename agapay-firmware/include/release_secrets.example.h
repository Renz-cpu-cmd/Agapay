#pragma once
// Install from a protected per-device secret source; never share these credentials.
constexpr char WIFI_SSID[]="REPLACE_WITH_FIELD_NETWORK";
constexpr char WIFI_PASSWORD[]="REPLACE_WITH_UNIQUE_WIFI_SECRET";
// DNS name must match the broker certificate SAN. Never use an IP to bypass DNS validation.
constexpr char MQTT_HOST[]="mqtt.REPLACE_WITH_REVIEWED_DOMAIN";
constexpr int MQTT_PORT=8883;
constexpr char MQTT_USERNAME[]="REPLACE_WITH_COMMISSIONED_STATION_ID";
constexpr char MQTT_PASSWORD[]="REPLACE_WITH_UNIQUE_HIGH_ENTROPY_BROKER_PASSWORD";
