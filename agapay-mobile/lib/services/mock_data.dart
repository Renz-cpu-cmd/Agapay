import '../models/alert_tier.dart';
import '../models/trend_direction.dart';
import '../models/station.dart';
import '../models/flood_alert.dart';
import '../models/evacuation_center.dart';
import '../models/telemetry_history.dart';
import '../models/user_profile.dart';
import '../models/notification_item.dart';

/// Comprehensive local seed dataset for AGAPAY
class MockData {
  static final DateTime _now = DateTime.now();

  // Initial user
  static final UserProfile defaultUser = UserProfile(
    id: 'USR-88291',
    fullName: 'Maria Santos',
    email: 'maria.santos@agapay.community',
    phone: '+63 917 555 0192',
    barangay: 'Brgy. San Nicolas',
    emergencyContacts: const [
      '+63 917 123 4567 (Juan Santos - Spouse)',
      '+63 918 765 4321 (Brgy. San Nicolas Rescue Desk)',
    ],
    preferredLanguage: 'en',
    floodAlertsEnabled: true,
    heavyRainAlertsEnabled: true,
    soundAlertsEnabled: true,
  );

  // Monitoring stations
  static final List<Station> initialStations = [
    Station(
      id: 'STATION_001',
      name: 'Brgy. San Nicolas River Bridge',
      barangay: 'Brgy. San Nicolas',
      distanceKm: 0.6,
      latitude: 14.7365,
      longitude: 120.9582,
      waterDepthCm: 42.0,
      maxThresholdCm: 100.0,
      advisoryThresholdCm: 40.0,
      warningThresholdCm: 70.0,
      evacuateThresholdCm: 85.0,
      rainfallMm: 3.2,
      batteryPercent: 87,
      isOnline: true,
      lastUpdated: _now.subtract(const Duration(seconds: 10)),
      trend: TrendDirection.stable,
      rssi: -62,
      solarCharging: true,
      flowSpeedMs: 0.85,
    ),
    Station(
      id: 'STATION_002',
      name: 'Brgy. Poblacion River Station',
      barangay: 'Brgy. Poblacion',
      distanceKm: 1.4,
      latitude: 14.7410,
      longitude: 120.9630,
      waterDepthCm: 74.5,
      maxThresholdCm: 100.0,
      advisoryThresholdCm: 40.0,
      warningThresholdCm: 70.0,
      evacuateThresholdCm: 85.0,
      rainfallMm: 14.8,
      batteryPercent: 92,
      isOnline: true,
      lastUpdated: _now.subtract(const Duration(seconds: 25)),
      trend: TrendDirection.rising,
      rssi: -58,
      solarCharging: true,
      flowSpeedMs: 1.62,
    ),
    Station(
      id: 'STATION_003',
      name: 'Brgy. San Vicente Monitoring Station',
      barangay: 'Brgy. San Vicente',
      distanceKm: 2.1,
      latitude: 14.7290,
      longitude: 120.9490,
      waterDepthCm: 28.0,
      maxThresholdCm: 100.0,
      advisoryThresholdCm: 40.0,
      warningThresholdCm: 70.0,
      evacuateThresholdCm: 85.0,
      rainfallMm: 0.5,
      batteryPercent: 95,
      isOnline: true,
      lastUpdated: _now.subtract(const Duration(minutes: 1)),
      trend: TrendDirection.falling,
      rssi: -71,
      solarCharging: false,
      flowSpeedMs: 0.45,
    ),
  ];

  // Active flood alerts
  static final List<FloodAlert> initialAlerts = [
    FloodAlert(
      id: 'ALT-10492',
      tier: AlertTier.warning,
      title: 'Water Level Warning: Poblacion River',
      description: 'Water level at Brgy. Poblacion has surpassed the 70 cm warning threshold due to continuous heavy rainfall upstream.',
      stationId: 'STATION_002',
      stationName: 'Brgy. Poblacion River Station',
      barangay: 'Brgy. Poblacion',
      waterLevelCm: 74.5,
      thresholdCm: 70.0,
      trend: TrendDirection.rising,
      rainfallMm: 14.8,
      predictedLevelCm: 86.0,
      recommendedAction: 'Prepare go-bags, move electrical appliances to higher floors, and review evacuation routes.',
      timestamp: _now.subtract(const Duration(minutes: 14)),
      isAcknowledged: false,
    ),
    FloodAlert(
      id: 'ALT-10491',
      tier: AlertTier.advisory,
      title: 'River Advisory: San Nicolas Bridge',
      description: 'Water level reached 42 cm (Advisory threshold). Current river flow is stable but rainfall continues.',
      stationId: 'STATION_001',
      stationName: 'Brgy. San Nicolas River Bridge',
      barangay: 'Brgy. San Nicolas',
      waterLevelCm: 42.0,
      thresholdCm: 40.0,
      trend: TrendDirection.stable,
      rainfallMm: 3.2,
      predictedLevelCm: 46.0,
      recommendedAction: 'Stay alert, avoid low-lying riverbanks, and monitor live AGAPAY sensor telemetry.',
      timestamp: _now.subtract(const Duration(minutes: 38)),
      isAcknowledged: true,
    ),
  ];

  // Evacuation Centers
  static final List<EvacuationCenter> initialEvacuationCenters = [
    const EvacuationCenter(
      id: 'EVAC_001',
      name: 'San Nicolas Elementary School Evacuation Center',
      barangay: 'Brgy. San Nicolas',
      address: 'J.P. Rizal St., Brgy. San Nicolas',
      capacity: 450,
      currentOccupancy: 110,
      distanceKm: 0.8,
      estimatedTravelMinutes: 4,
      latitude: 14.7378,
      longitude: 120.9560,
      contactNumber: '(044) 791-2211',
      isOpen: true,
      hasMedicalStation: true,
      hasReliefGoods: true,
    ),
    const EvacuationCenter(
      id: 'EVAC_002',
      name: 'Poblacion Community Covered Court',
      barangay: 'Brgy. Poblacion',
      address: 'Mabini Avenue cor. Burgos St.',
      capacity: 600,
      currentOccupancy: 420,
      distanceKm: 1.5,
      estimatedTravelMinutes: 8,
      latitude: 14.7425,
      longitude: 120.9615,
      contactNumber: '(044) 791-3344',
      isOpen: true,
      hasMedicalStation: true,
      hasReliefGoods: true,
    ),
    const EvacuationCenter(
      id: 'EVAC_003',
      name: 'San Vicente Multi-Purpose Gym',
      barangay: 'Brgy. San Vicente',
      address: 'National Road, Brgy. San Vicente',
      capacity: 500,
      currentOccupancy: 45,
      distanceKm: 2.3,
      estimatedTravelMinutes: 12,
      latitude: 14.7280,
      longitude: 120.9470,
      contactNumber: '(044) 791-5588',
      isOpen: true,
      hasMedicalStation: false,
      hasReliefGoods: true,
    ),
  ];

  // Notifications Inbox
  static final List<NotificationItem> initialNotifications = [
    NotificationItem(
      id: 'NOTIF-01',
      title: 'Warning: Water level reached warning threshold',
      description: 'Brgy. Poblacion River Station is at 74.5 cm and rising. Review evacuation readiness.',
      timestamp: _now.subtract(const Duration(minutes: 15)),
      tier: AlertTier.warning,
      type: NotificationType.waterLevelWarning,
      isRead: false,
      relatedStationId: 'STATION_002',
    ),
    NotificationItem(
      id: 'NOTIF-02',
      title: 'Flood Advisory: Water level increased',
      description: 'Brgy. San Nicolas River Bridge water depth reached 42 cm.',
      timestamp: _now.subtract(const Duration(minutes: 40)),
      tier: AlertTier.advisory,
      type: NotificationType.floodAlert,
      isRead: true,
      relatedStationId: 'STATION_001',
    ),
    NotificationItem(
      id: 'NOTIF-03',
      title: 'System Notification: Station Connection Restored',
      description: 'ESP32 telemetry link for San Vicente Monitoring Station is active and transmitting.',
      timestamp: _now.subtract(const Duration(hours: 2)),
      tier: AlertTier.normal,
      type: NotificationType.systemStatus,
      isRead: true,
      relatedStationId: 'STATION_003',
    ),
    NotificationItem(
      id: 'NOTIF-04',
      title: 'Weather Advisory: Monsoon Rain Inflow',
      description: 'PAGASA heavy rainfall advisory active for region. Rainfall expected 10-15 mm/h.',
      timestamp: _now.subtract(const Duration(hours: 5)),
      tier: AlertTier.advisory,
      type: NotificationType.weatherUpdate,
      isRead: true,
    ),
  ];

  // Generates realistic historical telemetry data points
  static TelemetrySummary getHistoricalSummary(String stationId, int hoursBack) {
    final List<TelemetryDataPoint> history = [];
    final double baseDepth = stationId == 'STATION_002' ? 74.5 : (stationId == 'STATION_003' ? 28.0 : 42.0);
    final double baseRain = stationId == 'STATION_002' ? 14.8 : 3.2;

    int points = hoursBack == 24 ? 24 : (hoursBack == 168 ? 28 : 30);
    double intervalMinutes = (hoursBack * 60) / points;

    for (int i = points; i >= 0; i--) {
      final pointTime = _now.subtract(Duration(minutes: (i * intervalMinutes).toInt()));
      // Sine wave perturbation
      final wave = (i % 6 - 3) * 2.5;
      final depth = (baseDepth - (i * 0.5) + wave).clamp(10.0, 95.0);
      final rain = (baseRain + (i % 4 - 2)).clamp(0.0, 30.0);

      history.add(TelemetryDataPoint(
        timestamp: pointTime,
        waterDepthCm: depth,
        rainfallMm: rain,
      ));
    }

    // AI Predictions
    final List<TelemetryDataPoint> predictions = [
      TelemetryDataPoint(
        timestamp: _now.add(const Duration(minutes: 30)),
        waterDepthCm: (baseDepth + 4.2).clamp(0.0, 100.0),
        rainfallMm: baseRain * 1.1,
        isPredicted: true,
        predictionLabel: 'T+30 min',
      ),
      TelemetryDataPoint(
        timestamp: _now.add(const Duration(minutes: 60)),
        waterDepthCm: (baseDepth + 9.5).clamp(0.0, 100.0),
        rainfallMm: baseRain * 1.25,
        isPredicted: true,
        predictionLabel: 'T+60 min',
      ),
      TelemetryDataPoint(
        timestamp: _now.add(const Duration(minutes: 90)),
        waterDepthCm: (baseDepth + 14.0).clamp(0.0, 100.0),
        rainfallMm: baseRain * 1.35,
        isPredicted: true,
        predictionLabel: 'T+90 min',
      ),
    ];

    double minVal = history.first.waterDepthCm;
    double maxVal = history.first.waterDepthCm;
    double sum = 0.0;
    double totalRain = 0.0;

    for (final p in history) {
      if (p.waterDepthCm < minVal) minVal = p.waterDepthCm;
      if (p.waterDepthCm > maxVal) maxVal = p.waterDepthCm;
      sum += p.waterDepthCm;
      totalRain += p.rainfallMm;
    }

    return TelemetrySummary(
      minDepthCm: minVal,
      maxDepthCm: maxVal,
      avgDepthCm: sum / history.length,
      currentDepthCm: baseDepth,
      totalRainfallMm: totalRain,
      history: history,
      predictions: predictions,
    );
  }
}
