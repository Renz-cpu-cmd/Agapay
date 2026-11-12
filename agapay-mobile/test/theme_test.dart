import 'package:agapay_mobile/app.dart';
import 'package:flutter/services.dart';
import 'dart:async';
import 'package:agapay_mobile/controllers/theme_controller.dart';
import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/navigation/main_navigation_shell.dart';
import 'package:agapay_mobile/widgets/common/water_level_gauge.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:flutter_test/flutter_test.dart';
import 'support/accounts.dart';

({double y, double width, double height}) waterGeometry(String source) {
  final rect = RegExp(
    r'<rect\b[^>]*fill="url\(#water\)"[^>]*>',
  ).firstMatch(source);
  expect(
    rect,
    isNotNull,
    reason: 'The SVG must contain the water fill rectangle',
  );
  double number(String attribute) {
    final match = RegExp('$attribute="([^"]+)"').firstMatch(rect!.group(0)!);
    expect(
      match,
      isNotNull,
      reason: 'Missing water geometry attribute $attribute',
    );
    final value = double.tryParse(match!.group(1)!);
    expect(value, isNotNull, reason: 'Invalid numeric $attribute');
    expect(value!.isFinite, isTrue, reason: '$attribute must be finite');
    return value;
  }

  return (y: number('y'), width: number('width'), height: number('height'));
}

class MemoryThemes implements ThemePreferenceStore {
  String? value;
  Completer<String?>? pendingRead;
  bool fail = false;
  @override
  Future<String?> read() async =>
      pendingRead == null ? value : await pendingRead!.future;
  @override
  Future<void> write(String value) async {
    if (fail) throw StateError('Unavailable');
    this.value = value;
  }
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
  test(
    'new installs default to light; dark selection survives a restart',
    () async {
      final store = MemoryThemes();
      final first = ThemeController(store: store);
      await first.restore();
      expect(first.mode, ThemeMode.light);
      await first.setMode(ThemeMode.dark);
      first.dispose();
      final restored = ThemeController(store: store);
      await restored.restore();
      expect(restored.mode, ThemeMode.dark);
      restored.dispose();
    },
  );

  test('rapid switching persists the last choice', () async {
    final store = MemoryThemes();
    final theme = ThemeController(store: store);
    final first = theme.setMode(ThemeMode.dark);
    final second = theme.setMode(ThemeMode.light);
    await Future.wait([first, second]);
    expect(store.value, 'light');
    expect(theme.mode, ThemeMode.light);
    theme.dispose();
  });

  test('late restoration cannot overwrite a user selection', () async {
    final store = MemoryThemes()..pendingRead = Completer<String?>();
    final theme = ThemeController(store: store);
    final restoring = theme.restore();
    await theme.setMode(ThemeMode.light);
    store.pendingRead!.complete('dark');
    await restoring;
    expect(theme.mode, ThemeMode.light);
    theme.dispose();
  });

  test(
    'storage failure leaves the chosen theme usable and reports unsaved state',
    () async {
      final theme = ThemeController(store: MemoryThemes()..fail = true);
      await theme.setMode(ThemeMode.dark);
      expect(theme.mode, ThemeMode.dark);
      expect(theme.saveError, isNotNull);
      theme.dispose();
    },
  );

  testWidgets(
    'gauge surface follows theme without changing scale or water level',
    (tester) async {
      for (final theme in [AppTheme.light, AppTheme.dark]) {
        await tester.pumpWidget(
          MaterialApp(
            theme: theme,
            home: const Scaffold(body: WaterLevelGauge(60)),
          ),
        );
        await tester.pumpAndSettle();
        final svg = tester.widget<SvgPicture>(find.byType(SvgPicture));
        final source = (svg.bytesLoader as SvgStringLoader).provideSvg(null);
        final colors = tester.element(find.byType(WaterLevelGauge)).colors;
        String hex(Color color) =>
            color.toARGB32().toRadixString(16).substring(2);
        expect(
          source,
          contains(
            'fill="#${hex(colors.surfaceRaised)}" stroke="#${hex(colors.border)}"',
          ),
        );
        final water = waterGeometry(source);
        expect(water.y, closeTo(98, 1e-9));
        expect(water.width, closeTo(28, 1e-9));
        expect(water.height, closeTo(90, 1e-9));
        expect(svg.height, 196);
        expect(source, contains('viewBox="0 0 100 196"'));
        expect(source, contains('y1="38" x2="32" y2="38"'));
        expect(source, contains('y1="60.5" x2="32" y2="60.5"'));
        expect(source, contains('y1="98" x2="32" y2="98"'));
        expect(
          find.bySemanticsLabel(RegExp('Water level 60.0 centimeters')),
          findsOneWidget,
        );
      }
    },
  );

  testWidgets(
    'default gauge clamps fill while keeping measured level semantics',
    (tester) async {
      for (final (level, y, fill) in [
        (0.0, 188.0, 0.0),
        (120.0, 8.0, 180.0),
        (180.0, 8.0, 180.0),
      ]) {
        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.light,
            home: Scaffold(body: WaterLevelGauge(level)),
          ),
        );
        await tester.pumpAndSettle();
        final svg = tester.widget<SvgPicture>(find.byType(SvgPicture));
        final source = (svg.bytesLoader as SvgStringLoader).provideSvg(null);
        expect(svg.height, 196);
        final water = waterGeometry(source);
        expect(water.y, closeTo(y, 1e-9));
        expect(water.width, closeTo(28, 1e-9));
        expect(water.height, closeTo(fill, 1e-9));
        expect(
          find.bySemanticsLabel(
            RegExp('Water level ${level.toStringAsFixed(1)} centimeters'),
          ),
          findsOneWidget,
        );
      }
    },
  );

  testWidgets(
    'profile selector updates all tabs and map fallback in both themes',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final app = fixtureController(themeStorage: MemoryThemes());
      await app.login('resident@example.com', 'long-password-value');
      await tester.pumpWidget(
        RepaintBoundary(
          key: const ValueKey('theme-preview'),
          child: AgapayApp(controller: app),
        ),
      );
      await tester.pump(const Duration(seconds: 3));
      await tester.pumpAndSettle();
      app.navigate(AppTab.profile);
      await tester.pumpAndSettle();
      expect(
        Theme.of(tester.element(find.byType(MainNavigationShell))).brightness,
        Brightness.light,
      );
      await tester.ensureVisible(find.text('Default'));
      await tester.tap(find.text('Default'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Dark (Current theme)'));
      await tester.pumpAndSettle();
      expect(
        Theme.of(tester.element(find.byType(MainNavigationShell))).brightness,
        Brightness.dark,
      );
      for (final mode in [ThemeMode.light, ThemeMode.dark]) {
        await app.theme.setMode(mode);
        for (final tab in AppTab.values) {
          app.navigate(tab);
          await tester.pump(const Duration(milliseconds: 400));
          await tester.pump(const Duration(seconds: 1));
          expect(tester.takeException(), isNull, reason: '$mode / $tab');
          if (tab == AppTab.map) {
            final stationButton = find.widgetWithText(
              TextButton,
              'STATION_001',
            );
            await tester.ensureVisible(stationButton);
            await tester.tap(stationButton);
            await tester.pumpAndSettle();
            final selected = tester.widget<TextButton>(stationButton);
            final foreground = selected.style!.foregroundColor!.resolve({})!;
            final background = selected.style!.backgroundColor!.resolve({})!;
            final contrast =
                (foreground.computeLuminance() + .05) /
                (background.computeLuminance() + .05);
            expect(
              contrast < 1 ? 1 / contrast : contrast,
              greaterThanOrEqualTo(4.5),
              reason: 'Selected station text must be readable in $mode',
            );
          }
          if (const bool.fromEnvironment('CAPTURE_THEME_PREVIEWS') &&
              [AppTab.home, AppTab.map, AppTab.profile].contains(tab)) {
            await expectLater(
              find.byKey(const ValueKey('theme-preview')),
              matchesGoldenFile(
                '../build/theme-previews/${mode.name}-${tab.name}.png',
              ),
            );
          }
        }
      }
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}
