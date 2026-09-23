import '../../core/ui.dart';
import '../../models/community_alert.dart';
import '../../controllers/community_alert_controller.dart';

class CommunityEpisodeSummary extends StatelessWidget {
  const CommunityEpisodeSummary({required this.episode, super.key});
  final CommunityAlert episode;
  @override
  Widget build(BuildContext context) {
    final a = episode;
    return Panel(
      color: a.severity.background,
      border: a.severity.color.withValues(alpha: .65),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          tx(
            '${a.severity.label}${a.isResolved ? ' · Peak tier' : ''}',
            mono: true,
            weight: 700,
            color: a.severity.textColor,
          ),
          tx(a.status.name.toUpperCase(), size: 11, mono: true),
          gap,
          tx(a.stationName, display: true, weight: 600, size: 18),
          tx(a.stationId, size: 11, color: AppColors.muted),
          if (a.area.isNotEmpty)
            tx(a.area, size: 12, color: AppColors.secondary),
          gap,
          tx(
            'Trigger depth: ${a.triggerDepthCm.toStringAsFixed(1)} cm',
            size: 12,
          ),
          tx(
            '${a.isResolved ? 'Recovery depth' : 'Latest depth'}: ${a.latestDepthCm.toStringAsFixed(1)} cm',
            weight: 600,
          ),
          tx('Triggered: ${communityAlertTime(a.triggeredAt)}', size: 11),
          tx(
            'Last transition: ${communityAlertTime(a.lastTransitionAt)}',
            size: 11,
          ),
          if (a.resolvedAt != null)
            tx('Resolved: ${communityAlertTime(a.resolvedAt!)}', size: 11),
          gap,
          tx('AGAPAY sensor alert', size: 11, color: AppColors.secondary),
        ],
      ),
    );
  }
}

class CommunityPagination extends StatelessWidget {
  const CommunityPagination({
    required this.offset,
    required this.total,
    required this.loading,
    required this.onPage,
    super.key,
  });
  final int offset, total;
  final bool loading;
  final ValueChanged<int> onPage;
  @override
  Widget build(BuildContext context) => Column(
    children: [
      tx(
        'Page ${offset ~/ CommunityAlertController.pageSize + 1} · $total records',
        size: 11,
        color: AppColors.muted,
      ),
      Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          TextButton(
            onPressed: loading || offset == 0
                ? null
                : () => onPage(
                    (offset - CommunityAlertController.pageSize).clamp(
                      0,
                      offset,
                    ),
                  ),
            child: const Text('Previous'),
          ),
          TextButton(
            onPressed:
                loading || offset + CommunityAlertController.pageSize >= total
                ? null
                : () => onPage(offset + CommunityAlertController.pageSize),
            child: const Text('Next'),
          ),
        ],
      ),
    ],
  );
}
