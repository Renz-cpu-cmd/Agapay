import '../../core/ui.dart';
import '../../models/monitoring.dart';
import '../../widgets/common/forecast_panel.dart';
import '../../widgets/common/water_level_gauge.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final station = app.monitoring.primary;
    final activeStation = station?.hasValidReading == true ? station : null;
    final usingMonitoring = activeStation != null;
    final level = activeStation?.alertLevel ?? app.alert;
    final waterDepth = activeStation?.currentDepthCm ?? level.water;
    final sourceLabel = activeStation != null
        ? activeStation.isSimulator
              ? 'VIRTUAL STATION'
              : 'LIVE'
        : station == null
        ? 'DEMO'
        : 'WAITING FOR DATA';
    final sourceColor = activeStation?.isOnline == true
        ? AppColors.green
        : usingMonitoring
        ? const Color(0xfffbbf24)
        : AppColors.muted;
    final trend = activeStation != null
        ? switch (activeStation.trend) {
            'rising_rapidly' => '↑ RAPIDLY RISING',
            'rising' => '↗ RISING',
            'falling' => '↘ FALLING',
            _ => '→ STABLE',
          }
        : level.trend;
    return PageContent(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  spacing: 9,
                  children: [
                    const AgapayLogo(size: 32),
                    tx(
                      'AGAPAY',
                      display: true,
                      weight: 700,
                      size: 23,
                      color: Colors.white,
                      spacing: -.45,
                    ),
                  ],
                ),
                const SizedBox(height: 2),
                Row(
                  spacing: 6,
                  children: [
                    const Icon(
                      Icons.location_on,
                      size: 12,
                      color: AppColors.muted,
                    ),
                    tx(
                      'San Vicente, Urdaneta',
                      size: 11,
                      color: AppColors.muted,
                    ),
                  ],
                ),
              ],
            ),
            Row(
              spacing: 8,
              children: [
                Semantics(
                  label: 'Notifications',
                  button: true,
                  child: InkWell(
                    onTap: () => app.navigate(AppTab.alerts),
                    borderRadius: BorderRadius.circular(12),
                    child: Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        color: AppColors.surface,
                        border: Border.all(color: AppColors.border),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Stack(
                        clipBehavior: Clip.none,
                        alignment: Alignment.center,
                        children: [const SvgIcon('bell', size: 20)],
                      ),
                    ),
                  ),
                ),
                Semantics(
                  label: 'Profile',
                  button: true,
                  child: InkWell(
                    onTap: () => app.navigate(AppTab.profile),
                    child: Container(
                      width: 40,
                      height: 40,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(12),
                        color: AppColors.surface,
                        border: Border.all(color: AppColors.border),
                      ),
                      child: const Center(child: SvgIcon('user', size: 18)),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
        gap,
        Panel(
          color: level.background,
          border: level.color.withValues(alpha: .65),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                spacing: 8,
                children: [
                  Dot(level.color, size: 10, glow: true),
                  tx(
                    level.label,
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
                level.description,
                display: true,
                size: 18,
                weight: 600,
                color: Colors.white,
                height: 1.375,
              ),
              const SizedBox(height: 4),
              tx(level.action, size: 12, color: level.textColor),
              gap,
              InkWell(
                onTap: () => app.showAlert(),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  spacing: 6,
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
        Panel(
          padding: 0,
          radius: 10,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  spacing: 8,
                  children: [
                    Dot(sourceColor, glow: usingMonitoring),
                    tx(
                      sourceLabel,
                      size: 11,
                      mono: true,
                      weight: 700,
                      color: sourceColor,
                    ),
                  ],
                ),
                Flexible(
                  child: tx(
                    usingMonitoring
                        ? '${activeStation.ageSeconds ?? 0}s ago · ${activeStation.id}'
                        : station == null
                        ? 'Connecting to AGAPAY · STATION_001'
                        : 'Start the virtual station · ${station.id}',
                    size: 10,
                    mono: true,
                    color: AppColors.muted,
                    align: TextAlign.right,
                  ),
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
              caption('WATER LEVEL'),
              const SizedBox(height: 4),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: WaterLevelGauge(waterDepth),
                  ),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.only(top: 16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          FittedBox(
                            fit: BoxFit.scaleDown,
                            child: tx(
                              waterDepth.toStringAsFixed(1),
                              size: 56,
                              weight: 700,
                              mono: true,
                              color: level.color,
                              height: 1,
                            ),
                          ),
                          tx(
                            'cm',
                            display: true,
                            size: 18,
                            weight: 600,
                            color: AppColors.secondary,
                          ),
                          const SizedBox(height: 16),
                          FittedBox(
                            fit: BoxFit.scaleDown,
                            child: tx(
                              trend,
                              size: 20,
                              weight: 700,
                              mono: true,
                              color: level.textColor,
                            ),
                          ),
                          tx(
                            usingMonitoring
                                ? activeStation.sensorQuality == 'valid'
                                      ? 'Backend-classified trend'
                                      : 'Latest sample invalid'
                                : level.rate,
                            size: 11,
                            mono: true,
                            color: AppColors.muted,
                          ),
                          const SizedBox(height: 16),
                          tx(
                            'Threshold',
                            size: 10,
                            mono: true,
                            color: AppColors.muted,
                          ),
                          const SizedBox(height: 4),
                          SizedBox(
                            width: 128,
                            child: Column(
                              children: [
                                Stack(
                                  clipBehavior: Clip.none,
                                  children: [
                                    ClipRRect(
                                      borderRadius: BorderRadius.circular(8),
                                      child: LinearProgressIndicator(
                                        value: (waterDepth / 120)
                                            .clamp(0.0, 1.0)
                                            .toDouble(),
                                        minHeight: 6,
                                        color: level.color,
                                        backgroundColor: AppColors.border,
                                      ),
                                    ),
                                    for (final t in [60, 85, 100])
                                      Positioned(
                                        left: t / 120 * 128,
                                        top: -3,
                                        child: Container(
                                          width: 2,
                                          height: 12,
                                          color: AppColors.background,
                                        ),
                                      ),
                                  ],
                                ),
                                const SizedBox(height: 4),
                                Row(
                                  mainAxisAlignment:
                                      MainAxisAlignment.spaceBetween,
                                  children: [
                                    for (final l in AlertLevel.values)
                                      tx(
                                        l.label[0],
                                        size: 8,
                                        mono: true,
                                        color: l.textColor,
                                      ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
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
                        const Icon(
                          Icons.water_drop_outlined,
                          size: 17,
                          color: AppColors.link,
                        ),
                        caption('RAINFALL'),
                      ],
                    ),
                    const SizedBox(height: 8),
                    tx(
                      usingMonitoring
                          ? '${(activeStation.latestRainfallMm ?? 0).toStringAsFixed(1)} mm'
                          : level.rainfall,
                      size: 20,
                      weight: 700,
                      mono: true,
                      color: const Color(0xff93c5fd),
                    ),
                    tx(
                      usingMonitoring
                          ? 'Latest reporting interval'
                          : 'Demonstration rainfall',
                      size: 10,
                      mono: true,
                      color: AppColors.muted,
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
                        const Icon(
                          Icons.sensors_rounded,
                          size: 17,
                          color: AppColors.link,
                        ),
                        caption('STATION'),
                      ],
                    ),
                    const SizedBox(height: 8),
                    FittedBox(
                      fit: BoxFit.scaleDown,
                      child: tx(
                        station?.id ?? 'STATION_001',
                        size: 14,
                        weight: 700,
                        mono: true,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      spacing: 6,
                      children: [
                        Dot(
                          station?.isOnline == true
                              ? AppColors.green
                              : AppColors.muted,
                          size: 6,
                        ),
                        tx(
                          station?.isOnline == true ? 'ONLINE' : 'OFFLINE',
                          size: 10,
                          mono: true,
                          color: station?.isOnline == true
                              ? AppColors.green
                              : AppColors.muted,
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
        const ForecastPanel(),
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
                border: AppColors.blue.withValues(alpha: .25),
                textColor: AppColors.link,
                onPressed: () => app.navigate(AppTab.map, evacuation: true),
              ),
            ),
            Expanded(
              child: ActionButton(
                'VIEW HISTORY',
                fontSize: 12,
                vertical: 14,
                color: AppColors.surface,
                border: AppColors.border,
                textColor: AppColors.secondary,
                onPressed: () => _showTelemetryHistory(context, station),
              ),
            ),
          ],
        ),
        gap,
        if (!usingMonitoring)
          Panel(
            color: const Color(0xff080e1a),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                tx(
                  'DEMO MODE · SIMULATE WATER LEVEL',
                  size: 10,
                  mono: true,
                  weight: 600,
                  spacing: 1,
                  color: AppColors.faint,
                ),
                gap,
                Row(
                  spacing: 8,
                  children: [
                    for (final l in AlertLevel.values)
                      Expanded(
                        child: Semantics(
                          button: true,
                          selected: level == l,
                          child: InkWell(
                            onTap: () => app.setAlert(l),
                            child: Container(
                              padding: const EdgeInsets.symmetric(vertical: 8),
                              decoration: BoxDecoration(
                                color: level == l
                                    ? l.color
                                    : Colors.transparent,
                                border: Border.all(
                                  color: l.color.withValues(alpha: .38),
                                ),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: FittedBox(
                                fit: BoxFit.scaleDown,
                                child: tx(
                                  l.label,
                                  size: 9,
                                  weight: 700,
                                  mono: true,
                                  color: level == l ? Colors.white : l.color,
                                  spacing: .2,
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
                const SizedBox(height: 8),
                Wrap(
                  alignment: WrapAlignment.spaceBetween,
                  children: [
                    tx(
                      'Simulated: ${level.water} cm',
                      size: 9,
                      mono: true,
                      color: AppColors.faint,
                    ),
                    tx(
                      'For thesis defense use',
                      size: 9,
                      mono: true,
                      color: AppColors.faint,
                    ),
                  ],
                ),
              ],
            ),
          ),
      ],
    );
  }
}

void _showTelemetryHistory(BuildContext context, MonitoringStation? station) {
  if (station == null || station.history.isEmpty) {
    previewNotice(context, 'No station telemetry has been received yet.');
    return;
  }
  showModalBottomSheet<void>(
    context: context,
    backgroundColor: AppColors.background,
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
              color: AppColors.muted,
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
                            ? '${sample.waterDepthCm!.toStringAsFixed(1)} cm · ${sample.rainfallMm.toStringAsFixed(1)} mm rain'
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
