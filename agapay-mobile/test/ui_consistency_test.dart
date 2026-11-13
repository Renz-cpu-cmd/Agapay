import 'dart:io';
import 'dart:ui' as ui;
import 'package:agapay_mobile/app.dart';
import 'package:agapay_mobile/controllers/theme_controller.dart';
import 'package:agapay_mobile/core/ui.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'support/accounts.dart';

class ReviewThemeStore implements ThemePreferenceStore {
  String? value;
  @override
  Future<String?> read() async => value;
  @override
  Future<void> write(String next) async {
    value = next;
  }
}

// Render the real resident shell with synthetic service responses. These are
// layout checks and optional review images, not physical-device evidence.
void main() {
  setUpAll(() async {
    for (final name in ['Inter', 'Outfit', 'JetBrainsMono']) {
      await (FontLoader(
        name,
      )..addFont(rootBundle.load('assets/fonts/$name.ttf'))).load();
    }
    await (FontLoader(
      'MaterialIcons',
    )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
  });
  for (final dark in [false, true]) {
    for (final scale in [1.0, 2.0]) {
      testWidgets('resident visual reflow dark=$dark scale=$scale', (
        tester,
      ) async {
        tester.view.physicalSize = Size(scale == 1 ? 390 : 320, 844);
        tester.view.devicePixelRatio = 1;
        tester.platformDispatcher.textScaleFactorTestValue = scale;
        tester.platformDispatcher.accessibilityFeaturesTestValue =
            const FakeAccessibilityFeatures(disableAnimations: true);
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
        addTearDown(
          tester.platformDispatcher.clearAccessibilityFeaturesTestValue,
        );
        final app = fixtureController(themeStorage: ReviewThemeStore());
        await app.login('resident@example.com', 'synthetic-password');
        await app.theme.setMode(dark ? ThemeMode.dark : ThemeMode.light);
        final boundary = GlobalKey();
        await tester.pumpWidget(
          RepaintBoundary(
            key: boundary,
            child: AgapayApp(controller: app),
          ),
        );
        await tester.pump(const Duration(seconds: 3));
        await tester.pump(const Duration(seconds: 1));
        await tester.runAsync(
          () => precacheImage(
            const AssetImage('assets/images/agapay-logo.png'),
            boundary.currentContext!,
          ),
        );
        await tester.pump();
        final directory = Platform.environment['AGAPAY_CAPTURE_MOBILE_UI'];
        Future<void> capture(String name) async {
          if (directory == null) return;
          await tester.runAsync(() async {
            final image =
                await (boundary.currentContext!.findRenderObject()!
                        as RenderRepaintBoundary)
                    .toImage(pixelRatio: 1);
            final bytes = await image.toByteData(
              format: ui.ImageByteFormat.png,
            );
            await Directory(directory).create(recursive: true);
            await File(
              '$directory/$name-${dark ? 'dark' : 'light'}-$scale.png',
            ).writeAsBytes(bytes!.buffer.asUint8List());
            image.dispose();
          });
        }

        for (final tab in AppTab.values) {
          app.navigate(tab);
          await tester.pump(const Duration(seconds: 1));
          expect(tester.takeException(), isNull, reason: '${tab.name} top');
          await capture('${tab.name}-top');
          final scroll = find.byType(SingleChildScrollView).hitTestable().first;
          if (scroll.evaluate().isNotEmpty) {
            await tester.drag(scroll, const Offset(0, -500));
            await tester.pump(const Duration(seconds: 1));
            expect(
              tester.takeException(),
              isNull,
              reason: '${tab.name} middle',
            );
            await capture('${tab.name}-middle');
            await tester.drag(scroll, const Offset(0, -5000));
            await tester.pump(const Duration(seconds: 1));
            expect(
              tester.takeException(),
              isNull,
              reason: '${tab.name} bottom',
            );
            await capture('${tab.name}-bottom');
          }
        }
        app.navigate(AppTab.home);
        app.showAlert();
        await tester.pump(const Duration(seconds: 1));
        expect(tester.takeException(), isNull, reason: 'sensor detail top');
        expect(
          tester.getRect(find.text('95.8').first).top,
          lessThan(660),
          reason:
              'large text must not push the primary depth below the initial viewport',
        );
        await capture('sensor-detail-top');
        final detailScroll = find
            .byType(SingleChildScrollView)
            .hitTestable()
            .first;
        await tester.drag(detailScroll, const Offset(0, -500));
        await tester.pump(const Duration(seconds: 1));
        expect(tester.takeException(), isNull, reason: 'sensor detail middle');
        await capture('sensor-detail-middle');
        await tester.pumpWidget(const SizedBox.shrink());
      });
    }
  }
}
