import 'l10n.dart';

/// Formats a number for the app's language. German: decimal comma and a dot
/// between thousands ("1.234,5"). English: the other way round ("1,234.5").
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
