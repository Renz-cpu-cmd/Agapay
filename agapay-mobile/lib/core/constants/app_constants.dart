/// Global constants for the AGAPAY application
class AppConstants {
  static const String appName = 'AGAPAY';
  static const String appTagline = 'Community Flood & Disaster Early-Warning System';
  static const String appVersion = 'v1.0.0-beta';

  // Barangays
  static const List<String> availableBarangays = [
    'Brgy. San Nicolas',
    'Brgy. Poblacion',
    'Brgy. San Vicente',
    'Brgy. Santa Cruz',
    'Brgy. Santo Rosario',
    'Brgy. San Isidro',
  ];

  // Default coordinates (e.g., Central Luzon / Bulacan / Marikina Basin area in PH)
  static const double defaultLat = 14.7350;
  static const double defaultLng = 120.9570;

  // Emergency Hotlines
  static const String hotlineNationalEmergency = '911';
  static const String hotlineNDRRMC = '(02) 8911-5061';
  static const String hotlineRedCross = '143';
  static const String hotlineLocalBDRRMC = '(044) 791-0523';

  // Simulated Telemetry Thresholds (in cm)
  static const double defaultMaxThreshold = 100.0;
  static const double advisoryThresholdPercent = 0.40; // 40%
  static const double warningThresholdPercent = 0.70;  // 70%
  static const double evacuateThresholdPercent = 0.85; // 85%
}
