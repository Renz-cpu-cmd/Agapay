import 'dart:math';
import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/formatters.dart';
import '../../models/alert_tier.dart';
import '../../models/trend_direction.dart';
import '../common/trend_indicator.dart';

/// Reusable 0-100% Water Level Gauge with alert threshold indicators and animated fill
class WaterLevelGauge extends StatefulWidget {
  final double depthCm;
  final double maxDepthCm;
  final double advisoryCm;
  final double warningCm;
  final double evacuateCm;
  final AlertTier tier;
  final TrendDirection trend;
  final DateTime lastUpdated;
  final double size;
  final bool showHeader;

  const WaterLevelGauge({
    super.key,
    required this.depthCm,
    this.maxDepthCm = 100.0,
    this.advisoryCm = 40.0,
    this.warningCm = 70.0,
    this.evacuateCm = 85.0,
    required this.tier,
    required this.trend,
    required this.lastUpdated,
    this.size = 240,
    this.showHeader = true,
  });

  @override
  State<WaterLevelGauge> createState() => _WaterLevelGaugeState();
}

class _WaterLevelGaugeState extends State<WaterLevelGauge> with SingleTickerProviderStateMixin {
  late AnimationController _animController;
  late Animation<double> _depthAnimation;
  double _prevDepth = 0.0;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );
    _depthAnimation = Tween<double>(begin: 0.0, end: widget.depthCm).animate(
      CurvedAnimation(parent: _animController, curve: Curves.easeOutCubic),
    );
    _prevDepth = widget.depthCm;
    _animController.forward();
  }

  @override
  void didUpdateWidget(covariant WaterLevelGauge oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.depthCm != widget.depthCm) {
      _depthAnimation = Tween<double>(begin: _prevDepth, end: widget.depthCm).animate(
        CurvedAnimation(parent: _animController, curve: Curves.easeOutCubic),
      );
      _prevDepth = widget.depthCm;
      _animController.forward(from: 0.0);
    }
  }

  @override
  void dispose() {
    _animController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final percent = (widget.depthCm / widget.maxDepthCm).clamp(0.0, 1.0);
    final percentText = '${(percent * 100).toInt()}%';

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        SizedBox(
          width: widget.size,
          height: widget.size * 0.76,
          child: Stack(
            alignment: Alignment.center,
            children: [
              AnimatedBuilder(
                animation: _depthAnimation,
                builder: (context, child) {
                  return CustomPaint(
                    size: Size(widget.size, widget.size * 0.76),
                    painter: _GaugePainter(
                      currentDepth: _depthAnimation.value,
                      maxDepth: widget.maxDepthCm,
                      advisoryDepth: widget.advisoryCm,
                      warningDepth: widget.warningCm,
                      evacuateDepth: widget.evacuateCm,
                      tierColor: widget.tier.color,
                    ),
                  );
                },
              ),
              Positioned(
                bottom: 10,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // Water Level Readout (38px bold)
                    AnimatedBuilder(
                      animation: _depthAnimation,
                      builder: (context, child) {
                        return Text(
                          Formatters.formatWaterLevel(_depthAnimation.value),
                          style: TextStyle(
                            color: widget.tier.color,
                            fontSize: 38,
                            fontWeight: FontWeight.w800,
                            letterSpacing: -0.5,
                            height: 1.0,
                          ),
                        );
                      },
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Water Level ($percentText of capacity)',
                      style: const TextStyle(
                        color: AppColors.textSecondary,
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 8),
                    // Trend Indicator
                    TrendIndicator(trend: widget.trend),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 6),
        // Threshold Legends
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16.0),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _thresholdLegend('Normal', '< 40 cm', AppColors.alertNormal),
              _thresholdLegend('Advisory', '≥ 40 cm', AppColors.alertAdvisory),
              _thresholdLegend('Warning', '≥ 70 cm', AppColors.alertWarning),
              _thresholdLegend('Evacuate', '≥ 85 cm', AppColors.alertEvacuate),
            ],
          ),
        ),
        const SizedBox(height: 10),
        // Last updated readout
        Text(
          'Last updated: ${Formatters.formatRelativeTime(widget.lastUpdated)}',
          style: const TextStyle(
            color: AppColors.textMuted,
            fontSize: 11,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }

  Widget _thresholdLegend(String name, String value, Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 4),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              name,
              style: TextStyle(
                color: color,
                fontSize: 11,
                fontWeight: FontWeight.w700,
              ),
            ),
            Text(
              value,
              style: const TextStyle(
                color: AppColors.textSecondary,
                fontSize: 10,
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _GaugePainter extends CustomPainter {
  final double currentDepth;
  final double maxDepth;
  final double advisoryDepth;
  final double warningDepth;
  final double evacuateDepth;
  final Color tierColor;

  _GaugePainter({
    required this.currentDepth,
    required this.maxDepth,
    required this.advisoryDepth,
    required this.warningDepth,
    required this.evacuateDepth,
    required this.tierColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height * 0.88);
    final radius = size.width * 0.44;
    const startAngle = pi * 0.85;
    const sweepAngle = pi * 1.30;
    const strokeWidth = 16.0;

    final rect = Rect.fromCircle(center: center, radius: radius);

    // Background track
    final bgPaint = Paint()
      ..color = const Color(0xFFE2E8F0)
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeWidth = strokeWidth;

    canvas.drawArc(rect, startAngle, sweepAngle, false, bgPaint);

    // Active progress arc
    final progress = (currentDepth / maxDepth).clamp(0.0, 1.0);
    final currentSweep = sweepAngle * progress;

    if (progress > 0.01) {
      final activePaint = Paint()
        ..color = tierColor
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeWidth = strokeWidth;

      canvas.drawArc(rect, startAngle, currentSweep, false, activePaint);
    }

    // Threshold tick markers
    _drawThresholdTick(canvas, center, radius, startAngle, sweepAngle, advisoryDepth / maxDepth, AppColors.alertAdvisory);
    _drawThresholdTick(canvas, center, radius, startAngle, sweepAngle, warningDepth / maxDepth, AppColors.alertWarning);
    _drawThresholdTick(canvas, center, radius, startAngle, sweepAngle, evacuateDepth / maxDepth, AppColors.alertEvacuate);
  }

  void _drawThresholdTick(
    Canvas canvas,
    Offset center,
    double radius,
    double startAngle,
    double sweepAngle,
    double ratio,
    Color color,
  ) {
    final angle = startAngle + (sweepAngle * ratio);
    final inner = Offset(
      center.dx + (radius - 12) * cos(angle),
      center.dy + (radius - 12) * sin(angle),
    );
    final outer = Offset(
      center.dx + (radius + 12) * cos(angle),
      center.dy + (radius + 12) * sin(angle),
    );

    final tickPaint = Paint()
      ..color = color
      ..strokeWidth = 3.0
      ..strokeCap = StrokeCap.round;

    canvas.drawLine(inner, outer, tickPaint);
  }

  @override
  bool shouldRepaint(covariant _GaugePainter oldDelegate) {
    return oldDelegate.currentDepth != currentDepth ||
        oldDelegate.tierColor != tierColor ||
        oldDelegate.maxDepth != maxDepth;
  }
}
