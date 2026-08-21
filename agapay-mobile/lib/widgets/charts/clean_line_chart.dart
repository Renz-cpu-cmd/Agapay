import 'dart:math';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../core/theme/app_colors.dart';
import '../../models/telemetry_history.dart';

/// Clean lightweight Canvas Line Chart for Water Level & Rainfall
class CleanLineChart extends StatefulWidget {
  final List<TelemetryDataPoint> dataPoints;
  final List<TelemetryDataPoint>? predictions;
  final double? warningThreshold;
  final double? evacuateThreshold;
  final String unit;
  final Color lineColor;
  final double height;
  final bool isRainfall;

  const CleanLineChart({
    super.key,
    required this.dataPoints,
    this.predictions,
    this.warningThreshold,
    this.evacuateThreshold,
    this.unit = 'cm',
    this.lineColor = AppColors.primary,
    this.height = 200,
    this.isRainfall = false,
  });

  @override
  State<CleanLineChart> createState() => _CleanLineChartState();
}

class _CleanLineChartState extends State<CleanLineChart> {
  int? _selectedPointIndex;

  @override
  Widget build(BuildContext context) {
    if (widget.dataPoints.isEmpty) {
      return Container(
        height: widget.height,
        alignment: Alignment.center,
        child: const Text('No historical data available', style: TextStyle(color: AppColors.textMuted)),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Legend & threshold guide
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                Container(width: 12, height: 3, color: widget.lineColor),
                const SizedBox(width: 6),
                Text(
                  widget.isRainfall ? 'Observed Rainfall' : 'Observed Depth',
                  style: const TextStyle(fontSize: 12, color: AppColors.textSecondary, fontWeight: FontWeight.w600),
                ),
                if (widget.predictions != null && widget.predictions!.isNotEmpty) ...[
                  const SizedBox(width: 12),
                  Container(
                    width: 12,
                    height: 3,
                    decoration: const BoxDecoration(
                      border: Border(top: BorderSide(color: AppColors.secondary, width: 2, style: BorderStyle.solid)),
                    ),
                  ),
                  const SizedBox(width: 6),
                  const Text(
                    'AI Forecast',
                    style: TextStyle(fontSize: 12, color: AppColors.secondary, fontWeight: FontWeight.w600),
                  ),
                ],
              ],
            ),
            if (widget.evacuateThreshold != null)
              Row(
                children: [
                  Container(width: 10, height: 2, color: AppColors.alertEvacuate),
                  const SizedBox(width: 4),
                  Text(
                    'Evac (${widget.evacuateThreshold!.toInt()}cm)',
                    style: const TextStyle(fontSize: 10, color: AppColors.alertEvacuate, fontWeight: FontWeight.bold),
                  ),
                ],
              ),
          ],
        ),
        const SizedBox(height: 12),
        // Chart Canvas
        GestureDetector(
          onTapDown: (details) {
            // Find closest point to tap
            final RenderBox box = context.findRenderObject() as RenderBox;
            final local = details.localPosition;
            final chartWidth = box.size.width;
            final totalPoints = widget.dataPoints.length;
            final step = chartWidth / max(totalPoints - 1, 1);
            final index = (local.dx / step).round().clamp(0, totalPoints - 1);
            setState(() {
              _selectedPointIndex = index;
            });
          },
          child: Container(
            height: widget.height,
            width: double.infinity,
            padding: const EdgeInsets.only(top: 8, bottom: 20, right: 8, left: 8),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: AppColors.border),
            ),
            child: CustomPaint(
              painter: _LineChartPainter(
                dataPoints: widget.dataPoints,
                predictions: widget.predictions,
                warningThreshold: widget.warningThreshold,
                evacuateThreshold: widget.evacuateThreshold,
                lineColor: widget.lineColor,
                selectedIndex: _selectedPointIndex,
                isRainfall: widget.isRainfall,
              ),
            ),
          ),
        ),
        // Selected point readout
        if (_selectedPointIndex != null && _selectedPointIndex! < widget.dataPoints.length) ...[
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: AppColors.surfaceSecondary,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  DateFormat('MMM d, h:mm a').format(widget.dataPoints[_selectedPointIndex!].timestamp),
                  style: const TextStyle(fontSize: 12, color: AppColors.textSecondary, fontWeight: FontWeight.w500),
                ),
                Text(
                  widget.isRainfall
                      ? '${widget.dataPoints[_selectedPointIndex!].rainfallMm.toStringAsFixed(1)} mm/h'
                      : '${widget.dataPoints[_selectedPointIndex!].waterDepthCm.toStringAsFixed(1)} cm',
                  style: TextStyle(
                    fontSize: 13,
                    color: widget.lineColor,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

class _LineChartPainter extends CustomPainter {
  final List<TelemetryDataPoint> dataPoints;
  final List<TelemetryDataPoint>? predictions;
  final double? warningThreshold;
  final double? evacuateThreshold;
  final Color lineColor;
  final int? selectedIndex;
  final bool isRainfall;

  _LineChartPainter({
    required this.dataPoints,
    this.predictions,
    this.warningThreshold,
    this.evacuateThreshold,
    required this.lineColor,
    this.selectedIndex,
    this.isRainfall = false,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (dataPoints.isEmpty) return;

    final allPoints = [...dataPoints, if (predictions != null) ...predictions!];
    double maxVal = 100.0;
    double minVal = 0.0;

    for (final p in allPoints) {
      final val = isRainfall ? p.rainfallMm : p.waterDepthCm;
      if (val > maxVal) maxVal = val + 10;
    }

    final double width = size.width;
    final double height = size.height;

    // Draw grid lines
    final gridPaint = Paint()
      ..color = const Color(0xFFF1F5F9)
      ..strokeWidth = 1;

    for (int i = 0; i <= 4; i++) {
      final y = height * (i / 4.0);
      canvas.drawLine(Offset(0, y), Offset(width, y), gridPaint);
    }

    // Draw Threshold Lines (Warning & Evacuate)
    if (!isRainfall) {
      if (evacuateThreshold != null) {
        final evacY = height - (evacuateThreshold! / maxVal * height);
        final evacPaint = Paint()
          ..color = AppColors.alertEvacuate.withOpacity(0.4)
          ..strokeWidth = 1.2;
        canvas.drawLine(Offset(0, evacY), Offset(width, evacY), evacPaint);
      }
      if (warningThreshold != null) {
        final warnY = height - (warningThreshold! / maxVal * height);
        final warnPaint = Paint()
          ..color = AppColors.alertWarning.withOpacity(0.4)
          ..strokeWidth = 1.2;
        canvas.drawLine(Offset(0, warnY), Offset(width, warnY), warnPaint);
      }
    }

    // Coordinates mapper
    final totalCount = allPoints.length;
    final stepX = width / max(totalCount - 1, 1);

    Offset getPointCoord(int index, double value) {
      final x = index * stepX;
      final y = height - ((value - minVal) / (maxVal - minVal) * height).clamp(0.0, height);
      return Offset(x, y);
    }

    // Draw Historical Data Line
    final historyPath = Path();
    final fillPath = Path();

    final firstCoord = getPointCoord(0, isRainfall ? dataPoints[0].rainfallMm : dataPoints[0].waterDepthCm);
    historyPath.moveTo(firstCoord.dx, firstCoord.dy);
    fillPath.moveTo(firstCoord.dx, height);
    fillPath.lineTo(firstCoord.dx, firstCoord.dy);

    for (int i = 1; i < dataPoints.length; i++) {
      final val = isRainfall ? dataPoints[i].rainfallMm : dataPoints[i].waterDepthCm;
      final coord = getPointCoord(i, val);
      historyPath.lineTo(coord.dx, coord.dy);
      fillPath.lineTo(coord.dx, coord.dy);
    }

    final lastHistoryCoord = getPointCoord(
      dataPoints.length - 1,
      isRainfall ? dataPoints.last.rainfallMm : dataPoints.last.waterDepthCm,
    );
    fillPath.lineTo(lastHistoryCoord.dx, height);
    fillPath.close();

    // Area gradient fill
    final areaPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [
          lineColor.withOpacity(0.2),
          lineColor.withOpacity(0.01),
        ],
      ).createShader(Rect.fromLTWH(0, 0, width, height))
      ..style = PaintingStyle.fill;
    canvas.drawPath(fillPath, areaPaint);

    // Line stroke
    final linePaint = Paint()
      ..color = lineColor
      ..strokeWidth = 2.5
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round
      ..style = PaintingStyle.stroke;
    canvas.drawPath(historyPath, linePaint);

    // Draw Forecast Predictions (dashed / dotted continuation)
    if (predictions != null && predictions!.isNotEmpty) {
      final forecastPath = Path();
      forecastPath.moveTo(lastHistoryCoord.dx, lastHistoryCoord.dy);

      for (int i = 0; i < predictions!.length; i++) {
        final globalIndex = dataPoints.length + i;
        final val = isRainfall ? predictions![i].rainfallMm : predictions![i].waterDepthCm;
        final coord = getPointCoord(globalIndex, val);
        forecastPath.lineTo(coord.dx, coord.dy);

        // Draw prediction dot
        final dotPaint = Paint()
          ..color = AppColors.secondary
          ..style = PaintingStyle.fill;
        canvas.drawCircle(coord, 3.5, dotPaint);
      }

      final forecastLinePaint = Paint()
        ..color = AppColors.secondary
        ..strokeWidth = 2.0
        ..style = PaintingStyle.stroke;
      canvas.drawPath(forecastPath, forecastLinePaint);
    }

    // Highlight selected point
    if (selectedIndex != null && selectedIndex! < dataPoints.length) {
      final selVal = isRainfall ? dataPoints[selectedIndex!].rainfallMm : dataPoints[selectedIndex!].waterDepthCm;
      final selCoord = getPointCoord(selectedIndex!, selVal);

      final selLinePaint = Paint()
        ..color = lineColor.withOpacity(0.5)
        ..strokeWidth = 1.0;
      canvas.drawLine(Offset(selCoord.dx, 0), Offset(selCoord.dx, height), selLinePaint);

      final circlePaint = Paint()
        ..color = Colors.white
        ..style = PaintingStyle.fill;
      canvas.drawCircle(selCoord, 5.0, circlePaint);

      final circleBorderPaint = Paint()
        ..color = lineColor
        ..strokeWidth = 2.5
        ..style = PaintingStyle.stroke;
      canvas.drawCircle(selCoord, 5.0, circleBorderPaint);
    }
  }

  @override
  bool shouldRepaint(covariant _LineChartPainter oldDelegate) {
    return oldDelegate.dataPoints != dataPoints ||
        oldDelegate.selectedIndex != selectedIndex ||
        oldDelegate.predictions != predictions;
  }
}
