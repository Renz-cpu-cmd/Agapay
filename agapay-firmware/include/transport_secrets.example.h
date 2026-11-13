#pragma once
// Public trust anchor, obtained through a reviewed channel. This placeholder is
// deliberately incomplete: obtain the actual deployment CA before a release build.
constexpr char MQTT_ROOT_CA[] = R"PEM(
REPLACE_WITH_REVIEWED_PEM_CA_CERTIFICATE
)PEM";
