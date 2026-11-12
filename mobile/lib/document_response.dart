import 'dart:convert';

import 'l10n.dart';

class CockpitException implements Exception {
  const CockpitException(this.message);
  final String message;

  @override
  String toString() => message;
}

/// Validates the metadata response returned by the invoice and report page APIs.
Map<String, dynamic> parseDocumentPagesResponse(
  int statusCode,
  String body, {
  required String documentLabel,
  String? notFoundMessage,
}) {
  if (statusCode == 401 || statusCode == 403) {
    throw CockpitException(
      tr('Anmeldung fehlgeschlagen. Bitte App-Passwort und Zugriffsrechte prüfen.'),
    );
  }
  if (statusCode == 404 && notFoundMessage != null) {
    throw CockpitException(notFoundMessage);
  }
  if (statusCode != 200) {
    throw CockpitException(
      trf('{0} konnte nicht geladen werden (HTTP {1}).', [documentLabel, statusCode]),
    );
  }

  final decoded = jsonDecode(body);
  if (decoded is! Map<String, dynamic> ||
      decoded['pages'] is! int ||
      (decoded['pages'] as int) < 1) {
    throw CockpitException(trf('Ungültige Antwort für {0}.', [documentLabel]));
  }
  return decoded;
}
