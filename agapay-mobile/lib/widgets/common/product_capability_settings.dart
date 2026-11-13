import '../../core/ui.dart';
import '../../l10n/generated/app_localizations_en.dart';

class ProductCapabilitySettings extends StatefulWidget {
  const ProductCapabilitySettings({super.key});
  @override
  State<ProductCapabilitySettings> createState() =>
      _ProductCapabilitySettingsState();
}

class _ProductCapabilitySettingsState extends State<ProductCapabilitySettings> {
  bool _queried = false;
  final strings = AppLocalizationsEn();
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_queried) {
      _queried = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) AppScope.of(context).refreshCapabilities();
      });
    }
  }

  Future<void> _requestLanguage() async {
    final app = AppScope.of(context);
    var requested = app.preferences.requestedLanguage ?? '';
    final value = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Community language request'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(strings.languageRequest),
            TextFormField(
              initialValue: requested,
              onChanged: (value) => requested = value,
              maxLength: 80,
              decoration: const InputDecoration(
                labelText: 'Requested language',
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, requested.trim()),
            child: const Text('Save request'),
          ),
        ],
      ),
    );
    if (value != null) {
      await app.preferences.save({
        'requested_language': value.isEmpty ? null : value,
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context), prefs = app.preferences;
    final canSave = prefs.ready && !prefs.busy && !prefs.conflicted;
    final os = app.capabilities.location;
    final permission = switch (os.permission) {
      'always' => 'Allowed always',
      'whileInUse' => 'Allowed while in use',
      'denied' => 'Denied or not requested',
      'deniedForever' => 'Denied; change in OS settings',
      _ => os.permission,
    };
    final choices = prefs.areas;
    final selected = choices.any((a) => a['id'] == prefs.residentAreaId)
        ? prefs.residentAreaId
        : null;
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Icon(
                Icons.notifications_none,
                size: 21,
                color: context.colors.link,
              ),
              const SizedBox(width: 12),
              Expanded(child: tx('Flood Alerts', display: true, weight: 600)),
              Semantics(
                label: 'Flood Alerts',
                child: Switch.adaptive(
                  value: app.notifications,
                  onChanged: canSave
                      ? (value) => app.updateSettings(notifications: value)
                      : null,
                ),
              ),
            ],
          ),
          tx(strings.deliveryPolicy, size: 10, color: context.colors.muted),
          tx(
            app.notificationRegistration.capabilitySupported
                ? 'Device push configured'
                : 'Device push unavailable on this build',
            size: 11,
            color: context.colors.secondary,
          ),
          ExpansionTile(
            key: const PageStorageKey('profile-notification-permissions'),
            tilePadding: EdgeInsets.zero,
            title: tx('Notification permission details', size: 11),
            children: [
              tx(
                'Account preference: ${prefs.ready ? (app.notifications ? 'on' : 'off') : 'unknown'} · Device push: ${app.notificationRegistration.capabilitySupported ? 'configured' : 'unavailable on this build'} · OS notification permission: ${app.notificationRegistration.permissionStatus} · Registration: ${app.notificationRegistration.state.name}',
                size: 10,
                color: context.colors.secondary,
              ),
            ],
          ),
          const Divider(),
          Row(
            children: [
              Icon(
                Icons.location_on_outlined,
                size: 21,
                color: context.colors.link,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: tx('Location Services', display: true, weight: 600),
              ),
              Semantics(
                label: 'Location Services',
                child: Switch.adaptive(
                  value: app.location,
                  onChanged: (value) => app.updateSettings(location: value),
                ),
              ),
            ],
          ),
          tx(
            'OS permission: $permission · Device location service: ${os.service}',
            size: 10,
            color: context.colors.secondary,
          ),
          tx(strings.locationPolicy, size: 10, color: context.colors.muted),
          TextButton(
            onPressed: () => app.refreshCapabilities(),
            child: const Text('Refresh device permission status'),
          ),
          const Divider(),
          Row(
            children: [
              Icon(Icons.language, size: 21, color: context.colors.link),
              const SizedBox(width: 12),
              Expanded(
                child: tx(
                  'Language · ${strings.operationalLanguage}',
                  display: true,
                  weight: 600,
                ),
              ),
            ],
          ),
          tx(
            strings.translationUnavailable,
            size: 11,
            color: context.colors.muted,
          ),
          TextButton(
            onPressed: canSave ? _requestLanguage : null,
            child: Text(
              prefs.requestedLanguage == null
                  ? 'Request a community language'
                  : 'Language requested: ${prefs.requestedLanguage}',
            ),
          ),
          const Divider(),
          Row(
            children: [
              Icon(
                Icons.home_work_outlined,
                size: 21,
                color: context.colors.link,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: tx(strings.residentArea, display: true, weight: 600),
              ),
            ],
          ),
          DropdownButtonFormField<String>(
            key: ValueKey('${prefs.revision}-$selected'),
            initialValue: selected,
            isExpanded: true,
            decoration: const InputDecoration(
              labelText: 'Verified area selection',
            ),
            items: [
              const DropdownMenuItem<String>(
                value: null,
                child: Text('No verified area selected'),
              ),
              for (final area in choices)
                DropdownMenuItem(
                  value: area['id'] as String,
                  child: Text(
                    '${area['name']} · ${area['id']}',
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
            ],
            onChanged: canSave && choices.isNotEmpty
                ? (value) => prefs.save({'resident_area_id': value})
                : null,
          ),
          tx(
            '${prefs.residentAreaName ?? 'No verified resident area'} · ID ${prefs.residentAreaId ?? '—'}. Profile context does not subscribe you to alerts or establish exposure.',
            size: 10,
            color: context.colors.muted,
          ),
          if (choices.isEmpty)
            tx(
              'No verified geographic choices available. Existing locality text remains self-reported.',
              size: 10,
              color: context.colors.muted,
            ),
          if (prefs.error != null)
            tx(prefs.error!, size: 11, color: context.colors.red),
          if (prefs.localError != null)
            tx(prefs.localError!, size: 11, color: context.colors.red),
          if (!prefs.ready || prefs.error != null || prefs.conflicted)
            TextButton(
              onPressed: prefs.busy ? null : prefs.refresh,
              child: const Text('Refresh preferences; review before saving'),
            ),
        ],
      ),
    );
  }
}
