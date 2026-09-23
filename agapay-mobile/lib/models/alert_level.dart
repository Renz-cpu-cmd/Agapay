import 'package:flutter/material.dart';

enum AlertLevel { normal, advisory, warning, evacuate }

extension AlertValues on AlertLevel {
  String get label => name.toUpperCase();
  Color get color => const [
    Color(0xff16a34a),
    Color(0xffca8a04),
    Color(0xffea580c),
    Color(0xffdc2626),
  ][index];
  Color get textColor => const [
    Color(0xff4ade80),
    Color(0xfffbbf24),
    Color(0xfffb923c),
    Color(0xfff87171),
  ][index];
  Color get background => const [
    Color(0x80052e16),
    Color(0x801c1200),
    Color(0x801c0a00),
    Color(0x801c0000),
  ][index];
  double get water => const [42.3, 63.1, 95.8, 103.4][index];
  String get description => const [
    'Water level is within normal range.',
    'Water level is increasing. Stay alert.',
    'Flood water is rising. Prepare for possible evacuation.',
    'High flood risk detected. Follow official local authority instructions.',
  ][index];
  String get action => const [
    'Continue daily activities. Monitor updates.',
    'Stay alert and monitor updates. Prepare emergency supplies.',
    'Prepare for possible evacuation. Move valuables to higher ground.',
    'AGAPAY EVACUATE-level sensor alert. Prepare to evacuate and follow official local authority instructions. Confirm shelter activation and safe access.',
  ][index];
  String get trend =>
      const ['→ STABLE', '↗ RISING', '↗ RISING', '↑ RAPIDLY RISING'][index];
  String get detailTrend =>
      const ['→ Stable', '↗ Rising', '↗ Rising', '↑ Rapidly Rising'][index];
  String get rate => const [
    '+0.1 cm / 10 min',
    '+2.4 cm / 10 min',
    '+3.2 cm / 10 min',
    '+5.8 cm / 10 min',
  ][index];
  String get rainfall => const ['1.2 mm', '4.6 mm', '6.4 mm', '9.6 mm'][index];
  static AlertLevel forWater(num cm) => cm >= 100
      ? AlertLevel.evacuate
      : cm >= 85
      ? AlertLevel.warning
      : cm >= 60
      ? AlertLevel.advisory
      : AlertLevel.normal;
}
