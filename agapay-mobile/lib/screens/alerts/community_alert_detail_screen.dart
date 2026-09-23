import '../../core/ui.dart';
import '../../models/community_alert.dart';
import '../../navigation/app_routes.dart';
import 'community_alert_widgets.dart';

class CommunityAlertDetailScreen extends StatelessWidget {
  const CommunityAlertDetailScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final controller = app.communityAlerts;
    final resource = controller.detail;
    final detail = resource.data;
    return PageContent(
      children: [
        PageHeading(
          'Sensor alert details',
          'Persistent community episode',
          onBack: app.closeDetails,
        ),
        if (resource.loading) tx('Loading community alerts…'),
        if (resource.error != null) ...[
          tx('Alert service is currently unavailable.'),
          TextButton(
            onPressed: () => controller.openDetail(
              controller.selectedId!,
              offset: controller.transitionOffset,
            ),
            child: const Text('Retry details'),
          ),
        ],
        if (detail != null) ...[
          CommunityEpisodeSummary(episode: detail.episode),
          gap,
          Panel(
            child: tx(
              detail.episode.isResolved
                  ? 'This episode resolved after a valid NORMAL reading. Peak tier describes the past incident, not the current condition. Resolution does not guarantee an area is safe.'
                  : detail.episode.severity == AlertLevel.evacuate
                  ? 'AGAPAY EVACUATE-level sensor alert. High flood risk detected. Prepare to evacuate and follow official local authority instructions. Proceed to a confirmed evacuation site when instructed or when immediate safety requires it.'
                  : 'AGAPAY sensor alert. Monitor updates and follow official local authority instructions. Prepare emergency supplies and for possible evacuation.',
              size: 13,
            ),
          ),
          gap,
          tx(
            'Sensor tiers are not official LGU evacuation orders. Physical/site calibration is pending. Historical device/simulator origin is unknown.',
            size: 11,
            color: AppColors.muted,
          ),
          gap,
          caption('SEVERITY TIMELINE'),
          gap,
          for (final transition in detail.transitions.items) ...[
            Panel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  tx(
                    '${transition.previousSeverity.label} → ${transition.newSeverity.label}',
                    weight: 600,
                    color: transition.newSeverity.textColor,
                  ),
                  tx(
                    '${transition.waterDepthCm.toStringAsFixed(1)} cm · ${communityAlertTime(transition.transitionedAt)}',
                    size: 11,
                  ),
                ],
              ),
            ),
            gap,
          ],
          if (detail.transitions.items.isEmpty)
            tx('No transitions on this page.'),
          CommunityPagination(
            offset: controller.transitionOffset,
            total: detail.transitions.total,
            loading: resource.loading,
            onPage: (offset) =>
                controller.openDetail(detail.episode.id, offset: offset),
          ),
          gap,
          tx(
            'Trigger depth is not peak depth. Latest/recovery depth is the last valid episode reading and may be stale.',
            size: 11,
            color: AppColors.muted,
          ),
          gap,
          tx(
            'UCU Gym is a prototype evacuation destination. Confirm shelter activation and a safe entrance before traveling.',
            size: 12,
          ),
          gap,
          ActionButton(
            'VIEW EVACUATION MAP',
            onPressed: () {
              app.navigate(AppTab.map, evacuation: true);
              if (ModalRoute.of(context)?.settings.name ==
                  AppRoutes.notificationHistory) {
                Navigator.of(context).pop();
              }
            },
          ),
        ],
      ],
    );
  }
}
