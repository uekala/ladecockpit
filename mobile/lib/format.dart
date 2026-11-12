/// Formats a number the German way: decimal comma and a dot between
/// thousands, e.g. 1234.5 with one digit becomes "1.234,5".
String formatNumber(num value, int digits) {
  if (value.isNaN || value.isInfinite) return '–';
  final fixed = value.abs().toStringAsFixed(digits);
  final parts = fixed.split('.');
  final whole = parts[0].replaceAllMapped(RegExp(r'\B(?=(\d{3})+$)'), (match) => '.');
  final isZero = RegExp(r'^[0.]+$').hasMatch(fixed);
  final sign = value < 0 && !isZero ? '-' : '';
  return '$sign$whole${parts.length > 1 ? ',${parts[1]}' : ''}';
}
