import '../../core/ui.dart';
import '../../widgets/common/forecast_panel.dart';
import 'community_alert_detail_screen.dart';

class AlertDetailsScreen extends StatelessWidget {
  const AlertDetailsScreen({super.key});
  @override
  Widget build(BuildContext context) {
    final app = AppScope.of(context);
    if (app.communityAlerts.selectedId != null) {
      return const CommunityAlertDetailScreen();
    }
    final station = app.monitoring.primary;
    final level = station?.alertLevel ?? app.alert;
    final waterDepth = station?.currentDepthCm ?? level.water;
    final observed = station?.observedAt;
    final observedTime = observed == null
        ? 'DEMO READING'
        : '${observed.hour.toString().padLeft(2, '0')}:${observed.minute.toString().padLeft(2, '0')} · ${station!.isSimulator ? 'VIRTUAL STATION' : 'LIVE'}';
    return PageContent(
      children: [
        PageHeading(
          'Flood Alert',
          station?.name ?? 'San Vicente River Station',
          onBack: app.closeDetails,
        ),
        Panel(
          padding: 20,
          color: level.background,
          border: level.color.withValues(alpha: .25),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                spacing: 8,
                children: [
                  Dot(level.color, size: 12, glow: true),
                  tx(
                    level.label,
                    size: 14,
                    weight: 700,
                    mono: true,
                    color: level.color,
                    spacing: 1.4,
                  ),
                ],
              ),
              gap,
              Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                spacing: 12,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      tx(
                        waterDepth.toStringAsFixed(1),
                        size: 48,
                        mono: true,
                        weight: 700,
                        color: level.color,
                        height: 1,
                      ),
                      tx(
                        'cm',
                        size: 16,
                        display: true,
                        weight: 600,
                        color: AppColors.secondary,
                      ),
                    ],
                  ),
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          tx(
                            level.detailTrend,
                            size: 14,
                            mono: true,
                            weight: 700,
                            color: level.textColor,
                          ),
                          tx(
                            observedTime,
                            size: 11,
                            mono: true,
                            color: AppColors.muted,
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
              gap,
              tx(
                level.action,
                display: true,
                weight: 500,
                color: Colors.white.withValues(alpha: .8),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        Row(
          spacing: 12,
          children: [
            Expanded(
              child: _Stat(
                'Rainfall',
                station == null
                    ? level.rainfall
                    : '${(station.latestRainfallMm ?? 0).toStringAsFixed(1)} mm',
                station == null
                    ? 'Demonstration rainfall'
                    : 'Latest reporting interval',
              ),
            ),
            Expanded(
              child: _Stat(
                'Station ID',
                station?.id ?? 'STATION_001',
                station == null
                    ? '● Demo data'
                    : '${station.isOnline ? '● Online' : '● Offline'} · ${station.sensorQuality ?? 'No data'}',
                small: true,
              ),
            ),
          ],
        ),
        gap,
        Row(
          spacing: 12,
          children: [
            Expanded(
              child: _Stat(
                'Sensor Quality',
                station?.sensorQuality == 'valid' ? '✓ Valid' : 'Not valid',
                station == null
                    ? 'Demonstration state'
                    : station.firmwareVersion ?? 'Firmware unavailable',
                color: station?.sensorQuality == 'valid'
                    ? AppColors.green
                    : AppColors.muted,
              ),
            ),
            Expanded(
              child: _Stat(
                'Last Updated',
                observed == null
                    ? 'Demo'
                    : '${observed.hour.toString().padLeft(2, '0')}:${observed.minute.toString().padLeft(2, '0')}:${observed.second.toString().padLeft(2, '0')}',
                station?.isStale == true ? 'STALE / OFFLINE' : 'Today',
                small: true,
              ),
            ),
          ],
        ),
        gap,
        const ForecastPanel(detailed: true),
        gap,
        Panel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              caption('RECOMMENDED ACTION'),
              const SizedBox(height: 8),
              tx(level.action, display: true, weight: 500, height: 1.625),
            ],
          ),
        ),
        const SizedBox(height: 16),
        ActionButton(
          'NAVIGATE TO SHELTER',
          glow: true,
          endColor: const Color(0xff2563eb),
          onPressed: () => app.navigate(AppTab.map, evacuation: true),
        ),
        if (level != AlertLevel.normal) ...[
          gap,
          ActionButton(
            '🔴  SEND EMERGENCY SOS',
            color: const Color(0xff7f1d1d),
            border: AppColors.red.withValues(alpha: .38),
            onPressed: () => app.navigate(AppTab.sos),
          ),
        ],
      ],
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat(
    this.label,
    this.value,
    this.sub, {
    this.small = false,
    this.color = AppColors.text,
  });
  final String label, value, sub;
  final bool small;
  final Color color;
  @override
  Widget build(BuildContext context) => Panel(
    padding: 12,
    radius: 12,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        caption(label),
        const SizedBox(height: 8),
        FittedBox(
          fit: BoxFit.scaleDown,
          child: tx(
            value,
            size: small ? 13 : 18,
            mono: true,
            weight: 700,
            color: color,
          ),
        ),
        const SizedBox(height: 2),
        tx(sub, size: 10, mono: true, color: AppColors.muted),
      ],
    ),
  );
}
