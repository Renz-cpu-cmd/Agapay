#pragma once
// Copy to ignored ingest_secrets.h and install the ONE-TIME token issued by an
// AGAPAY administrator for this commissioned station. Never use a staff session,
// MQTT password, or another station's token. Do not commit or print the real token.
constexpr char STATION_INGEST_TOKEN[] = "REPLACE_WITH_STATION_INGEST_TOKEN";
// Must match the admin-reviewed device_id and commissioning version exactly.
#define AGAPAY_DEVICE_ID "REPLACE_WITH_COMMISSIONED_DEVICE_ID"
#define AGAPAY_CONFIG_VERSION 1
