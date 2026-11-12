import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/screens/profile/privacy_screen.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'support/accounts.dart';

void main() {
  testWidgets(
    'privacy requires an explicit request, clears password and distinguishes review from erasure',
    (tester) async {
      var posts = 0;
      final app = AppController(
        locationSource: TestLocationSource(),
        preferenceStorage: MemoryProductPreferences(),
        sosStorage: MemorySosDrafts(),
        authApi: AuthApi(
          readerStorage: MemoryReaderStorage(),
          storage: MemoryTokens(),
          client: MockClient((request) async {
            final path = request.url.path;
            if (path.endsWith('/login')) {
              return http.Response(
                jsonEncode({
                  'user': resident(),
                  'access_token': 'synthetic-session',
                }),
                200,
              );
            }
            if (path.endsWith('/preferences')) {
              return http.Response(
                '{"revision":0,"notifications_enabled":false,"locale":"en"}',
                200,
              );
            }
            if (path.endsWith('/areas')) return http.Response('[]', 200);
            if (path.endsWith('/privacy/notice')) {
              return http.Response(
                jsonEncode({
                  'deployment': {'status': 'unapproved_development'},
                  'policy': {
                    'resolved_sos_location_days': 7,
                    'resolved_sos_narrative_days': 30,
                  },
                  'data': ['Account'],
                  'recipients': ['Configured providers'],
                  'limits': 'Unapproved development policy.',
                }),
                200,
              );
            }
            if (path.endsWith('/privacy/cases')) {
              if (request.method == 'GET') return http.Response('[]', 200);
              posts++;
              expect(
                jsonDecode(request.body)['current_password'],
                'synthetic-owner-password',
              );
              return http.Response(
                '{"id":"case-synthetic","kind":"access","state":"OPEN","due_at":"2026-11-06T00:00:00Z"}',
                202,
              );
            }
            if (path.endsWith('/privacy/export')) {
              return http.Response(
                '{"account":{"name":"Synthetic owner"},"sos":[],"next_after":null}',
                200,
              );
            }
            return http.Response('{}', 503);
          }),
        ),
      );
      await tester.runAsync(
        () => app.login('resident@example.com', 'synthetic-owner-password'),
      );
      tester.view.physicalSize = const Size(320, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: const PrivacyScreen(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(posts, 0);
      expect(find.text('Unapproved development policy'), findsOneWidget);
      await tester.enterText(
        find.byType(TextField),
        'synthetic-owner-password',
      );
      final submit = find.text('Record privacy request');
      await tester.ensureVisible(submit);
      await tester.tap(submit);
      await tester.pumpAndSettle();
      expect(posts, 1);
      expect(
        tester.widget<TextField>(find.byType(TextField)).controller!.text,
        isEmpty,
      );
      expect(
        find.textContaining('not confirmation of erasure'),
        findsOneWidget,
      );
      await tester.enterText(
        find.byType(TextField),
        'synthetic-owner-password',
      );
      final export = find.text('View my record page');
      await tester.ensureVisible(export);
      await tester.tap(export);
      await tester.pumpAndSettle();
      expect(find.byType(SelectableText), findsOneWidget);
      await tester.ensureVisible(find.text('Clear record copy from screen'));
      await tester.tap(find.text('Clear record copy from screen'));
      await tester.pump();
      expect(find.byType(SelectableText), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );
}
