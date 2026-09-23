import 'alert_level.dart';

enum CommunityAlertStatus { active, resolved }

Map<String, Object?> _object(Object? value) {
  if (value is! Map<String, Object?>) {
    throw const FormatException('Expected object');
  }
  return value;
}

String _text(Object? value) {
  if (value is! String || value.isEmpty) {
    throw const FormatException('Expected text');
  }
  return value;
}

String? _area(Object? value) => value == null ? null : value as String;
int _integer(Object? value, {int minimum = 0}) {
  if (value is! int || value < minimum) {
    throw const FormatException('Invalid integer');
  }
  return value;
}

double _depth(Object? value) {
  if (value is! num || !value.isFinite || value < 0) {
    throw const FormatException('Invalid depth');
  }
  return value.toDouble();
}

DateTime _timestamp(Object? value) {
  final text = _text(value);
  if (!RegExp(r'(Z|[+-]\d\d:\d\d)$').hasMatch(text)) {
    throw const FormatException('Missing timezone');
  }
  return DateTime.parse(text).toUtc();
}

AlertLevel _severity(Object? value, {bool transition = false}) =>
    switch (value) {
      'NORMAL' when transition => AlertLevel.normal,
      'ADVISORY' => AlertLevel.advisory,
      'WARNING' => AlertLevel.warning,
      'EVACUATE' => AlertLevel.evacuate,
      _ => throw const FormatException('Unknown sensor severity'),
    };
List<T> _items<T>(Object? value, T Function(Object?) parse) {
  if (value is! List) throw const FormatException('Expected items');
  return List.unmodifiable(value.map(parse));
}

class CommunityAlert {
  CommunityAlert.fromJson(Object? raw) {
    final json = _object(raw);
    id = _integer(json['id'], minimum: 1);
    stationId = _text(json['station_id']);
    stationName = _text(json['station_name']);
    barangay = _area(json['barangay']);
    municipality = _area(json['municipality']);
    status = switch (json['status']) {
      'ACTIVE' => CommunityAlertStatus.active,
      'RESOLVED' => CommunityAlertStatus.resolved,
      _ => throw const FormatException('Unknown episode status'),
    };
    severity = _severity(json['severity']);
    source = _text(json['source']);
    if (source != 'sensor') {
      throw const FormatException('Unexpected episode source');
    }
    triggerDepthCm = _depth(json['trigger_depth_cm']);
    latestDepthCm = _depth(json['latest_depth_cm']);
    triggeredAt = _timestamp(json['triggered_at']);
    lastTransitionAt = _timestamp(json['last_transition_at']);
    resolvedAt = json['resolved_at'] == null
        ? null
        : _timestamp(json['resolved_at']);
    if (isResolved != (resolvedAt != null)) {
      throw const FormatException('Invalid resolution state');
    }
  }
  late final int id;
  late final String stationId, stationName, source;
  late final String? barangay, municipality;
  late final CommunityAlertStatus status;
  late final AlertLevel severity;
  late final double triggerDepthCm, latestDepthCm;
  late final DateTime triggeredAt, lastTransitionAt;
  late final DateTime? resolvedAt;
  bool get isResolved => status == CommunityAlertStatus.resolved;
  String get area => [
    barangay,
    municipality,
  ].whereType<String>().where((s) => s.isNotEmpty).join(', ');
}

class CommunityAlertTransition {
  CommunityAlertTransition.fromJson(Object? raw) {
    final json = _object(raw);
    previousSeverity = _severity(json['previous_severity'], transition: true);
    newSeverity = _severity(json['new_severity'], transition: true);
    waterDepthCm = _depth(json['water_depth_cm']);
    transitionedAt = _timestamp(json['transitioned_at']);
  }
  late final AlertLevel previousSeverity, newSeverity;
  late final double waterDepthCm;
  late final DateTime transitionedAt;
}

class CommunityAlertPage {
  CommunityAlertPage.fromJson(Object? raw) {
    final json = _object(raw);
    items = _items(json['items'], CommunityAlert.fromJson);
    total = _integer(json['total']);
    if (items.length > total ||
        items.map((a) => a.id).toSet().length != items.length) {
      throw const FormatException('Invalid episode page');
    }
  }
  late final List<CommunityAlert> items;
  late final int total;
}

class CommunityAlertTransitionPage {
  CommunityAlertTransitionPage.fromJson(Object? raw) {
    final json = _object(raw);
    items = _items(json['items'], CommunityAlertTransition.fromJson);
    total = _integer(json['total']);
    if (items.length > total) {
      throw const FormatException('Invalid transition page');
    }
  }
  late final List<CommunityAlertTransition> items;
  late final int total;
}

class CommunityAlertDetail {
  CommunityAlertDetail.fromJson(Object? raw)
    : episode = CommunityAlert.fromJson(raw),
      transitions = CommunityAlertTransitionPage.fromJson(
        _object(raw)['transitions'],
      );
  final CommunityAlert episode;
  final CommunityAlertTransitionPage transitions;
}

/// Philippine display time (UTC+08:00), independent of the phone's timezone.
/// API DateTimes stay UTC; this shifted value is only used to format the label.
String communityAlertTime(DateTime value) {
  final ph = value.toUtc().add(const Duration(hours: 8));
  String two(int n) => n.toString().padLeft(2, '0');
  return '${ph.year}-${two(ph.month)}-${two(ph.day)} ${two(ph.hour)}:${two(ph.minute)}:${two(ph.second)} PHT';
}
