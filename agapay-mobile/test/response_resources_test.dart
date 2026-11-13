import 'dart:async';
import 'dart:convert';
import 'package:geolocator/geolocator.dart';
import 'package:agapay_mobile/widgets/maps/agapay_google_map.dart';
import 'package:agapay_mobile/controllers/response_resource_controller.dart';
import 'package:agapay_mobile/models/response_resource.dart';
import 'package:agapay_mobile/screens/map/shelter_explorer.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:agapay_mobile/widgets/common/resource_instructions.dart';
import 'package:agapay_mobile/widgets/common/offline_reader_banner.dart';
import 'package:agapay_mobile/widgets/common/sos_outbox.dart';
import 'package:agapay_mobile/core/ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/accounts.dart';

Map<String, dynamic> resource({
  String state = 'active',
  String verification = 'verified',
  String kind = 'shelter',
  DateTime? expires,
}) => {
  'id': 'TEST_SHELTER',
  'kind': kind,
  'mode': 'Actual',
  'version': 1,
  'authority_id': 'TEST_AUTH',
  'issuer_name': 'Synthetic test issuer',
  'source': 'Isolated fixture - no real shelter claim',
  'area_names': ['Synthetic area'],
  'verification': verification,
  'verified_at': verification == 'unverified'
      ? null
      : DateTime.now()
            .toUtc()
            .subtract(const Duration(minutes: 10))
            .toIso8601String(),
  'expires_at': (expires ?? DateTime.now().add(const Duration(hours: 1)))
      .toUtc()
      .toIso8601String(),
  'route_candidate': true,
  'data': {
    'name': 'Synthetic shelter',
    'state': state,
    'address': 'Synthetic entrance address',
    'point': {'latitude': 15.97, 'longitude': 120.57},
    'capacity': 20,
    'occupancy': 5,
    'capacity_observed_at': DateTime.now()
        .subtract(const Duration(hours: 1))
        .toUtc()
        .toIso8601String(),
    'wheelchair_accessible': null,
    'services': ['Synthetic service'],
    'access_constraints': 'Synthetic access constraint',
    'instructions': 'Synthetic reviewed entrance instructions',
    'contacts': [
      {
        'name': 'Synthetic contact',
        'contact': 'TEST-ONLY-CONTACT',
        'hours': 'Exercise hours',
      },
    ],
  },
};
void main() {
  test(
    'inactive full unverified expired and cached shelters cannot become a route candidate',
    () {
      final now = DateTime.now();
      expect(
        ResponseResource.fromJson(
          resource(),
        ).routeCandidate(now, cached: false),
        isTrue,
      );
      for (final state in ['inactive', 'full']) {
        expect(
          ResponseResource.fromJson(
            resource(state: state),
          ).routeCandidate(now, cached: false),
          isFalse,
        );
      }
      for (final status in [
        'unverified',
        'withdrawn',
        'authority_unavailable',
      ]) {
        expect(
          ResponseResource.fromJson(
            resource(verification: status),
          ).routeCandidate(now, cached: false),
          isFalse,
        );
      }
      final expired = ResponseResource.fromJson(resource(expires: now));
      expect(expired.verification(now), 'expired');
      expect(expired.routeCandidate(now, cached: false), isFalse);
      expect(
        ResponseResource.fromJson(resource()).routeCandidate(now, cached: true),
        isFalse,
      );
      final full = resource();
      (full['data'] as Map)['occupancy'] = 20;
      final model = ResponseResource.fromJson(full);
      expect(model.state, 'full');
      expect(model.capacityCurrent(now), isFalse);
      expect(model.routeCandidate(now, cached: false), isFalse);
    },
  );

  test(
    'registry channels fail independently and retain the original source as last known',
    () async {
      var fail = false;
      final api = AuthApi(
        storage: MemoryTokens(),
        readerStorage: MemoryReaderStorage(),
        client: MockClient((r) async {
          final kind = r.url.queryParameters['kind'];
          if (fail && kind == 'road') return http.Response('{}', 503);
          return http.Response(
            jsonEncode({
              'items': [resource(kind: kind!)],
              'total': 1,
            }),
            200,
          );
        }),
      );
      final controller = ResponseResourceController(api);
      controller.setOwner(1);
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect(controller.items['road']!.length, 1);
      fail = true;
      await controller.refresh();
      expect(controller.cached['road'], isTrue);
      expect(controller.errors['road'], contains('last known'));
      expect(controller.items['road']!.single.name, 'Synthetic shelter');
      expect(controller.cached['shelter'], isFalse);
      controller.setOwner(null);
      expect(controller.items, isEmpty);
      controller.dispose();
      api.dispose();
    },
  );

  test('late registry response cannot leak into another account', () async {
    final pending = Completer<http.Response>();
    final api = AuthApi(
      storage: MemoryTokens(),
      client: MockClient((_) => pending.future),
      readerStorage: MemoryReaderStorage(),
    );
    final controller = ResponseResourceController(api);
    controller.setOwner(1);
    await Future<void>.delayed(Duration.zero);
    controller.setOwner(null);
    pending.complete(
      http.Response(
        jsonEncode({
          'items': [resource()],
          'total': 1,
        }),
        200,
      ),
    );
    await Future<void>.delayed(const Duration(milliseconds: 10));
    expect(controller.items, isEmpty);
    controller.dispose();
    api.dispose();
  });

  testWidgets(
    'map failure and GPS choice retain verified text and contacts without a demonstration destination',
    (tester) async {
      final app = fixtureController();
      await app.login('resident@example.com', 'password123');
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: const Scaffold(
              body: SingleChildScrollView(child: ShelterExplorer()),
            ),
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 30));
      app.resources.items['shelter'] = [ResponseResource.fromJson(resource())];
      app.resources.cached['shelter'] = false;
      app.resources.checkedAt['shelter'] = DateTime.now();
      app.resources.errors.remove('shelter');
      app.resources.notifyListeners();
      await tester.pump();
      expect(find.textContaining('Synthetic entrance address'), findsOneWidget);
      expect(find.textContaining('TEST-ONLY-CONTACT'), findsOneWidget);
      expect(
        find.textContaining('do not establish flood-safe'),
        findsOneWidget,
      );
      expect(find.textContaining('UCU Gym'), findsNothing);
      expect(find.textContaining('current space unknown'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
      await tester.pump();
    },
  );

  testWidgets(
    'unverified content is withheld and expired verified content stays explicitly historical',
    (tester) async {
      Future<void> mount(ResponseResource r) async {
        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.light,
            home: Scaffold(
              body: SingleChildScrollView(
                child: ResourceInstructions(resource: r, cached: true),
              ),
            ),
          ),
        );
      }

      await mount(
        ResponseResource.fromJson(resource(verification: 'unverified')),
      );
      expect(find.textContaining('TEST-ONLY-CONTACT'), findsNothing);
      expect(find.textContaining('withheld'), findsOneWidget);
      await mount(
        ResponseResource.fromJson(
          resource(
            expires: DateTime.now().subtract(const Duration(seconds: 1)),
          ),
        ),
      );
      expect(
        find.textContaining('LAST KNOWN / CURRENT STATUS UNCONFIRMED'),
        findsOneWidget,
      );
      expect(
        find.textContaining('Previously reviewed instructions'),
        findsOneWidget,
      );
      expect(find.textContaining('TEST-ONLY-CONTACT'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'narrow offline banner and outbox preserve queued versus received distinctions',
    (tester) async {
      tester.view.physicalSize = const Size(320, 800);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final app = fixtureController();
      await app.login('resident@example.com', 'password123');
      app.auth.offlineReader = true;
      await app.sos.send({
        'location': 'Synthetic practice entrance',
        'message': 'Practice only',
        'location_source': 'manual',
      });
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: const Scaffold(
              body: SingleChildScrollView(
                child: Column(
                  children: [OfflineReaderBanner(), SosOutboxPanel()],
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pump();
      expect(
        find.text('OFFLINE READER · LAST KNOWN · NOT LIVE'),
        findsOneWidget,
      );
      expect(find.text('QUEUED ON DEVICE · NOT SENT'), findsOneWidget);
      expect(
        find.textContaining('Last confirmed server receipt'),
        findsNothing,
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
      await tester.pump();
    },
  );

  for (final scenario in ['GPS denial', 'route failure']) {
    testWidgets('$scenario retains verified source instructions and contacts', (
      tester,
    ) async {
      final app = fixtureController();
      await app.login('resident@example.com', 'password123');
      Future<Position> capture() async {
        if (scenario == 'GPS denial') {
          throw const AccountException('Permission denied');
        }
        return Position(
          latitude: 15.97,
          longitude: 120.56,
          timestamp: DateTime.now(),
          accuracy: 5,
          altitude: 0,
          altitudeAccuracy: 0,
          heading: 0,
          headingAccuracy: 0,
          speed: 0,
          speedAccuracy: 0,
        );
      }

      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: Scaffold(
              body: SingleChildScrollView(
                child: ShelterExplorer(captureLocation: capture),
              ),
            ),
          ),
        ),
      );
      await tester.pump();
      app.resources.items['shelter'] = [ResponseResource.fromJson(resource())];
      app.resources.cached['shelter'] = false;
      app.resources.checkedAt['shelter'] = DateTime.now();
      app.resources.errors.remove('shelter');
      app.resources.notifyListeners();
      await tester.pump();
      await tester.ensureVisible(find.text('Select this shelter on map'));
      await tester.tap(find.text('Select this shelter on map'));
      await tester.pump();
      await tester.ensureVisible(
        find.text('Use GPS for generic walking directions'),
      );
      await tester.tap(find.text('Use GPS for generic walking directions'));
      await tester.pump();
      if (scenario == 'route failure') {
        final map = tester.widget<AgapayGoogleMap>(
          find.byType(AgapayGoogleMap),
        );
        expect(map.route, isNotNull);
        map.onRouteUpdate!(
          AgapayGoogleMapRouteUpdate(id: map.route!.id, status: 'error'),
        );
        await tester.pump();
        expect(
          find.textContaining('Route unavailable. The text instructions'),
          findsOneWidget,
        );
      } else {
        expect(
          find.textContaining('GPS unavailable. Use the shelter address'),
          findsOneWidget,
        );
      }
      expect(find.textContaining('TEST-ONLY-CONTACT'), findsOneWidget);
      expect(
        find.textContaining('Synthetic reviewed entrance instructions'),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
      await tester.pump();
    });
  }
}
