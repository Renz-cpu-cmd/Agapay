import 'package:flutter/material.dart';

abstract final class AppColors {
  static const background = Color(0xff000c21);
  static const surface = Color(0xff00112e);
  static const surfaceRaised = Color(0xff071a34);
  static const border = Color(0xff12396d);
  static const muted = Color(0xff58739e);
  static const secondary = Color(0xff7895bd);
  static const label = Color(0xffa2b5d0);
  static const text = Color(0xffeef5ff);
  static const faint = Color(0xff30486c);
  static const blue = Color(0xff1f5fd4);
  static const link = Color(0xff69a7ff);
  static const green = Color(0xff4ade80);
  static const red = Color(0xffdc2626);
}

abstract final class AppTheme {
  static final dark = ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    fontFamily: 'Inter',
    scaffoldBackgroundColor: AppColors.background,
    colorScheme: const ColorScheme.dark(
      primary: AppColors.link,
      surface: AppColors.surface,
      onSurface: AppColors.text,
    ),
    splashFactory: NoSplash.splashFactory,
    dividerColor: AppColors.border,
    dividerTheme: const DividerThemeData(
      color: AppColors.border,
      thickness: 1,
      space: 1,
    ),
    textSelectionTheme: const TextSelectionThemeData(
      cursorColor: Color(0xff3b82f6),
      selectionColor: Color(0x403b82f6),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: AppColors.surface,
      isDense: true,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      hintStyle: const TextStyle(color: AppColors.faint, fontSize: 14),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: AppColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: AppColors.link, width: 1.5),
      ),
    ),
  );
}
