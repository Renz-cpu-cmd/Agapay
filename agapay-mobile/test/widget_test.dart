import 'package:flutter_test/flutter_test.dart';
import 'package:agapay_mobile/main.dart';
import 'package:agapay_mobile/controllers/app_controller.dart';
import 'package:agapay_mobile/models/alert_tier.dart';
import 'package:agapay_mobile/models/trend_direction.dart';
import 'package:agapay_mobile/models/station.dart';

void main() {
  test('Station calculates alert tier correctly based on depth thresholds', () {
    final stationNormal = Station(
      id: 'TEST_01',
      name: 'Test Bridge',
      barangay: 'Brgy. Test',
      distanceKm: 1.0,
      latitude: 14.7,
      longitude: 120.9,
      waterDepthCm: 25.0,
      advisoryThresholdCm: 40.0,
      warningThresholdCm: 70.0,
      evacuateThresholdCm: 85.0,
      rainfallMm: 2.0,
      batteryPercent: 90,
      lastUpdated: DateTime.now(),
      trend: TrendDirection.stable,
    );

    expect(stationNormal.alertTier, AlertTier.normal);

    final stationAdvisory = stationNormal.copyWith(waterDepthCm: 50.0);
    expect(stationAdvisory.alertTier, AlertTier.advisory);

    final stationWarning = stationNormal.copyWith(waterDepthCm: 75.0);
    expect(stationWarning.alertTier, AlertTier.warning);

    final stationEvacuate = stationNormal.copyWith(waterDepthCm: 90.0);
    expect(stationEvacuate.alertTier, AlertTier.evacuate);
  });

  testWidgets('AgapayApp boots, renders splash, and transitions to dashboard', (WidgetTester tester) async {
    final controller = AppController();
    await tester.pumpWidget(AgapayApp(controller: controller));

    // Verify Splash branding renders
    expect(find.text('AGAPAY'), findsWidgets);

    // Fast-forward splash screen timer and animation
    await tester.pump(const Duration(milliseconds: 500));
    await tester.pump(const Duration(seconds: 3));
    await tester.pumpAndSettle();

    // Verify Home Dashboard loaded
    expect(find.text('Nearby Sensor Stations'), findsOneWidget);
    expect(find.text('SOS'), findsWidgets);

    controller.dispose();
  });
}
