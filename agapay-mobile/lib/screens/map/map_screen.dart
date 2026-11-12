import '../../widgets/common/monitoring_status.dart';
import '../../widgets/common/resident_decisions.dart';
import '../../core/ui.dart';
import '../../models/monitoring.dart';
import '../../controllers/monitoring_controller.dart';
import '../../widgets/maps/agapay_google_map.dart';
import 'shelter_explorer.dart';
import '../../widgets/common/unverified_station_banner.dart';

class MapScreen extends StatefulWidget {
  const MapScreen({super.key});
  @override
  State<MapScreen> createState() => _MapScreenState();
}

/// R4: neutral pin for a station whose reading must not read as an operational
/// warning. Uses the shared fail-closed MonitoringStation.operationallyVerified.
const unverifiedMarkerColor = Color(0xff94a3b8);
bool _unverified(StationFreshnessView v) =>
    v.depth.value != null && !v.station.operationallyVerified;

class _MapScreenState extends State<MapScreen> {
  bool _showMap = true;
  Color _markerColor(StationFreshnessView v) => !v.depth.fresh
      ? const Color(0xffa855f7)
      : _unverified(v)
      ? unverifiedMarkerColor
      : switch (v.station.observationLevel) {
          AlertLevel.normal => const Color(0xff22c55e),
          AlertLevel.advisory => const Color(0xffeab308),
          AlertLevel.warning => const Color(0xfff97316),
          AlertLevel.evacuate => const Color(0xffef4444),
          _ => const Color(0xffa855f7),
        };
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context), monitoring = app.monitoring;
    final views = monitoring.views;
    // R1: only validated registry positions are mapped; nothing is substituted.
    final mapped = views.where((v) => v.station.mapCoordinates != null).toList();
    final selected = monitoring.primaryView;
    final center =
        mapped.where((v) => v.station.id == selected?.station.id).firstOrNull ??
        mapped.firstOrNull;
    return PageContent(
      children: [
        PageHeading('Map', 'Evacuation & Station Map'),
        Panel(
          padding: 4,
          radius: 12,
          child: Row(
            children: [
              Expanded(
                child: SelectionButton(
                  'Monitoring Stations',
                  outlined: false,
                  selected: !app.evacuationMap,
                  onPressed: () => app.navigate(AppTab.map, evacuation: false),
                ),
              ),
              const SizedBox(width: 4),
              Expanded(
                child: SelectionButton(
                  'Evacuation Route',
                  outlined: false,
                  selected: app.evacuationMap,
                  onPressed: () => app.navigate(AppTab.map, evacuation: true),
                ),
              ),
            ],
          ),
        ),
        gap,
        if (app.evacuationMap)
          const ShelterExplorer()
        else ...[
          if (monitoring.loading) const Text('Checking station observations…'),
          if (monitoring.error != null)
            const Text(
              'Station feed unavailable. Retained measurements keep their original age; current conditions are unconfirmed.',
            ),
          if (views.isEmpty)
            const Text(
              'No monitoring stations are available. No sample pin or reading is substituted.',
            ),
          if (center != null) ...[
            if (_showMap)
              ClipRRect(
                borderRadius: BorderRadius.circular(16),
                child: SizedBox(
                  height: 360,
                  child: AgapayGoogleMap(
                    center: AgapayMapCoordinate(
                      center.station.mapCoordinates!.latitude,
                      center.station.mapCoordinates!.longitude,
                    ),
                    markers: [
                      for (final v in mapped)
                        AgapayGoogleMapMarker(
                          id: v.station.id,
                          title:
                              '${v.station.name} · ${_unverified(v) ? '$unverifiedStationTitle · ' : ''}${stationStatusDescription(v)}',
                          position: AgapayMapCoordinate(
                            v.station.mapCoordinates!.latitude,
                            v.station.mapCoordinates!.longitude,
                          ),
                          color: _markerColor(v),
                          glyph: _unverified(v) ? 'U' : 'S',
                          selected: v.station.id == selected?.station.id,
                        ),
                    ],
                    selectedMarkerId: selected?.station.id,
                    onMarkerTap: app.selectStation,
                  ),
                ),
              ),
          ] else
            const Text(
              'No station coordinates are available. The text list works without Maps.',
            ),
          if (views.isNotEmpty) ...[
            const SizedBox(height: 8),
            Panel(
              padding: 4,
              radius: 10,
              child: Wrap(
                spacing: 4,
                runSpacing: 4,
                children: [
                  for (final view in views)
                    SizedBox(
                      width: views.length == 1 ? double.infinity : null,
                      child: TextButton(
                        onPressed: () => app.selectStation(view.station.id),
                        style: TextButton.styleFrom(
                          foregroundColor:
                              view.station.id == selected?.station.id
                              ? context.colors.text
                              : context.colors.muted,
                          backgroundColor:
                              view.station.id == selected?.station.id
                              ? context.colors.border
                              : Colors.transparent,
                        ),
                        child: Text(view.station.id),
                      ),
                    ),
                ],
              ),
            ),
          ],
          gap,
          Panel(
            radius: 5,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                caption('STATION LEGEND'),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 14,
                  runSpacing: 10,
                  children: [
                    for (final tier in AlertLevel.values.where(
                      (v) => v != AlertLevel.unknown,
                    ))
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Dot(context.colors.resolve(tier.textColor), size: 8),
                          const SizedBox(width: 6),
                          Flexible(
                            child: tx(
                              tier.label[0] +
                                  tier.label.substring(1).toLowerCase(),
                              size: 11,
                              color: context.colors.muted,
                            ),
                          ),
                        ],
                      ),
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Dot(
                          context.colors.resolve(const Color(0xffa855f7)),
                          size: 8,
                        ),
                        const SizedBox(width: 6),
                        Flexible(
                          child: tx(
                            'No current reading',
                            size: 11,
                            color: context.colors.muted,
                          ),
                        ),
                      ],
                    ),
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Dot(
                          context.colors.resolve(unverifiedMarkerColor),
                          size: 8,
                        ),
                        const SizedBox(width: 6),
                        Flexible(
                          child: tx(
                            'Unverified station · not a warning',
                            size: 11,
                            color: context.colors.muted,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                tx(
                  'Colors show the observation tier of reviewed stations. Unverified stations are grey. Connection and measurement quality are listed separately.',
                  size: 10,
                  color: context.colors.muted,
                ),
              ],
            ),
          ),
          for (final view in views)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Panel(
                border: view.station.id == selected?.station.id
                    ? context.colors.link
                    : context.colors.border,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    caption(view.station.id),
                    const SizedBox(height: 6),
                    tx(view.station.name, size: 16, weight: 700),
                    if (_unverified(view)) ...[
                      const SizedBox(height: 10),
                      UnverifiedStationBanner(
                        key: ValueKey('map-unverified-${view.station.id}'),
                        compact: true,
                      ),
                    ],
                    const SizedBox(height: 16),
                    _MapFact(
                      view.depth.fresh
                          ? 'Observed water depth'
                          : view.depth.value == null
                          ? 'Water depth'
                          : 'Last known water depth',
                      view.depth.value == null
                          ? 'No valid reading'
                          : '${view.depth.value!.toStringAsFixed(1)} cm',
                    ),
                    _MapFact(
                      'Observation tier',
                      // Stale data never shows a current tier; unverified data is a
                      // recorded measurement, not an operational warning.
                      !view.depth.fresh
                          ? 'UNKNOWN · reading not current'
                          : _unverified(view)
                          ? 'Recorded ${view.station.observationLevel.label} reading · unverified'
                          : view.station.observationLevel.label,
                    ),
                    _MapFact('Connection', view.heartbeat.status.toUpperCase()),
                    _MapFact('Source', view.sourceLabel),
                    tx(
                      'Depth: ${view.depth.status} · ${MonitoringController.ageLabel(view.depth.ageSeconds)} · quality ${view.depth.quality}',
                      size: 10,
                      color: context.colors.muted,
                    ),
                    tx(
                      'Heartbeat: ${view.heartbeat.status} · rain: ${view.rain.status} · episode: ${view.station.activeHazardTier ?? 'None recorded'}',
                      size: 10,
                      color: context.colors.muted,
                    ),
                    ExpansionTile(
                      key: PageStorageKey(
                        'map-source-${app.user?.id}-${view.station.id}',
                      ),
                      title: const Text('Source and measurement details'),
                      children: [MonitoringStatus(view: view)],
                    ),
                    switch (view.station.locationState) {
                      'verified' => _MapFact('Location', 'Confirmed registry location'),
                      'unverified' => _MapFact('Location', 'Unconfirmed registry location'),
                      'missing' => const Text('Coordinates unavailable · no map pin'),
                      _ => const Text('Recorded location invalid · no map pin'),
                    },
                  ],
                ),
              ),
            ),
          gap,
          Wrap(
            spacing: 8,
            runSpacing: 4,
            children: [
              TextButton(
                onPressed: monitoring.loading ? null : monitoring.refresh,
                child: const Text('Refresh stations'),
              ),
              if (center != null)
                TextButton(
                  onPressed: () => setState(() => _showMap = !_showMap),
                  child: Text(
                    _showMap ? 'Hide station map' : 'Show station map',
                  ),
                ),
            ],
          ),
          const ExpansionTile(
            key: PageStorageKey('map-area-preferences'),
            title: Text('Area and advisory preferences'),
            children: [ResidentAreaPanel()],
          ),
        ],
      ],
    );
  }
}

class _MapFact extends StatelessWidget {
  const _MapFact(this.label, this.value);
  final String label, value;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 5),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(child: tx(label, size: 11, color: context.colors.muted)),
        const SizedBox(width: 12),
        Flexible(
          child: tx(value, size: 12, weight: 600, align: TextAlign.right),
        ),
      ],
    ),
  );
}
