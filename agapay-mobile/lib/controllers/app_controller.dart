import 'dart:async';
import '../services/notification_receipts.dart';
import 'delivery_controller.dart';
import 'package:flutter/material.dart';
import '../models/alert_level.dart';
import '../models/account.dart';
import '../services/auth_api.dart';
import '../services/push_token_provider.dart';
import '../services/push_messaging.dart';
import 'notification_registration_controller.dart';
import '../services/sos_drafts.dart';
import 'sos_controller.dart';
import 'forecast_controller.dart';
import 'hybrid_projection_controller.dart';
import 'monitoring_controller.dart';
import 'community_alert_controller.dart';
import 'official_notice_controller.dart';
import 'theme_controller.dart';
import 'product_preferences_controller.dart';
import 'device_capabilities_controller.dart';
import 'build_information_controller.dart';
import 'response_resource_controller.dart';
import 'station_tracking_controller.dart';

enum AppTab { home, map, sos, alerts, profile }

/// Central state for accounts, forecasts, SOS, and station monitoring.
class AppController extends ChangeNotifier {
  AppController({
    AuthApi? authApi,
    DateTime Function()? observationClock,
    SosDraftStore? sosStorage,
    PushTokenProvider? pushTokenProvider,
    PushMessages? pushMessages,
    StationPositionSource? trackingSource,
    ReceiptStorage? receiptStorage,
    ThemePreferenceStore? themeStorage,
    ProductPreferenceStore? preferenceStorage,
    LocationCapabilitySource? locationSource,
    BuildInformationController? buildInformation,
  }) : auth = authApi ?? AuthApi() {
    theme = ThemeController(store: themeStorage)..addListener(_themeChanged);
    unawaited(theme.restore());
    notificationRegistration = NotificationRegistrationController(
      auth,
      provider: pushTokenProvider ?? const DisabledPushTokenProvider(),
    );
    notificationRegistration.addListener(_capabilitiesChanged);
    unawaited(notificationRegistration.setPreference(false));
    preferences = ProductPreferencesController(auth, store: preferenceStorage)
      ..addListener(_preferencesChanged);
    capabilities = DeviceCapabilitiesController(source: locationSource)
      ..addListener(_capabilitiesChanged);
    buildInfo = buildInformation ?? BuildInformationController();
    buildInfo.addListener(_capabilitiesChanged);
    unawaited(capabilities.refresh());
    unawaited(buildInfo.refresh());
    sos = SosController(auth, storage: sosStorage);
    forecasts = ForecastController(auth);
    hybrid = HybridProjectionController(auth);
    monitoring = MonitoringController(auth, now: observationClock)
      ..addListener(_monitoringChanged);
    communityAlerts = CommunityAlertController(auth)
      ..addListener(_communityChanged);
    notices = OfficialNoticeController(auth, now: observationClock)
      ..addListener(_communityChanged);
    resources = ResponseResourceController(auth)
      ..addListener(_communityChanged);
    deliveries = DeliveryController(auth, storage: receiptStorage)
      ..addListener(_communityChanged);
    tracking = StationTrackingController(auth, source: trackingSource);
    if (pushMessages != null) {
      _pushSubscriptions.add(
        pushMessages.foreground.listen((data) {
          if (_disposed) return;
          final exercise = ExercisePush.parse(data);
          if (exercise != null) {
            // Drill only: no operational refresh, receipt or alert history.
            if (signedIn) showExerciseAlert(exercise);
            return;
          }
          if (SensorPush.parse(data) == null) return;
          unawaited(deliveries.capture(data, 'RECEIVED'));
          if (signedIn) {
            unawaited(communityAlerts.refreshActive());
            unawaited(communityAlerts.refreshHistory(offset: 0));
          }
        }, onError: (Object _) {}),
      );
      _pushSubscriptions.add(
        pushMessages.opened.listen(
          (data) => unawaited(_openPush(data)),
          onError: (Object _) {},
        ),
      );
      unawaited(_initialPush(pushMessages));
    }
    auth.onExpired = () {
      ++_accountGeneration;
      user = null;
      unawaited(preferences.setOwner(null));
      sos.setOwner(null);
      forecasts.setOwner(null);
      hybrid.setOwner(null);
      monitoring.setOwner(null);
      communityAlerts.setOwner(null);
      notices.setScope(null, null);
      resources.setOwner(null);
      deliveries.setOwner(null);
      tracking.reset();
      notificationRegistration.setOwner(null);
      details = false;
      notifyListeners();
    };
    auth.onReaderChanged = () {
      if (_disposed) return;
      if (user != null) {
        unawaited(
          notificationRegistration.setPreference(
            preferences.notificationsEnabled &&
                !auth.offlineReader &&
                auth.hasSession,
          ),
        );
      }
      notifyListeners();
    };
  }
  final AuthApi auth;
  late final ThemeController theme;
  void _themeChanged() => notifyListeners();
  VoidCallback? onPushOpened;
  bool _disposed = false;
  final _pushSubscriptions = <StreamSubscription<Map<String, Object?>>>[];
  Future<void> _initialPush(PushMessages messages) async {
    try {
      final data = await messages.initialMessage();
      if (data != null) await _openPush(data);
    } catch (_) {
      /* Push failure must not affect API login. */
    }
  }

  Future<void> _openPush(Map<String, Object?> data) async {
    final exercise = ExercisePush.parse(data);
    if (exercise != null) {
      if (_disposed) return;
      await restoreSession();
      if (_disposed || !signedIn) return;
      showExerciseAlert(exercise);
      onPushOpened?.call();
      return;
    }
    final push = SensorPush.parse(data);
    if (push == null || _disposed) return;
    unawaited(deliveries.capture(data, 'OPENED'));
    await restoreSession();
    if (_disposed || !signedIn) return;
    tab = AppTab.alerts;
    showCommunityAlert(push.alertId);
    onPushOpened?.call();
  }

  late final DeliveryController deliveries;
  late final SosController sos;
  late final NotificationRegistrationController notificationRegistration;
  late final ProductPreferencesController preferences;
  late final DeviceCapabilitiesController capabilities;
  late final BuildInformationController buildInfo;
  int _accountGeneration = 0;
  bool _stationRestored = false;
  void _capabilitiesChanged() {
    if (!_disposed) notifyListeners();
  }

  void _preferencesChanged() {
    if (_disposed) return;
    if (user != null && preferences.ready) {
      unawaited(
        notificationRegistration.setPreference(
          preferences.notificationsEnabled &&
              !auth.offlineReader &&
              auth.hasSession,
        ),
      );
      _restoreStationSelection();
    }
    notices.setScope(user?.id, preferences.residentAreaId);
    resources.setArea(preferences.residentAreaId);
    notifyListeners();
  }

  void _restoreStationSelection() {
    if (_stationRestored || !preferences.ready || monitoring.stations.isEmpty) {
      return;
    }
    _stationRestored = true;
    if (monitoring.stations.any((s) => s.id == preferences.selectedStationId)) {
      monitoring.selectStation(preferences.selectedStationId);
    }
  }

  Future<void> resumeCapabilities() async {
    if (signedIn) await preferences.refresh();
    if (!_disposed) await refreshCapabilities();
  }

  Future<void> refreshCapabilities() async {
    await capabilities.refresh();
    await notificationRegistration.refreshPermission();
    await notificationRegistration.refresh();
  }

  void selectStation(String id) {
    monitoring.selectStation(id);
    _stationRestored = true;
    unawaited(preferences.updateLocal(station: id));
  }

  late final ForecastController forecasts;
  late final HybridProjectionController hybrid;
  late final MonitoringController monitoring;
  late final CommunityAlertController communityAlerts;
  late final OfficialNoticeController notices;
  late final ResponseResourceController resources;
  late final StationTrackingController tracking;
  Account? user;
  String? authError;
  Future<void>? _restoring;
  bool get signedIn => user != null;

  Future<void> restoreSession() => _restoring ??= _restore();
  Future<void> _restore() async {
    try {
      final restored = await auth.restore();
      if (!_disposed && restored != null) await _setUser(restored);
    } catch (error) {
      authError = error is AccountException
          ? error.message
          : 'Unable to restore your session. Please sign in again.';
    }
  }

  Future<void> _setUser(Account account, {bool resetSession = true}) async {
    if (!resetSession && user?.id == account.id) {
      user = account;
      barangay = account.barangay;
      notifyListeners();
      return;
    }
    final generation = ++_accountGeneration;
    user = account;
    _stationRestored = false;
    notificationRegistration.setOwner(null);
    await notificationRegistration.setPreference(false);
    if (_disposed || generation != _accountGeneration) return;
    sos.setOwner(account.id);
    forecasts.setOwner(account.id);
    hybrid.setOwner(account.id);
    monitoring.setOwner(account.id);
    communityAlerts.setOwner(account.id);
    notices.setScope(account.id, null);
    resources.setOwner(account.id);
    deliveries.setOwner(account.id);
    notificationRegistration.setOwner(auth.offlineReader ? null : account.id);
    tracking.reset();
    if (account.role == 'resident' && !auth.offlineReader) {
      unawaited(tracking.refresh());
    }
    barangay = account.barangay;
    authError = null;
    notifyListeners();
    await preferences.setOwner(account.id);
    if (!_disposed && generation == _accountGeneration) {
      _restoreStationSelection();
      unawaited(refreshCapabilities());
    }
  }

  Future<void> login(String email, String password) async {
    await _setUser(await auth.login(email, password));
    navigate(AppTab.home);
  }

  Future<void> register(Map<String, dynamic> fields) async {
    await _setUser(await auth.register(fields));
    navigate(AppTab.home);
  }

  Future<void> refreshProfile() async {
    final owner = user?.id, generation = _accountGeneration;
    final refreshed = await auth.me();
    if (_disposed || generation != _accountGeneration || user?.id != owner) {
      return;
    }
    await _setUser(refreshed, resetSession: false);
  }

  Future<void> verifyConnection() async {
    final owner = user?.id, generation = _accountGeneration;
    final verified = await auth.me();
    if (_disposed || generation != _accountGeneration || owner != verified.id) {
      return;
    }
    await _setUser(verified);
  }

  Future<void> saveProfile(Map<String, dynamic> fields) async {
    final owner = user!.id, generation = _accountGeneration;
    final saved = await auth.updateProfile({
      'expected_version': user!.version,
      ...fields,
    });
    if (_disposed || generation != _accountGeneration || user?.id != owner) {
      return;
    }
    await _setUser(saved, resetSession: false);
    if (fields.containsKey('password')) {
      await auth.clearLocalSession();
      user = null;
      ++_accountGeneration;
      unawaited(preferences.setOwner(null));
      sos.setOwner(null);
      forecasts.setOwner(null);
      hybrid.setOwner(null);
      monitoring.setOwner(null);
      communityAlerts.setOwner(null);
      notices.setScope(null, null);
      resources.setOwner(null);
      deliveries.setOwner(null);
      tracking.reset();
      notificationRegistration.setOwner(null);
      details = false;
      notifyListeners();
    }
  }

  Future<void> logout() async {
    try {
      if (auth.offlineReader) {
        await auth.clearLocalSession();
      } else {
        await auth.logout(
          beforeRevoke: notificationRegistration.unregisterForLogout,
        );
      }
    } catch (_) {
      notificationRegistration.setOwner(user?.id);
      rethrow;
    }
    user = null;
    ++_accountGeneration;
    unawaited(preferences.setOwner(null));
    sos.setOwner(null);
    forecasts.setOwner(null);
    hybrid.setOwner(null);
    monitoring.setOwner(null);
    communityAlerts.setOwner(null);
    notices.setScope(null, null);
    resources.setOwner(null);
    deliveries.setOwner(null);
    tracking.reset();
    notificationRegistration.setOwner(null);
    details = false;
    tab = AppTab.home;
    barangay = 'Profile locality unavailable';
    notifyListeners();
  }

  void setForeground(bool value) {
    deliveries.setForeground(value);
    monitoring.setForeground(value);
    hybrid.setForeground(value);
    forecasts.setForeground(value);
    communityAlerts.setForeground(value);
    notices.setForeground(value);
    resources.setForeground(value);
    // Pick up a tracking assignment granted while the app was in the background.
    if (value && user?.role == 'resident' && !auth.offlineReader && !tracking.tracking) {
      unawaited(tracking.refresh());
    }
  }

  @override
  void dispose() {
    _disposed = true;
    theme.removeListener(_themeChanged);
    theme.dispose();
    preferences.removeListener(_preferencesChanged);
    preferences.dispose();
    capabilities.removeListener(_capabilitiesChanged);
    capabilities.dispose();
    buildInfo.removeListener(_capabilitiesChanged);
    buildInfo.dispose();
    onPushOpened = null;
    for (final subscription in _pushSubscriptions) {
      unawaited(subscription.cancel());
    }
    auth.onExpired = null;
    auth.onReaderChanged = null;
    sos.dispose();
    forecasts.dispose();
    hybrid.dispose();
    monitoring.removeListener(_monitoringChanged);
    monitoring.dispose();
    communityAlerts.removeListener(_communityChanged);
    communityAlerts.dispose();
    notices.removeListener(_communityChanged);
    notices.dispose();
    resources.removeListener(_communityChanged);
    deliveries.removeListener(_communityChanged);
    deliveries.dispose();
    tracking.dispose();
    resources.dispose();
    notificationRegistration.removeListener(_capabilitiesChanged);
    notificationRegistration.dispose();
    auth.dispose();
    super.dispose();
  }

  AlertLevel? get alert => monitoring.primary?.hasValidReading == true
      ? monitoring.primary?.alertLevel
      : null;
  AppTab tab = AppTab.home;
  bool details = false;
  bool evacuationMap = false;
  bool get notifications => preferences.notificationsEnabled;
  bool get location => preferences.locationEnabled;
  String get language => 'English';
  String barangay = 'Profile locality unavailable';

  void _communityChanged() => notifyListeners();

  void _monitoringChanged() {
    _restoreStationSelection();
    final selected = monitoring.primary;
    if (selected != null) {
      hybrid.selectStation(selected.id);
      forecasts.selectStation(selected.id);
    }
    notifyListeners();
  }

  void navigate(AppTab value, {bool evacuation = false}) {
    tab = value;
    details = false;
    communityAlerts.closeDetail();
    if (value == AppTab.alerts) {
      unawaited(communityAlerts.refreshActive());
      unawaited(communityAlerts.refreshHistory(offset: 0));
    }
    evacuationMap = evacuation;
    notifyListeners();
  }

  void showAlert() {
    communityAlerts.closeDetail();
    exerciseAlert = null;
    details = true;
    notifyListeners();
  }

  void showCommunityAlert(int id) {
    exerciseAlert = null;
    details = true;
    unawaited(communityAlerts.openDetail(id));
    notifyListeners();
  }

  /// Currently displayed EXERCISE_TEST drill, if any. Local only.
  ExercisePush? exerciseAlert;

  void showExerciseAlert(ExercisePush push) {
    communityAlerts.closeDetail();
    exerciseAlert = push;
    details = true;
    notifyListeners();
  }

  void closeDetails() {
    details = false;
    exerciseAlert = null;
    communityAlerts.closeDetail();
    notifyListeners();
  }

  Future<void> updateSettings({
    bool? notifications,
    bool? location,
    String? language,
    String? barangay,
  }) async {
    if (language != null && language != 'English') {
      throw const AccountException(
        'Translation unavailable; operational language remains English.',
      );
    }
    if (notifications != null) {
      await preferences.save({'notifications_enabled': notifications});
    }
    if (location != null) await preferences.updateLocal(location: location);
    if (barangay != null) await saveProfile({'barangay': barangay});
  }
}

class AppScope extends InheritedNotifier<AppController> {
  const AppScope({
    required AppController controller,
    required super.child,
    super.key,
  }) : super(notifier: controller);
  static AppController of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<AppScope>()!.notifier!;
}
