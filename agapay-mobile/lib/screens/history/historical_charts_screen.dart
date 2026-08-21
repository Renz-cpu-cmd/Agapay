import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/formatters.dart';
import '../../models/telemetry_history.dart';
import '../../controllers/app_controller.dart';
import '../../widgets/charts/clean_line_chart.dart';
import '../../widgets/cards/prediction_card.dart';
import '../../widgets/common/state_views.dart';

/// Screen 10: Historical Telemetry Charts and AI / ML Flood Level Forecasts
class HistoricalChartsScreen extends StatefulWidget {
  final AppController controller;

  const HistoricalChartsScreen({super.key, required this.controller});

  @override
  State<HistoricalChartsScreen> createState() => _HistoricalChartsScreenState();
}

class _HistoricalChartsScreenState extends State<HistoricalChartsScreen> {
  int _selectedHoursBack = 24; // 24h, 168h (7d), 720h (30d)
  TelemetrySummary? _summary;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    setState(() => _isLoading = true);
    final stationId = widget.controller.selectedStation?.id ?? 'STATION_001';
    final result = await widget.controller.getStationHistory(stationId, hoursBack: _selectedHoursBack);
    if (mounted) {
      setState(() {
        _summary = result;
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final station = widget.controller.selectedStation;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text('Historical Charts & AI Forecast'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _loadHistory,
          ),
        ],
      ),
      body: SafeArea(
        child: _isLoading || _summary == null
            ? const LoadingState(message: 'Loading sensor history and running AI forecasts...')
            : SingleChildScrollView(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Station Subtitle
                    if (station != null) ...[
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  station.name,
                                  style: const TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w800,
                                    color: AppColors.textPrimary,
                                  ),
                                ),
                                Text(
                                  station.barangay,
                                  style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 14),
                    ],

                    // Time Range Selector
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(4),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AppColors.border),
                      ),
                      child: Row(
                        children: [
                          _timeRangeButton(24, '24 Hours'),
                          _timeRangeButton(168, '7 Days'),
                          _timeRangeButton(720, '30 Days'),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),

                    // Aggregated Key Metrics (Min, Max, Avg, Current)
                    Row(
                      children: [
                        _summaryMetric('Current', Formatters.formatWaterLevel(_summary!.currentDepthCm), AppColors.primary),
                        const SizedBox(width: 8),
                        _summaryMetric('Min Depth', Formatters.formatWaterLevel(_summary!.minDepthCm), AppColors.alertNormal),
                        const SizedBox(width: 8),
                        _summaryMetric('Avg Depth', Formatters.formatWaterLevel(_summary!.avgDepthCm), AppColors.secondary),
                        const SizedBox(width: 8),
                        _summaryMetric('Max Depth', Formatters.formatWaterLevel(_summary!.maxDepthCm), AppColors.alertWarning),
                      ],
                    ),
                    const SizedBox(height: 20),

                    // Water Level Chart
                    const Text(
                      'Water Depth History & AI Forecast (cm)',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: AppColors.textPrimary),
                    ),
                    const SizedBox(height: 8),
                    CleanLineChart(
                      dataPoints: _summary!.history,
                      predictions: _summary!.predictions,
                      warningThreshold: station?.warningThresholdCm ?? 70.0,
                      evacuateThreshold: station?.evacuateThresholdCm ?? 85.0,
                      lineColor: AppColors.primary,
                      height: 210,
                    ),
                    const SizedBox(height: 20),

                    // Rainfall Chart
                    const Text(
                      'Precipitation & Rainfall History (mm/h)',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: AppColors.textPrimary),
                    ),
                    const SizedBox(height: 8),
                    CleanLineChart(
                      dataPoints: _summary!.history,
                      lineColor: const Color(0xFF0284C7),
                      isRainfall: true,
                      height: 170,
                    ),
                    const SizedBox(height: 24),

                    // AI / ML Predictions Section
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: AppColors.secondary.withOpacity(0.4), width: 1.5),
                        boxShadow: [
                          BoxShadow(
                            color: AppColors.secondary.withOpacity(0.06),
                            blurRadius: 10,
                            offset: const Offset(0, 3),
                          ),
                        ],
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Container(
                                padding: const EdgeInsets.all(6),
                                decoration: BoxDecoration(
                                  color: AppColors.secondaryLight,
                                  borderRadius: BorderRadius.circular(8),
                                ),
                                child: const Icon(Icons.auto_graph_rounded, color: AppColors.primary, size: 18),
                              ),
                              const SizedBox(width: 8),
                              const Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      'AI / ML Predictive Early Warning',
                                      style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800, color: AppColors.textPrimary),
                                    ),
                                    Text(
                                      'Hydrodynamic LSTM neural model estimates',
                                      style: TextStyle(fontSize: 11, color: AppColors.textSecondary),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 14),
                          SingleChildScrollView(
                            scrollDirection: Axis.horizontal,
                            child: Row(
                              children: _summary!.predictions.map((p) {
                                return Padding(
                                  padding: const EdgeInsets.only(right: 10.0),
                                  child: PredictionCard(
                                    prediction: p,
                                    currentDepthCm: _summary!.currentDepthCm,
                                  ),
                                );
                              }).toList(),
                            ),
                          ),
                          const SizedBox(height: 12),
                          // Important Public Safety Disclaimer
                          Container(
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: AppColors.surfaceSecondary,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: const Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Icon(Icons.info_outline_rounded, size: 15, color: AppColors.textSecondary),
                                SizedBox(width: 6),
                                Expanded(
                                  child: Text(
                                    'AI / ML forecasts are statistical projections based on upstream telemetry and rainfall intensity. Projections are not guaranteed. Follow official NDRRMC and Barangay evacuation directives.',
                                    style: TextStyle(fontSize: 11, color: AppColors.textSecondary, height: 1.35),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 24),
                  ],
                ),
              ),
      ),
    );
  }

  Widget _timeRangeButton(int hours, String label) {
    final isSelected = _selectedHoursBack == hours;
    return Expanded(
      child: GestureDetector(
        onTap: () {
          if (_selectedHoursBack != hours) {
            setState(() => _selectedHoursBack = hours);
            _loadHistory();
          }
        },
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(
            color: isSelected ? AppColors.primary : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
          ),
          alignment: Alignment.center,
          child: Text(
            label,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: isSelected ? Colors.white : AppColors.textSecondary,
            ),
          ),
        ),
      ),
    );
  }

  Widget _summaryMetric(String label, String value, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.border),
        ),
        child: Column(
          children: [
            Text(label, style: const TextStyle(fontSize: 10, color: AppColors.textSecondary, fontWeight: FontWeight.w500)),
            const SizedBox(height: 2),
            Text(
              value,
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: color),
            ),
          ],
        ),
      ),
    );
  }
}
