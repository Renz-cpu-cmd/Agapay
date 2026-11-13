// Presentation-only coverage. Keep outside the theme-only staging candidate.
import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/widgets/common/water_level_gauge.dart';
import 'package:agapay_mobile/widgets/common/water_depth_dial.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets(
    'home keeps its circular readout for missing data, zero and a valid depth',
    (tester) async {
      for (final theme in [AppTheme.light, AppTheme.dark]) {
        for (final depth in <double?>[null, 0, 95.8]) {
          await tester.pumpWidget(
            MaterialApp(
              theme: theme,
              home: Scaffold(
                body: SizedBox(
                  width: 160,
                  child: WaterDepthDial(
                    depth: depth,
                    trend: 'RISING',
                    level: depth == null
                        ? AlertLevel.unknown
                        : AlertLevel.warning,
                  ),
                ),
              ),
            ),
          );
          await tester.pumpAndSettle();
          final dial = tester.widget<DecoratedBox>(
            find.byKey(const ValueKey('water-depth-dial')),
          );
          expect((dial.decoration as BoxDecoration).shape, BoxShape.circle);
          expect(find.text(depth?.toStringAsFixed(1) ?? '—'), findsOneWidget);
          expect(
            find.text('No valid reading'),
            depth == null ? findsOneWidget : findsNothing,
          );
          expect(tester.takeException(), isNull);
        }
      }
    },
  );
  testWidgets('custom 152px gauge preserves water scale and semantics', (
    tester,
  ) async {
    for (final theme in [AppTheme.light, AppTheme.dark]) {
      await tester.pumpWidget(
        MaterialApp(
          theme: theme,
          home: const Scaffold(body: WaterLevelGauge(60, height: 152)),
        ),
      );
      await tester.pumpAndSettle();
      final svg = tester.widget<SvgPicture>(find.byType(SvgPicture));
      final source = (svg.bytesLoader as SvgStringLoader).provideSvg(null);
      expect(svg.height, 152);
      expect(source, contains('y="98.0" width="28" height="90.0"'));
      expect(
        find.bySemanticsLabel(RegExp('Water depth 60.0 centimeters')),
        findsOneWidget,
      );
    }
  });
}
