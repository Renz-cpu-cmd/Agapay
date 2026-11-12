import 'package:flutter_svg/flutter_svg.dart';
import '../../core/ui.dart';

class WaterLevelGauge extends StatelessWidget {
  const WaterLevelGauge(
    this.level, {
    this.height = 196,
    this.advisory,
    this.warning,
    this.critical,
    this.maximum = 120,
    super.key,
  });
  final double? level;
  final double height;
  final double? advisory, warning, critical;
  final double maximum;
  @override
  Widget build(BuildContext context) {
    if (level == null) {
      return Semantics(
        label: 'Water depth · No valid reading',
        child: Container(
          width: 100,
          height: height,
          decoration: BoxDecoration(
            border: Border.all(color: context.colors.border),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Center(child: tx('—', size: 32, color: context.colors.muted)),
        ),
      );
    }
    return TweenAnimationBuilder<double>(
      tween: Tween(end: level),
      duration: MediaQuery.disableAnimationsOf(context)
          ? Duration.zero
          : const Duration(milliseconds: 800),
      curve: Curves.easeOut,
      builder: (context, value, child) {
        final color =
            (advisory != null && warning != null && critical != null
                    ? AlertValues.forWater(
                        value,
                        advisory: advisory!,
                        warning: warning!,
                        critical: critical!,
                      ).color
                    : context.colors.muted)
                .toARGB32()
                .toRadixString(16)
                .substring(2);
        String line(double threshold, String color) {
          final position = 188 - threshold / maximum * 180;
          return '<line x1="0" y1="$position" x2="32" y2="$position" stroke="$color" stroke-width=".8" stroke-dasharray="2,1.5"/>';
        }

        final fillHeight = (value / maximum).clamp(0, 1) * 180;
        final y = 188 - fillHeight;
        final surface = context.colors.surfaceRaised
            .toARGB32()
            .toRadixString(16)
            .substring(2);
        final border = context.colors.border
            .toARGB32()
            .toRadixString(16)
            .substring(2);
        return Semantics(
          label: 'Water depth ${level!.toStringAsFixed(1)} centimeters',
          child: SizedBox(
            width: 100,
            height: height,
            child: Stack(
              children: [
                SvgPicture.string(
                  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 196">'
                  '<defs><clipPath id="tube"><rect x="0" y="8" width="28" height="180" rx="4"/></clipPath>'
                  '<linearGradient id="water" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#$color" stop-opacity=".95"/><stop offset="100%" stop-color="#$color" stop-opacity=".6"/></linearGradient></defs>'
                  '<rect x="0" y="8" width="28" height="180" rx="4" fill="#$surface" stroke="#$border"/>'
                  '<rect x="0" y="$y" width="28" height="$fillHeight" fill="url(#water)" clip-path="url(#tube)"/>'
                  '<rect x="0" y="$y" width="28" height="2" fill="#$color" opacity=".9" clip-path="url(#tube)"/>'
                  '${critical == null ? "" : line(critical!, "#dc2626")}'
                  '${warning == null ? "" : line(warning!, "#ea580c")}'
                  '${advisory == null ? "" : line(advisory!, "#ca8a04")}'
                  '</svg>',
                  width: 100,
                  height: height,
                  fit: BoxFit.fill,
                ),
                for (final row in [
                  if (critical != null)
                    (
                      'EVAC ${critical!.toStringAsFixed(0)}',
                      183 - critical! / maximum * 180,
                      AlertLevel.evacuate.textColor,
                    ),
                  if (warning != null)
                    (
                      'WARN ${warning!.toStringAsFixed(0)}',
                      183 - warning! / maximum * 180,
                      AlertLevel.warning.textColor,
                    ),
                  if (advisory != null)
                    (
                      'ADV ${advisory!.toStringAsFixed(0)}',
                      183 - advisory! / maximum * 180,
                      AlertLevel.advisory.textColor,
                    ),
                  ('0 cm', 183.0, context.colors.muted),
                ])
                  Positioned(
                    left: 35,
                    top: row.$2 / 196 * height,
                    child: tx(
                      row.$1,
                      size: 8,
                      mono: true,
                      weight: 600,
                      color: row.$3,
                      height: 1.25,
                    ),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }
}
