import '../../core/ui.dart';
import '../../navigation/app_routes.dart';
import '../../widgets/common/auth_field.dart';

class EditProfileScreen extends StatefulWidget {
  const EditProfileScreen({super.key});
  @override
  State<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends State<EditProfileScreen> {
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _phone = TextEditingController();
  final _barangay = TextEditingController();
  final _current = TextEditingController();
  final _password = TextEditingController();
  bool _loaded = false, _busy = false;
  String? _error;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_loaded) {
      final user = AppScope.of(context).user;
      if (user != null) {
        _name.text = user.name;
        _email.text = user.email;
        _phone.text = user.phone;
        _barangay.text = user.barangay;
      }
      _loaded = true;
    }
  }

  @override
  void dispose() {
    for (final controller in [
      _name,
      _email,
      _phone,
      _barangay,
      _current,
      _password,
    ]) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    FocusManager.instance.primaryFocus?.unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });
    final app = AppScope.of(context);
    try {
      await app.saveProfile({
        'name': _name.text.trim(),
        'email': _email.text.trim(),
        'phone': _phone.text.trim(),
        'barangay': _barangay.text.trim(),
        if (_current.text.isNotEmpty) 'current_password': _current.text,
        if (_password.text.isNotEmpty) 'password': _password.text,
      });
      if (!mounted) return;
      if (!app.signedIn) {
        Navigator.pushNamedAndRemoveUntil(
          context,
          AppRoutes.login,
          (_) => false,
        );
      } else {
        Navigator.pop(context);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Your profile has been saved.')),
        );
      }
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
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
              tx('Edit Profile', size: 20, display: true, weight: 700),
            ],
          ),
          gap,
          AuthField('Full Name', controller: _name, hint: 'Your full name'),
          gap,
          AuthField(
            'Email Address',
            controller: _email,
            hint: 'your@email.com',
            keyboardType: TextInputType.emailAddress,
          ),
          gap,
          AuthField(
            'Phone Number',
            controller: _phone,
            hint: '+63 9xx xxx xxxx',
            keyboardType: TextInputType.phone,
          ),
          gap,
          AuthField('Barangay', controller: _barangay, hint: 'Your barangay'),
          gap,
          tx(
            'Enter your current password to change your email or password. A new password signs you out on all devices.',
            size: 12,
            color: AppColors.muted,
          ),
          gap,
          AuthField(
            'Current Password',
            controller: _current,
            hint: 'Current password',
            password: true,
          ),
          gap,
          AuthField(
            'New Password (optional)',
            controller: _password,
            hint: 'At least 12 characters',
            password: true,
          ),
          gap,
          if (_error != null) ...[
            Semantics(
              liveRegion: true,
              child: tx(_error!, color: const Color(0xfff87171), size: 12),
            ),
            gap,
          ],
          ActionButton(
            _busy ? 'SAVING...' : 'SAVE CHANGES',
            onPressed: _busy ? null : _save,
          ),
        ],
      ),
    ),
  );
}
