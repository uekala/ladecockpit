// Verbindung zum Ladecockpit-Server: Anfragen, Antworten und verständliche Fehlertexte.
// Aus main.dart herausgelöst, damit die Oberfläche und die Server-Anbindung getrennt bleiben.
// Die Texte werden zur Laufzeit nachgeschlagen (tr) – wie in main.dart gelten dieselben Ausnahmen.
// ignore_for_file: prefer_const_constructors, prefer_const_literals_to_create_immutables, prefer_const_declarations, unnecessary_brace_in_string_interps

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import 'document_response.dart';
import 'l10n.dart';

class CockpitClient {
  static const _storage = FlutterSecureStorage();
  static const _urlKey = 'server_url';
  static const _passwordKey = 'app_password';

  CockpitClient({
    http.Client? httpClient,
    Future<String?> Function()? serverUrlProvider,
    Future<String?> Function()? passwordProvider,
  })  : _http = httpClient ?? http.Client(),
        _serverUrlProvider = serverUrlProvider,
        _passwordProvider = passwordProvider;

  final http.Client _http;
  final Future<String?> Function()? _serverUrlProvider;
  final Future<String?> Function()? _passwordProvider;

  Future<String?> get serverUrl =>
      _serverUrlProvider?.call() ?? _storage.read(key: _urlKey);
  Future<String?> get password =>
      _passwordProvider?.call() ?? _storage.read(key: _passwordKey);

  Future<void> saveConnection(String url, String password) async {
    await _storage.write(key: _urlKey, value: url.trim().replaceAll(RegExp(r'/+$'), ''));
    await _storage.write(key: _passwordKey, value: password);
  }

  Future<Map<String, String>> _headers({bool json = false}) async {
    return cockpitRequestHeaders(await password, json: json);
  }

  /// Kopfzeilen für Anfragen, die die Oberfläche selbst stellt (z. B. Seitenbilder der Rechnungs-PDFs).
  Future<Map<String, String>> requestHeaders() => _headers();

  /// Unverschlüsseltes HTTP ist nur zu Adressen erlaubt, die nicht über das
  /// offene Internet laufen: Tailscale (100.64.0.0/10, *.ts.net,
  /// fd7a:115c:a1e0::/48), private Heimnetze (10/8, 172.16/12, 192.168/16,
  /// fc00::/7), das Gerät selbst und lokale Namen (.local, .home.arpa,
  /// .internal und Namen ohne Punkt). Alles andere braucht HTTPS.
  static bool allowsCleartextHttp(String host) {
    var name = host.toLowerCase();
    if (name.startsWith('[') && name.endsWith(']')) {
      name = name.substring(1, name.length - 1);
    }
    if (name.endsWith('.')) {
      name = name.substring(0, name.length - 1);
    }
    if (name.isEmpty) return false;
    final address = InternetAddress.tryParse(name);
    if (address != null) return _isPrivateAddress(address);
    if (name == 'localhost' || !name.contains('.')) return true;
    return ['.ts.net', '.local', '.home.arpa', '.internal'].any(name.endsWith);
  }

  static bool _isPrivateAddress(InternetAddress address) {
    if (address.isLoopback) return true;
    final b = address.rawAddress;
    if (address.type == InternetAddressType.IPv4) {
      return b[0] == 10 ||
          (b[0] == 172 && b[1] >= 16 && b[1] <= 31) ||
          (b[0] == 192 && b[1] == 168) ||
          (b[0] == 100 && b[1] >= 64 && b[1] <= 127);
    }
    if (address.type == InternetAddressType.IPv6) {
      return (b[0] & 0xfe) == 0xfc;
    }
    return false;
  }

  Future<Uri> _endpoint(String path) async {
    final base = await serverUrl;
    if (base == null || base.isEmpty) {
      throw CockpitException(tr('Bitte zuerst die Serveradresse einrichten.'));
    }
    final root = Uri.tryParse(base);
    if (root == null || !root.hasScheme || root.host.isEmpty ||
        (root.scheme != 'http' && root.scheme != 'https')) {
      throw CockpitException(tr('Bitte eine gültige HTTP- oder HTTPS-Serveradresse eingeben.'));
    }
    if (root.scheme == 'http' && !allowsCleartextHttp(root.host)) {
      throw CockpitException(
        tr('Unverschlüsseltes HTTP ist aus Sicherheitsgründen nur im eigenen Netz erlaubt (Tailscale oder Heimnetz). Für andere Adressen bitte HTTPS verwenden.'),
      );
    }
    return root.resolve(path);
  }

  Future<Map<String, dynamic>> invoicePages(String sessionId) async {
    final uri = await _endpoint('/api/invoice/${Uri.encodeComponent(sessionId)}/pages');
    final response = await _http.get(uri, headers: await _headers(json: true))
        .timeout(Duration(seconds: 30));
    return parseDocumentPagesResponse(
      response.statusCode,
      response.body,
      documentLabel: tr('die Rechnung'),
      notFoundMessage: tr('Die Rechnung ist auf dem Server noch nicht verfügbar.'),
    );
  }

  Future<Uri> invoicePageUri(String sessionId, int page) =>
      _endpoint('/api/invoice/${Uri.encodeComponent(sessionId)}/page/$page.png');

  /// Die Rechnung einer Ladung als PDF, zum Teilen oder Speichern.
  Future<List<int>> invoicePdf(String sessionId) async {
    final uri = await _endpoint('/api/invoice/${Uri.encodeComponent(sessionId)}');
    final response = await _http.get(uri, headers: await _headers())
        .timeout(Duration(seconds: 60));
    if (response.statusCode == 401) {
      throw CockpitException(tr('Anmeldung fehlgeschlagen. Bitte App-Passwort prüfen.'));
    }
    if (response.statusCode != 200) {
      throw CockpitException(trf('Die Rechnung konnte nicht geladen werden (HTTP {0}).', [response.statusCode]));
    }
    return response.bodyBytes;
  }

  /// Betreibernamen, die der Server kennt, zur Auswahl.
  Future<List<String>> knownOperators() async {
    final uri = await _endpoint('/api/operators');
    final response = await _http.get(uri, headers: await _headers(json: true))
        .timeout(Duration(seconds: 30));
    if (response.statusCode != 200) return [];
    final decoded = jsonDecode(utf8.decode(response.bodyBytes, allowMalformed: true));
    final known = decoded is Map ? decoded['known'] : null;
    return known is List ? known.map((name) => name.toString()).toList() : [];
  }

  /// Ordnet einem Standort einen Betreiber zu; ein leerer Name entfernt die Zuordnung.
  Future<void> assignOperator(String site, String operator) async {
    final uri = await _endpoint('/api/operator');
    final response = await _http.put(uri,
        headers: {...await _headers(json: true), 'Content-Type': 'application/json'},
        body: jsonEncode({'site': site, 'operator': operator}))
        .timeout(Duration(seconds: 30));
    if (response.statusCode == 401) {
      throw CockpitException(tr('Anmeldung fehlgeschlagen. Bitte App-Passwort prüfen.'));
    }
    if (response.statusCode == 404) {
      throw CockpitException(tr('Der Server kann noch keine Betreiber zuordnen. Bitte Ladecockpit aktualisieren.'));
    }
    if (response.statusCode != 200) {
      throw CockpitException(trf('Betreiber konnte nicht gespeichert werden (HTTP {0}).', [response.statusCode]));
    }
  }

  /// Blendet einen Tipp der Einrichtungsprüfung aus; ohne ID erscheint jeder ausgeblendete Tipp wieder.
  Future<void> hideHint(String? id) async {
    final uri = await _endpoint(id == null ? '/api/hints/hidden' : '/api/hint');
    final headers = {...await _headers(json: true), 'Content-Type': 'application/json'};
    final response = await (id == null
            ? _http.delete(uri, headers: headers)
            : _http.put(uri, headers: headers, body: jsonEncode({'id': id, 'hidden': true})))
        .timeout(Duration(seconds: 30));
    if (response.statusCode == 401) {
      throw CockpitException(tr('Anmeldung fehlgeschlagen. Bitte App-Passwort prüfen.'));
    }
    if (response.statusCode != 200) {
      throw CockpitException(trf('Konnte nicht gespeichert werden (HTTP {0}).', [response.statusCode]));
    }
  }

  Future<String> csvExport() async {
    final uri = await _endpoint('/api/export.csv');
    final response = await _http.get(uri, headers: await _headers())
        .timeout(Duration(seconds: 60));
    if (response.statusCode == 401) {
      throw CockpitException(tr('Anmeldung fehlgeschlagen. Bitte App-Passwort prüfen.'));
    }
    if (response.statusCode != 200) {
      throw CockpitException(trf('CSV-Export fehlgeschlagen (HTTP {0}).', [response.statusCode]));
    }
    return utf8.decode(response.bodyBytes, allowMalformed: true);
  }

  /// Ladehistorie, Messwerte und Rechnungen in einer Datei (ohne die Tesla-Anmeldung).
  Future<List<int>> backupZip() async {
    final uri = await _endpoint('/api/backup.zip');
    final response = await _http.get(uri, headers: await _headers())
        .timeout(Duration(seconds: 180));
    if (response.statusCode == 401) {
      throw CockpitException(tr('Anmeldung fehlgeschlagen. Bitte App-Passwort prüfen.'));
    }
    if (response.statusCode != 200) {
      throw CockpitException(trf('Datensicherung fehlgeschlagen (HTTP {0}).', [response.statusCode]));
    }
    return response.bodyBytes;
  }

  Future<List<int>> invoiceZip(String month) async {
    final uri = await _endpoint('/api/invoices/$month.zip');
    final response = await _http.get(uri, headers: await _headers())
        .timeout(Duration(seconds: 120));
    if (response.statusCode == 401) {
      throw CockpitException(tr('Anmeldung fehlgeschlagen. Bitte App-Passwort prüfen.'));
    }
    if (response.statusCode == 404) {
      throw CockpitException(tr('Für diesen Monat sind keine Rechnungen vorhanden.'));
    }
    if (response.statusCode != 200) {
      throw CockpitException(trf('Rechnungs-ZIP fehlgeschlagen (HTTP {0}).', [response.statusCode]));
    }
    return response.bodyBytes;
  }

  Future<Map<String, dynamic>> monthReportPages(String month) async {
    final uri = await _endpoint('/api/report/$month/pages');
    final response = await _http.get(uri, headers: await _headers(json: true))
        .timeout(Duration(seconds: 60));
    return parseDocumentPagesResponse(
      response.statusCode,
      response.body,
      documentLabel: tr('den Monatsbericht'),
    );
  }

  Future<Uri> monthReportPageUri(String month, int page) =>
      _endpoint('/api/report/$month/page/$page.png');

  Future<Map<String, dynamic>> yearReportPages(String year) async {
    final uri = await _endpoint('/api/year/$year/pages');
    final response = await _http.get(uri, headers: await _headers(json: true))
        .timeout(Duration(seconds: 60));
    return parseDocumentPagesResponse(
      response.statusCode,
      response.body,
      documentLabel: tr('die Jahresübersicht'),
    );
  }

  Future<Uri> yearReportPageUri(String year, int page) =>
      _endpoint('/api/year/$year/page/$page.png');

  Future<Map<String, dynamic>> dashboard() async {
    final uri = await _endpoint('/api/dashboard');
    final headers = await _headers(json: true);
    final response = await _http.get(uri, headers: headers)
        .timeout(Duration(seconds: 20));
    return parseDashboardResponse(response.statusCode, response.body);
  }
}

Map<String, String> cockpitRequestHeaders(String? password, {bool json = false}) {
  final headers = <String, String>{
    'Accept': json ? 'application/json' : '*/*',
  };
  final secret = password ?? '';
  if (secret.isNotEmpty) {
    headers['Authorization'] =
        'Basic ${base64Encode(utf8.encode('ladecockpit:$secret'))}';
  }
  return headers;
}

Map<String, dynamic> parseDashboardResponse(int statusCode, String body) {
  if (statusCode == 401 || statusCode == 403) {
    throw CockpitException(
      tr('Anmeldung fehlgeschlagen (HTTP 401/403). Bitte App-Passwort und Zugriffsrechte prüfen.'),
    );
  }
  if (statusCode != 200) {
    throw CockpitException(trf('Server antwortet mit HTTP {0}.', [statusCode]));
  }
  final decoded = jsonDecode(body);
  if (decoded is! Map<String, dynamic>) {
    throw CockpitException(tr('Ungültige Antwort vom Ladecockpit.'));
  }
  return decoded;
}

String connectionErrorMessage(Object error) {
if (error is CockpitException) {
  return error.message;
}
if (error is TimeoutException) {
  return tr('Zeitüberschreitung: Der Server hat nicht rechtzeitig geantwortet. Bitte Verbindung prüfen und erneut versuchen.');
}
if (error is HandshakeException) {
  return tr('Sichere Verbindung fehlgeschlagen: Bitte HTTPS-Zertifikat und Serveradresse prüfen.');
}
if (error is SocketException) {
  final details = <String>[
    error.message,
    if (error.osError != null) error.osError!.message,
    if (error.address != null) trf('Adresse: {0}', [error.address]),
    if (error.port != null) trf('Port: {0}', [error.port]),
  ].where((part) => part.trim().isNotEmpty).toSet().join(' · ');
  return trf('Server nicht erreichbar: Netzwerk, Serveradresse oder VPN/Tailscale-Verbindung prüfen.\nDiagnose: {0}', [details]);
}
if (error is HttpException) {
  return trf('Netzwerkfehler bei der HTTP-Verbindung: {0}', [error.message]);
}
if (error is FormatException) {
  return tr('Der Server hat eine ungültige Antwort gesendet. Bitte später erneut versuchen.');
}
return trf('Verbindung fehlgeschlagen.\nDiagnose: {0} · {1}', [error.runtimeType, error]);
}

/// Fehlertext für Meldungen: Netzwerkfehler wie beim Laden, sonst ohne „Exception:“-Vorsatz.
String friendlyError(Object error) {
  if (error is CockpitException || error is TimeoutException || error is SocketException ||
      error is HandshakeException || error is HttpException || error is FormatException) {
    return connectionErrorMessage(error);
  }
  final text = error.toString().replaceFirst(RegExp(r'^[A-Za-z]*Exception[:(]?\s*'), '').trim();
  return text.isEmpty ? tr('Das hat nicht geklappt.') : trf('Das hat nicht geklappt: {0}', [text]);
}
