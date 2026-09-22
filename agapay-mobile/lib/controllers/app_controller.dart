import 'package:flutter/material.dart';
import '../models/alert_level.dart';
import '../models/account.dart';
import '../services/auth_api.dart';
import '../services/sos_drafts.dart';
import 'sos_controller.dart';
import 'forecast_controller.dart';
import 'monitoring_controller.dart';

enum AppTab { home, map, sos, alerts, profile }

/// Central state for accounts, forecasts, practice SOS, and station monitoring.
class AppController extends ChangeNotifier {
  AppController({AuthApi? authApi, SosDraftStore? sosStorage})
    : auth = authApi ?? AuthApi() {
    sos = SosController(auth, storage: sosStorage);
    forecasts = ForecastController(auth);
    monitoring = MonitoringController(auth)..addListener(_monitoringChanged);
    auth.onExpired = () {
      user = null;
      sos.setOwner(null);
      forecasts.setOwner(null);
      monitoring.setOwner(null);
      notifyListeners();
    };
  }
  final AuthApi auth;
  late final SosController sos;
  late final ForecastController forecasts;
  late final MonitoringController monitoring;
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
      notifyListeners();
    }
  }

  Future<void> logout() async {
    await auth.logout();
    user = null;
    sos.setOwner(null);
    forecasts.setOwner(null);
    monitoring.setOwner(null);
    details = false;
    historyAlert = null;
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
    auth.dispose();
    super.dispose();
  }

  AlertLevel alert = AlertLevel.warning;
  AppTab tab = AppTab.home;
  bool details = false;
  AlertLevel? historyAlert;
  bool evacuationMap = false;
  bool notifications = true;
  bool location = true;
  String language = 'English';
  String barangay = 'San Vicente';

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
    historyAlert = null;
    evacuationMap = evacuation;
    notifyListeners();
  }

  void showAlert([AlertLevel? value]) {
    historyAlert = value;
    details = true;
    notifyListeners();
  }

  void closeDetails() {
    details = false;
    historyAlert = null;
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
