import 'dart:async';
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:agapay_mobile/controllers/product_preferences_controller.dart';
import 'package:agapay_mobile/controllers/device_capabilities_controller.dart';
import 'package:agapay_mobile/controllers/build_information_controller.dart';
import 'package:agapay_mobile/l10n/generated/app_localizations.dart';
import 'package:agapay_mobile/l10n/generated/app_localizations_en.dart';
import 'package:agapay_mobile/services/auth_api.dart';
import 'package:agapay_mobile/controllers/app_controller.dart';
import 'package:agapay_mobile/core/theme/app_theme.dart';
import 'package:agapay_mobile/widgets/common/product_capability_settings.dart';
import 'package:flutter/material.dart';
import 'support/accounts.dart';

class LocationProbe implements LocationCapabilitySource {
  LocationCapability value = const LocationCapability(
    permission: 'deniedForever',
    service: 'disabled',
  );
  int calls = 0;
  @override
  Future<LocationCapability> read() async {
    calls++;
    return value;
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'device choices survive restart and remain isolated by account',
    () async {
      final store = MemoryProductPreferences();
      final api = AuthApi(
        readerStorage: MemoryReaderStorage(),
        storage: MemoryTokens(),
        client: MockClient(
          (r) async => http.Response(
            r.url.path.endsWith('/areas')
                ? '[]'
                : '{"revision":0,"notifications_enabled":false,"locale":"en"}',
            200,
          ),
        ),
      );
      final first = ProductPreferencesController(api, store: store);
      await first.setOwner(1);
      await first.updateLocal(location: false, station: 'SELECTED_STATION');
      first.dispose();
      final restored = ProductPreferencesController(api, store: store);
      await restored.setOwner(1);
      expect(restored.locationEnabled, isFalse);
      expect(restored.selectedStationId, 'SELECTED_STATION');
      await restored.setOwner(2);
      expect(restored.locationEnabled, isTrue);
      expect(restored.selectedStationId, 'STATION_001');
      restored.dispose();
      api.dispose();
    },
  );
  test(
    'stale preference writes stop until an explicit refresh and manual save',
    () async {
      var writes = 0, reads = 0;
      final api = AuthApi(
        readerStorage: MemoryReaderStorage(),
        storage: MemoryTokens(),
        client: MockClient((r) async {
          if (r.url.path.endsWith('/areas')) return http.Response('[]', 200);
          if (r.method == 'PATCH') {
            writes++;
            return http.Response('{"detail":"Preferences changed"}', 409);
          }
          reads++;
          return http.Response(
            jsonEncode({
              'revision': reads,
              'notifications_enabled': true,
              'locale': 'en',
            }),
            200,
          );
        }),
      );
      final c = ProductPreferencesController(
        api,
        store: MemoryProductPreferences(),
      );
      await c.setOwner(1);
      expect(await c.save({'notifications_enabled': false}), isFalse);
      expect(c.conflicted, isTrue);
      await c.save({'notifications_enabled': false});
      expect(writes, 1);
      expect(c.notificationsEnabled, isTrue);
      await c.refresh();
      expect(c.conflicted, isFalse);
      expect(c.revision, 2);
      expect(writes, 1);
      c.dispose();
      api.dispose();
    },
  );
  test(
    'old account responses cannot replace the next account preferences',
    () async {
      final gate = Completer<http.Response>();
      var reads = 0;
      final api = AuthApi(
        readerStorage: MemoryReaderStorage(),
        storage: MemoryTokens(),
        client: MockClient((r) async {
          if (r.url.path.endsWith('/areas')) return http.Response('[]', 200);
          if (++reads == 1) return gate.future;
          return http.Response(
            '{"revision":4,"notifications_enabled":false,"locale":"en"}',
            200,
          );
        }),
      );
      final c = ProductPreferencesController(
        api,
        store: MemoryProductPreferences(),
      );
      final old = c.setOwner(1);
      await Future<void>.delayed(Duration.zero);
      await c.setOwner(2);
      gate.complete(
        http.Response(
          '{"revision":99,"notifications_enabled":true,"locale":"en"}',
          200,
        ),
      );
      await old;
      expect(c.revision, 4);
      expect(c.notificationsEnabled, isFalse);
      c.dispose();
      api.dispose();
    },
  );
  test(
    'unavailable preferences never enable registration or claim saved data',
    () async {
      final api = AuthApi(
        readerStorage: MemoryReaderStorage(),
        storage: MemoryTokens(),
        client: MockClient((r) async => http.Response('{}', 503)),
      );
      final c = ProductPreferencesController(
        api,
        store: MemoryProductPreferences(),
      );
      await c.setOwner(1);
      expect(c.ready, isFalse);
      expect(c.notificationsEnabled, isFalse);
      expect(c.error, isNotNull);
      c.dispose();
      api.dispose();
    },
  );
  test(
    'capability query reports OS permission and service independently',
    () async {
      final source = LocationProbe(),
          c = DeviceCapabilitiesController(source: LocationProbe());
      final probe = DeviceCapabilitiesController(source: source);
      await probe.refresh();
      expect(probe.location.permission, 'deniedForever');
      expect(probe.location.service, 'disabled');
      source.value = const LocationCapability(
        permission: 'whileInUse',
        service: 'enabled',
      );
      await probe.refresh();
      expect(probe.location.permission, 'whileInUse');
      expect(source.calls, 2);
      probe.dispose();
      c.dispose();
    },
  );
  testWidgets('disposing a stalled OS probe cancels its timeout', (
    tester,
  ) async {
    final source = _StalledLocation();
    final c = DeviceCapabilitiesController(source: source);
    final request = c.refresh();
    c.dispose();
    await request;
    expect(tester.takeException(), isNull);
  });
  test(
    'build labels use actual package metadata and unavailable remains explicit',
    () async {
      final c = BuildInformationController(
        load: () async => PackageInfo(
          appName: 'AGAPAY',
          packageName: 'test',
          version: '0.1.0',
          buildNumber: '42',
        ),
      );
      await c.refresh();
      expect(c.label, 'Version 0.1.0 · Build 42');
      c.dispose();
      final failed = BuildInformationController(
        load: () async => throw StateError('unavailable'),
      );
      await failed.refresh();
      expect(failed.label, 'Build information unavailable');
      failed.dispose();
    },
  );
  test(
    'English is the only supported locale and critical instructions come from English resources',
    () {
      expect(AppLocalizations.supportedLocales.map((l) => l.languageCode), [
        'en',
      ]);
      final strings = AppLocalizationsEn();
      expect(strings.translationUnavailable, contains('Filipino'));
    },
  );
  testWidgets(
    'narrow settings show true capability states and save a language request without translation',
    (tester) async {
      tester.view.physicalSize = const Size(320, 700);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final app = fixtureController();
      await tester.runAsync(
        () => app.login('resident@example.com', 'password'),
      );
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: const Scaffold(
              body: SingleChildScrollView(child: ProductCapabilitySettings()),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(
        find.textContaining('Filipino translation unavailable'),
        findsOneWidget,
      );
      expect(
        find.textContaining('OS permission: Denied or not requested'),
        findsOneWidget,
      );
      expect(find.textContaining('unavailable on this build'), findsOneWidget);
      final request = find.text('Request a community language');
      await tester.ensureVisible(request);
      await tester.tap(request);
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byType(TextFormField),
        'Community requested language',
      );
      await tester.tap(find.text('Save request'));
      await tester.pumpAndSettle();
      expect(app.preferences.requestedLanguage, 'Community requested language');
      expect(app.language, 'English');
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );
}

class _StalledLocation implements LocationCapabilitySource {
  @override
  Future<LocationCapability> read() => Completer<LocationCapability>().future;
}
