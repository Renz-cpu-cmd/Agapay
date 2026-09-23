Map<String, Object?> communityEpisode({
  int id = 501,
  bool resolved = false,
  String severity = 'EVACUATE',
}) => {
  'id': id,
  'station_id': 'STATION_TEST',
  'station_name': 'Community Test Station',
  'barangay': 'San Vicente',
  'municipality': 'Urdaneta',
  'status': resolved ? 'RESOLVED' : 'ACTIVE',
  'severity': severity,
  'source': 'sensor',
  'trigger_depth_cm': 105.0,
  'latest_depth_cm': resolved ? 35.2 : 102.3,
  'triggered_at': '2026-09-23T01:02:03Z',
  'last_transition_at': resolved
      ? '2026-09-23T01:05:00Z'
      : '2026-09-23T01:02:03Z',
  'resolved_at': resolved ? '2026-09-23T01:05:00Z' : null,
};
Map<String, Object?> communityDetail({int id = 501, bool resolved = false}) => {
  ...communityEpisode(id: id, resolved: resolved),
  'transitions': {
    'total': resolved ? 2 : 1,
    'items': [
      {
        'previous_severity': 'NORMAL',
        'new_severity': 'EVACUATE',
        'water_depth_cm': 105.0,
        'transitioned_at': '2026-09-23T01:02:03Z',
      },
      if (resolved)
        {
          'previous_severity': 'EVACUATE',
          'new_severity': 'NORMAL',
          'water_depth_cm': 35.2,
          'transitioned_at': '2026-09-23T01:05:00Z',
        },
    ],
  },
};
Map<String, Object?> communityPage({
  bool resolved = false,
  int id = 501,
  int total = 1,
}) => {
  'items': [communityEpisode(id: id, resolved: resolved)],
  'total': total,
};
