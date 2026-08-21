import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';

/// Clean, scalable vector AGAPAY logo (Shield + Water Wave + Early-Warning Beacon)
class AgapayLogo extends StatelessWidget {
  final double size;
  final bool showText;
  final bool isDark;
  final String? subtitle;

  const AgapayLogo({
    super.key,
    this.size = 64,
    this.showText = false,
    this.isDark = false,
    this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    final logoIcon = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: isDark ? Colors.white : AppColors.primary,
        borderRadius: BorderRadius.circular(size * 0.26),
        boxShadow: [
          BoxShadow(
            color: (isDark ? Colors.black : AppColors.primary).withOpacity(0.18),
            blurRadius: size * 0.2,
            offset: Offset(0, size * 0.08),
          ),
        ],
      ),
      child: Center(
        child: CustomPaint(
          size: Size(size * 0.65, size * 0.65),
          painter: _AgapaySymbolPainter(
            color: isDark ? AppColors.primary : Colors.white,
            secondaryColor: isDark ? AppColors.secondary : const Color(0xFF60A5FA),
          ),
        ),
      ),
    );

    if (!showText) {
      return logoIcon;
    }

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        logoIcon,
        const SizedBox(height: 16),
        Text(
          'AGAPAY',
          style: TextStyle(
            color: isDark ? Colors.white : AppColors.primary,
            fontSize: size * 0.42,
            fontWeight: FontWeight.w800,
            letterSpacing: 1.5,
          ),
        ),
        if (subtitle != null) ...[
          const SizedBox(height: 6),
          Text(
            subtitle!,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: isDark ? const Color(0xFFCBD5E1) : AppColors.textSecondary,
              fontSize: 13,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ],
    );
  }
}

/// Custom painter for the Shield + Water Wave symbol
class _AgapaySymbolPainter extends CustomPainter {
  final Color color;
  final Color secondaryColor;

  _AgapaySymbolPainter({required this.color, required this.secondaryColor});

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    // Shield outline
    final shieldPath = Path();
    shieldPath.moveTo(w * 0.5, 0);
    shieldPath.cubicTo(w * 0.85, 0, w, h * 0.15, w, h * 0.45);
    shieldPath.cubicTo(w, h * 0.78, w * 0.5, h, w * 0.5, h);
    shieldPath.cubicTo(w * 0.5, h, 0, h * 0.78, 0, h * 0.45);
    shieldPath.cubicTo(0, h * 0.15, w * 0.15, 0, w * 0.5, 0);
    shieldPath.close();

    final shieldPaint = Paint()
      ..color = color.withOpacity(0.18)
      ..style = PaintingStyle.fill;
    canvas.drawPath(shieldPath, shieldPaint);

    final shieldStroke = Paint()
      ..color = color
      ..strokeWidth = w * 0.08
      ..style = PaintingStyle.stroke;
    canvas.drawPath(shieldPath, shieldStroke);

    // Water wave inside shield
    final wavePath = Path();
    wavePath.moveTo(w * 0.2, h * 0.6);
    wavePath.cubicTo(w * 0.35, h * 0.48, w * 0.45, h * 0.72, w * 0.65, h * 0.55);
    wavePath.cubicTo(w * 0.75, h * 0.48, w * 0.8, h * 0.52, w * 0.8, h * 0.52);

    final wavePaint = Paint()
      ..color = secondaryColor
      ..strokeWidth = w * 0.09
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;
    canvas.drawPath(wavePath, wavePaint);

    // Top Beacon Dot
    final dotPaint = Paint()
      ..color = color
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(w * 0.5, h * 0.32), w * 0.12, dotPaint);
  }

  @override
  bool shouldRepaint(covariant _AgapaySymbolPainter oldDelegate) {
    return oldDelegate.color != color || oldDelegate.secondaryColor != secondaryColor;
  }
}
