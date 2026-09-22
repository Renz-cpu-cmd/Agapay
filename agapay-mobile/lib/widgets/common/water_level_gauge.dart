import 'package:flutter_svg/flutter_svg.dart';
import '../../core/ui.dart';

class WaterLevelGauge extends StatelessWidget {
  const WaterLevelGauge(this.level, {super.key});
  final double level;
  @override
  Widget build(BuildContext context) => TweenAnimationBuilder<double>(
    tween: Tween(end: level),
    duration: const Duration(milliseconds: 800),
    curve: Curves.easeOut,
    builder: (context, value, child) {
      final color = AlertValues.forWater(
        value,
      ).color.toARGB32().toRadixString(16).substring(2);
      final height = (value / 120).clamp(0, 1) * 180;
      final y = 188 - height;
      return Semantics(
        label: 'Water level ${level.toStringAsFixed(1)} centimeters',
        child: SizedBox(
          width: 100,
          height: 196,
          child: Stack(
            children: [
              SvgPicture.string(
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 196">'
                '<defs><clipPath id="tube"><rect x="0" y="8" width="28" height="180" rx="4"/></clipPath>'
                '<linearGradient id="water" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#$color" stop-opacity=".95"/><stop offset="100%" stop-color="#$color" stop-opacity=".6"/></linearGradient></defs>'
                '<rect x="0" y="8" width="28" height="180" rx="4" fill="#0d1525" stroke="#1a2740"/>'
                '<rect x="0" y="$y" width="28" height="$height" fill="url(#water)" clip-path="url(#tube)"/>'
                '<rect x="0" y="$y" width="28" height="2" fill="#$color" opacity=".9" clip-path="url(#tube)"/>'
                '<line x1="0" y1="38" x2="32" y2="38" stroke="#dc2626" stroke-width=".8" stroke-dasharray="2,1.5"/>'
                '<line x1="0" y1="60.5" x2="32" y2="60.5" stroke="#ea580c" stroke-width=".8" stroke-dasharray="2,1.5"/>'
                '<line x1="0" y1="98" x2="32" y2="98" stroke="#ca8a04" stroke-width=".8" stroke-dasharray="2,1.5"/>'
                '</svg>',
                width: 100,
                height: 196,
              ),
              for (final row in [
                ('EVAC 100', 33.0, AlertLevel.evacuate.textColor),
                ('WARN 85', 55.5, AlertLevel.warning.textColor),
                ('ADV 60', 93.0, AlertLevel.advisory.textColor),
                ('0 cm', 183.0, AppColors.muted),
              ])
                Positioned(
                  left: 35,
                  top: row.$2,
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
