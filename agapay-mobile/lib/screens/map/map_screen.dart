import 'dart:async';

import 'package:url_launcher/url_launcher.dart';

import '../../core/ui.dart';
import '../../services/auth_api.dart';
import '../../services/sos_location.dart';
import '../../widgets/maps/agapay_google_map.dart';

typedef Station = ({
  String id,
  String name,
  String barangay,
  AlertLevel? level,
  double? cm,
  AgapayMapCoordinate point,
  bool online,
  DateTime? observedAt,
  String source,
});

// UCU campus coordinate. The city ecological profile lists UCU Gym as an
// evacuation-use facility; activation and exact entrance must be confirmed by
// the Urdaneta CDRRMO during a real incident.
const _ucuGym = AgapayMapCoordinate(15.97995, 120.56083);
const _cityCenter = AgapayMapCoordinate(15.978, 120.567);

class MapScreen extends StatefulWidget {
  const MapScreen({super.key});

  @override
  State<MapScreen> createState() => _MapScreenState();
}

class _MapScreenState extends State<MapScreen> {
  AgapayMapCoordinate? _resident;
  bool _locating = false;
  bool _loadingStations = true;
  String? _error;
  String? _stationError;
  String? _routeStatus;
  String? _routeError;
  double? _routeDistanceMeters;
  int? _routeDurationSeconds;
  List<String> _routeWarnings = const [];
  List<Station> _stations = const [];
  Station? _station;
  Timer? _stationTimer;

  String? get _routeId {
    final resident = _resident;
    if (resident == null) return null;
    return '${resident.latitude.toStringAsFixed(6)},${resident.longitude.toStringAsFixed(6)}'
        '>${_ucuGym.latitude},${_ucuGym.longitude}:walking';
  }

  AgapayGoogleMapRoute? get _walkingRoute => _resident == null
      ? null
      : AgapayGoogleMapRoute(
          id: _routeId!,
          origin: _resident!,
          destination: _ucuGym,
        );

  double? get _routeDistanceKm =>
      _routeDistanceMeters == null ? null : _routeDistanceMeters! / 1000;

  int? get _walkingMinutes => _routeDurationSeconds == null
      ? null
      : (_routeDurationSeconds! / 60).ceil();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadStations();
      _stationTimer = Timer.periodic(
        const Duration(seconds: 5),
        (_) => _loadStations(),
      );
    });
  }

  @override
  void dispose() {
    _stationTimer?.cancel();
    super.dispose();
  }

  Color _markerColor(AlertLevel? level) => switch (level) {
    AlertLevel.normal => const Color(0xff22c55e),
    AlertLevel.advisory => const Color(0xffeab308),
    AlertLevel.warning => const Color(0xfff97316),
    AlertLevel.evacuate => const Color(0xffef4444),
    null => const Color(0xffa855f7),
  };

  AlertLevel? _level(dynamic value) => switch (value) {
    'NORMAL' => AlertLevel.normal,
    'ADVISORY' => AlertLevel.advisory,
    'WARNING' => AlertLevel.warning,
    'EVACUATE' => AlertLevel.evacuate,
    _ => null,
  };

  String _observed(DateTime? value) {
    if (value == null) return 'No valid reading';
    final hour = value.hour.toString().padLeft(2, '0');
    final minute = value.minute.toString().padLeft(2, '0');
    return '${value.month}/${value.day}/${value.year} $hour:$minute';
  }

  Future<void> _loadStations() async {
    if (!mounted) return;
    if (_stations.isEmpty) setState(() => _loadingStations = true);
    try {
      final app = AppScope.of(context);
      final raw =
          await app.auth.request('monitoring/stations?history_limit=20')
              as Map<String, dynamic>;
      final mapped = <Station>[];
      for (final value in raw['stations'] as List<dynamic>) {
        final data = value as Map<String, dynamic>;
        final latitude = (data['latitude'] as num?)?.toDouble();
        final longitude = (data['longitude'] as num?)?.toDouble();
        if (latitude == null || longitude == null) continue;
        mapped.add((
          id: data['station_id'] as String,
          name: data['station_name'] as String,
          barangay: (data['barangay'] as String?) ?? 'Barangay unavailable',
          level: _level(data['alert_tier']),
          cm: (data['current_depth_cm'] as num?)?.toDouble(),
          point: AgapayMapCoordinate(latitude, longitude),
          online: data['is_online'] as bool,
          observedAt: data['observed_at'] is String
              ? DateTime.tryParse(data['observed_at'] as String)?.toLocal()
              : null,
          source: data['source'] as String,
        ));
      }
      if (!mounted) return;
      setState(() {
        _stations = mapped;
        final selectedId = _station?.id;
        _station = null;
        for (final station in mapped) {
          if (station.id == selectedId) _station = station;
        }
        _stationError = null;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _stationError = error is AccountException
            ? error.message
            : 'Monitoring stations could not be loaded.';
      });
    } finally {
      if (mounted) setState(() => _loadingStations = false);
    }
  }

  void _selectStation(Station station) {
    setState(() => _station = station);
  }

  List<AgapayGoogleMapMarker> _markers(bool evacuation) => evacuation
      ? [
          if (_resident != null)
            AgapayGoogleMapMarker(
              id: 'resident',
              position: _resident!,
              color: const Color(0xff38bdf8),
              glyph: '●',
              title: 'Your latest GPS location',
            ),
          const AgapayGoogleMapMarker(
            id: 'ucu-gym',
            position: _ucuGym,
            color: Color(0xff22c55e),
            glyph: 'E',
            title: 'UCU Gym · confirm shelter activation',
          ),
        ]
      : [
          for (final station in _stations)
            AgapayGoogleMapMarker(
              id: station.id,
              position: station.point,
              color: station.online
                  ? _markerColor(station.level)
                  : const Color(0xffa855f7),
              glyph: station.id.replaceFirst('STATION_0', ''),
              title: station.cm == null
                  ? '${station.name} · No valid reading'
                  : '${station.name} · ${station.cm!.toStringAsFixed(1)} cm',
              selected: _station?.id == station.id,
            ),
        ];

  Future<void> _useCurrentLocation() async {
    final app = AppScope.of(context);
    if (!app.location) {
      setState(
        () => _error =
            'Location sharing is turned off in Profile / Settings. Turn it on to show your device position.',
      );
      return;
    }
    setState(() {
      _locating = true;
      _error = null;
    });
    try {
      final position = await captureSosLocation();
      if (!mounted) return;
      setState(() {
        _resident = AgapayMapCoordinate(position.latitude, position.longitude);
        _routeStatus = 'loading';
        _routeError = null;
        _routeDistanceMeters = null;
        _routeDurationSeconds = null;
        _routeWarnings = const [];
      });
    } catch (e) {
      if (!mounted) return;
      setState(
        () => _error = e is AccountException
            ? e.message
            : 'Your position could not be read. Enable precise location and try again.',
      );
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  Future<void> _openDirections() async {
    final resident = _resident;
    final uri = Uri.https('www.google.com', '/maps/dir/', {
      'api': '1',
      if (resident != null)
        'origin': '${resident.latitude},${resident.longitude}',
      'destination': '${_ucuGym.latitude},${_ucuGym.longitude}',
      'travelmode': 'walking',
    });
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication) &&
        mounted) {
      setState(() => _error = 'No directions app is available on this device.');
    }
  }

  void _onRouteUpdate(AgapayGoogleMapRouteUpdate update) {
    if (!mounted || update.id != _routeId) return;
    setState(() {
      _routeStatus = update.status;
      _routeError = update.status == 'error' ? update.message : null;
      _routeDistanceMeters = update.status == 'ready'
          ? update.distanceMeters
          : null;
      _routeDurationSeconds = update.status == 'ready'
          ? update.durationSeconds
          : null;
      _routeWarnings = update.status == 'ready' ? update.warnings : const [];
    });
  }

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final evacuation = app.evacuationMap;
    return PageContent(
      children: [
        PageHeading(
          'Map',
          'San Vicente, Urdaneta City',
          onBack: () => app.navigate(AppTab.home),
        ),
        Panel(
          padding: 4,
          radius: 12,
          child: Row(
            children: [
              for (final entry in [
                (false, 'Monitoring Stations'),
                (true, 'Evacuation Route'),
              ])
                Expanded(
                  child: Semantics(
                    selected: evacuation == entry.$1,
                    button: true,
                    child: InkWell(
                      borderRadius: BorderRadius.circular(8),
                      onTap: () {
                        app.navigate(AppTab.map, evacuation: entry.$1);
                        if (entry.$1) {
                          WidgetsBinding.instance.addPostFrameCallback((_) {
                            if (_resident == null && !_locating) {
                              _useCurrentLocation();
                            }
                          });
                        }
                      },
                      child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 9),
                        decoration: BoxDecoration(
                          color: evacuation == entry.$1
                              ? AppColors.border
                              : Colors.transparent,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: tx(
                          entry.$2,
                          size: 11,
                          display: true,
                          weight: 600,
                          color: evacuation == entry.$1
                              ? AppColors.text
                              : AppColors.muted,
                          align: TextAlign.center,
                        ),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
        gap,
        ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: SizedBox(
            height: 360,
            child: AgapayGoogleMap(
              center: evacuation ? _ucuGym : _cityCenter,
              markers: _markers(evacuation),
              route: evacuation ? _walkingRoute : null,
              zoom: evacuation ? 16.5 : 15,
              tilt: evacuation ? 45 : 42,
              fitAll: evacuation && _resident != null,
              selectedMarkerId: evacuation ? null : _station?.id,
              onMarkerTap: evacuation
                  ? null
                  : (id) {
                      for (final station in _stations) {
                        if (station.id == id) {
                          _selectStation(station);
                          return;
                        }
                      }
                    },
              onRouteUpdate: evacuation ? _onRouteUpdate : null,
            ),
          ),
        ),
        if (!evacuation && _stations.isNotEmpty) ...[
          const SizedBox(height: 8),
          Panel(
            padding: 4,
            radius: 10,
            child: Row(
              children: [
                for (final station in _stations)
                  Expanded(
                    child: TextButton(
                      onPressed: () => _selectStation(station),
                      style: TextButton.styleFrom(
                        foregroundColor: _station?.id == station.id
                            ? Colors.white
                            : AppColors.secondary,
                        backgroundColor: _station?.id == station.id
                            ? AppColors.border
                            : Colors.transparent,
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        textStyle: const TextStyle(
                          fontFamily: 'JetBrainsMono',
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      child: Text(station.id),
                    ),
                  ),
              ],
            ),
          ),
        ],
        gap,
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: tx(
              _error!,
              size: 12,
              color: const Color(0xfff87171),
              height: 1.5,
            ),
          ),
        if (evacuation) ...[
          Panel(
            color: const Color(0x80052e16),
            border: const Color(0x4016a34a),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                caption('EVACUATION DESTINATION'),
                const SizedBox(height: 6),
                tx(
                  'UCU Gym',
                  size: 17,
                  display: true,
                  weight: 700,
                  color: Colors.white,
                ),
                tx(
                  'Urdaneta City University · San Vicente West',
                  size: 11,
                  color: AppColors.secondary,
                ),
                gap,
                Row(
                  children: [
                    Expanded(
                      child: DataRow(
                        'Walking route distance',
                        _routeDistanceKm == null
                            ? 'Use device GPS'
                            : '${_routeDistanceKm!.toStringAsFixed(2)} km',
                        mono: true,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: DataRow(
                        'Estimated walk',
                        _walkingMinutes == null
                            ? _routeStatus == 'loading'
                                  ? 'Calculating…'
                                  : 'Route unavailable'
                            : '$_walkingMinutes min',
                        mono: true,
                      ),
                    ),
                  ],
                ),
                gap,
                tx(
                  'Urdaneta City’s ecological profile lists UCU Gym as an evacuation-use facility. The pin marks the campus location; confirm that the shelter is activated and which entrance is safe before traveling.',
                  size: 11,
                  color: AppColors.muted,
                  height: 1.5,
                ),
                const SizedBox(height: 8),
                tx(
                  'The cyan path follows Google’s walking route from your latest GPS position. Refresh your location if you move, and follow official evacuation instructions if they differ from the map.',
                  size: 11,
                  color: AppColors.muted,
                  height: 1.5,
                ),
                if (_routeStatus == 'loading') ...[
                  const SizedBox(height: 8),
                  tx(
                    'Calculating the current walking route…',
                    size: 11,
                    color: AppColors.secondary,
                  ),
                ],
                if (_routeError != null) ...[
                  const SizedBox(height: 8),
                  tx(
                    'Walking route unavailable: $_routeError',
                    size: 11,
                    color: const Color(0xfff87171),
                    height: 1.5,
                  ),
                ],
                for (final warning in _routeWarnings) ...[
                  const SizedBox(height: 8),
                  tx(
                    warning,
                    size: 11,
                    color: const Color(0xfffbbf24),
                    height: 1.5,
                  ),
                ],
                gap,
                ActionButton(
                  _locating
                      ? 'LOCATING…'
                      : _resident == null
                      ? 'USE MY CURRENT LOCATION'
                      : 'REFRESH LOCATION & ROUTE',
                  vertical: 12,
                  onPressed: _locating ? null : _useCurrentLocation,
                ),
                const SizedBox(height: 8),
                OutlinedButton(
                  onPressed: _openDirections,
                  child: const Text('OPEN WALKING DIRECTIONS'),
                ),
              ],
            ),
          ),
        ] else ...[
          Panel(
            child: _loadingStations
                ? const Center(child: CircularProgressIndicator())
                : _stationError != null
                ? Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      tx(
                        _stationError!,
                        size: 12,
                        color: const Color(0xfff87171),
                      ),
                      TextButton(
                        onPressed: _loadStations,
                        child: const Text('RETRY'),
                      ),
                    ],
                  )
                : _stations.isEmpty
                ? Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      tx(
                        'No deployed monitoring station has verified coordinates in the backend yet. Sample pins have been removed.',
                        size: 12,
                        color: AppColors.secondary,
                        height: 1.5,
                      ),
                      const SizedBox(height: 8),
                      OutlinedButton(
                        onPressed: _loadStations,
                        child: const Text('REFRESH STATIONS'),
                      ),
                    ],
                  )
                : _station == null
                ? tx(
                    'Tap a deployed monitoring-station marker to see its latest backend reading.',
                    size: 12,
                    color: AppColors.secondary,
                  )
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      caption(_station!.id),
                      const SizedBox(height: 4),
                      tx(
                        _station!.name,
                        display: true,
                        weight: 700,
                        color: Colors.white,
                      ),
                      gap,
                      DataRow(
                        'Water level',
                        _station!.cm == null
                            ? 'No valid reading'
                            : '${_station!.cm!.toStringAsFixed(1)} cm',
                        mono: true,
                      ),
                      DataRow('Alert', _station!.level?.label ?? 'Unavailable'),
                      DataRow(
                        'Connection',
                        _station!.online ? 'ONLINE' : 'OFFLINE',
                      ),
                      DataRow(
                        'Source',
                        _station!.source == 'simulator'
                            ? 'VIRTUAL STATION'
                            : _station!.source.toUpperCase(),
                      ),
                      DataRow('Barangay', _station!.barangay),
                      DataRow('Observed', _observed(_station!.observedAt)),
                    ],
                  ),
          ),
        ],
      ],
    );
  }
}
