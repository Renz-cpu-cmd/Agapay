import 'package:intl/intl.dart';

/// Formatting utility helpers for AGAPAY
class Formatters {
  static String formatWaterLevel(double depthCm) {
    if (depthCm >= 100) {
      final meters = depthCm / 100.0;
      return '${meters.toStringAsFixed(2)} m';
    }
    return '${depthCm.toStringAsFixed(1)} cm';
  }

  static String formatRainfall(double rainfallMm) {
    return '${rainfallMm.toStringAsFixed(1)} mm/h';
  }

  static String formatBattery(int batteryPercent) {
    return '$batteryPercent%';
  }

  static String formatDistance(double km) {
    if (km < 1.0) {
      return '${(km * 1000).toInt()} m';
    }
    return '${km.toStringAsFixed(1)} km';
  }

  static String formatTimestamp(DateTime dateTime) {
    final formatter = DateFormat('h:mm a · MMM d, yyyy');
    return formatter.format(dateTime);
  }

  static String formatTimeOnly(DateTime dateTime) {
    final formatter = DateFormat('h:mm a');
    return formatter.format(dateTime);
  }

  static String formatRelativeTime(DateTime dateTime) {
    final now = DateTime.now();
    final difference = now.difference(dateTime);

    if (difference.inSeconds < 15) {
      return 'just now';
    } else if (difference.inSeconds < 60) {
      return '${difference.inSeconds} seconds ago';
    } else if (difference.inMinutes < 60) {
      return '${difference.inMinutes} minute${difference.inMinutes > 1 ? 's' : ''} ago';
    } else if (difference.inHours < 24) {
      return '${difference.inHours} hour${difference.inHours > 1 ? 's' : ''} ago';
    } else {
      return '${difference.inDays} day${difference.inDays > 1 ? 's' : ''} ago';
    }
  }
}
