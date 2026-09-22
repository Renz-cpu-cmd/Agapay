class SosRequest {
  SosRequest.fromJson(Map<String, dynamic> json)
    : id = json['id'] as int,
      requestId = json['request_id'] as String,
      status = json['status'] as String,
      location = json['location'] as String,
      message = json['message'] as String,
      latitude = (json['latitude'] as num?)?.toDouble(),
      longitude = (json['longitude'] as num?)?.toDouble(),
      locationSource = json['location_source'] as String,
      accuracyM = (json['accuracy_m'] as num?)?.toDouble(),
      locationRecordedAt = _date(json['location_recorded_at']),
      createdAt = DateTime.parse(json['created_at'] as String),
      acknowledgedBy = json['acknowledged_by_name'] as String?,
      acknowledgedAt = _date(json['acknowledged_at']),
      resolvedBy = json['resolved_by_name'] as String?,
      resolvedAt = _date(json['resolved_at']),
      resolutionNote = json['resolution_note'] as String?;
  final int id;
  final String requestId, status, location, message;
  final String locationSource;
  final double? latitude, longitude;
  final double? accuracyM;
  final DateTime? locationRecordedAt;
  final DateTime createdAt;
  final String? acknowledgedBy, resolvedBy, resolutionNote;
  final DateTime? acknowledgedAt, resolvedAt;
  static DateTime? _date(dynamic value) =>
      value == null ? null : DateTime.parse(value as String);
}

String sosTime(DateTime value) {
  final local = value.toLocal();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${local.year}-${two(local.month)}-${two(local.day)} ${two(local.hour)}:${two(local.minute)}';
}
