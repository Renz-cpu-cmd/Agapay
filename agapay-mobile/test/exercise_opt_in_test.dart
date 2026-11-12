// Device-specific EXERCISE_TEST opt-in: off by default, revocable, testing-only
// wording, separate from operational alert preferences. Fake client; no network.
import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/screens/exercises/exercise_screen.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:agapay_mobile/widgets/common/exercise_test_opt_in.dart';
import 'package:flutter_test/flutter_test.dart';
import 'firebase_push_test.dart' show PushHarness;

class FakeConsent implements ExerciseConsentClient {
  FakeConsent({this.optedIn = false, this.status});
  bool optedIn;
  final int? status;
  final calls = <String>[];
  @override
  Future<bool> read(String deviceId) async {
    calls.add('read $deviceId');
    if (status != null) throw AccountException('refused', status: status);
    return optedIn;
  }

  @override
  Future<bool> write(String deviceId, bool value) async {
    calls.add('${value ? 'PUT' : 'DELETE'} $deviceId');
    if (status != null) throw AccountException('refused', status: status);
    return optedIn = value;
  }
}

Future<void> pump(
  WidgetTester tester,
  Widget child, {
  ThemeData? theme,
  double scale = 1,
}) async {
  tester.view.physicalSize = const Size(320, 2000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    MaterialApp(
      theme: theme ?? AppTheme.light,
      builder: (context, c) => MediaQuery(
        data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(scale)),
        child: c!,
      ),
      home: Scaffold(body: SingleChildScrollView(child: child)),
    ),
  );
  await tester.pump();
  await tester.pump();
}

SwitchListTile toggle(WidgetTester tester) => tester.widget<SwitchListTile>(
  find.byKey(const ValueKey('exercise-test-opt-in-switch')),
);

void main() {
  testWidgets('off by default, opt in and revoke for this device only', (tester) async {
    final client = FakeConsent();
    await pump(tester, ExerciseTestOptIn(deviceId: 'device-a', client: client));
    expect(toggle(tester).value, isFalse);
    expect(find.text('Off'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('exercise-test-opt-in-switch')));
    await tester.pump();
    expect(toggle(tester).value, isTrue);
    expect(find.text('On · testing only'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('exercise-test-opt-in-switch')));
    await tester.pump();
    expect(toggle(tester).value, isFalse);
    expect(client.calls, ['read device-a', 'PUT device-a', 'DELETE device-a']);
  });

  testWidgets('server state is shown, never assumed', (tester) async {
    await pump(
      tester,
      ExerciseTestOptIn(deviceId: 'device-a', client: FakeConsent(optedIn: true)),
    );
    expect(toggle(tester).value, isTrue);
  });

  testWidgets('no registered device: explains and offers no switch', (tester) async {
    final client = FakeConsent();
    await pump(tester, ExerciseTestOptIn(deviceId: null, client: client));
    expect(find.text('Turn on push notifications for this device first.'), findsOneWidget);
    expect(find.byKey(const ValueKey('exercise-test-opt-in-switch')), findsNothing);
    expect(client.calls, isEmpty);
  });

  testWidgets('disabled server: explains and keeps the switch off and inert', (tester) async {
    final client = FakeConsent(status: 403);
    await pump(tester, ExerciseTestOptIn(deviceId: 'device-a', client: client));
    expect(find.text('Exercise testing is not enabled on this server.'), findsOneWidget);
    expect(toggle(tester).value, isFalse);
    expect(toggle(tester).onChanged, isNull);
  });

  for (final theme in [AppTheme.light, AppTheme.dark]) {
    testWidgets('${theme.brightness.name}: testing-only wording at 320px, 2x text', (tester) async {
      final semantics = tester.ensureSemantics();
      await pump(
        tester,
        ExerciseTestOptIn(deviceId: 'device-a', client: FakeConsent()),
        theme: theme,
        scale: 2,
      );
      expect(tester.takeException(), isNull);
      expect(find.textContaining('Testing only.'), findsOneWidget);
      expect(find.textContaining('AGAPAY TEST ALERT — NOT A REAL EMERGENCY'), findsOneWidget);
      expect(find.textContaining('does not change your flood alert settings'), findsOneWidget);
      expect(find.bySemanticsLabel('Exercise test notifications'), findsOneWidget);
      semantics.dispose();
    });
  }

  testWidgets('test workspace hosts the opt-in separately from operational settings', (tester) async {
    final h = PushHarness();
    tester.view.physicalSize = const Size(390, 3000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      AppScope(
        controller: h.app,
        child: MaterialApp(theme: AppTheme.light, home: const ExerciseScreen()),
      ),
    );
    await tester.pump();
    expect(find.byKey(const ValueKey('exercise-test-opt-in')), findsOneWidget);
    expect(find.text('Turn on push notifications for this device first.'), findsOneWidget);
    expect(find.text('TEST WORKSPACE · SYNTHETIC DATA'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    h.app.dispose();
    await h.gateway.close();
  });
}
