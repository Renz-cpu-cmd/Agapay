import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:agapay_mobile/core/operational_vocabulary.dart';
import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/models/monitoring.dart';
import 'package:agapay_mobile/widgets/common/monitoring_status.dart';

void main() {
  final contract =
      jsonDecode(
            File(
              '../agapay-docs/contracts/operational-presentation-cases.json',
            ).readAsStringSync(),
          )
          as Map;
  test('resident vocabulary agrees with the cross-platform contract', () {
    expect(contract['vocabulary'], {
      'observed': OperationalVocabulary.observed,
      'lastKnown': OperationalVocabulary.lastKnown,
      'noValidReading': OperationalVocabulary.noValidReading,
      'experimentalProjection': OperationalVocabulary.experimentalProjection,
      'officialAdvisory': OperationalVocabulary.officialAdvisory,
      'practiceSos': OperationalVocabulary.practiceSos,
    });
  });
  test('observed tier does not inherit an unresolved critical episode', () {
    final station = MonitoringStation.fromJson({
      'station_id': 'SYNTHETIC',
      'station_name': 'Synthetic recovery',
      'connection_status': 'online',
      'is_online': true,
      'is_stale': false,
      'current_depth_cm': 0,
      'observation_tier': 'NORMAL',
      'alert_tier': 'EVACUATE',
      'active_hazard_tier': 'EVACUATE',
      'source': 'device',
      'history': <dynamic>[],
      'threshold_advisory_cm': 60,
      'threshold_warning_cm': 85,
      'threshold_evacuate_cm': 100,
    });
    expect(station.observationLevel, AlertLevel.normal);
    expect(station.alertLevel, AlertLevel.evacuate);
  });
  for (final row in contract['cases'] as List) {
    for (final theme in [AppTheme.light, AppTheme.dark]) {
      testWidgets(
        '${row['id']} has independent spoken facts at 320px/200% ${theme.brightness}',
        (tester) async {
          tester.view.physicalSize = const Size(320, 900);
          tester.view.devicePixelRatio = 1;
          addTearDown(tester.view.resetPhysicalSize);
          addTearDown(tester.view.resetDevicePixelRatio);
          final semantics = tester.ensureSemantics();
          final time = row['measuredAt'] == null
              ? null
              : DateTime.parse(row['measuredAt'] as String);
          final station = MonitoringStation.fromJson({
            'station_id': 'SYNTHETIC',
            'station_name': 'Synthetic review station',
            'connection_status': row['connectivity'],
            'is_online': row['connectivity'] == 'online',
            'is_stale': !row['current'],
            'current_depth_cm': row['depth'],
            'sensor_quality': row['quality'],
            'active_hazard_tier': row['episodeTier'],
            'alert_tier': 'EVACUATE',
            'observation_tier': 'EVACUATE',
            'history': <dynamic>[],
            'source': 'device',
            'threshold_advisory_cm': 60,
            'threshold_warning_cm': 85,
            'threshold_evacuate_cm': 100,
          });
          ChannelFreshness channel(
            double? value,
            bool fresh,
            String quality,
            String status,
          ) => ChannelFreshness(
            value: value,
            measuredAt: time,
            ageSeconds: time == null ? null : 0,
            status: status,
            quality: quality,
            source: 'Synthetic physical source',
            fresh: fresh,
          );
          final view = StationFreshnessView(
            station: station,
            asOf: DateTime.utc(2026, 10, 23),
            depth: channel(
              (row['depth'] as num?)?.toDouble(),
              row['current'] as bool,
              row['quality'] as String,
              'test',
            ),
            heartbeat: channel(
              null,
              row['connectivity'] == 'online',
              'unknown',
              row['connectivity'] as String,
            ),
            rain: channel(null, false, 'unknown', 'missing'),
            sourceLabel: 'Synthetic physical source',
            sourceStatus: 'test',
            hazardState: row['hazardState'] as String,
          );
          expect(
            OperationalVocabulary.readingLabel(
              view.depth.value,
              view.depth.fresh,
              time,
            ),
            row['label'],
          );
          await tester.pumpWidget(
            MaterialApp(
              theme: theme,
              home: MediaQuery(
                data: const MediaQueryData(textScaler: TextScaler.linear(2)),
                child: Scaffold(
                  body: SingleChildScrollView(
                    child: MonitoringStatus(view: view),
                  ),
                ),
              ),
            ),
          );
          expect(tester.takeException(), isNull);
          for (final fact in [
            'Connectivity: ${row['connectivity']}',
            'Latest sample validity: ${row['quality']}',
            'Episode tier: ${row['episodeTier'] ?? 'None recorded'}',
            'Water depth: ${row['label']}',
          ]) {
            expect(
              find.bySemanticsLabel(RegExp(RegExp.escape(fact))),
              findsWidgets,
              reason: fact,
            );
          }
          expect(find.textContaining('Rain: No valid reading'), findsOneWidget);
          semantics.dispose();
        },
      );
    }
  }
}
