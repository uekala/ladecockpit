// The texts are looked up at run time (tr), so widgets holding them cannot be const.
// ignore_for_file: prefer_const_constructors, prefer_const_literals_to_create_immutables, prefer_const_declarations, unnecessary_brace_in_string_interps
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';
export 'document_response.dart' show CockpitException;
import 'dashboard_cache.dart';
import 'document_response.dart';
import 'format.dart';
import 'l10n.dart';
import 'theme/app_theme.dart';
import 'update_check.dart';

void main() {
  // Until the server has answered, the app speaks the phone's language.
  appLanguage = languageFrom(Platform.localeName) ?? 'en';
  runApp(const LadecockpitApp());
}

class LadecockpitApp extends StatelessWidget {
  const LadecockpitApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: tr('Ladecockpit'),
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      home: DashboardPage(),
    );
  }
}

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

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key, this.client, this.updates, this.cache});

  /// Injectable for tests; the app uses the defaults.
  final CockpitClient? client;
  final UpdateChecker? updates;
  final DashboardCache? cache;

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  late final CockpitClient _client = widget.client ?? CockpitClient();
  late final UpdateChecker _updates = widget.updates ?? UpdateChecker();
  late final DashboardCache _cache = widget.cache ?? DashboardCache();
  // True while the figures on screen come from the phone's own copy.
  bool _fromCache = false;
  Map<String, dynamic>? _data;
  String? _error;
  bool _loading = false;
  int _selectedTab = 0;
  DateTime? _lastSuccessfulFetch;
  String _sessionMonthFilter = 'all';
  String _sessionNetworkFilter = 'all';
  String _sessionSiteFilter = 'all';

  @override
  void initState() {
    super.initState();
    _load();
    _checkForUpdate();
  }

  Future<void> _checkForUpdate() async {
    final update = await _updates.check();
    if (update == null || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    messenger.showMaterialBanner(
      MaterialBanner(
        leading: Icon(Icons.system_update_outlined, color: AppTheme.accentGreen),
        content: Text(trf('Ladecockpit {0} ist verfügbar (installiert: {1}).', [update.version, appVersion])),
        actions: [
          TextButton(
            onPressed: messenger.hideCurrentMaterialBanner,
            child: Text(tr('Später')),
          ),
          FilledButton(
            onPressed: () async {
              messenger.hideCurrentMaterialBanner();
              final opened = await launchUrl(
                Uri.parse(update.downloadUrl),
                mode: LaunchMode.externalApplication,
              );
              if (!opened && mounted) {
                messenger.showSnackBar(SnackBar(content: Text(trf('Download-Seite: {0}', [update.pageUrl]))));
              }
            },
            child: Text(tr('Update laden')),
          ),
        ],
      ),
    );
  }

  String _fetchTimeLabel(DateTime? value) {
    if (value == null) return tr('Noch kein erfolgreicher Abruf');
    final date = value.toLocal();
    final day = date.day.toString().padLeft(2, '0');
    final month = date.month.toString().padLeft(2, '0');
    final hour = date.hour.toString().padLeft(2, '0');
    final minute = date.minute.toString().padLeft(2, '0');
    return trf('{0}.{1}.{2}, {3}:{4} Uhr', [day, month, date.year, hour, minute]);
  }

  Future<void> _load() async {
    if (_loading) return;
    setState(() { _loading = true; _error = null; });
    try {
      final data = await _client.dashboard();
      final now = DateTime.now();
      if (mounted) {
        setState(() {
          // The app follows the language of the server (APP_LANG), like the web app.
          appLanguage = languageFrom(data['lang']) ?? appLanguage;
          _data = data;
          _lastSuccessfulFetch = now;
          _fromCache = false;
        });
      }
      unawaited(_cache.write(data, now));
    } catch (e) {
      // Nothing on screen yet: show the last figures the phone has kept.
      final cached = _data == null ? await _cache.read() : null;
      if (mounted) {
        setState(() {
          _error = connectionErrorMessage(e);
          if (cached != null) {
            appLanguage = languageFrom(cached.data['lang']) ?? appLanguage;
            _data = cached.data;
            _lastSuccessfulFetch = cached.fetchedAt;
            _fromCache = true;
          }
        });
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _settings() async {
    final urlController = TextEditingController(text: await _client.serverUrl ?? '');
    final passwordController = TextEditingController(text: await _client.password ?? '');
    if (!mounted) {
      urlController.dispose();
      passwordController.dispose();
      return;
    }
    final hasSavedServer = urlController.text.trim().isNotEmpty;
    final previousUrl = urlController.text.trim();
    final showUpdateSwitch = _updates.supported;
    var updateCheck = showUpdateSwitch && await _updates.enabled;
    if (!mounted) {
      urlController.dispose();
      passwordController.dispose();
      return;
    }
    try {
      final saved = await showDialog<bool>(
        context: context,
        builder: (context) => StatefulBuilder(builder: (context, setDialogState) => AlertDialog(
          title: Row(
            children: [
              Icon(Icons.dns_outlined, color: AppTheme.accentGreen, size: 22),
              SizedBox(width: 10),
              Expanded(child: Text(tr('Serververbindung'))),
            ],
          ),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: double.infinity,
                  padding: EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: (hasSavedServer ? AppTheme.accentGreen : AppTheme.accentTeal)
                        .withValues(alpha: 0.08),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        hasSavedServer ? Icons.check_circle_outline : Icons.info_outline,
                        color: hasSavedServer ? AppTheme.accentGreen : AppTheme.accentTeal,
                        size: 19,
                      ),
                      SizedBox(width: 9),
                      Expanded(
                        child: Text(
                          hasSavedServer
                              ? tr('Eine Serveradresse ist auf diesem Gerät hinterlegt.')
                              : tr('Hinterlege die Adresse deines Ladecockpit-Servers.'),
                          style: TextStyle(fontSize: 12, height: 1.35),
                        ),
                      ),
                    ],
                  ),
                ),
                SizedBox(height: 18),
                Text(tr('SERVERZUGRIFF'),
                  style: TextStyle(
                    color: AppTheme.accentGreen,
                    fontSize: 10,
                    letterSpacing: 1.1,
                    fontWeight: FontWeight.w800,
                  )),
                SizedBox(height: 8),
                TextField(
                  controller: urlController,
                  keyboardType: TextInputType.url,
                  textInputAction: TextInputAction.next,
                  autocorrect: false,
                  enableSuggestions: false,
                  decoration: InputDecoration(
                    prefixIcon: Icon(Icons.link_rounded),
                    labelText: tr('Serveradresse'),
                    hintText: 'https://ladecockpit.example:8077',
                    helperText: tr('Adresse mit Port, z. B. über Tailscale oder im Heimnetz'),
                    helperMaxLines: 2,
                  ),
                ),
                SizedBox(height: 16),
                Text(tr('ANMELDUNG'),
                  style: TextStyle(
                    color: AppTheme.accentGreen,
                    fontSize: 10,
                    letterSpacing: 1.1,
                    fontWeight: FontWeight.w800,
                  )),
                SizedBox(height: 8),
                TextField(
                  controller: passwordController,
                  obscureText: true,
                  textInputAction: TextInputAction.done,
                  autocorrect: false,
                  enableSuggestions: false,
                  decoration: InputDecoration(
                    prefixIcon: Icon(Icons.lock_outline_rounded),
                    labelText: tr('App-Passwort'),
                    helperText: tr('Optional – nur wenn dein Server ein Passwort verlangt'),
                    helperMaxLines: 2,
                  ),
                ),
                if (showUpdateSwitch) ...[
                  SizedBox(height: 8),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    value: updateCheck,
                    onChanged: (value) => setDialogState(() => updateCheck = value),
                    title: Text(tr('Nach Updates suchen')),
                    subtitle: Text(
                      tr('Fragt beim Start bei GitHub nach der neuesten Version. Es werden keine Ladedaten übertragen.'),
                      style: TextStyle(fontSize: 11, height: 1.35),
                    ),
                  ),
                ],
                SizedBox(height: 10),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.shield_outlined, size: 16, color: AppTheme.textSecondary),
                    SizedBox(width: 7),
                    Expanded(
                      child: Text(
                        tr('Die Zugangsdaten werden geschützt auf diesem Gerät gespeichert. Die Verbindung erfolgt direkt zu deinem Server.'),
                        style: TextStyle(color: AppTheme.textSecondary, fontSize: 11, height: 1.35),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: Text(tr('Abbrechen')),
            ),
            FilledButton.icon(
              onPressed: () => Navigator.pop(context, true),
              icon: Icon(Icons.save_outlined, size: 18),
              label: Text(tr('Speichern & verbinden')),
            ),
          ],
        )),
      );
      if (saved == true) {
        if (showUpdateSwitch) await _updates.setEnabled(updateCheck);
        await _client.saveConnection(urlController.text, passwordController.text);
        if (urlController.text.trim() != previousUrl) {
          // Another server: its figures must not mix with the old ones.
          await _cache.clear();
          if (mounted) setState(() => _data = null);
        }
        await _load();
      }
    } finally {
      urlController.dispose();
      passwordController.dispose();
    }
  }

  String _value(dynamic value, {int? digits}) {
    if (value == null) return '–';
    if (value is num && digits != null) return formatNumber(value, digits);
    if (value is double) return formatNumber(value, 1);
    if (value is int) return formatNumber(value, 0);
    if (value is Map || value is List) return '';
    return value.toString();
  }

  Widget _metric(String title, dynamic value, {String suffix = '', int? digits}) {
    final text = _value(value, digits: digits);
    if (text.isEmpty) return SizedBox.shrink();
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [AppTheme.surfaceElevated, AppTheme.surface],
          ),
        ),
        padding: EdgeInsets.fromLTRB(15, 14, 15, 15),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                Container(
                  width: 6,
                  height: 6,
                  decoration: BoxDecoration(
                    color: AppTheme.accentTeal,
                    shape: BoxShape.circle,
                  ),
                ),
                SizedBox(width: 7),
                Expanded(
                  child: Text(
                    title.toUpperCase(),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: AppTheme.textSecondary,
                      fontSize: 9,
                      height: 1.25,
                      letterSpacing: 0.8,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ],
            ),
            SizedBox(height: 6),
            // Flexible + FittedBox: the value shrinks instead of overflowing
            // when a long title takes two lines on a narrow phone.
            Flexible(
              child: FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerLeft,
                child: Text(
                  '$text$suffix',
                  maxLines: 1,
                  style: TextStyle(
                    color: AppTheme.textPrimary,
                    fontSize: 23,
                    height: 1.05,
                    fontWeight: FontWeight.w800,
                    letterSpacing: -0.7,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _homeChargingSummary(Map<String, dynamic>? home) {
    if (home == null || (home['kwh'] == null && home['cost'] == null)) {
      return SizedBox.shrink();
    }
    final energy = home['kwh'] == null ? '–' : _sectionValue('kwh', home['kwh']);
    final cost = home['cost'] == null ? '–' : _sectionValue('total_cost', home['cost']);
    return Card(
      margin: EdgeInsets.only(top: 2, bottom: 10),
      child: Padding(
        padding: EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        child: Row(
          children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: AppTheme.accentTeal.withValues(alpha: 0.10),
                borderRadius: BorderRadius.circular(11),
              ),
              child: Icon(Icons.home_outlined,
                color: AppTheme.accentTeal, size: 19),
            ),
            SizedBox(width: 11),
            Expanded(child: Text(tr('Zuhause geladen'),
              style: TextStyle(fontWeight: FontWeight.w600))),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(energy, style: TextStyle(fontWeight: FontWeight.w700)),
                SizedBox(height: 2),
                Text(cost, style: TextStyle(
                  color: AppTheme.textSecondary, fontSize: 11)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _sectionLabel(String key) {
    const labels = <String, String>{
      'soc': 'Akkustand', 'range': 'Reichweite', 'as_of': 'Stand von',
      'floor': 'Akku-Untergrenze', 'target': 'Ladelimit',
      'sessions': 'Ladevorgänge', 'count': 'Anzahl',
      'kwh': 'Geladene Energie', 'cost': 'Ladekosten',
      'charge_cost': 'Reine Ladekosten', 'total_cost': 'Gesamtkosten',
      'avg_price': 'Durchschnittspreis', 'price': 'Preis pro kWh',
      'avg_kw': 'Durchschnittliche Ladeleistung', 'duration_min': 'Ladedauer',
      'idle': 'Standgebühren', 'credit': 'Gutschriften',
      'site': 'Standort', 'operator': 'Betreiber', 'address': 'Adresse',
      'start': 'Beginn', 'end': 'Ende', 'network': 'Ladenetz',
      'date': 'Voraussichtlicher Ladestopp', 'text': 'Prognose',
      'days_to_floor': 'Tage bis zur Untergrenze',
      'rate_pct_day': 'Akkuverlust pro Tag', 'dist_day': 'Strecke pro Tag',
      'plan_saving': 'Mögliche Ersparnis', 'plan_site': 'Empfohlener Standort',
      'plan_date': 'Empfohlenes Datum', 'model': 'Modell', 'trim': 'Ausstattung',
      'paint': 'Farbe', 'wheels': 'Felgen', 'vin': 'Fahrzeug-ID',
      'generation': 'Baureihe',
      'range_at_100': 'Reichweite bei 100 %', 'change_pct': 'Veränderung',
      'since': 'Seit', 'samples': 'Messwerte', 'dc_share': 'Supercharger-Anteil',
      'per_100': 'Kosten pro 100 km', 'kwh_per_100': 'Verbrauch pro 100 km',
      'distance': 'Gefahrene Strecke', 'savings': 'Ersparnis gegenüber Verbrenner',
      'fuel_equivalent': 'Vergleichbare Spritkosten', 'label': 'Bezeichnung',
      'best_time': 'Günstigste Ladezeit', 'best_site': 'Günstigster Standort',
      'best_time_price': 'Preis zur besten Ladezeit',
      'best_site_price': 'Preis am günstigsten Standort',
    };
    return tr(labels[key] ?? key.replaceAll('_', ' ').replaceFirstMapped(
      RegExp(r'^[a-z]'), (match) => match.group(0)!.toUpperCase()));
  }

  String _sectionValue(String key, dynamic value) {
    if (value == null) return '–';
    const percentKeys = {'soc', 'floor', 'target', 'change_pct', 'dc_share'};
    const energyKeys = {'kwh'};
    const moneyKeys = {'cost', 'charge_cost', 'total_cost', 'idle', 'credit',
      'savings', 'fuel_equivalent', 'plan_saving'};
    const priceKeys = {'price', 'avg_price', 'best_time_price', 'best_site_price'};
    const distanceKeys = {'range', 'distance', 'dist_day', 'range_at_100'};
    if (value is num) {
      final digits = priceKeys.contains(key) ? 3
          : moneyKeys.contains(key) || key == 'per_100' ? 2
          : energyKeys.contains(key) || key == 'avg_kw' ||
              percentKeys.contains(key) || key == 'rate_pct_day' ||
              key == 'dist_day' || key == 'kwh_per_100'
              ? 1
              : value is int || value == value.roundToDouble() ? 0 : 1;
      final number = formatNumber(value, digits);
      if (percentKeys.contains(key)) return '$number %';
      if (energyKeys.contains(key)) return trf('{0} kWh', [number]);
      if (moneyKeys.contains(key)) return '$number €';
      if (priceKeys.contains(key)) return trf('{0} €/kWh', [number]);
      if (key == 'dist_day') return trf('{0} km/Tag', [number]);
      if (distanceKeys.contains(key)) return trf('{0} km', [number]);
      if (key == 'avg_kw') return trf('{0} kW', [number]);
      if (key == 'rate_pct_day') return trf('{0} %/Tag', [number]);
      if (key == 'per_100') return trf('{0} €/100 km', [number]);
      if (key == 'kwh_per_100') return trf('{0} kWh/100 km', [number]);
      if (key == 'duration_min') return _durationLabel(value);
      if (key == 'days_to_floor') return trf('{0} Tage', [number]);
      return number;
    }
    if (value is bool) return value ? tr('Ja') : tr('Nein');
    if (key == 'network') return value == 'multipass' ? tr('MultiPass') : tr('Supercharger');
    if (value is String && RegExp(r'^\d{4}-\d{2}-\d{2}T').hasMatch(value)) {
      return _dateTimeLabel(value);
    }
    return value.toString();
  }

  /// Joins the non-empty parts of a card's summary line.
  String? _summaryLine(List<dynamic> parts) {
    final texts = parts
        .map((part) => part?.toString().trim() ?? '')
        .where((part) => part.isNotEmpty)
        .toList();
    return texts.isEmpty ? null : texts.join(' · ');
  }

  String _shortDateLabel(dynamic value) {
    final date = DateTime.tryParse(value?.toString() ?? '')?.toLocal();
    if (date == null) return '';
    final day = date.day.toString().padLeft(2, '0');
    final month = date.month.toString().padLeft(2, '0');
    return '$day.$month.';
  }

  /// [keys] picks and orders the rows; without it the card shows the plain
  /// values the server sent. [summary] is the line under the title.
  Widget _section(String title, Map<String, dynamic>? values,
      {List<String>? keys, String? summary}) {
    if (values == null || values.isEmpty) return SizedBox.shrink();
    // Internal fields mean nothing to the reader.
    const hidden = {'id', 'url', 'thumb', 'auto', 'push_state', 'currency', 'has_invoice', 'slow'};
    const hideWhenZero = {'idle', 'credit'};
    bool shown(String key, dynamic value) =>
        value != null && value is! Map && value is! List &&
        !(value is String && value.trim().isEmpty) &&
        !(hideWhenZero.contains(key) && value is num && value == 0);
    final entries = keys != null
        ? [
            for (final key in keys)
              if (shown(key, values[key])) MapEntry<String, dynamic>(key, values[key]),
          ]
        : values.entries
            .where((e) => !hidden.contains(e.key) && shown(e.key, e.value))
            .take(8).toList();
    if (entries.isEmpty) return SizedBox.shrink();

    final first = entries.first;
    final summaryText = summary ??
        '${_sectionLabel(first.key)} · ${_sectionValue(first.key, first.value)}';
    final sectionIcon = switch (title) {
      'Letzter Ladevorgang' => Icons.ev_station_rounded,
      'Gesamt' => Icons.insights_rounded,
      'Ladeprognose' => Icons.battery_charging_full_rounded,
      'Fahrzeug' => Icons.directions_car_rounded,
      _ => Icons.tune_rounded,
    };

    return Card(
      margin: EdgeInsets.only(top: 5, bottom: 5),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          key: PageStorageKey<String>('section-$title'),
          initiallyExpanded: false,
          tilePadding: EdgeInsets.symmetric(horizontal: 16, vertical: 2),
          childrenPadding: EdgeInsets.fromLTRB(16, 0, 16, 12),
          leading: Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: AppTheme.accentGreen.withValues(alpha: 0.09),
              borderRadius: BorderRadius.circular(11),
            ),
            child: Icon(sectionIcon, color: AppTheme.accentGreen, size: 19),
          ),
          title: Text(tr(title),
            style: TextStyle(fontWeight: FontWeight.w700)),
          subtitle: Text(summaryText,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
          children: [
            for (var i = 0; i < entries.length; i++) ...[
              if (i > 0) Divider(height: 1),
              Padding(
                padding: EdgeInsets.symmetric(vertical: 10),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: Text(_sectionLabel(entries[i].key),
                      style: TextStyle(color: AppTheme.textSecondary))),
                    SizedBox(width: 12),
                    Flexible(child: Text(
                      _sectionValue(entries[i].key, entries[i].value),
                      textAlign: TextAlign.end,
                      style: TextStyle(fontWeight: FontWeight.w600))),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Map<String, dynamic>? _map(dynamic value) =>
      value is Map<String, dynamic> ? value : null;

  Widget _sessionMetric(String label, String value, IconData icon) {
    final highlighted = label == tr('Kosten');
    final accent = highlighted ? AppTheme.accentGreen : AppTheme.textSecondary;
    return Container(
      padding: EdgeInsets.symmetric(horizontal: 10, vertical: 9),
      decoration: BoxDecoration(
        color: (highlighted ? AppTheme.accentGreen : AppTheme.surface)
            .withValues(alpha: highlighted ? 0.09 : 0.55),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: highlighted
            ? AppTheme.accentGreen.withValues(alpha: 0.18)
            : AppTheme.border.withValues(alpha: 0.7)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 16, color: accent),
          SizedBox(width: 7),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: AppTheme.textSecondary)),
                SizedBox(height: 3),
                Text(value, maxLines: 2, overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontWeight: FontWeight.w800,
                    color: highlighted ? AppTheme.accentGreen : AppTheme.textPrimary)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _sessions(dynamic raw) {
    if (raw is! List || raw.isEmpty) return SizedBox.shrink();
    final items = raw.whereType<Map<String, dynamic>>().toList();
    if (items.isEmpty) return SizedBox.shrink();

    String monthKey(Map<String, dynamic> item) {
      final date = DateTime.tryParse(item['start']?.toString() ?? '')?.toLocal();
      if (date == null) return '';
      return '${date.year}-${date.month.toString().padLeft(2, '0')}';
    }

    String monthLabel(String key) {
      final parts = key.split('-');
      if (parts.length != 2) return key;
      const names = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
        'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'];
      final index = int.tryParse(parts[1]);
      if (index == null || index < 1 || index > 12) return key;
      return '${tr(names[index - 1])} ${parts[0]}';
    }

    String dateLabel(dynamic value) {
      final date = DateTime.tryParse(value?.toString() ?? '')?.toLocal();
      if (date == null) return tr('Datum unbekannt');
      final day = date.day.toString().padLeft(2, '0');
      final month = date.month.toString().padLeft(2, '0');
      final hour = date.hour.toString().padLeft(2, '0');
      final minute = date.minute.toString().padLeft(2, '0');
      return trf('{0}.{1}.{2} · {3}:{4} Uhr', [day, month, date.year, hour, minute]);
    }

    String number(dynamic value, {int digits = 1}) {
      final parsed = value is num ? value : num.tryParse(value?.toString() ?? '');
      return parsed == null ? '–' : formatNumber(parsed, digits);
    }

    final months = items.map(monthKey).where((v) => v.isNotEmpty).toSet().toList()
      ..sort((a, b) => b.compareTo(a));
    final sites = items.map((s) => s['site']?.toString() ?? '')
      .where((v) => v.isNotEmpty).toSet().toList()
      ..sort((a, b) => a.toLowerCase().compareTo(b.toLowerCase()));
    final networks = items.map((s) => s['network']?.toString() ?? 'supercharger')
      .where((v) => v.isNotEmpty).toSet().toList()..sort();

    // Keep dropdown values valid when refreshed data no longer contains a previous selection.
    final selectedMonth = months.contains(_sessionMonthFilter) ? _sessionMonthFilter : 'all';
    final selectedNetwork = networks.contains(_sessionNetworkFilter) ? _sessionNetworkFilter : 'all';
    final selectedSite = sites.contains(_sessionSiteFilter) ? _sessionSiteFilter : 'all';

    final filtered = items.where((session) {
      final monthMatches = selectedMonth == 'all' ||
        monthKey(session) == selectedMonth;
      final networkMatches = selectedNetwork == 'all' ||
        (session['network']?.toString() ?? 'supercharger') == selectedNetwork;
      final siteMatches = selectedSite == 'all' ||
        (session['site']?.toString() ?? '') == selectedSite;
      return monthMatches && networkMatches && siteMatches;
    }).toList();

    Widget filterField(String label, String value, List<DropdownMenuItem<String>> options,
        ValueChanged<String?> onChanged, {double width = 150}) {
      return SizedBox(
        width: width,
        child: DropdownButtonFormField<String>(
          key: ValueKey('$label-$value'),
          initialValue: value,
          isExpanded: true,
          decoration: InputDecoration(
            labelText: label,
            isDense: true,
            contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 10),
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
          ),
          items: options,
          onChanged: onChanged,
        ),
      );
    }

    final monthOptions = <DropdownMenuItem<String>>[
      DropdownMenuItem(value: 'all', child: Text(tr('Alle Monate'))),
      ...months.map((m) => DropdownMenuItem(value: m, child: Text(monthLabel(m)))),
    ];
    final networkOptions = <DropdownMenuItem<String>>[
      DropdownMenuItem(value: 'all', child: Text(tr('Alle Netzwerke'))),
      ...networks.map((n) => DropdownMenuItem(
        value: n,
        child: Text(n == 'multipass' ? tr('MultiPass') :
          n == 'supercharger' ? tr('Supercharger') : n),
      )),
    ];
    final siteOptions = <DropdownMenuItem<String>>[
      DropdownMenuItem(value: 'all', child: Text(tr('Alle Standorte'))),
      ...sites.map((s) => DropdownMenuItem(value: s, child: Text(s,
        overflow: TextOverflow.ellipsis))),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeading(tr('Ladevorgänge'),
          trailing: '${filtered.length} / ${items.length}'),
        Builder(builder: (context) {
          final filtersActive = selectedMonth != 'all' ||
              selectedNetwork != 'all' || selectedSite != 'all';
          final filterSummary = [
            selectedMonth == 'all' ? tr('Alle Zeiträume') : monthLabel(selectedMonth),
            selectedNetwork == 'all' ? tr('Alle Netzwerke') :
              (selectedNetwork == 'multipass' ? tr('MultiPass') :
                selectedNetwork == 'supercharger' ? tr('Supercharger') : selectedNetwork),
            selectedSite == 'all' ? tr('Alle Standorte') : selectedSite,
          ].join(' · ');
          return Card(
            margin: EdgeInsets.only(bottom: 8),
            child: ExpansionTile(
              key: PageStorageKey<String>('session-filter'),
              initiallyExpanded: false,
              leading: Icon(Icons.tune,
                color: filtersActive ? Theme.of(context).colorScheme.primary : AppTheme.textSecondary),
              title: Row(
                children: [
                  Expanded(child: Text(tr('Filter'), style: TextStyle(fontWeight: FontWeight.w600))),
                  if (filtersActive)
                    Text(tr('Aktiv'), style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: Theme.of(context).colorScheme.primary, fontWeight: FontWeight.w700)),
                ],
              ),
              subtitle: Text(filterSummary, maxLines: 1, overflow: TextOverflow.ellipsis),
              childrenPadding: EdgeInsets.fromLTRB(16, 0, 16, 12),
              children: [
                LayoutBuilder(
                  builder: (context, constraints) {
                    final compact = constraints.maxWidth < 520;
                    final fields = [
                      filterField(tr('Zeitraum'), selectedMonth, monthOptions,
                        (value) => setState(() => _sessionMonthFilter = value ?? 'all'),
                        width: compact ? double.infinity : 165),
                      filterField(tr('Netzwerk'), selectedNetwork, networkOptions,
                        (value) => setState(() => _sessionNetworkFilter = value ?? 'all'),
                        width: compact ? double.infinity : 165),
                      filterField(tr('Standort'), selectedSite, siteOptions,
                        (value) => setState(() => _sessionSiteFilter = value ?? 'all'),
                        width: compact ? double.infinity : 210),
                    ];
                    if (compact) {
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          for (var i = 0; i < fields.length; i++) ...[
                            if (i > 0) SizedBox(height: 8),
                            fields[i],
                          ],
                        ],
                      );
                    }
                    return Wrap(spacing: 8, runSpacing: 8, children: fields);
                  },
                ),
                if (filtersActive)
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextButton.icon(
                      onPressed: () => setState(() {
                        _sessionMonthFilter = 'all';
                        _sessionNetworkFilter = 'all';
                        _sessionSiteFilter = 'all';
                      }),
                      icon: Icon(Icons.filter_alt_off, size: 17),
                      label: Text(tr('Filter zurücksetzen')),
                    ),
                  ),
              ],
            ),
          );
        }),
        if (filtered.isEmpty)
          Card(child: Padding(
            padding: EdgeInsets.all(16),
            child: Text(tr('Keine Ladevorgänge für diese Filter gefunden.')),
          )),
        ...filtered.take(50).map((session) {
          final site = session['site']?.toString() ?? tr('Unbekannter Standort');
          final networkValue = session['network']?.toString() ?? 'supercharger';
          final network = networkValue == 'multipass' ? tr('MultiPass') :
            networkValue == 'supercharger' ? tr('Supercharger') : networkValue;
          final kwhValue = session['kwh'];
          final costValue = session['cost'];
          final kwh = kwhValue == null ? null : number(kwhValue);
          final cost = costValue == null ? null : number(costValue, digits: 2);
          final currency = session['currency']?.toString() ?? 'EUR';
          final currencyLabel = currency == 'EUR' ? '€' : currency;
          final invoice = session['has_invoice'] == true;
          final metrics = <Widget>[
            if (kwh != null)
              _sessionMetric(tr('Energie'), trf('{0} kWh', [kwh]), Icons.bolt),
            if (cost != null)
              _sessionMetric(tr('Kosten'), '$cost $currencyLabel', Icons.euro),
            // Keep the list glanceable; effective price and duration remain in the detail view.
          ];
          return Card(
            clipBehavior: Clip.antiAlias,
            child: InkWell(
              onTap: () => _showSessionDetails(session),
              child: Padding(
                padding: EdgeInsets.fromLTRB(13, 10, 13, 11),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Container(
                        width: 38,
                        height: 38,
                        decoration: BoxDecoration(
                          color: (invoice ? AppTheme.accentGreen : AppTheme.accentTeal)
                              .withValues(alpha: 0.10),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Icon(
                          invoice ? Icons.receipt_long_outlined : Icons.ev_station,
                          size: 19,
                          color: invoice ? AppTheme.accentGreen : AppTheme.accentTeal,
                        ),
                      ),
                      SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(site, maxLines: 1, overflow: TextOverflow.ellipsis,
                              style: TextStyle(fontWeight: FontWeight.w600)),
                            SizedBox(height: 3),
                            Text(
                              '${dateLabel(session['start'])} · ${network}${invoice ? tr(' · Rechnung vorhanden') : ''}',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppTheme.textSecondary),
                            ),
                          ],
                        ),
                      ),
                      Icon(Icons.chevron_right, color: AppTheme.textSecondary),
                    ]),
                    if (metrics.isNotEmpty) ...[
                      SizedBox(height: 9),
                      Divider(height: 1),
                      SizedBox(height: 8),
                      LayoutBuilder(
                        builder: (context, constraints) {
                          final columns = constraints.maxWidth < 350 ? 1 : metrics.length.clamp(1, 3);
                          final metricWidth = (constraints.maxWidth - (columns - 1) * 8) / columns;
                          return Wrap(
                            spacing: 8,
                            runSpacing: 10,
                            children: [
                              for (final metric in metrics)
                                SizedBox(width: metricWidth, child: metric),
                            ],
                          );
                        },
                      ),
                    ],
                  ],
                ),
              ),
            ),
          );
        }),
        if (filtered.length > 50)
          Padding(
            padding: EdgeInsets.all(8),
            child: Text(tr('Es werden die ersten 50 Treffer angezeigt.'),
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppTheme.textSecondary)),
          ),
      ],
    );
  }

  String _dateTimeLabel(dynamic value) {
    final date = DateTime.tryParse(value?.toString() ?? '')?.toLocal();
    if (date == null) return '–';
    final day = date.day.toString().padLeft(2, '0');
    final month = date.month.toString().padLeft(2, '0');
    final hour = date.hour.toString().padLeft(2, '0');
    final minute = date.minute.toString().padLeft(2, '0');
    return trf('{0}.{1}.{2}, {3}:{4} Uhr', [day, month, date.year, hour, minute]);
  }

  String _numberLabel(dynamic value, {int digits = 2, String suffix = ''}) {
    final parsed = value is num ? value : num.tryParse(value?.toString() ?? '');
    return parsed == null ? '–' : '${formatNumber(parsed, digits)}$suffix';
  }

  String _durationLabel(dynamic value) {
    final minutes = value is num ? value.round() : int.tryParse(value?.toString() ?? '');
    if (minutes == null) return '–';
    final hours = minutes ~/ 60;
    final rest = minutes % 60;
    return hours > 0 ? trf('{0} Std. {1} Min.', [hours, rest]) : trf('{0} Min.', [rest]);
  }

  Widget _detailRow(String label, String value) => Padding(
    padding: EdgeInsets.symmetric(vertical: 7),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(child: Text(label, style: TextStyle(color: AppTheme.textSecondary))),
        SizedBox(width: 12),
        Flexible(child: Text(value, textAlign: TextAlign.end,
          style: TextStyle(fontWeight: FontWeight.w600))),
      ],
    ),
  );

  Widget _detailGroup(String title, List<Widget> rows) {
    if (rows.isEmpty) return SizedBox.shrink();
    return Padding(
      padding: EdgeInsets.only(top: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.labelLarge?.copyWith(
            color: Theme.of(context).colorScheme.primary,
            fontWeight: FontWeight.w700,
          )),
          SizedBox(height: 4),
          ...rows,
        ],
      ),
    );
  }

  Future<void> _showSessionDetails(Map<String, dynamic> session) async {
    final site = session['site']?.toString() ?? tr('Unbekannter Standort');
    final currency = session['currency']?.toString() ?? 'EUR';
    final currencySymbol = currency == 'EUR' ? '€' : currency;
    final networkValue = session['network']?.toString() ?? 'supercharger';
    final network = networkValue == 'multipass' ? tr('MultiPass')
        : networkValue == 'supercharger' ? tr('Supercharger') : networkValue;
    final invoice = session['has_invoice'] == true;
    final sessionId = session['id']?.toString();
    final energyValue = session['kwh'] is num
        ? session['kwh'] as num
        : num.tryParse(session['kwh']?.toString() ?? '');
    final costValue = session['cost'] is num
        ? session['cost'] as num
        : num.tryParse(session['cost']?.toString() ?? '');
    final effectivePrice = energyValue != null && energyValue > 0 &&
            costValue != null
        ? costValue / energyValue
        : null;
    String? textValue(String key) {
      final value = session[key];
      if (value == null || value.toString().trim().isEmpty) return null;
      return value.toString();
    }
    final timingRows = <Widget>[
      if (textValue('start') != null)
        _detailRow(tr('Beginn'), _dateTimeLabel(session['start'])),
      if (textValue('end') != null)
        _detailRow(tr('Ende'), _dateTimeLabel(session['end'])),
      if (session['duration_min'] != null)
        _detailRow(tr('Ladedauer'), _durationLabel(session['duration_min'])),
    ];
    final costRows = <Widget>[
      if (session['kwh'] != null)
        _detailRow(tr('Geladene Energie'), _numberLabel(session['kwh'], suffix: tr(' kWh'))),
      if (session['cost'] != null)
        _detailRow(tr('Gesamtkosten'), _numberLabel(session['cost'], suffix: ' $currencySymbol')),
      if (session['charge_cost'] != null)
        _detailRow(tr('Ladekosten'), _numberLabel(session['charge_cost'], suffix: ' $currencySymbol')),
      if (session['idle'] != null)
        _detailRow(tr('Standgebühren'), _numberLabel(session['idle'], suffix: ' $currencySymbol')),
      if (session['credit'] != null)
        _detailRow(tr('Gutschrift'), _numberLabel(session['credit'], suffix: ' $currencySymbol')),
      if (session['price'] != null)
        _detailRow(tr('Preis pro kWh'), _numberLabel(session['price'], digits: 3, suffix: trf(' {0}/kWh', [currencySymbol]))),
      if (session['price'] == null && effectivePrice != null)
        _detailRow(tr('Effektivpreis (berechnet)'),
          _numberLabel(effectivePrice, digits: 3, suffix: trf(' {0}/kWh', [currencySymbol]))),
      if (session['avg_kw'] != null)
        _detailRow(tr('Durchschnittsleistung'), _numberLabel(session['avg_kw'], suffix: tr(' kW'))),
      if (session['start_soc'] != null)
        _detailRow(tr('Start-Ladestand'), _numberLabel(session['start_soc'], digits: 0, suffix: ' %')),
    ];
    final locationRows = <Widget>[
      if (textValue('operator') != null)
        _detailRow(tr('Betreiber'), textValue('operator')!),
      if (textValue('address') != null)
        _detailRow(tr('Adresse'), textValue('address')!),
    ];

    await showDialog<void>(
      context: context,
      builder: (dialogContext) => Dialog.fullscreen(
        child: Scaffold(
          appBar: AppBar(
            title: Text(tr('Ladevorgang')),
            leading: IconButton(
              icon: Icon(Icons.close),
              tooltip: tr('Schließen'),
              onPressed: () => Navigator.pop(dialogContext),
            ),
          ),
          body: ListView(
            padding: EdgeInsets.fromLTRB(20, 12, 20, 28),
            children: [
              Text(site,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w800)),
              if (textValue('address') != null) ...[
                SizedBox(height: 4),
                SelectableText(textValue('address')!,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppTheme.textSecondary)),
              ],
              SizedBox(height: 8),
              if (energyValue != null || costValue != null)
                Card(
                  margin: EdgeInsets.only(bottom: 8),
                  child: Padding(
                    padding: EdgeInsets.all(10),
                    child: Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        if (energyValue != null)
                          SizedBox(
                            width: 142,
                            child: _sessionMetric(
                              tr('Geladen'),
                              _numberLabel(energyValue, digits: 1, suffix: tr(' kWh')),
                              Icons.bolt_rounded,
                            ),
                          ),
                        if (costValue != null)
                          SizedBox(
                            width: 142,
                            child: _sessionMetric(
                              tr('Gesamtkosten'),
                              _numberLabel(costValue, suffix: ' $currencySymbol'),
                              Icons.euro_rounded,
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  Chip(
                    avatar: Icon(Icons.ev_station, size: 16),
                    label: Text(network),
                  ),
                  if (invoice)
                    Chip(
                      avatar: Icon(Icons.receipt_long, size: 16),
                      label: Text(tr('Rechnung vorhanden')),
                    ),
                ],
              ),
              _detailGroup(tr('ZEITRAUM'), timingRows),
              _detailGroup(tr('ENERGIE UND KOSTEN'), costRows),
              _detailGroup(tr('STANDORT'), locationRows),
              if (!invoice)
                Padding(
                  padding: EdgeInsets.only(top: 18),
                  child: Text(tr('Für diesen Ladevorgang ist keine Rechnung hinterlegt.'),
                    style: TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
                ),
            ],
          ),
          bottomNavigationBar: invoice && sessionId != null
              ? SafeArea(
                  minimum: EdgeInsets.fromLTRB(20, 8, 20, 16),
                  child: FilledButton.icon(
                    onPressed: () {
                      Navigator.pop(dialogContext);
                      _showInvoice(sessionId, site);
                    },
                    icon: Icon(Icons.receipt_long),
                    label: Text(tr('Rechnung öffnen')),
                  ),
                )
              : null,
        ),
      ),
    );
  }

  Widget _priceRadar(dynamic rawSlots, dynamic rawSites) {
    final slots = rawSlots is List
        ? rawSlots.whereType<Map<String, dynamic>>()
            .where((slot) => slot['sessions'] is num && (slot['sessions'] as num) > 0)
            .toList()
        : <Map<String, dynamic>>[];
    final sites = rawSites is List
        ? rawSites.whereType<Map<String, dynamic>>().take(8).toList()
        : <Map<String, dynamic>>[];
    num? lowestSlotPrice;
    for (final slot in slots) {
      final price = slot['avg_price'];
      if (price is num && (lowestSlotPrice == null || price < lowestSlotPrice)) {
        lowestSlotPrice = price;
      }
    }
    num? lowestSitePrice;
    for (final site in sites) {
      final price = site['avg_price'];
      if (price is num && (lowestSitePrice == null || price < lowestSitePrice)) {
        lowestSitePrice = price;
      }
    }
    if (slots.isEmpty && sites.isEmpty) return SizedBox.shrink();
    Map<String, dynamic>? cheapestSlot;
    Map<String, dynamic>? cheapestSite;
    for (final slot in slots) {
      if (slot['avg_price'] is num &&
          (cheapestSlot == null || (slot['avg_price'] as num) < (cheapestSlot['avg_price'] as num))) {
        cheapestSlot = slot;
      }
    }
    for (final site in sites) {
      if (site['avg_price'] is num &&
          (cheapestSite == null || (site['avg_price'] as num) < (cheapestSite['avg_price'] as num))) {
        cheapestSite = site;
      }
    }

    Widget priceValue(dynamic value, {bool highlighted = false}) =>
        Container(
          padding: EdgeInsets.symmetric(horizontal: 10, vertical: 7),
          decoration: BoxDecoration(
            color: (highlighted ? AppTheme.accentGreen : AppTheme.accentTeal)
                .withValues(alpha: 0.10),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: (highlighted ? AppTheme.accentGreen : AppTheme.border)
                  .withValues(alpha: highlighted ? 0.35 : 1),
            ),
          ),
          child: Text(
            value is num ? trf('{0} €/kWh', [formatNumber(value, 3)]) : '–',
            textAlign: TextAlign.end,
            style: TextStyle(
              color: highlighted ? AppTheme.accentGreen : AppTheme.textPrimary,
              fontSize: 12,
              fontWeight: FontWeight.w800,
            ),
          ),
        );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: EdgeInsets.fromLTRB(4, 0, 4, 10),
          child: Text(tr('Historische Durchschnittswerte aus deinen erfassten Ladevorgängen – keine Live-Tarife.'),
            style: TextStyle(color: AppTheme.textSecondary, fontSize: 11)),
        ),
        _sectionHeading(tr('Preisradar')),
        if (cheapestSlot != null || cheapestSite != null)
          Card(
            margin: EdgeInsets.only(bottom: 12),
            child: Container(
              width: double.infinity,
              padding: EdgeInsets.all(14),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(16),
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    AppTheme.accentGreen.withValues(alpha: 0.11),
                    AppTheme.surface,
                  ],
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.savings_outlined,
                        color: AppTheme.accentGreen, size: 18),
                      SizedBox(width: 8),
                      Expanded(child: Text(tr('Günstigstes Zeitfenster'),
                        style: TextStyle(fontWeight: FontWeight.w800))),
                      if (cheapestSlot?['avg_price'] is num)
                        Text(trf('{0} €/kWh', [formatNumber(cheapestSlot!['avg_price'] as num, 3)]),
                          style: TextStyle(color: AppTheme.accentGreen,
                            fontWeight: FontWeight.w800)),
                    ],
                  ),
                  if (cheapestSlot != null) ...[
                    SizedBox(height: 5),
                    Text(trf('Zeitfenster · {0}', [cheapestSlot['label'] ?? cheapestSlot['range'] ?? tr('Günstigste Ladezeit')]),
                      style: TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
                  ],
                  if (cheapestSite != null) ...[
                    SizedBox(height: 8),
                    Container(height: 1, color: AppTheme.border),
                    SizedBox(height: 8),
                    Row(
                      children: [
                        Icon(Icons.location_on_outlined,
                          color: AppTheme.accentTeal, size: 17),
                        SizedBox(width: 7),
                        Expanded(child: Text(
                          trf('Standort · {0}', [cheapestSite['label'] ?? cheapestSite['site'] ?? tr('Günstigster Standort')]),
                          maxLines: 2, overflow: TextOverflow.ellipsis,
                          style: TextStyle(fontSize: 12))),
                        if (cheapestSite['avg_price'] is num)
                          Text(trf('{0} €/kWh', [formatNumber(cheapestSite['avg_price'] as num, 3)]),
                            style: TextStyle(color: AppTheme.accentGreen,
                              fontWeight: FontWeight.w800, fontSize: 12)),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ),
        if (slots.isNotEmpty) ...[
          Padding(
            padding: EdgeInsets.fromLTRB(4, 4, 4, 6),
            child: Text(tr('Tarif nach Ladezeit'), style: TextStyle(color: AppTheme.textSecondary)),
          ),
          ...slots.map((slot) {
            final label = slot['label']?.toString() ?? tr('Zeitfenster');
            final range = slot['range']?.toString() ?? '';
            final count = slot['sessions'] is num ? (slot['sessions'] as num).round() : 0;
            final isCheapest = slot['avg_price'] is num &&
                lowestSlotPrice != null && slot['avg_price'] == lowestSlotPrice;
            return Card(
              child: Padding(
                padding: EdgeInsets.symmetric(horizontal: 14, vertical: 11),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(isCheapest ? Icons.savings_outlined : Icons.schedule,
                          color: isCheapest ? AppTheme.accentGreen : AppTheme.textSecondary,
                          size: 19),
                        SizedBox(width: 9),
                        Expanded(
                          child: Text('${label}${isCheapest ? tr(' · Günstigste Zeit') : ''}',
                            maxLines: 2, overflow: TextOverflow.ellipsis,
                            style: TextStyle(fontWeight: FontWeight.w600)),
                        ),
                        SizedBox(width: 8),
                        priceValue(slot['avg_price'], highlighted: isCheapest),
                      ],
                    ),
                    Padding(
                      padding: EdgeInsets.only(left: 28, top: 4),
                      child: Text(trf('{0} · {1} Ladevorgänge · €/kWh', [range.isEmpty ? tr('Zeitfenster') : range, count]),
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: AppTheme.textSecondary)),
                    ),
                  ],
                ),
              ),
            );
          }),
        ],
        if (sites.isNotEmpty) ...[
          Padding(
            padding: EdgeInsets.fromLTRB(4, 14, 4, 6),
            child: Text(tr('Deine häufigsten Ladestandorte'),
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                color: AppTheme.textSecondary, fontWeight: FontWeight.w700)),
          ),
          Card(
            child: ExpansionTile(
              key: PageStorageKey<String>('top-sites'),
              initiallyExpanded: false,
              leading: Icon(Icons.ev_station, color: AppTheme.accentTeal),
              title: Text(trf('{0} Ladestandorte', [sites.length]),
                style: TextStyle(fontWeight: FontWeight.w700)),
              subtitle: Text(
                cheapestSite == null
                    ? tr('Durchschnittspreise und Ladehäufigkeit')
                    : trf('Niedrigster erfasster Standortpreis: {0} €/kWh', [formatNumber(cheapestSite['avg_price'] as num, 3)]),
                maxLines: 1, overflow: TextOverflow.ellipsis,
              ),
              children: sites.map((site) {
                final label = site['label']?.toString() ??
                    site['site']?.toString() ?? tr('Unbekannter Standort');
                final network = site['network'] == 'multipass' ? tr('MultiPass') : tr('Supercharger');
                final count = site['sessions'] is num ? (site['sessions'] as num).round() : 0;
                final kwh = _numberLabel(site['kwh'], digits: 1, suffix: tr(' kWh'));
                final address = site['address']?.toString();
                final isCheapest = site['avg_price'] is num &&
                    lowestSitePrice != null && site['avg_price'] == lowestSitePrice;
                return Padding(
                  padding: EdgeInsets.fromLTRB(16, 9, 16, 10),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(isCheapest ? Icons.savings_outlined : Icons.location_on_outlined,
                            color: isCheapest ? AppTheme.accentGreen : AppTheme.textSecondary,
                            size: 19),
                          SizedBox(width: 9),
                          Expanded(
                            child: Text('${label}${isCheapest ? tr(' · Günstigster') : ''}',
                              maxLines: 2, overflow: TextOverflow.ellipsis,
                              style: TextStyle(fontWeight: FontWeight.w600)),
                          ),
                          SizedBox(width: 8),
                          priceValue(site['avg_price'], highlighted: isCheapest),
                        ],
                      ),
                      Padding(
                        padding: EdgeInsets.only(left: 28, top: 4),
                        child: Text(trf('{0} · {1} Ladevorgänge · {2}{3}', [network, count, kwh, address != null && address.isNotEmpty ? '\n$address' : '']),
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: AppTheme.textSecondary)),
                      ),
                    ],
                  ),
                );              }).toList(),
            ),
          ),
        ],
        Padding(
          padding: EdgeInsets.fromLTRB(4, 4, 4, 0),
          child: Text(tr('Preiswerte basieren auf den erfassten Rechnungsdaten und sind keine Live-Tarife.'),
            style: TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
        ),
      ],
    );
  }

  Future<void> _shareInvoiceZip(String month) async {
    try {
      final bytes = await _client.invoiceZip(month);
      final directory = await getTemporaryDirectory();
      final file = File('${directory.path}/ladecockpit-rechnungen-$month.zip');
      await file.writeAsBytes(bytes, flush: true);
      if (!mounted) return;
      await Share.shareXFiles(
        [XFile(file.path, mimeType: 'application/zip')],
        text: trf('Ladecockpit – Rechnungen {0}', [month]),
        subject: trf('Ladecockpit Rechnungen {0}', [month]),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error.toString())),
      );
    }
  }

  Future<void> _showMonthlyReport(String month, {bool year = false}) async {
    try {
      final metadata = year
          ? await _client.yearReportPages(month)
          : await _client.monthReportPages(month);
      final pages = metadata['pages'] as int;
      final headers = await _client._headers();
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (dialogContext) => Dialog.fullscreen(
          child: Scaffold(
            appBar: AppBar(
              title: Text(year ? trf('Jahresübersicht · {0}', [month]) : trf('Monatsbericht · {0}', [month])),
              leading: IconButton(
                icon: Icon(Icons.close),
                onPressed: () => Navigator.pop(dialogContext),
              ),
            ),
            body: Column(
              children: [
                Padding(
                  padding: EdgeInsets.fromLTRB(16, 12, 16, 4),
                  child: Container(
                    width: double.infinity,
                    padding: EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: AppTheme.surface,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppTheme.border),
                    ),
                    child: Row(
                      children: [
                        Container(
                          width: 40,
                          height: 40,
                          decoration: BoxDecoration(
                            color: AppTheme.accentTeal.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Icon(Icons.assessment_outlined,
                            color: AppTheme.accentTeal),
                        ),
                        SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(year ? tr('JAHRESÜBERSICHT') : tr('MONATSAUSWERTUNG'),
                                style: TextStyle(fontSize: 10, letterSpacing: 1.1,
                                  color: AppTheme.textSecondary, fontWeight: FontWeight.w700)),
                              SizedBox(height: 3),
                              Text(year ? tr('Deine Ladekosten im Jahr') : tr('Dein Ladebericht'),
                                style: TextStyle(fontWeight: FontWeight.w700)),
                            ],
                          ),
                        ),
                        SizedBox(width: 8),
                        Text('${pages} ${pages == 1 ? tr('Seite') : tr('Seiten')}',
                          style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                      ],
                    ),
                  ),
                ),
                Expanded(
                  child: ListView.builder(
                    padding: EdgeInsets.fromLTRB(8, 8, 8, 24),
                    itemCount: pages,
                    itemBuilder: (context, index) => Padding(
                      padding: EdgeInsets.only(bottom: 12),
                      child: FutureBuilder<Uri>(
                        future: year
                            ? _client.yearReportPageUri(month, index + 1)
                            : _client.monthReportPageUri(month, index + 1),
                        builder: (context, snapshot) {
                          if (snapshot.hasError) {
                            return Padding(
                              padding: EdgeInsets.all(24),
                              child: Text(tr('Seite konnte nicht geladen werden.')),
                            );
                          }
                          if (!snapshot.hasData) {
                            return SizedBox(
                              height: 240,
                              child: Center(child: CircularProgressIndicator()),
                            );
                          }
                          return Image.network(snapshot.data.toString(), headers: headers,
                            fit: BoxFit.contain,
                            loadingBuilder: (context, child, progress) => progress == null
                                ? child
                                : SizedBox(
                                    height: 240,
                                    child: Center(child: CircularProgressIndicator()),
                                  ),
                            errorBuilder: (_, __, ___) => Padding(
                              padding: EdgeInsets.all(24),
                              child: Text(tr('Seite konnte nicht geladen werden.')),
                            ));
                        },
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error.toString())),
      );
    }
  }

  Future<void> _showCsvExport() async {
    try {
      final csv = await _client.csvExport();
      if (!mounted) return;
      final rows = LineSplitter().convert(csv);
      final preview = rows.take(8).join('\n');
      await showDialog<void>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: Text(tr('CSV-Export')),
          content: SizedBox(
            width: double.maxFinite,
            child: SingleChildScrollView(
              child: SelectableText(
                trf('{0}{1} Zeilen insgesamt', [rows.length > 8 ? '$preview\n…\n' : '$preview\n', rows.length]),
                style: TextStyle(fontFamily: 'monospace', fontSize: 11),
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: Text(tr('Schließen')),
            ),
            FilledButton.icon(
              onPressed: () async {
                final directory = await getTemporaryDirectory();
                final file = File('${directory.path}/ladecockpit-sessions.csv');
                await file.writeAsString(csv, encoding: utf8, flush: true);
                if (!dialogContext.mounted) return;
                Navigator.pop(dialogContext);
                await Share.shareXFiles(
                  [XFile(file.path, mimeType: 'text/csv')],
                  text: tr('Ladecockpit – Ladevorgänge als CSV'),
                  subject: tr('Ladecockpit CSV-Export'),
                );
              },
              icon: Icon(Icons.copy),
              label: Text(tr('CSV teilen / speichern')),
            ),
          ],
        ),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error.toString())),
      );
    }
  }

  Widget _costLegend(Color color, String label) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(width: 9, height: 9, decoration: BoxDecoration(
        color: color, borderRadius: BorderRadius.circular(2))),
      SizedBox(width: 6),
      Text(label, style: TextStyle(color: AppTheme.textSecondary, fontSize: 11)),
    ],
  );

  Widget _costDevelopment(dynamic rawMonths) {
    final months = rawMonths is List
        ? rawMonths.whereType<Map<String, dynamic>>()
            .where((month) => month['key'] is String).toList()
        : <Map<String, dynamic>>[];
    if (months.isEmpty) return SizedBox.shrink();

    // Die API liefert Monate teilweise neueste zuerst; die Anzeige soll
    // unabhängig davon chronologisch von alt nach neu laufen.
    months.sort((a, b) => a['key'].toString().compareTo(b['key'].toString()));

    num amount(dynamic value) =>
        value is num ? value : num.tryParse(value?.toString() ?? '') ?? 0;
    num totalCost(Map<String, dynamic> month) =>
        amount(month['cost']) + amount(month['home_cost']);
    int? ordinal(String key) {
      final parts = key.split('-');
      if (parts.length != 2 || parts[0].length != 4 || parts[1].length != 2) return null;
      final year = int.tryParse(parts[0]);
      final month = int.tryParse(parts[1]);
      if (year == null || month == null || month < 1 || month > 12) return null;
      return year * 12 + month;
    }

    final values = months.map(totalCost).toList();
    final latestMonth = months.last;
    final latestKey = latestMonth['key'].toString();
    final latestParts = latestKey.split('-');
    final latestLabel = latestParts.length == 2
        ? '${latestParts[1]}.${latestParts[0]}' : latestKey;
    final averageCost = values.fold<num>(0, (sum, value) => sum + value) / values.length;

    Widget summaryMetric(String label, String value, String detail, IconData icon,
        {bool compact = false}) =>
        Expanded(
          child: Card(
            margin: EdgeInsets.zero,
            child: Padding(
              padding: EdgeInsets.all(compact ? 9 : 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(icon, size: compact ? 16 : 18, color: AppTheme.accentGreen),
                  SizedBox(height: compact ? 5 : 8),
                  Text(label, maxLines: 2, overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: AppTheme.textSecondary)),
                  SizedBox(height: 3),
                  FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerLeft,
                    child: Text(value, style: TextStyle(
                      fontSize: compact ? 16 : 18, fontWeight: FontWeight.w800)),
                  ),
                  Text(detail, maxLines: 1, overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: AppTheme.textSecondary)),
                ],
              ),
            ),
          ),
        );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeading(tr('Kostenentwicklung'),
          icon: Icons.trending_up_rounded, trailing: trf('{0} Monate', [months.length])),
        LayoutBuilder(
          builder: (context, constraints) {
            final compact = constraints.maxWidth < 370;
            return Row(
              children: [
                summaryMetric(tr('Letzter Monat'), '${formatNumber(values.last, 2)} €',
                  latestLabel, Icons.calendar_month_outlined, compact: compact),
                SizedBox(width: compact ? 7 : 10),
                summaryMetric(tr('Monatsdurchschnitt'), '${formatNumber(averageCost, 2)} €',
                  trf('über {0} Monate', [months.length]), Icons.show_chart, compact: compact),
              ],
            );
          },
        ),
        SizedBox(height: 8),
        Card(
          child: Padding(
            padding: EdgeInsets.all(16),
            child: Column(
              children: [
                ...List.generate(months.length, (index) {
                  final month = months[index];
                  final total = values[index];
                  final publicCost = amount(month['cost']);
                  final homeCostKnown = month['home_cost'] is num ||
                      num.tryParse(month['home_cost']?.toString() ?? '') != null;
                  final homeEnergyKnown = month['home_kwh'] is num ||
                      num.tryParse(month['home_kwh']?.toString() ?? '') != null;
                  final homeCost = amount(month['home_cost']);
                  final publicEnergy = amount(month['kwh']);
                  final homeEnergy = amount(month['home_kwh']);
                  final homeCostLabel = !homeEnergyKnown
                      ? tr('nicht erfasst')
                      : homeCostKnown ? '${formatNumber(homeCost, 2)} €'
                      : tr('Preis nicht hinterlegt');
                  final publicFlex = (publicCost * 1000).round().clamp(0, 100000000);
                  final homeFlex = (homeCost * 1000).round().clamp(0, 100000000);
                  final key = month['key'].toString();
                  final parts = key.split('-');
                  final label = parts.length == 2 ? '${parts[1]}.${parts[0]}' : key;
                  String? comparison;
                  Color? comparisonColor;
                  if (index > 0) {
                    final previous = months[index - 1];
                    final currentOrdinal = ordinal(key);
                    final previousOrdinal = ordinal(previous['key'].toString());
                    final previousHomeEnergyKnown = previous['home_kwh'] is num ||
                        num.tryParse(previous['home_kwh']?.toString() ?? '') != null;
                    final previousHomeCostKnown = previous['home_cost'] is num ||
                        num.tryParse(previous['home_cost']?.toString() ?? '') != null;
                    final sameHomeCostCoverage = homeEnergyKnown == previousHomeEnergyKnown &&
                        homeCostKnown == previousHomeCostKnown;
                    if (currentOrdinal != null && previousOrdinal != null &&
                        currentOrdinal - previousOrdinal == 1 && sameHomeCostCoverage) {
                      final previousTotal = totalCost(previous);
                      if (previousTotal > 0) {
                        final difference = total - previousTotal;
                        final percentage = difference / previousTotal * 100;
                        final sign = difference > 0 ? '+' : '';
                        comparison = trf('{0}{1} € ({2}{3} %) gegenüber Vormonat', [sign, formatNumber(difference, 2), sign, formatNumber(percentage, 1)]);
                        comparisonColor = difference > 0 ? AppTheme.warning :
                            difference < 0 ? AppTheme.accentGreen : AppTheme.textSecondary;
                      } else {
                        comparison = tr('Vormonat ohne erfasste Kosten – kein Prozentvergleich');
                        comparisonColor = AppTheme.textSecondary;
                      }
                    }
                  }
                  return Padding(
                    padding: EdgeInsets.symmetric(vertical: 7),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        LayoutBuilder(
                          builder: (context, constraints) {
                            final compact = constraints.maxWidth < 370;
                            Widget bar = ClipRRect(
                              borderRadius: BorderRadius.circular(6),
                              child: SizedBox(
                                height: 10,
                                child: Row(children: [
                                  if (publicFlex > 0)
                                    Expanded(flex: publicFlex, child: Container(
                                      color: Theme.of(context).colorScheme.primary)),
                                  if (homeFlex > 0)
                                    Expanded(flex: homeFlex, child: Container(
                                      color: Colors.lightBlueAccent)),
                                  if (publicFlex == 0 && homeFlex == 0)
                                    Expanded(child: Container(color: AppTheme.border)),
                                ]),
                              ),
                            );
                            if (compact) {
                              return Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    children: [
                                      Expanded(child: Text(label,
                                        style: TextStyle(color: AppTheme.textSecondary))),
                                      Text('${formatNumber(total, 2)} €',
                                        style: TextStyle(fontWeight: FontWeight.w700)),
                                    ],
                                  ),
                                  SizedBox(height: 7),
                                  bar,
                                ],
                              );
                            }
                            return Row(
                              children: [
                                SizedBox(width: 54, child: Text(label,
                                  style: TextStyle(color: AppTheme.textSecondary))),
                                Expanded(child: bar),
                                SizedBox(width: 12),
                                SizedBox(width: 76, child: Text('${formatNumber(total, 2)} €',
                                  textAlign: TextAlign.end,
                                  style: TextStyle(fontWeight: FontWeight.w600))),
                              ],
                            );
                          },
                        ),
                        Theme(
                          data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                          child: ExpansionTile(
                            key: PageStorageKey<String>('month-$key'),
                            tilePadding: EdgeInsets.only(left: 48, right: 4),
                            childrenPadding: EdgeInsets.only(left: 54, right: 4, bottom: 8),
                            dense: true,
                            visualDensity: VisualDensity.compact,
                            title: Text(
                              trf('{0} kWh · {1} öffentliche Ladevorgänge', [formatNumber(publicEnergy + (homeEnergyKnown ? homeEnergy : 0), 1), amount(month['sessions']).round()]),
                              style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                            children: [
                              Align(
                                alignment: Alignment.centerLeft,
                                child: Text(
                                  trf('Öffentlich: {0} € · Zuhause: {1}\nEnergie: öffentlich {2} kWh · zuhause {3}', [formatNumber(publicCost, 2), homeCostLabel, formatNumber(publicEnergy, 1), homeEnergyKnown ? trf('{0} kWh', [formatNumber(homeEnergy, 1)]) : tr('nicht erfasst')]),
                                  style: TextStyle(color: AppTheme.textSecondary, fontSize: 11)),
                              ),
                              if (comparison != null)
                                Align(
                                  alignment: Alignment.centerLeft,
                                  child: Padding(
                                    padding: EdgeInsets.only(top: 6),
                                    child: Text(comparison,
                                      style: TextStyle(color: comparisonColor, fontSize: 11)),
                                  ),
                                ),
                            ],
                          ),
                        ),
                        if (index != months.length - 1) SizedBox(height: 3),
                      ],
                    ),
                  );
                }),
                Divider(height: 20),
                Wrap(
                  spacing: 14,
                  runSpacing: 8,
                  children: [
                    _costLegend(Theme.of(context).colorScheme.primary, tr('Öffentlich')),
                    _costLegend(Colors.lightBlueAccent, tr('Zuhause · erfasste Kosten')),
                  ],
                ),
                SizedBox(height: 8),
                Align(alignment: Alignment.centerLeft,
                  child: Text(tr('Nicht erfasste Heimladekosten werden nicht als 0 € gewertet. Balken zeigen nur bekannte Kosten; Vergleiche berücksichtigen nur die erfassten Beträge.'),
                    style: TextStyle(color: AppTheme.textSecondary, fontSize: 11))),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _exports(dynamic rawMonths, dynamic rawYears) {
    final years = rawYears is List ? rawYears.whereType<int>().toList() : <int>[];
    num amount(dynamic value) =>
        value is num ? value : num.tryParse(value?.toString() ?? '') ?? 0;
    final months = rawMonths is List
        ? rawMonths.whereType<Map<String, dynamic>>()
            .where((month) => month['key'] is String).toList().reversed.toList()
        : <Map<String, dynamic>>[];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeading(tr('Berichte & Export')),
        Card(
          child: ListTile(
            contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 5),
            leading: Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                color: AppTheme.accentTeal.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(13),
              ),
              child: Icon(Icons.table_chart_outlined, color: AppTheme.accentTeal),
            ),
            title: Text(tr('Ladehistorie exportieren'),
              style: TextStyle(fontWeight: FontWeight.w700)),
            subtitle: Text(tr('Alle Ladevorgänge als CSV für Excel')),
            trailing: Icon(Icons.chevron_right, color: AppTheme.textSecondary),
            onTap: _showCsvExport,
          ),
        ),
        for (final year in years)
          Card(
            child: ListTile(
              contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 5),
              leading: Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: AppTheme.accentGreen.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(13),
                ),
                child: Icon(Icons.calendar_month_outlined, color: AppTheme.accentGreen),
              ),
              title: Text(trf('Jahresübersicht {0}', [year]),
                style: TextStyle(fontWeight: FontWeight.w700)),
              subtitle: Text(tr('Eine Zeile je Monat, z. B. für Steuer oder Arbeitgeber')),
              trailing: Icon(Icons.chevron_right, color: AppTheme.textSecondary),
              onTap: () => _showMonthlyReport('$year', year: true),
            ),
          ),
        if (months.isNotEmpty)
          Padding(
            padding: EdgeInsets.fromLTRB(4, 14, 4, 6),
            child: Text(tr('MONATSBERICHTE'),
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                color: AppTheme.textSecondary, letterSpacing: 1.1, fontWeight: FontWeight.w700)),
          ),
        ...months.map((month) {
          final key = month['key'].toString();
          final parts = key.split('-');
          final label = parts.length == 2 ? '${parts[1]}.${parts[0]}' : key;
          final count = month['sessions'] is num ? (month['sessions'] as num).round() : 0;
          final energy = _numberLabel(month['kwh'], digits: 1, suffix: tr(' kWh'));
          final monthTotal = formatNumber(
              amount(month['cost']) + amount(month['home_cost']), 2);
          return Card(
            child: Padding(
              padding: EdgeInsets.fromLTRB(14, 12, 8, 12),
              child: Row(
                children: [
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      color: AppTheme.accentGreen.withValues(alpha: 0.10),
                      borderRadius: BorderRadius.circular(13),
                    ),
                    child: Icon(Icons.calendar_month_outlined,
                      color: AppTheme.accentGreen),
                  ),
                  SizedBox(width: 12),
                  Expanded(
                    child: InkWell(
                      borderRadius: BorderRadius.circular(10),
                      onTap: () => _showMonthlyReport(key),
                      child: Padding(
                        padding: EdgeInsets.symmetric(vertical: 4),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(label, style: TextStyle(fontWeight: FontWeight.w700)),
                            SizedBox(height: 3),
                            Text(trf('{0} Ladevorgänge · {1}', [count, energy]),
                              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                            SizedBox(height: 3),
                            Text(trf('{0} € erfasste Kosten', [monthTotal]),
                              style: TextStyle(fontSize: 12,
                                color: AppTheme.accentGreen, fontWeight: FontWeight.w700)),
                          ],
                        ),
                      ),
                    ),
                  ),
                  IconButton(
                    tooltip: tr('Rechnungen als ZIP teilen'),
                    onPressed: () => _shareInvoiceZip(key),
                    icon: Icon(Icons.folder_zip_outlined),
                  ),
                  IconButton(
                    tooltip: tr('Monatsbericht ansehen'),
                    onPressed: () => _showMonthlyReport(key),
                    icon: Icon(Icons.picture_as_pdf_outlined,
                      color: AppTheme.accentTeal),
                  ),
                ],
              ),
            ),
          );
        }),
        if (months.isEmpty)
          Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: Text(tr('Sobald Monatsdaten vorhanden sind, erscheinen deine Berichte hier.'),
              style: TextStyle(color: AppTheme.textSecondary)),
          )
        else
          Padding(
            padding: EdgeInsets.fromLTRB(4, 4, 4, 0),
            child: Text(tr('Monatsbericht öffnen oder die zugehörigen Rechnungen gesammelt teilen.'),
              style: TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
          ),
      ],
    );
  }

  Future<void> _showInvoice(String sessionId, String site) async {
    try {
      final metadata = await _client.invoicePages(sessionId);
      final pages = metadata['pages'] as int;
      final headers = await _client._headers();
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (dialogContext) => Dialog.fullscreen(
          child: Scaffold(
            appBar: AppBar(
              title: Text(trf('Rechnung · {0}', [site]), maxLines: 1, overflow: TextOverflow.ellipsis),
              leading: IconButton(
                icon: Icon(Icons.close),
                onPressed: () => Navigator.pop(dialogContext),
              ),
            ),
            body: Column(
              children: [
                Padding(
                  padding: EdgeInsets.fromLTRB(16, 12, 16, 4),
                  child: Container(
                    width: double.infinity,
                    padding: EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: AppTheme.surface,
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: AppTheme.border),
                    ),
                    child: Row(
                      children: [
                        Container(
                          width: 40,
                          height: 40,
                          decoration: BoxDecoration(
                            color: AppTheme.accentGreen.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Icon(Icons.receipt_long_outlined,
                            color: AppTheme.accentGreen),
                        ),
                        SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(tr('LADERECHNUNG'),
                                style: TextStyle(fontSize: 10, letterSpacing: 1.1,
                                  color: AppTheme.textSecondary, fontWeight: FontWeight.w700)),
                              SizedBox(height: 3),
                              Text(site, maxLines: 1, overflow: TextOverflow.ellipsis,
                                style: TextStyle(fontWeight: FontWeight.w700)),
                            ],
                          ),
                        ),
                        SizedBox(width: 8),
                        Text('${pages} ${pages == 1 ? tr('Seite') : tr('Seiten')}',
                          style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                      ],
                    ),
                  ),
                ),
                Expanded(
                  child: ListView.builder(
                    padding: EdgeInsets.fromLTRB(8, 8, 8, 24),
                    itemCount: pages,
                    itemBuilder: (context, index) => Padding(
                      padding: EdgeInsets.only(bottom: 12),
                      child: FutureBuilder<Uri>(
                        future: _client.invoicePageUri(sessionId, index + 1),
                        builder: (context, uriSnapshot) {
                          if (uriSnapshot.hasError) {
                            return Padding(
                              padding: EdgeInsets.all(24),
                              child: Text(tr('Seite konnte nicht geladen werden.')),
                            );
                          }
                          if (!uriSnapshot.hasData) {
                            return SizedBox(
                              height: 240,
                              child: Center(child: CircularProgressIndicator()),
                            );
                          }
                          return Image.network(
                            uriSnapshot.data.toString(),
                            headers: headers,
                            fit: BoxFit.contain,
                            loadingBuilder: (context, child, progress) => progress == null
                                ? child
                                : SizedBox(
                                    height: 240,
                                    child: Center(child: CircularProgressIndicator()),
                                  ),
                            errorBuilder: (context, error, stack) => Padding(
                              padding: EdgeInsets.all(24),
                              child: Text(tr('PDF-Seite konnte nicht geladen werden.')),
                            ),
                          );
                        },
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error.toString())),
      );
    }
  }

  Widget _statusLine(IconData icon, String label, String value, {Color? color}) {
    return Padding(
      padding: EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          Icon(icon, size: 18, color: color ?? AppTheme.textSecondary),
          SizedBox(width: 10),
          Expanded(child: Text(label, style: TextStyle(color: AppTheme.textSecondary))),
          Flexible(child: Text(value, textAlign: TextAlign.end,
            style: TextStyle(fontWeight: FontWeight.w600, color: color))),
        ],
      ),
    );
  }

  Widget _vehicleHero(Map<String, dynamic>? status, Map<String, dynamic>? car) {
    final data = status ?? {};
    final compactCard = MediaQuery.sizeOf(context).width < 390;
    final vehicleName = car?['name']?.toString().trim();
    final vehicleImage = car?['url']?.toString().trim();
    final vehicleLabels = _map(car?['labels']) ?? {};
    final vehicleDetails = [
      vehicleLabels['generation'], vehicleLabels['trim'],
      vehicleLabels['paint'], vehicleLabels['wheel'],
    ].whereType<String>().map((value) => value.trim())
      .where((value) => value.isNotEmpty).toList();
    final soc = data['soc'] is num ? (data['soc'] as num).toDouble() : null;
    final range = data['range'] is num ? (data['range'] as num).round() : null;
    final charging = data['charging'];
    final power = data['power'] is num ? (data['power'] as num).toDouble() : null;
    final rate = data['rate'] is num ? (data['rate'] as num).toDouble() : null;
    final finish = data['finish'];
    final target = data['target'] is num ? (data['target'] as num).round() : null;
    final socSource = data['soc_source']?.toString();
    final asOf = data['as_of']?.toString();
    final level = soc == null ? 0.0 : (soc / 100).clamp(0.0, 1.0).toDouble();
    final readingLabel = socSource == 'last'
        ? tr('LETZTER BEKANNTER STAND')
        : socSource == 'live' ? tr('LIVE-FAHRZEUGDATEN') : tr('AKKUSTAND');
    final readingColor = socSource == 'last'
        ? AppTheme.warning
        : socSource == 'live' ? AppTheme.accentGreen : AppTheme.textSecondary;
    final chargingText = charging == true ? tr('Wird geladen')
        : charging == false ? tr('Lädt derzeit nicht') : tr('Ladestatus nicht verfügbar');
    final chargingColor = charging == true
        ? AppTheme.accentGreen
        : charging == false ? AppTheme.textSecondary : AppTheme.warning;

    return Card(
      clipBehavior: Clip.antiAlias,
      margin: EdgeInsets.only(top: 4, bottom: 18),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(28),
        side: BorderSide(color: AppTheme.border),
      ),
      child: Container(
        width: double.infinity,
        padding: EdgeInsets.fromLTRB(compactCard ? 15 : 20, compactCard ? 15 : 19,
          compactCard ? 15 : 20, compactCard ? 14 : 18),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF172B30), Color(0xFF101820), Color(0xFF0D1218)],
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 38,
                  height: 38,
                  decoration: BoxDecoration(
                    color: AppTheme.accentTeal.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(13),
                    border: Border.all(color: AppTheme.accentTeal.withValues(alpha: 0.22)),
                  ),
                  child: Icon(Icons.electric_car_outlined,
                    color: AppTheme.accentTeal, size: 21),
                ),
                SizedBox(width: 11),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(tr('FAHRZEUGSTATUS'),
                        style: TextStyle(fontSize: 11, letterSpacing: 1.5,
                          color: AppTheme.textSecondary, fontWeight: FontWeight.w700)),
                      SizedBox(height: 3),
                      Text(vehicleName == null || vehicleName.isEmpty
                          ? tr('Dein Ladecockpit') : vehicleName,
                        maxLines: 1, overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                    ],
                  ),
                ),
                if (charging == true)
                  Container(
                    padding: EdgeInsets.symmetric(horizontal: 10, vertical: 7),
                    decoration: BoxDecoration(
                      color: AppTheme.accentGreen.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: AppTheme.accentGreen.withValues(alpha: 0.25)),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.bolt, color: AppTheme.accentGreen, size: 15),
                        SizedBox(width: 4),
                        Text(tr('LÄDT'), style: TextStyle(fontSize: 10,
                          letterSpacing: 0.8, color: AppTheme.accentGreen,
                          fontWeight: FontWeight.w800)),
                      ],
                    ),
                  ),
              ],
            ),
            if (vehicleImage != null && vehicleImage.isNotEmpty) ...[
              SizedBox(height: 12),
              Container(
                height: compactCard ? 82 : 108,
                width: double.infinity,
                padding: EdgeInsets.symmetric(horizontal: 12, vertical: 5),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.025),
                  borderRadius: BorderRadius.circular(18),
                  border: Border.all(color: Colors.white.withValues(alpha: 0.045)),
                ),
                child: Image.network(
                  vehicleImage,
                  fit: BoxFit.contain,
                  alignment: Alignment.center,
                  errorBuilder: (context, error, stackTrace) => Center(
                    child: Icon(Icons.directions_car_filled_rounded,
                      size: 42, color: AppTheme.textSecondary),
                  ),
                ),
              ),
            ],
            if (vehicleDetails.isNotEmpty) ...[
              SizedBox(height: 8),
              Text(vehicleDetails.join('  ·  '),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(color: AppTheme.textSecondary, fontSize: 11)),
            ],
            SizedBox(height: compactCard ? 15 : 22),
            LayoutBuilder(
              builder: (context, constraints) {
                final compact = constraints.maxWidth < 360;
                final gaugeSize = compact ? 108.0 : 132.0;
                final gaugeGap = compact ? 14.0 : 22.0;
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    SizedBox(
                      width: gaugeSize,
                      height: gaugeSize,
                      child: Stack(
                        alignment: Alignment.center,
                        children: [
                          SizedBox.expand(
                            child: CircularProgressIndicator(
                              value: level,
                              strokeWidth: compact ? 8 : 10,
                              strokeCap: StrokeCap.round,
                              backgroundColor: Colors.white.withValues(alpha: 0.07),
                              valueColor: AlwaysStoppedAnimation<Color>(
                                soc == null ? AppTheme.border : AppTheme.accentGreen,
                              ),
                            ),
                          ),
                          Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(soc == null ? '–' : '${soc.round()}%',
                                style: TextStyle(fontSize: compact ? 29 : 34,
                                  height: 1.0, fontWeight: FontWeight.w800,
                                  letterSpacing: -1.2)),
                              SizedBox(height: 5),
                              Text(tr('BATTERIE'),
                                style: TextStyle(fontSize: 9, letterSpacing: 1.2,
                                  color: AppTheme.textSecondary, fontWeight: FontWeight.w700)),
                            ],
                          ),
                        ],
                      ),
                    ),
                    SizedBox(width: gaugeGap),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(tr('REICHWEITE'),
                            style: TextStyle(fontSize: 10, letterSpacing: 1.3,
                              color: AppTheme.textSecondary, fontWeight: FontWeight.w700)),
                          SizedBox(height: 5),
                          Text(range == null ? '–' : trf('{0} km', [range]),
                            maxLines: 1, softWrap: false,
                            style: TextStyle(fontSize: compact ? 25 : 30,
                              fontWeight: FontWeight.w800, letterSpacing: -1.0)),
                          if (target != null) ...[
                            SizedBox(height: 8),
                            Text(trf('Ladelimit {0} %', [target]),
                              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                          ],
                        ],
                      ),
                    ),
                  ],
                );
              },
            ),
            SizedBox(height: compactCard ? 14 : 20),
            Container(height: 1, color: AppTheme.border),
            SizedBox(height: compactCard ? 10 : 13),
            Row(
              children: [
                Icon(
                  charging == true ? Icons.ev_station_rounded : Icons.power_rounded,
                  color: chargingColor, size: 19),
                SizedBox(width: 9),
                Expanded(
                  child: Text(chargingText,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(color: chargingColor,
                      fontWeight: FontWeight.w700, fontSize: 13)),
                ),
                if (power != null) ...[
                  SizedBox(width: 8),
                  Container(
                    padding: EdgeInsets.symmetric(horizontal: 9, vertical: 6),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.06),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text(trf('{0} kW', [formatNumber(power, 1)]),
                      maxLines: 1,
                      style: TextStyle(fontWeight: FontWeight.w800, fontSize: 12)),
                  ),
                ],
              ],
            ),
            if (soc != null) ...[
              SizedBox(height: 11),
              Row(
                children: [
                  Icon(socSource == 'last' ? Icons.history_rounded : Icons.sensors_rounded,
                    size: 14, color: readingColor),
                  SizedBox(width: 6),
                  Expanded(child: Text(readingLabel,
                    style: TextStyle(fontSize: 10, letterSpacing: 0.8,
                      color: readingColor, fontWeight: FontWeight.w700))),
                  if (asOf != null)
                    Flexible(
                      child: Text(trf('Stand · {0}', [_dateTimeLabel(asOf)]),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        textAlign: TextAlign.end,
                        style: TextStyle(fontSize: 10,
                          color: AppTheme.textSecondary)),
                    ),
                ],
              ),
            ],
            if (charging == true && (rate != null || finish is String)) ...[
              SizedBox(height: 12),
              Container(
                width: double.infinity,
                padding: EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                decoration: BoxDecoration(
                  color: AppTheme.accentGreen.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: AppTheme.accentGreen.withValues(alpha: 0.18)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.timelapse_rounded,
                      color: AppTheme.accentGreen, size: 19),
                    SizedBox(width: 9),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (finish is String)
                            Text(trf('Voraussichtlich fertig · {0}', [_dateTimeLabel(finish)]),
                              style: TextStyle(fontSize: 12,
                                fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
                          if (rate != null) ...[
                            if (finish is String) SizedBox(height: 3),
                            Text(trf('Ladegeschwindigkeit · {0} % pro Stunde', [formatNumber(rate, 1)]),
                              style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _connectionStatus() {
    final setup = _map(_data?['setup']) ?? {};
    final sync = _map(_data?['sync']) ?? {};
    final teslaConfigured = setup['tesla_configured'] == true;
    final teslaConnected = setup['tesla_connected'] == true;
    final teslaError = setup['tesla_auth_error']?.toString();
    final haConfigured = setup['ha_configured'] == true;
    final haOk = setup['ha_ok'] == true;
    final haError = setup['ha_error']?.toString();
    final syncError = sync['error']?.toString();
    final problem = sync['problem']?.toString();
    final vehicleStatus = _map(_data?['status']) ?? {};
    final socSource = vehicleStatus['soc_source']?.toString();
    final hasVehicleReading = vehicleStatus['soc'] is num;
    final vehicleDataLabel = !hasVehicleReading
        ? tr('Keine Fahrzeugdaten')
        : socSource == 'live' ? tr('Fahrzeugdaten live') : tr('Letzter Stand');
    final vehicleDataColor = !hasVehicleReading
        ? AppTheme.textSecondary
        : socSource == 'live' ? AppTheme.accentGreen : AppTheme.warning;
    final hasTeslaError = teslaError != null && teslaError.isNotEmpty;
    final hasSyncError = syncError != null && syncError.isNotEmpty;

    final teslaLabel = !teslaConfigured
        ? tr('Einrichtung fehlt')
        : teslaConnected ? tr('Verbunden') : tr('Nicht verbunden');
    final teslaColor = teslaConnected ? AppTheme.accentGreen : AppTheme.warning;
    final teslaHint = !teslaConfigured
        ? tr('Tesla-Zugang muss zuerst auf dem Ladecockpit-Server eingerichtet werden.')
        : !teslaConnected && !hasTeslaError
            ? tr('Der Tesla-Zugang ist eingerichtet, aktuell besteht aber keine Verbindung.')
            : null;
    final haLabel = !haConfigured
        ? tr('Nicht eingerichtet · optional')
        : haOk ? tr('Verbunden') : tr('Nicht erreichbar');
    final haHint = haConfigured && !haOk && (haError == null || haError.isEmpty)
        ? tr('Home Assistant ist eingerichtet, antwortet aktuell aber nicht.')
        : null;
    final haColor = !haConfigured || haOk ? AppTheme.accentGreen : AppTheme.warning;
    final hasProblem = !teslaConnected || (haConfigured && !haOk) ||
        hasTeslaError || hasSyncError;
    final summaryColor = hasProblem ? AppTheme.warning : AppTheme.accentGreen;
    final summaryLabel = hasProblem ? tr('Verbindung prüfen') : tr('Alles verbunden');

    return Card(
      margin: EdgeInsets.only(bottom: 14),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          key: PageStorageKey<String>('connections'),
          initiallyExpanded: false,
          tilePadding: EdgeInsets.symmetric(horizontal: 16, vertical: 2),
          childrenPadding: EdgeInsets.fromLTRB(16, 0, 16, 14),
          leading: Icon(
            hasProblem ? Icons.cloud_off_outlined : Icons.cloud_done_outlined,
            color: summaryColor,
          ),
          title: Text(tr('Verbindungen'),
            style: TextStyle(fontWeight: FontWeight.w700)),
          subtitle: Row(
            children: [
              Container(width: 7, height: 7, decoration: BoxDecoration(
                color: summaryColor, shape: BoxShape.circle)),
              SizedBox(width: 7),
              Expanded(child: Text(summaryLabel,
                style: TextStyle(color: summaryColor, fontSize: 12))),
              Container(
                padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: vehicleDataColor.withValues(alpha: 0.10),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(vehicleDataLabel,
                  style: TextStyle(color: vehicleDataColor, fontSize: 10,
                    fontWeight: FontWeight.w700)),
              ),
            ],
          ),
          children: [
            Row(
              children: [
                Expanded(child: _statusLine(
                  teslaConnected ? Icons.check_circle : Icons.cloud_off,
                  tr('Tesla'), teslaLabel, color: teslaColor)),
                IconButton(
                  tooltip: tr('Status aktualisieren'),
                  visualDensity: VisualDensity.compact,
                  onPressed: _loading ? null : _load,
                  icon: Icon(Icons.refresh, size: 19),
                ),
              ],
            ),
            // Fahrzeugdaten-Frische steht bereits kompakt in der Zusammenfassung
            // und im Fahrzeug-Header; hier bleiben nur Verbindungsdetails.
            if (teslaHint != null)
              Padding(
                padding: EdgeInsets.only(left: 28, bottom: 5),
                child: Text(teslaHint,
                  style: TextStyle(color: AppTheme.textSecondary, fontSize: 11, height: 1.35)),
              ),
            if (hasTeslaError)
              Padding(
                padding: EdgeInsets.only(left: 28, bottom: 5),
                child: Text(trf('Tesla-Fehler: {0}', [teslaError]),
                  style: TextStyle(color: AppTheme.warning, fontSize: 12, height: 1.35)),
              ),
            _statusLine(
              !haConfigured || haOk ? Icons.home_outlined : Icons.warning_amber_rounded,
              tr('Home Assistant'), haLabel, color: haColor),
            if (haHint != null)
              Padding(
                padding: EdgeInsets.only(left: 28, bottom: 5),
                child: Text(haHint,
                  style: TextStyle(color: AppTheme.textSecondary, fontSize: 11, height: 1.35)),
              ),
            if (haConfigured && !haOk && haError != null && haError.isNotEmpty)
              Padding(
                padding: EdgeInsets.only(left: 28, bottom: 5),
                child: Text(trf('Home-Assistant-Fehler: {0}', [haError]),
                  style: TextStyle(color: AppTheme.warning, fontSize: 12, height: 1.35)),
              ),
            Divider(height: 18),
            _statusLine(Icons.history, tr('Letzte Synchronisation'), _dateTimeLabel(sync['last'])),
            _statusLine(Icons.download_done,
              tr('Letzter erfolgreicher App-Abruf'), _fetchTimeLabel(_lastSuccessfulFetch)),
            if (sync['next'] != null)
              _statusLine(Icons.schedule, tr('Nächste Synchronisation'), _dateTimeLabel(sync['next'])),
            if (hasSyncError)
              Padding(
                padding: EdgeInsets.only(top: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(Icons.error_outline, color: AppTheme.warning, size: 18),
                    SizedBox(width: 8),
                    Expanded(child: Text(syncError,
                      style: TextStyle(color: AppTheme.warning, fontSize: 12))),
                  ],
                ),
              ),
            if (!hasSyncError && problem != null && problem.isNotEmpty && problem != 'None')
              Padding(
                padding: EdgeInsets.only(top: 6),
                child: Text(trf('Hinweis: {0}', [problem]),
                  style: TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
              ),
          ],
        ),
      ),
    );
  }

  Widget _sectionHeading(String title, {IconData? icon, String? trailing}) {
    return Padding(
      padding: EdgeInsets.fromLTRB(4, 22, 4, 8),
      child: Row(
        children: [
          if (icon != null) ...[
            Icon(icon, color: AppTheme.accentGreen, size: 19),
            SizedBox(width: 8),
          ],
          Expanded(
            child: Text(title,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold)),
          ),
          if (trailing != null)
            Text(trailing,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                color: AppTheme.textSecondary)),
        ],
      ),
    );
  }

  Widget _tabIntro(String eyebrow, String title, String description, IconData icon) {
    return Padding(
      padding: EdgeInsets.fromLTRB(2, 10, 2, 16),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: AppTheme.accentGreen.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(13),
            ),
            child: Icon(icon, color: AppTheme.accentGreen, size: 21),
          ),
          SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(eyebrow.toUpperCase(),
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: AppTheme.accentGreen,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 1.2,
                  )),
                SizedBox(height: 3),
                Text(title, style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.w800,
                )),
                SizedBox(height: 3),
                Text(description, style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: AppTheme.textSecondary,
                  height: 1.35,
                )),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _loadStatePanel({
    required IconData icon,
    required String title,
    required String message,
    required Color color,
    Widget? action,
  }) {
    return Card(
      margin: EdgeInsets.only(top: 12, bottom: 14),
      child: Padding(
        padding: EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(13),
              ),
              child: Icon(icon, color: color, size: 22),
            ),
            SizedBox(height: 13),
            Text(title, style: TextStyle(
              fontSize: 16, fontWeight: FontWeight.w700)),
            SizedBox(height: 5),
            Text(message, style: TextStyle(
              color: AppTheme.textSecondary, height: 1.4)),
            if (action != null) ...[
              SizedBox(height: 14),
              action,
            ],
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final month = _map(_data?['month']);
    final last = _map(_data?['last_charge']);
    final totals = _map(_data?['totals']);
    final forecast = _map(_data?['forecast']);
    final car = _map(_data?['car']);
    final carLabels = _map(car?['labels']);
    final vehicleInfo = <String, dynamic>{
      'model': car?['name'],
      'generation': carLabels?['generation'],
      'trim': carLabels?['trim'],
      'paint': carLabels?['paint'],
      'wheels': carLabels?['wheel'],
    };
    String? money(dynamic value) => value is num ? '${formatNumber(value, 2)} €' : null;
    String? count(dynamic value, String unit) =>
        value is num ? '${formatNumber(value, 0)} $unit' : null;
    final overviewMetrics = <Widget>[
      if (month?['sessions'] != null || month?['count'] != null)
        _metric(tr('Ladevorgänge diesen Monat'),
          month?['sessions'] ?? month?['count']),
      if (month?['total_cost'] != null || month?['cost'] != null)
        _metric(tr('Gesamtkosten diesen Monat'),
          month?['total_cost'] ?? month?['cost'], suffix: ' €', digits: 2),
      if (month?['kwh'] != null)
        _metric(tr('Unterwegs geladen'), month?['kwh'], suffix: tr(' kWh')),
      if (month?['avg_price'] != null)
        _metric(tr('Ø Preis unterwegs'), month?['avg_price'], suffix: tr(' €/kWh'), digits: 2),
    ];
    const tabTitles = ['Cockpit', 'Ladevorgänge', 'Auswertungen'];

    return Scaffold(
      appBar: AppBar(
        title: Text(tr(tabTitles[_selectedTab]),
          style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(
            onPressed: _loading ? null : _load,
            tooltip: _loading ? tr('Wird aktualisiert') : tr('Aktualisieren'),
            icon: _loading
                ? SizedBox(
                    width: 19,
                    height: 19,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Icon(Icons.refresh),
          ),
          IconButton(onPressed: _settings, tooltip: tr('Verbindung'),
            icon: Icon(Icons.settings_outlined)),
        ],
      ),
      body: ColoredBox(
        color: AppTheme.background,
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView(
          key: PageStorageKey('ladecockpit-tab-$_selectedTab'),
          physics: AlwaysScrollableScrollPhysics(),
          padding: EdgeInsets.fromLTRB(16, 8, 16, 32),
          children: [
            if (_data != null)
              Padding(
                padding: EdgeInsets.fromLTRB(4, 0, 4, 10),
                child: Row(
                  children: [
                    if (_loading) ...[
                      SizedBox(
                        width: 13,
                        height: 13,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                      SizedBox(width: 8),
                      Text(tr('Daten werden aktualisiert'),
                        style: TextStyle(color: AppTheme.accentTeal, fontSize: 11,
                          fontWeight: FontWeight.w600)),
                    ] else ...[
                      Icon(_fromCache ? Icons.history_rounded : Icons.check_circle_outline,
                        color: _fromCache ? AppTheme.warning : AppTheme.accentGreen, size: 14),
                      SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          _lastSuccessfulFetch == null
                              ? tr('Daten geladen')
                              : _fromCache
                                  ? trf('Letzter Stand · {0}', [_fetchTimeLabel(_lastSuccessfulFetch)])
                                  : trf('Aktualisiert · {0}', [_fetchTimeLabel(_lastSuccessfulFetch)]),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(color: AppTheme.textSecondary, fontSize: 11),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            if (_error != null)
              _loadStatePanel(
                icon: Icons.cloud_off_rounded,
                title: _data == null ? tr('Verbindung nicht möglich')
                    : _fromCache ? tr('Keine Verbindung zum Server') : tr('Aktualisierung fehlgeschlagen'),
                message: _data == null
                    ? _error!
                    : _fromCache
                        ? trf('Du siehst den letzten Stand, den dein Handy gespeichert hat. {0}', [_error])
                        : trf('Die zuletzt geladenen Daten bleiben sichtbar. {0}', [_error]),
                color: AppTheme.warning,
                action: Wrap(spacing: 8, runSpacing: 8, children: [
                  FilledButton.icon(
                    onPressed: _loading ? null : _load,
                    icon: Icon(Icons.refresh),
                    label: Text(tr('Erneut versuchen')),
                  ),
                  if (_data == null)
                    OutlinedButton.icon(
                      onPressed: _settings,
                      icon: Icon(Icons.settings_outlined),
                      label: Text(tr('Verbindung einrichten')),
                    ),
                ]),
              ),
            if (_data == null && _loading && _error == null)
              _loadStatePanel(
                icon: Icons.electric_car_rounded,
                title: tr('Lade dein Cockpit'),
                message: tr('Fahrzeug- und Ladedaten werden sicher vom Server abgerufen.'),
                color: AppTheme.accentGreen,
                action: LinearProgressIndicator(minHeight: 3),
              ),
            if (_data != null && _selectedTab == 0) ...[
              _vehicleHero(_map(_data?['status']), _map(_data?['car'])),
              _connectionStatus(),
              Padding(
                padding: EdgeInsets.fromLTRB(4, 2, 4, 9),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(tr('MONATSÜBERBLICK'),
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: AppTheme.accentGreen,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 1.2)),
                    SizedBox(height: 3),
                    Text(tr('Ladeaktivität und Kosten auf einen Blick'),
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: AppTheme.textSecondary)),
                  ],
                ),
              ),
              if (overviewMetrics.isNotEmpty)
                GridView.count(
                  crossAxisCount: 2,
                  shrinkWrap: true,
                  physics: NeverScrollableScrollPhysics(),
                  crossAxisSpacing: 9,
                  mainAxisSpacing: 9,
                  childAspectRatio: 1.85,
                  children: overviewMetrics,
                )
              else
                Card(
                  child: Padding(
                    padding: EdgeInsets.all(14),
                    child: Text(tr('Für diesen Monat liegen noch keine Kennzahlen vor.'),
                      style: TextStyle(color: AppTheme.textSecondary)),
                  ),
                ),
              _homeChargingSummary(_map(month?['home'])),
              _section('Letzter Ladevorgang', last,
                keys: ['site', 'network', 'operator', 'start', 'end', 'duration_min',
                  'kwh', 'price', 'cost', 'idle', 'credit', 'avg_kw'],
                summary: _summaryLine([
                  last?['site'], _shortDateLabel(last?['start']), money(last?['cost']),
                ])),
              _section('Gesamt', totals,
                keys: ['sessions', 'kwh', 'cost', 'charge_cost', 'idle', 'credit',
                  'avg_price', 'since'],
                summary: _summaryLine([
                  count(totals?['sessions'], tr('Ladevorgänge')),
                  totals?['kwh'] is num ? trf('{0} kWh', [formatNumber(totals?['kwh'] as num, 1)]) : null,
                  money(totals?['cost']),
                ])),
              _section('Ladeprognose', forecast,
                keys: ['text', 'days_to_floor', 'rate_pct_day', 'dist_day'],
                summary: _summaryLine([forecast?['text']])),
              _section('Fahrzeug', vehicleInfo,
                summary: _summaryLine([car?['name'], carLabels?['paint'], carLabels?['wheel']])),
              SizedBox(height: 12),
              Text(tr('Die Daten kommen direkt von deinem eigenen Ladecockpit.'),
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: AppTheme.textSecondary)),
            ],
            if (_data != null && _selectedTab == 1) ...[
              _tabIntro(
                tr('Ladeaktivität'),
                tr('Deine Ladevorgänge'),
                tr('Finde frühere Ladungen und filtere nach Zeitraum, Ladenetz oder Standort.'),
                Icons.ev_station_rounded,
              ),
              _sessions(_data?['sessions']),
              if (_data?['sessions'] is! List || (_data?['sessions'] as List).isEmpty)
                _loadStatePanel(
                  icon: Icons.history_rounded,
                  title: tr('Noch keine Ladevorgänge'),
                  message: tr('Sobald dein Ladecockpit Ladevorgänge erfasst hat, erscheinen sie hier.'),
                  color: AppTheme.textSecondary,
                ),
            ],
            if (_data != null && _selectedTab == 2) ...[
              _tabIntro(
                tr('Kosten & Überblick'),
                tr('Deine Auswertungen'),
                tr('Behalte Ladepreise, Kostenentwicklung und deine Monatsberichte im Blick.'),
                Icons.insights_rounded,
              ),
              _priceRadar(_data?['slots'], _data?['sites']),
              _costDevelopment(_data?['monthly']),
              _exports(_data?['monthly'], _data?['years']),
            ],
            if (_data == null && !_loading && _error == null)
              _loadStatePanel(
                icon: Icons.directions_car_outlined,
                title: tr('Noch nicht verbunden'),
                message: tr('Richte die Verbindung zu deinem Ladecockpit ein, um Fahrzeugstatus, Ladevorgänge und Kosten hier zu sehen.'),
                color: AppTheme.textSecondary,
                action: OutlinedButton.icon(
                  onPressed: _settings,
                  icon: Icon(Icons.settings_outlined),
                  label: Text(tr('Verbindung einrichten')),
                ),
              ),
          ],
          ),
        ),
      ),
      bottomNavigationBar: NavigationBar(
        height: 72,
        elevation: 8,
        backgroundColor: AppTheme.surface,
        indicatorColor: AppTheme.accentGreen.withValues(alpha: 0.16),
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        selectedIndex: _selectedTab,
        onDestinationSelected: (index) => setState(() => _selectedTab = index),
        destinations: [
          NavigationDestination(
            icon: Icon(Icons.directions_car_outlined),
            selectedIcon: Icon(Icons.directions_car),
            label: tr('Cockpit'),
          ),
          NavigationDestination(
            icon: Icon(Icons.ev_station_outlined),
            selectedIcon: Icon(Icons.ev_station),
            label: tr('Ladevorgänge'),
          ),
          NavigationDestination(
            icon: Icon(Icons.insights_outlined),
            selectedIcon: Icon(Icons.insights),
            label: tr('Auswertung'),
          ),
        ],
      ),
    );
  }
}
