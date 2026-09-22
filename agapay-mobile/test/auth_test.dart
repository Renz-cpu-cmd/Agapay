import 'dart:convert';
import 'package:agapay_mobile/app.dart';
import 'package:agapay_mobile/controllers/app_controller.dart';
import 'package:agapay_mobile/navigation/main_navigation_shell.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'support/accounts.dart';

void main() {
  test(
    'login sends resident audience and restores a securely stored token',
    () async {
      final storage = MemoryTokens();
      final calls = <http.Request>[];
      final api = AuthApi(
        storage: storage,
        client: MockClient((request) async {
          calls.add(request);
          if (request.url.path.endsWith('/login')) {
            expect(jsonDecode(request.body), {
              'email': 'resident@example.com',
              'password': 'long-password-value',
              'audience': 'mobile',
            });
            expect(request.headers.containsKey('Authorization'), isFalse);
            return http.Response(
              jsonEncode({'user': resident(), 'access_token': 'saved-token'}),
              200,
            );
          }
          expect(request.headers['Authorization'], 'Bearer saved-token');
          return http.Response(jsonEncode(resident()), 200);
        }),
      );
      await api.login(' resident@example.com ', 'long-password-value');
      expect(storage.value, 'saved-token');
      final restored = await api.restore();
      expect(restored?.name, 'Test Resident');
      expect(calls.length, 2);
      api.dispose();
    },
  );

  test(
    'expired session clears storage and notifies the account gate',
    () async {
      final storage = MemoryTokens()..value = 'expired';
      var expired = false;
      final api = AuthApi(
        storage: storage,
        client: MockClient(
          (_) async => http.Response('{"detail":"Session expired"}', 401),
        ),
      )..onExpired = () => expired = true;
      expect(await api.restore(), isNull);
      expect(storage.value, isNull);
      expect(expired, isTrue);
      api.dispose();
    },
  );

  test('connection failure keeps a stored session for a later retry', () async {
    final storage = MemoryTokens()..value = 'saved';
    final api = AuthApi(
      storage: storage,
      client: MockClient((_) async => throw http.ClientException('offline')),
    );
    await expectLater(api.restore(), throwsA(isA<AccountException>()));
    expect(storage.value, 'saved');
    api.dispose();
  });

  test('logout revokes server session before clearing local storage', () async {
    final storage = MemoryTokens()..value = 'saved';
    var revoked = false;
    final api = AuthApi(
      storage: storage,
      client: MockClient((request) async {
        if (request.url.path.endsWith('/logout')) {
          expect(request.method, 'POST');
          expect(request.headers['Authorization'], 'Bearer saved');
          revoked = true;
          return http.Response('', 204);
        }
        return http.Response(jsonEncode(resident()), 200);
      }),
    );
    await api.restore();
    await api.logout();
    expect(revoked, isTrue);
    expect(storage.value, isNull);
    api.dispose();
  });

  testWidgets('invalid credentials stay on login and display the API error', (
    tester,
  ) async {
    final controller = AppController(
      authApi: AuthApi(
        storage: MemoryTokens(),
        client: MockClient(
          (_) async => http.Response(
            '{"detail":"Email or password is incorrect."}',
            401,
          ),
        ),
      ),
    );
    await tester.pumpWidget(AgapayApp(controller: controller));
    await tester.pump(const Duration(seconds: 3));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byType(TextField).at(0),
      'resident@example.com',
    );
    await tester.enterText(find.byType(TextField).at(1), 'wrong-password');
    await tester.ensureVisible(find.text('LOG IN'));
    await tester.tap(find.text('LOG IN'));
    await tester.pumpAndSettle();
    expect(find.text('Email or password is incorrect.'), findsOneWidget);
    expect(find.byType(MainNavigationShell), findsNothing);
    expect(controller.signedIn, isFalse);
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets(
    'resident registration and edited profile are reflected in the app',
    (tester) async {
      final controller = fixtureController();
      await tester.pumpWidget(AgapayApp(controller: controller));
      await tester.pump(const Duration(seconds: 3));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Register'));
      await tester.tap(find.text('Register'));
      await tester.pumpAndSettle();
      for (final pair in {
        0: 'New Resident',
        1: 'new@example.com',
        2: '+639123456789',
        3: 'long-password-value',
      }.entries) {
        await tester.enterText(find.byType(TextField).at(pair.key), pair.value);
      }
      await tester.ensureVisible(find.text('CREATE ACCOUNT'));
      await tester.tap(find.text('CREATE ACCOUNT'));
      await tester.pumpAndSettle();
      expect(controller.user?.name, 'New Resident');
      await tester.tap(find.text('Profile').last);
      await tester.pumpAndSettle();
      expect(find.text('new@example.com'), findsOneWidget);
      await tester.ensureVisible(find.text('EDIT PROFILE'));
      await tester.tap(find.text('EDIT PROFILE'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField).at(0), 'Updated Resident');
      await tester.ensureVisible(find.text('SAVE CHANGES'));
      await tester.tap(find.text('SAVE CHANGES'));
      await tester.pumpAndSettle();
      expect(find.text('Updated Resident'), findsOneWidget);
      expect(controller.user?.name, 'Updated Resident');
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}
