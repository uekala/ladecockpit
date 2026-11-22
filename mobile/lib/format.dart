import 'l10n.dart';

/// Formatiert eine Zahl für die Sprache der App. Deutsch: Dezimalkomma und Punkt
/// zwischen Tausendern ("1.234,5"). Englisch: umgekehrt ("1,234.5").
String formatNumber(num value, int digits) {
  if (value.isNaN || value.isInfinite) return '–';
  final english = appLanguage == 'en';
  final fixed = value.abs().toStringAsFixed(digits);
  final parts = fixed.split('.');
  final whole = parts[0].replaceAllMapped(
      RegExp(r'\B(?=(\d{3})+$)'), (match) => english ? ',' : '.');
  final isZero = RegExp(r'^[0.]+$').hasMatch(fixed);
  final sign = value < 0 && !isZero ? '-' : '';
  return '$sign$whole${parts.length > 1 ? '${english ? '.' : ','}${parts[1]}' : ''}';
}
