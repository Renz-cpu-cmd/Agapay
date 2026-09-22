import '../../core/ui.dart';
import '../../navigation/app_routes.dart';
import '../../widgets/common/auth_field.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});
  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _phone = TextEditingController();
  final _password = TextEditingController();
  String _barangay = 'San Vicente';
  bool _busy = false;
  String? _error;

  Future<void> _submit() async {
    FocusManager.instance.primaryFocus?.unfocus();
    if ([
      _name.text,
      _email.text,
      _phone.text,
    ].any((value) => value.trim().isEmpty)) {
      setState(() => _error = 'Enter your name, email, and phone number.');
      return;
    }
    if (_password.text.length < 12 || _password.text.length > 128) {
      setState(() => _error = 'Use a password with 12–128 characters.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await AppScope.of(context).register({
        'name': _name.text.trim(),
        'email': _email.text.trim(),
        'phone': _phone.text.trim(),
        'barangay': _barangay,
        'password': _password.text,
      });
      if (mounted) {
        Navigator.pushNamedAndRemoveUntil(
          context,
          AppRoutes.main,
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
  void dispose() {
    for (final c in [_name, _email, _phone, _password]) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: PageContent(
        padding: const EdgeInsets.fromLTRB(24, 24, 24, 32),
        children: [
          Row(
            children: [
              Semantics(
                label: 'Back',
                button: true,
                child: InkWell(
                  onTap: () => Navigator.pop(context),
                  child: Container(
                    width: 32,
                    height: 32,
                    decoration: BoxDecoration(
                      color: AppColors.surface,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Center(
                      child: SvgIcon('back', size: 16, color: AppColors.label),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    tx(
                      'Create Account',
                      size: 20,
                      weight: 700,
                      display: true,
                      color: Colors.white,
                      height: 1.4,
                    ),
                    tx(
                      'Join the AGAPAY community network',
                      size: 12,
                      color: AppColors.muted,
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              const AgapayLogo(size: 32),
              const SizedBox(width: 8),
              tx(
                'AGAPAY',
                display: true,
                weight: 700,
                size: 16,
                spacing: .8,
                color: AppColors.link,
              ),
            ],
          ),
          const SizedBox(height: 20),
          Column(
            spacing: 16,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              AuthField('Full Name', controller: _name, hint: 'Renz Alvarez'),
              AuthField(
                'Email Address',
                controller: _email,
                hint: 'example@email.com',
                keyboardType: TextInputType.emailAddress,
              ),
              AuthField(
                'Phone Number',
                controller: _phone,
                hint: '+63 9xx xxx xxxx',
                keyboardType: TextInputType.phone,
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  tx(
                    'BARANGAY',
                    size: 11,
                    weight: 600,
                    color: AppColors.label,
                    display: true,
                    spacing: 1.1,
                  ),
                  const SizedBox(height: 6),
                  BarangayPicker(
                    value: _barangay,
                    onChanged: (value) => setState(() => _barangay = value),
                  ),
                ],
              ),
              AuthField(
                'Password',
                controller: _password,
                hint: 'At least 12 characters',
                password: true,
              ),
            ],
          ),
          const SizedBox(height: 28),
          if (_error != null) ...[
            Semantics(
              liveRegion: true,
              child: tx(_error!, color: const Color(0xfff87171), size: 12),
            ),
            const SizedBox(height: 12),
          ],
          ActionButton(
            _busy ? 'CREATING ACCOUNT...' : 'CREATE ACCOUNT',
            vertical: 14,
            endColor: const Color(0xff2563eb),
            onPressed: _busy ? null : _submit,
          ),
          const SizedBox(height: 20),
          Text.rich(
            TextSpan(
              style: const TextStyle(
                fontSize: 12,
                height: 16 / 12,
                color: AppColors.muted,
              ),
              children: const [
                TextSpan(
                  text: 'By creating an account you agree to the AGAPAY ',
                ),
                TextSpan(
                  text: 'Terms of Service',
                  style: TextStyle(color: AppColors.link),
                ),
              ],
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    ),
  );
}
