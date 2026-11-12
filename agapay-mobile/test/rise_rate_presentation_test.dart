import 'package:agapay_mobile/core/ui.dart';
import 'package:agapay_mobile/screens/home/home_screen.dart';
import 'package:flutter_test/flutter_test.dart';
import 'support/accounts.dart';

void main() {
  testWidgets(
    'fresh depth with insufficient rate coverage shows unknown rather than stable or an example rate',
    (tester) async {
      final app = fixtureController(
        monitoringChanges: {
          'trend': 'unknown',
          'rise_rate_cm_per_minute': null,
          'trend_reason': 'Insufficient timing coverage',
        },
      );
      await app.login('resident@example.com', 'password123');
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: const Scaffold(body: HomeScreen()),
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 50));
      await tester.pumpAndSettle();
      expect(find.text('— UNKNOWN TREND'), findsOneWidget);
      expect(
        find.textContaining('Rate — · Insufficient timing coverage'),
        findsOneWidget,
      );
      expect(find.text('→ STABLE'), findsNothing);
      expect(find.textContaining('+3.2 cm / 10 min'), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );

  testWidgets(
    'rate displays backend cm per minute and slope range without converting the example levels',
    (tester) async {
      final app = fixtureController(
        monitoringChanges: {
          'trend': 'rising',
          'rise_rate_cm_per_minute': 1.2,
          'rise_rate_lower': 1.1,
          'rise_rate_upper': 1.3,
          'trend_reason': 'Covered measured-time window',
        },
      );
      await app.login('resident@example.com', 'password123');
      await tester.pumpWidget(
        AppScope(
          controller: app,
          child: MaterialApp(
            theme: AppTheme.light,
            home: const Scaffold(body: HomeScreen()),
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 50));
      await tester.pumpAndSettle();
      expect(
        find.textContaining('1.200 cm/min · range 1.100 to 1.300'),
        findsOneWidget,
      );
      expect(find.text('↗ RISING'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      app.dispose();
    },
  );
}
