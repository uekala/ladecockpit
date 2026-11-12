import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:ladecockpit_mobile/format.dart';
import 'package:ladecockpit_mobile/l10n.dart';
import 'package:ladecockpit_mobile/l10n_en.dart';

/// The value of a single-quoted Dart string literal as written in the source.
String _unescape(String source) => source.replaceAllMapped(
      RegExp(r'\\(.)'),
      (match) => switch (match.group(1)) { 'n' => '\n', 't' => '\t', final other => other! },
    );

void main() {
  tearDown(() => appLanguage = 'de');

  test('German is the default and unknown texts stay German', () {
    expect(tr('Später'), 'Später');
    appLanguage = 'en';
    expect(tr('Später'), 'Later');
    expect(tr('Ein Text ohne Übersetzung'), 'Ein Text ohne Übersetzung');
  });

  test('values are put into the text in both languages', () {
    expect(trf('Ladelimit {0} %', [80]), 'Ladelimit 80 %');
    expect(trf('{0}.{1}.{2}, {3}:{4} Uhr', ['12', '11', 2026, '18', '30']), '12.11.2026, 18:30 Uhr');
    appLanguage = 'en';
    expect(trf('Ladelimit {0} %', [80]), 'Charge limit 80 %');
    expect(trf('{0}.{1}.{2}, {3}:{4} Uhr', ['12', '11', 2026, '18', '30']), '2026-11-12, 18:30');
    expect(trf('Ohne Eintrag {0} {1}', ['a']), 'Ohne Eintrag a {1}');
  });

  test('numbers follow the language', () {
    expect(formatNumber(1234.5, 1), '1.234,5');
    appLanguage = 'en';
    expect(formatNumber(1234.5, 1), '1,234.5');
    expect(formatNumber(0.4, 2), '0.40');
  });

  test('the phone or server language maps to de or en', () {
    expect(languageFrom('de_DE'), 'de');
    expect(languageFrom('en_US'), 'en');
    expect(languageFrom('EN'), 'en');
    expect(languageFrom('fr_FR'), isNull);
    expect(languageFrom(null), isNull);
  });

  test('every text in the code has an English entry', () {
    final missing = <String>{};
    final pattern = RegExp(r"\btrf?\(\s*'((?:[^'\\]|\\.)*)'");
    for (final file in Directory('lib').listSync(recursive: true).whereType<File>()) {
      if (!file.path.endsWith('.dart') || file.path.endsWith('l10n_en.dart')) continue;
      for (final match in pattern.allMatches(file.readAsStringSync())) {
        final key = _unescape(match.group(1)!);
        if (!english.containsKey(key)) missing.add(key);
      }
    }
    expect(missing, isEmpty, reason: missing.join('\n'));
  });

  test('English entries keep the placeholders of the German text', () {
    final placeholder = RegExp(r'\{\d+\}');
    for (final entry in english.entries) {
      final german = placeholder.allMatches(entry.key).map((m) => m.group(0)).toSet();
      final englishOnes = placeholder.allMatches(entry.value).map((m) => m.group(0)).toSet();
      expect(englishOnes, german, reason: entry.key);
      expect(entry.value.trim(), isNotEmpty, reason: entry.key);
    }
  });
}
