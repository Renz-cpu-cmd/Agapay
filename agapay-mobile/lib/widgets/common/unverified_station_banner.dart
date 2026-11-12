import '../../core/ui.dart';

/// R4: shown wherever an observation or recorded incident comes from a station
/// that has not completed AGAPAY's internal field review (or whose eligibility
/// was withdrawn). Wording is fixed so residents never read it as an order.
const unverifiedStationTitle = 'UNVERIFIED STATION — NOT AN OPERATIONAL WARNING';
const unverifiedStationGuidance =
    'This station has not completed AGAPAY field review, or its review was '
    'withdrawn. The reading is kept as a diagnostic record and is not an '
    'evacuation instruction. Follow official local authority advisories.';

class UnverifiedStationBanner extends StatelessWidget {
  const UnverifiedStationBanner({this.compact = false, super.key});
  final bool compact;

  @override
  Widget build(BuildContext context) => Semantics(
    container: true,
    label: compact
        ? unverifiedStationTitle
        : '$unverifiedStationTitle. $unverifiedStationGuidance',
    excludeSemantics: true,
    child: Panel(
      key: const ValueKey('unverified-station-banner'),
      padding: compact ? 10 : 14,
      radius: 12,
      border: AlertLevel.warning.color,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.report_gmailerrorred,
            size: compact ? 18 : 22,
            color: AlertLevel.warning.textColor,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                tx(
                  unverifiedStationTitle,
                  size: compact ? 12 : 13,
                  weight: 800,
                  color: context.colors.text,
                ),
                if (!compact) ...[
                  const SizedBox(height: 4),
                  tx(
                    unverifiedStationGuidance,
                    size: 12,
                    color: context.colors.secondary,
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    ),
  );
}
