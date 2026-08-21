import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/formatters.dart';
import '../../models/flood_alert.dart';
import '../../models/alert_tier.dart';
import '../common/status_badge.dart';
import '../common/trend_indicator.dart';

/// Highly visible alert card communicating disaster tier and recommended actions
class AlertCard extends StatelessWidget {
  final FloodAlert alert;
  final VoidCallback? onTap;
  final VoidCallback? onNavigateEvac;

  const AlertCard({
    super.key,
    required this.alert,
    this.onTap,
    this.onNavigateEvac,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: alert.tier.color.withOpacity(0.5), width: 1.5),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            color: alert.tier.backgroundColor.withOpacity(0.4),
          ),
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header: Badge + Time
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  StatusBadge(tier: alert.tier),
                  Text(
                    Formatters.formatRelativeTime(alert.timestamp),
                    style: const TextStyle(
                      color: AppColors.textSecondary,
                      fontSize: 12,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              // Title
              Text(
                alert.title,
                style: TextStyle(
                  color: alert.tier.textColor,
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.2,
                ),
              ),
              const SizedBox(height: 6),
              // Description
              Text(
                alert.description,
                style: const TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 13,
                  height: 1.35,
                ),
              ),
              const SizedBox(height: 12),
              // Telemetry quick specs
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: AppColors.border),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _metricCol('Water Level', '${alert.waterLevelCm} cm', alert.tier.color),
                    _divider(),
                    _metricCol('Rainfall', '${alert.rainfallMm} mm/h', AppColors.textPrimary),
                    _divider(),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Trend', style: TextStyle(fontSize: 11, color: AppColors.textSecondary)),
                        const SizedBox(height: 2),
                        TrendIndicator(trend: alert.trend, showLabel: false),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              // Recommended Action Banner
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: alert.tier.backgroundColor,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: alert.tier.color.withOpacity(0.3)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.shield_outlined, size: 16, color: alert.tier.textColor),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        alert.recommendedAction,
                        style: TextStyle(
                          color: alert.tier.textColor,
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              if (onNavigateEvac != null && alert.tier == AlertTier.evacuate) ...[
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  height: 44,
                  child: ElevatedButton.icon(
                    onPressed: onNavigateEvac,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.alertEvacuate,
                      foregroundColor: Colors.white,
                      elevation: 0,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                    ),
                    icon: const Icon(Icons.directions_run_rounded, size: 18),
                    label: const Text('Move to Evacuation Center', style: TextStyle(fontWeight: FontWeight.w700)),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _divider() {
    return Container(width: 1, height: 28, color: AppColors.border);
  }

  Widget _metricCol(String label, String value, Color valueColor) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 11, color: AppColors.textSecondary)),
        const SizedBox(height: 2),
        Text(
          value,
          style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: valueColor),
        ),
      ],
    );
  }
}
