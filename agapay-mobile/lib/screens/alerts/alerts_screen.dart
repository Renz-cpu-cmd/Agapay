import 'dart:async';
import '../../core/ui.dart';
import 'community_alert_widgets.dart';

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({this.initialHistory = false, super.key});
  final bool initialHistory;
  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  late bool _history = widget.initialHistory;
  bool _started = false;
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_started && widget.initialHistory) {
      _started = true;
      final controller = AppScope.of(context).communityAlerts;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) unawaited(controller.refreshHistory(offset: 0));
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final controller = app.communityAlerts;
    final resource = _history ? controller.history : controller.active;
    final page = resource.data;
    return PageContent(
      children: [
        const PageHeading('Notifications', 'AGAPAY community sensor episodes'),
        tx(
          'In-app alert feed · Push delivery and read receipts are not connected.',
          size: 11,
          color: AppColors.muted,
        ),
        gap,
        Row(
          children: [
            Expanded(
              child: TextButton(
                onPressed: () => setState(() => _history = false),
                child: Text(_history ? 'Active' : 'Active •'),
              ),
            ),
            Expanded(
              child: TextButton(
                onPressed: () {
                  setState(() => _history = true);
                  unawaited(controller.refreshHistory(offset: 0));
                },
                child: Text(_history ? 'History •' : 'History'),
              ),
            ),
            TextButton(
              onPressed: resource.loading
                  ? null
                  : () => _history
                        ? controller.refreshHistory()
                        : controller.refreshActive(),
              child: const Text('Refresh'),
            ),
          ],
        ),
        if (!_history && page != null)
          tx('${page.total} active sensor alerts', size: 12, weight: 600),
        if (_history)
          tx(
            'History includes active and resolved episodes. Resolved severity is the peak tier.',
            size: 11,
            color: AppColors.muted,
          ),
        gap,
        if (resource.loading) tx('Loading community alerts…'),
        if (resource.error != null) ...[
          Panel(child: tx('Alert service is currently unavailable.')),
          gap,
          tx(
            'Current alert state cannot be confirmed. Refresh to retry; no offline copy is shown.',
            size: 12,
            color: AppColors.muted,
          ),
        ],
        if (page != null) ...[
          if (page.items.isEmpty)
            tx(
              page.total == 0
                  ? (_history
                        ? 'No alert history available.'
                        : 'No active AGAPAY sensor alerts.')
                  : 'No alerts on this page. Return to the previous page or refresh.',
            ),
          for (final episode in page.items) ...[
            Semantics(
              button: true,
              label: 'Open sensor alert for ${episode.stationName}',
              child: InkWell(
                key: ValueKey('community-alert-${episode.id}'),
                onTap: () => app.showCommunityAlert(episode.id),
                borderRadius: BorderRadius.circular(16),
                child: CommunityEpisodeSummary(episode: episode),
              ),
            ),
            gap,
          ],
          CommunityPagination(
            offset: _history
                ? controller.historyOffset
                : controller.activeOffset,
            total: page.total,
            loading: resource.loading,
            onPage: (offset) => _history
                ? controller.refreshHistory(offset: offset)
                : controller.refreshActive(offset: offset),
          ),
        ],
        gap,
        tx(
          'Times shown in Philippine time (PHT). Device/simulator origin is not recorded for these episodes. Last valid depths may be stale; invalid readings do not resolve alerts.',
          size: 11,
          color: AppColors.muted,
        ),
      ],
    );
  }
}
