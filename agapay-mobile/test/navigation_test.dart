import 'support/accounts.dart';
import 'package:agapay_mobile/app.dart';
import 'package:agapay_mobile/controllers/app_controller.dart';
import 'package:agapay_mobile/models/alert_level.dart';
import 'package:agapay_mobile/navigation/main_navigation_shell.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

const capturePreviews = bool.fromEnvironment('CAPTURE_PREVIEWS');

Future<void> capture(WidgetTester tester, String name) async {
  if (capturePreviews) {
    await expectLater(
      find.byKey(const ValueKey('preview')),
      matchesGoldenFile('../build/previews/$name.png'),
    );
  }
}

Future<void> start(
  WidgetTester tester, {
  Size size = const Size(390, 844),
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    RepaintBoundary(
      key: const ValueKey('preview'),
      child: AgapayApp(controller: fixtureController()),
    ),
  );
  await tester.pump(const Duration(milliseconds: 400));
  await capture(tester, 'splash');
  await tester.pump(const Duration(milliseconds: 2800));
  await tester.pumpAndSettle();
}

Future<void> tapText(WidgetTester tester, String text) async {
  final target = find.text(text).last;
  await tester.ensureVisible(target);
  await tester.tap(target);
  await tester.pump(const Duration(milliseconds: 400));
}

Future<void> tab(WidgetTester tester, String text) async {
  await tester.tap(
    find.descendant(
      of: find.byType(AgapayBottomNav),
      matching: find.text(text),
    ),
  );
  await tester.pump(const Duration(milliseconds: 400));
}

void main() {
  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    for (final name in ['Inter', 'Outfit', 'JetBrainsMono']) {
      final loader = FontLoader(name)
        ..addFont(rootBundle.load('assets/fonts/$name.ttf'));
      await loader.load();
    }
    final icons = FontLoader('MaterialIcons')
      ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
    await icons.load();
  });

  testWidgets(
    'prototype navigation, alerts, maps, settings and confirmed SOS',
    (tester) async {
      await start(tester);
      await capture(tester, 'login');
      expect(find.text('Welcome back'), findsOneWidget);

      await tapText(tester, 'Register');
      await tester.pumpAndSettle();
      await capture(tester, 'registration');
      await tester.enterText(find.byType(TextField).at(0), 'Test Resident');
      await tapText(tester, 'San Vicente');
      await tester.pumpAndSettle();
      await capture(tester, 'barangay');
      await tester.tap(find.text('Catablan'));
      await tester.pumpAndSettle();
      expect(find.text('Catablan'), findsOneWidget);
      await tester.tap(find.bySemanticsLabel('Back'));
      await tester.pumpAndSettle();
      expect(find.text('your@email.com'), findsOneWidget);
      await tester.enterText(
        find.byType(TextField).at(0),
        'resident@example.com',
      );
      await tester.enterText(
        find.byType(TextField).at(1),
        'long-password-value',
      );

      await tapText(tester, 'LOG IN');
      await tester.pumpAndSettle();
      await capture(tester, 'home');
      await tester.ensureVisible(find.text('WATER-DEPTH FORECAST'));
      await tester.pumpAndSettle();
      await capture(tester, 'home_forecast');
      expect(find.text('95.8'), findsWidgets);
      final controller = AppScope.of(
        tester.element(find.byType(MainNavigationShell)),
      );
      expect(controller.alert, AlertLevel.warning);
      expect(find.textContaining('Observed'), findsWidgets);
      expect(tester.takeException(), isNull);
      await tester.drag(
        find.byType(SingleChildScrollView).first,
        const Offset(0, 2500),
      );
      await tester.pump(const Duration(seconds: 1));
      await capture(tester, 'home_evacuate');
      await tapText(tester, 'VIEW ALERT DETAILS');
      await capture(tester, 'alert_details');
      expect(find.text('Sensor episode'), findsOneWidget);
      await tapText(tester, 'NAVIGATE TO SHELTER');
      await capture(tester, 'evacuation_map');
      expect(
        find.text('Shelter inventory & reported road restrictions'),
        findsOneWidget,
      );
      expect(find.text('UCU Gym'), findsNothing);
      expect(
        find.textContaining('No authority-maintained shelter'),
        findsOneWidget,
      );

      await tapText(tester, 'Monitoring Stations');
      await tester.ensureVisible(
        find.widgetWithText(TextButton, 'STATION_001'),
      );
      await tester.tap(find.widgetWithText(TextButton, 'STATION_001'));
      await tester.pump(const Duration(milliseconds: 400));
      await capture(tester, 'map_station');
      expect(find.text('95.8 cm'), findsOneWidget);

      await tab(tester, 'Alerts');
      await capture(tester, 'notifications');
      expect(find.text('1 active sensor alerts'), findsOneWidget);
      expect(find.textContaining('unread'), findsNothing);
      await tapText(tester, 'Community Test Station');
      await tester.pumpAndSettle();
      expect(find.text('Sensor alert details'), findsOneWidget);
      await capture(tester, 'community_alert_details');
      expect(find.text('Latest depth: 102.3 cm'), findsOneWidget);
      expect(find.text('NORMAL → EVACUATE'), findsOneWidget);
      expect(find.textContaining('Demo notification'), findsNothing);
      await tester.tap(find.bySemanticsLabel('Back').last);
      await tester.pumpAndSettle();
      expect(find.text('1 active sensor alerts'), findsOneWidget);

      await tapText(tester, 'Episode history');
      await capture(tester, 'community_alert_history');
      expect(find.text('EVACUATE · Peak tier'), findsOneWidget);
      expect(find.text('Recovery depth: 35.2 cm'), findsOneWidget);

      await tab(tester, 'SOS');
      await capture(tester, 'sos');
      await tester.tap(find.bySemanticsLabel(RegExp('Start SOS')));
      await tester.pump(const Duration(milliseconds: 400));
      await capture(tester, 'sos_confirm');
      await tester.enterText(
        find.byKey(const ValueKey('sos-location')),
        'Practice site, San Vicente',
      );
      await tester.enterText(
        find.byKey(const ValueKey('sos-message')),
        'Prototype test',
      );
      await tapText(tester, 'CANCEL');
      expect(find.text('START SOS'), findsOneWidget);
      expect(find.text('REQUEST RECEIVED'), findsNothing);
      await tester.tap(find.bySemanticsLabel(RegExp('Start SOS')));
      await tester.pump();
      await tapText(tester, 'SEND SOS');
      await tester.pump(const Duration(seconds: 1));
      await capture(tester, 'sos_received');
      expect(find.text('REQUEST RECEIVED'), findsOneWidget);
      expect(
        find.text(
          'Server receipt confirmed. This does not confirm that a person has reviewed it or that a responder was sent.',
        ),
        findsOneWidget,
      );
      await tapText(tester, 'BACK TO SOS HISTORY');
      expect(find.text('TEST REQUEST #1'), findsOneWidget);

      await tab(tester, 'Profile');
      await capture(tester, 'profile');
      await tester.ensureVisible(find.bySemanticsLabel('Flood Alerts').last);
      await tester.tap(find.bySemanticsLabel('Flood Alerts').last);
      await tester.pump();
      expect(controller.notifications, isFalse);
      expect(controller.language, 'English');
      expect(
        find.textContaining('Filipino translation unavailable'),
        findsOneWidget,
      );
      await tapText(tester, 'LOG OUT');
      await tester.pumpAndSettle();
      expect(find.text('Welcome back'), findsOneWidget);
      expect(find.byType(AgapayBottomNav), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );

  testWidgets('registration, keyboard and all tabs fit a narrow phone', (
    tester,
  ) async {
    await start(tester, size: const Size(320, 568));
    await tapText(tester, 'Register');
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).at(0), 'Test Resident');
    await tester.enterText(
      find.byType(TextField).at(1),
      'resident@example.com',
    );
    await tester.enterText(find.byType(TextField).at(2), '+639123456789');
    await tester.enterText(find.byType(TextField).at(3), 'long-password-value');
    tester.view.viewInsets = const FakeViewPadding(bottom: 250);
    await tester.pump();
    await tapText(tester, 'CREATE ACCOUNT');
    tester.view.resetViewInsets();
    await tester.pumpAndSettle();
    expect(find.byType(MainNavigationShell), findsOneWidget);
    for (final label in ['Home', 'Map', 'Alerts', 'SOS', 'Profile']) {
      await tab(tester, label);
      expect(
        tester.takeException(),
        isNull,
        reason: 'Overflow in $label at 320 px',
      );
    }
    await tab(tester, 'Home');
    await capture(tester, 'home_compact');
    tester.platformDispatcher.textScaleFactorTestValue = 1.6;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.pump();
    expect(tester.takeException(), isNull, reason: 'Home with larger text');
    await capture(tester, 'home_large_text');
    await tester.pumpWidget(const SizedBox.shrink());
  });
}
