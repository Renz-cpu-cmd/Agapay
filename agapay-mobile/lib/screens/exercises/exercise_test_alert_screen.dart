import '../../core/ui.dart';
import '../../services/push_messaging.dart';

/// Test-only view for an EXERCISE_TEST drill push. Rendered locally from the push
/// identifiers; it never loads, stores or opens an operational alert, receipt,
/// advisory or SOS workflow.
class ExerciseTestAlertScreen extends StatelessWidget {
  const ExerciseTestAlertScreen({super.key});

  static const explanation =
      'EXERCISE ONLY. This is an AGAPAY system test sent to a designated test '
      'device. It is not a flood warning, evacuation instruction or official '
      'advisory. No action is required.';

  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final push = app.exerciseAlert;
    return PageContent(
      children: [
        PageHeading('Test alert', 'Exercise only', onBack: app.closeDetails),
        Semantics(
          container: true,
          label: '$exerciseAlertTitle. $explanation',
          excludeSemantics: true,
          child: Panel(
            key: const ValueKey('exercise-test-alert'),
            border: context.colors.link,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.science_outlined, color: context.colors.link),
                    const SizedBox(width: 10),
                    Expanded(
                      child: tx(
                        exerciseAlertTitle,
                        size: 16,
                        weight: 800,
                        color: context.colors.text,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                tx(explanation, size: 13, color: context.colors.text),
              ],
            ),
          ),
        ),
        gap,
        if (push != null) ...[
          tx(
            'Test delivery ${push.deliveryId}',
            size: 11,
            mono: true,
            color: context.colors.muted,
          ),
          tx(
            'Exercise session ${push.sessionId}',
            size: 11,
            mono: true,
            color: context.colors.muted,
          ),
          gap,
        ],
        tx(
          'Test alerts are not saved in community alert history and do not start SOS or emergency response.',
          size: 11,
          color: context.colors.muted,
        ),
        gap,
        ActionButton('CLOSE TEST ALERT', onPressed: app.closeDetails),
      ],
    );
  }
}
