import '../../core/ui.dart';
import '../../navigation/app_routes.dart';
import '../auth/recovery_screen.dart';

class AccountSecurityScreen extends StatefulWidget {
  const AccountSecurityScreen({super.key});
  @override
  State<AccountSecurityScreen> createState() => _AccountSecurityScreenState();
}

class _AccountSecurityScreenState extends State<AccountSecurityScreen> {
  bool _queried = false, _busy = false;
  Map<String, dynamic>? _data;
  String? _error;
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_queried) {
      _queried = true;
      _load();
    }
  }

  Future<void> _load() async {
    try {
      final result = await AppScope.of(context).auth.request('auth/security');
      if (mounted) {
        setState(() {
          _data = (result as Map).cast<String, dynamic>();
          _error = null;
        });
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  Future<void> _revoke(
    String action,
    Map<String, dynamic> fields, {
    bool current = false,
  }) async {
    if (_busy) return;
    setState(() => _busy = true);
    final app = AppScope.of(context);
    try {
      await app.auth.request(
        'auth/security/$action',
        method: 'POST',
        body: {
          ...fields,
          'reason': 'Account owner explicitly revoked this authorization',
        },
      );
      if (current) {
        await app.logout();
      } else {
        await _load();
      }
      if (mounted && !app.signedIn) {
        Navigator.pushNamedAndRemoveUntil(
          context,
          AppRoutes.login,
          (_) => false,
        );
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!AppScope.of(context).signedIn) {
      return Scaffold(
        body: SafeArea(
          child: Center(
            child: TextButton(
              onPressed: () => Navigator.pushNamedAndRemoveUntil(
                context,
                AppRoutes.login,
                (_) => false,
              ),
              child: const Text('Session ended. Sign in again.'),
            ),
          ),
        ),
      );
    }
    final sessions = (_data?['sessions'] as List?) ?? [],
        devices = (_data?['devices'] as List?) ?? [];
    return Scaffold(
      body: SafeArea(
        child: PageContent(
          children: [
            Row(
              children: [
                IconButton(
                  onPressed: () => Navigator.pop(context),
                  icon: const Icon(Icons.arrow_back),
                ),
                Expanded(child: tx('Account security', size: 20, weight: 700)),
              ],
            ),
            gap,
            tx(
              'Email: ${_data == null
                  ? 'unknown'
                  : _data!['email_verified'] == true
                  ? 'verified'
                  : 'not verified'}',
              weight: 600,
            ),
            TextButton(
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute<void>(builder: (_) => const RecoveryScreen()),
              ),
              child: const Text('Verify email or recover account'),
            ),
            gap,
            tx('Signed-in sessions', size: 16, weight: 700),
            tx(
              'Expiry alone does not disable push. Explicit revocation signs out that session and removes its push authorization.',
              size: 11,
            ),
            gap,
            for (final session in sessions)
              Panel(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    tx(
                      '${session['audience']} · ${session['current'] == true ? 'This session' : 'Other session'}',
                      weight: 600,
                    ),
                    tx('Expires ${session['expires_at']}', size: 11),
                    TextButton(
                      onPressed: _busy
                          ? null
                          : () => _revoke('revoke-session', {
                              'session_id': session['id'],
                            }, current: session['current'] == true),
                      child: const Text('Revoke session'),
                    ),
                  ],
                ),
              ),
            gap,
            ActionButton(
              'SIGN OUT ALL SESSIONS',
              onPressed: _busy || _data == null
                  ? null
                  : () => _revoke('revoke-all', {}, current: true),
            ),
            gap,
            tx('Push devices', size: 16, weight: 700),
            for (final device in devices)
              Panel(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    tx(
                      '${device['platform']} · ${device['enabled'] == true ? 'enabled' : 'disabled'}',
                    ),
                    TextButton(
                      onPressed: _busy || device['enabled'] != true
                          ? null
                          : () => _revoke('revoke-device', {
                              'device_id': device['id'],
                            }),
                      child: const Text('Revoke device and its session'),
                    ),
                  ],
                ),
              ),
            if (_data != null && devices.isEmpty)
              tx('No push devices registered.', size: 12),
            if (_error != null)
              tx(_error!, color: context.colors.red, size: 12),
            TextButton(
              onPressed: _busy ? null : _load,
              child: const Text('Refresh account security'),
            ),
          ],
        ),
      ),
    );
  }
}
