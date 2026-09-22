import '../../core/ui.dart';

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({super.key});
  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  final _read = <int>{2, 3, 4, 5, 6};
  static const _alerts = [
    (
      AlertLevel.evacuate,
      'EVACUATION ALERT',
      'San Vicente River Station — Water level reached 103.2 cm. Proceed to nearest evacuation shelter.',
      '11:45 AM',
    ),
    (
      AlertLevel.warning,
      'FLOOD WARNING',
      'Water level has reached warning level at San Vicente Station. 95.8 cm — Prepare for evacuation.',
      '11:41 AM',
    ),
    (
      AlertLevel.advisory,
      'ADVISORY',
      'Elevated water level detected at STATION_001. 63.1 cm and rising. Stay alert.',
      '11:32 AM',
    ),
    (
      AlertLevel.advisory,
      'RAINFALL ADVISORY',
      'Rainfall accumulation at 4.6 mm. River levels may increase. Monitor AGAPAY for updates.',
      '10:55 AM',
    ),
    (
      AlertLevel.normal,
      'ALL CLEAR',
      'Water level has returned to normal. 38.2 cm. No immediate danger. Stay prepared.',
      '8:12 PM',
    ),
    (
      null,
      'SYSTEM UPDATE',
      'AGAPAY sensor calibration completed. STATION_001 is fully operational.',
      '3:30 PM',
    ),
    (
      AlertLevel.warning,
      'FLOOD WARNING',
      'Water level reached 88.5 cm at San Vicente Station. Residents in low-lying areas should prepare.',
      '1:15 PM',
    ),
  ];
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    return PageContent(
      children: [
        const PageHeading(
          'Notifications',
          'San Vicente, Urdaneta · All alerts',
        ),
        if (app.alert != AlertLevel.normal) ...[
          Panel(
            padding: 14,
            radius: 14,
            color: const Color(0x601c0000),
            border: const Color(0x99dc2626),
            child: Row(
              spacing: 12,
              children: [
                const Dot(AppColors.red),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      tx(
                        'ACTIVE ALERT IN EFFECT',
                        size: 12,
                        mono: true,
                        weight: 700,
                        color: const Color(0xfff87171),
                      ),
                      tx(
                        'Tap any alert below for details',
                        size: 11,
                        color: AppColors.secondary,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          gap,
        ],
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            caption('TODAY'),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: AppColors.red,
                borderRadius: BorderRadius.circular(20),
              ),
              child: tx(
                '${_alerts.length - _read.length} unread',
                size: 10,
                mono: true,
                weight: 600,
                color: Colors.white,
              ),
            ),
          ],
        ),
        gap,
        for (var i = 0; i < _alerts.length; i++) ...[
          if (i == 4) ...[gap, caption('YESTERDAY'), gap],
          _card(context, i),
          gap,
        ],
        tx(
          'Showing last 7 days · All times local · AGAPAY EWS',
          size: 10,
          mono: true,
          color: AppColors.faint,
          align: TextAlign.center,
        ),
      ],
    );
  }

  Widget _card(BuildContext context, int index) {
    final (level, title, body, time) = _alerts[index];
    final color = level?.textColor ?? AppColors.link;
    return Semantics(
      button: true,
      child: InkWell(
        onTap: () {
          setState(() => _read.add(index));
          showModalBottomSheet<void>(
            context: context,
            backgroundColor: AppColors.background,
            showDragHandle: true,
            isScrollControlled: true,
            builder: (context) => SafeArea(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(24, 0, 24, 32),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    tx(
                      title,
                      size: 18,
                      weight: 700,
                      display: true,
                      color: color,
                    ),
                    gap,
                    tx(body),
                    gap,
                    tx(
                      '$time · Demo notification',
                      size: 11,
                      mono: true,
                      color: AppColors.muted,
                    ),
                  ],
                ),
              ),
            ),
          );
        },
        borderRadius: BorderRadius.circular(14),
        child: Panel(
          padding: 14,
          radius: 14,
          color: (level?.background ?? const Color(0xff0d1f3c)).withValues(
            alpha: .42,
          ),
          border: color.withValues(alpha: .68),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            spacing: 12,
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 5),
                child: Dot(color, size: 10, glow: !_read.contains(index)),
              ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      spacing: 8,
                      children: [
                        Expanded(
                          child: tx(
                            title,
                            size: 13,
                            mono: true,
                            weight: 700,
                            color: color,
                            spacing: 1.2,
                          ),
                        ),
                        Row(
                          spacing: 6,
                          children: [
                            if (!_read.contains(index))
                              const Dot(AppColors.red, size: 6),
                            tx(
                              time,
                              size: 10,
                              mono: true,
                              color: AppColors.muted,
                            ),
                          ],
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    tx(body, size: 12, color: AppColors.label, height: 1.55),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
