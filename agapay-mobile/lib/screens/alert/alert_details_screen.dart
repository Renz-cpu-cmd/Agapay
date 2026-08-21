import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/formatters.dart';
import '../../models/flood_alert.dart';
import '../../models/alert_tier.dart';
import '../../widgets/common/status_badge.dart';
import '../../widgets/common/trend_indicator.dart';
import '../../widgets/common/app_buttons.dart';
import '../../widgets/cards/info_card.dart';
import '../../navigation/app_routes.dart';

/// Screen 5: Alert Details Screen
class AlertDetailsScreen extends StatelessWidget {
  final FloodAlert alert;

  const AlertDetailsScreen({super.key, required this.alert});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Alert Details'),
        actions: [
          IconButton(
            icon: const Icon(Icons.share_outlined),
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Flood alert details copied to clipboard to share with neighbors.')),
              );
            },
          ),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Top Banner with Alert Tier
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  color: alert.tier.backgroundColor,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: alert.tier.color, width: 1.5),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        StatusBadge(tier: alert.tier, isLarge: true),
                        Text(
                          Formatters.formatTimestamp(alert.timestamp),
                          style: const TextStyle(
                            fontSize: 12,
                            fontWeight: FontWeight.w600,
                            color: AppColors.textSecondary,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      alert.title,
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w900,
                        color: alert.tier.textColor,
                        letterSpacing: -0.3,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      alert.description,
                      style: const TextStyle(
                        fontSize: 14,
                        color: AppColors.textPrimary,
                        height: 1.4,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // Recommended Public Safety Action Guide
              InfoCard(
                title: 'Official Action Recommendation',
                subtitle: 'Issued by Local Barangay Disaster Risk Reduction Council',
                icon: Icons.shield_rounded,
                iconColor: alert.tier.color,
                content: Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: alert.tier.backgroundColor.withOpacity(0.5),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: alert.tier.color.withOpacity(0.3)),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.info_outline_rounded, size: 18, color: alert.tier.textColor),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          alert.recommendedAction,
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w700,
                            color: alert.tier.textColor,
                            height: 1.35,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),

              // Telemetry Data Points Grid
              const Text(
                'Sensor Telemetry at Timestamp',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: AppColors.textPrimary),
              ),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: AppColors.border),
                ),
                child: Column(
                  children: [
                    _telemetryRow('Monitoring Station', alert.stationName, Icons.location_on_outlined),
                    const Divider(height: 20),
                    _telemetryRow(
                      'Current Water Depth',
                      '${alert.waterLevelCm} cm',
                      Icons.water_rounded,
                      valueColor: alert.tier.color,
                      isBold: true,
                    ),
                    const Divider(height: 20),
                    _telemetryRow(
                      'Threshold Level',
                      '${alert.thresholdCm} cm (${alert.tier.displayName})',
                      Icons.tune_rounded,
                    ),
                    const Divider(height: 20),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Row(
                          children: [
                            Icon(Icons.timeline_rounded, size: 18, color: AppColors.textSecondary),
                            SizedBox(width: 8),
                            Text('Water Trend', style: TextStyle(fontSize: 13, color: AppColors.textSecondary)),
                          ],
                        ),
                        TrendIndicator(trend: alert.trend),
                      ],
                    ),
                    const Divider(height: 20),
                    _telemetryRow(
                      'Current Rainfall Rate',
                      '${alert.rainfallMm} mm/h',
                      Icons.grain_rounded,
                    ),
                    const Divider(height: 20),
                    _telemetryRow(
                      'AI Forecast (T+30 min)',
                      '${alert.predictedLevelCm} cm (ML Prediction)',
                      Icons.auto_graph_rounded,
                      valueColor: AppColors.secondary,
                      isBold: true,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),

              // Navigate to Evacuation Center Action
              PrimaryButton(
                label: 'Navigate to Evacuation Center',
                icon: Icons.directions_run_rounded,
                onPressed: () {
                  Navigator.pushNamed(context, AppRoutes.evacuationMap);
                },
              ),
              const SizedBox(height: 12),
              SecondaryButton(
                label: 'View Historical Telemetry Charts',
                icon: Icons.show_chart_rounded,
                onPressed: () {
                  Navigator.pushNamed(context, AppRoutes.historicalCharts);
                },
              ),
              const SizedBox(height: 24),
            ],
          ),
        ),
      ),
    );
  }

  Widget _telemetryRow(String label, String value, IconData icon, {Color? valueColor, bool isBold = false}) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Row(
          children: [
            Icon(icon, size: 18, color: AppColors.textSecondary),
            const SizedBox(width: 8),
            Text(
              label,
              style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
            ),
          ],
        ),
        Text(
          value,
          style: TextStyle(
            fontSize: 13,
            fontWeight: isBold ? FontWeight.w800 : FontWeight.w600,
            color: valueColor ?? AppColors.textPrimary,
          ),
        ),
      ],
    );
  }
}
