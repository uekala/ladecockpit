import 'l10n_en.dart';

/// Language of the app: 'de' or 'en'. The texts in the code are German;
/// English is looked up in [english]. The app follows the language of the
/// Ladecockpit server (APP_LANG) once it has answered, and the phone's
/// language before that.
String appLanguage = 'de';

/// 'en' for an English server or phone, 'de' for a German one, else null.
String? languageFrom(dynamic value) {
  final text = value?.toString().toLowerCase() ?? '';
  if (text.startsWith('en')) return 'en';
  if (text.startsWith('de')) return 'de';
  return null;
}

/// The text in the app's language.
String tr(String german) => appLanguage == 'en' ? (english[german] ?? german) : german;

/// Like [tr] for a text with values: `{0}`, `{1}` … are replaced by [values].
String trf(String german, List<Object?> values) {
  final template = tr(german);
  return template.replaceAllMapped(RegExp(r'\{(\d+)\}'), (match) {
    final index = int.parse(match.group(1)!);
    return index < values.length ? '${values[index]}' : match.group(0)!;
  });
}
