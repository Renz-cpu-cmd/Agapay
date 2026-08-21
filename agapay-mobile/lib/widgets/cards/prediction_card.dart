import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/formatters.dart';
import '../../models/telemetry_history.dart';

/// Card for AI / ML predicted water levels at T+30, T+60, T+90 minutes
class PredictionCard extends StatelessWidget {
  final TelemetryDataPoint prediction;
  final double currentDepthCm;

  const PredictionCard({
    super.key,
    required this.prediction,
    required this.currentDepthCm,
  });

  @override
  Widget build(BuildContext context) {
    final diff = prediction.waterDepthCm - currentDepthCm;
    final isRising = diff > 0;

    return Container(
      width: 140,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                prediction.predictionLabel ?? 'Forecast',
                style: const TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                  color: AppColors.primary,
                ),
              ),
              Icon(
                isRising ? Icons.trending_up_rounded : Icons.trending_down_rounded,
                size: 16,
                color: isRising ? AppColors.alertWarning : AppColors.alertNormal,
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            Formatters.formatWaterLevel(prediction.waterDepthCm),
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            '${diff >= 0 ? '+' : ''}${diff.toStringAsFixed(1)} cm change',
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: isRising ? AppColors.alertWarning : AppColors.alertNormal,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Rain: ${prediction.rainfallMm.toStringAsFixed(1)} mm/h',
            style: const TextStyle(fontSize: 10, color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }
}
