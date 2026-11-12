import 'package:agapay_mobile/app.dart';
import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/screens/alerts/delivery_evidence_screen.dart';
import 'package:flutter_test/flutter_test.dart';
import 'support/accounts.dart';
import 'ui_consistency_test.dart' show ReviewThemeStore;

void main() {
  testWidgets(
    'resident primary navigation has no duplicate profile/back links and bell opens delivery history',
    (tester) async {
      final app = fixtureController(themeStorage: ReviewThemeStore());
      await app.login('resident@example.com', 'synthetic-password');
      await tester.pumpWidget(AgapayApp(controller: app));
      await tester.pump(const Duration(seconds: 3));
      await tester.pump(const Duration(seconds: 1));
      expect(find.bySemanticsLabel('Profile'), findsNothing);
      for (final tab in [AppTab.map, AppTab.sos]) {
        app.navigate(tab);
        await tester.pump(const Duration(milliseconds: 500));
        expect(find.bySemanticsLabel('Back'), findsNothing);
      }
      app.navigate(AppTab.home);
      await tester.pump(const Duration(milliseconds: 500));
      await tester.tap(find.bySemanticsLabel('Notifications'));
      await tester.pumpAndSettle();
      expect(find.byType(DeliveryEvidenceScreen), findsOneWidget);
      expect(app.tab, AppTab.home);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}
