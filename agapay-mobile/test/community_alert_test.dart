import 'dart:async';
import 'dart:convert';
import 'package:agapay_mobile/controllers/app_controller.dart';
import 'package:agapay_mobile/controllers/community_alert_controller.dart';
import 'package:agapay_mobile/core/theme/app_theme.dart';
import 'package:agapay_mobile/models/alert_level.dart';
import 'package:agapay_mobile/models/community_alert.dart';
import 'package:agapay_mobile/screens/alerts/alerts_screen.dart';
import 'package:agapay_mobile/screens/alerts/alert_details_screen.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/accounts.dart';
import 'support/community_alerts.dart';

AuthApi apiFor(Future<http.Response> Function(http.Request) handler) =>
    AuthApi(storage: MemoryTokens(), client: MockClient(handler));
http.Response ok(Object body) => http.Response(jsonEncode(body), 200);
Future<void> drain() => Future<void>.delayed(Duration.zero);

void main() {
  for (final severity in ['WARNING', 'EVACUATE']) {
    test('parses active $severity with UTC dates and nullable area', () {
      final a = CommunityAlert.fromJson({
        ...communityEpisode(severity: severity),
        'barangay': null,
        'municipality': null,
      });
      expect(a.severity.label, severity);
      expect(a.status, CommunityAlertStatus.active);
      expect(a.latestDepthCm, 102.3);
      expect(a.area, '');
      expect(a.triggeredAt, DateTime.utc(2026, 9, 23, 1, 2, 3));
      expect(communityAlertTime(a.triggeredAt), '2026-09-23 09:02:03 PHT');
    });
  }
  test('resolved peak, recovery, and sanitized direct transition parsing', () {
    final d = CommunityAlertDetail.fromJson(communityDetail(resolved: true));
    expect(d.episode.severity, AlertLevel.evacuate);
    expect(d.episode.latestDepthCm, 35.2);
    expect(d.episode.resolvedAt, isNotNull);
    expect(d.transitions.total, 2);
    expect(d.transitions.items.first.previousSeverity, AlertLevel.normal);
    expect(d.transitions.items.first.newSeverity, AlertLevel.evacuate);
    expect(d.transitions.items.last.newSeverity, AlertLevel.normal);
  });
  for (final change in <String, Object?>{
    'severity': 'UNKNOWN',
    'status': 'UNKNOWN',
    'source': 'physical',
    'latest_depth_cm': double.nan,
    'triggered_at': '2026-09-23T01:00:00',
    'resolved_at': '2026-09-23T01:00:00Z',
  }.entries) {
    test('rejects unsafe ${change.key} rather than normalizing to NORMAL', () {
      expect(
        () => CommunityAlert.fromJson({
          ...communityEpisode(),
          change.key: change.value,
        }),
        throwsFormatException,
      );
    });
  }
  test('rejects NORMAL incident severity and duplicate page IDs', () {
    expect(
      () => CommunityAlert.fromJson(communityEpisode(severity: 'NORMAL')),
      throwsFormatException,
    );
    expect(
      () => CommunityAlertPage.fromJson({
        'items': [communityEpisode(), communityEpisode()],
        'total': 2,
      }),
      throwsFormatException,
    );
  });

  test(
    'owner loads active; history, list pages and timeline pages stay bounded',
    () async {
      final calls = <Uri>[];
      final api = apiFor((request) async {
        calls.add(request.url);
        final offset = request.url.queryParameters['offset'] ?? '0';
        return ok(
          request.url.path.endsWith('/501')
              ? communityDetail()
              : communityPage(id: offset == '0' ? 501 : 502, total: 51),
        );
      });
      final c = CommunityAlertController(api);
      c.setOwner(1);
      expect(c.active.loading, isTrue);
      await drain();
      expect(c.active.data!.items.first.id, 501);
      await c.refreshHistory();
      await c.refreshHistory(offset: 50);
      expect(c.history.data!.items.map((a) => a.id), [502]);
      expect(c.history.data!.total, 51);
      await c.refreshActive(offset: 50);
      expect(c.active.data!.items.single.id, 502);
      await c.openDetail(501, offset: 50);
      expect(c.detail.data!.transitions.total, 1);
      expect(
        calls.every((u) => u.path.startsWith('/api/community-alerts')),
        isTrue,
      );
      expect(
        calls
            .where((u) => !u.path.endsWith('/501'))
            .every((u) => u.queryParameters['limit'] == '50'),
        isTrue,
      );
      expect(calls.last.queryParameters, {
        'transition_limit': '50',
        'transition_offset': '50',
      });
      c.dispose();
      api.dispose();
    },
  );

  test(
    'offline and malformed responses clear prior data, never claim normal',
    () async {
      var fail = false, malformed = false;
      final api = apiFor(
        (_) async => fail
            ? http.Response('{}', 503)
            : ok(
                malformed
                    ? {
                        'items': [{}],
                        'total': 1,
                      }
                    : communityPage(),
              ),
      );
      final c = CommunityAlertController(api)..setOwner(1);
      await drain();
      expect(c.active.data, isNotNull);
      fail = true;
      await c.refreshActive();
      expect(c.active.data, isNull);
      expect(c.active.error, 'Alert service is currently unavailable.');
      fail = false;
      malformed = true;
      await c.refreshActive();
      expect(c.active.data, isNull);
      expect(c.active.error, isNotNull);
      c.dispose();
      api.dispose();
    },
  );

  testWidgets(
    'polling never overlaps; logout and disposal suppress late responses',
    (tester) async {
      var count = 0;
      final pending = Completer<http.Response>();
      final api = apiFor((_) {
        count++;
        return pending.future;
      });
      final c = CommunityAlertController(api)..setOwner(1);
      await tester.pump();
      await tester.pump(const Duration(seconds: 11));
      expect(count, 1);
      c.setOwner(null);
      pending.complete(ok(communityPage()));
      await tester.pump();
      expect(c.active.data, isNull);
      expect(c.active.loading, isFalse);
      await tester.pump(const Duration(seconds: 11));
      expect(count, 1);
      c.dispose();
      api.dispose();
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('active polls again after completion; history is not polled', (
    tester,
  ) async {
    final paths = <String>[];
    final api = apiFor((r) async {
      paths.add(r.url.path);
      return ok(communityPage());
    });
    final c = CommunityAlertController(api)..setOwner(1);
    await tester.pump();
    unawaited(c.refreshHistory());
    await tester.pump();
    await tester.pump(const Duration(seconds: 5));
    expect(paths.where((p) => p.endsWith('/active')).length, 2);
    expect(paths.where((p) => p == '/api/community-alerts').length, 1);
    c.dispose();
    api.dispose();
  });

  test(
    'account change discards old result and serializes new owner read',
    () async {
      final pending = Completer<http.Response>();
      var count = 0;
      final api = apiFor((_) {
        count++;
        return count == 1
            ? pending.future
            : Future.value(ok(communityPage(id: 502)));
      });
      final c = CommunityAlertController(api)..setOwner(1);
      await drain();
      c.setOwner(null);
      c.setOwner(2);
      await drain();
      expect(count, 1);
      pending.complete(ok(communityPage()));
      await drain();
      expect(c.active.data!.items.single.id, 502);
      expect(count, 2);
      c.dispose();
      api.dispose();
    },
  );

  test('changing selected episode ignores delayed old detail', () async {
    final pending = Completer<http.Response>();
    final api = apiFor((r) async {
      if (r.url.path.endsWith('/501')) return pending.future;
      if (r.url.path.endsWith('/502')) return ok(communityDetail(id: 502));
      return ok(communityPage());
    });
    final c = CommunityAlertController(api)..setOwner(1);
    await drain();
    final old = c.openDetail(501);
    await drain();
    final latest = c.openDetail(502);
    pending.complete(ok(communityDetail()));
    await old;
    await latest;
    expect(c.detail.data!.episode.id, 502);
    c.dispose();
    api.dispose();
  });

  test(
    'dispose while response pending does not notify disposed listeners',
    () async {
      final pending = Completer<http.Response>();
      final api = apiFor((_) => pending.future);
      final c = CommunityAlertController(api)..setOwner(1);
      await drain();
      c.dispose();
      pending.complete(ok(communityPage()));
      await drain();
      expect(c.active.data, isNull);
      api.dispose();
    },
  );

  test('rejects resolved active feed and mismatched detail ID', () async {
    final api = apiFor(
      (r) async => ok(
        r.url.path.endsWith('/501')
            ? communityDetail(id: 999)
            : communityPage(resolved: true),
      ),
    );
    final c = CommunityAlertController(api)..setOwner(1);
    await drain();
    expect(c.active.data, isNull);
    expect(c.active.error, isNotNull);
    await c.openDetail(501);
    expect(c.detail.data, isNull);
    expect(c.detail.error, isNotNull);
    c.dispose();
    api.dispose();
  });

  for (final end in ['expired', 'logout', 'password']) {
    test(
      '$end integrates with AppController and clears resident alerts',
      () async {
        var expired = false;
        final tokens = MemoryTokens()..value = 'synthetic-session';
        final api = AuthApi(
          storage: tokens,
          client: MockClient((r) async {
            if (r.url.path.startsWith('/api/community-alerts')) {
              expect(r.headers['Authorization'], 'Bearer synthetic-session');
              return expired ? http.Response('{}', 401) : ok(communityPage());
            }
            if (r.url.path == '/api/auth/logout') return http.Response('', 204);
            if (r.url.path == '/api/auth/me') return ok(resident());
            return http.Response('{}', 503);
          }),
        );
        final app = AppController(authApi: api, sosStorage: MemorySosDrafts());
        await app.restoreSession();
        await drain();
        expect(app.communityAlerts.active.data, isNotNull);
        if (end == 'expired') {
          expired = true;
          await app.communityAlerts.refreshActive();
        } else if (end == 'logout') {
          await app.logout();
        } else {
          await app.saveProfile({'password': 'synthetic-test-value'});
        }
        await drain();
        expect(app.signedIn, isFalse);
        expect(app.communityAlerts.active.data, isNull);
        expect(app.communityAlerts.history.data, isNull);
        expect(app.communityAlerts.selectedId, isNull);
        expect(tokens.value, isNull);
        app.dispose();
      },
    );
  }

  for (final state in [
    'loading',
    'error',
    'empty',
    'active',
    'history',
    'empty history',
  ]) {
    testWidgets('Alerts UI $state uses explicit real-data states at 320px', (
      tester,
    ) async {
      tester.view.physicalSize = const Size(320, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final pending = Completer<http.Response>();
      final api = apiFor((r) async {
        if (state == 'loading') return pending.future;
        if (state == 'error') return http.Response('{}', 503);
        if (state.startsWith('empty')) return ok({'items': [], 'total': 0});
        return ok(communityPage(resolved: state == 'history'));
      });
      final app = AppController(authApi: api, sosStorage: MemorySosDrafts());
      app.communityAlerts.setOwner(1);
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.dark,
            home: Scaffold(
              body: AlertsScreen(initialHistory: state.contains('history')),
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.pump();
      if (state == 'loading') {
        expect(find.text('Loading community alerts…'), findsOneWidget);
      }
      if (state == 'error') {
        expect(
          find.text('Alert service is currently unavailable.'),
          findsOneWidget,
        );
        expect(find.text('No active AGAPAY sensor alerts.'), findsNothing);
      }
      if (state == 'empty') {
        expect(find.text('No active AGAPAY sensor alerts.'), findsOneWidget);
      }
      if (state == 'empty history') {
        expect(find.text('No alert history available.'), findsOneWidget);
      }
      if (state == 'active') {
        expect(find.text('Community Test Station'), findsOneWidget);
        expect(find.text('Latest depth: 102.3 cm'), findsOneWidget);
      }
      if (state == 'history') {
        expect(find.text('EVACUATE · Peak tier'), findsOneWidget);
        expect(find.text('Recovery depth: 35.2 cm'), findsOneWidget);
        expect(find.text('Trigger depth: 105.0 cm'), findsOneWidget);
      }
      expect(find.textContaining('unread'), findsNothing);
      expect(find.textContaining('Demo notification'), findsNothing);
      expect(find.text('Resolve'), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
      if (!pending.isCompleted) {
        pending.complete(ok(communityPage()));
        await tester.pump();
      }
    });
  }

  testWidgets(
    'detail renders sanitized direct timeline and qualified safety wording',
    (tester) async {
      final api = apiFor(
        (r) async => ok(
          r.url.path.endsWith('/501') ? communityDetail() : communityPage(),
        ),
      );
      final app = AppController(authApi: api, sosStorage: MemorySosDrafts());
      app.communityAlerts.setOwner(1);
      app.showCommunityAlert(501);
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.dark,
            home: const Scaffold(body: AlertDetailsScreen()),
          ),
        ),
      );
      await tester.pump();
      expect(find.text('NORMAL → EVACUATE'), findsOneWidget);
      expect(
        find.textContaining('official LGU evacuation orders'),
        findsOneWidget,
      );
      expect(find.textContaining('EVACUATE IMMEDIATELY'), findsNothing);
      expect(find.textContaining('Sequence'), findsNothing);
      expect(find.textContaining('Rainfall'), findsNothing);
      expect(find.textContaining('Demo'), findsNothing);
      await tester.ensureVisible(find.text('VIEW EVACUATION MAP'));
      await tester.tap(find.text('VIEW EVACUATION MAP'));
      await tester.pump();
      expect(app.tab, AppTab.map);
      expect(app.evacuationMap, isTrue);
      expect(app.communityAlerts.selectedId, isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );
}
