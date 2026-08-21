/// Evacuation Shelter Center
class EvacuationCenter {
  final String id;
  final String name;
  final String barangay;
  final String address;
  final int capacity;
  final int currentOccupancy;
  final double distanceKm;
  final int estimatedTravelMinutes;
  final double latitude;
  final double longitude;
  final String contactNumber;
  final bool isOpen;
  final bool hasMedicalStation;
  final bool hasReliefGoods;

  const EvacuationCenter({
    required this.id,
    required this.name,
    required this.barangay,
    required this.address,
    required this.capacity,
    required this.currentOccupancy,
    required this.distanceKm,
    required this.estimatedTravelMinutes,
    required this.latitude,
    required this.longitude,
    required this.contactNumber,
    this.isOpen = true,
    this.hasMedicalStation = true,
    this.hasReliefGoods = true,
  });

  int get availableSlots => (capacity - currentOccupancy).clamp(0, capacity);
  double get occupancyPercent => capacity > 0 ? (currentOccupancy / capacity).clamp(0.0, 1.0) : 0.0;
}
