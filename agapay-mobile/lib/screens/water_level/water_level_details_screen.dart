import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../controllers/app_controller.dart';
import '../../widgets/gauge/water_level_gauge.dart';
import '../../widgets/common/status_badge.dart';
import '../../widgets/common/app_buttons.dart';
import '../../navigation/app_routes.dart';

/// Screen 6: In-Depth Sensor Telemetry and Water Level Diagnostics
class WaterLevelDetailsScreen extends StatelessWidget {
  final AppController controller;

  const WaterLevelDetailsScreen({super.key, required this.controller});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final station = controller.selectedStation;
        if (station == null) {
          return Scaffold(
            appBar: AppBar(title: const Text('Water Level Details')),
            body: const Center(child: Text('No sensor station selected.')),
          );
        }

        return Scaffold(
          backgroundColor: AppColors.background,
          appBar: AppBar(
            title: Text(station.barangay),
            actions: [
              IconButton(
                icon: const Icon(Icons.refresh_rounded),
                onPressed: controller.refreshData,
              ),
            ],
          ),
          body: SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Station Card
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: Column(
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    station.name,
                                    style: const TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.w800,
                                      color: AppColors.textPrimary,
                                    ),
                                  ),
                                  const SizedBox(height: 2),
                                  Text(
                                    'Station ID: ${station.id} · ${station.distanceKm} km away',
                                    style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(width: 8),
                            StatusBadge(tier: station.alertTier),
                          ],
                        ),
                        const SizedBox(height: 16),
                        // Animated Gauge
                        WaterLevelGauge(
                          depthCm: station.waterDepthCm,
                          maxDepthCm: station.maxThresholdCm,
                          advisoryCm: station.advisoryThresholdCm,
                          warningCm: station.warningThresholdCm,
                          evacuateCm: station.evacuateThresholdCm,
                          tier: station.alertTier,
                          trend: station.trend,
                          lastUpdated: station.lastUpdated,
                          size: 260,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Hardware & Environmental Sensors Grid
                  const Text(
                    'ESP32 Sensor Array Telemetry',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: AppColors.textPrimary),
                  ),
                  const SizedBox(height: 8),
                  GridView.count(
                    crossAxisCount: 2,
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    mainAxisSpacing: 10,
                    crossAxisSpacing: 10,
                    childAspectRatio: 1.6,
                    children: [
                      _telemetryCard(
                        Icons.speed_rounded,
                        'Flow Speed',
                        '${station.flowSpeedMs.toStringAsFixed(2)} m/s',
                        'Surface velocity',
                        AppColors.secondary,
                      ),
                      _telemetryCard(
                        Icons.grain_rounded,
                        'Rainfall Intensity',
                        '${station.rainfallMm.toStringAsFixed(1)} mm/h',
                        'Tipping bucket',
                        AppColors.primary,
                      ),
                      _telemetryCard(
                        Icons.battery_charging_full_rounded,
                        'Battery Level',
                        '${station.batteryPercent}%',
                        station.solarCharging ? 'Solar charging' : 'Discharging',
                        AppColors.alertNormal,
                      ),
                      _telemetryCard(
                        Icons.wifi_rounded,
                        'Telemetry Link',
                        '${station.rssi} dBm',
                        'MQTT over LTE/Cell',
                        AppColors.textSecondary,
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  // Threshold Reference Table
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Community Alert Threshold Tiers',
                          style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: AppColors.textPrimary),
                        ),
                        const SizedBox(height: 12),
                        _thresholdRow('Normal Range', '0 – 39.9 cm', AppColors.alertNormal, 'Safe, routine flow'),
                        const Divider(height: 16),
                        _thresholdRow('Advisory Tier', '40 – 69.9 cm', AppColors.alertAdvisory, 'Caution, rising waters'),
                        const Divider(height: 16),
                        _thresholdRow('Warning Tier', '70 – 84.9 cm', AppColors.alertWarning, 'Standby for evacuation'),
                        const Divider(height: 16),
                        _thresholdRow('Evacuation Tier', '≥ 85.0 cm', AppColors.alertEvacuate, 'Mandatory evacuation'),
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),

                  // Actions
                  PrimaryButton(
                    label: 'View Historical Data & AI Predictions',
                    icon: Icons.insights_rounded,
                    onPressed: () {
                      Navigator.pushNamed(context, AppRoutes.historicalCharts);
                    },
                  ),
                  const SizedBox(height: 10),
                  SecondaryButton(
                    label: 'View Evacuation Shelters on Map',
                    icon: Icons.map_outlined,
                    onPressed: () {
                      Navigator.pushNamed(context, AppRoutes.evacuationMap);
                    },
                  ),
                  const SizedBox(height: 24),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _telemetryCard(IconData icon, String title, String value, String subtitle, Color color) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Row(
            children: [
              Icon(icon, size: 16, color: color),
              const SizedBox(width: 6),
              Text(title, style: const TextStyle(fontSize: 11, color: AppColors.textSecondary, fontWeight: FontWeight.w600)),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: AppColors.textPrimary),
          ),
          Text(
            subtitle,
            style: const TextStyle(fontSize: 10, color: AppColors.textMuted),
          ),
        ],
      ),
    );
  }

  Widget _thresholdRow(String name, String range, Color color, String desc) {
    return Row(
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(name, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: color)),
              Text(desc, style: const TextStyle(fontSize: 11, color: AppColors.textSecondary)),
            ],
          ),
        ),
        Text(
          range,
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: AppColors.textPrimary),
        ),
      ],
    );
  }
}
