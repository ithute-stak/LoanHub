import 'package:flutter/material.dart';

/// Mobile color tokens mirrored from the LoanHub web application.
abstract final class LoanHubColors {
  static const primary = Color(0xFF0B5EA8);
  static const primaryLight = Color(0xFF45A4EB);
  static const brandGreen = Color(0xFF37A928);
  static const brandNavy = Color(0xFF062B55);
  static const heading = Color(0xFF0F2742);
  static const ink = Color(0xFF172033);
  static const softBlue = Color(0xFFEDF6FF);
  static const background = Color(0xFFF8FAFC);
  static const surface = Color(0xFFFFFFFF);
  static const border = Color(0xFFD7E3EE);
  static const muted = Color(0xFF64748B);
  static const darkBackground = Color(0xFF111827);
  static const darkSurface = Color(0xFF172033);
  static const darkBorder = Color(0xFF334155);
}

abstract final class LoanHubTheme {
  static ThemeData light() {
    const scheme = ColorScheme.light(
      primary: LoanHubColors.primary,
      onPrimary: Colors.white,
      secondary: LoanHubColors.brandGreen,
      onSecondary: Colors.white,
      tertiary: LoanHubColors.brandNavy,
      onTertiary: Colors.white,
      surface: LoanHubColors.surface,
      onSurface: LoanHubColors.ink,
      error: Color(0xFFB42318),
      onError: Colors.white,
      outline: LoanHubColors.border,
      outlineVariant: Color(0xFFE7EEF5),
    );
    return _base(scheme).copyWith(
      scaffoldBackgroundColor: LoanHubColors.background,
      appBarTheme: const AppBarTheme(
        centerTitle: false,
        elevation: 0,
        scrolledUnderElevation: 1,
        backgroundColor: LoanHubColors.surface,
        foregroundColor: LoanHubColors.brandNavy,
        surfaceTintColor: Colors.transparent,
        titleTextStyle: TextStyle(
          color: LoanHubColors.brandNavy,
          fontSize: 20,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }

  static ThemeData dark() {
    const scheme = ColorScheme.dark(
      primary: LoanHubColors.primaryLight,
      onPrimary: LoanHubColors.brandNavy,
      secondary: Color(0xFF67C95B),
      onSecondary: Color(0xFF071A08),
      tertiary: Color(0xFF8CC8F5),
      onTertiary: Color(0xFF071A2D),
      surface: LoanHubColors.darkSurface,
      onSurface: Color(0xFFF1F5F9),
      error: Color(0xFFFFB4AB),
      onError: Color(0xFF690005),
      outline: LoanHubColors.darkBorder,
      outlineVariant: Color(0xFF25364A),
    );
    return _base(scheme).copyWith(
      scaffoldBackgroundColor: LoanHubColors.darkBackground,
      appBarTheme: const AppBarTheme(
        centerTitle: false,
        elevation: 0,
        scrolledUnderElevation: 1,
        backgroundColor: LoanHubColors.darkSurface,
        foregroundColor: Color(0xFFF1F5F9),
        surfaceTintColor: Colors.transparent,
        titleTextStyle: TextStyle(
          color: Color(0xFFF1F5F9),
          fontSize: 20,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }

  static ThemeData _base(ColorScheme scheme) {
    final border = scheme.outlineVariant;
    return ThemeData(
      colorScheme: scheme,
      useMaterial3: true,
      visualDensity: VisualDensity.standard,
      materialTapTargetSize: MaterialTapTargetSize.padded,
      cardTheme: CardThemeData(
        margin: EdgeInsets.zero,
        elevation: 0,
        color: scheme.surface,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: BorderSide(color: border),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: scheme.primary, width: 2),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(48, 48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w800),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(48, 48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w800),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        height: 70,
        backgroundColor: scheme.surface,
        indicatorColor: scheme.primary.withValues(alpha: .14),
        labelTextStyle: WidgetStatePropertyAll(
          TextStyle(color: scheme.onSurface, fontWeight: FontWeight.w700),
        ),
      ),
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: scheme.surface,
        indicatorColor: scheme.primary.withValues(alpha: .14),
        selectedIconTheme: IconThemeData(color: scheme.primary),
        selectedLabelTextStyle: TextStyle(
          color: scheme.primary,
          fontWeight: FontWeight.w800,
        ),
      ),
      dividerTheme: DividerThemeData(color: border),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    );
  }
}
