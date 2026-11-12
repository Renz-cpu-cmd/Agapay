class ResponseResource {
  ResponseResource.fromJson(Map<String, dynamic> json)
    : raw = json,
      id = json['id'] as String,
      kind = json['kind'] as String,
      data = (json['data'] as Map).cast<String, dynamic>();
  final Map<String, dynamic> raw, data;
  final String id, kind;
  String get name => data['name'] as String;
  DateTime? get expiresAt =>
      DateTime.tryParse(raw['expires_at'] as String? ?? '');
  String verification(DateTime now) {
    final reported = raw['verification'] as String;
    return reported == 'verified' &&
            (expiresAt == null || !now.isBefore(expiresAt!))
        ? 'expired'
        : reported;
  }

  String get state {
    if (kind == 'shelter' &&
        data['capacity'] is num &&
        data['occupancy'] is num &&
        (data['occupancy'] as num) >= (data['capacity'] as num)) {
      return 'full';
    }
    return data['state'] as String? ?? 'reference';
  }

  bool capacityCurrent(DateTime now) {
    final at = DateTime.tryParse(data['capacity_observed_at'] as String? ?? '');
    return at != null &&
        !at.isAfter(now) &&
        now.difference(at) <= const Duration(minutes: 30);
  }

  bool routeCandidate(DateTime now, {required bool cached}) =>
      !cached &&
      kind == 'shelter' &&
      raw['mode'] == 'Actual' &&
      verification(now) == 'verified' &&
      state == 'active' &&
      raw['route_candidate'] == true;
}
