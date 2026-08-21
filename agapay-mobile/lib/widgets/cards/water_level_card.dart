import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../models/station.dart';
import '../gauge/water_level_gauge.dart';

/// Prominent Water Level Card featuring the animated WaterLevelGauge and station metadata
class WaterLevelCard extends StatelessWidget {
  final Station station;
  final VoidCallback? onTap;

  const WaterLevelCard({
    super.key,
    required this.station,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
        side: const BorderSide(color: AppColors.border, width: 1.2),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Station Header
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: AppColors.secondaryLight,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(Icons.water_rounded, color: AppColors.primary, size: 22),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          station.name,
                          style: const TextStyle(
                            color: AppColors.textPrimary,
                            fontSize: 16,
                            fontWeight: FontWeight.w800,
                            letterSpacing: -0.2,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '${station.barangay} · ${station.distanceKm} km away',
                          style: const TextStyle(
                            color: AppColors.textSecondary,
                            fontSize: 12,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const Icon(Icons.chevron_right_rounded, color: AppColors.textMuted),
                ],
              ),
              const SizedBox(height: 16),
              // Gauge Visualization
              Center(
                child: WaterLevelGauge(
                  depthCm: station.waterDepthCm,
                  maxDepthCm: station.maxThresholdCm,
                  advisoryCm: station.advisoryThresholdCm,
                  warningCm: station.warningThresholdCm,
                  evacuateCm: station.evacuateThresholdCm,
                  tier: station.alertTier,
                  trend: station.trend,
                  lastUpdated: station.lastUpdated,
                  size: 250,
                ),
              ),
              const SizedBox(height: 14),
              // Quick Specs footer
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                decoration: BoxDecoration(
                  color: AppColors.surfaceSecondary,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    _metricItem(Icons.grain_rounded, 'Rainfall', '${station.rainfallMm} mm/h'),
                    Container(width: 1, height: 24, color: AppColors.border),
                    _metricItem(Icons.battery_charging_full_rounded, 'Battery', '${station.batteryPercent}%'),
                    Container(width: 1, height: 24, color: AppColors.border),
                    _metricItem(Icons.wifi_rounded, 'Signal', '${station.rssi} dBm'),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _metricItem(IconData icon, String label, String value) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 16, color: AppColors.textSecondary),
        const SizedBox(width: 6),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(label, style: const TextStyle(fontSize: 10, color: AppColors.textSecondary)),
            Text(
              value,
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
              ),
            ),
          ],
        ),
      ],
    );
  }
}
