import 'alert_tier.dart';

enum NotificationType {
  floodAlert,
  waterLevelWarning,
  evacuationOrder,
  systemStatus,
  weatherUpdate,
}

/// Notification inbox item
class NotificationItem {
  final String id;
  final String title;
  final String description;
  final DateTime timestamp;
  final AlertTier tier;
  final NotificationType type;
  final bool isRead;
  final String? relatedStationId;

  const NotificationItem({
    required this.id,
    required this.title,
    required this.description,
    required this.timestamp,
    this.tier = AlertTier.normal,
    this.type = NotificationType.floodAlert,
    this.isRead = false,
    this.relatedStationId,
  });

  NotificationItem copyWith({
    String? id,
    String? title,
    String? description,
    DateTime? timestamp,
    AlertTier? tier,
    NotificationType? type,
    bool? isRead,
    String? relatedStationId,
  }) {
    return NotificationItem(
      id: id ?? this.id,
      title: title ?? this.title,
      description: description ?? this.description,
      timestamp: timestamp ?? this.timestamp,
      tier: tier ?? this.tier,
      type: type ?? this.type,
      isRead: isRead ?? this.isRead,
      relatedStationId: relatedStationId ?? this.relatedStationId,
    );
  }
}
