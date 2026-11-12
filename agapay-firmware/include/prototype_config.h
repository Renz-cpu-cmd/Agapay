// UNVALIDATED BENCH GEOMETRY: 150 cm datum, not the existing 120 cm installation.
// Generated from a reviewed API configuration; do not edit individual values.
#pragma once
constexpr char CONFIGURED_STATION_ID[] = "STATION_001";
constexpr char APPLIED_CONFIG_HASH[] = "c5eed6b3f6b820c6a77342c4e30b64cbd9c46657eec086e115b5fff590d7557b";
constexpr unsigned INSTALLATION_REVISION = 1;
// Validation evidence remains in the backend; a hash does not prove physical calibration.
constexpr float SENSOR_HEIGHT_CM = 150.0F;
constexpr float MIN_DISTANCE_CM = 20.0F;
constexpr float MAX_DISTANCE_CM = 450.0F;
constexpr float SENSOR_UNCERTAINTY_CM = 2.0F;
constexpr float RANGE_MARGIN_CM = 5.0F;
constexpr float THRESHOLD_ADVISORY_CM = 60.0F;
constexpr float THRESHOLD_WARNING_CM = 85.0F;
constexpr float THRESHOLD_EVACUATE_CM = 100.0F;
constexpr float RAIN_MM_PER_TIP = 0.7F;
