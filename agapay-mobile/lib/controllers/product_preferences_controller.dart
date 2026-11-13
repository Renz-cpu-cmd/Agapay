import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../services/auth_api.dart';

abstract interface class ProductPreferenceStore {
  Future<String?> read(int owner);
  Future<void> write(int owner, String value);
}

class DeviceProductPreferenceStore implements ProductPreferenceStore {
  const DeviceProductPreferenceStore();
  static const storage = FlutterSecureStorage();
  @override
  Future<String?> read(int owner) =>
      storage.read(key: 'agapay_product_preferences_v1_$owner');
  @override
  Future<void> write(int owner, String value) =>
      storage.write(key: 'agapay_product_preferences_v1_$owner', value: value);
}

class ProductPreferencesController extends ChangeNotifier {
  ProductPreferencesController(this.api, {ProductPreferenceStore? store})
    : store = store ?? const DeviceProductPreferenceStore();
  final AuthApi api;
  final ProductPreferenceStore store;
  int? _owner;
  int _generation = 0, _localRevision = 0;
  bool _disposed = false,
      ready = false,
      busy = false,
      conflicted = false,
      locationEnabled = true,
      notificationsEnabled = false;
  int revision = 0;
  String selectedStationId = 'STATION_001';
  String? error,
      localError,
      residentAreaId,
      residentAreaName,
      requestedLanguage;
  List<Map<String, dynamic>> areas = [];
  Future<void> _writes = Future.value();
  bool _current(int version) =>
      !_disposed && _owner != null && version == _generation;

  Future<void> setOwner(int? owner) async {
    if (_disposed) return;
    _owner = owner;
    final version = ++_generation;
    ready = false;
    busy = false;
    conflicted = false;
    error = null;
    localError = null;
    notificationsEnabled = false;
    locationEnabled = true;
    selectedStationId = 'STATION_001';
    residentAreaId = null;
    residentAreaName = null;
    requestedLanguage = null;
    revision = 0;
    areas = [];
    notifyListeners();
    if (owner == null) return;
    final localVersion = _localRevision;
    try {
      final value = await store.read(owner);
      if (_current(version) &&
          localVersion == _localRevision &&
          value != null) {
        final saved = jsonDecode(value) as Map;
        locationEnabled = saved['location_enabled'] is bool
            ? saved['location_enabled'] as bool
            : true;
        if (saved['selected_station_id'] is String) {
          selectedStationId = saved['selected_station_id'] as String;
        }
      }
    } catch (_) {
      if (_current(version)) {
        localError =
            'Device preferences could not be restored; current choices are shown.';
      }
    }
    if (_current(version)) await refresh();
  }

  Future<void> refresh() async {
    if (_disposed || _owner == null || busy) return;
    final version = _generation;
    busy = true;
    error = null;
    notifyListeners();
    try {
      final response = await api.request('auth/preferences');
      if (!_current(version)) return;
      _apply(response);
      try {
        final choices = await api.request('auth/preferences/areas');
        if (_current(version)) {
          areas = (choices as List)
              .map((a) => (a as Map).cast<String, dynamic>())
              .toList();
        }
      } catch (_) {
        if (_current(version)) areas = [];
      }
    } catch (e) {
      if (_current(version)) {
        error = e is AccountException
            ? e.message
            : (ready
                  ? 'Unable to refresh; last saved preferences are shown. Backend account settings govern delivery.'
                  : 'Account preferences unavailable. Push registration remains paused until refreshed.');
      }
    } finally {
      if (_current(version)) {
        busy = false;
        notifyListeners();
      }
    }
  }

  void _apply(dynamic response) {
    if (response is! Map ||
        response['revision'] is! int ||
        response['notifications_enabled'] is! bool ||
        response['locale'] != 'en') {
      throw const FormatException('Invalid preference contract');
    }
    revision = response['revision'] as int;
    notificationsEnabled = response['notifications_enabled'] as bool;
    residentAreaId = response['resident_area_id'] as String?;
    residentAreaName = response['resident_area_name'] as String?;
    requestedLanguage = response['requested_language'] as String?;
    ready = true;
    conflicted = false;
  }

  Future<bool> save(Map<String, dynamic> changes) async {
    if (_disposed || _owner == null || !ready || busy || conflicted) {
      return false;
    }
    final version = _generation;
    busy = true;
    error = null;
    notifyListeners();
    try {
      final response = await api.request(
        'auth/preferences',
        method: 'PATCH',
        body: {'expected_revision': revision, ...changes},
      );
      if (!_current(version)) return false;
      _apply(response);
      return true;
    } catch (e) {
      if (_current(version)) {
        error = e is AccountException
            ? e.message
            : 'Preferences could not be saved.';
        if (e is AccountException && e.status == 409) conflicted = true;
      }
      return false;
    } finally {
      if (_current(version)) {
        busy = false;
        notifyListeners();
      }
    }
  }

  Future<void> updateLocal({bool? location, String? station}) {
    if (_disposed) return Future.value();
    ++_localRevision;
    locationEnabled = location ?? locationEnabled;
    selectedStationId = station ?? selectedStationId;
    localError = null;
    notifyListeners();
    final owner = _owner, version = _generation;
    final payload = jsonEncode({
      'location_enabled': locationEnabled,
      'selected_station_id': selectedStationId,
    });
    if (owner == null) return Future.value();
    return _writes = _writes.then((_) async {
      try {
        await store.write(owner, payload);
      } catch (_) {
        if (_current(version)) {
          localError =
              'Device preference changed for this session but could not be saved.';
          notifyListeners();
        }
      }
    });
  }

  @override
  void dispose() {
    _disposed = true;
    ++_generation;
    super.dispose();
  }
}
