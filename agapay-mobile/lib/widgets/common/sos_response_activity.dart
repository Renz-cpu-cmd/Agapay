import 'dart:async';
import '../../core/ui.dart';
import '../../models/sos_request.dart';

/// Resident-only read model: stages come from recorded drill actions.
class SosResponseActivity extends StatefulWidget {
  const SosResponseActivity({super.key, required this.sosId});
  final int sosId;
  @override
  State<SosResponseActivity> createState() => _SosResponseActivityState();
}

class _SosResponseActivityState extends State<SosResponseActivity>
    with WidgetsBindingObserver {
  Map<String, dynamic>? _data;
  String? _error;
  int? _owner;
  int _generation = 0;
  bool _loading = false;
  DateTime? _checkedAt;
  int? _before;
  bool _foreground = true, _needsCheck = true;
  AppController? _app;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _foreground =
        WidgetsBinding.instance.lifecycleState == null ||
        WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed;
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _foreground = state == AppLifecycleState.resumed;
    ++_generation;
    _loading = false;
    if (mounted) setState(() => _needsCheck = true);
    if (_foreground && _owner != null) unawaited(_load());
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _app = AppScope.of(context);
    if (_owner != _app?.user?.id) {
      _owner = _app?.user?.id;
      _generation++;
      _data = null;
      _checkedAt = null;
      _needsCheck = true;
      _before = null;
      _error = null;
      _loading = false;
      if (_owner != null) unawaited(_load());
    }
    _timer ??= Timer.periodic(const Duration(seconds: 5), (_) {
      if (mounted && _foreground && _owner != null && _app?.tab == AppTab.sos) {
        unawaited(_load());
      }
    });
  }

  Future<void> _load() async {
    if (_loading || _owner == null || !_foreground) return;
    final generation = _generation;
    _loading = true;
    try {
      final value = await _app!.auth.request(
        'sos-response/${widget.sosId}${_before == null ? '' : '?before_event_id=$_before'}',
      );
      if (!mounted || generation != _generation) return;
      if (value is! Map ||
          value['mode'] != 'drill' ||
          value['operational_enabled'] != false ||
          value['events'] is! List) {
        throw const FormatException('Unconfirmed response workflow');
      }
      setState(() {
        _data = value.cast<String, dynamic>();
        _error = null;
        _checkedAt = DateTime.now();
        _needsCheck = false;
      });
    } catch (_) {
      if (mounted && generation == _generation) {
        setState(
          () => _error =
              'Response activity unavailable. Any displayed records may be out of date.',
        );
      }
    } finally {
      if (generation == _generation) _loading = false;
    }
  }

  void _page(int? cursor) {
    if (_loading) return;
    _before = cursor;
    unawaited(_load());
  }

  @override
  void didUpdateWidget(SosResponseActivity oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.sosId != widget.sosId) {
      ++_generation;
      _data = null;
      _checkedAt = null;
      _before = null;
      _error = null;
      _loading = false;
      unawaited(_load());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _generation++;
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_owner == null) return const SizedBox.shrink();
    final events = (_data?['events'] as List?) ?? [];
    return Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          tx('Recorded response drill', size: 16, weight: 700),
          gap,
          tx(
            'Exercise only. Acknowledgement confirms review, not that a responder was sent.',
            size: 12,
          ),
          if (_data != null) ...[
            gap,
            Text(
              _needsCheck ||
                      _error != null ||
                      _checkedAt == null ||
                      DateTime.now().difference(_checkedAt!) >
                          const Duration(seconds: 30)
                  ? 'LAST KNOWN OWNERSHIP · current responsibility unconfirmed'
                  : 'Response activity checked ${sosTime(_checkedAt!)}',
            ),
            if (_data!['coordinator_name'] == null)
              const Text(
                'Request owner: no coordinator is recorded. Staff acknowledgement alone is not an assignment.',
              ),
            tx(
              _data!['started'] == true
                  ? 'Recorded stage: ${_data!['phase']}'
                  : 'No response drill has been started.',
              weight: 700,
            ),
            if (_data!['coordinator_name'] != null)
              tx('Coordinator: ${_data!['coordinator_name']}', size: 12),
            if (_data!['responder_name'] != null)
              tx('Drill responder: ${_data!['responder_name']}', size: 12),
            if (_data!['attention'] == 'needs_review')
              tx(
                'Drill escalation needs coordinator review.',
                color: context.colors.red,
                size: 12,
              ),
            if (_data!['incident_reference'] != null)
              tx(
                'Incident ${_data!['incident_reference']} · your request remains separate.',
                size: 12,
              ),
            if (_data!['closure_reason'] != null)
              tx('Closure: ${_data!['closure_reason']}', size: 12),
            for (final e in events)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: tx(
                  '${sosTime(DateTime.parse(e['created_at'] as String))} · ${e['message']}',
                  size: 12,
                ),
              ),
            if (_before != null)
              TextButton(
                onPressed: _loading
                    ? null
                    : () {
                        _page(null);
                      },
                child: const Text('Latest recorded actions'),
              ),
            if (_data!['has_more_events'] == true &&
                _data!['next_before_event_id'] is int)
              TextButton(
                onPressed: _loading
                    ? null
                    : () {
                        _page(_data!['next_before_event_id'] as int);
                      },
                child: const Text('Earlier recorded actions'),
              ),
          ],
          if (_data == null)
            const Text(
              'Request owner and assignment are unconfirmed until recorded response activity is available.',
            ),
          if (_error != null) tx(_error!, color: context.colors.red, size: 12),
          TextButton(
            onPressed: () => unawaited(_load()),
            child: const Text('Refresh recorded response'),
          ),
        ],
      ),
    );
  }
}
