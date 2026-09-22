import '../../core/ui.dart';
import '../../models/prediction.dart';

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
          color: const Color(0xff0c1320),
          border: const Color(0x660d1f3c),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Wrap(
                alignment: WrapAlignment.spaceBetween,
                runSpacing: 6,
                children: [
                  caption('FLOOD FORECAST'),
                  tx(
                    forecast.preview ? 'SIMULATED PREVIEW' : 'ADVISORY ONLY',
                    size: 9,
                    mono: true,
                    color: forecast.preview
                        ? const Color(0xfffbbf24)
                        : AppColors.faint,
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: Semantics(
                      liveRegion: true,
                      child: tx(
                        title,
                        size: 12,
                        weight: 600,
                        color: AppColors.secondary,
                      ),
                    ),
                  ),
                  TextButton(
                    onPressed: forecast.loading ? null : forecast.refresh,
                    child: Text(forecast.loading ? 'Checking…' : 'Refresh'),
                  ),
                ],
              ),
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
                            color: AppColors.secondary,
                          ),
                        ),
                        if (forecast.available)
                          SizedBox(
                            width: 72,
                            child: LinearProgressIndicator(
                              value: (data!.points[i].waterDepthCm! / 120)
                                  .clamp(0.0, 1.0),
                              minHeight: 4,
                              color: AppColors.link,
                              backgroundColor: AppColors.border,
                            ),
                          ),
                        const SizedBox(width: 8),
                        tx(
                          forecast.available
                              ? '${data!.points[i].waterDepthCm!.toStringAsFixed(1)} cm'
                              : '—',
                          size: 14,
                          mono: true,
                          weight: 700,
                          color: forecast.available
                              ? AppColors.link
                              : AppColors.muted,
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
                          color: AppColors.background,
                          child: Column(
                            children: [
                              tx(
                                '${(i + 1) * 30} min',
                                size: 10,
                                mono: true,
                                color: AppColors.muted,
                              ),
                              const SizedBox(height: 4),
                              tx(
                                forecast.available
                                    ? data!.points[i].waterDepthCm!
                                          .toStringAsFixed(1)
                                    : '—',
                                size: 18,
                                mono: true,
                                weight: 700,
                                color: forecast.available
                                    ? AppColors.link
                                    : AppColors.muted,
                              ),
                              tx(
                                'cm',
                                size: 9,
                                mono: true,
                                color: AppColors.faint,
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
                      : AppColors.secondary,
                ),
              ],
              if (data != null) ...[
                const SizedBox(height: 10),
                tx(
                  '${forecast.preview ? 'Synthetic input' : 'Latest input'}: ${predictionTime(data.latestInputAt)} · Local time',
                  size: 10,
                  mono: true,
                  color: AppColors.muted,
                ),
                if (forecast.available)
                  tx(
                    'Generated ${predictionTime(data.generatedAt)} · Valid until ${predictionTime(data.validUntil)}',
                    size: 10,
                    mono: true,
                    color: AppColors.muted,
                  ),
                if (data.modelVersion != null)
                  tx(
                    'Model: ${data.modelVersion}',
                    size: 10,
                    mono: true,
                    color: AppColors.muted,
                  ),
              ],
              const SizedBox(height: 10),
              tx(
                'Advisory only. Measured thresholds determine alert levels.',
                size: 10,
                color: AppColors.muted,
              ),
              if (forecast.previewAllowed || forecast.preview) ...[
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
