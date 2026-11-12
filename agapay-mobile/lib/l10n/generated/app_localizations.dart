import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'generated/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[Locale('en')];

  /// No description provided for @operationalLanguage.
  ///
  /// In en, this message translates to:
  /// **'English'**
  String get operationalLanguage;

  /// No description provided for @translationUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Filipino translation unavailable. All operational and critical flows remain in English.'**
  String get translationUnavailable;

  /// No description provided for @residentArea.
  ///
  /// In en, this message translates to:
  /// **'Resident area (verified ID)'**
  String get residentArea;

  /// No description provided for @profileLocality.
  ///
  /// In en, this message translates to:
  /// **'Profile locality (self-reported)'**
  String get profileLocality;

  /// No description provided for @selectedStation.
  ///
  /// In en, this message translates to:
  /// **'Selected station'**
  String get selectedStation;

  /// No description provided for @languageRequest.
  ///
  /// In en, this message translates to:
  /// **'Which language would help your community? This records a request; it does not change app language.'**
  String get languageRequest;

  /// No description provided for @unknownDescription.
  ///
  /// In en, this message translates to:
  /// **'Current hazard unknown. No valid measurement is available.'**
  String get unknownDescription;

  /// No description provided for @normalDescription.
  ///
  /// In en, this message translates to:
  /// **'Measured depth is below the advisory threshold. Local hazards may remain.'**
  String get normalDescription;

  /// No description provided for @advisoryDescription.
  ///
  /// In en, this message translates to:
  /// **'Measured depth crossed the advisory threshold. Monitor local updates.'**
  String get advisoryDescription;

  /// No description provided for @warningDescription.
  ///
  /// In en, this message translates to:
  /// **'Measured depth crossed the warning threshold. Prepare and check local guidance.'**
  String get warningDescription;

  /// No description provided for @evacuateDescription.
  ///
  /// In en, this message translates to:
  /// **'Measured depth crossed the EVACUATE threshold. Follow official local authority instructions.'**
  String get evacuateDescription;

  /// No description provided for @unknownAction.
  ///
  /// In en, this message translates to:
  /// **'Check official local updates while monitoring is unavailable.'**
  String get unknownAction;

  /// No description provided for @normalAction.
  ///
  /// In en, this message translates to:
  /// **'Keep monitoring local updates; a below-threshold reading does not rule out hazards.'**
  String get normalAction;

  /// No description provided for @advisoryAction.
  ///
  /// In en, this message translates to:
  /// **'Stay alert and monitor updates. Prepare emergency supplies.'**
  String get advisoryAction;

  /// No description provided for @warningAction.
  ///
  /// In en, this message translates to:
  /// **'Prepare for possible evacuation. Move valuables to higher ground.'**
  String get warningAction;

  /// No description provided for @evacuateAction.
  ///
  /// In en, this message translates to:
  /// **'AGAPAY EVACUATE-level sensor alert. Prepare to evacuate and follow official local authority instructions. Confirm shelter activation and safe access.'**
  String get evacuateAction;

  /// No description provided for @practiceSos.
  ///
  /// In en, this message translates to:
  /// **'SOS does not dispatch emergency responders.'**
  String get practiceSos;

  /// No description provided for @deliveryPolicy.
  ///
  /// In en, this message translates to:
  /// **'Off disables all AGAPAY sensor push, including critical and citywide. In-app notices remain visible. Messages already in flight may arrive.'**
  String get deliveryPolicy;

  /// No description provided for @locationChoice.
  ///
  /// In en, this message translates to:
  /// **'App location choice'**
  String get locationChoice;

  /// No description provided for @locationPolicy.
  ///
  /// In en, this message translates to:
  /// **'Your app choice, operating-system permission and device location service are separate. Manual SOS location stays available.'**
  String get locationPolicy;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
