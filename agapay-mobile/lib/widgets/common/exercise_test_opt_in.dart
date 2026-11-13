import '../../core/ui.dart';
import '../../services/auth_api.dart';
import '../../services/push_messaging.dart';

/// Device-specific consent for EXERCISE_TEST drill messages. Separate from
/// operational alert preferences; off unless the server confirms an opt-in
/// for this exact device registration.
abstract interface class ExerciseConsentClient {
  Future<bool> read(String deviceId);
  Future<bool> write(String deviceId, bool optedIn);
}

class ApiExerciseConsentClient implements ExerciseConsentClient {
  const ApiExerciseConsentClient(this.api);
  final AuthApi api;
  String _path(String id) =>
      'exercise-notifications/consent/${Uri.encodeComponent(id)}';

  @override
  Future<bool> read(String deviceId) async {
    final data = await api.request(_path(deviceId));
    return data is Map && data['opted_in'] == true;
  }

  @override
  Future<bool> write(String deviceId, bool optedIn) async {
    final data = await api.request(
      _path(deviceId),
      method: optedIn ? 'PUT' : 'DELETE',
    );
    return data is Map && data['opted_in'] == true;
  }
}

class ExerciseTestOptIn extends StatefulWidget {
  const ExerciseTestOptIn({
    required this.deviceId,
    required this.client,
    super.key,
  });
  final String? deviceId;
  final ExerciseConsentClient client;

  static const explanation =
      'Testing only. When on, an AGAPAY administrator may send clearly labelled '
      '"$exerciseAlertTitle" messages to this device during a scheduled exercise. '
      'It does not change your flood alert settings, and you can turn it off at any time.';

  @override
  State<ExerciseTestOptIn> createState() => _ExerciseTestOptInState();
}

class _ExerciseTestOptInState extends State<ExerciseTestOptIn> {
  bool _optedIn = false, _busy = false;
  String? _message;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final id = widget.deviceId;
    if (id == null) return;
    setState(() => _busy = true);
    try {
      final value = await widget.client.read(id);
      if (mounted) setState(() => _optedIn = value);
    } on AccountException catch (error) {
      if (mounted) setState(() => _message = _explain(error));
    } catch (_) {
      if (mounted) {
        setState(() => _message = 'Exercise test status is unavailable.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _explain(AccountException error) => error.status == 403
      ? 'Exercise testing is not enabled on this server.'
      : 'Exercise test status is unavailable.';

  Future<void> _change(bool value) async {
    final id = widget.deviceId;
    if (id == null || _busy) return;
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      final confirmed = await widget.client.write(id, value);
      if (mounted) setState(() => _optedIn = confirmed);
    } on AccountException catch (error) {
      if (mounted) setState(() => _message = _explain(error));
    } catch (_) {
      if (mounted) {
        setState(() => _message = 'Could not update. Try again.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Panel(
    key: const ValueKey('exercise-test-opt-in'),
    border: context.colors.link,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Semantics(
          header: true,
          child: tx('Exercise test notifications', size: 16, weight: 700),
        ),
        const SizedBox(height: 6),
        tx(
          ExerciseTestOptIn.explanation,
          size: 12,
          color: context.colors.secondary,
        ),
        const SizedBox(height: 8),
        if (widget.deviceId == null)
          tx(
            'Turn on push notifications for this device first.',
            size: 12,
            color: context.colors.muted,
          )
        else
          SwitchListTile(
            key: const ValueKey('exercise-test-opt-in-switch'),
            contentPadding: EdgeInsets.zero,
            title: const Text('Receive exercise test alerts on this device'),
            subtitle: Text(_optedIn ? 'On · testing only' : 'Off'),
            value: _optedIn,
            onChanged: _busy || _message != null && _message!.contains('not enabled')
                ? null
                : _change,
          ),
        if (_message != null)
          tx(_message!, size: 12, color: context.colors.muted),
      ],
    ),
  );
}
