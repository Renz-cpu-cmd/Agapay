/// Resident / Community Member Profile Model
class UserProfile {
  final String id;
  final String fullName;
  final String email;
  final String phone;
  final String barangay;
  final List<String> emergencyContacts;
  final String preferredLanguage; // 'en' or 'fil'
  final bool floodAlertsEnabled;
  final bool heavyRainAlertsEnabled;
  final bool soundAlertsEnabled;

  const UserProfile({
    required this.id,
    required this.fullName,
    required this.email,
    required this.phone,
    required this.barangay,
    this.emergencyContacts = const ['+63 917 123 4567 (Family)', '+63 918 765 4321 (Barangay Office)'],
    this.preferredLanguage = 'en',
    this.floodAlertsEnabled = true,
    this.heavyRainAlertsEnabled = true,
    this.soundAlertsEnabled = true,
  });

  UserProfile copyWith({
    String? id,
    String? fullName,
    String? email,
    String? phone,
    String? barangay,
    List<String>? emergencyContacts,
    String? preferredLanguage,
    bool? floodAlertsEnabled,
    bool? heavyRainAlertsEnabled,
    bool? soundAlertsEnabled,
  }) {
    return UserProfile(
      id: id ?? this.id,
      fullName: fullName ?? this.fullName,
      email: email ?? this.email,
      phone: phone ?? this.phone,
      barangay: barangay ?? this.barangay,
      emergencyContacts: emergencyContacts ?? this.emergencyContacts,
      preferredLanguage: preferredLanguage ?? this.preferredLanguage,
      floodAlertsEnabled: floodAlertsEnabled ?? this.floodAlertsEnabled,
      heavyRainAlertsEnabled: heavyRainAlertsEnabled ?? this.heavyRainAlertsEnabled,
      soundAlertsEnabled: soundAlertsEnabled ?? this.soundAlertsEnabled,
    );
  }
}
