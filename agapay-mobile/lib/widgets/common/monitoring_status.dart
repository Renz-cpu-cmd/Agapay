import '../../core/ui.dart';
import '../../controllers/monitoring_controller.dart';
import '../../core/operational_states.dart';
import '../../core/operational_vocabulary.dart';
import '../../models/monitoring.dart';

String stationStatusDescription(StationFreshnessView view) =>
    '${view.station.id} · Observation tier: ${view.depth.fresh ? view.station.observationTier ?? view.station.alertLevel?.name.toUpperCase() ?? "UNKNOWN" : "UNKNOWN"}'
    ' · Episode tier: ${view.station.activeHazardTier ?? "None recorded"} (${view.hazardState})'
    ' · Connectivity: ${view.heartbeat.status} · Heartbeat age: ${MonitoringController.ageLabel(view.heartbeat.ageSeconds)}'
    ' · Water depth: ${OperationalVocabulary.readingLabel(view.depth.value, view.depth.fresh, view.depth.measuredAt)}'
    ' · Latest sample validity: ${view.depth.quality}'
    ' · Measured: ${view.depth.measuredAt?.toUtc().toIso8601String() ?? "unknown"}'
    ' · ${view.sourceLabel}'
    // R4: shared fail-closed rule; internal review only, never LGU authorization.
    '${view.station.operationallyVerified ? " · Verification: AGAPAY field-reviewed station (internal review, not an official order)" : ""}';

/// Shared input provenance/freshness on monitoring, maps, detail and forecasts.
class MonitoringStatus extends StatelessWidget {
  const MonitoringStatus({this.view, super.key});
  final StationFreshnessView? view;
  @override
  Widget build(BuildContext context) {
    final view = this.view ?? AppScope.of(context).monitoring.primaryView;
    if (view == null) {
      return const OperationalStateLabel(
        OperationalState.unknown,
        detail:
            'No valid reading · Observation tier: UNKNOWN · Connectivity: unknown · Latest sample validity: unknown',
      );
    }
    final state = view.depth.quality == 'invalid'
        ? OperationalState.invalid
        : view.sourceStatus.contains('EXERCISE') ||
              view.station.sourceClass == 'simulator'
        ? OperationalState.exercise
        : view.depth.value == null
        ? OperationalState.unknown
        : !view.depth.fresh
        ? OperationalState.stale
        : null;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (state != null) OperationalStateLabel(state),
        Text(
          '${stationStatusDescription(view)} · Depth age: ${MonitoringController.ageLabel(view.depth.ageSeconds)} · Rain: ${OperationalVocabulary.readingLabel(view.rain.value, view.rain.fresh, view.rain.measuredAt)} / ${view.rain.status} / ${view.rain.source}',
          key: const ValueKey('shared-monitoring-status'),
          style: TextStyle(fontSize: 14, color: context.colors.secondary),
        ),
      ],
    );
  }
}
