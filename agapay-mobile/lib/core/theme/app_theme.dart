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
  static final light = dark.copyWith(
    brightness: Brightness.light,
    scaffoldBackgroundColor: const Color(0xfff3f6fb),
    colorScheme: const ColorScheme.light(
      primary: Color(0xff2462b7),
      surface: Colors.white,
      onSurface: Color(0xff172b49),
    ),
    textTheme: dark.textTheme.apply(
      bodyColor: const Color(0xff172b49),
      displayColor: const Color(0xff172b49),
    ),
    dividerColor: const Color(0xffcbd8e8),
    dividerTheme: const DividerThemeData(
      color: Color(0xffcbd8e8),
      thickness: 1,
      space: 1,
    ),
    inputDecorationTheme: dark.inputDecorationTheme.copyWith(
      fillColor: Colors.white,
      hintStyle: const TextStyle(color: Color(0xff63758e), fontSize: 14),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: Color(0xffcbd8e8)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: Color(0xff2462b7), width: 1.5),
      ),
    ),
  );
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

/// Shared palette used by every screen; the original constants remain dark tokens.
class AppPalette {
  const AppPalette(this.isDark);
  final bool isDark;
  Color get background =>
      isDark ? AppColors.background : const Color(0xfff3f6fb);
  Color get surface => isDark ? AppColors.surface : Colors.white;
  Color get surfaceRaised =>
      isDark ? AppColors.surfaceRaised : const Color(0xfff8faff);
  Color get border => isDark ? AppColors.border : const Color(0xffcbd8e8);
  Color get muted => isDark ? AppColors.muted : const Color(0xff526581);
  Color get secondary => isDark ? AppColors.secondary : const Color(0xff405775);
  Color get label => isDark ? AppColors.label : const Color(0xff405775);
  Color get text => isDark ? AppColors.text : const Color(0xff172b49);
  Color get faint => isDark ? AppColors.faint : const Color(0xff63758e);
  Color get blue => AppColors.blue;
  Color get link => isDark ? AppColors.link : const Color(0xff2462b7);
  Color get green => isDark ? AppColors.green : const Color(0xff15803d);
  Color get red => AppColors.red;

  Color resolve(Color color) {
    if (isDark) return color;
    const dark = [
      AppColors.background,
      AppColors.surface,
      AppColors.surfaceRaised,
      AppColors.border,
      AppColors.muted,
      AppColors.secondary,
      AppColors.label,
      AppColors.text,
      AppColors.faint,
      AppColors.link,
      AppColors.green,
    ];
    final light = [
      background,
      surface,
      surfaceRaised,
      border,
      muted,
      secondary,
      label,
      text,
      faint,
      link,
      green,
    ];
    final index = dark.indexOf(color);
    if (index >= 0) return light[index];
    if (color == Colors.white) return text;
    if (light.contains(color)) return color;
    final hsv = HSVColor.fromColor(color);
    if (hsv.value < .3 && hsv.saturation > .3 && color.a > .1) {
      return hsv.withSaturation(.08).withValue(.99).withAlpha(1).toColor();
    }
    if (hsv.value < .25 && color.a > .8) return surfaceRaised;
    if (hsv.saturation > .3 && hsv.value > .65) {
      return hsv.withValue(.58).toColor();
    }
    return color;
  }
}

extension ThemePalette on BuildContext {
  AppPalette get colors =>
      AppPalette(Theme.of(this).brightness == Brightness.dark);
}
