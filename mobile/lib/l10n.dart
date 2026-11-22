import 'l10n_en.dart';

/// Sprache der App: 'de' oder 'en'. Die Texte im Code sind deutsch;
/// Englisch wird in [english] nachgeschlagen. Die App folgt der Sprache des
/// Ladecockpit-Servers (APP_LANG), sobald er geantwortet hat, und davor der
/// Sprache des Handys.
String appLanguage = 'de';

/// 'en' für einen englischen Server oder ein englisches Handy, 'de' für ein deutsches, sonst null.
String? languageFrom(dynamic value) {
  final text = value?.toString().toLowerCase() ?? '';
  if (text.startsWith('en')) return 'en';
  if (text.startsWith('de')) return 'de';
  return null;
}

/// Der Text in der Sprache der App.
String tr(String german) => appLanguage == 'en' ? (english[german] ?? german) : german;

/// Wie [tr] für einen Text mit Werten: `{0}`, `{1}` … werden durch [values] ersetzt.
String trf(String german, List<Object?> values) {
  final template = tr(german);
  return template.replaceAllMapped(RegExp(r'\{(\d+)\}'), (match) {
    final index = int.parse(match.group(1)!);
    return index < values.length ? '${values[index]}' : match.group(0)!;
  });
}
