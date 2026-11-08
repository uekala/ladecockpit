import 'package:flutter/material.dart';

/// Central visual system for the Ladecockpit mobile app.
///
/// Keep this theme presentation-only: API behavior and dashboard data remain
/// owned by the existing screens and client.
abstract final class AppTheme {
  static const background = Color(0xFF070B10);
  static const surface = Color(0xFF111820);
  static const surfaceElevated = Color(0xFF182329);
  static const border = Color(0xFF27333A);
  static const textPrimary = Color(0xFFF2F6FA);
  static const textSecondary = Color(0xFF8D9AAF);
  static const accentGreen = Color(0xFF39E6A5);
  static const accentTeal = Color(0xFF22C9C3);
  static const warning = Color(0xFFF5B85B);
  static const error = Color(0xFFFF6B70);

  static ThemeData get dark {
    final scheme = ColorScheme.fromSeed(
      seedColor: accentTeal,
      brightness: Brightness.dark,
    ).copyWith(
      primary: accentTeal,
      secondary: accentGreen,
      surface: surface,
      error: error,
      onSurface: textPrimary,
      onPrimary: background,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: scheme,
      scaffoldBackgroundColor: background,
      canvasColor: background,
      dividerColor: border,
      textTheme: ThemeData.dark().textTheme.apply(
        bodyColor: textPrimary,
        displayColor: textPrimary,
      ).copyWith(
        bodySmall: ThemeData.dark().textTheme.bodySmall?.copyWith(
          color: textSecondary,
        ),
        labelMedium: ThemeData.dark().textTheme.labelMedium?.copyWith(
          color: textSecondary,
          letterSpacing: 0.2,
        ),
        titleMedium: ThemeData.dark().textTheme.titleMedium?.copyWith(
          color: textPrimary,
          fontWeight: FontWeight.w700,
        ),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: background,
        foregroundColor: textPrimary,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        surfaceTintColor: Colors.transparent,
        margin: const EdgeInsets.symmetric(vertical: 7),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(24),
          side: const BorderSide(color: border, width: 1),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surfaceElevated,
        labelStyle: const TextStyle(color: textSecondary),
        hintStyle: const TextStyle(color: textSecondary),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: accentTeal, width: 1.5),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: surfaceElevated,
        contentTextStyle: const TextStyle(color: textPrimary),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
      dividerTheme: const DividerThemeData(
        color: border,
        thickness: 1,
        space: 1,
      ),
      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: accentGreen,
        linearTrackColor: border,
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: accentGreen,
          foregroundColor: background,
          minimumSize: const Size(48, 48),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: textPrimary,
          minimumSize: const Size(48, 48),
          side: const BorderSide(color: border),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
        ),
      ),
    );
  }
}
