import '../../core/ui.dart';
import '../../models/community_alert.dart';
import '../../controllers/community_alert_controller.dart';
import '../../widgets/common/unverified_station_banner.dart';

class CommunityEpisodeSummary extends StatelessWidget {
  const CommunityEpisodeSummary({
    required this.episode,
    this.compact = false,
    super.key,
  });
  final CommunityAlert episode;
  final bool compact;
  @override
  Widget build(BuildContext context) {
    final a = episode;
    // R4: an unverified incident stays visible as a diagnostic record but never
    // borrows the operational severity styling or wording.
    final verified = a.isOperational || !showStationVerificationNotices;
    final tierColor = verified ? a.severity.textColor : context.colors.secondary;
    final tier = verified
        ? '${a.severity.label}${a.isResolved ? ' · Peak tier' : ''}'
        : 'Recorded ${a.severity.label} reading${a.isResolved ? ' · Peak tier' : ''}';
    final footer = verified
        ? null
        : 'Unverified station record · not an operational warning';
    return Panel(
      color: verified ? a.severity.background : AppColors.surface,
      border: verified
          ? a.severity.color.withValues(alpha: .65)
          : AlertLevel.warning.color.withValues(alpha: .65),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!verified) ...[
            UnverifiedStationBanner(compact: compact),
            const SizedBox(height: 10),
          ],
          if (compact) ...[
            Wrap(
              spacing: 12,
              runSpacing: 4,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Icon(Icons.circle, size: 8, color: tierColor),
                tx(
                  tier,
                  size: 12,
                  weight: 700,
                  color: tierColor,
                ),
                tx(
                  a.status.name.toUpperCase(),
                  size: 11,
                  color: tierColor,
                ),
                tx(
                  communityAlertTime(a.lastTransitionAt),
                  size: 11,
                  color: context.colors.secondary,
                ),
              ],
            ),
            const SizedBox(height: 8),
            tx(a.stationName, display: true, weight: 600, size: 16),
            if (a.area.isNotEmpty)
              tx(a.area, size: 12, color: context.colors.secondary),
            const SizedBox(height: 4),
            if (a.isResolved)
              tx(
                'Trigger depth: ${a.triggerDepthCm.toStringAsFixed(1)} cm',
                size: 12,
              ),
            tx(
              '${a.isResolved ? 'Recovery depth' : 'Latest depth'}: ${a.latestDepthCm.toStringAsFixed(1)} cm',
              size: 13,
              weight: 600,
            ),
            tx(
              footer == null
                  ? 'AGAPAY sensor alert · View history and details'
                  : '$footer · View history and details',
              size: 11,
              color: context.colors.secondary,
            ),
          ] else ...[
            tx(
              tier,
              mono: true,
              weight: 700,
              color: tierColor,
            ),
            tx(a.status.name.toUpperCase(), size: 11, mono: true),
            gap,
            tx(a.stationName, display: true, weight: 600, size: 18),
            tx(a.stationId, size: 11, color: context.colors.muted),
            if (a.area.isNotEmpty)
              tx(a.area, size: 12, color: context.colors.secondary),
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
            tx(
              footer ?? 'AGAPAY sensor alert',
              size: 11,
              color: context.colors.secondary,
            ),
          ],
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
        color: context.colors.muted,
      ),
      Wrap(
        alignment: WrapAlignment.spaceBetween,
        spacing: 12,
        runSpacing: 8,
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
