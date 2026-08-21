import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/formatters.dart';
import '../../models/alert_tier.dart';
import '../../controllers/app_controller.dart';
import '../../widgets/common/app_header.dart';
import '../../widgets/common/state_views.dart';
import '../../widgets/common/status_badge.dart';
import '../../widgets/cards/water_level_card.dart';
import '../../widgets/cards/alert_card.dart';
import '../../widgets/cards/station_card.dart';
import '../../navigation/app_routes.dart';

/// Screen 4: Home Dashboard Screen — Primary operational center for residents
class HomeDashboardScreen extends StatelessWidget {
  final AppController controller;

  const HomeDashboardScreen({super.key, required this.controller});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final station = controller.selectedStation;
        final currentTier = station?.alertTier ?? AlertTier.normal;

        return Scaffold(
          backgroundColor: AppColors.background,
          appBar: AppHeader(
            barangay: controller.user.barangay,
            unreadCount: controller.unreadNotificationCount,
            isOffline: controller.isOffline,
            onNotificationTap: () => Navigator.pushNamed(context, AppRoutes.notifications),
            onBarangayTap: () => _showBarangaySelector(context),
          ),
          body: RefreshIndicator(
            onRefresh: controller.refreshData,
            color: AppColors.primary,
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Offline banner when active
                  if (controller.isOffline)
                    OfflineBanner(
                      lastUpdated: controller.lastSyncTime,
                      onRetry: controller.refreshData,
                    ),

                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 12.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // Section 1: Community Flood Status Card
                        _buildFloodStatusCard(context, currentTier),
                        const SizedBox(height: 16),

                        // Section 2: Water Level Card with Gauge
                        if (station != null) ...[
                          WaterLevelCard(
                            station: station,
                            onTap: () {
                              Navigator.pushNamed(context, AppRoutes.waterLevelDetails);
                            },
                          ),
                          const SizedBox(height: 16),
                        ],

                        // Section 3: Prominent Emergency SOS Action Banner
                        _buildEmergencySosBanner(context),
                        const SizedBox(height: 16),

                        // Section 4: Latest Active Alert (if any)
                        if (controller.latestAlert != null) ...[
                          _sectionTitle('Active Alert'),
                          const SizedBox(height: 8),
                          AlertCard(
                            alert: controller.latestAlert!,
                            onTap: () {
                              Navigator.pushNamed(
                                context,
                                AppRoutes.alertDetails,
                                arguments: controller.latestAlert!,
                              );
                            },
                            onNavigateEvac: () {
                              Navigator.pushNamed(context, AppRoutes.evacuationMap);
                            },
                          ),
                          const SizedBox(height: 16),
                        ],

                        // Section 5: Nearest Other Sensor Stations
                        _sectionTitle('Nearby Sensor Stations'),
                        const SizedBox(height: 8),
                        ...controller.stations
                            .where((s) => s.id != (station?.id ?? ''))
                            .take(2)
                            .map((otherStation) {
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 10.0),
                            child: StationCard(
                              station: otherStation,
                              onTap: () {
                                controller.selectStation(otherStation.id);
                              },
                            ),
                          );
                        }),
                        const SizedBox(height: 24),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _sectionTitle(String title) {
    return Text(
      title,
      style: const TextStyle(
        fontSize: 17,
        fontWeight: FontWeight.w800,
        color: AppColors.textPrimary,
        letterSpacing: -0.3,
      ),
    );
  }

  /// High priority visual status banner (Normal, Advisory, Warning, Evacuate)
  Widget _buildFloodStatusCard(BuildContext context, AlertTier tier) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: tier.backgroundColor,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: tier.color, width: 1.5),
        boxShadow: [
          BoxShadow(
            color: tier.color.withOpacity(0.12),
            blurRadius: 10,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: Colors.white,
              shape: BoxShape.circle,
              border: Border.all(color: tier.color.withOpacity(0.4)),
            ),
            child: Icon(tier.icon, color: tier.color, size: 26),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      tier.code,
                      style: TextStyle(
                        color: tier.textColor,
                        fontSize: 20,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 1.0,
                      ),
                    ),
                    StatusBadge(tier: tier, showIcon: false),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  tier.summary,
                  style: TextStyle(
                    color: tier.textColor,
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    height: 1.3,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  tier.recommendedAction,
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// Emergency SOS Action Card on Home Screen
  Widget _buildEmergencySosBanner(BuildContext context) {
    final isSosActive = controller.isSosActive;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isSosActive ? AppColors.sosRedLight : Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isSosActive ? AppColors.sosRed : AppColors.border,
          width: isSosActive ? 2.0 : 1.2,
        ),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: isSosActive ? AppColors.sosRed : AppColors.sosRedLight,
              shape: BoxShape.circle,
            ),
            child: Icon(
              Icons.emergency_rounded,
              color: isSosActive ? Colors.white : AppColors.sosRed,
              size: 26,
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  isSosActive ? 'SOS ACTIVE · Responders Dispatched' : 'Emergency SOS Beacon',
                  style: TextStyle(
                    color: isSosActive ? AppColors.sosRed : AppColors.textPrimary,
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  isSosActive
                    ? 'BDRRMC tracking your GPS coordinates.'
                    : 'Need immediate rescue? Broadcast your location directly.',
                  style: TextStyle(
                    color: isSosActive ? AppColors.textPrimary : AppColors.textSecondary,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          ElevatedButton(
            onPressed: () => Navigator.pushNamed(context, AppRoutes.sosBeacon),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.sosRed,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              minimumSize: const Size(60, 38),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            child: Text(
              isSosActive ? 'VIEW' : 'SOS',
              style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 13, letterSpacing: 0.5),
            ),
          ),
        ],
      ),
    );
  }

  void _showBarangaySelector(BuildContext context) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(20.0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Select Community Barangay',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800, color: AppColors.textPrimary),
                ),
                const SizedBox(height: 4),
                const Text(
                  'Change your active monitoring zone',
                  style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
                ),
                const SizedBox(height: 16),
                ...controller.stations.map((st) {
                  final isSelected = controller.selectedStation?.id == st.id;
                  return ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: st.alertTier.backgroundColor,
                        shape: BoxShape.circle,
                      ),
                      child: Icon(st.alertTier.icon, color: st.alertTier.color, size: 20),
                    ),
                    title: Text(st.barangay, style: const TextStyle(fontWeight: FontWeight.w700)),
                    subtitle: Text('${st.name} · ${Formatters.formatWaterLevel(st.waterDepthCm)}'),
                    trailing: isSelected
                        ? const Icon(Icons.check_circle_rounded, color: AppColors.primary)
                        : null,
                    onTap: () {
                      controller.selectStation(st.id);
                      Navigator.pop(ctx);
                    },
                  );
                }),
              ],
            ),
          ),
        );
      },
    );
  }
}
