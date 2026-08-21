import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../models/station.dart';
import '../../models/alert_tier.dart';
import '../../controllers/app_controller.dart';
import '../../widgets/map/mock_map_view.dart';
import '../../widgets/cards/station_card.dart';
import '../../navigation/app_routes.dart';

/// Screen 9: Station Map & Monitoring Network Directory
class StationMapScreen extends StatefulWidget {
  final AppController controller;

  const StationMapScreen({super.key, required this.controller});

  @override
  State<StationMapScreen> createState() => _StationMapScreenState();
}

class _StationMapScreenState extends State<StationMapScreen> {
  AlertTier? _selectedTierFilter;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.controller,
      builder: (context, _) {
        final stations = widget.controller.stations;
        final filteredStations = _selectedTierFilter == null
            ? stations
            : stations.where((s) => s.alertTier == _selectedTierFilter).toList();

        return Scaffold(
          backgroundColor: AppColors.background,
          appBar: AppBar(
            title: const Text('Sensor Stations Network'),
            actions: [
              IconButton(
                icon: const Icon(Icons.refresh_rounded),
                onPressed: widget.controller.refreshData,
              ),
            ],
          ),
          body: SafeArea(
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Tactical Map view
                  MockMapView(
                    stations: filteredStations,
                    evacuationCenters: widget.controller.evacuationCenters,
                    height: 280,
                    onStationSelected: (st) {
                      widget.controller.selectStation(st.id);
                      _showStationDetailBottomSheet(context, st);
                    },
                  ),
                  const SizedBox(height: 12),

                  // Tier Filter Pills
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: Row(
                      children: [
                        _filterPill('All (${stations.length})', null),
                        const SizedBox(width: 8),
                        _filterPill('Normal', AlertTier.normal),
                        const SizedBox(width: 8),
                        _filterPill('Advisory', AlertTier.advisory),
                        const SizedBox(width: 8),
                        _filterPill('Warning', AlertTier.warning),
                        const SizedBox(width: 8),
                        _filterPill('Evacuate', AlertTier.evacuate),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Station Directory Cards List
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text(
                              'Active River Sensors',
                              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: AppColors.textPrimary),
                            ),
                            Text(
                              '${filteredStations.length} reporting',
                              style: const TextStyle(fontSize: 12, color: AppColors.textSecondary, fontWeight: FontWeight.w600),
                            ),
                          ],
                        ),
                        const SizedBox(height: 10),
                        ...filteredStations.map((station) {
                          final isSelected = widget.controller.selectedStation?.id == station.id;
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 12.0),
                            child: StationCard(
                              station: station,
                              isSelected: isSelected,
                              onTap: () {
                                widget.controller.selectStation(station.id);
                                _showStationDetailBottomSheet(context, station);
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

  Widget _filterPill(String label, AlertTier? tier) {
    final isSelected = _selectedTierFilter == tier;
    return ChoiceChip(
      selected: isSelected,
      label: Text(label),
      selectedColor: tier?.color ?? AppColors.primary,
      backgroundColor: Colors.white,
      labelStyle: TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.w700,
        color: isSelected ? Colors.white : AppColors.textPrimary,
      ),
      side: BorderSide(color: isSelected ? (tier?.color ?? AppColors.primary) : AppColors.border),
      onSelected: (val) {
        setState(() => _selectedTierFilter = val ? tier : null);
      },
    );
  }

  void _showStationDetailBottomSheet(BuildContext context, Station station) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
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
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Text(
                        station.name,
                        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close_rounded),
                      onPressed: () => Navigator.pop(ctx),
                    ),
                  ],
                ),
                Text(
                  '${station.barangay} · ${station.distanceKm} km away',
                  style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
                ),
                const SizedBox(height: 16),
                StationCard(station: station),
                const SizedBox(height: 16),
                ElevatedButton.icon(
                  onPressed: () {
                    Navigator.pop(ctx);
                    widget.controller.selectStation(station.id);
                    Navigator.pushNamed(context, AppRoutes.waterLevelDetails);
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    foregroundColor: Colors.white,
                    minimumSize: const Size(double.infinity, 48),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  icon: const Icon(Icons.insights_rounded, size: 18),
                  label: const Text('View Full Telemetry & Forecasts', style: TextStyle(fontWeight: FontWeight.w700)),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
