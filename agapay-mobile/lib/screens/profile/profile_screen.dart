import '../../core/ui.dart';
import 'privacy_screen.dart';
import '../../widgets/common/alert_subscriptions.dart';
import '../../navigation/app_routes.dart';
import '../../widgets/common/auth_field.dart';
import 'edit_profile_screen.dart';
import 'account_security_screen.dart';
import '../../widgets/common/product_capability_settings.dart';

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
                      shape: BoxShape.circle,
                      color: context.colors.blue,
                    ),
                    child: Center(
                      child: tx(
                        user.name.substring(0, 1).toUpperCase(),
                        size: 24,
                        display: true,
                        weight: 800,
                        color: Colors.white,
                        adaptive: false,
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
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 8,
                                vertical: 2,
                              ),
                              decoration: BoxDecoration(
                                color: context.colors.border,
                                borderRadius: BorderRadius.circular(20),
                              ),
                              child: tx(
                                'Resident',
                                size: 10,
                                mono: true,
                                color: context.colors.link,
                              ),
                            ),
                            tx(
                              'Active account',
                              size: 10,
                              mono: true,
                              color: context.colors.muted,
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
                'Profile locality: ${app.barangay}',
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
              TextButton.icon(
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute<void>(
                    builder: (_) => const AccountSecurityScreen(),
                  ),
                ),
                icon: const Icon(Icons.lock_outline, size: 18),
                label: const Text(
                  'Account security and signed-in devices',
                  textAlign: TextAlign.center,
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
                Icons.palette_outlined,
                'Appearance',
                'Map follows your theme',
                _link(
                  app.theme.mode == ThemeMode.dark ? 'Dark' : 'Default',
                  () => showModalBottomSheet<void>(
                    context: context,
                    showDragHandle: true,
                    builder: (context) => SafeArea(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          for (final choice in [
                            (ThemeMode.light, 'Default (Light)'),
                            (ThemeMode.dark, 'Dark'),
                          ])
                            ListTile(
                              title: tx(choice.$2),
                              selected: app.theme.mode == choice.$1,
                              trailing: app.theme.mode == choice.$1
                                  ? Icon(
                                      Icons.check,
                                      color: context.colors.link,
                                    )
                                  : null,
                              onTap: () {
                                Navigator.pop(context);
                                app.theme.setMode(choice.$1);
                              },
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
              if (app.theme.saveError != null)
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: tx(
                    app.theme.saveError!,
                    size: 11,
                    color: context.colors.red,
                  ),
                ),
              _line(),
              const ProductCapabilitySettings(),
              _line(),
              _setting(
                Icons.home_work_outlined,
                'Profile locality (self-reported)',
                'Profile locality; push targeting uses explicit subscriptions',
                _link(
                  app.barangay,
                  () => showModalBottomSheet<void>(
                    context: context,
                    showDragHandle: true,
                    backgroundColor: context.colors.background,
                    builder: (context) => SafeArea(
                      child: ListView(
                        shrinkWrap: true,
                        children: [
                          for (final b in barangays)
                            ListTile(
                              title: tx(b),
                              trailing: b == app.barangay
                                  ? SvgIcon('check', color: context.colors.link)
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
                  applicationVersion: app.buildInfo.label,
                  children: [
                    tx(
                      'Community Flood Early-Warning System. Interactive frontend prototype for Urdaneta City, Pangasinan.',
                    ),
                  ],
                ),
                child: _setting(
                  Icons.info_outline_rounded,
                  'About AGAPAY',
                  app.buildInfo.label,
                  SvgIcon('chevron', size: 14, color: context.colors.muted),
                ),
              ),
              _line(),
              InkWell(
                onTap: () => Navigator.push(
                  context,
                  MaterialPageRoute<void>(
                    builder: (_) => const PrivacyScreen(),
                  ),
                ),
                child: _setting(
                  Icons.privacy_tip_outlined,
                  'Privacy Policy',
                  'How AGAPAY handles your data',
                  SvgIcon('chevron', size: 14, color: context.colors.muted),
                ),
              ),
            ],
          ),
        ),
        gap,
        const ExpansionTile(
          key: PageStorageKey('profile-alert-subscriptions'),
          title: Text('Alert subscriptions'),
          children: [AlertSubscriptionsPanel()],
        ),
        gap,
        ActionButton(
          _leaving
              ? 'SIGNING OUT…'
              : app.auth.offlineReader
              ? 'EXIT OFFLINE READER (LOCAL)'
              : 'LOG OUT',
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
          color: context.colors.faint,
          align: TextAlign.center,
        ),
        tx(
          'AGAPAY · © ${DateTime.now().year}',
          size: 10,
          mono: true,
          color: context.colors.faint,
          align: TextAlign.center,
        ),
      ],
    );
  }

  Widget _profileRow(IconData icon, String label, String value) => Row(
    spacing: 10,
    children: [
      SizedBox(
        width: 22,
        child: Icon(icon, size: 18, color: context.colors.link),
      ),
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            tx(label, size: 10, mono: true, color: context.colors.muted),
            tx(value, display: true, weight: 500),
          ],
        ),
      ),
    ],
  );
  Widget _setting(IconData icon, String label, String sub, Widget right) =>
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: LayoutBuilder(
          builder: (context, box) {
            final stacked = MediaQuery.textScalerOf(context).scale(14) > 20;
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  spacing: 12,
                  children: [
                    SizedBox(
                      width: 28,
                      child: Icon(icon, size: 21, color: context.colors.link),
                    ),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          tx(
                            label,
                            display: true,
                            weight: 600,
                            color: Colors.white,
                          ),
                          tx(
                            sub,
                            size: 11,
                            color: context.colors.muted,
                            height: 1.4,
                          ),
                        ],
                      ),
                    ),
                    if (!stacked)
                      ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 94),
                        child: right,
                      ),
                  ],
                ),
                if (stacked)
                  Padding(
                    padding: const EdgeInsets.only(left: 40, top: 8),
                    child: Align(alignment: Alignment.centerLeft, child: right),
                  ),
              ],
            );
          },
        ),
      );
  Widget _line() => const Padding(
    padding: EdgeInsets.symmetric(horizontal: 16),
    child: Divider(height: 1),
  );
  Widget _link(String label, VoidCallback tap) => InkWell(
    onTap: tap,
    child: ConstrainedBox(
      constraints: const BoxConstraints(minWidth: 48, minHeight: 48),
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
              color: context.colors.link,
            ),
          ),
          SvgIcon('chevron', size: 10, color: context.colors.link),
        ],
      ),
    ),
  );
}
