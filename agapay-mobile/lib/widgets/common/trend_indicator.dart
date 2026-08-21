import 'package:flutter/material.dart';
import '../../models/trend_direction.dart';

/// Clean trend indicator for water level progression
class TrendIndicator extends StatelessWidget {
  final TrendDirection trend;
  final bool showLabel;

  const TrendIndicator({
    super.key,
    required this.trend,
    this.showLabel = true,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: trend.color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            trend.icon,
            size: 16,
            color: trend.color,
          ),
          if (showLabel) ...[
            const SizedBox(width: 4),
            Text(
              trend.label,
              style: TextStyle(
                color: trend.color,
                fontSize: 12,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
