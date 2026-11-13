import 'package:flutter/material.dart';

enum OperationalState { unknown, stale, invalid, exercise, official }

extension OperationalStatePresentation on OperationalState {
  String get label => switch (this) {
    OperationalState.unknown =>
      'No valid reading · current measurement unavailable',
    OperationalState.stale => 'Last known · stale measurement',
    OperationalState.invalid => 'Latest sample invalid · sensor review needed',
    OperationalState.exercise => 'Virtual station feed',
    OperationalState.official => 'Official advisory · check issuer and expiry',
  };
  IconData get icon => switch (this) {
    OperationalState.unknown => Icons.help_outline,
    OperationalState.stale => Icons.schedule,
    OperationalState.invalid => Icons.warning_amber,
    OperationalState.exercise => Icons.science_outlined,
    OperationalState.official => Icons.campaign_outlined,
  };
  Color color(bool dark) => switch (this) {
    OperationalState.unknown =>
      dark ? const Color(0xffb0bfd3) : const Color(0xff405775),
    OperationalState.stale =>
      dark ? const Color(0xffffd278) : const Color(0xff754700),
    OperationalState.invalid =>
      dark ? const Color(0xffffaaaa) : const Color(0xffa51c30),
    OperationalState.exercise =>
      dark ? const Color(0xffd9b8ff) : const Color(0xff663399),
    OperationalState.official =>
      dark ? const Color(0xff8ac3ff) : const Color(0xff174f91),
  };
}

class OperationalStateLabel extends StatelessWidget {
  const OperationalStateLabel(this.state, {this.detail, super.key});
  final OperationalState state;
  final String? detail;
  @override
  Widget build(BuildContext context) => Semantics(
    liveRegion: true,
    child: Wrap(
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 8,
      children: [
        Icon(
          state.icon,
          color: state.color(Theme.of(context).brightness == Brightness.dark),
        ),
        Text(
          detail ?? state.label,
          style: TextStyle(
            fontSize: 14,
            color: state.color(Theme.of(context).brightness == Brightness.dark),
          ),
        ),
      ],
    ),
  );
}
