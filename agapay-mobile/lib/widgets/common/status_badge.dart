import 'package:flutter/material.dart';
import '../../models/alert_tier.dart';

/// Multi-modal accessible status badge displaying both color, text code, and icon
class StatusBadge extends StatelessWidget {
  final AlertTier tier;
  final bool isLarge;
  final bool showIcon;

  const StatusBadge({
    super.key,
    required this.tier,
    this.isLarge = false,
    this.showIcon = true,
  });

  @override
  Widget build(BuildContext context) {
    final horizontalPad = isLarge ? 14.0 : 10.0;
    final verticalPad = isLarge ? 8.0 : 4.0;
    final fontSize = isLarge ? 14.0 : 12.0;
    final iconSize = isLarge ? 18.0 : 14.0;

    return Container(
      padding: EdgeInsets.symmetric(horizontal: horizontalPad, vertical: verticalPad),
      decoration: BoxDecoration(
        color: tier.backgroundColor,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: tier.color.withOpacity(0.4), width: 1.2),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (showIcon) ...[
            Icon(
              tier.icon,
              size: iconSize,
              color: tier.textColor,
            ),
            const SizedBox(width: 6),
          ],
          Text(
            tier.code,
            style: TextStyle(
              color: tier.textColor,
              fontSize: fontSize,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.8,
            ),
          ),
        ],
      ),
    );
  }
}
