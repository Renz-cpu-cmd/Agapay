import '../../core/ui.dart';
import '../alerts/delivery_evidence_screen.dart';
import '../../core/release_configuration.dart';
import '../../widgets/common/monitoring_status.dart';
import '../../widgets/common/resident_decisions.dart';
import '../../widgets/common/official_notices.dart';
import '../exercises/exercise_screen.dart';
import '../../models/monitoring.dart';
import '../../widgets/common/hybrid_trend_panels.dart';
import '../../widgets/common/water_level_gauge.dart';
import '../../widgets/common/water_depth_dial.dart';
import '../../widgets/common/unverified_station_banner.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final station = app.monitoring.primary;
    final view = app.monitoring.primaryView;
    // A8: coverage, calibration and origin of the rain-gauge figure, from API metadata.
    final rain = view?.station.rainPresentation;
    final usingMonitoring = station != null && view?.depth.value != null;
    final fresh = view?.depth.fresh == true;
    final level = usingMonitoring
        ? station.observationLevel
        : AlertLevel.unknown;
    // R4: an unreviewed/ineligible station's tier is shown as a measurement, never
    // as an operational instruction (fail-closed on missing review fields).
    final unverified = usingMonitoring && !station.operationallyVerified;
    final waterDepth = view?.depth.value;
    final sourceLabel = view == null || waterDepth == null
        ? 'NO VALID READING'
        : view.sourceStatus.contains('UNVERIFIED')
        ? 'UNVERIFIED SOURCE'
        : view.sourceStatus.contains('REVIEW')
        ? 'REVIEW REQUIRED'
        : station?.sourceClass == 'simulator'
        ? 'EXERCISE'
        : fresh
        ? 'OBSERVED'
        : 'LAST KNOWN';
    final sourceColor = fresh ? context.colors.green : context.colors.muted;
    final trend = !fresh
        ? '— UNKNOWN TREND'
        : switch (station?.trend) {
            'rising_rapidly' => '↑ RAPIDLY RISING',
            'rising' => '↗ RISING',
            'falling' => '↘ FALLING',
            'stable' => '→ STABLE',
            _ => '— UNKNOWN TREND',
          };
    final riseRate = station?.riseRate;
    final rateText = !fresh
        ? 'Rate — · Current measurement unconfirmed'
        : riseRate == null
        ? 'Rate — · ${station?.trendReason ?? 'Insufficient timing coverage'}'
        : '${riseRate.toStringAsFixed(3)} cm/min · range ${station?.riseRateLower?.toStringAsFixed(3) ?? 'unknown'} to ${station?.riseRateUpper?.toStringAsFixed(3) ?? 'unknown'} · ${station?.trendReason ?? 'Coverage unconfirmed'}';
    return PageContent(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
      children: [
        const _OriginalHomeHeader(),
        gap,
        if (unverified) ...[const UnverifiedStationBanner(), gap],
        Panel(
          color: level.background,
          border: level.color.withValues(alpha: .65),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Wrap(
                spacing: 8,
                runSpacing: 4,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Dot(level.color, size: 10, glow: true),
                  tx(
                    fresh
                        ? level == AlertLevel.unknown
                              ? 'Observed · tier unavailable'
                              : 'Observed · ${level.label}'
                        : waterDepth == null
                        ? 'UNKNOWN'
                        : 'Last known · ${level.label}',
                    size: 12,
                    mono: true,
                    weight: 700,
                    color: level.color,
                    spacing: 1.2,
                  ),
                ],
              ),
              const SizedBox(height: 8),
              tx(
                fresh
                    ? level == AlertLevel.unknown
                          ? 'Observed water depth'
                          : unverified
                          ? 'Observed water depth · unverified station'
                          : level.description
                    : waterDepth == null
                    ? 'No valid reading'
                    : 'Last known water depth',
                display: true,
                size: 18,
                weight: 600,
                color: Colors.white,
                height: 1.375,
              ),
              const SizedBox(height: 4),
              tx(
                fresh
                    ? level == AlertLevel.unknown
                          ? 'Observation tier unavailable. Check station details and official advisories.'
                          : unverified
                          ? 'Not an operational warning or all-clear. Follow official local authority advisories.'
                          : level.action
                    : 'Current conditions are unconfirmed. Check area advisories.',
                size: 12,
                color: level.textColor,
              ),
              gap,
              InkWell(
                onTap: () => app.showAlert(),
                child: Wrap(
                  crossAxisAlignment: WrapCrossAlignment.center,
                  spacing: 6,
                  runSpacing: 4,
                  children: [
                    tx(
                      'VIEW ALERT DETAILS',
                      size: 12,
                      display: true,
                      weight: 600,
                      color: level.textColor,
                      spacing: .3,
                    ),
                    SvgIcon('arrow', size: 12, color: level.textColor),
                  ],
                ),
              ),
            ],
          ),
        ),
        gap,
        if (app.notices.current.items.isNotEmpty) ...[
          const OfficialNoticesPanel(compact: true),
          gap,
        ],
        Panel(
          padding: 0,
          radius: 10,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            child: Wrap(
              alignment: WrapAlignment.spaceBetween,
              spacing: 8,
              runSpacing: 4,
              children: [
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Dot(sourceColor),
                    const SizedBox(width: 8),
                    Flexible(
                      child: tx(
                        sourceLabel,
                        size: 11,
                        mono: true,
                        weight: 700,
                        color: sourceColor,
                      ),
                    ),
                  ],
                ),
                tx(
                  station == null
                      ? 'Waiting for a valid observation'
                      : 'Depth measured ${app.monitoring.measurementAgeLabel(station)} · ${station.id}',
                  size: 10,
                  mono: true,
                  color: context.colors.muted,
                ),
              ],
            ),
          ),
        ),
        gap,
        Panel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              caption('WATER DEPTH'),
              const SizedBox(height: 4),
              LayoutBuilder(
                builder: (context, constraints) {
                  final dialSize =
                      144 * MediaQuery.textScalerOf(context).scale(1);
                  final stacked = constraints.maxWidth < 108 + dialSize;
                  final gauge = Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: WaterLevelGauge(
                      waterDepth,
                      height: 152,
                      advisory: station?.thresholdAdvisoryCm,
                      warning: station?.thresholdWarningCm,
                      critical: station?.thresholdEvacuateCm,
                      maximum: (station?.thresholdEvacuateCm ?? 100) * 1.2,
                    ),
                  );
                  final dial = SizedBox(
                    width: dialSize.clamp(0, constraints.maxWidth),
                    child: WaterDepthDial(
                      depth: waterDepth,
                      trend: trend,
                      level: level,
                    ),
                  );
                  return stacked
                      ? Column(
                          children: [dial, const SizedBox(height: 12), gauge],
                        )
                      : Row(
                          crossAxisAlignment: CrossAxisAlignment.center,
                          children: [
                            gauge,
                            const SizedBox(width: 4),
                            Expanded(child: Center(child: dial)),
                          ],
                        );
                },
              ),
              const SizedBox(height: 8),
              tx(rateText, size: 11, mono: true, color: context.colors.muted),
              const SizedBox(height: 12),
              _DepthThresholdBar(
                depth: waterDepth,
                station: station,
                level: level,
              ),
            ],
          ),
        ),
        gap,
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          spacing: 12,
          children: [
            Expanded(
              child: Panel(
                padding: 12,
                radius: 12,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      spacing: 7,
                      children: [
                        Icon(
                          Icons.water_drop_outlined,
                          size: 17,
                          color: context.colors.link,
                        ),
                        Expanded(child: caption(rain?.title ?? 'RAINFALL')),
                      ],
                    ),
                    if (rain?.badge != null) ...[
                      const SizedBox(height: 6),
                      Container(
                        key: const ValueKey('rain-badge'),
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          border: Border.all(color: context.colors.muted),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: tx(rain!.badge!, size: 10, weight: 700, color: context.colors.muted),
                      ),
                    ],
                    const SizedBox(height: 8),
                    tx(
                      view?.rain.value == null
                          ? '— mm'
                          : '${view!.rain.value!.toStringAsFixed(1)} mm',
                      size: 20,
                      weight: 700,
                      mono: true,
                      color: const Color(0xff93c5fd),
                    ),
                    if (rain != null && !rain.calibrated && view?.rain.value != null)
                      tx('rainfall-equivalent', size: 10, color: context.colors.muted),
                    tx(
                      usingMonitoring
                          ? view?.rain.fresh == true
                                ? [rain?.tips, rain?.coverage]
                                      .whereType<String>()
                                      .join(' · ')
                                : 'Last known / missing interval · ${rain?.coverage ?? 'Coverage unknown'}'
                          : 'No valid rainfall interval',
                      size: 10,
                      mono: true,
                      color: context.colors.muted,
                    ),
                    if (usingMonitoring && rain != null && !rain.calibrated)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: KeyedSubtree(
                          key: const ValueKey('rain-caveat'),
                          child: tx(rain.caveat, size: 10, color: context.colors.muted),
                        ),
                      ),
                  ],
                ),
              ),
            ),
            Expanded(
              child: Panel(
                padding: 12,
                radius: 12,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      spacing: 7,
                      children: [
                        Icon(
                          Icons.sensors_rounded,
                          size: 17,
                          color: context.colors.link,
                        ),
                        Expanded(child: caption('STATION')),
                      ],
                    ),
                    const SizedBox(height: 8),
                    FittedBox(
                      fit: BoxFit.scaleDown,
                      child: tx(
                        station?.id ?? '—',
                        size: 14,
                        weight: 700,
                        mono: true,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Wrap(
                      spacing: 6,
                      runSpacing: 4,
                      children: [
                        Dot(
                          view?.heartbeat.fresh == true
                              ? context.colors.green
                              : context.colors.muted,
                          size: 6,
                        ),
                        tx(
                          view?.heartbeat.fresh == true
                              ? 'ONLINE'
                              : (view?.heartbeat.status.toUpperCase() ??
                                    'NO HEARTBEAT'),
                          size: 10,
                          mono: true,
                          color: view?.heartbeat.fresh == true
                              ? context.colors.green
                              : context.colors.muted,
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
        gap,
        tx(
          'Device heartbeat: ${view?.heartbeat.status ?? 'unknown'} · Sensor: ${view?.depth.quality ?? 'unknown'} · Episode: ${station?.activeHazardTier ?? 'None recorded'}',
          size: 10,
          color: context.colors.muted,
        ),
        if (view?.hazardState == 'unresolved')
          tx(
            'Sensor episode unresolved · ${station?.activeHazardTier ?? 'review pending'} · current conditions unconfirmed',
            size: 10,
            color: context.colors.red,
          ),
        gap,
        const WaterDepthTrendPanel(),
        gap,
        const HybridForecastTrendPanel(),
        gap,
        const RainfallActivityPanel(),
        gap,
        Row(
          spacing: 12,
          children: [
            Expanded(
              child: ActionButton(
                'EVACUATION MAP',
                fontSize: 12,
                vertical: 14,
                color: const Color(0xff0d1f3c),
                border: context.colors.blue.withValues(alpha: .25),
                textColor: context.colors.link,
                onPressed: () => app.navigate(AppTab.map, evacuation: true),
              ),
            ),
            Expanded(
              child: ActionButton(
                'VIEW HISTORY',
                fontSize: 12,
                vertical: 14,
                color: context.colors.surface,
                border: context.colors.border,
                textColor: context.colors.secondary,
                onPressed: () => _showTelemetryHistory(context, station),
              ),
            ),
          ],
        ),
        gap,
        ExpansionTile(
          key: PageStorageKey('home-source-${app.user?.id}-${station?.id}'),
          title: const Text('Measurement source and station details'),
          children: const [MonitoringStatus()],
        ),
        ExpansionTile(
          key: PageStorageKey('home-resources-${app.user?.id}'),
          title: const Text('Area advisories and verified contacts'),
          children: [
            const ResidentAreaPanel(),
            const OfficialNoticesPanel(compact: true),
            TextButton(
              onPressed: () => showModalBottomSheet<void>(
                context: context,
                isScrollControlled: true,
                showDragHandle: true,
                builder: (_) => SafeArea(
                  child: SizedBox(
                    height: MediaQuery.sizeOf(context).height * .8,
                    child: const SingleChildScrollView(
                      padding: EdgeInsets.all(16),
                      child: ResidentHelpPanel(inSheet: true),
                    ),
                  ),
                ),
              ),
              child: const Text('Verified contacts'),
            ),
          ],
        ),
        if (ReleaseConfiguration.exercisesAvailable)
          TextButton(
            onPressed: () => Navigator.of(context).push<void>(
              MaterialPageRoute(builder: (_) => const ExerciseScreen()),
            ),
            child: const Text('OPEN TEST WORKSPACE'),
          ),
      ],
    );
  }
}

class _OriginalHomeHeader extends StatelessWidget {
  const _OriginalHomeHeader();
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const AgapayLogo(size: 32),
                  const SizedBox(width: 9),
                  Expanded(
                    child: tx(
                      'AGAPAY',
                      display: true,
                      weight: 700,
                      size: 23,
                      spacing: -.45,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 2),
              InkWell(
                key: const ValueKey('home-area-selector'),
                onTap: () => showModalBottomSheet<void>(
                  context: context,
                  isScrollControlled: true,
                  showDragHandle: true,
                  builder: (_) => const SafeArea(
                    child: SingleChildScrollView(
                      padding: EdgeInsets.all(16),
                      child: ResidentAreaPanel(),
                    ),
                  ),
                ),
                child: Row(
                  children: [
                    Icon(
                      Icons.location_on,
                      size: 12,
                      color: context.colors.muted,
                    ),
                    const SizedBox(width: 6),
                    Expanded(
                      child: tx(
                        app.preferences.residentAreaName ??
                            app.preferences.residentAreaId ??
                            '${app.user?.barangay ?? 'Your area'} · select area',
                        size: 11,
                        color: context.colors.muted,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: 8),
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (final action in [(AppTab.alerts, 'bell', 'Notifications')])
              Padding(
                padding: const EdgeInsets.only(left: 8),
                child: Semantics(
                  label: action.$3,
                  button: true,
                  child: InkWell(
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute<void>(
                        builder: (_) => const DeliveryEvidenceScreen(),
                      ),
                    ),
                    borderRadius: BorderRadius.circular(12),
                    child: Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: context.colors.surface,
                        border: Border.all(color: context.colors.border),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Center(child: SvgIcon(action.$2, size: 20)),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ],
    );
  }
}

class _DepthThresholdBar extends StatelessWidget {
  const _DepthThresholdBar({
    required this.depth,
    required this.station,
    required this.level,
  });
  final double? depth;
  final MonitoringStation? station;
  final AlertLevel level;
  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, box) {
      final maximum = (station?.thresholdEvacuateCm ?? 100) * 1.2;
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          tx('Threshold', size: 10, mono: true, color: context.colors.muted),
          const SizedBox(height: 6),
          Stack(
            clipBehavior: Clip.none,
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: LinearProgressIndicator(
                  value: depth == null ? 0 : (depth! / maximum).clamp(0.0, 1.0),
                  minHeight: 6,
                  color: context.colors.resolve(level.color),
                  backgroundColor: context.colors.border,
                ),
              ),
              for (final threshold in [
                station?.thresholdAdvisoryCm,
                station?.thresholdWarningCm,
                station?.thresholdEvacuateCm,
              ].whereType<double>())
                Positioned(
                  left: (threshold / maximum).clamp(0, 1) * (box.maxWidth - 2),
                  top: -3,
                  child: Container(
                    width: 2,
                    height: 12,
                    color: context.colors.background,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 6),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              for (final tier in AlertLevel.values.where(
                (v) => v != AlertLevel.unknown,
              ))
                tx(tier.label[0], size: 8, mono: true, color: tier.textColor),
            ],
          ),
        ],
      );
    },
  );
}

void _showTelemetryHistory(BuildContext context, MonitoringStation? station) {
  if (station == null || station.history.isEmpty) {
    previewNotice(context, 'No station telemetry has been received yet.');
    return;
  }
  showModalBottomSheet<void>(
    context: context,
    backgroundColor: context.colors.background,
    showDragHandle: true,
    isScrollControlled: true,
    builder: (context) => SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            tx(
              'Recent telemetry · ${station.id}',
              display: true,
              size: 18,
              weight: 700,
              color: Colors.white,
            ),
            const SizedBox(height: 4),
            tx(
              station.isSimulator
                  ? 'Virtual station readings'
                  : 'Monitoring station readings',
              size: 11,
              mono: true,
              color: context.colors.muted,
            ),
            gap,
            ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 420),
              child: SingleChildScrollView(
                child: Column(
                  children: [
                    for (final sample in station.history.reversed.take(12))
                      DataRow(
                        '${sample.recordedAt.hour.toString().padLeft(2, '0')}:${sample.recordedAt.minute.toString().padLeft(2, '0')}:${sample.recordedAt.second.toString().padLeft(2, '0')}',
                        sample.sensorQuality == 'valid' &&
                                sample.waterDepthCm != null
                            ? '${sample.waterDepthCm!.toStringAsFixed(1)} cm · ${sample.rainfallMm?.toStringAsFixed(1) ?? '—'} mm rain'
                            : 'INVALID SENSOR READING',
                        mono: true,
                      ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    ),
  );
}
