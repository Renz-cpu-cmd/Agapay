import 'package:flutter/material.dart';
import '../core/theme/app_colors.dart';

/// Water level trend direction
enum TrendDirection {
  rising,
  stable,
  falling,
}

extension TrendDirectionExtension on TrendDirection {
  String get label {
    switch (this) {
      case TrendDirection.rising:
        return 'Rising';
      case TrendDirection.stable:
        return 'Stable';
      case TrendDirection.falling:
        return 'Falling';
    }
  }

  IconData get icon {
    switch (this) {
      case TrendDirection.rising:
        return Icons.arrow_upward_rounded;
      case TrendDirection.stable:
        return Icons.remove_rounded;
      case TrendDirection.falling:
        return Icons.arrow_downward_rounded;
    }
  }

  Color get color {
    switch (this) {
      case TrendDirection.rising:
        return AppColors.alertWarning;
      case TrendDirection.stable:
        return AppColors.textSecondary;
      case TrendDirection.falling:
        return AppColors.alertNormal;
    }
  }
}
