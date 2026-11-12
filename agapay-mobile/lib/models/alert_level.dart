import 'package:flutter/material.dart';
import '../l10n/generated/app_localizations_en.dart';

final _messages = AppLocalizationsEn();

enum AlertLevel { normal, advisory, warning, evacuate, unknown }

extension AlertValues on AlertLevel {
  String get label => name.toUpperCase();
  Color get color => this == AlertLevel.unknown
      ? const Color(0xff64748b)
      : const [
          Color(0xff16a34a),
          Color(0xffca8a04),
          Color(0xffea580c),
          Color(0xffdc2626),
        ][index];
  Color get textColor => this == AlertLevel.unknown
      ? const Color(0xff64748b)
      : const [
          Color(0xff4ade80),
          Color(0xfffbbf24),
          Color(0xfffb923c),
          Color(0xfff87171),
        ][index];
  Color get background => this == AlertLevel.unknown
      ? const Color(0x1464748b)
      : const [
          Color(0x80052e16),
          Color(0x801c1200),
          Color(0x801c0a00),
          Color(0x801c0000),
        ][index];
  String get description => switch (this) {
    AlertLevel.normal => _messages.normalDescription,
    AlertLevel.advisory => _messages.advisoryDescription,
    AlertLevel.warning => _messages.warningDescription,
    AlertLevel.evacuate => _messages.evacuateDescription,
    AlertLevel.unknown => _messages.unknownDescription,
  };
  String get action => switch (this) {
    AlertLevel.normal => _messages.normalAction,
    AlertLevel.advisory => _messages.advisoryAction,
    AlertLevel.warning => _messages.warningAction,
    AlertLevel.evacuate => _messages.evacuateAction,
    AlertLevel.unknown => _messages.unknownAction,
  };
  static AlertLevel forWater(
    num cm, {
    required num advisory,
    required num warning,
    required num critical,
  }) => cm >= critical
      ? AlertLevel.evacuate
      : cm >= warning
      ? AlertLevel.warning
      : cm >= advisory
      ? AlertLevel.advisory
      : AlertLevel.normal;
}
