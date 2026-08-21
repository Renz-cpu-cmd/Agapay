import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../models/evacuation_center.dart';
import '../../controllers/app_controller.dart';
import '../../widgets/map/mock_map_view.dart';
import '../../widgets/common/app_buttons.dart';

/// Screen 7: Evacuation Center Tactical Map and Navigation Guide
class EvacuationMapScreen extends StatefulWidget {
  final AppController controller;

  const EvacuationMapScreen({super.key, required this.controller});

  @override
  State<EvacuationMapScreen> createState() => _EvacuationMapScreenState();
}

class _EvacuationMapScreenState extends State<EvacuationMapScreen> {
  EvacuationCenter? _selectedCenter;

  @override
  void initState() {
    super.initState();
    _selectedCenter = widget.controller.nearestEvacuationCenter;
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.controller,
      builder: (context, _) {
        final nearest = widget.controller.nearestEvacuationCenter;
        final activeShelter = _selectedCenter ?? nearest;

        return Scaffold(
          backgroundColor: AppColors.background,
          appBar: AppBar(
            title: const Text('Evacuation Shelters Map'),
            actions: [
              IconButton(
                icon: const Icon(Icons.my_location_rounded),
                onPressed: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Centered on current resident GPS position.')),
                  );
                },
              ),
            ],
          ),
          body: SafeArea(
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Tactical Map
                  MockMapView(
                    stations: widget.controller.stations,
                    evacuationCenters: widget.controller.evacuationCenters,
                    activeSos: widget.controller.activeSos,
                    height: 320,
                    onEvacuationCenterSelected: (center) {
                      setState(() => _selectedCenter = center);
                    },
                    onStationSelected: (station) {
                      widget.controller.selectStation(station.id);
                    },
                  ),
                  const SizedBox(height: 16),

                  // Nearest / Selected Evacuation Center Card
                  if (activeShelter != null) ...[
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16.0),
                      child: Container(
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: const Color(0xFF0D9488), width: 1.5),
                          boxShadow: [
                            BoxShadow(
                              color: const Color(0xFF0D9488).withOpacity(0.1),
                              blurRadius: 10,
                              offset: const Offset(0, 4),
                            ),
                          ],
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFFCCFBF1),
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: const Row(
                                    children: [
                                      Icon(Icons.near_me_rounded, size: 12, color: Color(0xFF0F766E)),
                                      SizedBox(width: 4),
                                      Text(
                                        'NEAREST SHELTER',
                                        style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: Color(0xFF0F766E)),
                                      ),
                                    ],
                                  ),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                  decoration: BoxDecoration(
                                    color: activeShelter.isOpen ? AppColors.alertNormalBg : AppColors.alertEvacuateBg,
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: Text(
                                    activeShelter.isOpen ? 'OPEN' : 'CLOSED',
                                    style: TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.w800,
                                      color: activeShelter.isOpen ? AppColors.alertNormalText : AppColors.alertEvacuateText,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 10),
                            Text(
                              activeShelter.name,
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w800,
                                color: AppColors.textPrimary,
                              ),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              activeShelter.address,
                              style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                            ),
                            const SizedBox(height: 12),
                            // Distance & Capacity Grid
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceAround,
                              children: [
                                _statBadge(Icons.route_rounded, 'Distance', '${activeShelter.distanceKm} km'),
                                _statBadge(Icons.timer_outlined, 'Est. Travel', '${activeShelter.estimatedTravelMinutes} mins'),
                                _statBadge(
                                  Icons.people_outline_rounded,
                                  'Available Slots',
                                  '${activeShelter.availableSlots} / ${activeShelter.capacity}',
                                ),
                              ],
                            ),
                            const SizedBox(height: 14),
                            // Navigation Trigger
                            PrimaryButton(
                              label: 'Start Navigation to Shelter',
                              icon: Icons.navigation_rounded,
                              onPressed: () {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(
                                    content: Text('Starting route guidance to ${activeShelter.name} via high-ground roads.'),
                                    backgroundColor: AppColors.primary,
                                  ),
                                );
                              },
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),
                  ],

                  // Full Evacuation Shelter Directory
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Community Shelters Directory',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: AppColors.textPrimary),
                        ),
                        const SizedBox(height: 10),
                        ...widget.controller.evacuationCenters.map((center) {
                          final isSelected = activeShelter?.id == center.id;
                          return Container(
                            margin: const EdgeInsets.only(bottom: 10),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(
                                color: isSelected ? AppColors.primary : AppColors.border,
                                width: isSelected ? 1.5 : 1.0,
                              ),
                            ),
                            child: ListTile(
                              leading: Container(
                                padding: const EdgeInsets.all(8),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFCCFBF1),
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: const Icon(Icons.night_shelter_rounded, color: Color(0xFF0F766E), size: 20),
                              ),
                              title: Text(center.name, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
                              subtitle: Text('${center.distanceKm} km · ${center.availableSlots} slots left'),
                              trailing: IconButton(
                                icon: const Icon(Icons.phone_rounded, color: AppColors.secondary, size: 20),
                                onPressed: () {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    SnackBar(content: Text('Calling shelter desk: ${center.contactNumber}')),
                                  );
                                },
                              ),
                              onTap: () {
                                setState(() => _selectedCenter = center);
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

  Widget _statBadge(IconData icon, String label, String value) {
    return Column(
      children: [
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 14, color: AppColors.textSecondary),
            const SizedBox(width: 4),
            Text(label, style: const TextStyle(fontSize: 11, color: AppColors.textSecondary)),
          ],
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: AppColors.textPrimary),
        ),
      ],
    );
  }
}
