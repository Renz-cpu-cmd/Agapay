import '../../core/ui.dart';
import '../../models/response_resource.dart';

class ResourceInstructions extends StatelessWidget {
  const ResourceInstructions({
    super.key,
    required this.resource,
    required this.cached,
  });
  final ResponseResource resource;
  final bool cached;
  @override
  Widget build(BuildContext context) {
    final data = resource.data, raw = resource.raw, now = DateTime.now();
    final reviewed =
        raw['verified_at'] != null &&
        resource.verification(now) != 'unverified' &&
        resource.verification(now) != 'withdrawn';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        tx(resource.name, size: 16, weight: 700),
        tx(
          '${cached ? 'LAST KNOWN / CURRENT STATUS UNCONFIRMED · ' : ''}${resource.verification(now).toUpperCase()} · ${resource.state}',
          size: 12,
          weight: 700,
        ),
        if (data['address'] != null) tx(data['address'] as String, size: 12),
        if (resource.kind == 'shelter') ...[
          tx(
            'Capacity ${data['capacity'] ?? 'unknown'} · Occupancy ${data['occupancy'] ?? 'unknown'} · ${resource.capacityCurrent(now) && !cached ? 'recent report' : 'last known / current space unknown'}',
            size: 12,
          ),
          tx(
            'Capacity observed ${data['capacity_observed_at'] ?? 'not supplied'}',
            size: 10,
          ),
          tx('Activated ${data['activated_at'] ?? 'not activated'}', size: 10),
          tx(
            'Wheelchair access: ${data['wheelchair_accessible'] == null
                ? 'unknown'
                : data['wheelchair_accessible'] == true
                ? 'reported available'
                : 'reported unavailable'}',
            size: 12,
          ),
          tx(
            'Services: ${(data['services'] as List? ?? []).join(', ')}',
            size: 12,
          ),
        ],
        if (reviewed) ...[
          if (data['access_constraints'] != null)
            tx('Access constraints: ${data['access_constraints']}', size: 12),
          tx(
            '${cached || resource.verification(now) != 'verified' ? 'Previously reviewed instructions' : 'Reviewed instructions'}: ${data['instructions']}',
            size: 12,
          ),
          for (final contact in (data['contacts'] as List? ?? []))
            SelectableText(
              '${contact['name']}: ${contact['contact']} · Hours: ${contact['hours']}',
              style: TextStyle(fontSize: 12, color: context.colors.text),
            ),
        ] else
          tx(
            'Instructions and contacts are withheld until this revision is verified. No destination is endorsed.',
            size: 12,
          ),
        tx(
          'Source: ${raw['issuer_name']} (${raw['authority_id']}) · ${raw['source']}',
          size: 10,
        ),
        tx(
          'Verified ${raw['verified_at'] ?? 'never'} · Expires ${raw['expires_at'] ?? 'not verified'}',
          size: 10,
        ),
        tx('Areas: ${(raw['area_names'] as List? ?? []).join(', ')}', size: 10),
      ],
    );
  }
}

class PreparednessPanel extends StatelessWidget {
  const PreparednessPanel({super.key});
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context), registry = app.resources;
    final rows = registry.items['preparedness'] ?? [];
    return Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          caption('REVIEWED PREPAREDNESS & CONTACT REFERENCES'),
          if (registry.errors['preparedness'] != null)
            tx(registry.errors['preparedness']!, size: 12),
          if (rows.isEmpty)
            tx(
              'No approved preparedness/contact reference is saved for this installation. No contact is invented.',
              size: 12,
            ),
          for (final row in rows)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: ResourceInstructions(
                resource: row,
                cached:
                    !registry.isCurrent('preparedness') ||
                    app.auth.offlineReader,
              ),
            ),
          TextButton(
            onPressed: registry.busy ? null : () => registry.refresh(),
            child: const Text('Refresh reference content'),
          ),
        ],
      ),
    );
  }
}
