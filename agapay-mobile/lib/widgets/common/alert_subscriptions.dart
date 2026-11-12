import 'dart:async';
import '../../core/ui.dart';

class AlertSubscriptionsPanel extends StatefulWidget {
  const AlertSubscriptionsPanel({super.key});
  @override
  State<AlertSubscriptionsPanel> createState() =>
      _AlertSubscriptionsPanelState();
}

class _AlertSubscriptionsPanelState extends State<AlertSubscriptionsPanel> {
  AppController? _app;
  int? _owner;
  int _generation = 0;
  Map<String, dynamic>? _data;
  bool _busy = false;
  String? _error;
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final app = AppScope.of(context);
    if (_app == app && _owner == app.user?.id) return;
    _app = app;
    _owner = app.user?.id;
    ++_generation;
    _data = null;
    _busy = false;
    _error = null;
    if (_owner != null) unawaited(_refresh());
  }

  Future<void> _refresh() async {
    final generation = ++_generation;
    _busy = true;
    try {
      final result =
          await _app!.auth.request('alert-subscriptions')
              as Map<String, dynamic>;
      if (mounted && generation == _generation) {
        setState(() {
          _data = result;
          _error = null;
        });
      }
    } catch (_) {
      if (mounted && generation == _generation) {
        setState(() {
          _data = null;
          _error =
              'Subscription service unavailable. Refresh to review your choices.';
        });
      }
    } finally {
      if (mounted && generation == _generation) setState(() => _busy = false);
    }
  }

  Future<void> _change(
    String kind,
    String id,
    bool enabled,
    int revision,
  ) async {
    final generation = _generation;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await _app!.auth.request(
        'alert-subscriptions',
        method: 'POST',
        body: {
          'kind': kind,
          'target_id': id,
          'enabled': enabled,
          'expected_revision': revision,
        },
      );
      if (mounted && generation == _generation) await _refresh();
    } catch (_) {
      if (mounted && generation == _generation) {
        setState(() {
          _error =
              'Change was not confirmed. Refresh and manually review before trying again.';
          _data = null;
        });
      }
    } finally {
      if (mounted && generation == _generation) setState(() => _busy = false);
    }
  }

  @override
  void dispose() {
    ++_generation;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final subscriptions = (_data?['subscriptions'] as List?) ?? [];
    final choices = [
      for (final station in (_data?['stations'] as List?) ?? [])
        (
          'station',
          station['station_id'] as String,
          station['station_name'] as String,
        ),
      for (final area in (_data?['areas'] as List?) ?? [])
        ('area', area['id'] as String, area['name'] as String),
    ];
    return Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          caption('PUSH ALERT SUBSCRIPTIONS'),
          tx(
            'Choose stations or verified areas. Your profile barangay and map selection do not enroll you. Authorized citywide overrides are separate.',
            size: 11,
            color: context.colors.muted,
          ),
          if (_error != null) tx(_error!, size: 11),
          if (!_busy && _data != null && choices.isEmpty)
            tx('No subscription targets are configured.', size: 11),
          ExpansionTile(
            // Own PageStorage identity: unkeyed, it shares the enclosing
            // "Alert subscriptions" panel's slot and opens whenever that panel opens.
            key: const PageStorageKey('alert-subscription-targets'),
            title: const Text('Choose stations and areas'),
            children: [
              for (final (kind, id, name) in choices)
                Builder(
                  builder: (context) {
                    final matching = subscriptions.where(
                      (row) => row['kind'] == kind && row['target_id'] == id,
                    );
                    final current = matching.isEmpty
                        ? null
                        : matching.first as Map;
                    return CheckboxListTile(
                      title: Text(name),
                      subtitle: Text('$kind · $id'),
                      value: current?['enabled'] == true,
                      onChanged: _busy
                          ? null
                          : (value) => unawaited(
                              _change(
                                kind,
                                id,
                                value == true,
                                current?['revision'] as int? ?? 0,
                              ),
                            ),
                    );
                  },
                ),
            ],
          ),
          TextButton(
            onPressed: _busy ? null : _refresh,
            child: Text(
              _busy ? 'Checking subscriptions…' : 'Refresh subscriptions',
            ),
          ),
        ],
      ),
    );
  }
}
