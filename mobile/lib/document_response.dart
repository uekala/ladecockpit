import 'dart:convert';

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
    throw const CockpitException(
      'Anmeldung fehlgeschlagen. Bitte App-Passwort und Zugriffsrechte prüfen.',
    );
  }
  if (statusCode == 404 && notFoundMessage != null) {
    throw CockpitException(notFoundMessage);
  }
  if (statusCode != 200) {
    throw CockpitException(
      '$documentLabel konnte nicht geladen werden (HTTP $statusCode).',
    );
  }

  final decoded = jsonDecode(body);
  if (decoded is! Map<String, dynamic> ||
      decoded['pages'] is! int ||
      (decoded['pages'] as int) < 1) {
    throw CockpitException('Ungültige Antwort für $documentLabel.');
  }
  return decoded;
}
