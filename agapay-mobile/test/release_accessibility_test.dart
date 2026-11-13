import 'package:flutter_test/flutter_test.dart';
import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/core/operational_states.dart';
import 'package:agapay_mobile/core/release_configuration.dart';
import 'package:agapay_mobile/widgets/common/hybrid_trend_panels.dart';
import 'dart:math' as math;
import 'package:agapay_mobile/app.dart';
import 'support/accounts.dart';
import 'package:agapay_mobile/controllers/theme_controller.dart';

class MemoryThemes implements ThemePreferenceStore {
  String? value;
  @override
  Future<String?> read() async => value;
  @override
  Future<void> write(String next) async {
    value = next;
  }
}

void main() {
  void release({
    String environment = 'production',
    String? flavor = 'production',
    String api = 'https://api.agapay.org',
    String revision = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    String mapMode = 'list_only',
    String mapOrigin = '',
  }) => ReleaseConfiguration.validateValues(
    release: true,
    environment: environment,
    flavor: flavor,
    api: api,
    revision: revision,
    releaseId: 'test-v1',
    mapMode: mapMode,
    mapOrigin: mapOrigin,
  );
  test(
    'release refuses development, mixed flavor, missing provenance and insecure origins',
    () {
      release();
      for (final attempt in [
        () => release(environment: 'development'),
        () => release(flavor: 'staging'),
        () => release(flavor: null),
        () => release(revision: ''),
        () => release(api: 'http://api.agapay.org'),
        () => release(api: 'https://127.0.0.1'),
        () => release(api: 'https://[::ffff:127.0.0.1]'),
        () => release(api: 'https://api.agapay.org/?token=bad'),
        () => release(mapMode: 'demo'),
        () => release(mapMode: 'hosted'),
      ]) {
        expect(attempt, throwsStateError);
      }
    },
  );
  test(
    'chart coordinates use elapsed time and refuse missing/reordered timestamps',
    () {
      final at = DateTime.utc(2026);
      expect(
        elapsedFractions([
          at,
          at.add(const Duration(seconds: 10)),
          at.add(const Duration(seconds: 100)),
        ]),
        [0, .1, 1],
      );
      expect(elapsedFractions([at, null]), isNull);
      expect(elapsedFractions([at, at]), isNull);
      expect(
        elapsedFractions([at.add(const Duration(minutes: 1)), at]),
        isNull,
      );
    },
  );
  double luminance(Color c) {
    double f(double n) =>
        n <= .04045 ? n / 12.92 : math.pow((n + .055) / 1.055, 2.4).toDouble();
    return .2126 * f(c.r) + .7152 * f(c.g) + .0722 * f(c.b);
  }

  double ratio(Color a, Color b) {
    final x = luminance(a), y = luminance(b);
    return (math.max(x, y) + .05) / (math.min(x, y) + .05);
  }

  test(
    'shared text and operational tokens meet normal-text contrast in both palettes',
    () {
      for (final dark in [false, true]) {
        final palette = AppPalette(dark);
        for (final background in [
          palette.background,
          palette.surface,
          palette.surfaceRaised,
        ]) {
          for (final text in [
            palette.text,
            palette.muted,
            palette.secondary,
            palette.label,
            palette.link,
            palette.resolve(AlertLevel.unknown.textColor),
          ]) {
            expect(
              ratio(text, background),
              greaterThanOrEqualTo(4.5),
              reason: '${dark ? 'dark' : 'light'} text contrast',
            );
          }
          for (final state in OperationalState.values) {
            expect(
              ratio(state.color(dark), background),
              greaterThanOrEqualTo(4.5),
              reason: state.name,
            );
          }
        }
      }
    },
  );
  for (final dark in [false, true]) {
    testWidgets(
      'resident tabs at 320px and 200% text, reduced motion, dark=$dark',
      (tester) async {
        tester.view.physicalSize = const Size(320, 900);
        tester.view.devicePixelRatio = 1;
        tester.platformDispatcher.textScaleFactorTestValue = 2;
        tester.platformDispatcher.accessibilityFeaturesTestValue =
            const FakeAccessibilityFeatures(disableAnimations: true);
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
        addTearDown(
          tester.platformDispatcher.clearAccessibilityFeaturesTestValue,
        );
        final app = fixtureController(themeStorage: MemoryThemes());
        await app.login('resident@example.com', 'synthetic-password');
        await app.theme.setMode(dark ? ThemeMode.dark : ThemeMode.light);
        await tester.pumpWidget(AgapayApp(controller: app));
        await tester.pump(const Duration(seconds: 3));
        await tester.pump(const Duration(seconds: 1));
        for (final tab in AppTab.values) {
          app.navigate(tab);
          await tester.pump(const Duration(milliseconds: 500));
          await tester.pump(const Duration(seconds: 1));
          expect(
            tester.takeException(),
            isNull,
            reason: 'large text ${tab.name}',
          );
        }
        await tester.pumpWidget(const SizedBox.shrink());
      },
    );
  }
  for (final theme in [AppTheme.light, AppTheme.dark]) {
    testWidgets(
      'critical controls and timestamp table support 320px and 200% text in ${theme.brightness}',
      (tester) async {
        tester.view.physicalSize = const Size(320, 900);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final semantics = tester.ensureSemantics();

        final at = DateTime.utc(2026);
        await tester.pumpWidget(
          MaterialApp(
            theme: theme,
            home: MediaQuery(
              data: const MediaQueryData(textScaler: TextScaler.linear(2)),
              child: Scaffold(
                body: SingleChildScrollView(
                  child: Column(
                    children: [
                      const OperationalStateLabel(OperationalState.stale),
                      ActionButton(
                        'Review current instructions',
                        onPressed: () {},
                      ),
                      Switch.adaptive(value: true, onChanged: (value) {}),
                      StationTrendChart(
                        values: const [0, null, 20],
                        times: [
                          at,
                          at.add(const Duration(minutes: 1)),
                          at.add(const Duration(minutes: 4)),
                        ],
                        label: 'Observed depth',
                        storageId: 'accessibility-fixture',
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        );
        await tester.pump();
        expect(tester.takeException(), isNull);
        expect(
          tester.getSize(find.byType(ActionButton)).height,
          greaterThanOrEqualTo(48),
        );
        await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
        await tester.ensureVisible(find.text('View timestamped data'));
        await tester.tap(find.byType(ExpansionTile));
        await tester.pumpAndSettle();
        await tester.ensureVisible(find.text('0.0 cm · valid value'));
        expect(find.text('0.0 cm · valid value'), findsOneWidget);
        expect(find.text('Unknown / invalid measurement'), findsOneWidget);
        expect(tester.takeException(), isNull);
        semantics.dispose();
      },
    );
  }
}
