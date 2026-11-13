import 'dart:async';
import 'package:geolocator/geolocator.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../core/ui.dart';
import '../../services/sos_location.dart';
import '../../widgets/maps/agapay_google_map.dart';
import '../../widgets/common/resource_instructions.dart';
import '../../models/response_resource.dart';
import '../../models/community_alert.dart';
import '../../controllers/monitoring_controller.dart';

class ShelterExplorer extends StatefulWidget {
  const ShelterExplorer({super.key, this.captureLocation = captureSosLocation});
  final Future<Position> Function() captureLocation;
  @override
  State<ShelterExplorer> createState() => _ShelterExplorerState();
}

class _ShelterExplorerState extends State<ShelterExplorer> {
  String? _selected, _error;
  AgapayMapCoordinate? _origin;
  bool _locating = false, _showMap = false;
  String? _scope;
  AgapayGoogleMapRouteUpdate? _route;
  Timer? _clock;
  @override
  void initState() {
    super.initState();
    _clock = Timer.periodic(const Duration(seconds: 5), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final scope =
        '${AppScope.of(context).user?.id}:${AppScope.of(context).resources.areaId}';
    if (_scope != scope) {
      _scope = scope;
      _selected = null;
      _origin = null;
      _route = null;
      _error = null;
      _showMap = false;
    }
  }

  @override
  void dispose() {
    _clock?.cancel();
    super.dispose();
  }

  AgapayMapCoordinate point(Map data) => AgapayMapCoordinate(
    (data['latitude'] as num).toDouble(),
    (data['longitude'] as num).toDouble(),
  );
  Future<void> locate() async {
    final app = AppScope.of(context),
        owner = AppScope.of(context).user?.id,
        area = AppScope.of(context).resources.areaId;
    if (!app.location) {
      setState(
        () => _error =
            'GPS is disabled in settings. Source instructions and contacts remain available below.',
      );
      return;
    }
    setState(() {
      _locating = true;
      _error = null;
      _route = null;
    });
    try {
      final p = await widget.captureLocation();
      if (mounted &&
          app.user?.id == owner &&
          app.location &&
          app.resources.areaId == area) {
        setState(() {
          _origin = AgapayMapCoordinate(p.latitude, p.longitude);
          _showMap = true;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              'GPS unavailable. Use the shelter address, source instructions and contacts below.',
        );
      }
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context),
        registry = app.resources,
        now = DateTime.now();
    final shelters = [...?registry.items['shelter']]
      ..sort(
        (a, b) =>
            (a.routeCandidate(now, cached: !registry.isCurrent('shelter'))
                    ? 0
                    : 1)
                .compareTo(
                  b.routeCandidate(now, cached: !registry.isCurrent('shelter'))
                      ? 0
                      : 1,
                ),
      );
    final roads = registry.items['road'] ?? <ResponseResource>[];
    final selected = shelters.where((s) => s.id == _selected).firstOrNull;
    final cached = !registry.isCurrent('shelter') || app.auth.offlineReader;
    final eligible = selected?.routeCandidate(now, cached: cached) == true;
    final destination = selected == null
        ? null
        : point((selected.data['point'] as Map).cast<String, dynamic>());
    final routeId = eligible && _origin != null
        ? '${selected!.id}:${selected.raw['version']}:${_origin!.latitude}:${_origin!.longitude}'
        : null;
    final route = _route?.id == routeId ? _route : null;
    final overlays = [
      for (final road in roads)
        AgapayGoogleMapPolyline(
          id: road.id,
          title: '${road.name} · ${road.state} · ${road.verification(now)}',
          points: [
            for (final p in road.data['geometry'] as List)
              point((p as Map).cast<String, dynamic>()),
          ],
          color:
              road.verification(now) == 'verified' &&
                  registry.isCurrent('road') &&
                  !app.auth.offlineReader &&
                  road.state != 'reopened'
              ? '#ef4444'
              : '#eab308',
        ),
    ];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        tx(
          'Shelter inventory & reported road restrictions',
          size: 18,
          weight: 700,
        ),
        Text(
          registry.areaId == null
              ? 'All published areas · choose your area above for relevant resources.'
              : 'Resources explicitly published for area ${registry.areaId}',
        ),
        Text(
          'Active verified: ${shelters.where((r) => r.routeCandidate(now, cached: cached)).length} · other statuses: ${shelters.where((r) => !r.routeCandidate(now, cached: cached)).length}',
        ),
        if (registry.checkedAt['shelter'] != null)
          Text(
            'Inventory checked ${MonitoringController.ageLabel(DateTime.now().difference(registry.checkedAt['shelter']!).inSeconds)} · ${communityAlertTime(registry.checkedAt['shelter']!)} · ${cached ? 'LAST KNOWN / availability unconfirmed' : 'Capacity is dated separately'}',
          ),
        Text(
          'Road reports available: ${roads.length}${registry.isCurrent('road') ? '' : ' · current source unconfirmed'}. Coverage is partial; missing reports do not establish passability.',
        ),
        if (_error != null) tx(_error!, color: context.colors.red, size: 12),
        if (registry.errors['shelter'] != null)
          tx(registry.errors['shelter']!, size: 12),
        TextButton(
          onPressed: registry.busy ? null : () => registry.refresh(),
          child: const Text('Refresh shelter and road sources'),
        ),
        if (shelters.isEmpty)
          tx(
            'No authority-maintained shelter is published for this view. No sample destination is substituted.',
            size: 12,
          ),
        if ((registry.totals['shelter'] ?? 0) > shelters.length)
          tx(
            'Showing a page of ${shelters.length} of ${registry.totals['shelter']} shelters. Use the page controls for remaining records.',
            size: 12,
          ),
        for (final s in shelters)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Panel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  ResourceInstructions(resource: s, cached: cached),
                  TextButton(
                    onPressed: () => setState(() {
                      _selected = s.id;
                      _route = null;
                    }),
                    child: const Text('Select this shelter on map'),
                  ),
                ],
              ),
            ),
          ),
        _pages('shelter'),
        tx(
          'Generic walking directions do not establish flood-safe access and do not incorporate the road reports shown here. Confirm access with the listed source.',
          size: 12,
        ),
        if (selected != null) ...[
          gap,
          tx('Selected: ${selected.name}', weight: 700),
          if (!eligible)
            tx(
              'Directions disabled: shelter is inactive, full, unverified, expired or cached. Current activation and space are not confirmed.',
              size: 12,
            ),
          TextButton(
            onPressed: eligible && !_locating ? locate : null,
            child: Text(
              _locating
                  ? 'Locating…'
                  : 'Use GPS for generic walking directions',
            ),
          ),
          const Text(
            'Requesting directions shares your captured origin and shelter coordinates with Google Maps. Road closures are not incorporated into its route.',
          ),
          if (route?.status == 'ready')
            tx(
              'Generic estimate: ${route!.distanceMeters?.round() ?? 'unknown'} m · ${route.durationSeconds == null ? 'unknown' : (route.durationSeconds! / 60).ceil()} min. Flood safety not established.',
              size: 12,
            ),
          if (route?.status == 'error')
            tx(
              'Route unavailable. The text instructions and contacts above remain available.',
              size: 12,
            ),
          for (final warning in route?.warnings ?? <String>[])
            tx(warning, size: 12),
          TextButton(
            onPressed: eligible
                ? () async {
                    final uri = Uri.https('www.google.com', '/maps/dir/', {
                      'api': '1',
                      'destination':
                          '${destination!.latitude},${destination.longitude}',
                      'travelmode': 'walking',
                      if (_origin != null)
                        'origin': '${_origin!.latitude},${_origin!.longitude}',
                    });
                    try {
                      if (!await launchUrl(
                            uri,
                            mode: LaunchMode.externalApplication,
                          ) &&
                          mounted) {
                        setState(
                          () => _error =
                              'Directions app unavailable. Use source instructions and contacts.',
                        );
                      }
                    } catch (_) {
                      if (mounted) {
                        setState(
                          () => _error =
                              'Directions unavailable. Use source instructions and contacts.',
                        );
                      }
                    }
                  }
                : null,
            child: const Text(
              'Open generic directions · closures not incorporated',
            ),
          ),
        ],
        if (shelters.isNotEmpty)
          TextButton(
            onPressed: () => setState(() => _showMap = !_showMap),
            child: Text(_showMap ? 'Hide shelter map' : 'Show shelter map'),
          ),
        if (_showMap)
          SizedBox(
            height: 320,
            child: AgapayGoogleMap(
              center:
                  destination ??
                  point(
                    (shelters.first.data['point'] as Map)
                        .cast<String, dynamic>(),
                  ),
              markers: [
                for (final s in shelters)
                  AgapayGoogleMapMarker(
                    id: s.id,
                    title: '${s.name} · ${s.verification(now)} · ${s.state}',
                    position: point(
                      (s.data['point'] as Map).cast<String, dynamic>(),
                    ),
                    color: s.state == 'full'
                        ? const Color(0xfff97316)
                        : s.verification(now) != 'verified'
                        ? const Color(0xffa855f7)
                        : s.state == 'inactive'
                        ? const Color(0xff64748b)
                        : const Color(0xff38bdf8),
                    glyph: 'S',
                    selected: s.id == _selected,
                  ),
              ],
              overlays: overlays,
              route: routeId == null
                  ? null
                  : AgapayGoogleMapRoute(
                      id: routeId,
                      origin: _origin!,
                      destination: destination!,
                    ),
              onMarkerTap: (id) => setState(() {
                _selected = id;
                _route = null;
              }),
              onRouteUpdate: (result) {
                if (mounted &&
                    result.id == routeId &&
                    _scope == '${app.user?.id}:${registry.areaId}') {
                  setState(() => _route = result);
                }
              },
            ),
          ),
        if (_showMap)
          tx(
            'Red: currently verified closure/restriction reports. Amber: expired, reopened or last-known reports; current passability is unconfirmed. Coverage is partial, including when no report is listed.',
            size: 11,
          ),
        gap,
        caption('ROAD REPORTS · TEXT FALLBACK'),
        if (registry.errors['road'] != null)
          tx(registry.errors['road']!, size: 12),
        if (roads.isEmpty)
          tx(
            'No road report is available. This does not mean roads are open.',
            size: 12,
          ),
        for (final road in roads)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Panel(
              child: ResourceInstructions(
                resource: road,
                cached: !registry.isCurrent('road') || app.auth.offlineReader,
              ),
            ),
          ),
        gap,
        _pages('road'),
        const PreparednessPanel(),
      ],
    );
  }

  Widget _pages(String kind) {
    final registry = AppScope.of(context).resources,
        offset = AppScope.of(context).resources.offsets[kind] ?? 0;
    return Wrap(
      spacing: 8,
      children: [
        Text(
          'Showing ${registry.items[kind]?.length ?? 0} of ${registry.totals[kind] ?? 0} · page ${offset ~/ 100 + 1}',
        ),
        TextButton(
          onPressed: registry.busy || offset == 0
              ? null
              : () => registry.refresh(kind: kind, offset: offset - 100),
          child: Text('Previous $kind records'),
        ),
        TextButton(
          onPressed:
              registry.busy || offset + 100 >= (registry.totals[kind] ?? 0)
              ? null
              : () => registry.refresh(kind: kind, offset: offset + 100),
          child: Text('Next $kind records'),
        ),
      ],
    );
  }
}
