import '../../core/ui.dart';
import 'resource_instructions.dart';
import '../../models/community_alert.dart';

class ResidentAreaPanel extends StatelessWidget {
  const ResidentAreaPanel({super.key});
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context), prefs = app.preferences;
    final choices = prefs.areas;
    final selected = choices.any((a) => a['id'] == prefs.residentAreaId)
        ? prefs.residentAreaId
        : null;
    return Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Semantics(
            header: true,
            child: tx('Your area', size: 20, weight: 700),
          ),
          Text(
            prefs.residentAreaName ??
                prefs.residentAreaId ??
                'No verified area selected',
          ),
          if (choices.isNotEmpty)
            DropdownButtonFormField<String>(
              key: ValueKey(
                'resident-area-$selected-${prefs.revision}-${prefs.busy}-${prefs.error}',
              ),
              initialValue: selected,
              isExpanded: true,
              itemHeight: null,
              decoration: const InputDecoration(
                labelText: 'Area for advisories',
              ),
              items: [
                const DropdownMenuItem<String>(
                  value: null,
                  child: Text('No verified area selected'),
                ),
                for (final a in choices)
                  DropdownMenuItem(
                    value: a['id'] as String,
                    child: Text(a['name'] as String),
                  ),
              ],
              onChanged: prefs.busy || prefs.conflicted
                  ? null
                  : (value) => prefs.save({'resident_area_id': value}),
            )
          else
            TextButton(
              onPressed: prefs.busy ? null : prefs.refresh,
              child: const Text('Check available areas'),
            ),
          if (prefs.error != null) Text(prefs.error!),
          if (prefs.error != null || prefs.conflicted)
            TextButton(
              onPressed: prefs.busy ? null : prefs.refresh,
              child: const Text('Refresh area choices'),
            ),
          const Text(
            'Area filters advisories. Your sensor station and push subscriptions are separate choices.',
          ),
        ],
      ),
    );
  }
}

class ResidentNextAction extends StatelessWidget {
  const ResidentNextAction({this.compact = false, super.key});
  final bool compact;
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context), view = app.monitoring.primaryView;
    final notices = app.notices;
    final effective = notices.current.items.where(
      (n) => n.status == 'Actual' && n.lifecycle(notices.now()) == 'effective',
    );
    final confirmed = notices.confirmed(notices.current);
    final String instruction;
    if (confirmed && effective.isNotEmpty) {
      instruction = compact
          ? 'Check the current area advisory and follow its issuer’s instructions.'
          : 'Read the current area instructions below and check the issuer and expiry. If notices differ, confirm with the issuing authority.';
    } else if (app.preferences.residentAreaId == null) {
      instruction = compact
          ? 'Choose your area above to check local advisories.'
          : 'Choose your area to check applicable advisories. Use a verified contact if you need local guidance.';
    } else if (!confirmed || view == null || !view.depth.fresh) {
      instruction = compact
          ? 'Conditions are unconfirmed. Check authority updates or a verified contact.'
          : 'Current conditions are unconfirmed. Check authority updates and verified contacts; a missing or old reading cannot establish safety.';
    } else {
      instruction =
          view.station.alertLevel?.action ??
          'Check authority updates and local conditions before deciding what to do.';
    }
    return Panel(
      padding: compact ? 14 : 16,
      border: context.colors.blue,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Semantics(
            header: true,
            child: tx('What to do next', size: compact ? 18 : 20, weight: 700),
          ),
          Text(instruction),
          if (!compact)
            TextButton(
              onPressed: () => app.navigate(AppTab.alerts),
              child: const Text('Review area advisories'),
            ),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              FilledButton.icon(
                style: compact
                    ? FilledButton.styleFrom(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 10,
                        ),
                        minimumSize: const Size(48, 48),
                      )
                    : null,
                onPressed: () => app.navigate(AppTab.sos),
                icon: Icon(Icons.sos, size: compact ? 18 : 24),
                label: const Text('SOS'),
              ),
              OutlinedButton(
                style: compact
                    ? OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 10,
                        ),
                        minimumSize: const Size(48, 48),
                      )
                    : null,
                onPressed: () => showModalBottomSheet<void>(
                  context: context,
                  isScrollControlled: true,
                  showDragHandle: true,
                  builder: (context) => SafeArea(
                    child: SizedBox(
                      height: MediaQuery.sizeOf(context).height * .8,
                      child: const SingleChildScrollView(
                        padding: EdgeInsets.all(16),
                        child: ResidentHelpPanel(inSheet: true),
                      ),
                    ),
                  ),
                ),
                child: const Text('Verified contacts'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class ResidentHelpPanel extends StatelessWidget {
  const ResidentHelpPanel({this.inSheet = false, super.key});
  final bool inSheet;
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context),
        registry = app.resources,
        area = app.preferences.residentAreaId;
    void navigate(AppTab tab, {bool evacuation = false}) {
      if (inSheet) Navigator.of(context).pop();
      app.navigate(tab, evacuation: evacuation);
    }

    final rows = (registry.items['preparedness'] ?? [])
        .where(
          (r) =>
              area != null &&
              (r.raw['area_ids'] as List? ?? []).contains(area) &&
              r.raw['mode'] == 'Actual' &&
              r.raw['verified_at'] != null &&
              ['verified', 'expired'].contains(r.verification(DateTime.now())),
        )
        .toList();
    return Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Semantics(
            header: true,
            child: tx('Help and contacts', size: 20, weight: 700),
          ),
          const Text(
            'SOS is a test workflow. It does not dispatch a responder. Use verified response contacts for real assistance.',
          ),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              FilledButton.icon(
                onPressed: () => navigate(AppTab.sos),
                icon: const Icon(Icons.sos),
                label: const Text('Open SOS'),
              ),
              OutlinedButton.icon(
                onPressed: () => navigate(AppTab.map, evacuation: true),
                icon: const Icon(Icons.location_on_outlined),
                label: const Text('Shelters and road reports'),
              ),
            ],
          ),
          if (rows.isEmpty)
            const Text(
              'No verified contact reference is available for your selected area. No response coverage is confirmed.',
            ),
          if (registry.errors['preparedness'] != null)
            Text(registry.errors['preparedness']!),
          for (final row in rows.take(3)) ...[
            const SizedBox(height: 12),
            Text(
              '${row.name} · ${row.raw['issuer_name']}',
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
            Text(
              '${!registry.isCurrent('preparedness') || app.auth.offlineReader || row.verification(DateTime.now()) != 'verified' ? 'LAST KNOWN · confirm availability' : 'Verified reference'} · Expires ${row.expiresAt == null ? 'unknown' : communityAlertTime(row.expiresAt!)}',
            ),
            for (final contact in (row.data['contacts'] as List? ?? []))
              SelectableText(
                '${contact['name']}: ${contact['contact']} · Hours: ${contact['hours']}',
              ),
            ExpansionTile(
              key: PageStorageKey('preparedness-${row.id}-details'),
              title: const Text('Preparedness instructions and source'),
              children: [
                ResourceInstructions(
                  resource: row,
                  cached:
                      !registry.isCurrent('preparedness') ||
                      app.auth.offlineReader,
                ),
              ],
            ),
          ],
          TextButton(
            onPressed: registry.busy ? null : registry.refresh,
            child: const Text('Refresh contacts'),
          ),
        ],
      ),
    );
  }
}
