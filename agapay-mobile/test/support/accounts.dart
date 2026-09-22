import 'dart:convert';
import 'package:agapay_mobile/controllers/app_controller.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:agapay_mobile/services/sos_drafts.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'predictions.dart';

class MemoryTokens implements TokenStore {
  String? value;
  @override
  Future<String?> read() async => value;
  @override
  Future<void> write(String token) async {
    value = token;
  }

  @override
  Future<void> clear() async {
    value = null;
  }
}

class MemorySosDrafts implements SosDraftStore {
  final values = <int, Map<String, dynamic>>{};
  @override
  Future<Map<String, dynamic>?> read(int userId) async => values[userId];
  @override
  Future<void> write(int userId, Map<String, dynamic> draft) async {
    values[userId] = Map.from(draft);
  }

  @override
  Future<void> clear(int userId) async {
    values.remove(userId);
  }
}

Map<String, dynamic> practiceSos({
  Map<String, dynamic> fields = const {},
  String status = 'ACTIVE',
}) => {
  'id': 1,
  'request_id': '00000000-0000-4000-8000-000000000001',
  'location': 'Practice site, San Vicente',
  'message': 'Practice only',
  'latitude': null,
  'longitude': null,
  'status': status,
  'practice': true,
  'created_at': '2026-09-04T01:00:00Z',
  'acknowledged_by_name': status == 'ACTIVE' ? null : 'Test Officer',
  'acknowledged_at': status == 'ACTIVE' ? null : '2026-09-04T01:02:00Z',
  'resolved_by_name': status == 'RESOLVED' ? 'Test Officer' : null,
  'resolved_at': status == 'RESOLVED' ? '2026-09-04T01:05:00Z' : null,
  'resolution_note': status == 'RESOLVED' ? 'Practice complete.' : null,
  ...fields,
};

Map<String, dynamic> resident() => {
  'id': 1,
  'name': 'Test Resident',
  'email': 'resident@example.com',
  'phone': '+639123456789',
  'barangay': 'San Vicente',
  'role': 'resident',
  'created_at': '2026-09-04T01:00:00Z',
  'updated_at': '2026-09-04T01:00:00Z',
  'is_active': true,
};

AppController fixtureController() {
  var user = resident();
  final storage = MemoryTokens();
  final requests = <Map<String, dynamic>>[];
  final client = MockClient((request) async {
    if (request.url.path == '/api/monitoring/stations') {
      final now = DateTime.now().toUtc().toIso8601String();
      return http.Response(
        jsonEncode({
          'checked_at': now,
          'stale_after_seconds': 30,
          'stations': [
            {
              'station_id': 'STATION_001',
              'station_name': 'Test Deployed Station',
              'barangay': 'San Vicente',
              'municipality': 'Urdaneta City',
              'latitude': 15.98165,
              'longitude': 120.560573,
              'administrative_status': 'active',
              'connection_status': 'online',
              'is_online': true,
              'is_stale': false,
              'age_seconds': 1,
              'alert_tier': 'WARNING',
              'trend': 'rising',
              'current_depth_cm': 95.8,
              'latest_depth_cm': 95.8,
              'latest_rainfall_mm': 3.2,
              'sensor_quality': 'valid',
              'last_ping': now,
              'observed_at': now,
              'firmware_version': '0.2.0-simulator',
              'source': 'simulator',
              'threshold_advisory_cm': 60.0,
              'threshold_warning_cm': 85.0,
              'threshold_evacuate_cm': 100.0,
              'history': [
                {
                  'sequence_no': 1,
                  'water_depth_cm': 95.8,
                  'rainfall_mm': 3.2,
                  'sensor_quality': 'valid',
                  'device_uptime_ms': 1000,
                  'recorded_at': now,
                },
              ],
            },
          ],
        }),
        200,
      );
    }
    if (request.url.path == '/api/stations') {
      return http.Response(
        jsonEncode([
          {
            'station_id': 'STATION_001',
            'station_name': 'Test Deployed Station',
            'barangay': 'San Vicente',
            'municipality': 'Urdaneta City',
            'latitude': 15.98165,
            'longitude': 120.560573,
            'sensor_height_cm': 120.0,
            'threshold_advisory_cm': 60.0,
            'threshold_warning_cm': 85.0,
            'threshold_evacuate_cm': 100.0,
            'status': 'active',
            'last_ping': DateTime.now().toUtc().toIso8601String(),
            'firmware_version': '1.0.0',
            'created_at': '2026-09-04T01:00:00Z',
          },
        ]),
        200,
      );
    }
    if (request.url.path == '/api/telemetry/STATION_001/latest') {
      return http.Response(
        jsonEncode({
          'id': 1,
          'station_id': 'STATION_001',
          'sequence_no': 1,
          'water_depth_cm': 95.8,
          'rainfall_mm': 3.2,
          'sensor_quality': 'valid',
          'device_uptime_ms': 1000,
          'recorded_at': DateTime.now().toUtc().toIso8601String(),
        }),
        200,
      );
    }
    if (request.url.path.startsWith('/api/predictions/')) {
      final preview = request.url.queryParameters['mode'] == 'preview';
      return http.Response(
        jsonEncode(
          predictionFixture(
            status: preview
                ? request.url.queryParameters['scenario'] ?? 'available'
                : 'not_trained',
            source: preview ? 'simulated' : 'none',
          ),
        ),
        200,
      );
    }
    if (request.url.path == '/api/sos') {
      if (request.method == 'POST') {
        final saved = practiceSos(
          fields: jsonDecode(request.body) as Map<String, dynamic>,
        );
        requests.add(saved);
        return http.Response(jsonEncode(saved), 201);
      }
      return http.Response(
        jsonEncode({'items': requests, 'total': requests.length}),
        200,
      );
    }
    if (request.url.path.endsWith('/logout')) return http.Response('', 204);
    if (request.url.path.endsWith('/me')) {
      if (request.method == 'PATCH') {
        user = {...user, ...jsonDecode(request.body) as Map<String, dynamic>};
      }
      return http.Response(jsonEncode(user), 200);
    }
    if (request.url.path.endsWith('/register')) {
      final fields = jsonDecode(request.body) as Map<String, dynamic>;
      fields.remove('password');
      user = {...user, ...fields};
    }
    return http.Response(
      jsonEncode({
        'user': user,
        'access_token': 'test-session',
        'expires_at': '2026-09-11T01:00:00Z',
      }),
      200,
    );
  });
  return AppController(
    sosStorage: MemorySosDrafts(),
    authApi: AuthApi(client: client, storage: storage),
  );
}
