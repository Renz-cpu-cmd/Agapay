// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get operationalLanguage => 'English';

  @override
  String get translationUnavailable =>
      'Filipino translation unavailable. All operational and critical flows remain in English.';

  @override
  String get residentArea => 'Resident area (verified ID)';

  @override
  String get profileLocality => 'Profile locality (self-reported)';

  @override
  String get selectedStation => 'Selected station';

  @override
  String get languageRequest =>
      'Which language would help your community? This records a request; it does not change app language.';

  @override
  String get unknownDescription =>
      'Current hazard unknown. No valid measurement is available.';

  @override
  String get normalDescription =>
      'Measured depth is below the advisory threshold. Local hazards may remain.';

  @override
  String get advisoryDescription =>
      'Measured depth crossed the advisory threshold. Monitor local updates.';

  @override
  String get warningDescription =>
      'Measured depth crossed the warning threshold. Prepare and check local guidance.';

  @override
  String get evacuateDescription =>
      'Measured depth crossed the EVACUATE threshold. Follow official local authority instructions.';

  @override
  String get unknownAction =>
      'Check official local updates while monitoring is unavailable.';

  @override
  String get normalAction =>
      'Keep monitoring local updates; a below-threshold reading does not rule out hazards.';

  @override
  String get advisoryAction =>
      'Stay alert and monitor updates. Prepare emergency supplies.';

  @override
  String get warningAction =>
      'Prepare for possible evacuation. Move valuables to higher ground.';

  @override
  String get evacuateAction =>
      'AGAPAY EVACUATE-level sensor alert. Prepare to evacuate and follow official local authority instructions. Confirm shelter activation and safe access.';

  @override
  String get practiceSos => 'SOS does not dispatch emergency responders.';

  @override
  String get deliveryPolicy =>
      'Off disables all AGAPAY sensor push, including critical and citywide. In-app notices remain visible. Messages already in flight may arrive.';

  @override
  String get locationChoice => 'App location choice';

  @override
  String get locationPolicy =>
      'Your app choice, operating-system permission and device location service are separate. Manual SOS location stays available.';
}
