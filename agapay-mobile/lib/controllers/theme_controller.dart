import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

abstract interface class ThemePreferenceStore {
  Future<String?> read();
  Future<void> write(String value);
}

class DeviceThemePreferenceStore implements ThemePreferenceStore {
  const DeviceThemePreferenceStore();
  static const _storage = FlutterSecureStorage();
  static const _key = 'agapay_theme';
  @override
  Future<String?> read() => _storage.read(key: _key);
  @override
  Future<void> write(String value) => _storage.write(key: _key, value: value);
}

class ThemeController extends ChangeNotifier {
  ThemeController({ThemePreferenceStore? store})
    : _store = store ?? const DeviceThemePreferenceStore();
  final ThemePreferenceStore _store;
  ThemeMode mode = ThemeMode.light;
  bool _disposed = false;
  int _revision = 0;
  Future<void> _writes = Future.value();
  Future<void>? _restoring;
  String? saveError;
  Future<void> restore() => _restoring ??= _restore();
  Future<void> _restore() async {
    final revision = _revision;
    try {
      final saved = await _store.read();
      if (_disposed || revision != _revision) return;
      mode = saved == 'dark' ? ThemeMode.dark : ThemeMode.light;
      notifyListeners();
    } catch (_) {
      /* Unavailable storage falls back to light. */
    }
  }

  Future<void> setMode(ThemeMode next) {
    if (_disposed) return Future.value();
    final revision = ++_revision;
    mode = next == ThemeMode.dark ? ThemeMode.dark : ThemeMode.light;
    saveError = null;
    final value = mode == ThemeMode.dark ? 'dark' : 'light';
    notifyListeners();
    // Serialize writes so rapid switching cannot save an older selection last.
    return _writes = _writes.then((_) async {
      try {
        await _store.write(value);
      } catch (_) {
        if (!_disposed && revision == _revision) {
          saveError = 'Theme changed for this session, but could not be saved.';
          notifyListeners();
        }
      }
    });
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}
