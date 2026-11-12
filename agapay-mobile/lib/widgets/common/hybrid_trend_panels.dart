import 'monitoring_status.dart';
import 'dart:math' as math;
import '../../core/ui.dart';
import 'forecast_panel.dart';
import '../../models/prediction.dart';

/// Real elapsed-time coordinates. Unknown or reordered times cannot imply a trend.
List<double>? elapsedFractions(List<DateTime?> times) {
  if (times.isEmpty || times.any((t) => t == null)) return null;
  if (times.length == 1) return const [.5];
  final stamps = times.map((t) => t!.microsecondsSinceEpoch).toList();
  for (var i = 1; i < stamps.length; i++) {
    if (stamps[i] <= stamps[i - 1]) return null;
  }
  final span = stamps.last - stamps.first;
  return stamps.map((t) => (t - stamps.first) / span).toList(growable: false);
}

String chartTime(DateTime? value) =>
    value == null ? 'Time unknown' : value.toUtc().toIso8601String();

String chartAxisTime(DateTime value) {
  final at = value.toUtc().add(const Duration(hours: 8));
  const months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ];
  return '${at.day} ${months[at.month - 1]} · ${_pht(value)}';
}

class StationTrendChart extends StatelessWidget {
  const StationTrendChart({
    required this.values,
    required this.label,
    required this.storageId,
    this.times = const [],
    this.unit = 'cm',
    this.bars = false,
    this.maximumGap = const Duration(minutes: 5),
    super.key,
  });
  final List<double?> values;
  final List<DateTime?> times;
  final String label, unit;

  /// Stable, unique name for this chart's "View timestamped data" panel state.
  /// Without its own PageStorageKey the panel shares the enclosing tab's page-scroll
  /// slot and reads the scroll offset (a double) as its expanded flag.
  final String storageId;
  final bool bars;
  final Duration maximumGap;
  @override
  Widget build(BuildContext context) {
    final positions = times.length == values.length
        ? elapsedFractions(times)
        : null;
    final valid = values.whereType<double>().where((v) => v.isFinite).toList();
    final low = valid.isEmpty
        ? 0.0
        : bars
        ? 0.0
        : math.max(0.0, valid.reduce(math.min) - .5);
    final high = valid.isEmpty
        ? 1.0
        : math.max(low + 1, valid.reduce(math.max) + (bars ? 0 : .5));
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          '$label · $unit · gaps remain unavailable',
          style: TextStyle(fontSize: 14, color: context.colors.secondary),
        ),
        if (positions != null && valid.isNotEmpty) ...[
          SizedBox(
            height: math.max(
              140,
              110 * MediaQuery.textScalerOf(context).scale(1),
            ),
            child: Row(
              children: [
                SizedBox(
                  width:
                      58 *
                      MediaQuery.textScalerOf(context).scale(1).clamp(1, 2),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      for (final v in [high, (high + low) / 2, low])
                        Text(
                          v.toStringAsFixed(1),
                          style: const TextStyle(fontSize: 12),
                        ),
                    ],
                  ),
                ),
                Expanded(
                  child: Semantics(
                    label:
                        'Elapsed measurement time on horizontal axis; $unit on vertical axis. Expand timestamped data for every value.',
                    child: ExcludeSemantics(
                      child: CustomPaint(
                        size: const Size(double.infinity, double.infinity),
                        painter: _TrendPainter(
                          values,
                          positions,
                          times,
                          context.colors.link,
                          context.colors.border,
                          bars,
                          low,
                          high,
                          maximumGap,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: LayoutBuilder(
              builder: (context, box) {
                final large =
                    MediaQuery.textScalerOf(context).scale(12) > 18 ||
                    box.maxWidth < 280;
                final labels = [
                  Text(
                    'Start ${chartAxisTime(times.first!)}',
                    style: const TextStyle(fontSize: 11),
                  ),
                  Text(
                    'End ${chartAxisTime(times.last!)}',
                    textAlign: large ? TextAlign.left : TextAlign.right,
                    style: const TextStyle(fontSize: 11),
                  ),
                ];
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    if (large)
                      ...labels
                    else
                      Row(
                        children: [
                          Expanded(child: labels[0]),
                          const SizedBox(width: 12),
                          Expanded(child: labels[1]),
                        ],
                      ),
                    const Text(
                      'Measurement time · PHT',
                      style: TextStyle(fontSize: 10),
                    ),
                  ],
                );
              },
            ),
          ),
        ] else
          const Text(
            'Chart timing unavailable; use the timestamped data below.',
          ),
        ExpansionTile(
          key: PageStorageKey<String>('trend-data-$storageId'),
          title: const Text('View timestamped data'),
          children: [
            for (var i = 0; i < values.length; i++)
              ListTile(
                title: Text(chartTime(i < times.length ? times[i] : null)),
                subtitle: Text(
                  values[i] == null || !values[i]!.isFinite
                      ? 'Unknown / invalid measurement'
                      : '${values[i]!.toStringAsFixed(1)} $unit · valid value',
                ),
              ),
          ],
        ),
      ],
    );
  }
}

class _TrendPainter extends CustomPainter {
  _TrendPainter(
    this.values,
    this.positions,
    this.times,
    this.color,
    this.grid,
    this.bars,
    this.low,
    this.high,
    this.maximumGap,
  );
  final List<double?> values;
  final List<double> positions;
  final List<DateTime?> times;
  final Color color, grid;
  final bool bars;
  final double low, high;
  final Duration maximumGap;
  @override
  void paint(Canvas canvas, Size size) {
    final line = Paint()
      ..color = grid
      ..strokeWidth = 1;
    for (var i = 0; i < 4; i++) {
      final y = 8 + i * (size.height - 16) / 3;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), line);
    }
    final path = Path();
    var connected = false;
    for (var i = 0; i < values.length; i++) {
      final v = values[i];
      if (v == null || !v.isFinite) {
        connected = false;
        continue;
      }
      if (i > 0 && times[i]!.difference(times[i - 1]!) > maximumGap) {
        connected = false;
      }
      final x = 4 + positions[i] * (size.width - 8),
          y = size.height - 8 - (v - low) / (high - low) * (size.height - 16);
      if (bars) {
        final half = math.min(
          10.0,
          (size.width - 8) / math.max(1, values.length) * .32,
        );
        canvas.drawRect(
          Rect.fromLTRB(x - half, y, x + half, size.height - 8),
          Paint()..color = color,
        );
      } else {
        if (connected) {
          path.lineTo(x, y);
        } else {
          path.moveTo(x, y);
        }
        connected = true;
        canvas.drawCircle(Offset(x, y), 2.5, Paint()..color = color);
      }
    }
    if (!bars) {
      canvas.drawPath(
        path,
        Paint()
          ..color = color
          ..strokeWidth = 2
          ..style = PaintingStyle.stroke,
      );
    }
  }

  @override
  bool shouldRepaint(_TrendPainter old) =>
      old.values != values ||
      old.positions != positions ||
      old.color != color ||
      old.grid != grid ||
      old.bars != bars ||
      old.maximumGap != maximumGap;
}

class WaterDepthTrendPanel extends StatelessWidget {
  const WaterDepthTrendPanel({super.key});
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final station = app.monitoring.primary;
    final values =
        station?.history
            .map((s) => s.sensorQuality == 'valid' ? s.waterDepthCm : null)
            .toList() ??
        <double?>[];
    return Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          caption('WATER DEPTH TREND'),
          const SizedBox(height: 6),
          tx(station?.name ?? 'No station selected', size: 13, weight: 600),
          tx(
            station == null
                ? 'Select a monitoring station on the map.'
                : '${station.id} · Depth measured ${app.monitoring.measurementAgeLabel(station)} · ${app.monitoring.isFresh(station) ? 'Observed' : 'Last known'}',
            size: 10,
            color: context.colors.muted,
          ),
          if (values.whereType<double>().isNotEmpty) ...[
            StationTrendChart(
              values: values,
              times: station!.history
                  .map((sample) => sample.recordedAt)
                  .toList(),
              maximumGap: const Duration(seconds: 30),
              storageId: 'water-depth',
              label:
                  'Recorded water depths in centimeters: ${values.map((v) => v?.toStringAsFixed(1) ?? 'unknown').join(', ')}',
            ),
            tx(
              'Received samples · oldest to latest · cm',
              size: 10,
              color: context.colors.muted,
            ),
          ] else
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 26),
              child: tx(
                'No measured history available.',
                size: 12,
                color: context.colors.muted,
              ),
            ),
        ],
      ),
    );
  }
}

class HybridForecastTrendPanel extends StatelessWidget {
  const HybridForecastTrendPanel({super.key});
  @override
  Widget build(BuildContext context) {
    final forecast = AppScope.of(context).forecasts;
    return ListenableBuilder(
      listenable: forecast,
      builder: (context, _) {
        final data = forecast.data;
        final available = forecast.available && !forecast.preview;
        final resolution =
            (data?.publication['uncertainty']?['display_resolution_cm'] as num?)
                ?.toDouble() ??
            1;
        final status = forecast.error != null
            ? 'Forecast service unavailable'
            : forecast.expired
            ? 'Forecast expired'
            : data == null
            ? 'Checking forecast…'
            : forecastLabels[data.status] ?? 'Forecast unavailable';
        return Panel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Expanded(child: caption('WATER-DEPTH FORECAST')),
                  tx(
                    'ADVISORY ONLY',
                    size: 9,
                    mono: true,
                    color: context.colors.muted,
                  ),
                ],
              ),
              const SizedBox(height: 8),
              tx(status, size: 13, weight: 600, color: context.colors.link),
              const SizedBox(height: 8),
              if (available)
                StationTrendChart(
                  values: data!.points.map((p) => p.waterDepthCm).toList(),
                  times: data.points.map((p) => p.targetAt).toList(),
                  maximumGap: const Duration(minutes: 31),
                  storageId: 'published-forecast',
                  label: 'Published water-depth forecast',
                )
              else
                Container(
                  height: 130,
                  alignment: Alignment.center,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    border: Border.all(color: context.colors.border),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: tx(
                    forecast.error ??
                        data?.reason ??
                        'Waiting for a reviewed forecast product.',
                    size: 11,
                    color: context.colors.muted,
                    align: TextAlign.center,
                  ),
                ),
              gap,
              Row(
                children: [
                  for (var i = 0; i < 3; i++)
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          tx(
                            '+${(i + 1) * 30} minutes',
                            size: 10,
                            color: context.colors.muted,
                          ),
                          tx(
                            available
                                ? '${forecastDepth(data!.points[i].waterDepthCm, resolution)} cm'
                                : '—',
                            size: 14,
                            weight: 700,
                            mono: true,
                            color: context.colors.link,
                          ),
                          if (available)
                            tx(
                              forecastInterval(data!.points[i]),
                              size: 9,
                              color: context.colors.muted,
                            ),
                        ],
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 8),
              tx(
                'Published forecast · separate from observed depth',
                size: 10,
                color: context.colors.muted,
              ),
              ExpansionTile(
                key: PageStorageKey(
                  'published-forecast-source-${data?.stationId}',
                ),
                tilePadding: EdgeInsets.zero,
                title: tx(
                  'Publication source, uncertainty and version',
                  size: 11,
                  color: context.colors.link,
                ),
                children: const [ForecastPanel(detailed: true)],
              ),
            ],
          ),
        );
      },
    );
  }
}

class PrivateHybridForecastTrendPanel extends StatelessWidget {
  const PrivateHybridForecastTrendPanel({super.key});
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    return ListenableBuilder(
      listenable: app.hybrid,
      builder: (context, _) {
        final feed = app.hybrid;
        final values = feed.available ? feed.data!.depths : <double>[];
        final delta = values.isEmpty ? 0.0 : values.last - values.first;
        final trend = delta > .001
            ? 'Rising'
            : delta < -.001
            ? 'Falling'
            : 'Stable';
        final status = feed.expired
            ? 'Forecast expired'
            : feed.error != null
            ? 'Forecast unavailable'
            : feed.available
            ? '$trend · ${delta >= 0 ? '+' : ''}${delta.toStringAsFixed(0)} cm over 90 minutes'
            : feed.loading && feed.data == null
            ? 'Checking forecast…'
            : 'Live inputs unavailable';
        return Panel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Wrap(
                alignment: WrapAlignment.spaceBetween,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  caption('Experimental projection'),
                  const MonitoringStatus(),
                  TextButton(
                    onPressed: feed.loading ? null : feed.refresh,
                    child: const Text('Refresh'),
                  ),
                ],
              ),
              Semantics(
                liveRegion: true,
                child: tx(
                  status,
                  size: 13,
                  weight: 600,
                  color: context.colors.link,
                ),
              ),
              const SizedBox(height: 6),
              if (feed.available) ...[
                tx(
                  'Modeled now: ${values.first.toStringAsFixed(0)} cm',
                  size: 11,
                  color: context.colors.secondary,
                ),
                StationTrendChart(
                  values: values,
                  times: [
                    DateTime.tryParse(feed.data!.json['checked_at'] as String),
                    for (final point in feed.data!.json['points'] as List)
                      DateTime.tryParse(point['target_at'] as String),
                  ],
                  maximumGap: const Duration(minutes: 31),
                  storageId: 'private-forecast',
                  label:
                      'Projected water depths, modeled now and at 30, 60, 90 minutes: ${values.join(', ')} centimeters',
                ),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    for (final t in ['Now', '+30m', '+60m', '+90m'])
                      tx(t, size: 10, color: context.colors.muted),
                  ],
                ),
              ] else
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 18),
                  child: tx(
                    feed.error ??
                        feed.data?.reason ??
                        'Waiting for fresh depth and physical rainfall inputs.',
                    size: 12,
                    color: context.colors.muted,
                  ),
                ),
              gap,
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (var i = 0; i < 3; i++)
                    SizedBox(
                      width: 82,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          tx(
                            '+${(i + 1) * 30} minutes',
                            size: 10,
                            color: context.colors.muted,
                          ),
                          tx(
                            feed.available
                                ? '${values[i + 1].toStringAsFixed(0)} cm'
                                : '—',
                            size: 13,
                            weight: 700,
                            color: context.colors.link,
                          ),
                        ],
                      ),
                    ),
                ],
              ),
              gap,
              tx(
                feed.available
                    ? feed.data!.historical
                          ? 'Historical rainfall context'
                          : (feed.data!.rain ?? {})['data_source'] ==
                                'simulated_rain_gauge'
                          ? 'SYNTHETIC test feed'
                          : 'Live gauge history · experimental'
                    : 'Experimental projection',
                size: 10,
                color: context.colors.secondary,
              ),
              if (feed.available)
                tx(
                  'Updated ${_pht(feed.data!.checkedAt)} PHT',
                  size: 10,
                  color: context.colors.muted,
                ),
              tx(
                'Controlled-basin experiment. Calibration pending; measured thresholds determine alerts.',
                size: 10,
                color: context.colors.muted,
              ),
            ],
          ),
        );
      },
    );
  }
}

class RainfallActivityPanel extends StatelessWidget {
  const RainfallActivityPanel({super.key});
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    return ListenableBuilder(
      listenable: app.hybrid,
      builder: (context, _) {
        final feed = app.hybrid;
        final amount = feed.currentRainMm;
        final hours = feed.rainfallHours;
        final archive =
            !feed.gaugeFresh && feed.available && feed.data!.historical;
        return Panel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Wrap(
                alignment: WrapAlignment.spaceBetween,
                spacing: 12,
                children: [
                  caption('RAINFALL ACTIVITY'),
                  tx(
                    feed.gaugeFresh ? 'Connected' : 'Offline',
                    size: 10,
                    color: feed.gaugeFresh
                        ? context.colors.green
                        : context.colors.muted,
                  ),
                ],
              ),
              const SizedBox(height: 12),
              tx(
                'Received rain this hour',
                size: 11,
                color: context.colors.secondary,
              ),
              tx(
                amount == null ? '—' : '${amount.toStringAsFixed(0)} mm',
                size: 26,
                mono: true,
                weight: 700,
                color: context.colors.link,
              ),
              tx(
                amount == null
                    ? 'Waiting for current physical gauge readings.'
                    : 'Incomplete hour · ${feed.data?.rain?['mm_per_tip'] ?? '—'} mm/tip configured',
                size: 10,
                color: context.colors.muted,
              ),
              tx(
                '${feed.data?.rain?['current_hour_product']?['interval_start'] ?? '—'} to ${feed.data?.rain?['current_hour_product']?['interval_end'] ?? '—'} · ${feed.data?.rain?['data_source'] ?? 'unknown source'} · ${feed.data?.rain?['current_hour_product']?['coverage'] ?? 'coverage unknown'} · calibration ${feed.data?.rain?['calibration_version'] ?? 'unknown'}',
                size: 10,
                color: context.colors.muted,
              ),
              if (hours.whereType<double>().isNotEmpty) ...[
                gap,
                tx(
                  archive
                      ? 'HISTORICAL CONTEXT · archived rainfall'
                      : 'Completed hourly rainfall · mm',
                  size: 10,
                  color: context.colors.secondary,
                ),
                StationTrendChart(
                  values: hours,
                  times: feed.rainfallTimes,
                  unit: 'mm / completed hour',
                  maximumGap: const Duration(hours: 1, seconds: 1),
                  bars: true,
                  storageId: 'rainfall',
                  label:
                      '${archive ? 'Archived' : 'Completed hourly'} rainfall in millimeters. Missing hours remain unknown.',
                ),
                tx(
                  archive
                      ? 'Archived input is not current rain.'
                      : 'Oldest to latest · missing hours remain gaps.',
                  size: 10,
                  color: context.colors.muted,
                ),
              ] else
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 20),
                  child: tx(
                    'No completed rainfall history available.',
                    size: 11,
                    color: context.colors.muted,
                  ),
                ),
            ],
          ),
        );
      },
    );
  }
}

String _pht(DateTime date) {
  final at = date.toUtc().add(const Duration(hours: 8));
  return '${at.hour.toString().padLeft(2, '0')}:${at.minute.toString().padLeft(2, '0')}:${at.second.toString().padLeft(2, '0')}';
}
