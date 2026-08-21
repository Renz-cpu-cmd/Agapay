import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/constants/app_constants.dart';
import '../../controllers/app_controller.dart';
import '../../widgets/branding/agapay_logo.dart';
import '../../navigation/app_routes.dart';

/// Screen 12: Resident Settings & Preferences
class SettingsScreen extends StatelessWidget {
  final AppController controller;

  const SettingsScreen({super.key, required this.controller});

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final user = controller.user;

        return Scaffold(
          backgroundColor: AppColors.background,
          appBar: AppBar(
            title: const Text('Settings & Preferences'),
          ),
          body: SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Profile Card
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: Row(
                      children: [
                        CircleAvatar(
                          radius: 28,
                          backgroundColor: AppColors.primaryLight,
                          child: Text(
                            user.fullName.isNotEmpty ? user.fullName[0] : 'U',
                            style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w800),
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                user.fullName,
                                style: const TextStyle(
                                  fontSize: 17,
                                  fontWeight: FontWeight.w800,
                                  color: AppColors.textPrimary,
                                ),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                user.email,
                                style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                              ),
                              const SizedBox(height: 2),
                              Text(
                                '${user.phone} · ${user.barangay}',
                                style: const TextStyle(fontSize: 12, color: AppColors.secondary, fontWeight: FontWeight.w600),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 20),

                  // Section: Community & Location
                  _sectionHeader('Community Zone'),
                  _settingsGroup([
                    ListTile(
                      leading: const Icon(Icons.location_city_rounded, color: AppColors.primary),
                      title: const Text('Primary Monitoring Barangay', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                      subtitle: Text(user.barangay, style: const TextStyle(fontSize: 12)),
                      trailing: const Icon(Icons.chevron_right_rounded, color: AppColors.textMuted),
                      onTap: () => _showBarangayDialog(context),
                    ),
                  ]),
                  const SizedBox(height: 16),

                  // Section: Emergency Alert Preferences
                  _sectionHeader('Early-Warning Notification Channels'),
                  _settingsGroup([
                    SwitchListTile(
                      activeColor: AppColors.primary,
                      title: const Text('Critical Flood Alarms', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                      subtitle: const Text('High priority audible alarm for Warning & Evacuation tiers', style: TextStyle(fontSize: 11)),
                      value: user.floodAlertsEnabled,
                      onChanged: (val) {
                        controller.updateUserProfile(user.copyWith(floodAlertsEnabled: val));
                      },
                    ),
                    const Divider(height: 1, indent: 16, endIndent: 16),
                    SwitchListTile(
                      activeColor: AppColors.primary,
                      title: const Text('Heavy Rainfall Advisories', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                      subtitle: const Text('Notifies when precipitation exceeds 10 mm/h', style: TextStyle(fontSize: 11)),
                      value: user.heavyRainAlertsEnabled,
                      onChanged: (val) {
                        controller.updateUserProfile(user.copyWith(heavyRainAlertsEnabled: val));
                      },
                    ),
                  ]),
                  const SizedBox(height: 16),

                  // Section: Language & Localization
                  _sectionHeader('Language / Wika'),
                  _settingsGroup([
                    ListTile(
                      leading: const Icon(Icons.translate_rounded, color: AppColors.secondary),
                      title: const Text('App Language', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                      subtitle: Text(user.preferredLanguage == 'en' ? 'English (Default)' : 'Filipino / Tagalog', style: const TextStyle(fontSize: 12)),
                      trailing: TextButton(
                        onPressed: controller.toggleLanguage,
                        child: Text(
                          user.preferredLanguage == 'en' ? 'Switch to Filipino' : 'Switch to English',
                          style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12),
                        ),
                      ),
                    ),
                  ]),
                  const SizedBox(height: 16),

                  // Section: Emergency SOS Contacts
                  _sectionHeader('Emergency SOS Contacts'),
                  _settingsGroup([
                    ...user.emergencyContacts.map((contact) {
                      return ListTile(
                        leading: const Icon(Icons.contact_phone_rounded, color: AppColors.alertNormal, size: 20),
                        title: Text(contact, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                      );
                    }),
                  ]),
                  const SizedBox(height: 16),

                  // Section: Offline Simulation Mode (For Testing Offline UI)
                  _sectionHeader('Diagnostic & Network Settings'),
                  _settingsGroup([
                    SwitchListTile(
                      activeColor: AppColors.offlineGrey,
                      secondary: Icon(
                        controller.isOffline ? Icons.cloud_off_rounded : Icons.cloud_done_rounded,
                        color: controller.isOffline ? AppColors.offlineGrey : AppColors.alertNormal,
                      ),
                      title: const Text('Simulate Offline Mode', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                      subtitle: const Text('Test cached telemetry, offline banners, and resilient public safety UI', style: TextStyle(fontSize: 11)),
                      value: controller.isOffline,
                      onChanged: (val) => controller.toggleOfflineMode(),
                    ),
                  ]),
                  const SizedBox(height: 16),

                  // Section: About AGAPAY
                  _sectionHeader('About AGAPAY'),
                  _settingsGroup([
                    const ListTile(
                      leading: AgapayLogo(size: 32),
                      title: Text(AppConstants.appName, style: TextStyle(fontWeight: FontWeight.w800, fontSize: 14)),
                      subtitle: Text('${AppConstants.appTagline} · ${AppConstants.appVersion}', style: TextStyle(fontSize: 11)),
                    ),
                    const Divider(height: 1, indent: 16, endIndent: 16),
                    ListTile(
                      leading: const Icon(Icons.info_outline_rounded, color: AppColors.textSecondary),
                      title: const Text('Architecture & Backend Interface', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
                      subtitle: const Text('FastAPI + PostgreSQL/Supabase ready mock layer', style: TextStyle(fontSize: 11)),
                      onTap: () {
                        showAboutDialog(
                          context: context,
                          applicationName: 'AGAPAY',
                          applicationVersion: AppConstants.appVersion,
                          applicationLegalese: 'Community Flood & Disaster Early-Warning System\nDesigned for public safety and community resilience.',
                        );
                      },
                    ),
                  ]),
                  const SizedBox(height: 20),

                  // Logout Button
                  SizedBox(
                    width: double.infinity,
                    height: 48,
                    child: OutlinedButton.icon(
                      onPressed: () {
                        controller.logout();
                        Navigator.pushNamedAndRemoveUntil(context, AppRoutes.login, (route) => false);
                      },
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppColors.alertEvacuate,
                        side: const BorderSide(color: AppColors.alertEvacuate),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      icon: const Icon(Icons.logout_rounded, size: 18),
                      label: const Text('Sign Out', style: TextStyle(fontWeight: FontWeight.w700)),
                    ),
                  ),
                  const SizedBox(height: 32),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _sectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.only(left: 4.0, bottom: 8.0),
      child: Text(
        title,
        style: const TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w800,
          color: AppColors.textSecondary,
          letterSpacing: 0.5,
        ),
      ),
    );
  }

  Widget _settingsGroup(List<Widget> children) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(children: children),
    );
  }

  void _showBarangayDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) {
        return AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Text('Select Home Barangay', style: TextStyle(fontWeight: FontWeight.w800)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: AppConstants.availableBarangays.map((bg) {
              return ListTile(
                title: Text(bg, style: const TextStyle(fontWeight: FontWeight.w600)),
                trailing: controller.user.barangay == bg
                    ? const Icon(Icons.check_rounded, color: AppColors.primary)
                    : null,
                onTap: () {
                  controller.updateUserProfile(controller.user.copyWith(barangay: bg));
                  Navigator.pop(ctx);
                },
              );
            }).toList(),
          ),
        );
      },
    );
  }
}
