// UNVALIDATED BENCH GEOMETRY: 65 cm cardboard rig. Exercise thresholds only; not San Vicente river thresholds.
// Generated from a reviewed API configuration; do not edit individual values.
#pragma once
constexpr char CONFIGURED_STATION_ID[] = "STATION_001";
constexpr char APPLIED_CONFIG_HASH[] = "198f54baa791602e1db4178dc104a229add527c35fe359d658dc4f6c389d7610";
constexpr unsigned INSTALLATION_REVISION = 2;
// Validation evidence remains in the backend; a hash does not prove physical calibration.
constexpr float SENSOR_HEIGHT_CM = 65.0F;
constexpr float MIN_DISTANCE_CM = 20.0F;
constexpr float MAX_DISTANCE_CM = 450.0F;
constexpr float SENSOR_UNCERTAINTY_CM = 2.0F;
constexpr float RANGE_MARGIN_CM = 5.0F;
constexpr float THRESHOLD_ADVISORY_CM = 15.0F;
constexpr float THRESHOLD_WARNING_CM = 25.0F;
constexpr float THRESHOLD_EVACUATE_CM = 35.0F;
constexpr float RAIN_MM_PER_TIP = 0.7F;
