import 'package:flutter/material.dart';

/// AGAPAY Color System
/// Clean, trustworthy, public-safety focused color palette.
class AppColors {
  // Primary & Secondary Brand Colors
  static const Color primary = Color(0xFF0B3D91); // Deep Blue
  static const Color primaryDark = Color(0xFF062254);
  static const Color primaryLight = Color(0xFF1E5BBF);
  static const Color secondary = Color(0xFF1976D2); // Blue
  static const Color secondaryLight = Color(0xFFE3F2FD);

  // Background & Surfaces
  static const Color background = Color(0xFFF5F7FA);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color cardBackground = Color(0xFFFFFFFF);
  static const Color surfaceSecondary = Color(0xFFF1F5F9);

  // Text Colors
  static const Color textPrimary = Color(0xFF172033);
  static const Color textSecondary = Color(0xFF64748B);
  static const Color textMuted = Color(0xFF94A3B8);
  static const Color textOnPrimary = Color(0xFFFFFFFF);

  // Borders & Dividers
  static const Color border = Color(0xFFE2E8F0);
  static const Color borderLight = Color(0xFFF1F5F9);

  // Alert Tier Colors (Public Safety Status)
  static const Color alertNormal = Color(0xFF16A34A); // Green
  static const Color alertNormalBg = Color(0xFFDCFCE7);
  static const Color alertNormalText = Color(0xFF14532D);

  static const Color alertAdvisory = Color(0xFFEAB308); // Yellow / Amber
  static const Color alertAdvisoryBg = Color(0xFFFEF9C3);
  static const Color alertAdvisoryText = Color(0xFF713F12);

  static const Color alertWarning = Color(0xFFF97316); // Orange
  static const Color alertWarningBg = Color(0xFFFFEDD5);
  static const Color alertWarningText = Color(0xFF7C2D12);

  static const Color alertEvacuate = Color(0xFFDC2626); // Red
  static const Color alertEvacuateBg = Color(0xFFFEE2E2);
  static const Color alertEvacuateText = Color(0xFF7F1D1D);

  // SOS Emergency Color
  static const Color sosRed = Color(0xFFE11D48);
  static const Color sosRedLight = Color(0xFFFFE4E6);

  // Helper Tints
  static const Color infoBlue = Color(0xFF0284C7);
  static const Color infoBlueBg = Color(0xFFE0F2FE);
  static const Color offlineGrey = Color(0xFF475569);
  static const Color offlineBg = Color(0xFFE2E8F0);
}
