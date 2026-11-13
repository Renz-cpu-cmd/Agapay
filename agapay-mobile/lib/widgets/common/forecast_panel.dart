import 'monitoring_status.dart';
import '../../core/ui.dart';
import '../../models/prediction.dart';
import '../../screens/forecast_record_screen.dart';

class ForecastPanel extends StatelessWidget {
  const ForecastPanel({super.key, this.detailed = false});
  final bool detailed;

  @override
  Widget build(BuildContext context) {
    final forecast = AppScope.of(context).forecasts;
    return ListenableBuilder(
      listenable: forecast,
      builder: (context, _) {
        final data = forecast.data;
        final title = forecast.error != null
            ? 'Service unavailable'
            : forecast.expired
            ? 'Forecast expired'
            : data == null
            ? 'Checking forecast…'
            : forecastLabels[data.status]!;
        final reason =
            forecast.error ??
            (forecast.expired
                ? 'The forecast has expired. Refresh to check availability.'
                : data?.reason);
        return Panel(
          padding: 14,
          radius: 14,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const MonitoringStatus(),
              Wrap(
                alignment: WrapAlignment.spaceBetween,
                runSpacing: 6,
                children: [
                  caption('FLOOD FORECAST'),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 3,
                    ),
                    decoration: BoxDecoration(
                      color: context.colors.background,
                      border: Border.all(color: context.colors.border),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: tx(
                      forecast.preview ? 'PREVIEW' : 'ADVISORY ONLY',
                      size: 9,
                      mono: true,
                      color: forecast.preview
                          ? const Color(0xfffbbf24)
                          : context.colors.label,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Row(
                children: [
                  Expanded(
                    child: Semantics(
                      liveRegion: true,
                      child: tx(
                        title,
                        size: 12,
                        weight: 600,
                        color: context.colors.label,
                      ),
                    ),
                  ),
                  TextButton(
                    onPressed: forecast.loading ? null : forecast.refresh,
                    child: Text(forecast.loading ? 'Checking…' : 'Refresh'),
                  ),
                ],
              ),
              if (forecast.available && !forecast.preview) ...[
                for (final point in data!.points)
                  Text(
                    '+${point.horizonMinutes} min interval: ${forecastInterval(point)}',
                  ),
                const Text(
                  'Local-depth interval. Coverage can fail under drift; not flood probability.',
                ),
              ],
              if (detailed) ...[
                for (var i = 0; i < 3; i++)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Row(
                      children: [
                        Expanded(
                          child: tx(
                            '+${(i + 1) * 30} min',
                            size: 12,
                            mono: true,
                            color: context.colors.secondary,
                          ),
                        ),
                        if (forecast.available)
                          SizedBox(
                            width: 72,
                            child: LinearProgressIndicator(
                              value: (data!.points[i].waterDepthCm! / 120)
                                  .clamp(0.0, 1.0),
                              minHeight: 4,
                              color: context.colors.link,
                              backgroundColor: context.colors.border,
                            ),
                          ),
                        const SizedBox(width: 8),
                        tx(
                          forecast.available
                              ? '${forecastDepth(data!.points[i].waterDepthCm, (data.publication['uncertainty']?['display_resolution_cm'] as num?)?.toDouble() ?? 1)} cm'
                              : '—',
                          size: 14,
                          mono: true,
                          weight: 700,
                          color: forecast.available
                              ? context.colors.link
                              : context.colors.muted,
                        ),
                      ],
                    ),
                  ),
              ] else
                Row(
                  spacing: 8,
                  children: [
                    for (var i = 0; i < 3; i++)
                      Expanded(
                        child: Panel(
                          padding: 8,
                          radius: 12,
                          color: context.colors.background,
                          child: Column(
                            children: [
                              tx(
                                '${(i + 1) * 30} min',
                                size: 10,
                                mono: true,
                                color: context.colors.muted,
                              ),
                              const SizedBox(height: 2),
                              tx(
                                forecast.available
                                    ? forecast.preview
                                          ? data!.points[i].waterDepthCm!
                                                .toStringAsFixed(1)
                                          : forecastDepth(
                                              data!.points[i].waterDepthCm,
                                              (data.publication['uncertainty']?['display_resolution_cm']
                                                          as num?)
                                                      ?.toDouble() ??
                                                  1,
                                            )
                                    : '—',
                                size: 20,
                                mono: true,
                                weight: 700,
                                color: forecast.available
                                    ? context.colors.link
                                    : context.colors.muted,
                              ),
                              tx(
                                'cm',
                                size: 9,
                                mono: true,
                                color: context.colors.secondary,
                              ),
                            ],
                          ),
                        ),
                      ),
                  ],
                ),
              if (reason != null) ...[
                const SizedBox(height: 12),
                tx(
                  reason,
                  size: 11,
                  height: 1.5,
                  color: forecast.error != null
                      ? const Color(0xfff87171)
                      : context.colors.secondary,
                ),
              ],
              if (data != null) ...[
                const SizedBox(height: 10),
                tx(
                  '${forecast.preview ? 'Preview input' : 'Latest input'}: ${predictionTime(data.latestInputAt)} · Local time',
                  size: 10,
                  mono: true,
                  color: context.colors.muted,
                ),
                if (forecast.available)
                  tx(
                    'Generated ${predictionTime(data.generatedAt)} · Valid until ${predictionTime(data.validUntil)}',
                    size: 10,
                    mono: true,
                    color: context.colors.muted,
                  ),
                if (data.modelVersion != null)
                  tx(
                    'Model: ${data.modelVersion}',
                    size: 10,
                    mono: true,
                    color: context.colors.muted,
                  ),
                if (data.publication['forecast_id'] != null) ...[
                  TextButton(
                    onPressed: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => ForecastRecordScreen(
                          id: data.publication['forecast_id'] as String,
                        ),
                      ),
                    ),
                    child: tx(
                      'Forecast ID: ${data.publication['forecast_id']} · binding ${data.publication['deployment_version']}',
                      size: 10,
                      mono: true,
                      color: context.colors.muted,
                    ),
                  ),
                  tx(
                    'Datum: ${data.publication['reference_datum']} · cutoff ${data.publication['data_cutoff']}',
                    size: 10,
                    color: context.colors.muted,
                  ),
                ],
              ],
              const SizedBox(height: 10),
              tx(
                'Advisory only. Measured thresholds determine alert levels.',
                size: 10,
                color: context.colors.muted,
              ),
              if (forecast.preview) ...[
                const SizedBox(height: 8),
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton(
                    onPressed: () => forecast.setPreview(!forecast.preview),
                    child: Text(
                      forecast.preview
                          ? 'Return to actual status'
                          : 'Preview sample scenarios',
                      style: const TextStyle(fontSize: 12),
                    ),
                  ),
                ),
                if (forecast.preview)
                  DropdownButtonFormField<String>(
                    key: ValueKey('forecast-${forecast.scenario}'),
                    initialValue: forecast.scenario,
                    isExpanded: true,
                    decoration: const InputDecoration(
                      labelText: 'Forecast preview scenario',
                    ),
                    items: forecastLabels.entries
                        .map(
                          (e) => DropdownMenuItem(
                            value: e.key,
                            child: Text(
                              e.value,
                              style: const TextStyle(fontSize: 12),
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: (value) {
                      if (value != null) {
                        forecast.setPreview(true, scenario: value);
                      }
                    },
                  ),
              ],
            ],
          ),
        );
      },
    );
  }
}
