import '../../core/ui.dart';
import 'alerts_screen.dart';
import 'alert_details_screen.dart';

class NotificationHistoryScreen extends StatelessWidget {
  const NotificationHistoryScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    final detail = app.details && app.communityAlerts.selectedId != null;
    return PopScope(
      canPop: !detail,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop && detail) app.closeDetails();
      },
      child: Scaffold(
        body: SafeArea(
          child: detail
              ? const AlertDetailsScreen()
              : const AlertsScreen(initialHistory: true),
        ),
      ),
    );
  }
}
