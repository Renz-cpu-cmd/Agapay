import 'dart:async';
import 'package:geolocator/geolocator.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../core/ui.dart';
import '../../controllers/sos_controller.dart';
import '../../models/sos_request.dart';
import '../../services/auth_api.dart';
import '../../services/sos_location.dart';
import '../../widgets/maps/agapay_google_map.dart';

enum SosPhase { idle, confirm, details }

class SosScreen extends StatefulWidget {
  const SosScreen({super.key});
  @override
  State<SosScreen> createState() => _SosScreenState();
}

class _SosScreenState extends State<SosScreen>
    with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  SosPhase _phase = SosPhase.idle;
  final _message = TextEditingController();
  final _location = TextEditingController();
  final _latitude = TextEditingController();
  final _longitude = TextEditingController();
  Position? _position;
  bool _locating = false;
  String? _formError;
  SosRequest? _selected;
  AppController? _app;
  Timer? _timer;
  bool _foreground = true;
  bool _shareLive = true;
  bool _uploadingFix = false;
  int? _sharingSosId;
  DateTime? _lastLocationUpload;
  StreamSubscription<Position>? _locationStream;
  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1800),
  )..repeat();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _timer = Timer.periodic(const Duration(seconds: 5), (_) async {
      if (_foreground && _app?.tab == AppTab.sos) {
        await _app?.sos.refresh();
        _syncSharingState();
      }
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _app = AppScope.of(context);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _foreground = state == AppLifecycleState.resumed;
    if (_foreground) {
      _app?.sos.refresh();
      _startLocationStream();
    } else {
      _cancelLocationStream();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _timer?.cancel();
    _cancelLocationStream();
    _message.dispose();
    _location.dispose();
    _latitude.dispose();
    _longitude.dispose();
    _pulse.dispose();
    super.dispose();
  }

  void _syncSharingState() {
    final id = _sharingSosId;
    if (id == null) return;
    if (_app?.location != true) {
      _stopLiveSharing();
      return;
    }
    for (final item in _app!.sos.items) {
      if (item.id == id && item.status == 'RESOLVED') {
        _stopLiveSharing();
        return;
      }
    }
  }

  void _startLiveSharing(int sosId) {
    _sharingSosId = sosId;
    _lastLocationUpload = null;
    _startLocationStream();
  }

  void _startLocationStream() {
    if (!_foreground ||
        _sharingSosId == null ||
        _locationStream != null ||
        _app?.location != true) {
      return;
    }
    _locationStream =
        Geolocator.getPositionStream(
          locationSettings: AndroidSettings(
            accuracy: LocationAccuracy.high,
            distanceFilter: 10,
            intervalDuration: Duration(seconds: 5),
            forceLocationManager: true,
          ),
        ).listen(
          _uploadLocation,
          onError: (_) {
            if (mounted) {
              setState(
                () => _formError =
                    'Live location paused because the device position is unavailable.',
              );
            }
          },
        );
  }

  Future<void> _uploadLocation(Position position) async {
    final id = _sharingSosId;
    if (id == null || _uploadingFix || !_foreground) return;
    final now = DateTime.now();
    if (_lastLocationUpload != null &&
        now.difference(_lastLocationUpload!) < const Duration(seconds: 10)) {
      return;
    }
    _uploadingFix = true;
    _lastLocationUpload = now;
    try {
      final updated = await _app!.sos.updateLocation(
        id,
        latitude: position.latitude,
        longitude: position.longitude,
        accuracyM: position.accuracy,
        recordedAt: position.timestamp,
      );
      if (!mounted || updated == null) return;
      setState(() {
        _position = position;
        if (_selected?.id == updated.id) _selected = updated;
      });
      if (updated.status == 'RESOLVED') _stopLiveSharing();
    } finally {
      _uploadingFix = false;
    }
  }

  void _cancelLocationStream() {
    _locationStream?.cancel();
    _locationStream = null;
  }

  void _stopLiveSharing() {
    _cancelLocationStream();
    if (mounted) {
      setState(() {
        _sharingSosId = null;
        _lastLocationUpload = null;
      });
    } else {
      _sharingSosId = null;
      _lastLocationUpload = null;
    }
  }

  void _back() {
    if (_app!.sos.sending) return;
    setState(() {
      _phase = SosPhase.idle;
      _formError = null;
    });
  }

  void _confirm() {
    setState(() {
      _phase = SosPhase.confirm;
      _formError = null;
    });
  }

  Future<void> _capture() async {
    setState(() {
      _locating = true;
      _formError = null;
    });
    try {
      final position = await captureSosLocation();
      if (!mounted) return;
      if (!_app!.location) {
        setState(
          () => _formError =
              'Location sharing was turned off. Enter your location manually.',
        );
        return;
      }
      setState(() {
        _position = position;
        _latitude.text = position.latitude.toStringAsFixed(6);
        _longitude.text = position.longitude.toStringAsFixed(6);
      });
    } catch (e) {
      if (mounted) {
        setState(
          () => _formError = e is AccountException
              ? e.message
              : 'Unable to capture location. Enter a description or coordinates manually.',
        );
      }
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  Future<void> _send() async {
    FocusManager.instance.primaryFocus?.unfocus();
    final sos = _app!.sos;
    if (!_app!.location && _position != null && sos.pending == null) {
      setState(() {
        _position = null;
        _latitude.clear();
        _longitude.clear();
        _formError =
            'Location sharing is off. Review your manual location before sending.';
      });
      return;
    }
    Map<String, dynamic> fields = {};
    if (sos.pending == null) {
      final lat = double.tryParse(_latitude.text.trim()),
          lon = double.tryParse(_longitude.text.trim());
      final hasCoordinates =
          _latitude.text.trim().isNotEmpty || _longitude.text.trim().isNotEmpty;
      if (_location.text.trim().length < 3) {
        setState(
          () => _formError = 'Enter your location or a nearby landmark.',
        );
        return;
      }
      if (hasCoordinates &&
          (lat == null ||
              lon == null ||
              !lat.isFinite ||
              !lon.isFinite ||
              lat.abs() > 90 ||
              lon.abs() > 180)) {
        setState(
          () => _formError =
              'Enter valid latitude and longitude together, or leave both empty.',
        );
        return;
      }
      fields = {
        'location': _location.text.trim(),
        'message': _message.text.trim(),
        'latitude': lat,
        'longitude': lon,
        'location_source': _position == null ? 'manual' : 'gps',
        'accuracy_m': _position?.accuracy,
        'location_recorded_at': _position?.timestamp.toUtc().toIso8601String(),
      };
    }
    setState(() => _formError = null);
    final saved = await sos.send(fields);
    if (!mounted) return;
    if (saved != null) {
      setState(() {
        _selected = saved;
        _phase = SosPhase.details;
      });
      if (_position != null && _shareLive && _app!.location) {
        _startLiveSharing(saved.id);
      }
      await sos.refresh();
    }
  }

  Widget _notice() => Panel(
    padding: 12,
    radius: 12,
    color: const Color(0x30eab308),
    border: const Color(0x60eab308),
    child: tx(
      'PRACTICE MODE · Requests are saved to AGAPAY. Emergency dispatch and external notifications are not connected.',
      size: 12,
      color: const Color(0xfffbbf24),
      height: 1.5,
    ),
  );
  Widget _error(String message) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 12),
    child: Semantics(
      liveRegion: true,
      child: tx(message, size: 12, color: const Color(0xfff87171), height: 1.5),
    ),
  );
  Color _statusColor(String value) => value == 'RESOLVED'
      ? AppColors.green
      : value == 'ACKNOWLEDGED'
      ? const Color(0xfffbbf24)
      : AppColors.red;

  Future<void> _openGoogleLocation(double latitude, double longitude) async {
    final uri = Uri.https('www.google.com', '/maps/search/', {
      'api': '1',
      'query': '$latitude,$longitude',
    });
    await launchUrl(uri, mode: LaunchMode.externalApplication);
  }

  Widget _history(SosController sos) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Row(
        children: [
          Expanded(child: caption('MY SOS HISTORY')),
          TextButton(
            onPressed: sos.loading || sos.sending ? null : () => sos.refresh(),
            child: const Text('Refresh'),
          ),
        ],
      ),
      tx(
        sos.syncedAt == null
            ? 'Waiting for the server…'
            : 'Last synced ${sosTime(sos.syncedAt!)} · Local time',
        size: 10,
        color: AppColors.muted,
      ),
      const SizedBox(height: 12),
      if (sos.items.isEmpty)
        tx(
          sos.loading
              ? 'Loading requests…'
              : sos.error != null
              ? 'History unavailable. Retry when connected.'
              : 'No saved practice requests yet.',
          size: 12,
          color: AppColors.secondary,
        ),
      for (final item in sos.items)
        Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: InkWell(
            onTap: () => setState(() {
              _selected = item;
              _phase = SosPhase.details;
            }),
            child: Panel(
              padding: 14,
              radius: 12,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                spacing: 6,
                children: [
                  Wrap(
                    spacing: 12,
                    runSpacing: 6,
                    children: [
                      tx(
                        'PRACTICE #${item.id}',
                        size: 12,
                        mono: true,
                        color: AppColors.secondary,
                      ),
                      tx(
                        item.status,
                        size: 11,
                        weight: 700,
                        color: _statusColor(item.status),
                      ),
                    ],
                  ),
                  tx(item.location, size: 13, weight: 600),
                  tx(sosTime(item.createdAt), size: 11, color: AppColors.muted),
                ],
              ),
            ),
          ),
        ),
      if (sos.items.length < sos.total)
        TextButton(
          onPressed: sos.loading ? null : () => sos.refresh(more: true),
          child: Text('Load more · ${sos.items.length} of ${sos.total}'),
        ),
    ],
  );

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    return ListenableBuilder(
      listenable: app.sos,
      builder: (context, _) {
        final sos = app.sos;
        if (_phase == SosPhase.details && _selected != null) {
          var item = _selected!;
          for (final saved in sos.items) {
            if (saved.id == item.id) item = saved;
          }
          return PageContent(
            children: [
              PageHeading('SOS Request', 'Practice #${item.id}', onBack: _back),
              _notice(),
              gap,
              Center(
                child: Container(
                  width: 80,
                  height: 80,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: _statusColor(item.status).withValues(alpha: .12),
                    border: Border.all(
                      color: _statusColor(item.status),
                      width: 2,
                    ),
                  ),
                  child: const Center(
                    child: SvgIcon('check', size: 40, color: AppColors.green),
                  ),
                ),
              ),
              gap,
              Center(
                child: tx(
                  item.status == 'ACTIVE' ? 'REQUEST RECEIVED' : item.status,
                  size: 24,
                  display: true,
                  weight: 800,
                  color: _statusColor(item.status),
                ),
              ),
              gap,
              tx(
                item.status == 'ACTIVE'
                    ? 'Saved by the server. Waiting for staff acknowledgement.'
                    : item.status == 'ACKNOWLEDGED'
                    ? 'A staff member has acknowledged your practice request.'
                    : 'Your practice request has been marked resolved.',
                align: TextAlign.center,
                color: AppColors.secondary,
              ),
              gap,
              Panel(
                child: Column(
                  spacing: 12,
                  children: [
                    DataRow('Reference', 'SOS-${item.id}', mono: true),
                    const Divider(height: 1),
                    DataRow('Received', sosTime(item.createdAt)),
                    const Divider(height: 1),
                    DataRow('Location', item.location),
                    const Divider(height: 1),
                    DataRow(
                      'Coordinates',
                      item.latitude == null
                          ? 'Not provided'
                          : '${item.latitude!.toStringAsFixed(6)}, ${item.longitude!.toStringAsFixed(6)}',
                      mono: true,
                    ),
                    if (item.locationRecordedAt != null) ...[
                      const Divider(height: 1),
                      DataRow(
                        'Last GPS update',
                        '${sosTime(item.locationRecordedAt!)} · ±${item.accuracyM?.round() ?? 0} m',
                      ),
                    ],
                    if (item.message.isNotEmpty) ...[
                      const Divider(height: 1),
                      DataRow('Message', item.message),
                    ],
                  ],
                ),
              ),
              if (item.latitude != null && item.longitude != null) ...[
                gap,
                ClipRRect(
                  borderRadius: BorderRadius.circular(14),
                  child: SizedBox(
                    height: 220,
                    child: AgapayGoogleMap(
                      center: AgapayMapCoordinate(
                        item.latitude!,
                        item.longitude!,
                      ),
                      zoom: 17,
                      tilt: 42,
                      markers: [
                        AgapayGoogleMapMarker(
                          id: 'sos-${item.id}',
                          title: 'SOS-${item.id} · ${item.location}',
                          position: AgapayMapCoordinate(
                            item.latitude!,
                            item.longitude!,
                          ),
                          color: const Color(0xffef4444),
                          glyph: '!',
                        ),
                      ],
                    ),
                  ),
                ),
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton.icon(
                    onPressed: () =>
                        _openGoogleLocation(item.latitude!, item.longitude!),
                    icon: const Icon(Icons.open_in_new, size: 16),
                    label: const Text('OPEN IN GOOGLE MAPS'),
                  ),
                ),
              ],
              if (_sharingSosId == item.id && item.status != 'RESOLVED') ...[
                gap,
                Panel(
                  color: const Color(0x3016a34a),
                  border: const Color(0x6016a34a),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      tx(
                        '● LIVE LOCATION SHARING',
                        size: 12,
                        weight: 700,
                        color: AppColors.green,
                      ),
                      const SizedBox(height: 4),
                      tx(
                        'Your latest device position is sent to AGAPAY while this app is open. Sharing stops when you stop it, close the app, or staff resolve the SOS.',
                        size: 11,
                        color: AppColors.secondary,
                        height: 1.5,
                      ),
                      const SizedBox(height: 8),
                      OutlinedButton(
                        onPressed: _stopLiveSharing,
                        child: const Text('STOP SHARING'),
                      ),
                    ],
                  ),
                ),
              ],
              gap,
              caption('REQUEST TIMELINE'),
              gap,
              Panel(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  spacing: 12,
                  children: [
                    tx(
                      'Received · ${sosTime(item.createdAt)}',
                      size: 12,
                      color: AppColors.secondary,
                    ),
                    if (item.acknowledgedAt != null)
                      tx(
                        'Acknowledged · ${item.acknowledgedBy} · ${sosTime(item.acknowledgedAt!)}',
                        size: 12,
                        color: const Color(0xfffbbf24),
                      ),
                    if (item.resolvedAt != null)
                      tx(
                        'Resolved · ${item.resolvedBy} · ${sosTime(item.resolvedAt!)}',
                        size: 12,
                        color: AppColors.green,
                      ),
                    if (item.resolutionNote?.isNotEmpty ?? false)
                      tx(
                        'Resolution: ${item.resolutionNote}',
                        size: 12,
                        color: AppColors.secondary,
                      ),
                  ],
                ),
              ),
              if (sos.error != null) _error(sos.error!),
              gap,
              tx(
                sos.syncedAt == null
                    ? 'Status has not refreshed yet.'
                    : 'Last synced ${sosTime(sos.syncedAt!)} · Local time',
                size: 10,
                color: AppColors.muted,
              ),
              gap,
              ActionButton('BACK TO SOS HISTORY', onPressed: _back),
            ],
          );
        }
        if (_phase == SosPhase.confirm) {
          final pending = sos.pending;
          final locked = pending != null || sos.sending;
          return PageContent(
            children: [
              PageHeading(
                'Confirm SOS',
                'Practice request · Review before sending',
                subtitleColor: const Color(0xfff87171),
                onBack: _back,
              ),
              _notice(),
              gap,
              if (pending != null) ...[
                if (!sos.sending)
                  _error(
                    'A previous send has not been confirmed. Retry with its saved details and reference to avoid duplicates.',
                  ),
                Panel(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    spacing: 8,
                    children: [
                      tx(pending['location'] as String, weight: 600),
                      tx(
                        pending['message'] as String? ?? '',
                        size: 12,
                        color: AppColors.secondary,
                      ),
                      tx(
                        'Reference: ${pending['request_id']}',
                        size: 10,
                        mono: true,
                        color: AppColors.muted,
                      ),
                    ],
                  ),
                ),
              ] else ...[
                caption('YOUR LOCATION / NEARBY LANDMARK'),
                const SizedBox(height: 8),
                TextField(
                  key: const ValueKey('sos-location'),
                  controller: _location,
                  enabled: !locked,
                  maxLength: 300,
                  maxLines: 2,
                  decoration: const InputDecoration(
                    hintText:
                        'Street, house number or nearby landmark, barangay',
                  ),
                ),
                const SizedBox(height: 8),
                ActionButton(
                  _locating ? 'GETTING LOCATION…' : 'USE MY DEVICE LOCATION',
                  color: AppColors.surface,
                  border: AppColors.border,
                  textColor: AppColors.link,
                  onPressed: locked || _locating || !app.location
                      ? null
                      : _capture,
                ),
                const SizedBox(height: 8),
                tx(
                  !app.location
                      ? 'Location sharing is off in your profile. You can enter a location manually.'
                      : 'Optional. Location is requested only when you tap above and included only after you confirm sending.',
                  size: 11,
                  color: AppColors.muted,
                ),
                gap,
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  spacing: 12,
                  children: [
                    Expanded(
                      child: TextField(
                        key: const ValueKey('sos-latitude'),
                        controller: _latitude,
                        enabled: !locked && !_locating,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                          signed: true,
                        ),
                        onChanged: (_) => setState(() => _position = null),
                        decoration: const InputDecoration(
                          labelText: 'Latitude (optional)',
                        ),
                      ),
                    ),
                    Expanded(
                      child: TextField(
                        key: const ValueKey('sos-longitude'),
                        controller: _longitude,
                        enabled: !locked && !_locating,
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                          signed: true,
                        ),
                        onChanged: (_) => setState(() => _position = null),
                        decoration: const InputDecoration(
                          labelText: 'Longitude (optional)',
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                tx(
                  _position == null
                      ? 'Manual location · No GPS accuracy claimed'
                      : 'Device location · ±${_position!.accuracy.round()} m · Captured ${sosTime(_position!.timestamp)}',
                  size: 11,
                  color: AppColors.muted,
                ),
                if (_position != null && app.location) ...[
                  const SizedBox(height: 8),
                  SwitchListTile.adaptive(
                    contentPadding: EdgeInsets.zero,
                    value: _shareLive,
                    onChanged: locked
                        ? null
                        : (value) => setState(() => _shareLive = value),
                    title: tx(
                      'Share live location while SOS is open',
                      size: 13,
                      weight: 600,
                    ),
                    subtitle: tx(
                      'After you send, AGAPAY receives a new device fix when you move. Sharing runs only while the app is open and stops when the request is resolved.',
                      size: 10,
                      color: AppColors.muted,
                      height: 1.45,
                    ),
                  ),
                ],
                gap,
                caption('SITUATION (OPTIONAL)'),
                const SizedBox(height: 8),
                TextField(
                  key: const ValueKey('sos-message'),
                  controller: _message,
                  enabled: !locked,
                  maxLength: 1000,
                  maxLines: 3,
                  decoration: const InputDecoration(
                    hintText: 'Describe your practice scenario',
                  ),
                ),
              ],
              if (_formError != null) _error(_formError!),
              if (sos.error != null) _error(sos.error!),
              gap,
              ActionButton(
                sos.sending
                    ? 'SENDING…'
                    : pending == null
                    ? 'SEND PRACTICE SOS'
                    : 'RETRY SAME REQUEST',
                fontSize: 18,
                weight: 800,
                color: AppColors.red,
                glow: true,
                onPressed: sos.sending || !sos.ready || _locating
                    ? null
                    : _send,
              ),
              gap,
              ActionButton(
                pending == null ? 'CANCEL' : 'BACK TO HISTORY',
                color: AppColors.surface,
                border: AppColors.border,
                textColor: AppColors.secondary,
                onPressed: sos.sending ? null : _back,
              ),
              gap,
              tx(
                'Success appears only after the server accepts the request. Live sharing, when selected, runs only in the foreground.',
                size: 11,
                color: AppColors.muted,
                align: TextAlign.center,
              ),
            ],
          );
        }
        return PageContent(
          children: [
            PageHeading(
              'Emergency SOS',
              'Practice requests · Development mode',
              onBack: () => app.navigate(AppTab.home),
            ),
            _notice(),
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 32, 8, 0),
              child: Column(
                spacing: 24,
                children: [
                  SizedBox(
                    width: 176,
                    height: 176,
                    child: Stack(
                      clipBehavior: Clip.none,
                      alignment: Alignment.center,
                      children: [
                        for (final delay in [0.0, .333])
                          AnimatedBuilder(
                            animation: _pulse,
                            builder: (context, child) {
                              final t = (_pulse.value + delay) % 1;
                              return IgnorePointer(
                                child: Transform.scale(
                                  scale: 1 + 1.4 * t,
                                  child: Opacity(
                                    opacity: .8 * (1 - t),
                                    child: Container(
                                      width: 176,
                                      height: 176,
                                      decoration: BoxDecoration(
                                        shape: BoxShape.circle,
                                        border: Border.all(
                                          color: AppColors.red,
                                          width: delay == 0 ? 2 : 1,
                                        ),
                                      ),
                                    ),
                                  ),
                                ),
                              );
                            },
                          ),
                        Semantics(
                          label: 'Start practice SOS',
                          button: true,
                          child: InkWell(
                            customBorder: const CircleBorder(),
                            onTap: sos.ready && !sos.sending ? _confirm : null,
                            child: Container(
                              width: 176,
                              height: 176,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                gradient: const RadialGradient(
                                  colors: [
                                    Color(0xffb91c1c),
                                    Color(0xff7f1d1d),
                                  ],
                                ),
                                border: Border.all(
                                  color: const Color(0x80dc2626),
                                  width: 3,
                                ),
                                boxShadow: const [
                                  BoxShadow(
                                    color: Color(0x60dc2626),
                                    blurRadius: 48,
                                  ),
                                ],
                              ),
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                spacing: 8,
                                children: [
                                  const SvgIcon(
                                    'sos',
                                    size: 40,
                                    color: Colors.white,
                                  ),
                                  tx(
                                    'SOS',
                                    size: 30,
                                    display: true,
                                    weight: 900,
                                    color: Colors.white,
                                    spacing: 1.5,
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  Column(
                    children: [
                      tx(
                        'Practice an SOS request',
                        size: 20,
                        display: true,
                        weight: 700,
                        color: Colors.white,
                      ),
                      const SizedBox(height: 8),
                      tx(
                        'Review your location and message, then send a practice request to the AGAPAY command center.',
                        color: AppColors.secondary,
                        height: 1.625,
                        align: TextAlign.center,
                      ),
                    ],
                  ),
                  if (sos.pending != null)
                    Panel(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        spacing: 12,
                        children: [
                          tx(
                            'RECEIPT UNCONFIRMED',
                            color: const Color(0xfffbbf24),
                            weight: 700,
                          ),
                          tx(
                            'Your request reference is saved. Check history or retry the same request.',
                            size: 12,
                            color: AppColors.secondary,
                          ),
                          ActionButton(
                            'REVIEW SAVED REQUEST',
                            onPressed: _confirm,
                          ),
                        ],
                      ),
                    ),
                  if (sos.error != null) _error(sos.error!),
                  _info(
                    Icons.location_on_outlined,
                    'Location Sharing',
                    'Choose device location or enter a description manually. Live sharing is opt-in and foreground only.',
                  ),
                  _info(
                    Icons.assignment_outlined,
                    'SOS Record',
                    'Saved requests show staff acknowledgement, resolution and timestamps.',
                  ),
                  _history(sos),
                ],
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _info(IconData icon, String title, String description) => Panel(
    padding: 14,
    radius: 14,
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 12,
      children: [
        Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            color: AppColors.blue.withValues(alpha: .16),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: AppColors.link.withValues(alpha: .35)),
          ),
          child: Icon(icon, size: 19, color: AppColors.link),
        ),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              tx(title, display: true, weight: 600, color: Colors.white),
              const SizedBox(height: 2),
              tx(
                description,
                size: 11,
                color: AppColors.secondary,
                height: 1.625,
              ),
            ],
          ),
        ),
      ],
    ),
  );
}
