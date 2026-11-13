import 'dart:async';
import '../../core/ui.dart';

class DeliveryEvidenceScreen extends StatefulWidget {
  const DeliveryEvidenceScreen({super.key});
  @override
  State<DeliveryEvidenceScreen> createState() => _DeliveryEvidenceScreenState();
}

class _DeliveryEvidenceScreenState extends State<DeliveryEvidenceScreen> {
  int? _owner;
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final app = AppScope.of(context);
    if (_owner != app.user?.id) {
      _owner = app.user?.id;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) unawaited(app.deliveries.refresh());
      });
    }
  }

  String time(dynamic value) => value is String
      ? (DateTime.tryParse(value)?.toLocal().toString() ?? 'Unknown time')
      : 'Unknown time';
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context), feed = app.deliveries;
    return Scaffold(
      appBar: AppBar(title: const Text('Push delivery evidence')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const Text(
              'This is your notification delivery history. Provider acceptance does not confirm phone display. Missing receipt/open evidence stays unknown. Acknowledgement does not confirm evacuation or rescue.',
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Optional app receipt and open evidence'),
              subtitle: Text(
                app.notificationRegistration.capabilitySupported
                    ? 'Records callback stages for requested sensor notifications. No location is included. Off by default. Withdrawal stops new callbacks; previously recorded evidence remains.'
                    : 'Push callbacks are unavailable on this build. Existing evidence remains readable.',
              ),
              value: feed.consent?['enabled'] == true,
              onChanged:
                  feed.consent != null &&
                      !feed.saving &&
                      !feed.conflicted &&
                      !app.auth.offlineReader &&
                      app.notificationRegistration.capabilitySupported
                  ? (value) => unawaited(feed.changeConsent(value))
                  : null,
            ),
            Text(
              'App receipt callbacks awaiting submission: ${feed.receipts.pending}',
            ),
            if (feed.receipts.warning != null) Text(feed.receipts.warning!),
            if (feed.error != null) Text(feed.error!),
            if (feed.conflicted)
              const Text(
                'Evidence changed. Refresh and review before another action. No automatic acknowledgement retry occurred.',
              ),
            TextButton(
              onPressed: feed.loading ? null : () => unawaited(feed.refresh()),
              child: Text(
                feed.loading
                    ? 'Loading evidence…'
                    : 'Refresh and review evidence',
              ),
            ),
            if (!feed.loading && feed.items.isEmpty)
              const Text(
                'No delivery records loaded. This does not establish receipt or phone display.',
              ),
            ...feed.items.map((item) {
              final stages = (item['receipt_stages'] as List? ?? [])
                  .whereType<Map>()
                  .toList();
              return Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        'Delivery #${item['id']} · ${item['station_id']} · ${item['severity']}',
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                      Text('Queued: ${time(item['queued_at'])}'),
                      Text('Transport: ${item['state']}'),
                      Text(
                        'Provider accepted: ${item['provider_accepted'] == true ? 'reported by provider' : 'unconfirmed'}',
                      ),
                      if (item['operator_attested_acceptance'] == true)
                        const Text(
                          'Acceptance was attested by an operator; transport history is retained.',
                        ),
                      Text(
                        'Expiry: ${time(item['expires_at'])}${item['expired'] == true ? ' · expired' : ''}',
                      ),
                      for (final stage in [
                        'RECEIVED',
                        'OPENED',
                        'ACKNOWLEDGED',
                      ])
                        Text(
                          '$stage: ${stages.any((row) => row['stage'] == stage) ? stages.where((row) => row['stage'] == stage).map((row) => '${time(row['recorded_at'])} (${row['basis']})').join(', ') : 'unknown / not instrumented'}',
                        ),
                      if (item['can_acknowledge'] == true)
                        TextButton(
                          onPressed:
                              feed.saving ||
                                  feed.conflicted ||
                                  app.auth.offlineReader
                              ? null
                              : () => unawaited(
                                  feed.acknowledge(
                                    item['id'] as int,
                                    item['version'] as int,
                                  ),
                                ),
                          child: const Text('I have read this notification'),
                        ),
                    ],
                  ),
                ),
              );
            }),
            if (feed.nextBefore != null)
              TextButton(
                onPressed: feed.loading
                    ? null
                    : () => unawaited(feed.refresh(before: feed.nextBefore)),
                child: const Text('Older delivery records'),
              ),
          ],
        ),
      ),
    );
  }
}
