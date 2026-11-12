import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/models/official_notice.dart';
import 'package:agapay_mobile/widgets/common/official_notices.dart';
import 'package:agapay_mobile/widgets/common/alert_subscriptions.dart';
import 'package:flutter_test/flutter_test.dart';
import 'support/accounts.dart';

Map<String, dynamic> noticeJson() => {
  'id': 'notice-one',
  'authority_id': 'AGAPAY_APP_OPS',
  'issuer_name': 'AGAPAY App Operations',
  'authority_class': 'app_operator',
  'category': 'advisory',
  'status': 'Test',
  'message_type': 'Alert',
  'reference_id': null,
  'superseded_by': null,
  'area_ids': ['APP'],
  'area_names': ['App audience'],
  'urgency': 'Expected',
  'severity': 'Moderate',
  'certainty': 'Possible',
  'headline': 'Synthetic app advisory',
  'instruction': 'Exercise only. Follow official local updates.',
  'sent_at': '2026-10-21T00:00:00Z',
  'effective_at': '2026-10-21T00:00:00Z',
  'expires_at': '2026-10-21T01:00:00Z',
};

void main() {
  test(
    'app notices preserve issuer identity and correct lifecycle without becoming public orders',
    () {
      final notice = OfficialNotice.fromJson(noticeJson());
      expect(notice.kind, 'App advisory');
      expect(
        notice.lifecycle(DateTime.parse('2026-10-21T00:30:00Z')),
        'effective',
      );
      expect(
        notice.lifecycle(DateTime.parse('2026-10-21T01:00:00Z')),
        'expired',
      );
      expect(
        OfficialNotice.fromJson({
          ...noticeJson(),
          'message_type': 'Cancel',
        }).lifecycle(DateTime.now()),
        'cancelled',
      );
      expect(
        OfficialNotice.fromJson({
          ...noticeJson(),
          'superseded_by': 'new-notice',
        }).lifecycle(DateTime.now()),
        'superseded',
      );
      expect(
        () => OfficialNotice.fromJson({
          ...noticeJson(),
          'authority_class': 'sensor',
        }),
        throwsFormatException,
      );
    },
  );

  testWidgets(
    'resident notices show issuer, areas, expiry and cancellation history',
    (tester) async {
      final app = fixtureController(
        residentAreaId: 'APP',
        observationClock: () => DateTime.parse('2026-10-21T00:30:00Z'),
        officialNotices: [
          {
            ...noticeJson(),
            'status': 'Actual',
            'message_type': 'Cancel',
            'reference_id': 'original-notice',
          },
        ],
      );
      await app.login('resident@example.com', 'password123');
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: const Scaffold(body: OfficialNoticesPanel()),
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 50));
      expect(find.text('App advisory · cancelled'), findsOneWidget);
      expect(
        find.textContaining('Issuer: AGAPAY App Operations'),
        findsOneWidget,
      );
      expect(find.textContaining('Areas: App audience (APP)'), findsOneWidget);
      expect(find.textContaining('Expires'), findsOneWidget);
      await tester.ensureVisible(find.text('Source and update history'));
      await tester.tap(find.text('Source and update history'));
      await tester.pumpAndSettle();
      expect(find.textContaining('References original-notice'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );

  testWidgets(
    'resident explicitly follows a station without changing profile locality',
    (tester) async {
      final app = fixtureController();
      await app.login('resident@example.com', 'password123');
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: const Scaffold(body: AlertSubscriptionsPanel()),
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 50));
      await tester.tap(find.text('Choose stations and areas'));
      await tester.pumpAndSettle();
      final choice = find.byType(CheckboxListTile);
      expect(tester.widget<CheckboxListTile>(choice).value, isFalse);
      await tester.tap(choice);
      await tester.pumpAndSettle();
      expect(tester.widget<CheckboxListTile>(choice).value, isTrue);
      expect(app.user!.barangay, 'San Vicente');
      await tester.tap(choice);
      await tester.pumpAndSettle();
      expect(tester.widget<CheckboxListTile>(choice).value, isFalse);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );
}
