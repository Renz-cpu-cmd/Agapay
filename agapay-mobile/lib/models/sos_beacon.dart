import 'package:flutter/material.dart';
import '../core/theme/app_colors.dart';

enum SosStatus {
  idle,
  sending,
  sent,
  acknowledged,
  resolved,
}

extension SosStatusExtension on SosStatus {
  String get label {
    switch (this) {
      case SosStatus.idle:
        return 'Ready';
      case SosStatus.sending:
        return 'Transmitting SOS...';
      case SosStatus.sent:
        return 'SOS Sent';
      case SosStatus.acknowledged:
        return 'Responders Dispatched';
      case SosStatus.resolved:
        return 'Resolved / Safe';
    }
  }

  String get description {
    switch (this) {
      case SosStatus.idle:
        return 'Press and hold button in case of immediate danger.';
      case SosStatus.sending:
        return 'Transmitting your GPS coordinates to BDRRMC command center...';
      case SosStatus.sent:
        return 'Your location has been received by the emergency response dashboard.';
      case SosStatus.acknowledged:
        return 'Barangay rescue unit has acknowledged and is en route.';
      case SosStatus.resolved:
        return 'Emergency status closed. Glad you are safe.';
    }
  }

  Color get color {
    switch (this) {
      case SosStatus.idle:
        return AppColors.sosRed;
      case SosStatus.sending:
        return AppColors.alertWarning;
      case SosStatus.sent:
        return AppColors.secondary;
      case SosStatus.acknowledged:
        return AppColors.alertNormal;
      case SosStatus.resolved:
        return AppColors.textSecondary;
    }
  }

  IconData get icon {
    switch (this) {
      case SosStatus.idle:
        return Icons.emergency_rounded;
      case SosStatus.sending:
        return Icons.sensors_rounded;
      case SosStatus.sent:
        return Icons.check_circle_outline_rounded;
      case SosStatus.acknowledged:
        return Icons.directions_boat_rounded;
      case SosStatus.resolved:
        return Icons.verified_rounded;
    }
  }
}

/// Emergency SOS Beacon record
class SosBeacon {
  final String id;
  final String userId;
  final String userName;
  final String phone;
  final String barangay;
  final double latitude;
  final double longitude;
  final DateTime timestamp;
  final SosStatus status;
  final String? responderTeam;
  final int? etaMinutes;
  final String? emergencyType;

  const SosBeacon({
    required this.id,
    required this.userId,
    required this.userName,
    required this.phone,
    required this.barangay,
    required this.latitude,
    required this.longitude,
    required this.timestamp,
    this.status = SosStatus.idle,
    this.responderTeam,
    this.etaMinutes,
    this.emergencyType = 'Trapped by floodwaters',
  });

  SosBeacon copyWith({
    String? id,
    String? userId,
    String? userName,
    String? phone,
    String? barangay,
    double? latitude,
    double? longitude,
    DateTime? timestamp,
    SosStatus? status,
    String? responderTeam,
    int? etaMinutes,
    String? emergencyType,
  }) {
    return SosBeacon(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      userName: userName ?? this.userName,
      phone: phone ?? this.phone,
      barangay: barangay ?? this.barangay,
      latitude: latitude ?? this.latitude,
      longitude: longitude ?? this.longitude,
      timestamp: timestamp ?? this.timestamp,
      status: status ?? this.status,
      responderTeam: responderTeam ?? this.responderTeam,
      etaMinutes: etaMinutes ?? this.etaMinutes,
      emergencyType: emergencyType ?? this.emergencyType,
    );
  }
}
