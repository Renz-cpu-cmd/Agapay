import '../../widgets/common/monitoring_status.dart';
import '../../core/ui.dart';
import '../../widgets/common/hybrid_trend_panels.dart';
import 'community_alert_detail_screen.dart';
import '../../widgets/common/unverified_station_banner.dart';
import '../exercises/exercise_test_alert_screen.dart';

class AlertDetailsScreen extends StatelessWidget {
  const AlertDetailsScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    if (app.exerciseAlert != null) return const ExerciseTestAlertScreen();
    if (app.communityAlerts.selectedId != null) {
      return const CommunityAlertDetailScreen();
    }
    final station = app.monitoring.primary;
    final view = app.monitoring.primaryView;
    final fresh = view?.depth.fresh == true;
    final level = view?.depth.value != null
        ? station!.observationLevel
        : AlertLevel.unknown;
    final episodeLevel =
        AlertLevel.values
            .where(
              (tier) => tier.name.toUpperCase() == station?.activeHazardTier,
            )
            .firstOrNull ??
        AlertLevel.unknown;
    final waterDepth = view?.depth.value;
    final observed = view?.depth.measuredAt?.toUtc().add(
      const Duration(hours: 8),
    );
    // R4: fail closed for unreviewed or ineligible stations.
    final unverified =
        station != null && view?.depth.value != null && !station.operationallyVerified;
    final guidance = !fresh
        ? 'Current conditions are unconfirmed. Check official advisories and recorded sensor episodes.'
        : level == AlertLevel.unknown
        ? 'Observation tier unavailable. Check station details and official advisories.'
        : episodeLevel != AlertLevel.unknown && episodeLevel.index > level.index
        ? 'The recorded ${episodeLevel.label} sensor episode remains unresolved. Check official advisories and the incident history.'
        : unverified
        ? 'Unverified station measurement. Not an operational warning, evacuation instruction or all-clear. Follow official local authority advisories.'
        : level.action;
    final observedTime = observed == null
        ? 'No valid measurement time'
        : '${observed.hour.toString().padLeft(2, '0')}:${observed.minute.toString().padLeft(2, '0')} PHT · ${app.monitoring.measurementAgeLabel(station!)} · ${fresh ? 'Observed' : 'Last known'}';
    return PageContent(
      children: [
        PageHeading(
          'Sensor episode',
          station?.name ?? app.user?.barangay ?? 'No station selected',
          onBack: app.closeDetails,
        ),
        Panel(
          padding: 20,
          color: level.background,
          border: level.color.withValues(alpha: .25),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 4,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Dot(episodeLevel.color, size: 12, glow: true),
                  tx(
                    'Sensor episode: ${station?.activeHazardTier ?? "None recorded"}',
                    size: 14,
                    weight: 700,
                    mono: true,
                    color: episodeLevel.color,
                    spacing: 1.4,
                  ),
                ],
              ),
              tx(
                'Observation tier: ${fresh ? level.label : 'UNKNOWN'} · ${fresh
                    ? 'Observed'
                    : waterDepth == null
                    ? 'No valid reading'
                    : 'Last known'}',
                size: 11,
                color: context.colors.secondary,
              ),
              gap,
              LayoutBuilder(
                builder: (context, box) {
                  final stacked =
                      MediaQuery.textScalerOf(context).scale(14) > 20 ||
                      box.maxWidth < 260;
                  final reading = Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      FittedBox(
                        fit: BoxFit.scaleDown,
                        alignment: Alignment.centerLeft,
                        child: tx(
                          waterDepth?.toStringAsFixed(1) ?? '—',
                          size: 48,
                          mono: true,
                          weight: 700,
                          color: level == AlertLevel.unknown
                              ? context.colors.muted
                              : level.color,
                          height: 1,
                        ),
                      ),
                      tx(
                        'cm',
                        size: 16,
                        display: true,
                        weight: 600,
                        color: context.colors.secondary,
                      ),
                    ],
                  );
                  final facts = Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      tx(
                        !fresh && waterDepth != null
                            ? 'Retained valid depth'
                            : waterDepth == null || station?.trend == 'unknown'
                            ? '— Unknown trend'
                            : station!.trend.replaceAll('_', ' '),
                        size: 14,
                        mono: true,
                        weight: 700,
                        color: level == AlertLevel.unknown
                            ? context.colors.muted
                            : level.textColor,
                      ),
                      tx(
                        observedTime,
                        size: 11,
                        mono: true,
                        color: context.colors.muted,
                      ),
                      if (station != null)
                        tx(
                          view!.sourceLabel,
                          size: 10,
                          color: context.colors.muted,
                        ),
                      if (station?.activeHazardTier != null && !fresh)
                        tx(
                          'Hazard unresolved',
                          size: 11,
                          color: context.colors.red,
                        ),
                    ],
                  );
                  return stacked
                      ? Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [reading, gap, facts],
                        )
                      : Row(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            SizedBox(width: box.maxWidth * .43, child: reading),
                            const SizedBox(width: 12),
                            Expanded(child: facts),
                          ],
                        );
                },
              ),
              gap,
              tx(
                guidance,
                display: true,
                weight: 500,
                color: context.colors.text,
              ),
            ],
          ),
        ),
        gap,
        // Below the reading so large-text layouts keep the measurement above the fold;
        // the panel's own guidance line already states the unverified meaning.
        if (unverified) ...[const UnverifiedStationBanner(compact: true), gap],
        const ExpansionTile(
          key: PageStorageKey('sensor-detail-source'),
          title: Text('Source and measurement details'),
          children: [MonitoringStatus()],
        ),
        gap,
        tx(
          station == null ||
                  !app.monitoring.isFresh(station) ||
                  station.riseRate == null
              ? 'Rate — · ${station?.trendReason ?? "No valid timing/coverage"}'
              : '${station.riseRate!.toStringAsFixed(3)} cm/min · range ${station.riseRateLower?.toStringAsFixed(3)} to ${station.riseRateUpper?.toStringAsFixed(3)} · ${station.trendReason}',
          size: 11,
          color: context.colors.muted,
        ),
        const SizedBox(height: 16),
        Row(
          spacing: 12,
          children: [
            Expanded(
              child: _Stat(
                'Received rain this hour',
                station == null ||
                        !app.monitoring.isRainFresh(station) ||
                        station.latestRainfallMm == null
                    ? '—'
                    : '${station.latestRainfallMm!.toStringAsFixed(1)} mm',
                station == null
                    ? 'Independent rainfall unavailable'
                    : station.rainfallNote,
              ),
            ),
            Expanded(
              child: _Stat(
                'Station ID',
                station?.id ?? '—',
                station == null
                    ? 'No station selected'
                    : 'Heartbeat: ${view?.heartbeat.status ?? 'unknown'} · ${station.sensorQuality ?? 'No data'}',
                small: true,
              ),
            ),
          ],
        ),
        gap,
        Row(
          spacing: 12,
          children: [
            Expanded(
              child: _Stat(
                'Sensor Quality',
                station?.sensorQuality == 'valid'
                    ? '✓ Valid'
                    : station?.sensorQuality == 'invalid'
                    ? 'Invalid'
                    : 'Unknown',
                station == null
                    ? 'No sample received'
                    : station.firmwareVersion ?? 'Firmware unavailable',
                color: station?.sensorQuality == 'valid'
                    ? context.colors.green
                    : context.colors.muted,
              ),
            ),
            Expanded(
              child: _Stat(
                'Last valid depth time',
                observed == null
                    ? '—'
                    : '${observed.hour.toString().padLeft(2, '0')}:${observed.minute.toString().padLeft(2, '0')}:${observed.second.toString().padLeft(2, '0')}',
                observed == null
                    ? 'No valid reading'
                    : 'Depth measurement time · PHT',
                small: true,
              ),
            ),
          ],
        ),
        gap,
        const HybridForecastTrendPanel(),
        gap,
        Panel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              caption('RECOMMENDED ACTION'),
              const SizedBox(height: 8),
              tx(guidance, display: true, weight: 500, height: 1.625),
            ],
          ),
        ),
        const SizedBox(height: 16),
        ActionButton(
          'NAVIGATE TO SHELTER',
          glow: true,
          endColor: const Color(0xff2563eb),
          onPressed: () => app.navigate(AppTab.map, evacuation: true),
        ),
        if (level != AlertLevel.normal && level != AlertLevel.unknown) ...[
          gap,
          ActionButton(
            '🔴  SEND EMERGENCY SOS',
            color: const Color(0xff7f1d1d),
            border: context.colors.red.withValues(alpha: .38),
            onPressed: () => app.navigate(AppTab.sos),
          ),
        ],
      ],
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat(
    this.label,
    this.value,
    this.sub, {
    this.small = false,
    this.color = AppColors.text,
  });
  final String label, value, sub;
  final bool small;
  final Color color;
  @override
  Widget build(BuildContext context) => Panel(
    padding: 12,
    radius: 12,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        caption(label),
        const SizedBox(height: 8),
        FittedBox(
          fit: BoxFit.scaleDown,
          child: tx(
            value,
            size: small ? 13 : 18,
            mono: true,
            weight: 700,
            color: color,
          ),
        ),
        const SizedBox(height: 2),
        tx(sub, size: 10, mono: true, color: context.colors.muted),
      ],
    ),
  );
}
