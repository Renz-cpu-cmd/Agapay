// EXERCISE_TEST drill pushes are test-only: strict parsing, a local test view,
// and no operational alert history, receipt, refresh or SOS side effects.
// Fake messaging gateway only; no Firebase or device is contacted.
import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/screens/alerts/alert_details_screen.dart';
import 'package:agapay_mobile/services/push_messaging.dart';
import 'package:flutter_test/flutter_test.dart';
import 'firebase_push_test.dart' show PushHarness, flush;

const session = '0b0c2f6e-9d1e-4b8a-9c55-3f1f2e8a7b10';
const delivery = '6f9a1d22-3c4b-4e5f-8a9b-0c1d2e3f4a5b';
Map<String, Object?> drill([Map<String, Object?> changes = const {}]) => {
  'type': 'EXERCISE_TEST',
  'exercise': 'true',
  'session_id': session,
  'delivery_id': delivery,
  ...changes,
};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('strict parsing', () {
    test('only a well-formed EXERCISE_TEST payload is a drill', () {
      final push = ExercisePush.parse(drill());
      expect(push?.deliveryId, delivery);
      expect(push?.sessionId, session);
      for (final bad in <Map<String, Object?>>[
        {'type': 'SENSOR_ESCALATION'},
        {'type': 'EVACUATE'},
        {'exercise': 'false'},
        {'exercise': null},
        {'delivery_id': '42'},
        {'session_id': 'not-a-uuid'},
        {'delivery_id': null},
      ]) {
        expect(ExercisePush.parse(drill(bad)), isNull, reason: '$bad');
      }
    });

    test('a drill can never be read as an operational sensor alert', () {
      expect(SensorPush.parse({...drill(), 'alert_id': '501'}), isNull);
    });
  });

  test('opened drill shows only the test view, with no operational side effects', () async {
    final h = PushHarness();
    addTearDown(h.close);
    await h.login();
    final before = List.of(h.requests);
    h.gateway.openEvents.add(drill());
    await flush();
    expect(h.app.exerciseAlert?.deliveryId, delivery);
    expect(h.app.details, isTrue);
    expect(h.app.communityAlerts.selectedId, isNull);
    final added = h.requests.skip(before.length).map((r) => r.url.path).toList();
    expect(added.where((p) => p.contains('community-alerts')), isEmpty);
    expect(added.where((p) => p.contains('receipt') || p.contains('deliver')), isEmpty);
    expect(added.where((p) => p.contains('/api/sos')), isEmpty);
    // A later operational push still opens the real episode and clears the drill.
    h.gateway.openEvents.add({'type': 'SENSOR_ESCALATION', 'alert_id': '501'});
    await flush();
    expect(h.app.exerciseAlert, isNull);
    expect(h.app.communityAlerts.selectedId, 501);
  });

  test('foreground drill does not refresh operational alerts', () async {
    final h = PushHarness();
    addTearDown(h.close);
    await h.login();
    final before = h.requests.length;
    h.gateway.foregroundEvents.add(drill());
    await flush();
    expect(h.app.exerciseAlert?.sessionId, session);
    expect(
      h.requests.skip(before).where((r) => r.url.path.contains('community-alerts')),
      isEmpty,
    );
  });

  test('a drill before sign-in is ignored', () async {
    final h = PushHarness();
    addTearDown(h.close);
    h.gateway.foregroundEvents.add(drill());
    await flush();
    expect(h.app.exerciseAlert, isNull);
    expect(h.app.details, isFalse);
  });

  for (final theme in [AppTheme.light, AppTheme.dark]) {
    testWidgets('${theme.brightness.name}: test view is labelled, accessible and closes', (
      tester,
    ) async {
      tester.view.physicalSize = const Size(320, 3000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final semantics = tester.ensureSemantics();
      final h = PushHarness(); // rendering only; routing is covered by the tests above
      h.app.showExerciseAlert(ExercisePush.parse(drill())!);
      await tester.pumpWidget(
        AppScope(
          controller: h.app,
          child: MaterialApp(
            theme: theme,
            builder: (context, child) => MediaQuery(
              data: MediaQuery.of(
                context,
              ).copyWith(textScaler: const TextScaler.linear(2)),
              child: child!,
            ),
            home: const Scaffold(body: AlertDetailsScreen()),
          ),
        ),
      );
      await tester.pump();
      expect(tester.takeException(), isNull);
      expect(find.text(exerciseAlertTitle), findsOneWidget);
      expect(find.textContaining('EXERCISE ONLY'), findsOneWidget);
      expect(find.textContaining('Prepare to evacuate'), findsNothing);
      expect(find.text('EVACUATE'), findsNothing);
      expect(find.textContaining('VIEW EVACUATION MAP'), findsNothing);
      expect(
        find.bySemanticsLabel(RegExp('AGAPAY TEST ALERT — NOT A REAL EMERGENCY')),
        findsOneWidget,
      );
      final close = find.text('CLOSE TEST ALERT');
      await tester.ensureVisible(close);
      await tester.tap(close);
      await tester.pump();
      expect(h.app.exerciseAlert, isNull);
      expect(h.app.details, isFalse);
      semantics.dispose();
      await tester.pumpWidget(const SizedBox.shrink());
      h.app.dispose();
      await h.gateway.close();
    });
  }
}
