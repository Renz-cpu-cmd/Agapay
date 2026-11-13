import '../../core/ui.dart';

/// The original resident home circular depth readout, independent of whether
/// a device is connected. Missing data stays visibly unknown inside the dial.
class WaterDepthDial extends StatelessWidget {
  const WaterDepthDial({
    required this.depth,
    required this.trend,
    required this.level,
    super.key,
  });
  final double? depth;
  final String trend;
  final AlertLevel level;

  @override
  Widget build(BuildContext context) {
    final knownTier = depth != null && level != AlertLevel.unknown;
    final color = knownTier
        ? context.colors.resolve(level.color)
        : context.colors.muted;
    final text = knownTier
        ? context.colors.resolve(level.textColor)
        : context.colors.muted;
    return AspectRatio(
      aspectRatio: 1,
      child: DecoratedBox(
        key: const ValueKey('water-depth-dial'),
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: color.withValues(alpha: .1),
          border: Border.all(color: color.withValues(alpha: .7)),
        ),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              FittedBox(
                fit: BoxFit.scaleDown,
                child: tx(
                  depth?.toStringAsFixed(1) ?? '—',
                  size: 34,
                  weight: 700,
                  mono: true,
                  color: text,
                  height: 1.1,
                ),
              ),
              tx('cm', size: 12, color: context.colors.muted),
              const SizedBox(height: 6),
              FittedBox(
                fit: BoxFit.scaleDown,
                child: tx(
                  depth == null ? 'No valid reading' : trend,
                  size: 12,
                  weight: 700,
                  color: text,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
