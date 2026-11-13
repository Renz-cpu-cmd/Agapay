import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/controllers/official_notice_controller.dart';
import 'package:agapay_mobile/screens/home/home_screen.dart';
import 'package:agapay_mobile/screens/alerts/alerts_screen.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:agapay_mobile/widgets/common/resident_decisions.dart';
import 'package:agapay_mobile/models/response_resource.dart';
import 'support/accounts.dart';
import 'alert_governance_test.dart' show noticeJson;

Future<void> drain() => Future<void>.delayed(Duration.zero);
Map<String, dynamic> operationalNotice(
  String area, {
  String id = 'current',
  String type = 'Alert',
}) => {
  ...noticeJson(),
  'id': id,
  'status': 'Actual',
  'area_ids': [area],
  'area_names': ['Synthetic selected area'],
  'message_type': type,
  'reference_id': type == 'Alert' ? null : 'previous',
};
http.Response response(
  Uri uri,
  DateTime at,
  List<Map<String, dynamic>> items,
) => http.Response(
  jsonEncode({
    'items': items,
    'checked_at': at.toUtc().toIso8601String(),
    'has_more': false,
    'scope': {
      'area_id': uri.queryParameters['area_id'],
      'status': 'Actual',
      'current_only': uri.queryParameters['current_only'] == 'true',
    },
  }),
  200,
);
AuthApi apiWith(Future<http.Response> Function(http.Request) handle) => AuthApi(
  storage: MemoryTokens(),
  readerStorage: MemoryReaderStorage(),
  client: MockClient(handle),
);

void main() {
  setUpAll(() async {
    if (Platform.environment['AGAPAY_CAPTURE_RESIDENT_UI'] == null) return;
    for (final family in ['Inter', 'Outfit', 'JetBrainsMono']) {
      await (FontLoader(
        family,
      )..addFont(rootBundle.load('assets/fonts/$family.ttf'))).load();
    }
    await (FontLoader(
      'MaterialIcons',
    )..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'))).load();
  });
  test('no selected area cannot fetch or imply area applicability', () async {
    final api = apiWith((_) async => fail('No unscoped operational request'));
    final c = OfficialNoticeController(api)..setScope(1, null);
    await drain();
    expect(c.current.items, isEmpty);
    expect(c.confirmed(c.current), isFalse);
    c.dispose();
    api.dispose();
  });
  test(
    'area/account switches discard late results; history cannot replace home',
    () async {
      final at = DateTime.parse('2026-10-21T00:30:00Z');
      final pending = Completer<http.Response>();
      Uri? delayed;
      final api = apiWith((r) async {
        if (r.url.queryParameters['area_id'] == 'A') {
          delayed = r.url;
          return pending.future;
        }
        return response(r.url, at, [
          operationalNotice(
            'B',
            id: r.url.queryParameters['current_only'] == 'true'
                ? 'head'
                : 'history',
          ),
        ]);
      });
      final c = OfficialNoticeController(api, now: () => at)..setScope(1, 'A');
      await drain();
      c.setScope(2, 'B');
      await drain();
      expect(c.current.items.single.id, 'head');
      pending.complete(response(delayed!, at, [operationalNotice('A')]));
      await drain();
      expect(c.current.items.single.id, 'head');
      await c.refresh(past: true, offset: 50);
      expect(c.history.items.single.id, 'history');
      expect(c.current.items.single.id, 'head');
      c.setScope(null, null);
      expect(c.current.items, isEmpty);
      expect(c.history.items, isEmpty);
      c.dispose();
      api.dispose();
    },
  );
  for (final wrong in ['area', 'exercise', 'scope']) {
    test(
      'mismatched $wrong response cannot supply current instructions',
      () async {
        final at = DateTime.parse('2026-10-21T00:30:00Z');
        final api = apiWith(
          (r) async => response(
            wrong == 'scope'
                ? r.url.replace(
                    queryParameters: {...r.url.queryParameters, 'area_id': 'X'},
                  )
                : r.url,
            at,
            [
              {
                ...operationalNotice(wrong == 'area' ? 'X' : 'A'),
                if (wrong == 'exercise') 'status': 'Test',
              },
            ],
          ),
        );
        final c = OfficialNoticeController(api, now: () => at)
          ..setScope(1, 'A');
        await drain();
        expect(c.current.error, isNotNull);
        expect(c.current.items, isEmpty);
        expect(c.confirmed(c.current), isFalse);
        c.dispose();
        api.dispose();
      },
    );
  }
  test(
    'aging, background pause and failed refresh never renew instructions',
    () async {
      var at = DateTime.parse('2026-10-21T00:30:00Z'), failReads = false;
      final api = apiWith(
        (r) async => failReads
            ? http.Response('{}', 503)
            : response(r.url, at, [operationalNotice('A')]),
      );
      final c = OfficialNoticeController(api, now: () => at)..setScope(1, 'A');
      await drain();
      expect(c.confirmed(c.current), isTrue);
      at = at.add(const Duration(seconds: 91));
      expect(c.confirmed(c.current), isFalse);
      failReads = true;
      await c.refresh();
      expect(c.current.items.single.id, 'current');
      expect(c.confirmed(c.current), isFalse);
      c.setForeground(false);
      c.setForeground(true);
      await drain();
      expect(c.confirmed(c.current), isFalse);
      c.dispose();
      api.dispose();
    },
  );

  testWidgets(
    'conflicted area selection retains the saved scope and requires manual refresh',
    (tester) async {
      var writes = 0;
      final api = apiWith((r) async {
        if (r.url.path.endsWith('/login')) {
          return http.Response(
            jsonEncode({'user': resident(), 'access_token': 'synthetic'}),
            200,
          );
        }
        if (r.url.path.endsWith('/preferences/areas')) {
          return http.Response(
            '[{"id":"A","name":"Area A"},{"id":"B","name":"Area B"}]',
            200,
          );
        }
        if (r.url.path.endsWith('/preferences')) {
          if (r.method == 'PATCH') {
            writes++;
            return http.Response(
              '{"detail":"Area changed; refresh and review"}',
              409,
            );
          }
          return http.Response(
            '{"revision":1,"notifications_enabled":false,"locale":"en","resident_area_id":"A","resident_area_name":"Area A"}',
            200,
          );
        }
        return http.Response('{}', 503);
      });
      final app = AppController(
        authApi: api,
        locationSource: TestLocationSource(),
        preferenceStorage: MemoryProductPreferences(),
        sosStorage: MemorySosDrafts(),
      );
      await app.login('resident@example.com', 'synthetic');
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: const Scaffold(body: ResidentAreaPanel()),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byType(DropdownButtonFormField<String>));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Area B').last);
      await tester.pumpAndSettle();
      expect(writes, 1);
      expect(app.preferences.conflicted, isTrue);
      expect(app.notices.areaId, 'A');
      expect(
        tester
            .widget<DropdownButtonFormField<String>>(
              find.byType(DropdownButtonFormField<String>),
            )
            .initialValue,
        'A',
      );
      await tester.tap(find.text('Refresh area choices'));
      await tester.pumpAndSettle();
      expect(app.preferences.conflicted, isFalse);
      expect(app.notices.areaId, 'A');
      expect(writes, 1);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );

  testWidgets(
    'contact shortcuts expose only reviewed actual references for the selected area',
    (tester) async {
      final app = fixtureController(residentAreaId: 'A');
      await app.login('resident@example.com', 'synthetic');
      ResponseResource reference(String id, String area, String verification) =>
          ResponseResource.fromJson({
            'id': id,
            'kind': 'preparedness',
            'mode': 'Actual',
            'area_ids': [area],
            'issuer_name': 'Synthetic issuer',
            'verified_at': DateTime.now().toUtc().toIso8601String(),
            'expires_at': DateTime.now()
                .add(const Duration(hours: 1))
                .toUtc()
                .toIso8601String(),
            'verification': verification,
            'data': {
              'name': id,
              'contacts': [
                {
                  'name': 'Contact $id',
                  'contact': 'synthetic-$id',
                  'hours': 'Synthetic hours',
                },
              ],
            },
          });
      app.resources.items['preparedness'] = [
        reference('selected', 'A', 'verified'),
        reference('other', 'B', 'verified'),
        reference('unreviewed', 'A', 'unverified'),
      ];
      app.resources.cached['preparedness'] = true;
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: const Scaffold(
              body: SingleChildScrollView(child: ResidentHelpPanel()),
            ),
          ),
        ),
      );
      await tester.pump();
      expect(find.textContaining('synthetic-selected'), findsOneWidget);
      expect(find.textContaining('synthetic-other'), findsNothing);
      expect(find.textContaining('synthetic-unreviewed'), findsNothing);
      expect(
        find.textContaining('LAST KNOWN · confirm availability'),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );

  for (final dark in [false, true]) {
    for (final scale in [1.0, 2.0]) {
      testWidgets(
        'home keeps readings reachable without duplicate panels dark=$dark scale=$scale',
        (tester) async {
          tester.view.physicalSize = Size(scale == 1 ? 360 : 320, 844);
          tester.view.devicePixelRatio = 1;
          addTearDown(tester.view.resetPhysicalSize);
          addTearDown(tester.view.resetDevicePixelRatio);
          final app = fixtureController(emptyStations: true);
          await app.login('resident@example.com', 'synthetic-password');
          final boundary = GlobalKey();
          await tester.pumpWidget(
            AppScope(
              controller: app,
              child: MaterialApp(
                theme: dark ? AppTheme.dark : AppTheme.light,
                builder: (context, child) => MediaQuery(
                  data: MediaQuery.of(
                    context,
                  ).copyWith(textScaler: TextScaler.linear(scale)),
                  child: child!,
                ),
                home: RepaintBoundary(
                  key: boundary,
                  child: const Scaffold(
                    body: HomeScreen(),
                    bottomNavigationBar: SizedBox(height: 80),
                  ),
                ),
              ),
            ),
          );
          await tester.pump(const Duration(milliseconds: 100));
          expect(find.text('UNKNOWN'), findsOneWidget);
          expect(
            find.textContaining('Device heartbeat: unknown'),
            findsOneWidget,
          );
          expect(find.textContaining('Sensor: unknown'), findsOneWidget);
          expect(find.text('Help and contacts'), findsNothing);
          if (scale == 1) {
            expect(tester.getRect(find.text('cm')).bottom, lessThan(764));
          }
          final capture = Platform.environment['AGAPAY_CAPTURE_RESIDENT_UI'];
          if (capture != null) {
            await tester.runAsync(
              () => precacheImage(
                const AssetImage('assets/images/agapay-logo.png'),
                boundary.currentContext!,
              ),
            );
            await tester.pump();
            await tester.runAsync(() async {
              final image =
                  await (boundary.currentContext!.findRenderObject()!
                          as RenderRepaintBoundary)
                      .toImage(pixelRatio: 1);
              final bytes = await image.toByteData(
                format: ui.ImageByteFormat.png,
              );
              await Directory(capture).create(recursive: true);
              await File(
                '$capture/home-compact-${dark ? 'dark' : 'light'}-$scale.png',
              ).writeAsBytes(bytes!.buffer.asUint8List());
              image.dispose();
            });
          }
          await tester.tap(find.byKey(const ValueKey('home-area-selector')));
          await tester.pumpAndSettle();
          expect(find.text('Your area'), findsOneWidget);
          expect(find.text('No verified area selected'), findsOneWidget);
          expect(tester.takeException(), isNull);
          await tester.pumpWidget(const SizedBox.shrink());
          app.dispose();
        },
      );
    }
    testWidgets(
      'decision hierarchy, cancelled advice and operational separation dark=$dark',
      (tester) async {
        tester.view.physicalSize = const Size(390, 844);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final at = DateTime.parse('2026-10-21T00:30:00Z');
        final app = fixtureController(
          residentAreaId: 'APP',
          observationClock: () => at,
          emptyStations: true,
          officialNotices: [
            operationalNotice('APP', type: 'Cancel'),
            {...noticeJson(), 'headline': 'PRIVATE EXERCISE EXAMPLE'},
          ],
        );
        await app.login('resident@example.com', 'synthetic-password');
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
          await tester.pump(const Duration(milliseconds: 100));
        }

        await mount(const HomeScreen());
        if (Platform.environment['AGAPAY_CAPTURE_RESIDENT_UI'] != null) {
          await tester.runAsync(
            () => precacheImage(
              const AssetImage('assets/images/agapay-logo.png'),
              boundary.currentContext!,
            ),
          );
          await tester.pump();
        }
        final headings = [
          'Latest area advisories',
          'WATER DEPTH',
          'WATER DEPTH TREND',
          'WATER-DEPTH FORECAST',
        ];
        for (var i = 1; i < headings.length; i++) {
          expect(
            tester.getTopLeft(find.text(headings[i])).dy,
            greaterThan(tester.getTopLeft(find.text(headings[i - 1])).dy),
          );
        }
        expect(find.textContaining('CANCELLED ·'), findsOneWidget);
        expect(find.text('Action from the issuer'), findsNothing);
        expect(find.text('PRIVATE EXERCISE EXAMPLE'), findsNothing);
        expect(find.text('UNKNOWN'), findsOneWidget);
        expect(find.text('Help and contacts'), findsNothing);
        expect(find.text('AGAPAY'), findsOneWidget);
        expect(
          find.byKey(const ValueKey('home-area-selector')),
          findsOneWidget,
        );
        expect(find.text('Help and contacts'), findsNothing);
        expect(find.text('Configuration:'), findsNothing);
        final capture = Platform.environment['AGAPAY_CAPTURE_RESIDENT_UI'];
        Future<void> screenshot(String name) async {
          if (capture == null) return;
          await tester.runAsync(() async {
            final image =
                await (boundary.currentContext!.findRenderObject()!
                        as RenderRepaintBoundary)
                    .toImage(pixelRatio: 1);
            final bytes = await image.toByteData(
              format: ui.ImageByteFormat.png,
            );
            await Directory(capture).create(recursive: true);
            await File(
              '$capture/$name-${dark ? 'dark' : 'light'}.png',
            ).writeAsBytes(bytes!.buffer.asUint8List());
            image.dispose();
          });
        }

        await screenshot('home');
        await tester.ensureVisible(
          find.text('Area advisories and verified contacts'),
        );
        await tester.tap(find.text('Area advisories and verified contacts'));
        await tester.pumpAndSettle();
        await tester.ensureVisible(find.text('Verified contacts'));
        await tester.tap(find.text('Verified contacts'));
        await tester.pumpAndSettle();
        expect(find.text('Help and contacts'), findsOneWidget);
        final shelters = find.text('Shelters and road reports').last;
        await tester.ensureVisible(shelters);
        await tester.tap(shelters);
        await tester.pumpAndSettle();
        expect(app.tab, AppTab.map);
        expect(find.text('Help and contacts'), findsNothing);
        await mount(const AlertsScreen());
        expect(find.text('Advisories for your area'), findsOneWidget);
        expect(find.textContaining('cancelled'), findsWidgets);
        await screenshot('alerts');
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox.shrink());
        app.dispose();
      },
    );
  }
}
