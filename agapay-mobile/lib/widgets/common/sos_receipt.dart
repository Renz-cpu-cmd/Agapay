import '../../core/ui.dart';
import '../../models/sos_request.dart';
import '../../controllers/monitoring_controller.dart';

String sosLocationAge(DateTime? value) {
  if (value == null) return 'Capture time unknown';
  if (value.isAfter(DateTime.now())) {
    return 'Capture time unconfirmed · device clock ahead';
  }
  return MonitoringController.ageLabel(
    DateTime.now().difference(value).inSeconds,
  );
}

class SosReceiptCard extends StatelessWidget {
  const SosReceiptCard({required this.item, this.onOpen, super.key});
  final SosRequest item;
  final VoidCallback? onOpen;
  @override
  Widget build(BuildContext context) {
    final sos = AppScope.of(context).sos;
    final current =
        !sos.fromCache &&
        sos.error == null &&
        sos.syncedAt != null &&
        !DateTime.now().isBefore(sos.syncedAt!) &&
        DateTime.now().difference(sos.syncedAt!).inSeconds <= 30;
    return Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Semantics(
            header: true,
            child: tx('Did my request reach AGAPAY?', size: 20, weight: 700),
          ),
          tx('REQUEST RECEIVED', weight: 800, color: context.colors.link),
          const Text(
            'Server receipt confirmed. This does not confirm that a person has reviewed it or that a responder was sent.',
          ),
          SelectableText('Request reference: ${item.requestId}'),
          Text(
            'Server record: SOS-${item.id} · Received ${sosTime(item.createdAt)}',
          ),
          Text(
            '${current ? 'Last checked status' : 'LAST KNOWN STATUS · current response unconfirmed'}: ${item.status}',
          ),
          if (item.acknowledgedAt != null)
            Text(
              'Review recorded: ${item.acknowledgedBy ?? 'Staff identity unavailable'} · ${sosTime(item.acknowledgedAt!)}',
            ),
          if (onOpen != null)
            TextButton(
              onPressed: onOpen,
              child: const Text('View ownership and action timeline'),
            ),
        ],
      ),
    );
  }
}
