import 'dart:async';
import 'package:flutter/material.dart';
import '../models/alert_tier.dart';
import '../models/trend_direction.dart';
import '../models/station.dart';
import '../models/flood_alert.dart';
import '../models/evacuation_center.dart';
import '../models/sos_beacon.dart';
import '../models/user_profile.dart';
import '../models/notification_item.dart';
import '../models/telemetry_history.dart';
import '../repositories/station_repository.dart';
import '../repositories/alert_repository.dart';
import '../repositories/evacuation_repository.dart';
import '../repositories/sos_repository.dart';
import '../services/mock_data.dart';

/// Central reactive state controller for AGAPAY.
/// Uses standard Flutter ChangeNotifier for zero-dependency high-performance updates.
class AppController extends ChangeNotifier {
  final MockStationRepository _stationRepo = MockStationRepository();
  final MockAlertRepository _alertRepo = MockAlertRepository();
  final MockEvacuationRepository _evacRepo = MockEvacuationRepository();
  final MockSosRepository _sosRepo = MockSosRepository();

  // Authentication & User
  bool _isLoggedIn = true;
  UserProfile _user = MockData.defaultUser;

  // Connection & Offline
  bool _isOffline = false;
  DateTime _lastSyncTime = DateTime.now();

  // Stations & Live Telemetry
  List<Station> _stations = [];
  Station? _selectedStation;
  bool _isLoadingStations = false;

  // Alerts
  List<FloodAlert> _alerts = [];
  FloodAlert? _latestAlert;

  // Evacuation Centers
  List<EvacuationCenter> _evacuationCenters = [];
  EvacuationCenter? _nearestEvacuationCenter;

  // Emergency SOS State
  SosBeacon? _activeSos;
  bool _isSendingSos = false;
  Timer? _sosSimulationTimer;

  // Notifications
  List<NotificationItem> _notifications = List.from(MockData.initialNotifications);

  // Navigation
  int _currentTabIndex = 0;

  // Background ticker for live simulated sensor stream
  Timer? _liveTicker;

  AppController() {
    _initializeData();
    _startLiveSensorSimulation();
  }

  // Getters
  bool get isLoggedIn => _isLoggedIn;
  UserProfile get user => _user;
  bool get isOffline => _isOffline;
  DateTime get lastSyncTime => _lastSyncTime;

  List<Station> get stations => _stations;
  Station? get selectedStation => _selectedStation ?? (_stations.isNotEmpty ? _stations.first : null);
  bool get isLoadingStations => _isLoadingStations;

  List<FloodAlert> get alerts => _alerts;
  FloodAlert? get latestAlert => _latestAlert;

  List<EvacuationCenter> get evacuationCenters => _evacuationCenters;
  EvacuationCenter? get nearestEvacuationCenter => _nearestEvacuationCenter;

  SosBeacon? get activeSos => _activeSos;
  bool get isSendingSos => _isSendingSos;
  bool get isSosActive => _activeSos != null && _activeSos!.status != SosStatus.resolved && _activeSos!.status != SosStatus.idle;

  List<NotificationItem> get notifications => _notifications;
  int get unreadNotificationCount => _notifications.where((n) => !n.isRead).length;

  int get currentTabIndex => _currentTabIndex;
  String get currentLanguage => _user.preferredLanguage;

  Future<void> _initializeData() async {
    _isLoadingStations = true;
    notifyListeners();

    _stations = await _stationRepo.getStations();
    if (_stations.isNotEmpty) {
      _selectedStation = _stations.first;
    }
    _alerts = await _alertRepo.getActiveAlerts();
    _latestAlert = await _alertRepo.getLatestAlert();
    _evacuationCenters = await _evacRepo.getEvacuationCenters();
    _nearestEvacuationCenter = await _evacRepo.getNearestEvacuationCenter();

    _isLoadingStations = false;
    _lastSyncTime = DateTime.now();
    notifyListeners();
  }

  void _startLiveSensorSimulation() {
    _liveTicker?.cancel();
    _liveTicker = Timer.periodic(const Duration(seconds: 12), (timer) {
      if (_isOffline || _stations.isEmpty) return;

      // Subtle live sensor fluctuation simulation
      final updatedStations = _stations.map((station) {
        // Fluctuate depth slightly
        final delta = (DateTime.now().second % 3 == 0) ? 0.3 : -0.2;
        final newDepth = (station.waterDepthCm + delta).clamp(15.0, 95.0);
        final trend = delta > 0 ? TrendDirection.rising : (delta < 0 ? TrendDirection.falling : TrendDirection.stable);

        return station.copyWith(
          waterDepthCm: double.parse(newDepth.toStringAsFixed(1)),
          lastUpdated: DateTime.now(),
          trend: trend,
        );
      }).toList();

      _stations = updatedStations;
      if (_selectedStation != null) {
        _selectedStation = _stations.firstWhere(
          (s) => s.id == _selectedStation!.id,
          orElse: () => _stations.first,
        );
      }
      _lastSyncTime = DateTime.now();
      notifyListeners();
    });
  }

  void selectStation(String stationId) {
    final found = _stations.where((s) => s.id == stationId);
    if (found.isNotEmpty) {
      _selectedStation = found.first;
      notifyListeners();
    }
  }

  void setTabIndex(int index) {
    _currentTabIndex = index;
    notifyListeners();
  }

  void toggleOfflineMode() {
    _isOffline = !_isOffline;
    if (!_isOffline) {
      _lastSyncTime = DateTime.now();
    }
    notifyListeners();
  }

  void toggleLanguage() {
    final newLang = _user.preferredLanguage == 'en' ? 'fil' : 'en';
    _user = _user.copyWith(preferredLanguage: newLang);
    notifyListeners();
  }

  Future<void> refreshData() async {
    if (_isOffline) return;
    _isLoadingStations = true;
    notifyListeners();

    await Future.delayed(const Duration(milliseconds: 600));
    _stations = await _stationRepo.getStations();
    _alerts = await _alertRepo.getActiveAlerts();
    _latestAlert = await _alertRepo.getLatestAlert();
    _evacuationCenters = await _evacRepo.getEvacuationCenters();
    _nearestEvacuationCenter = await _evacRepo.getNearestEvacuationCenter();

    _lastSyncTime = DateTime.now();
    _isLoadingStations = false;
    notifyListeners();
  }

  // SOS Emergency Actions
  Future<void> triggerSos({String emergencyType = 'Trapped by floodwaters'}) async {
    _isSendingSos = true;
    notifyListeners();

    _activeSos = await _sosRepo.sendSos(
      userId: _user.id,
      userName: _user.fullName,
      phone: _user.phone,
      barangay: _user.barangay,
      latitude: _selectedStation?.latitude ?? 14.7365,
      longitude: _selectedStation?.longitude ?? 120.9582,
      emergencyType: emergencyType,
    );

    _isSendingSos = false;
    notifyListeners();

    // Simulate emergency center acknowledgment after 4 seconds
    _sosSimulationTimer?.cancel();
    _sosSimulationTimer = Timer(const Duration(seconds: 4), () {
      if (_activeSos != null && _activeSos!.status == SosStatus.sent) {
        _activeSos = _activeSos!.copyWith(
          status: SosStatus.acknowledged,
          responderTeam: 'BDRRMC Rescue Boat Bravo',
          etaMinutes: 6,
        );
        notifyListeners();
      }
    });
  }

  Future<void> cancelSos() async {
    if (_activeSos != null) {
      _sosSimulationTimer?.cancel();
      _activeSos = await _sosRepo.cancelSos(_activeSos!.id);
      notifyListeners();
    }
  }

  void resolveSos() {
    if (_activeSos != null) {
      _activeSos = _activeSos!.copyWith(status: SosStatus.resolved);
      notifyListeners();
    }
  }

  // Notifications
  void markNotificationRead(String id) {
    final index = _notifications.indexWhere((n) => n.id == id);
    if (index != -1) {
      _notifications[index] = _notifications[index].copyWith(isRead: true);
      notifyListeners();
    }
  }

  void markAllNotificationsRead() {
    _notifications = _notifications.map((n) => n.copyWith(isRead: true)).toList();
    notifyListeners();
  }

  void clearNotifications() {
    _notifications = [];
    notifyListeners();
  }

  // Auth
  Future<bool> login(String email, String password) async {
    await Future.delayed(const Duration(milliseconds: 500));
    _isLoggedIn = true;
    notifyListeners();
    return true;
  }

  Future<bool> register({
    required String fullName,
    required String email,
    required String password,
    required String barangay,
    required String phone,
  }) async {
    await Future.delayed(const Duration(milliseconds: 600));
    _user = UserProfile(
      id: 'USR-${DateTime.now().millisecondsSinceEpoch.toString().substring(8)}',
      fullName: fullName,
      email: email,
      phone: phone,
      barangay: barangay,
    );
    _isLoggedIn = true;
    notifyListeners();
    return true;
  }

  void logout() {
    _isLoggedIn = false;
    notifyListeners();
  }

  void updateUserProfile(UserProfile updated) {
    _user = updated;
    notifyListeners();
  }

  Future<TelemetrySummary> getStationHistory(String stationId, {int hoursBack = 24}) {
    return _stationRepo.getStationTelemetryHistory(stationId, hoursBack: hoursBack);
  }

  @override
  void dispose() {
    _liveTicker?.cancel();
    _sosSimulationTimer?.cancel();
    super.dispose();
  }
}
