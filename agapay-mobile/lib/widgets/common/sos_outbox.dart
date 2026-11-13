import '../../core/ui.dart';
import '../../models/sos_request.dart';

class SosOutboxPanel extends StatefulWidget {
  const SosOutboxPanel({super.key});
  @override
  State<SosOutboxPanel> createState() => _SosOutboxPanelState();
}

class _SosOutboxPanelState extends State<SosOutboxPanel> {
  String? _error;
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context), sos = app.sos;
    return ListenableBuilder(
      listenable: sos,
      builder: (context, _) {
        final draft = sos.pending;
        if (draft == null && sos.lastSent == null) {
          return const SizedBox.shrink();
        }
        const labels = {
          'queued': 'QUEUED ON DEVICE · NOT SENT',
          'unknown': 'RECEIPT UNCONFIRMED',
          'rejected': 'REJECTED · NOT RECEIVED',
          'conflict': 'CONFLICT · MANUAL REVIEW REQUIRED',
        };
        return Panel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              caption('SOS OUTBOX & RECEIPT'),
              if (sos.lastSent != null)
                tx(
                  'Last confirmed server receipt: SOS-${sos.lastSent!.id} · ${sos.lastSent!.requestId}. Receipt does not mean dispatch; current response status may be unavailable.',
                  size: 11,
                ),
              if (draft != null) ...[
                tx(
                  labels[sos.pendingState] ?? 'RECEIPT UNCONFIRMED',
                  weight: 800,
                  size: 13,
                ),
                SelectableText(
                  'Reference: ${draft['request_id'] ?? 'unavailable'}',
                  style: const TextStyle(fontSize: 11),
                ),
                tx(
                  'Saved ${sos.queuedAt == null ? 'time unknown' : '${sosTime(sos.queuedAt!)} · local time'} · Last attempt ${sos.lastAttemptAt == null ? 'never' : '${sosTime(sos.lastAttemptAt!)} · local time'}',
                  size: 10,
                ),
                tx('Location: ${draft['location'] ?? 'unavailable'}', size: 12),
                tx('Message: ${draft['message'] ?? ''}', size: 12),
                tx(
                  'Coordinates: ${draft['latitude'] ?? 'not supplied'}, ${draft['longitude'] ?? 'not supplied'} · Capture: ${draft['location_recorded_at'] ?? 'manual'}',
                  size: 10,
                ),
                if (sos.pendingState == 'conflict')
                  tx(
                    'Keep this reference. Review the received history with an app operator before trying again.',
                    size: 12,
                  ),
                Wrap(
                  spacing: 8,
                  children: [
                    TextButton(
                      onPressed:
                          sos.loading ||
                              sos.sending ||
                              sos.clearing ||
                              app.auth.offlineReader
                          ? null
                          : () => sos.refresh(),
                      child: const Text(
                        'Check whether this request was received',
                      ),
                    ),
                    if (['queued', 'unknown'].contains(sos.pendingState))
                      TextButton(
                        onPressed:
                            sos.sending ||
                                sos.clearing ||
                                app.auth.offlineReader
                            ? null
                            : () => sos.send(draft),
                        child: Text(
                          sos.pendingState == 'queued'
                              ? 'Send saved test request'
                              : 'Retry this saved request',
                        ),
                      ),
                    if (['queued', 'rejected'].contains(sos.pendingState))
                      TextButton(
                        onPressed: sos.sending || sos.clearing || sos.loading
                            ? null
                            : () async {
                                try {
                                  await sos.discardUnsent();
                                } catch (_) {
                                  if (mounted) {
                                    setState(
                                      () => _error =
                                          'The saved draft could not be removed. It has not been replaced.',
                                    );
                                  }
                                }
                              },
                        child: const Text('Discard unsent draft'),
                      ),
                  ],
                ),
              ],
              if (_error != null)
                tx(_error!, size: 12, color: context.colors.red),
            ],
          ),
        );
      },
    );
  }
}
