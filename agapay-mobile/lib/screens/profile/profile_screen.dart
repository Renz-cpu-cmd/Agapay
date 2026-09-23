import '../../core/ui.dart';
import '../../navigation/app_routes.dart';
import '../../widgets/common/auth_field.dart';
import 'edit_profile_screen.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});
  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  bool _leaving = false;
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final user = app.user;
    if (user == null) return const SizedBox.shrink();
    return PageContent(
      children: [
        const PageHeading('Profile', 'Account & Settings'),
        Panel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                spacing: 16,
                children: [
                  Container(
                    width: 56,
                    height: 56,
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(16),
                      gradient: const LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [AppColors.blue, Color(0xff7c3aed)],
                      ),
                    ),
                    child: Center(
                      child: tx(
                        user.name.substring(0, 1).toUpperCase(),
                        size: 24,
                        display: true,
                        weight: 800,
                        color: Colors.white,
                      ),
                    ),
                  ),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        tx(
                          user.name,
                          size: 18,
                          display: true,
                          weight: 700,
                          color: Colors.white,
                        ),
                        const SizedBox(height: 2),
                        Row(
                          spacing: 8,
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                color: AppColors.border,
                                borderRadius: BorderRadius.circular(20),
                              ),
                              child: tx(
                                'Resident',
                                size: 10,
                                mono: true,
                                color: AppColors.link,
                              ),
                            ),
                            tx(
                              'Active account',
                              size: 10,
                              mono: true,
                              color: AppColors.muted,
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              const Divider(height: 1),
              const SizedBox(height: 16),
              _profileRow(Icons.mail_outline_rounded, 'Email', user.email),
              const SizedBox(height: 10),
              _profileRow(Icons.phone_outlined, 'Phone', user.phone),
              const SizedBox(height: 10),
              _profileRow(
                Icons.location_on_outlined,
                'Barangay',
                '${app.barangay}, Urdaneta',
              ),
              const SizedBox(height: 10),
              _profileRow(
                Icons.calendar_today_outlined,
                'Member since',
                '${user.createdAt.toLocal().day}/${user.createdAt.toLocal().month}/${user.createdAt.toLocal().year}',
              ),
              const SizedBox(height: 16),
              ActionButton(
                'EDIT PROFILE',
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute<void>(
                    builder: (_) => const EditProfileScreen(),
                  ),
                ),
              ),
            ],
          ),
        ),
        gap,
        caption('SETTINGS'),
        const SizedBox(height: 8),
        Panel(
          padding: 0,
          child: Column(
            children: [
              _setting(
                Icons.notifications_none_rounded,
                'Flood Alerts',
                'Future preference only · Does not control push delivery',
                _toggle(
                  'Flood Alerts',
                  app.notifications,
                  (v) => app.updateSettings(notifications: v),
                ),
              ),
              _line(),
              _setting(
                Icons.my_location_rounded,
                'Location Services',
                app.location
                    ? 'Allowed · For SOS and nearest station'
                    : 'Denied · Tap to enable',
                _toggle(
                  'Location Services',
                  app.location,
                  (v) => app.updateSettings(location: v),
                ),
              ),
              _line(),
              _setting(
                Icons.language_rounded,
                'Language',
                'Display language for app content',
                _link(
                  app.language,
                  () => app.updateSettings(
                    language: app.language == 'English'
                        ? 'Filipino'
                        : 'English',
                  ),
                ),
              ),
              _line(),
              _setting(
                Icons.home_work_outlined,
                'Barangay',
                'Your registered barangay for targeted alerts',
                _link(
                  app.barangay,
                  () => showModalBottomSheet<void>(
                    context: context,
                    showDragHandle: true,
                    backgroundColor: AppColors.background,
                    builder: (context) => SafeArea(
                      child: ListView(
                        shrinkWrap: true,
                        children: [
                          for (final b in barangays)
                            ListTile(
                              title: tx(b),
                              trailing: b == app.barangay
                                  ? const SvgIcon(
                                      'check',
                                      color: AppColors.link,
                                    )
                                  : null,
                              onTap: () async {
                                try {
                                  await app.saveProfile({'barangay': b});
                                  if (context.mounted) Navigator.pop(context);
                                } catch (error) {
                                  if (context.mounted) {
                                    ScaffoldMessenger.of(context).showSnackBar(
                                      SnackBar(content: Text(error.toString())),
                                    );
                                  }
                                }
                              },
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
        gap,
        Panel(
          padding: 0,
          child: Column(
            children: [
              InkWell(
                onTap: () => showAboutDialog(
                  context: context,
                  applicationName: 'AGAPAY',
                  applicationVersion: '1.0.0',
                  children: [
                    tx(
                      'Community Flood Early-Warning System. Interactive frontend prototype for Urdaneta City, Pangasinan.',
                    ),
                  ],
                ),
                child: _setting(
                  Icons.info_outline_rounded,
                  'About AGAPAY',
                  'Version 1.0.0 · Build 2024.001',
                  const SvgIcon('chevron', size: 14, color: AppColors.muted),
                ),
              ),
              _line(),
              InkWell(
                onTap: () => previewNotice(
                  context,
                  'The privacy policy has not been supplied yet.',
                ),
                child: _setting(
                  Icons.privacy_tip_outlined,
                  'Privacy Policy',
                  'How AGAPAY handles your data',
                  const SvgIcon('chevron', size: 14, color: AppColors.muted),
                ),
              ),
            ],
          ),
        ),
        gap,
        ActionButton(
          _leaving ? 'SIGNING OUT…' : 'LOG OUT',
          vertical: 14,
          weight: 600,
          color: const Color(0x301c0000),
          border: const Color(0x40dc2626),
          textColor: const Color(0xfff87171),
          onPressed: _leaving
              ? null
              : () async {
                  setState(() => _leaving = true);
                  try {
                    await app.logout();
                    if (context.mounted) {
                      Navigator.pushNamedAndRemoveUntil(
                        context,
                        AppRoutes.login,
                        (_) => false,
                      );
                    }
                  } catch (error) {
                    if (context.mounted) {
                      ScaffoldMessenger.of(
                        context,
                      ).showSnackBar(SnackBar(content: Text(error.toString())));
                    }
                  } finally {
                    if (mounted) setState(() => _leaving = false);
                  }
                },
        ),
        const SizedBox(height: 16),
        tx(
          'AGAPAY · Community Flood Early-Warning System',
          size: 10,
          mono: true,
          color: AppColors.faint,
          align: TextAlign.center,
        ),
        tx(
          'Urdaneta City, Pangasinan · © 2024',
          size: 10,
          mono: true,
          color: AppColors.faint,
          align: TextAlign.center,
        ),
      ],
    );
  }

  Widget _profileRow(IconData icon, String label, String value) => Row(
    spacing: 10,
    children: [
      SizedBox(width: 22, child: Icon(icon, size: 18, color: AppColors.link)),
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            tx(label, size: 10, mono: true, color: AppColors.muted),
            tx(value, display: true, weight: 500),
          ],
        ),
      ),
    ],
  );
  Widget _setting(IconData icon, String label, String sub, Widget right) =>
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Row(
          spacing: 12,
          children: [
            SizedBox(
              width: 28,
              child: Icon(icon, size: 21, color: AppColors.link),
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  tx(label, display: true, weight: 600, color: Colors.white),
                  tx(sub, size: 11, color: AppColors.muted, height: 1.4),
                ],
              ),
            ),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 94),
              child: right,
            ),
          ],
        ),
      );
  Widget _line() => const Padding(
    padding: EdgeInsets.symmetric(horizontal: 16),
    child: Divider(height: 1),
  );
  Widget _link(String label, VoidCallback tap) => InkWell(
    onTap: tap,
    child: Row(
      mainAxisSize: MainAxisSize.min,
      spacing: 6,
      children: [
        Flexible(
          child: tx(
            label,
            size: 12,
            display: true,
            weight: 600,
            color: AppColors.link,
          ),
        ),
        const SvgIcon('chevron', size: 10, color: AppColors.link),
      ],
    ),
  );
  Widget _toggle(String label, bool value, ValueChanged<bool> onChanged) =>
      Semantics(
        label: label,
        toggled: value,
        child: InkWell(
          onTap: () => onChanged(!value),
          borderRadius: BorderRadius.circular(20),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 180),
            width: 40,
            height: 24,
            decoration: BoxDecoration(
              color: value ? AppColors.blue : AppColors.border,
              borderRadius: BorderRadius.circular(20),
            ),
            child: AnimatedAlign(
              duration: const Duration(milliseconds: 180),
              alignment: value ? Alignment.centerRight : Alignment.centerLeft,
              child: const Padding(
                padding: EdgeInsets.symmetric(horizontal: 4),
                child: Dot(Colors.white, size: 16),
              ),
            ),
          ),
        ),
      );
}
