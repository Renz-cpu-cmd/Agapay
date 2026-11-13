import '../../core/ui.dart';
import '../../widgets/common/auth_field.dart';

class RecoveryScreen extends StatefulWidget {
  const RecoveryScreen({super.key});
  @override
  State<RecoveryScreen> createState() => _RecoveryScreenState();
}

class _RecoveryScreenState extends State<RecoveryScreen> {
  final _email = TextEditingController(),
      _token = TextEditingController(),
      _password = TextEditingController();
  bool _busy = false, _queried = false, _available = false;
  String _purpose = 'password_reset';
  String? _message, _error;
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
      final caps = await AppScope.of(
        context,
      ).auth.request('auth/capabilities', authenticated: false);
      if (mounted) {
        setState(() => _available = caps['recovery_available'] == true);
      }
    } catch (_) {
      /* Unconfigured recovery stays unavailable. */
    }
  }

  Future<void> _submit(bool complete) async {
    if (_busy) return;
    FocusManager.instance.primaryFocus?.unfocus();
    setState(() {
      _busy = true;
      _error = null;
      _message = null;
    });
    try {
      final result = await AppScope.of(context).auth.request(
        complete ? 'auth/recovery/complete' : 'auth/recovery/request',
        method: 'POST',
        authenticated: false,
        body: complete
            ? {
                'token': _token.text.trim(),
                if (_password.text.isNotEmpty) 'password': _password.text,
              }
            : {'email': _email.text.trim(), 'purpose': _purpose},
      );
      if (mounted) setState(() => _message = result['message'] as String);
      if (complete) {
        _token.clear();
        _password.clear();
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  void dispose() {
    _email.dispose();
    _token.dispose();
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: PageContent(
        children: [
          Row(
            children: [
              IconButton(
                onPressed: () => Navigator.pop(context),
                icon: const Icon(Icons.arrow_back),
              ),
              Expanded(child: tx('Account recovery', size: 20, weight: 700)),
            ],
          ),
          gap,
          tx(
            'Email codes expire and work once. Recovery does not sign you in. Staff accounts continue to require their authenticator.',
            size: 12,
          ),
          gap,
          if (_available) ...[
            AuthField(
              'Email Address',
              controller: _email,
              hint: 'Your account email',
              keyboardType: TextInputType.emailAddress,
            ),
            gap,
            DropdownButtonFormField<String>(
              initialValue: _purpose,
              decoration: const InputDecoration(labelText: 'Email action'),
              items: const [
                DropdownMenuItem(
                  value: 'password_reset',
                  child: Text('Reset password'),
                ),
                DropdownMenuItem(
                  value: 'verify_email',
                  child: Text('Verify email'),
                ),
              ],
              onChanged: _busy
                  ? null
                  : (value) => setState(() => _purpose = value!),
            ),
            gap,
            ActionButton(
              'SEND EMAIL CODE',
              onPressed: _busy ? null : () => _submit(false),
            ),
            gap,
          ] else ...[
            tx(
              'Email recovery unavailable. Contact your AGAPAY operator. You can still confirm an existing code below.',
              size: 12,
            ),
            gap,
          ],
          AuthField(
            'One-use email code',
            controller: _token,
            hint: 'Paste the code from your email',
          ),
          gap,
          AuthField(
            'New Password (reset or invitation only)',
            controller: _password,
            hint: 'At least 12 characters',
            password: true,
          ),
          gap,
          ActionButton(
            'CONFIRM EMAIL CODE',
            onPressed: _busy ? null : () => _submit(true),
          ),
          gap,
          if (_message != null)
            Semantics(liveRegion: true, child: tx(_message!, size: 12)),
          if (_error != null)
            Semantics(
              liveRegion: true,
              child: tx(_error!, color: context.colors.red, size: 12),
            ),
        ],
      ),
    ),
  );
}
