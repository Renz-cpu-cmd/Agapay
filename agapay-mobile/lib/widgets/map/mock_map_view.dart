import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../models/alert_tier.dart';
import '../../models/station.dart';
import '../../models/evacuation_center.dart';
import '../../models/sos_beacon.dart';

enum MapFilter { all, stations, shelters, sos }

/// Tactical Interactive Canvas Map for Stations, Evacuation Shelters, and SOS Beacons
class MockMapView extends StatefulWidget {
  final List<Station> stations;
  final List<EvacuationCenter> evacuationCenters;
  final SosBeacon? activeSos;
  final Function(Station)? onStationSelected;
  final Function(EvacuationCenter)? onEvacuationCenterSelected;
  final double height;
  final bool showControls;

  const MockMapView({
    super.key,
    required this.stations,
    required this.evacuationCenters,
    this.activeSos,
    this.onStationSelected,
    this.onEvacuationCenterSelected,
    this.height = 360,
    this.showControls = true,
  });

  @override
  State<MockMapView> createState() => _MockMapViewState();
}

class _MockMapViewState extends State<MockMapView> {
  MapFilter _currentFilter = MapFilter.all;
  dynamic _selectedEntity; // Station, EvacuationCenter, or SosBeacon

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        if (widget.showControls) ...[
          // Filter Chips
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: [
                _filterChip(MapFilter.all, 'All Map Assets', Icons.layers_rounded),
                const SizedBox(width: 8),
                _filterChip(MapFilter.stations, 'Stations (${widget.stations.length})', Icons.sensors_rounded),
                const SizedBox(width: 8),
                _filterChip(MapFilter.shelters, 'Shelters (${widget.evacuationCenters.length})', Icons.night_shelter_rounded),
                if (widget.activeSos != null) ...[
                  const SizedBox(width: 8),
                  _filterChip(MapFilter.sos, 'Active SOS', Icons.emergency_rounded),
                ],
              ],
            ),
          ),
        ],
        // Interactive Canvas Container
        Container(
          height: widget.height,
          margin: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(
            color: const Color(0xFFE5EEF5), // Waterway terrain tint
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.border, width: 1.5),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.04),
                blurRadius: 10,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(15),
            child: Stack(
              children: [
                // Custom Map Grid & River Painter
                Positioned.fill(
                  child: CustomPaint(
                    painter: _MapTerrainPainter(),
                  ),
                ),

                // Station Markers
                if (_currentFilter == MapFilter.all || _currentFilter == MapFilter.stations)
                  ...widget.stations.map((st) {
                    // Normalize station coords to view area
                    final x = 0.25 + ((st.longitude - 120.9450) / 0.030) * 0.55;
                    final y = 0.20 + ((st.latitude - 14.7250) / 0.025) * 0.60;

                    return Positioned(
                      left: (x * 320).clamp(20.0, 280.0),
                      top: (y * (widget.height - 40)).clamp(20.0, widget.height - 60.0),
                      child: GestureDetector(
                        onTap: () {
                          setState(() => _selectedEntity = st);
                          widget.onStationSelected?.call(st);
                        },
                        child: _stationMarkerWidget(st),
                      ),
                    );
                  }),

                // Evacuation Shelter Markers
                if (_currentFilter == MapFilter.all || _currentFilter == MapFilter.shelters)
                  ...widget.evacuationCenters.map((shelter) {
                    final x = 0.35 + ((shelter.longitude - 120.9450) / 0.030) * 0.50;
                    final y = 0.28 + ((shelter.latitude - 14.7250) / 0.025) * 0.50;

                    return Positioned(
                      left: (x * 320).clamp(20.0, 280.0),
                      top: (y * (widget.height - 40)).clamp(20.0, widget.height - 60.0),
                      child: GestureDetector(
                        onTap: () {
                          setState(() => _selectedEntity = shelter);
                          widget.onEvacuationCenterSelected?.call(shelter);
                        },
                        child: _shelterMarkerWidget(shelter),
                      ),
                    );
                  }),

                // User Location Pin (Center-ish)
                Positioned(
                  left: 150,
                  top: widget.height * 0.48,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: AppColors.primary,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text(
                          'You',
                          style: TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold),
                        ),
                      ),
                      const SizedBox(height: 2),
                      Container(
                        width: 16,
                        height: 16,
                        decoration: BoxDecoration(
                          color: AppColors.primaryLight,
                          shape: BoxShape.circle,
                          border: Border.all(color: Colors.white, width: 2.5),
                          boxShadow: const [BoxShadow(color: Colors.black26, blurRadius: 4)],
                        ),
                      ),
                    ],
                  ),
                ),

                // Active SOS Marker
                if (widget.activeSos != null &&
                    (_currentFilter == MapFilter.all || _currentFilter == MapFilter.sos))
                  Positioned(
                    left: 165,
                    top: widget.height * 0.44,
                    child: Container(
                      padding: const EdgeInsets.all(6),
                      decoration: BoxDecoration(
                        color: AppColors.sosRed,
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white, width: 2),
                        boxShadow: [
                          BoxShadow(color: AppColors.sosRed.withOpacity(0.5), blurRadius: 8, spreadRadius: 2),
                        ],
                      ),
                      child: const Icon(Icons.emergency_rounded, color: Colors.white, size: 16),
                    ),
                  ),

                // Map Legend Overlay (Top Right)
                Positioned(
                  top: 10,
                  right: 10,
                  child: Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.92),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _legendRow(AppColors.alertNormal, 'Station (Safe)'),
                        const SizedBox(height: 3),
                        _legendRow(AppColors.alertWarning, 'Station (Warning)'),
                        const SizedBox(height: 3),
                        _legendRow(const Color(0xFF0D9488), 'Evacuation Shelter'),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _stationMarkerWidget(Station st) {
    final isSelected = _selectedEntity == st;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          padding: const EdgeInsets.all(6),
          decoration: BoxDecoration(
            color: st.alertTier.color,
            shape: BoxShape.circle,
            border: Border.all(color: isSelected ? Colors.black : Colors.white, width: isSelected ? 2.5 : 2),
            boxShadow: [
              BoxShadow(
                color: st.alertTier.color.withOpacity(0.4),
                blurRadius: 6,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: const Icon(
            Icons.sensors_rounded,
            color: Colors.white,
            size: 15,
          ),
        ),
        Container(
          margin: const EdgeInsets.only(top: 2),
          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.95),
            borderRadius: BorderRadius.circular(4),
            border: Border.all(color: AppColors.border, width: 0.8),
          ),
          child: Text(
            '${st.waterDepthCm.toInt()} cm',
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w800,
              color: st.alertTier.color,
            ),
          ),
        ),
      ],
    );
  }

  Widget _shelterMarkerWidget(EvacuationCenter shelter) {
    final isSelected = _selectedEntity == shelter;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          padding: const EdgeInsets.all(6),
          decoration: BoxDecoration(
            color: const Color(0xFF0D9488), // Teal / Green Shelter color
            shape: BoxShape.circle,
            border: Border.all(color: isSelected ? Colors.black : Colors.white, width: isSelected ? 2.5 : 2),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF0D9488).withOpacity(0.4),
                blurRadius: 6,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: const Icon(
            Icons.night_shelter_rounded,
            color: Colors.white,
            size: 15,
          ),
        ),
        Container(
          margin: const EdgeInsets.only(top: 2),
          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.95),
            borderRadius: BorderRadius.circular(4),
            border: Border.all(color: AppColors.border, width: 0.8),
          ),
          child: Text(
            '${shelter.availableSlots} slots',
            style: const TextStyle(
              fontSize: 9,
              fontWeight: FontWeight.w700,
              color: Color(0xFF0D9488),
            ),
          ),
        ),
      ],
    );
  }

  Widget _legendRow(Color color, String text) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 5),
        Text(text, style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w600, color: AppColors.textPrimary)),
      ],
    );
  }

  Widget _filterChip(MapFilter filter, String label, IconData icon) {
    final isSelected = _currentFilter == filter;
    return FilterChip(
      selected: isSelected,
      label: Text(label),
      avatar: Icon(icon, size: 16, color: isSelected ? Colors.white : AppColors.textSecondary),
      selectedColor: AppColors.primary,
      backgroundColor: Colors.white,
      checkmarkColor: Colors.white,
      labelStyle: TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.w600,
        color: isSelected ? Colors.white : AppColors.textPrimary,
      ),
      side: BorderSide(color: isSelected ? AppColors.primary : AppColors.border),
      onSelected: (val) {
        setState(() => _currentFilter = filter);
      },
    );
  }
}

/// Custom painter for tactical topographic terrain and river pathways
class _MapTerrainPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;

    // Roads / Streets Grid
    final roadPaint = Paint()
      ..color = Colors.white.withOpacity(0.7)
      ..strokeWidth = 3.5;

    canvas.drawLine(Offset(0, h * 0.35), Offset(w, h * 0.35), roadPaint);
    canvas.drawLine(Offset(0, h * 0.70), Offset(w, h * 0.70), roadPaint);
    canvas.drawLine(Offset(w * 0.30, 0), Offset(w * 0.30, h), roadPaint);
    canvas.drawLine(Offset(w * 0.75, 0), Offset(w * 0.75, h), roadPaint);

    // River Pathway
    final riverPath = Path();
    riverPath.moveTo(0, h * 0.15);
    riverPath.cubicTo(w * 0.35, h * 0.25, w * 0.45, h * 0.65, w, h * 0.55);
    riverPath.lineTo(w, h * 0.68);
    riverPath.cubicTo(w * 0.45, h * 0.78, w * 0.35, h * 0.38, 0, h * 0.28);
    riverPath.close();

    final riverPaint = Paint()
      ..color = const Color(0xFF93C5FD).withOpacity(0.85)
      ..style = PaintingStyle.fill;
    canvas.drawPath(riverPath, riverPaint);

    // River Center Flow Line
    final riverCenterPath = Path();
    riverCenterPath.moveTo(0, h * 0.21);
    riverCenterPath.cubicTo(w * 0.35, h * 0.31, w * 0.45, h * 0.71, w, h * 0.61);

    final riverStroke = Paint()
      ..color = const Color(0xFF3B82F6).withOpacity(0.6)
      ..strokeWidth = 1.8
      ..style = PaintingStyle.stroke;
    canvas.drawPath(riverCenterPath, riverStroke);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
