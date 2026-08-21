import '../models/evacuation_center.dart';
import '../services/mock_data.dart';

abstract class EvacuationRepository {
  Future<List<EvacuationCenter>> getEvacuationCenters();
  Future<EvacuationCenter?> getNearestEvacuationCenter();
}

class MockEvacuationRepository implements EvacuationRepository {
  final List<EvacuationCenter> _centers = List.from(MockData.initialEvacuationCenters);

  @override
  Future<List<EvacuationCenter>> getEvacuationCenters() async {
    await Future.delayed(const Duration(milliseconds: 200));
    return List.unmodifiable(_centers);
  }

  @override
  Future<EvacuationCenter?> getNearestEvacuationCenter() async {
    await Future.delayed(const Duration(milliseconds: 150));
    if (_centers.isEmpty) return null;
    final sorted = List<EvacuationCenter>.from(_centers)
      ..sort((a, b) => a.distanceKm.compareTo(b.distanceKm));
    return sorted.first;
  }
}
