import 'dart:async';
import 'package:geolocator/geolocator.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../core/ui.dart';
import '../../controllers/sos_controller.dart';
import '../../models/sos_request.dart';
import '../../services/auth_api.dart';
import '../../services/sos_location.dart';
import '../../widgets/maps/agapay_google_map.dart';
import '../../widgets/common/sos_response_activity.dart';
import '../../widgets/common/sos_outbox.dart';
import '../../widgets/common/sos_receipt.dart';
import '../../widgets/common/resident_decisions.dart';

enum SosPhase { idle, confirm, details }

class SosScreen extends StatefulWidget {
  const SosScreen({this.captureLocation = captureSosLocation, super.key});
  final Future<Position> Function() captureLocation;
  @override
  State<SosScreen> createState() => _SosScreenState();
}

class _SosScreenState extends State<SosScreen> with WidgetsBindingObserver {
  SosPhase _phase = SosPhase.idle;
  final _message = TextEditingController();
  final _location = TextEditingController();
  final _latitude = TextEditingController();
  final _longitude = TextEditingController();
  Position? _position;
  bool _locating = false;
  String? _formError;
  SosRequest? _selected;
  int? _privateMapFor;
  AppController? _app;
  Timer? _timer;
  bool _foreground = true;
  bool _shareLive = false;
  int? _owner;
  int _formGeneration = 0;
  bool _uploadingFix = false;
  int? _sharingSosId;
  DateTime? _lastLocationUpload;
  StreamSubscription<Position>? _locationStream;
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
    final next = AppScope.of(context);
    if (_owner != next.user?.id) {
      _owner = next.user?.id;
      ++_formGeneration;
      _cancelLocationStream();
      _sharingSosId = null;
      _lastLocationUpload = null;
      _selected = null;
      _privateMapFor = null;
      _position = null;
      _phase = SosPhase.idle;
      _formError = null;
      _shareLive = false;
      _locating = false;
      _message.clear();
      _location.clear();
      _latitude.clear();
      _longitude.clear();
    }
    _app = next;
    _syncSharingState();
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
    super.dispose();
  }

  void _syncSharingState() {
    final id = _sharingSosId;
    if (id == null) return;
    if (_app?.sos.locationConflicts.contains(id) == true) {
      _stopLiveSharing();
      return;
    }
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
            _cancelLocationStream();
            _sharingSosId = null;
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
    if (id == null || _uploadingFix || !_foreground || _app?.location != true) {
      return;
    }
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
      if (!mounted) return;
      if (updated == null) {
        _syncSharingState();
        return;
      }
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
    ++_formGeneration;
    setState(() {
      _phase = SosPhase.idle;
      _privateMapFor = null;
      _formError = null;
      _locating = false;
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
    final generation = _formGeneration;
    try {
      final position = await widget.captureLocation();
      if (!mounted || generation != _formGeneration) return;
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
      if (mounted && generation == _formGeneration) {
        setState(
          () => _formError = e is AccountException
              ? e.message
              : 'Unable to capture location. Enter a description or coordinates manually.',
        );
      }
    } finally {
      if (mounted && generation == _formGeneration) {
        setState(() => _locating = false);
      }
    }
  }

  Future<void> _resumeSharing(SosRequest item) async {
    if (_locating ||
        !_foreground ||
        _app?.location != true ||
        _app!.sos.locationConflicts.contains(item.id)) {
      return;
    }
    final owner = _app!.user?.id;
    final generation = _formGeneration;
    setState(() {
      _locating = true;
      _formError = null;
    });
    try {
      final position = await widget.captureLocation();
      if (!mounted ||
          !_foreground ||
          generation != _formGeneration ||
          _app?.user?.id != owner ||
          _app?.location != true) {
        return;
      }
      final updated = await _app!.sos.updateLocation(
        item.id,
        latitude: position.latitude,
        longitude: position.longitude,
        accuracyM: position.accuracy,
        recordedAt: position.timestamp,
      );
      if (!mounted || generation != _formGeneration) return;
      if (updated == null) {
        setState(
          () => _formError =
              _app!.sos.error ??
              'Location was not confirmed. Refresh and review.',
        );
        return;
      }
      if (updated.status == 'RESOLVED') {
        return;
      }
      setState(() {
        _selected = updated;
        _position = position;
      });
      _startLiveSharing(updated.id);
    } catch (error) {
      if (mounted && generation == _formGeneration) {
        setState(() => _formError = error.toString());
      }
    } finally {
      if (mounted && generation == _formGeneration) {
        setState(() => _locating = false);
      }
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
    final generation = _formGeneration;
    final saved = await sos.send(fields);
    if (!mounted || generation != _formGeneration) return;
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
      'TEST ENVIRONMENT · Requests are saved to AGAPAY. Emergency dispatch and external notifications are not connected.',
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
      ? context.colors.green
      : value == 'ACKNOWLEDGED'
      ? const Color(0xfffbbf24)
      : context.colors.red;

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
        color: context.colors.muted,
      ),
      const SizedBox(height: 12),
      if (sos.items.isEmpty)
        tx(
          sos.loading
              ? 'Loading requests…'
              : sos.error != null
              ? 'History unavailable. Retry when connected.'
              : 'No saved test requests yet.',
          size: 12,
          color: context.colors.secondary,
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
                        'TEST REQUEST #${item.id}',
                        size: 12,
                        mono: true,
                        color: context.colors.secondary,
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
                  tx(
                    sosTime(item.createdAt),
                    size: 11,
                    color: context.colors.muted,
                  ),
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
              PageHeading(
                'SOS Request',
                'Test request #${item.id}',
                onBack: _back,
              ),
              _notice(),
              gap,
              SosReceiptCard(item: item),
              gap,
              SosResponseActivity(key: ValueKey(item.id), sosId: item.id),
              gap,
              if (sos.pending != null) const SosOutboxPanel(),
              if (sos.locationConflicts.contains(item.id))
                TextButton(
                  onPressed: () => unawaited(sos.refresh(manual: true)),
                  child: const Text('Refresh and review location sharing'),
                ),
              gap,
              Panel(
                child: Column(
                  spacing: 12,
                  children: [
                    SelectableText('Request reference: ${item.requestId}'),
                    DataRow('Server record', 'SOS-${item.id}', mono: true),
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
                        'Location capture',
                        '${sosTime(item.locationRecordedAt!)} · ${sosLocationAge(item.locationRecordedAt)} · ${item.accuracyM == null ? 'Accuracy unknown' : '±${item.accuracyM!.round()} m'}',
                      ),
                    ],
                    DataRow('Location source', item.locationSource),
                    DataRow(
                      'Sharing consent',
                      _sharingSosId == item.id
                          ? 'Foreground updates enabled by you'
                          : 'Live updates off; request location retained',
                    ),
                    if (item.message.isNotEmpty) ...[
                      const Divider(height: 1),
                      DataRow('Message', item.message),
                    ],
                  ],
                ),
              ),
              if (item.latitude != null && item.longitude != null) ...[
                gap,
                TextButton(
                  onPressed: () => setState(
                    () => _privateMapFor = _privateMapFor == item.id
                        ? null
                        : item.id,
                  ),
                  child: Text(
                    _privateMapFor == item.id
                        ? 'HIDE LOCATION MAP'
                        : 'LOAD MAP — shares coordinates with Google Maps',
                  ),
                ),
                const Text(
                  'Opening this map shares the displayed coordinates with the configured map provider. Text location and contacts remain available without it.',
                ),
                if (_privateMapFor == item.id)
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
                            title: 'SOS location',
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
              if (_sharingSosId != item.id &&
                  item.status != 'RESOLVED' &&
                  app.location &&
                  !sos.locationConflicts.contains(item.id)) ...[
                gap,
                TextButton(
                  onPressed: _locating || !_foreground
                      ? null
                      : () => unawaited(_resumeSharing(item)),
                  child: const Text('Resume foreground sharing'),
                ),
              ],
              if (_formError != null)
                tx(_formError!, color: context.colors.red, size: 12),
              if (_sharingSosId == item.id && item.status != 'RESOLVED') ...[
                gap,
                Panel(
                  color: const Color(0x3016a34a),
                  border: const Color(0x6016a34a),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      tx(
                        'FOREGROUND SHARING ENABLED',
                        size: 12,
                        weight: 700,
                        color: context.colors.green,
                      ),
                      const SizedBox(height: 4),
                      tx(
                        'Updates are attempted while the app is open. Check the recorded fix time to confirm what reached AGAPAY. Sharing stops when you stop it, close the app, or staff resolve the SOS.',
                        size: 11,
                        color: context.colors.secondary,
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
                      color: context.colors.secondary,
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
                        color: context.colors.green,
                      ),
                    if (item.resolutionNote?.isNotEmpty ?? false)
                      tx(
                        'Resolution: ${item.resolutionNote}',
                        size: 12,
                        color: context.colors.secondary,
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
                color: context.colors.muted,
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
                'Test request · Review before sending',
                subtitleColor: const Color(0xfff87171),
                onBack: _back,
              ),
              _notice(),
              if (sos.pending != null) const SosOutboxPanel(),
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
                        color: context.colors.secondary,
                      ),
                      tx(
                        'Reference: ${pending['request_id']}',
                        size: 10,
                        mono: true,
                        color: context.colors.muted,
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
                  color: context.colors.surface,
                  border: context.colors.border,
                  textColor: context.colors.link,
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
                  color: context.colors.muted,
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
                      : 'Device location · ±${_position!.accuracy.round()} m · ${sosLocationAge(_position!.timestamp)} · Captured ${sosTime(_position!.timestamp)}',
                  size: 11,
                  color: context.colors.muted,
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
                      color: context.colors.muted,
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
                    hintText: 'Describe your request details',
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
                    ? (app.auth.offlineReader
                          ? 'SAVE SOS TO OUTBOX'
                          : 'SEND SOS')
                    : 'RETRY SAME REQUEST',
                fontSize: 18,
                weight: 800,
                color: context.colors.red,
                glow: true,
                onPressed:
                    sos.sending ||
                        !sos.ready ||
                        _locating ||
                        ['conflict', 'rejected'].contains(sos.pendingState)
                    ? null
                    : _send,
              ),
              gap,
              ActionButton(
                pending == null ? 'CANCEL' : 'BACK TO HISTORY',
                color: context.colors.surface,
                border: context.colors.border,
                textColor: context.colors.secondary,
                onPressed: sos.sending ? null : _back,
              ),
              gap,
              tx(
                'Success appears only after the server accepts the request. Live sharing, when selected, runs only in the foreground.',
                size: 11,
                color: context.colors.muted,
                align: TextAlign.center,
              ),
            ],
          );
        }
        final received = sos.lastSent ?? sos.items.firstOrNull;
        return PageContent(
          children: [
            PageHeading(
              'SOS requests',
              'Test environment · receipt and response evidence',
            ),
            _notice(),
            gap,
            if (sos.pending != null) const SosOutboxPanel(),
            if (sos.pending == null && received != null) ...[
              SosReceiptCard(
                item: received,
                onOpen: () => setState(() {
                  _selected = received;
                  _phase = SosPhase.details;
                }),
              ),
              gap,
            ],
            gap,
            Center(
              child: SosStartAction(
                label: sos.pending == null
                    ? (received == null ? 'START SOS' : 'START ANOTHER SOS')
                    : 'REVIEW SAVED REQUEST',
                onPressed: sos.ready && !sos.sending ? _confirm : null,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Review your location and consent before sending. An unconfirmed send keeps its original reference; do not create a duplicate.',
              textAlign: TextAlign.center,
            ),
            if (sos.error != null) _error(sos.error!),
            gap,
            _sosInfo(
              Icons.location_on_outlined,
              'Location sharing',
              'Choose whether to share your location. Its capture time and accuracy stay visible before you send.',
            ),
            gap,
            _sosInfo(
              Icons.fact_check_outlined,
              'Receipt and response',
              '${sos.loading
                  ? 'Checking saved requests…'
                  : sos.error != null
                  ? 'Receipt history is unavailable. No new receipt is confirmed.'
                  : received == null
                  ? 'No received test request is recorded here.'
                  : 'Open your latest receipt above for recorded actions.'} A server receipt, staff review and an assigned responder are different recorded steps.',
            ),
            gap,
            _sosInfo(
              Icons.history,
              'SOS record',
              'Keep your request reference. Review its history below and check saved requests before trying another send.',
            ),
            gap,
            const ExpansionTile(
              key: PageStorageKey('sos-help'),
              title: Text('Verified contacts and help'),
              children: [ResidentHelpPanel()],
            ),
            gap,
            _history(sos),
          ],
        );
      },
    );
  }

  Widget _sosInfo(IconData icon, String title, String description) => Panel(
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: context.colors.link, size: 24),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              tx(title, size: 14, weight: 600),
              const SizedBox(height: 4),
              tx(description, size: 12, color: context.colors.secondary),
            ],
          ),
        ),
      ],
    ),
  );
}

/// The original circular action opens consent/review; it never submits a request.
class SosStartAction extends StatelessWidget {
  const SosStartAction({
    required this.label,
    required this.onPressed,
    super.key,
  });
  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final scale = MediaQuery.textScalerOf(context).scale(1).clamp(1.0, 1.4);
      final diameter = (184 * scale).clamp(0.0, constraints.maxWidth);
      return SizedBox(
        width: diameter,
        height: diameter,
        child: Semantics(
          label: label == 'START SOS' ? 'Start SOS' : label,
          button: true,
          enabled: onPressed != null,
          onTap: onPressed,
          excludeSemantics: true,
          child: FilledButton(
            onPressed: onPressed,
            style: FilledButton.styleFrom(
              shape: const CircleBorder(),
              backgroundColor: const Color(0xffc92535),
              foregroundColor: Colors.white,
              disabledBackgroundColor: context.colors.border,
              disabledForegroundColor: context.colors.muted,
              padding: const EdgeInsets.all(24),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.warning_amber_rounded, size: 48),
                const SizedBox(height: 8),
                Text(
                  label,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
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
