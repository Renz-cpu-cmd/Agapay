import '../../core/ui.dart';
import 'alerts_screen.dart';

class NotificationHistoryScreen extends StatelessWidget {
  const NotificationHistoryScreen({super.key});
  @override
  Widget build(BuildContext context) =>
      const Scaffold(body: SafeArea(child: AlertsScreen()));
}
