import '../../core/ui.dart';
import '../../navigation/app_routes.dart';
import '../../widgets/common/auth_field.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;
  String? _error;

  Future<void> _submit() async {
    FocusManager.instance.primaryFocus?.unfocus();
    if (_email.text.trim().isEmpty || _password.text.isEmpty) {
      setState(() => _error = 'Enter your email and password.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await AppScope.of(context).login(_email.text, _password.text);
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
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Stack(
        children: [
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            height: 256,
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: RadialGradient(
                  center: Alignment.topCenter,
                  radius: .8,
                  colors: [
                    AppColors.blue.withValues(alpha: .2),
                    Colors.transparent,
                  ],
                  stops: const [0, .7],
                ),
              ),
            ),
          ),
          Column(
            children: [
              Expanded(
                child: SingleChildScrollView(
                  keyboardDismissBehavior:
                      ScrollViewKeyboardDismissBehavior.onDrag,
                  padding: const EdgeInsets.fromLTRB(24, 32, 24, 24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    spacing: 24,
                    children: [
                      Padding(
                        padding: const EdgeInsets.only(top: 16),
                        child: Column(
                          children: [
                            const AgapayLogo(),
                            const SizedBox(height: 12),
                            tx(
                              'AGAPAY',
                              size: 30,
                              weight: 900,
                              display: true,
                              color: Colors.white,
                              height: 1.2,
                              spacing: -.75,
                            ),
                            const SizedBox(height: 2),
                            tx(
                              'EARLY-WARNING SYSTEM',
                              size: 11,
                              color: AppColors.muted,
                              spacing: 1.1,
                            ),
                          ],
                        ),
                      ),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          tx(
                            'Welcome back',
                            size: 24,
                            weight: 700,
                            display: true,
                            color: Colors.white,
                            height: 32 / 24,
                          ),
                          const SizedBox(height: 4),
                          tx(
                            'Stay informed. Stay safe.',
                            color: AppColors.secondary,
                            height: 20 / 14,
                          ),
                        ],
                      ),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        spacing: 16,
                        children: [
                          AuthField(
                            'Email Address',
                            controller: _email,
                            hint: 'your@email.com',
                            keyboardType: TextInputType.emailAddress,
                          ),
                          AuthField(
                            'Password',
                            controller: _password,
                            hint: '••••••••',
                            password: true,
                          ),
                          Align(
                            alignment: Alignment.centerRight,
                            child: InkWell(
                              onTap: () => previewNotice(
                                context,
                                'Contact your AGAPAY administrator to reset your password.',
                              ),
                              child: tx(
                                'Forgot password?',
                                size: 12,
                                color: AppColors.link,
                                height: 16 / 12,
                              ),
                            ),
                          ),
                        ],
                      ),
                      if (_error != null ||
                          AppScope.of(context).authError != null)
                        Semantics(
                          liveRegion: true,
                          child: tx(
                            _error ?? AppScope.of(context).authError!,
                            color: const Color(0xfff87171),
                            size: 12,
                          ),
                        ),
                      ActionButton(
                        _busy ? 'SIGNING IN...' : 'LOG IN',
                        glow: true,
                        endColor: const Color(0xff2563eb),
                        onPressed: _busy ? null : _submit,
                      ),
                      Row(
                        children: [
                          const Expanded(child: Divider(height: 1)),
                          Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 12),
                            child: tx('OR', size: 11, color: AppColors.muted),
                          ),
                          const Expanded(child: Divider(height: 1)),
                        ],
                      ),
                      Wrap(
                        alignment: WrapAlignment.center,
                        children: [
                          tx(
                            "Don't have an account? ",
                            color: AppColors.secondary,
                          ),
                          InkWell(
                            onTap: () => Navigator.pushNamed(
                              context,
                              AppRoutes.register,
                            ),
                            child: tx(
                              'Register',
                              color: AppColors.link,
                              weight: 600,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 0, 12, 16),
                child: tx(
                  'AGAPAY v1.0.0 · URDANETA CITY, PANGASINAN',
                  size: 10,
                  mono: true,
                  color: AppColors.faint,
                  align: TextAlign.center,
                ),
              ),
            ],
          ),
        ],
      ),
    ),
  );
}
