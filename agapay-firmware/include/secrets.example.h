#pragma once

// Copy this file to secrets.h, replace every placeholder, and never commit secrets.h.
constexpr char WIFI_SSID[] = "YOUR_WIFI_NAME";
constexpr char WIFI_PASSWORD[] = "YOUR_WIFI_PASSWORD";

// LOCAL DEVELOPMENT ONLY. Field builds use the separate esp32-production profile
// and release_secrets.example.h plus the reviewed CA. Never expose plaintext.
// Use a private authenticated broker. Username must equal STATION_ID so the
// supplied broker ACL binds it to this station. Broker password is separate
// from the station ingestion token in ignored ingest_secrets.h.
constexpr char MQTT_HOST[] = "YOUR_MQTT_HOST";
constexpr int MQTT_PORT = 1883;
constexpr char MQTT_USERNAME[] = "STATION_001";
constexpr char MQTT_PASSWORD[] = "REPLACE_WITH_STATION_BROKER_PASSWORD";
