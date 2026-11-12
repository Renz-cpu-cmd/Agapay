import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:geolocator/geolocator.dart';
import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/controllers/sos_controller.dart';
import 'package:agapay_mobile/controllers/response_resource_controller.dart';
import 'package:agapay_mobile/models/response_resource.dart';
import 'package:agapay_mobile/models/account.dart';
import 'package:agapay_mobile/screens/sos/sos_screen.dart';
import 'package:agapay_mobile/screens/map/map_screen.dart';
import 'package:agapay_mobile/widgets/maps/agapay_google_map.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:agapay_mobile/widgets/common/sos_response_activity.dart';
import 'support/accounts.dart';
import 'response_resources_test.dart' show resource;

AuthApi apiWith(Future<http.Response> Function(http.Request) callback) =>
    AuthApi(
      client: MockClient(callback),
      storage: MemoryTokens(),
      readerStorage: MemoryReaderStorage(),
    );
Future<void> drain() => Future<void>.delayed(Duration.zero);

void main() {
  setUpAll(() async {
    if (Platform.environment['AGAPAY_CAPTURE_RESIDENT_RESPONSE_UI'] == null) {
      return;
    }
    for (final family in ['Inter', 'Outfit', 'JetBrainsMono']) {
      await (FontLoader(
        family,
      )..addFont(rootBundle.load('assets/fonts/$family.ttf'))).load();
    }
    await (FontLoader(
      'MaterialIcons',
    )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
  });
  test(
    'a mismatched send or lookup receipt cannot confirm a different request',
    () async {
      var sends = 0;
      final api = apiWith((r) async {
        if (r.method == 'GET') {
          return http.Response('{"items":[],"total":0}', 200);
        }
        final wrong = practiceSos(
          fields: {
            ...jsonDecode(r.body) as Map<String, dynamic>,
            'request_id': 'different-reference',
          },
        );
        if (r.url.path.endsWith('/receipt')) {
          return http.Response(
            jsonEncode({'receipt': 'received', 'item': wrong}),
            200,
          );
        }
        sends++;
        return http.Response(jsonEncode(wrong), 201);
      });
      final c = SosController(api, storage: MemorySosDrafts());
      await c.setOwner(1);
      expect(
        await c.send({
          'location': 'Synthetic entrance',
          'message': 'Practice',
          'location_source': 'manual',
        }),
        isNull,
      );
      final original = c.pending!['request_id'];
      expect(c.pendingState, 'unknown');
      expect(c.lastSent, isNull);
      await c.refresh();
      expect(c.pending!['request_id'], original);
      expect(c.lastSent, isNull);
      expect(sends, 1);
      c.dispose();
      api.dispose();
    },
  );
  test(
    'resource area changes, paging, pause and source age cannot manufacture current availability',
    () async {
      final delayed = Completer<http.Response>();
      final paths = <Uri>[];
      var fail = false;
      final api = apiWith((r) async {
        paths.add(r.url);
        final kind = r.url.queryParameters['kind']!,
            area = r.url.queryParameters['area_id'];
        if (area == 'A' && kind == 'shelter') return delayed.future;
        if (fail) return http.Response('{}', 503);
        return http.Response(
          jsonEncode({
            'items': [
              {
                ...resource(kind: kind),
                'id': '${area ?? 'ALL'}-${r.url.queryParameters['offset']}',
                'area_ids': [area ?? 'ALL'],
              },
            ],
            'total': 150,
          }),
          200,
        );
      });
      final c = ResponseResourceController(api)..setOwner(1);
      await drain();
      c.setArea('A');
      await drain();
      c.setArea('B');
      await drain();
      expect(c.items['shelter']!.single.id, 'B-0');
      delayed.complete(
        http.Response(
          jsonEncode({
            'items': [
              {
                ...resource(),
                'area_ids': ['A'],
              },
            ],
            'total': 1,
          }),
          200,
        ),
      );
      await drain();
      expect(c.items['shelter']!.single.id, 'B-0');
      await c.refresh(kind: 'shelter', offset: 100);
      expect(c.items['shelter']!.single.id, 'B-100');
      expect(paths.last.queryParameters['area_id'], 'B');
      final checked = c.checkedAt['shelter'];
      fail = true;
      await c.refresh(kind: 'shelter');
      expect(c.checkedAt['shelter'], checked);
      expect(c.isCurrent('shelter'), isFalse);
      c.setForeground(false);
      expect(c.isCurrent('road'), isFalse);
      c.setForeground(true);
      await drain();
      expect(c.isCurrent('shelter'), isFalse);
      c.setOwner(null);
      expect(c.items, isEmpty);
      c.dispose();
      api.dispose();
    },
  );
  testWidgets(
    'response ownership and earlier actions require recorded evidence',
    (tester) async {
      final paths = <Uri>[];
      var holdResume = false;
      final resumedResponse = Completer<http.Response>();
      final app = AppController(
        locationSource: TestLocationSource(),
        preferenceStorage: MemoryProductPreferences(),
        sosStorage: MemorySosDrafts(),
        authApi: apiWith((r) async {
          paths.add(r.url);
          if (holdResume) return resumedResponse.future;
          return http.Response(
            jsonEncode({
              'mode': 'drill',
              'operational_enabled': false,
              'started': true,
              'phase': 'ASSIGNED',
              'coordinator_name': 'Synthetic coordinator',
              'responder_name': 'Synthetic participant',
              'has_more_events': !r.url.hasQuery,
              'next_before_event_id': 10,
              'events': [
                {
                  'id': r.url.hasQuery ? 9 : 10,
                  'created_at': DateTime.now().toUtc().toIso8601String(),
                  'message': r.url.hasQuery
                      ? 'Earlier recorded action'
                      : 'Assignment recorded; dispatch not accepted',
                },
              ],
            }),
            200,
          );
        }),
      );
      app.user = Account.fromJson(resident());
      app.tab = AppTab.sos;
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: const Scaffold(
              body: SingleChildScrollView(child: SosResponseActivity(sosId: 1)),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Coordinator: Synthetic coordinator'), findsOneWidget);
      await tester.ensureVisible(find.text('Earlier recorded actions'));
      await tester.tap(find.text('Earlier recorded actions'));
      await tester.pumpAndSettle();
      expect(paths.last.queryParameters['before_event_id'], '10');
      expect(find.textContaining('Earlier recorded action'), findsWidgets);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      await tester.pump();
      final reads = paths.length;
      await tester.pump(const Duration(seconds: 6));
      expect(paths.length, reads);
      holdResume = true;
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump();
      expect(paths.length, reads + 1);
      expect(find.textContaining('LAST KNOWN OWNERSHIP'), findsOneWidget);
      resumedResponse.complete(
        http.Response(
          '{"mode":"drill","operational_enabled":false,"started":true,"phase":"ASSIGNED","events":[]}',
          200,
        ),
      );
      await tester.pumpAndSettle();
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );
  testWidgets(
    'stations without coordinates remain usable in the list without loading Maps',
    (tester) async {
      final app = fixtureController(
        monitoringChanges: {'latitude': null, 'longitude': null},
      );
      await app.login('resident@example.com', 'synthetic');
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: const Scaffold(body: MapScreen()),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Test Deployed Station'), findsOneWidget);
      expect(find.text('Coordinates unavailable · no map pin'), findsOneWidget);
      expect(find.byType(AgapayGoogleMap), findsNothing);
      await tester.ensureVisible(
        find.widgetWithText(TextButton, 'STATION_001'),
      );
      await tester.tap(find.widgetWithText(TextButton, 'STATION_001'));
      expect(app.monitoring.primary!.id, 'STATION_001');
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );
  testWidgets(
    'cancelled GPS capture cannot fill a later form and live sharing remains opt-in',
    (tester) async {
      final app = fixtureController();
      await app.login('resident@example.com', 'synthetic');
      app.navigate(AppTab.sos);
      final pending = Completer<Position>();
      var captures = 0;
      Position fix() => Position(
        latitude: 15.97,
        longitude: 120.57,
        timestamp: DateTime.now(),
        accuracy: 8,
        altitude: 0,
        altitudeAccuracy: 0,
        heading: 0,
        headingAccuracy: 0,
        speed: 0,
        speedAccuracy: 0,
      );
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: Scaffold(
              body: SosScreen(
                captureLocation: () {
                  captures++;
                  return captures == 1 ? pending.future : Future.value(fix());
                },
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('START SOS'));
      final startButton = tester.widget<FilledButton>(
        find.ancestor(
          of: find.text('START SOS'),
          matching: find.byType(FilledButton),
        ),
      );
      expect(startButton.style!.shape!.resolve({}), isA<CircleBorder>());
      expect(app.sos.items, isEmpty);
      await tester.tap(find.text('START SOS'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('USE MY DEVICE LOCATION'));
      await tester.tap(find.text('USE MY DEVICE LOCATION'));
      await tester.pump();
      await tester.ensureVisible(find.text('CANCEL'));
      await tester.tap(find.text('CANCEL'));
      await tester.pumpAndSettle();
      pending.complete(fix());
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('START SOS'));
      await tester.tap(find.text('START SOS'));
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<TextField>(find.byKey(const ValueKey('sos-latitude')))
            .controller!
            .text,
        isEmpty,
      );
      expect(find.byType(SwitchListTile), findsNothing);
      await tester.ensureVisible(find.text('USE MY DEVICE LOCATION'));
      await tester.tap(find.text('USE MY DEVICE LOCATION'));
      await tester.pumpAndSettle();
      expect(
        tester.widget<SwitchListTile>(find.byType(SwitchListTile)).value,
        isFalse,
      );
      expect(app.sos.items, isEmpty);
      expect(app.sos.pending, isNull);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );
  for (final dark in [false, true]) {
    testWidgets(
      'receipt, location consent and list-first resources remain truthful in both themes dark=$dark',
      (tester) async {
        tester.view.physicalSize = const Size(390, 844);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final app = fixtureController();
        await app.login('resident@example.com', 'synthetic');
        app.navigate(AppTab.sos);
        final boundary = GlobalKey();
        Future<void> mount(Widget screen) async {
          await tester.pumpWidget(
            AppScope(
              controller: app,
              child: MaterialApp(
                theme: dark ? AppTheme.dark : AppTheme.light,
                home: RepaintBoundary(
                  key: boundary,
                  child: Scaffold(body: screen),
                ),
              ),
            ),
          );
          await tester.pumpAndSettle();
        }

        Future<void> capture(String name) async {
          final path =
              Platform.environment['AGAPAY_CAPTURE_RESIDENT_RESPONSE_UI'];
          if (path == null) return;
          await tester.runAsync(() async {
            final image =
                await (boundary.currentContext!.findRenderObject()!
                        as RenderRepaintBoundary)
                    .toImage(pixelRatio: 1);
            final bytes = await image.toByteData(
              format: ui.ImageByteFormat.png,
            );
            await Directory(path).create(recursive: true);
            await File(
              '$path/$name-${dark ? 'dark' : 'light'}.png',
            ).writeAsBytes(bytes!.buffer.asUint8List());
            image.dispose();
          });
        }

        app.auth.offlineReader = true;
        await app.sos.send({
          'location': 'Synthetic queued entrance',
          'message': 'Practice only',
          'location_source': 'manual',
        });
        await mount(const SosScreen());
        expect(find.text('QUEUED ON DEVICE · NOT SENT'), findsOneWidget);
        expect(find.text('REQUEST RECEIVED'), findsNothing);
        await capture('sos-queued');
        app.auth.offlineReader = false;
        await app.sos.send(app.sos.pending!);
        await app.sos.refresh();
        await tester.pumpAndSettle();
        expect(find.text('REQUEST RECEIVED'), findsOneWidget);
        expect(find.textContaining('Request reference:'), findsOneWidget);
        await capture('sos-received');
        await tester.ensureVisible(find.text('TEST REQUEST #1'));
        await tester.tap(find.text('TEST REQUEST #1'));
        await tester.pumpAndSettle();
        expect(
          find.text('Live updates off; request location retained'),
          findsOneWidget,
        );
        app.auth.onExpired?.call();
        await tester.pumpAndSettle();
        expect(find.text('Synthetic queued entrance'), findsNothing);
        await tester.pumpWidget(const SizedBox.shrink());
        app.dispose();
        final maps = fixtureController();
        await maps.login('resident@example.com', 'synthetic');
        maps.navigate(AppTab.map);
        // Reuse the same mounted app scope for both list surfaces.
        await tester.pumpWidget(
          AppScope(
            controller: maps,
            child: MaterialApp(
              theme: dark ? AppTheme.dark : AppTheme.light,
              home: RepaintBoundary(
                key: boundary,
                child: const Scaffold(body: MapScreen()),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.byType(AgapayGoogleMap), findsOneWidget);
        await tester.ensureVisible(find.text('Hide station map'));
        await tester.tap(find.text('Hide station map'));
        await tester.pumpAndSettle();
        expect(find.byType(AgapayGoogleMap), findsNothing);
        await capture('stations');
        maps.resources.items['shelter'] = [
          ResponseResource.fromJson(resource()),
          ResponseResource.fromJson({
            ...resource(state: 'full'),
            'id': 'FULL',
            'data': {
              ...(resource(state: 'full')['data'] as Map),
              'name': 'Synthetic full shelter',
            },
          }),
        ];
        maps.resources.checkedAt['shelter'] = DateTime.now();
        maps.resources.cached['shelter'] = false;
        maps.resources.errors.remove('shelter');
        maps.resources.totals['shelter'] = 2;
        maps.navigate(AppTab.map, evacuation: true);
        await tester.pumpAndSettle();
        expect(find.textContaining('current space unknown'), findsWidgets);
        expect(find.byType(AgapayGoogleMap), findsNothing);
        await capture('shelters');
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox.shrink());
        maps.dispose();
      },
    );
  }
}
