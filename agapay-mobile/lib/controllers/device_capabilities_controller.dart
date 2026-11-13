import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';

class LocationCapability {
  const LocationCapability({required this.permission, required this.service});
  final String permission, service;
}

abstract interface class LocationCapabilitySource {
  Future<LocationCapability> read();
}

class OperatingSystemLocationSource implements LocationCapabilitySource {
  const OperatingSystemLocationSource();
  @override
  Future<LocationCapability> read() async {
    final permission = await Geolocator.checkPermission();
    final service = await Geolocator.isLocationServiceEnabled();
    return LocationCapability(
      permission: permission.name,
      service: service ? 'enabled' : 'disabled',
    );
  }
}

class DeviceCapabilitiesController extends ChangeNotifier {
  DeviceCapabilitiesController({LocationCapabilitySource? source})
    : source = source ?? const OperatingSystemLocationSource();
  final LocationCapabilitySource source;
  LocationCapability location = const LocationCapability(
    permission: 'unknown',
    service: 'unknown',
  );
  bool _disposed = false;
  int _generation = 0;
  final _pending = <Completer<LocationCapability>, Timer>{};
  Future<void> refresh() async {
    if (_disposed) return;
    final version = ++_generation;
    final result = Completer<LocationCapability>();
    final timer = Timer(const Duration(seconds: 5), () {
      if (!result.isCompleted) {
        result.completeError(TimeoutException('Capability query timed out'));
      }
    });
    _pending[result] = timer;
    try {
      source.read().then(
        (value) {
          if (!result.isCompleted) result.complete(value);
        },
        onError: (Object error, StackTrace stack) {
          if (!result.isCompleted) result.completeError(error, stack);
        },
      );
      final next = await result.future;
      if (!_disposed && version == _generation) location = next;
    } catch (_) {
      if (!_disposed && version == _generation) {
        location = const LocationCapability(
          permission: 'unavailable',
          service: 'unavailable',
        );
      }
    } finally {
      timer.cancel();
      _pending.remove(result);
    }
    if (!_disposed && version == _generation) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    ++_generation;
    for (final request in _pending.entries) {
      request.value.cancel();
      if (!request.key.isCompleted) {
        request.key.completeError(StateError('Capability query disposed'));
      }
    }
    _pending.clear();
    super.dispose();
  }
}
