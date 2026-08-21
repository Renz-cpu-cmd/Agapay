import '../models/sos_beacon.dart';

abstract class SosRepository {
  Future<SosBeacon> sendSos({
    required String userId,
    required String userName,
    required String phone,
    required String barangay,
    required double latitude,
    required double longitude,
    String? emergencyType,
  });
  Future<SosBeacon> cancelSos(String sosId);
  Future<SosBeacon?> getActiveSos();
}

class MockSosRepository implements SosRepository {
  SosBeacon? _activeSos;

  @override
  Future<SosBeacon> sendSos({
    required String userId,
    required String userName,
    required String phone,
    required String barangay,
    required double latitude,
    required double longitude,
    String? emergencyType,
  }) async {
    await Future.delayed(const Duration(milliseconds: 600));
    _activeSos = SosBeacon(
      id: 'SOS-${DateTime.now().millisecondsSinceEpoch.toString().substring(7)}',
      userId: userId,
      userName: userName,
      phone: phone,
      barangay: barangay,
      latitude: latitude,
      longitude: longitude,
      timestamp: DateTime.now(),
      status: SosStatus.sent,
      emergencyType: emergencyType ?? 'Trapped by floodwaters',
    );
    return _activeSos!;
  }

  @override
  Future<SosBeacon> cancelSos(String sosId) async {
    await Future.delayed(const Duration(milliseconds: 300));
    if (_activeSos != null && _activeSos!.id == sosId) {
      _activeSos = _activeSos!.copyWith(status: SosStatus.resolved);
    }
    return _activeSos!;
  }

  @override
  Future<SosBeacon?> getActiveSos() async {
    return _activeSos;
  }
}
