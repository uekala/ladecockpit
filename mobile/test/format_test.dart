import 'package:flutter_test/flutter_test.dart';
import 'package:ladecockpit_mobile/format.dart';

void main() {
  test('uses a decimal comma', () {
    expect(formatNumber(65.1, 2), '65,10');
    expect(formatNumber(0.4, 2), '0,40');
    expect(formatNumber(0.4534, 3), '0,453');
    expect(formatNumber(151.74, 1), '151,7');
    expect(formatNumber(7, 0), '7');
  });

  test('groups thousands with a dot', () {
    expect(formatNumber(1234.5, 1), '1.234,5');
    expect(formatNumber(999, 0), '999');
    expect(formatNumber(1000, 0), '1.000');
    expect(formatNumber(1234567.891, 2), '1.234.567,89');
  });

  test('handles negative and odd values', () {
    expect(formatNumber(-4.11, 2), '-4,11');
    expect(formatNumber(-1234.5, 1), '-1.234,5');
    expect(formatNumber(-0.001, 2), '0,00');
    expect(formatNumber(double.nan, 2), '–');
    expect(formatNumber(double.infinity, 1), '–');
  });
}
