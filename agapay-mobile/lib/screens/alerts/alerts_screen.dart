import '../../widgets/common/unverified_station_banner.dart';
import 'dart:async';
import 'delivery_evidence_screen.dart';
import '../../core/ui.dart';
import '../../widgets/common/official_notices.dart';
import '../../widgets/common/resident_decisions.dart';
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
        const PageHeading('Alerts', 'Community Alert History'),
        if (app.notices.current.items.isNotEmpty)
          const OfficialNoticesPanel()
        else
          ExpansionTile(
            // Own PageStorage identity: unkeyed, it shares the Alerts page-scroll slot.
            key: const PageStorageKey('alerts-area-advisories'),
            title: const Text('Advisories for your area'),
            children: const [ResidentAreaPanel(), OfficialNoticesPanel()],
          ),
        gap,
        Semantics(
          header: true,
          child: tx('Station sensor episodes', size: 20, weight: 700),
        ),
        tx(
          'Recorded sensor episodes · separate from authority advisories',
          size: 10,
          color: context.colors.muted,
        ),
        gap,
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            SelectionButton(
              'Active episodes',
              selected: !_history,
              onPressed: () => setState(() => _history = false),
            ),
            SelectionButton(
              'Episode history',
              selected: _history,
              onPressed: () {
                setState(() => _history = true);
                unawaited(controller.refreshHistory(offset: 0));
              },
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
        if (showStationVerificationNotices && page != null && page.items.any((e) => !e.isOperational))
          tx(
            'Includes unverified station records — these are not operational warnings.',
            size: 11,
            weight: 600,
            color: context.colors.secondary,
          ),
        if (_history)
          tx(
            'History includes active and resolved episodes. Resolved severity is the peak tier.',
            size: 11,
            color: context.colors.muted,
          ),
        gap,
        if (resource.loading) tx('Loading community alerts…'),
        if (resource.error != null) ...[
          Panel(child: tx('Alert service is currently unavailable.')),
          gap,
          tx(
            'Current alert state cannot be confirmed. Refresh to retry; no offline copy is shown.',
            size: 12,
            color: context.colors.muted,
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
                child: CommunityEpisodeSummary(episode: episode, compact: true),
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
          'Times shown in Philippine time (PHT). Ingress origin is not recorded for these episodes. Last valid depths may be stale; invalid readings do not resolve alerts.',
          size: 11,
          color: context.colors.muted,
        ),
        ExpansionTile(
          key: const PageStorageKey('alerts-delivery-evidence'),
          title: const Text('Notification receipt and acknowledgement'),
          subtitle: const Text(
            'Delivery evidence is separate from authority instructions',
          ),
          children: [
            const Text(
              'Opening an advisory does not confirm that help is on the way. Acknowledgement is available only for supported push delivery records.',
            ),
            TextButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => const DeliveryEvidenceScreen(),
                ),
              ),
              child: const Text('Push delivery evidence'),
            ),
          ],
        ),
      ],
    );
  }
}
