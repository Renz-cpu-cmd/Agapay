import 'dart:async';
import 'package:flutter/material.dart';
import '../models/alert_level.dart';
import '../models/account.dart';
import '../services/auth_api.dart';
import '../services/push_token_provider.dart';
import 'notification_registration_controller.dart';
import '../services/sos_drafts.dart';
import 'sos_controller.dart';
import 'forecast_controller.dart';
import 'monitoring_controller.dart';
import 'community_alert_controller.dart';

enum AppTab { home, map, sos, alerts, profile }

/// Central state for accounts, forecasts, practice SOS, and station monitoring.
class AppController extends ChangeNotifier {
  AppController({
    AuthApi? authApi,
    SosDraftStore? sosStorage,
    PushTokenProvider? pushTokenProvider,
  }) : auth = authApi ?? AuthApi() {
    notificationRegistration = NotificationRegistrationController(
      auth,
      provider: pushTokenProvider ?? const DisabledPushTokenProvider(),
    );
    sos = SosController(auth, storage: sosStorage);
    forecasts = ForecastController(auth);
    monitoring = MonitoringController(auth)..addListener(_monitoringChanged);
    communityAlerts = CommunityAlertController(auth)
      ..addListener(_communityChanged);
    auth.onExpired = () {
      user = null;
      sos.setOwner(null);
      forecasts.setOwner(null);
      monitoring.setOwner(null);
      communityAlerts.setOwner(null);
      notificationRegistration.setOwner(null);
      details = false;
      notifyListeners();
    };
  }
  final AuthApi auth;
  late final SosController sos;
  late final NotificationRegistrationController notificationRegistration;
  late final ForecastController forecasts;
  late final MonitoringController monitoring;
  late final CommunityAlertController communityAlerts;
  Account? user;
  String? authError;
  Future<void>? _restoring;
  bool get signedIn => user != null;

  Future<void> restoreSession() => _restoring ??= _restore();
  Future<void> _restore() async {
    try {
      final restored = await auth.restore();
      if (restored != null) _setUser(restored);
    } catch (error) {
      authError = error is AccountException
          ? error.message
          : 'Unable to restore your session. Please sign in again.';
    }
  }

  void _setUser(Account account) {
    user = account;
    sos.setOwner(account.id);
    forecasts.setOwner(account.id);
    monitoring.setOwner(account.id);
    communityAlerts.setOwner(account.id);
    notificationRegistration.setOwner(account.id);
    barangay = account.barangay;
    authError = null;
    notifyListeners();
  }

  Future<void> login(String email, String password) async {
    _setUser(await auth.login(email, password));
    navigate(AppTab.home);
  }

  Future<void> register(Map<String, dynamic> fields) async {
    _setUser(await auth.register(fields));
    navigate(AppTab.home);
  }

  Future<void> saveProfile(Map<String, dynamic> fields) async {
    _setUser(await auth.updateProfile(fields));
    if (fields.containsKey('password')) {
      await auth.clearLocalSession();
      user = null;
      sos.setOwner(null);
      forecasts.setOwner(null);
      monitoring.setOwner(null);
      communityAlerts.setOwner(null);
      notificationRegistration.setOwner(null);
      details = false;
      notifyListeners();
    }
  }

  Future<void> logout() async {
    try {
      await auth.logout(
        beforeRevoke: notificationRegistration.unregisterForLogout,
      );
    } catch (_) {
      notificationRegistration.setOwner(user?.id);
      rethrow;
    }
    user = null;
    sos.setOwner(null);
    forecasts.setOwner(null);
    monitoring.setOwner(null);
    communityAlerts.setOwner(null);
    notificationRegistration.setOwner(null);
    details = false;
    tab = AppTab.home;
    notifications = true;
    location = true;
    language = 'English';
    barangay = 'San Vicente';
    notifyListeners();
  }

  @override
  void dispose() {
    auth.onExpired = null;
    sos.dispose();
    forecasts.dispose();
    monitoring.removeListener(_monitoringChanged);
    monitoring.dispose();
    communityAlerts.removeListener(_communityChanged);
    communityAlerts.dispose();
    notificationRegistration.dispose();
    auth.dispose();
    super.dispose();
  }

  AlertLevel alert = AlertLevel.warning;
  AppTab tab = AppTab.home;
  bool details = false;
  bool evacuationMap = false;
  bool notifications = true;
  bool location = true;
  String language = 'English';
  String barangay = 'San Vicente';

  void _communityChanged() => notifyListeners();

  void _monitoringChanged() {
    final measuredLevel = monitoring.primary?.alertLevel;
    if (measuredLevel != null) alert = measuredLevel;
    notifyListeners();
  }

  void setAlert(AlertLevel value) {
    alert = value;
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
    details = true;
    notifyListeners();
  }

  void showCommunityAlert(int id) {
    details = true;
    unawaited(communityAlerts.openDetail(id));
    notifyListeners();
  }

  void closeDetails() {
    details = false;
    communityAlerts.closeDetail();
    notifyListeners();
  }

  void updateSettings({
    bool? notifications,
    bool? location,
    String? language,
    String? barangay,
  }) {
    this.notifications = notifications ?? this.notifications;
    this.location = location ?? this.location;
    this.language = language ?? this.language;
    this.barangay = barangay ?? this.barangay;
    notifyListeners();
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
