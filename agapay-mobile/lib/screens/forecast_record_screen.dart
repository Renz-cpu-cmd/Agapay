import 'dart:async';
import '../core/ui.dart';
import '../models/prediction.dart';

class ForecastRecordScreen extends StatefulWidget {
  const ForecastRecordScreen({required this.id, super.key});
  final String id;
  @override
  State<ForecastRecordScreen> createState() => _ForecastRecordScreenState();
}

class _ForecastRecordScreenState extends State<ForecastRecordScreen> {
  int? owner;
  int generation = 0;
  Prediction? data;
  bool current = false;
  String? error;
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final app = AppScope.of(context);
    if (owner != app.user?.id) {
      owner = app.user?.id;
      data = null;
      ++generation;
      if (owner != null) unawaited(load());
    }
  }

  Future<void> load() async {
    final app = AppScope.of(context);
    final ticket = ++generation;
    try {
      final raw = await app.auth.request('forecasts/${widget.id}') as Map;
      final product = Prediction.fromPublishedJson(
        (raw['product'] as Map).cast<String, dynamic>(),
      );
      if (product.publication['forecast_id'] != widget.id) {
        throw const FormatException('Wrong forecast record');
      }
      if (mounted && ticket == generation) {
        setState(() {
          data = product;
          current =
              raw['current'] == true &&
              product.validUntil!.isAfter(
                DateTime.parse(raw['read_at'] as String),
              );
          error = null;
        });
      }
    } catch (_) {
      if (mounted && ticket == generation) {
        setState(() {
          data = null;
          error =
              'Forecast record unavailable. No current forecast is inferred.';
        });
      }
    }
  }

  @override
  void dispose() {
    ++generation;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final product = data;
    return Scaffold(
      appBar: AppBar(title: const Text('Published forecast record')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'This immutable record is separate from current measurements, alerts and authority-issued instructions.',
          ),
          if (error != null) Text(error!),
          if (product != null) ...[
            Text(
              current
                  ? 'Within original validity at read time'
                  : 'Historical, expired or withdrawn — do not use as a current forecast',
            ),
            Text(
              'Forecast ${product.publication['forecast_id']} · ${product.stationId}',
            ),
            Text(
              'Generated ${product.generatedAt} · expires ${product.validUntil}',
            ),
            Text('Input cutoff ${product.publication['data_cutoff']}'),
            Text(
              'Local sensor depth · cm · datum ${product.publication['reference_datum']}',
            ),
            Text(
              'Model ${product.modelVersion} · binding ${product.publication['deployment_version']}',
            ),
            Text('Configuration ${product.publication['configuration_hash']}'),
            Text(
              'Source ${product.publication['ingress_identity']} · registry ${product.publication['registry_version']}',
            ),
            for (final point in product.points)
              Text(
                '+${point.horizonMinutes} min · ${point.targetAt?.toUtc()} · ${forecastDepth(point.waterDepthCm, (product.publication['uncertainty']?['display_resolution_cm'] as num?)?.toDouble() ?? 1)} cm · ${forecastInterval(point)}',
              ),
            const Text(
              'Original published values; opening this record never extends its expiry.',
            ),
          ],
          TextButton(
            onPressed: () => unawaited(load()),
            child: const Text('Reload record'),
          ),
        ],
      ),
    );
  }
}
