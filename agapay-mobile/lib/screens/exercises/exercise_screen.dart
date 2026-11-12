import '../../core/ui.dart';
import '../../core/release_configuration.dart';
import '../../widgets/common/water_level_gauge.dart';
import '../../widgets/common/exercise_test_opt_in.dart';

/// Local exercise state. This screen has no operational controller or API writes;
/// its only server call is the separate, device-specific EXERCISE_TEST opt-in.
class ExerciseScreen extends StatefulWidget {
  const ExerciseScreen({super.key});
  @override
  State<ExerciseScreen> createState() => _ExerciseScreenState();
}

class _ExerciseScreenState extends State<ExerciseScreen> {
  AlertLevel level = AlertLevel.normal;
  static const scenarios = {
    AlertLevel.normal: (42.3, '1.2 mm', '+0.1 cm / 10 min'),
    AlertLevel.advisory: (63.1, '4.6 mm', '+2.4 cm / 10 min'),
    AlertLevel.warning: (95.8, '6.4 mm', '+3.2 cm / 10 min'),
    AlertLevel.evacuate: (103.4, '9.6 mm', '+5.8 cm / 10 min'),
  };
  @override
  Widget build(BuildContext context) {
    if (!ReleaseConfiguration.exercisesAvailable) {
      return const Scaffold(
        body: SafeArea(
          child: Center(
            child: Text('Test tools are unavailable in this build.'),
          ),
        ),
      );
    }
    final scenario = scenarios[level]!;
    return Scaffold(
      appBar: AppBar(title: const Text('TEST WORKSPACE · SYNTHETIC DATA')),
      body: SafeArea(
        child: PageContent(
          children: [
            tx('Test workspace', display: true, size: 24, weight: 700),
            gap,
            tx(
              'Example readings for testing. These controls stay on this screen and do not change station measurements, alerts or notifications.',
            ),
            gap,
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final value in scenarios.keys)
                  ChoiceChip(
                    label: Text(value.label),
                    selected: level == value,
                    onSelected: (_) => setState(() => level = value),
                  ),
              ],
            ),
            gap,
            tx('SYNTHETIC ${level.label}', size: 20, color: level.textColor),
            tx(
              '${scenario.$1.toStringAsFixed(1)} cm · EXAMPLE',
              size: 28,
              mono: true,
            ),
            WaterLevelGauge(
              scenario.$1,
              advisory: 60,
              warning: 85,
              critical: 100,
            ),
            tx('Example rainfall: ${scenario.$2}'),
            tx('Example rate: ${scenario.$3}'),
            gap,
            Builder(
              builder: (context) {
                final app = AppScope.of(context);
                return ExerciseTestOptIn(
                  deviceId: app.notificationRegistration.deviceId,
                  client: ApiExerciseConsentClient(app.auth),
                );
              },
            ),
            gap,
            ActionButton(
              'RETURN TO OPERATIONAL HOME',
              onPressed: () => Navigator.of(context).pop(),
            ),
          ],
        ),
      ),
    );
  }
}
