import 'package:flutter/material.dart';
import '../core/theme/app_colors.dart';

/// 4-tier Public Safety Alert levels for AGAPAY
enum AlertTier {
  normal,
  advisory,
  warning,
  evacuate,
}

extension AlertTierExtension on AlertTier {
  String get code {
    switch (this) {
      case AlertTier.normal:
        return 'NORMAL';
      case AlertTier.advisory:
        return 'ADVISORY';
      case AlertTier.warning:
        return 'WARNING';
      case AlertTier.evacuate:
        return 'EVACUATE';
    }
  }

  String get displayName {
    switch (this) {
      case AlertTier.normal:
        return 'Normal';
      case AlertTier.advisory:
        return 'Advisory';
      case AlertTier.warning:
        return 'Warning';
      case AlertTier.evacuate:
        return 'Evacuate';
    }
  }

  String get summary {
    switch (this) {
      case AlertTier.normal:
        return 'Current conditions are safe.';
      case AlertTier.advisory:
        return 'Water level is rising. Monitor updates closely.';
      case AlertTier.warning:
        return 'Water level reached warning threshold. Prepare essentials.';
      case AlertTier.evacuate:
        return 'Critical water level! Immediate evacuation recommended.';
    }
  }

  String get recommendedAction {
    switch (this) {
      case AlertTier.normal:
        return 'Conditions normal. Continue routine monitoring.';
      case AlertTier.advisory:
        return 'Stay alert and monitor local flood broadcasts.';
      case AlertTier.warning:
        return 'Prepare go-bags, secure valuables, and stay on standby.';
      case AlertTier.evacuate:
        return 'Move to the nearest evacuation center immediately.';
    }
  }

  Color get color {
    switch (this) {
      case AlertTier.normal:
        return AppColors.alertNormal;
      case AlertTier.advisory:
        return AppColors.alertAdvisory;
      case AlertTier.warning:
        return AppColors.alertWarning;
      case AlertTier.evacuate:
        return AppColors.alertEvacuate;
    }
  }

  Color get backgroundColor {
    switch (this) {
      case AlertTier.normal:
        return AppColors.alertNormalBg;
      case AlertTier.advisory:
        return AppColors.alertAdvisoryBg;
      case AlertTier.warning:
        return AppColors.alertWarningBg;
      case AlertTier.evacuate:
        return AppColors.alertEvacuateBg;
    }
  }

  Color get textColor {
    switch (this) {
      case AlertTier.normal:
        return AppColors.alertNormalText;
      case AlertTier.advisory:
        return AppColors.alertAdvisoryText;
      case AlertTier.warning:
        return AppColors.alertWarningText;
      case AlertTier.evacuate:
        return AppColors.alertEvacuateText;
    }
  }

  IconData get icon {
    switch (this) {
      case AlertTier.normal:
        return Icons.check_circle_rounded;
      case AlertTier.advisory:
        return Icons.info_rounded;
      case AlertTier.warning:
        return Icons.warning_amber_rounded;
      case AlertTier.evacuate:
        return Icons.campaign_rounded;
    }
  }
}
