import '../../core/ui.dart';

/// Shown only to a resident account that an administrator has assigned to carry a
/// portable station. Reporting runs while the app is open and this phone has a GPS fix.
class StationTrackingPanel extends StatelessWidget {
  const StationTrackingPanel({super.key});

  @override
  Widget build(BuildContext context) {
    final tracking = AppScope.of(context).tracking;
    return ListenableBuilder(
      listenable: tracking,
      builder: (context, _) {
        final active = tracking.active;
        final sessions = tracking.sessions;
        if (active == null && sessions.isEmpty) return const SizedBox.shrink();
        final session = active ?? sessions.first;
        final colors = context.colors;
        return Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Panel(
            key: const Key('station-tracking-panel'),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              spacing: 8,
              children: [
                Row(
                  spacing: 8,
                  children: [
                    Icon(
                      active == null ? Icons.location_off_outlined : Icons.my_location,
                      size: 18,
                      color: active == null ? colors.muted : colors.link,
                    ),
                    Expanded(child: caption('STATION TRACKING')),
                    if (tracking.sending)
                      const SizedBox(
                        width: 12,
                        height: 12,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                  ],
                ),
                tx(session.stationName, size: 15, weight: 600),
                tx(
                  active == null
                      ? 'You are assigned to carry this station. Start tracking to share '
                            "this phone's GPS position with AGAPAY staff while the app is open."
                      : 'Sharing this phone’s GPS position with AGAPAY staff every '
                            '${tracking.interval.inSeconds} s. Keep the app open and the phone with the station.',
                  size: 12,
                  color: colors.muted,
                ),
                if (active != null)
                  tx(
                    [
                      '${tracking.accepted} sent',
                      if (tracking.rejected > 0) '${tracking.rejected} skipped',
                      if (tracking.lastAccuracyM != null)
                        '±${tracking.lastAccuracyM!.round()} m',
                    ].join(' · '),
                    size: 12,
                    mono: true,
                  ),
                if (tracking.message case final message? when message.isNotEmpty)
                  tx(message, size: 12, color: colors.muted),
                ActionButton(
                  active == null ? 'START TRACKING' : 'STOP TRACKING',
                  vertical: 12,
                  onPressed: active == null
                      ? () => tracking.start(session)
                      : () => tracking.stop(),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
