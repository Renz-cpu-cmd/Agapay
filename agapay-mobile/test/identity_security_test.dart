import 'dart:convert';
import 'package:agapay_mobile/controllers/app_controller.dart';
import 'package:agapay_mobile/core/theme/app_theme.dart';
import 'package:agapay_mobile/screens/auth/recovery_screen.dart';
import 'package:agapay_mobile/screens/profile/edit_profile_screen.dart';
import 'package:agapay_mobile/screens/profile/account_security_screen.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/accounts.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('account security hides cached sessions after session expiry', (
    tester,
  ) async {
    final app = AppController(
      locationSource: TestLocationSource(),
      preferenceStorage: MemoryProductPreferences(),
      sosStorage: MemorySosDrafts(),
      authApi: AuthApi(
        readerStorage: MemoryReaderStorage(),
        storage: MemoryTokens(),
        client: MockClient((request) async {
          if (request.url.path.endsWith('/login')) {
            return http.Response(
              jsonEncode({'user': resident(), 'access_token': 'test-session'}),
              200,
            );
          }
          if (request.url.path.endsWith('/security')) {
            return http.Response(
              jsonEncode({
                'email_verified': true,
                'sessions': [
                  {
                    'id': 'synthetic-session',
                    'audience': 'mobile_resident',
                    'current': true,
                    'expires_at': '2026-11-01T00:00:00Z',
                  },
                ],
                'devices': [],
              }),
              200,
            );
          }
          if (request.url.path.endsWith('/preferences')) {
            return http.Response(
              '{"revision":0,"notifications_enabled":false,"locale":"en"}',
              200,
            );
          }
          if (request.url.path.endsWith('/areas')) {
            return http.Response('[]', 200);
          }
          return http.Response('{}', 503);
        }),
      ),
    );
    await tester.runAsync(() => app.login('resident@example.com', 'password'));
    await tester.pumpWidget(
      AppScope(
        controller: app,
        child: MaterialApp(
          theme: AppTheme.light,
          home: const AccountSecurityScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.textContaining('mobile_resident'), findsOneWidget);
    await tester.runAsync(() => app.auth.clearLocalSession());
    app.auth.onExpired?.call();
    await tester.pumpAndSettle();
    expect(find.textContaining('mobile_resident'), findsNothing);
    expect(find.text('Session ended. Sign in again.'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    app.dispose();
  });
  testWidgets(
    'recovery requests use verified email workflow and never install a session',
    (tester) async {
      final calls = <http.Request>[];
      final tokens = MemoryTokens();
      final app = AppController(
        locationSource: TestLocationSource(),
        preferenceStorage: MemoryProductPreferences(),
        sosStorage: MemorySosDrafts(),
        authApi: AuthApi(
          readerStorage: MemoryReaderStorage(),
          storage: tokens,
          client: MockClient((request) async {
            calls.add(request);
            if (request.url.path.endsWith('/capabilities')) {
              return http.Response('{"recovery_available":true}', 200);
            }
            return http.Response(
              '{"message":"If eligible, check your email. Sign in again after confirmation."}',
              request.url.path.endsWith('/request') ? 202 : 200,
            );
          }),
        ),
      );
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: const RecoveryScreen(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byType(TextField).at(0),
        'resident@example.com',
      );
      await tester.ensureVisible(find.text('SEND EMAIL CODE'));
      await tester.tap(find.text('SEND EMAIL CODE'));
      await tester.pumpAndSettle();
      final request = calls.firstWhere((r) => r.url.path.endsWith('/request'));
      expect(jsonDecode(request.body), {
        'email': 'resident@example.com',
        'purpose': 'password_reset',
      });
      expect(request.headers.containsKey('Authorization'), isFalse);
      expect(tokens.value, isNull);
      expect(app.signedIn, isFalse);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );
  testWidgets(
    'stale profile clears passwords and cannot retry before manual refresh',
    (tester) async {
      var current = resident(), writes = 0;
      final api = AuthApi(
        readerStorage: MemoryReaderStorage(),
        storage: MemoryTokens(),
        client: MockClient((request) async {
          final path = request.url.path;
          if (path.endsWith('/login')) {
            return http.Response(
              jsonEncode({'user': current, 'access_token': 'test-session'}),
              200,
            );
          }
          if (path.endsWith('/me')) {
            if (request.method == 'PATCH') {
              writes++;
              expect(jsonDecode(request.body)['expected_version'], 1);
              current = {...current, 'version': 2, 'name': 'Newer server name'};
              return http.Response(
                jsonEncode({
                  'detail': {
                    'message': 'Record changed. Refresh manually.',
                    'current': current,
                  },
                }),
                409,
              );
            }
            return http.Response(jsonEncode(current), 200);
          }
          if (path.endsWith('/preferences')) {
            return http.Response(
              '{"revision":0,"notifications_enabled":false,"locale":"en"}',
              200,
            );
          }
          if (path.endsWith('/areas')) return http.Response('[]', 200);
          return http.Response('{}', 503);
        }),
      );
      final app = AppController(
        authApi: api,
        sosStorage: MemorySosDrafts(),
        preferenceStorage: MemoryProductPreferences(),
        locationSource: TestLocationSource(),
      );
      await tester.runAsync(
        () => app.login('resident@example.com', 'password'),
      );
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: const EditProfileScreen(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byType(TextField).at(4),
        'sensitive-current-password',
      );
      await tester.enterText(
        find.byType(TextField).at(5),
        'sensitive-new-password',
      );
      await tester.ensureVisible(find.text('SAVE CHANGES'));
      await tester.tap(find.text('SAVE CHANGES'));
      await tester.pumpAndSettle();
      expect(writes, 1);
      expect(
        find
            .byType(TextField)
            .evaluate()
            .map((e) => (e.widget as TextField).controller!.text)
            .every((value) => value.isEmpty),
        isTrue,
      );
      await tester.ensureVisible(find.text('SAVE CHANGES'));
      await tester.tap(find.text('SAVE CHANGES'));
      await tester.pumpAndSettle();
      expect(writes, 1);
      await tester.ensureVisible(find.text('Refresh profile and review'));
      final refresh = tester
          .widget<TextButton>(
            find.widgetWithText(TextButton, 'Refresh profile and review'),
          )
          .onPressed!;
      await tester.runAsync(() async {
        await (refresh as dynamic)();
      });
      await tester.pumpAndSettle();
      expect(
        (tester.widget<TextField>(
          find.byType(TextField).first,
        )).controller!.text,
        'Newer server name',
      );
      expect(
        (tester.widget<TextField>(
          find.byType(TextField).at(5),
        )).controller!.text,
        isEmpty,
      );
      expect(app.user!.version, 2);
      expect(writes, 1);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );
}
