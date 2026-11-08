import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:http/http.dart' as http;
export 'document_response.dart' show CockpitException;
import 'document_response.dart';
import 'theme/app_theme.dart';

void main() => runApp(const LadecockpitApp());

class LadecockpitApp extends StatelessWidget {
  const LadecockpitApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Ladecockpit',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      home: const DashboardPage(),
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

  Future<Uri> _endpoint(String path) async {
    final base = await serverUrl;
    if (base == null || base.isEmpty) {
      throw const CockpitException('Bitte zuerst die Serveradresse einrichten.');
    }
    final root = Uri.tryParse(base);
    if (root == null || !root.hasScheme || root.host.isEmpty ||
        (root.scheme != 'http' && root.scheme != 'https')) {
      throw const CockpitException('Bitte eine gültige HTTP- oder HTTPS-Serveradresse eingeben.');
    }
    return root.resolve(path);
  }

  Future<Map<String, dynamic>> invoicePages(String sessionId) async {
    final uri = await _endpoint('/api/invoice/${Uri.encodeComponent(sessionId)}/pages');
    final response = await _http.get(uri, headers: await _headers(json: true))
        .timeout(const Duration(seconds: 30));
    return parseDocumentPagesResponse(
      response.statusCode,
      response.body,
      documentLabel: 'die Rechnung',
      notFoundMessage: 'Die Rechnung ist auf dem Server noch nicht verfügbar.',
    );
  }

  Future<Uri> invoicePageUri(String sessionId, int page) =>
      _endpoint('/api/invoice/${Uri.encodeComponent(sessionId)}/page/$page.png');

  Future<String> csvExport() async {
    final uri = await _endpoint('/api/export.csv');
    final response = await _http.get(uri, headers: await _headers())
        .timeout(const Duration(seconds: 60));
    if (response.statusCode == 401) {
      throw const CockpitException('Anmeldung fehlgeschlagen. Bitte App-Passwort prüfen.');
    }
    if (response.statusCode != 200) {
      throw CockpitException('CSV-Export fehlgeschlagen (HTTP ${response.statusCode}).');
    }
    return utf8.decode(response.bodyBytes, allowMalformed: true);
  }

  Future<List<int>> invoiceZip(String month) async {
    final uri = await _endpoint('/api/invoices/$month.zip');
    final response = await _http.get(uri, headers: await _headers())
        .timeout(const Duration(seconds: 120));
    if (response.statusCode == 401) {
      throw const CockpitException('Anmeldung fehlgeschlagen. Bitte App-Passwort prüfen.');
    }
    if (response.statusCode == 404) {
      throw const CockpitException('Für diesen Monat sind keine Rechnungen vorhanden.');
    }
    if (response.statusCode != 200) {
      throw CockpitException('Rechnungs-ZIP fehlgeschlagen (HTTP ${response.statusCode}).');
    }
    return response.bodyBytes;
  }

  Future<Map<String, dynamic>> monthReportPages(String month) async {
    final uri = await _endpoint('/api/report/$month/pages');
    final response = await _http.get(uri, headers: await _headers(json: true))
        .timeout(const Duration(seconds: 60));
    return parseDocumentPagesResponse(
      response.statusCode,
      response.body,
      documentLabel: 'den Monatsbericht',
    );
  }

  Future<Uri> monthReportPageUri(String month, int page) =>
      _endpoint('/api/report/$month/page/$page.png');

  Future<Map<String, dynamic>> dashboard() async {
    final uri = await _endpoint('/api/dashboard');
    final headers = await _headers(json: true);
    final response = await _http.get(uri, headers: headers)
        .timeout(const Duration(seconds: 20));
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
    throw const CockpitException(
      'Anmeldung fehlgeschlagen (HTTP 401/403). Bitte App-Passwort und Zugriffsrechte prüfen.',
    );
  }
  if (statusCode != 200) {
    throw CockpitException('Server antwortet mit HTTP $statusCode.');
  }
  final decoded = jsonDecode(body);
  if (decoded is! Map<String, dynamic>) {
    throw const CockpitException('Ungültige Antwort vom Ladecockpit.');
  }
  return decoded;
}

String connectionErrorMessage(Object error) {
if (error is CockpitException) return error.message;
if (error is TimeoutException) {
  return 'Zeitüberschreitung: Der Server hat nicht rechtzeitig geantwortet. Bitte Verbindung prüfen und erneut versuchen.';
}
if (error is HandshakeException) {
  return 'Sichere Verbindung fehlgeschlagen: Bitte HTTPS-Zertifikat und Serveradresse prüfen.';
}
if (error is SocketException) {
  return 'Server nicht erreichbar: Netzwerk, Serveradresse oder VPN/Tailscale-Verbindung prüfen.';
}
if (error is HttpException) {
  return 'Netzwerkfehler bei der HTTP-Verbindung: Bitte Verbindung prüfen und erneut versuchen.';
}
if (error is FormatException) {
  return 'Der Server hat eine ungültige Antwort gesendet. Bitte später erneut versuchen.';
}
return 'Verbindung fehlgeschlagen: $error';
}

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key});
  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  final _client = CockpitClient();
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
  }

  String _fetchTimeLabel(DateTime? value) {
    if (value == null) return 'Noch kein erfolgreicher Abruf';
    final date = value.toLocal();
    final day = date.day.toString().padLeft(2, '0');
    final month = date.month.toString().padLeft(2, '0');
    final hour = date.hour.toString().padLeft(2, '0');
    final minute = date.minute.toString().padLeft(2, '0');
    return '$day.$month.${date.year}, $hour:$minute Uhr';
  }

  Future<void> _load() async {
    if (_loading) return;
    setState(() { _loading = true; _error = null; });
    try {
      final data = await _client.dashboard();
      if (mounted) {
        setState(() {
          _data = data;
          _lastSuccessfulFetch = DateTime.now();
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = connectionErrorMessage(e));
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _settings() async {
    final urlController = TextEditingController(text: await _client.serverUrl ?? '');
    final passwordController = TextEditingController(text: await _client.password ?? '');
    if (!mounted) return;
    final saved = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Verbindung einrichten'),
        content: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(
              controller: urlController,
              keyboardType: TextInputType.url,
              decoration: const InputDecoration(
                labelText: 'Ladecockpit-Adresse',
                hintText: 'http://100.x.y.z:8077',
                helperText: 'Tailscale-IP oder MagicDNS-Adresse inklusive Port',
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: passwordController,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'App-Passwort (falls aktiviert)'),
            ),
          ]),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Abbrechen')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Speichern')),
        ],
      ),
    );
    if (saved == true) {
      await _client.saveConnection(urlController.text, passwordController.text);
      await _load();
    }
    urlController.dispose();
    passwordController.dispose();
  }

  String _value(dynamic value) {
    if (value == null) return '–';
    if (value is double) return value.toStringAsFixed(1);
    if (value is Map || value is List) return '';
    return value.toString();
  }

  Widget _metric(String title, dynamic value, {String suffix = ''}) {
    final text = _value(value);
    if (text.isEmpty) return const SizedBox.shrink();
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [AppTheme.surfaceElevated, AppTheme.surface],
          ),
        ),
        padding: const EdgeInsets.fromLTRB(15, 14, 15, 15),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                Container(
                  width: 6,
                  height: 6,
                  decoration: const BoxDecoration(
                    color: AppTheme.accentTeal,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 7),
                Expanded(
                  child: Text(
                    title.toUpperCase(),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
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
            const SizedBox(height: 10),
            FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Text(
                '$text$suffix',
                maxLines: 1,
                style: const TextStyle(
                  color: AppTheme.textPrimary,
                  fontSize: 23,
                  height: 1.05,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.7,
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
      return const SizedBox.shrink();
    }
    final energy = home['kwh'] == null ? '–' : '${_sectionValue('kwh', home['kwh'])}';
    final cost = home['cost'] == null ? '–' : '${_sectionValue('total_cost', home['cost'])}';
    return Card(
      margin: const EdgeInsets.only(top: 2, bottom: 10),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        child: Row(
          children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: AppTheme.accentTeal.withValues(alpha: 0.10),
                borderRadius: BorderRadius.circular(11),
              ),
              child: const Icon(Icons.home_outlined,
                color: AppTheme.accentTeal, size: 19),
            ),
            const SizedBox(width: 11),
            const Expanded(child: Text('Zuhause geladen',
              style: TextStyle(fontWeight: FontWeight.w600))),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(energy, style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 2),
                Text(cost, style: const TextStyle(
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
      'range_at_100': 'Reichweite bei 100 %', 'change_pct': 'Veränderung',
      'since': 'Seit', 'samples': 'Messwerte', 'dc_share': 'Supercharger-Anteil',
      'per_100': 'Kosten pro 100 km', 'kwh_per_100': 'Verbrauch pro 100 km',
      'distance': 'Gefahrene Strecke', 'savings': 'Ersparnis gegenüber Verbrenner',
      'fuel_equivalent': 'Vergleichbare Spritkosten', 'label': 'Bezeichnung',
      'best_time': 'Günstigste Ladezeit', 'best_site': 'Günstigster Standort',
      'best_time_price': 'Preis zur besten Ladezeit',
      'best_site_price': 'Preis am günstigsten Standort',
    };
    return labels[key] ?? key.replaceAll('_', ' ').replaceFirstMapped(
      RegExp(r'^[a-z]'), (match) => match.group(0)!.toUpperCase());
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
      final number = value.toStringAsFixed(digits);
      if (percentKeys.contains(key)) return '$number %';
      if (energyKeys.contains(key)) return '$number kWh';
      if (moneyKeys.contains(key)) return '$number €';
      if (priceKeys.contains(key)) return '$number €/kWh';
      if (key == 'dist_day') return '$number km/Tag';
      if (distanceKeys.contains(key)) return '$number km';
      if (key == 'avg_kw') return '$number kW';
      if (key == 'rate_pct_day') return '$number %/Tag';
      if (key == 'per_100') return '$number €/100 km';
      if (key == 'kwh_per_100') return '$number kWh/100 km';
      if (key == 'duration_min') return _durationLabel(value);
      if (key == 'days_to_floor') return '$number Tage';
      return number;
    }
    if (value is bool) return value ? 'Ja' : 'Nein';
    if (value is String && value.contains('T')) return _dateTimeLabel(value);
    return value.toString();
  }

  Widget _section(String title, Map<String, dynamic>? values) {
    if (values == null || values.isEmpty) return const SizedBox.shrink();
    final entries = values.entries
        .where((e) => e.value != null && e.value is! Map && e.value is! List)
        .take(8).toList();
    if (entries.isEmpty) return const SizedBox.shrink();

    final first = entries.first;
    final summary = '${_sectionLabel(first.key)} · ${_sectionValue(first.key, first.value)}';

    return Card(
      margin: const EdgeInsets.only(top: 5, bottom: 5),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          initiallyExpanded: false,
          tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
          leading: const Icon(Icons.tune_rounded,
            color: AppTheme.textSecondary, size: 20),
          title: Text(title,
            style: const TextStyle(fontWeight: FontWeight.w700)),
          subtitle: Text(summary,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
          children: [
            for (var i = 0; i < entries.length; i++) ...[
              if (i > 0) const Divider(height: 1),
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 10),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: Text(_sectionLabel(entries[i].key),
                      style: const TextStyle(color: AppTheme.textSecondary))),
                    const SizedBox(width: 12),
                    Flexible(child: Text(
                      _sectionValue(entries[i].key, entries[i].value),
                      textAlign: TextAlign.end,
                      style: const TextStyle(fontWeight: FontWeight.w600))),
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
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 16, color: AppTheme.textSecondary),
        const SizedBox(width: 6),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: Theme.of(context).textTheme.labelSmall?.copyWith(color: AppTheme.textSecondary)),
              const SizedBox(height: 2),
              Text(value, maxLines: 2, overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w600)),
            ],
          ),
        ),
      ],
    );
  }

  Widget _sessions(dynamic raw) {
    if (raw is! List || raw.isEmpty) return const SizedBox.shrink();
    final items = raw.whereType<Map<String, dynamic>>().toList();
    if (items.isEmpty) return const SizedBox.shrink();

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
      return '${names[index - 1]} ${parts[0]}';
    }

    String dateLabel(dynamic value) {
      final date = DateTime.tryParse(value?.toString() ?? '')?.toLocal();
      if (date == null) return 'Datum unbekannt';
      final day = date.day.toString().padLeft(2, '0');
      final month = date.month.toString().padLeft(2, '0');
      return '$day.$month.${date.year}';
    }

    String number(dynamic value, {int digits = 1}) {
      final parsed = value is num ? value : num.tryParse(value?.toString() ?? '');
      return parsed == null ? '–' : parsed.toStringAsFixed(digits);
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
            contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
          ),
          items: options,
          onChanged: onChanged,
        ),
      );
    }

    final monthOptions = <DropdownMenuItem<String>>[
      const DropdownMenuItem(value: 'all', child: Text('Alle Monate')),
      ...months.map((m) => DropdownMenuItem(value: m, child: Text(monthLabel(m)))),
    ];
    final networkOptions = <DropdownMenuItem<String>>[
      const DropdownMenuItem(value: 'all', child: Text('Alle Netzwerke')),
      ...networks.map((n) => DropdownMenuItem(
        value: n,
        child: Text(n == 'multipass' ? 'MultiPass' :
          n == 'supercharger' ? 'Supercharger' : n),
      )),
    ];
    final siteOptions = <DropdownMenuItem<String>>[
      const DropdownMenuItem(value: 'all', child: Text('Alle Standorte')),
      ...sites.map((s) => DropdownMenuItem(value: s, child: Text(s,
        overflow: TextOverflow.ellipsis))),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 22, 4, 8),
          child: Row(
            children: [
              Expanded(child: Text('Ladevorgänge',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold))),
              Text('${filtered.length} / ${items.length}',
                style: Theme.of(context).textTheme.labelMedium?.copyWith(color: AppTheme.textSecondary)),
            ],
          ),
        ),
        Builder(builder: (context) {
          final filtersActive = selectedMonth != 'all' ||
              selectedNetwork != 'all' || selectedSite != 'all';
          final filterSummary = [
            selectedMonth == 'all' ? 'Alle Zeiträume' : monthLabel(selectedMonth),
            selectedNetwork == 'all' ? 'Alle Netzwerke' :
              (selectedNetwork == 'multipass' ? 'MultiPass' :
                selectedNetwork == 'supercharger' ? 'Supercharger' : selectedNetwork),
            selectedSite == 'all' ? 'Alle Standorte' : selectedSite,
          ].join(' · ');
          return Card(
            margin: const EdgeInsets.only(bottom: 8),
            child: ExpansionTile(
              initiallyExpanded: false,
              leading: Icon(Icons.tune,
                color: filtersActive ? Theme.of(context).colorScheme.primary : AppTheme.textSecondary),
              title: Row(
                children: [
                  const Expanded(child: Text('Filter', style: TextStyle(fontWeight: FontWeight.w600))),
                  if (filtersActive)
                    Text('Aktiv', style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: Theme.of(context).colorScheme.primary, fontWeight: FontWeight.w700)),
                ],
              ),
              subtitle: Text(filterSummary, maxLines: 1, overflow: TextOverflow.ellipsis),
              childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
              children: [
                LayoutBuilder(
                  builder: (context, constraints) {
                    final compact = constraints.maxWidth < 520;
                    final fields = [
                      filterField('Zeitraum', selectedMonth, monthOptions,
                        (value) => setState(() => _sessionMonthFilter = value ?? 'all'),
                        width: compact ? double.infinity : 165),
                      filterField('Netzwerk', selectedNetwork, networkOptions,
                        (value) => setState(() => _sessionNetworkFilter = value ?? 'all'),
                        width: compact ? double.infinity : 165),
                      filterField('Standort', selectedSite, siteOptions,
                        (value) => setState(() => _sessionSiteFilter = value ?? 'all'),
                        width: compact ? double.infinity : 210),
                    ];
                    if (compact) {
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          for (var i = 0; i < fields.length; i++) ...[
                            if (i > 0) const SizedBox(height: 8),
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
                      icon: const Icon(Icons.filter_alt_off, size: 17),
                      label: const Text('Filter zurücksetzen'),
                    ),
                  ),
              ],
            ),
          );
        }),
        if (filtered.isEmpty)
          const Card(child: Padding(
            padding: EdgeInsets.all(16),
            child: Text('Keine Ladevorgänge für diese Filter gefunden.'),
          )),
        ...filtered.take(50).map((session) {
          final site = session['site']?.toString() ?? 'Unbekannter Standort';
          final networkValue = session['network']?.toString() ?? 'supercharger';
          final network = networkValue == 'multipass' ? 'MultiPass' :
            networkValue == 'supercharger' ? 'Supercharger' : networkValue;
          final kwhValue = session['kwh'];
          final costValue = session['cost'];
          final durationValue = session['duration_min'];
          final kwh = kwhValue == null ? null : number(kwhValue);
          final cost = costValue == null ? null : number(costValue, digits: 2);
          final duration = durationValue == null ? null : _durationLabel(durationValue);
          final currency = session['currency']?.toString() ?? 'EUR';
          final currencyLabel = currency == 'EUR' ? '€' : currency;
          final invoice = session['has_invoice'] == true;
          final metrics = <Widget>[
            if (kwh != null)
              _sessionMetric('Energie', '$kwh kWh', Icons.bolt),
            if (cost != null)
              _sessionMetric('Kosten', '$cost $currencyLabel', Icons.euro),
            if (duration != null)
              _sessionMetric('Dauer', duration, Icons.schedule),
          ];
          return Card(
            clipBehavior: Clip.antiAlias,
            child: InkWell(
              onTap: () => _showSessionDetails(session),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(13, 10, 13, 11),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Icon(
                        invoice ? Icons.receipt_long_outlined : Icons.ev_station,
                        color: invoice ? Theme.of(context).colorScheme.primary : AppTheme.textSecondary,
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(site, maxLines: 1, overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontWeight: FontWeight.w600)),
                            const SizedBox(height: 3),
                            Text(
                              '${dateLabel(session['start'])} · $network${invoice ? ' · Rechnung vorhanden' : ''}',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppTheme.textSecondary),
                            ),
                          ],
                        ),
                      ),
                      const Icon(Icons.chevron_right, color: AppTheme.textSecondary),
                    ]),
                    if (metrics.isNotEmpty) ...[
                      const SizedBox(height: 9),
                      const Divider(height: 1),
                      const SizedBox(height: 8),
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          for (var i = 0; i < metrics.length; i++) ...[
                            if (i > 0) const SizedBox(width: 8),
                            Expanded(child: metrics[i]),
                          ],
                        ],
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
            padding: const EdgeInsets.all(8),
            child: Text('Es werden die ersten 50 Treffer angezeigt.',
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
    return '$day.$month.${date.year}, $hour:$minute Uhr';
  }

  String _numberLabel(dynamic value, {int digits = 2, String suffix = ''}) {
    final parsed = value is num ? value : num.tryParse(value?.toString() ?? '');
    return parsed == null ? '–' : '${parsed.toStringAsFixed(digits)}$suffix';
  }

  String _durationLabel(dynamic value) {
    final minutes = value is num ? value.round() : int.tryParse(value?.toString() ?? '');
    if (minutes == null) return '–';
    final hours = minutes ~/ 60;
    final rest = minutes % 60;
    return hours > 0 ? '$hours Std. $rest Min.' : '$rest Min.';
  }

  Widget _detailRow(String label, String value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 7),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(child: Text(label, style: const TextStyle(color: AppTheme.textSecondary))),
        const SizedBox(width: 12),
        Flexible(child: Text(value, textAlign: TextAlign.end,
          style: const TextStyle(fontWeight: FontWeight.w600))),
      ],
    ),
  );

  Widget _detailGroup(String title, List<Widget> rows) {
    if (rows.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.labelLarge?.copyWith(
            color: Theme.of(context).colorScheme.primary,
            fontWeight: FontWeight.w700,
          )),
          const SizedBox(height: 4),
          ...rows,
        ],
      ),
    );
  }

  Future<void> _showSessionDetails(Map<String, dynamic> session) async {
    final site = session['site']?.toString() ?? 'Unbekannter Standort';
    final currency = session['currency']?.toString() ?? 'EUR';
    final currencySymbol = currency == 'EUR' ? '€' : currency;
    final networkValue = session['network']?.toString() ?? 'supercharger';
    final network = networkValue == 'multipass' ? 'MultiPass'
        : networkValue == 'supercharger' ? 'Supercharger' : networkValue;
    final invoice = session['has_invoice'] == true;
    final sessionId = session['id']?.toString();
    String? textValue(String key) {
      final value = session[key];
      if (value == null || value.toString().trim().isEmpty) return null;
      return value.toString();
    }
    final timingRows = <Widget>[
      if (textValue('start') != null)
        _detailRow('Beginn', _dateTimeLabel(session['start'])),
      if (textValue('end') != null)
        _detailRow('Ende', _dateTimeLabel(session['end'])),
      if (session['duration_min'] != null)
        _detailRow('Ladedauer', _durationLabel(session['duration_min'])),
    ];
    final costRows = <Widget>[
      if (session['kwh'] != null)
        _detailRow('Geladene Energie', _numberLabel(session['kwh'], suffix: ' kWh')),
      if (session['cost'] != null)
        _detailRow('Gesamtkosten', _numberLabel(session['cost'], suffix: ' $currencySymbol')),
      if (session['charge_cost'] != null)
        _detailRow('Ladekosten', _numberLabel(session['charge_cost'], suffix: ' $currencySymbol')),
      if (session['idle'] != null)
        _detailRow('Standgebühren', _numberLabel(session['idle'], suffix: ' $currencySymbol')),
      if (session['credit'] != null)
        _detailRow('Gutschrift', _numberLabel(session['credit'], suffix: ' $currencySymbol')),
      if (session['price'] != null)
        _detailRow('Preis pro kWh', _numberLabel(session['price'], digits: 3, suffix: ' $currencySymbol/kWh')),
      if (session['avg_kw'] != null)
        _detailRow('Durchschnittsleistung', _numberLabel(session['avg_kw'], suffix: ' kW')),
      if (session['start_soc'] != null)
        _detailRow('Start-Ladestand', _numberLabel(session['start_soc'], digits: 0, suffix: ' %')),
    ];
    final locationRows = <Widget>[
      if (textValue('operator') != null)
        _detailRow('Betreiber', textValue('operator')!),
      if (textValue('address') != null)
        _detailRow('Adresse', textValue('address')!),
    ];

    await showDialog<void>(
      context: context,
      builder: (dialogContext) => Dialog.fullscreen(
        child: Scaffold(
          appBar: AppBar(
            title: const Text('Ladevorgang'),
            leading: IconButton(
              icon: const Icon(Icons.close),
              tooltip: 'Schließen',
              onPressed: () => Navigator.pop(dialogContext),
            ),
          ),
          body: ListView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
            children: [
              Text(site,
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w800)),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  Chip(
                    avatar: const Icon(Icons.ev_station, size: 16),
                    label: Text(network),
                  ),
                  if (invoice)
                    const Chip(
                      avatar: Icon(Icons.receipt_long, size: 16),
                      label: Text('Rechnung vorhanden'),
                    ),
                ],
              ),
              _detailGroup('ZEITRAUM', timingRows),
              _detailGroup('ENERGIE UND KOSTEN', costRows),
              _detailGroup('STANDORT', locationRows),
              if (!invoice)
                const Padding(
                  padding: EdgeInsets.only(top: 18),
                  child: Text('Für diesen Ladevorgang ist keine Rechnung hinterlegt.',
                    style: TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
                ),
            ],
          ),
          bottomNavigationBar: invoice && sessionId != null
              ? SafeArea(
                  minimum: const EdgeInsets.fromLTRB(20, 8, 20, 16),
                  child: FilledButton.icon(
                    onPressed: () {
                      Navigator.pop(dialogContext);
                      _showInvoice(sessionId, site);
                    },
                    icon: const Icon(Icons.receipt_long),
                    label: const Text('Rechnung öffnen'),
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
    if (slots.isEmpty && sites.isEmpty) return const SizedBox.shrink();

    Widget priceValue(dynamic value, {bool highlighted = false}) =>
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
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
            value is num ? '${value.toStringAsFixed(3)} €' : '–',
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
          padding: const EdgeInsets.fromLTRB(4, 22, 4, 8),
          child: Text('Preisradar',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
        ),
        if (slots.isNotEmpty) ...[
          const Padding(
            padding: EdgeInsets.fromLTRB(4, 4, 4, 6),
            child: Text('Tarif nach Ladezeit', style: TextStyle(color: AppTheme.textSecondary)),
          ),
          ...slots.map((slot) {
            final label = slot['label']?.toString() ?? 'Zeitfenster';
            final range = slot['range']?.toString() ?? '';
            final count = slot['sessions'] is num ? (slot['sessions'] as num).round() : 0;
            final isCheapest = slot['avg_price'] is num &&
                lowestSlotPrice != null && slot['avg_price'] == lowestSlotPrice;
            return Card(
              child: ListTile(
                dense: true,
                leading: Icon(isCheapest ? Icons.savings_outlined : Icons.schedule,
                  color: isCheapest ? AppTheme.accentGreen : AppTheme.textSecondary),
                title: Text('$label${isCheapest ? ' · Günstigste Zeit' : ''}'),
                subtitle: Text('${range.isEmpty ? 'Zeitfenster' : range} · $count Ladevorgänge'),
                trailing: Column(\n                  mainAxisAlignment: MainAxisAlignment.center,\n                  crossAxisAlignment: CrossAxisAlignment.end,\n                  mainAxisSize: MainAxisSize.min,\n                  children: [priceValue(slot['avg_price'], highlighted: isCheapest),\n                    const SizedBox(height: 2),\n                    const Text('€/kWh', style: TextStyle(fontSize: 9, color: AppTheme.textSecondary)),\n                  ],\n                ),
              ),
            );
          }),
        ],
        if (sites.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 14, 4, 6),
            child: Text('Deine häufigsten Ladestandorte',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                color: AppTheme.textSecondary, fontWeight: FontWeight.w700)),
          ),
          Card(
            child: ExpansionTile(
              initiallyExpanded: false,
              leading: const Icon(Icons.ev_station, color: AppTheme.accentTeal),
              title: Text('${sites.length} Ladestandorte',
                style: const TextStyle(fontWeight: FontWeight.w700)),
              subtitle: const Text('Durchschnittspreise und Ladehäufigkeit'),
              children: sites.map((site) {
                final label = site['label']?.toString() ??
                    site['site']?.toString() ?? 'Unbekannter Standort';
                final network = site['network'] == 'multipass' ? 'MultiPass' : 'Supercharger';
                final count = site['sessions'] is num ? (site['sessions'] as num).round() : 0;
                final kwh = _numberLabel(site['kwh'], digits: 1, suffix: ' kWh');
                final address = site['address']?.toString();
                final isCheapest = site['avg_price'] is num &&
                    lowestSitePrice != null && site['avg_price'] == lowestSitePrice;
                return ListTile(
                  dense: true,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
                  leading: Icon(isCheapest ? Icons.savings_outlined : Icons.location_on_outlined,
                    color: isCheapest ? AppTheme.accentGreen : AppTheme.textSecondary),
                  title: Text('$label${isCheapest ? ' · Günstigster' : ''}',
                    maxLines: 2, overflow: TextOverflow.ellipsis),
                  subtitle: Text('$network · $count Ladevorgänge · $kwh'
                    '${address != null && address.isNotEmpty ? '\n$address' : ''}'),
                  isThreeLine: address != null && address.isNotEmpty,
                  trailing: priceValue(site['avg_price'], highlighted: isCheapest),
                );
              }).toList(),
            ),
          ),
        ],
        const Padding(
          padding: EdgeInsets.fromLTRB(4, 4, 4, 0),
          child: Text('Preiswerte basieren auf den erfassten Rechnungsdaten und sind keine Live-Tarife.',
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
        text: 'Ladecockpit – Rechnungen $month',
        subject: 'Ladecockpit Rechnungen $month',
      );
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error.toString())),
      );
    }
  }

  Future<void> _showMonthlyReport(String month) async {
    try {
      final metadata = await _client.monthReportPages(month);
      final pages = metadata['pages'] as int;
      final headers = await _client._headers();
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (dialogContext) => Dialog.fullscreen(
          child: Scaffold(
            appBar: AppBar(
              title: Text('Monatsbericht · $month'),
              leading: IconButton(
                icon: const Icon(Icons.close),
                onPressed: () => Navigator.pop(dialogContext),
              ),
            ),
            body: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(14),
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
                          child: const Icon(Icons.assessment_outlined,
                            color: AppTheme.accentTeal),
                        ),
                        const SizedBox(width: 12),
                        const Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('MONATSAUSWERTUNG',
                                style: TextStyle(fontSize: 10, letterSpacing: 1.1,
                                  color: AppTheme.textSecondary, fontWeight: FontWeight.w700)),
                              SizedBox(height: 3),
                              Text('Dein Ladebericht',
                                style: TextStyle(fontWeight: FontWeight.w700)),
                            ],
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text('${pages} ${pages == 1 ? 'Seite' : 'Seiten'}',
                          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                      ],
                    ),
                  ),
                ),
                Expanded(
                  child: ListView.builder(
                    padding: const EdgeInsets.fromLTRB(8, 8, 8, 24),
                    itemCount: pages,
                    itemBuilder: (context, index) => Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: FutureBuilder<Uri>(
                        future: _client.monthReportPageUri(month, index + 1),
                        builder: (context, snapshot) {
                          if (snapshot.hasError) {
                            return const Padding(
                              padding: EdgeInsets.all(24),
                              child: Text('Seite konnte nicht geladen werden.'),
                            );
                          }
                          if (!snapshot.hasData) {
                            return const SizedBox(
                              height: 240,
                              child: Center(child: CircularProgressIndicator()),
                            );
                          }
                          return Image.network(snapshot.data.toString(), headers: headers,
                            fit: BoxFit.contain,
                            loadingBuilder: (context, child, progress) => progress == null
                                ? child
                                : const SizedBox(
                                    height: 240,
                                    child: Center(child: CircularProgressIndicator()),
                                  ),
                            errorBuilder: (_, __, ___) => const Padding(
                              padding: EdgeInsets.all(24),
                              child: Text('Seite konnte nicht geladen werden.'),
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
      final rows = const LineSplitter().convert(csv);
      final preview = rows.take(8).join('\n');
      await showDialog<void>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('CSV-Export'),
          content: SizedBox(
            width: double.maxFinite,
            child: SingleChildScrollView(
              child: SelectableText(
                '${rows.length > 8 ? '$preview\n…\n' : '$preview\n'}${rows.length} Zeilen insgesamt',
                style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('Schließen'),
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
                  text: 'Ladecockpit – Ladevorgänge als CSV',
                  subject: 'Ladecockpit CSV-Export',
                );
              },
              icon: const Icon(Icons.copy),
              label: const Text('CSV teilen / speichern'),
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
      const SizedBox(width: 6),
      Text(label, style: const TextStyle(color: AppTheme.textSecondary, fontSize: 11)),
    ],
  );

  Widget _costDevelopment(dynamic rawMonths) {
    final months = rawMonths is List
        ? rawMonths.whereType<Map<String, dynamic>>()
            .where((month) => month['key'] is String).toList()
        : <Map<String, dynamic>>[];
    if (months.isEmpty) return const SizedBox.shrink();

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

    Widget summaryMetric(String label, String value, String detail, IconData icon) =>
        Expanded(
          child: Card(
            margin: EdgeInsets.zero,
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(icon, size: 18, color: AppTheme.accentGreen),
                  const SizedBox(height: 8),
                  Text(label, style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: AppTheme.textSecondary)),
                  const SizedBox(height: 3),
                  FittedBox(
                    fit: BoxFit.scaleDown,
                    alignment: Alignment.centerLeft,
                    child: Text(value, style: const TextStyle(
                      fontSize: 18, fontWeight: FontWeight.w800)),
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
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 22, 4, 8),
          child: Text('Kostenentwicklung',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
        ),
        Row(
          children: [
            summaryMetric('Letzter Monat', '${values.last.toStringAsFixed(2)} €',
              latestLabel, Icons.calendar_month_outlined),
            const SizedBox(width: 10),
            summaryMetric('Monatsdurchschnitt', '${averageCost.toStringAsFixed(2)} €',
              'über ${months.length} Monate', Icons.show_chart),
          ],
        ),
        const SizedBox(height: 8),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
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
                      ? 'nicht erfasst'
                      : homeCostKnown ? '${homeCost.toStringAsFixed(2)} €'
                      : 'Preis nicht hinterlegt';
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
                        comparison = '$sign${difference.toStringAsFixed(2)} € ($sign${percentage.toStringAsFixed(1)} %) gegenüber Vormonat';
                        comparisonColor = difference > 0 ? AppTheme.warning :
                            difference < 0 ? AppTheme.accentGreen : AppTheme.textSecondary;
                      } else {
                        comparison = 'Vormonat ohne erfasste Kosten – kein Prozentvergleich';
                        comparisonColor = AppTheme.textSecondary;
                      }
                    }
                  }
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 7),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            SizedBox(width: 54, child: Text(label,
                              style: const TextStyle(color: AppTheme.textSecondary))),
                            Expanded(
                              child: ClipRRect(
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
                              ),
                            ),
                            const SizedBox(width: 12),
                            SizedBox(width: 76, child: Text('${total.toStringAsFixed(2)} €',
                              textAlign: TextAlign.end,
                              style: const TextStyle(fontWeight: FontWeight.w600))),
                          ],
                        ),
                        Theme(
                          data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                          child: ExpansionTile(
                            tilePadding: const EdgeInsets.only(left: 48, right: 4),
                            childrenPadding: const EdgeInsets.only(left: 54, right: 4, bottom: 8),
                            dense: true,
                            visualDensity: VisualDensity.compact,
                            title: Text(
                              '${(publicEnergy + (homeEnergyKnown ? homeEnergy : 0)).toStringAsFixed(1)} kWh · ${amount(month['sessions']).round()} öffentliche Ladevorgänge',
                              style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                            children: [
                              Align(
                                alignment: Alignment.centerLeft,
                                child: Text(
                                  'Öffentlich: ${publicCost.toStringAsFixed(2)} € · Zuhause: $homeCostLabel'
                                  '\nEnergie: öffentlich ${publicEnergy.toStringAsFixed(1)} kWh · zuhause ${homeEnergyKnown ? '${homeEnergy.toStringAsFixed(1)} kWh' : 'nicht erfasst'}',
                                  style: const TextStyle(color: AppTheme.textSecondary, fontSize: 11)),
                              ),
                              if (comparison != null)
                                Align(
                                  alignment: Alignment.centerLeft,
                                  child: Padding(
                                    padding: const EdgeInsets.only(top: 6),
                                    child: Text(comparison,
                                      style: TextStyle(color: comparisonColor, fontSize: 11)),
                                  ),
                                ),
                            ],
                          ),
                        ),
                        if (index != months.length - 1) const SizedBox(height: 3),
                      ],
                    ),
                  );
                }),
                const Divider(height: 20),
                Wrap(
                  spacing: 14,
                  runSpacing: 8,
                  children: [
                    _costLegend(Theme.of(context).colorScheme.primary, 'Öffentlich'),
                    _costLegend(Colors.lightBlueAccent, 'Zuhause · erfasste Kosten'),
                  ],
                ),
                const SizedBox(height: 8),
                const Align(alignment: Alignment.centerLeft,
                  child: Text('Nicht erfasste Heimladekosten werden nicht als 0 € gewertet. Balken zeigen nur bekannte Kosten; Vergleiche berücksichtigen nur die erfassten Beträge.',
                    style: TextStyle(color: AppTheme.textSecondary, fontSize: 11))),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _exports(dynamic rawMonths) {
    final months = rawMonths is List
        ? rawMonths.whereType<Map<String, dynamic>>()
            .where((month) => month['key'] is String).toList().reversed.toList()
        : <Map<String, dynamic>>[];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 22, 4, 8),
          child: Text('Berichte & Export',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
        ),
        Card(
          child: ListTile(
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
            leading: Container(
              width: 42,
              height: 42,
              decoration: BoxDecoration(
                color: AppTheme.accentTeal.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(13),
              ),
              child: const Icon(Icons.table_chart_outlined, color: AppTheme.accentTeal),
            ),
            title: const Text('Ladehistorie exportieren',
              style: TextStyle(fontWeight: FontWeight.w700)),
            subtitle: const Text('Alle Ladevorgänge als CSV für Excel'),
            trailing: const Icon(Icons.chevron_right, color: AppTheme.textSecondary),
            onTap: _showCsvExport,
          ),
        ),
        if (months.isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 14, 4, 6),
            child: Text('MONATSBERICHTE',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                color: AppTheme.textSecondary, letterSpacing: 1.1, fontWeight: FontWeight.w700)),
          ),
        ...months.map((month) {
          final key = month['key'].toString();
          final parts = key.split('-');
          final label = parts.length == 2 ? '${parts[1]}.${parts[0]}' : key;
          final count = month['sessions'] is num ? (month['sessions'] as num).round() : 0;
          final energy = _numberLabel(month['kwh'], digits: 1, suffix: ' kWh');
          return Card(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(14, 12, 8, 12),
              child: Row(
                children: [
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      color: AppTheme.accentGreen.withValues(alpha: 0.10),
                      borderRadius: BorderRadius.circular(13),
                    ),
                    child: const Icon(Icons.calendar_month_outlined,
                      color: AppTheme.accentGreen),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: InkWell(
                      borderRadius: BorderRadius.circular(10),
                      onTap: () => _showMonthlyReport(key),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(label, style: const TextStyle(fontWeight: FontWeight.w700)),
                            const SizedBox(height: 3),
                            Text('$count Ladevorgänge · $energy',
                              style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                          ],
                        ),
                      ),
                    ),
                  ),
                  IconButton(
                    tooltip: 'Rechnungen als ZIP teilen',
                    onPressed: () => _shareInvoiceZip(key),
                    icon: const Icon(Icons.folder_zip_outlined),
                  ),
                  IconButton(
                    tooltip: 'Monatsbericht ansehen',
                    onPressed: () => _showMonthlyReport(key),
                    icon: const Icon(Icons.picture_as_pdf_outlined,
                      color: AppTheme.accentTeal),
                  ),
                ],
              ),
            ),
          );
        }),
        if (months.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: Text('Sobald Monatsdaten vorhanden sind, erscheinen deine Berichte hier.',
              style: TextStyle(color: AppTheme.textSecondary)),
          )
        else
          const Padding(
            padding: EdgeInsets.fromLTRB(4, 4, 4, 0),
            child: Text('Monatsbericht öffnen oder die zugehörigen Rechnungen gesammelt teilen.',
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
              title: Text('Rechnung · $site', maxLines: 1, overflow: TextOverflow.ellipsis),
              leading: IconButton(
                icon: const Icon(Icons.close),
                onPressed: () => Navigator.pop(dialogContext),
              ),
            ),
            body: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(14),
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
                          child: const Icon(Icons.receipt_long_outlined,
                            color: AppTheme.accentGreen),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text('LADERECHNUNG',
                                style: TextStyle(fontSize: 10, letterSpacing: 1.1,
                                  color: AppTheme.textSecondary, fontWeight: FontWeight.w700)),
                              const SizedBox(height: 3),
                              Text(site, maxLines: 1, overflow: TextOverflow.ellipsis,
                                style: const TextStyle(fontWeight: FontWeight.w700)),
                            ],
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text('${pages} ${pages == 1 ? 'Seite' : 'Seiten'}',
                          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                      ],
                    ),
                  ),
                ),
                Expanded(
                  child: ListView.builder(
                    padding: const EdgeInsets.fromLTRB(8, 8, 8, 24),
                    itemCount: pages,
                    itemBuilder: (context, index) => Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: FutureBuilder<Uri>(
                        future: _client.invoicePageUri(sessionId, index + 1),
                        builder: (context, uriSnapshot) {
                          if (uriSnapshot.hasError) {
                            return const Padding(
                              padding: EdgeInsets.all(24),
                              child: Text('Seite konnte nicht geladen werden.'),
                            );
                          }
                          if (!uriSnapshot.hasData) {
                            return const SizedBox(
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
                                : const SizedBox(
                                    height: 240,
                                    child: Center(child: CircularProgressIndicator()),
                                  ),
                            errorBuilder: (context, error, stack) => const Padding(
                              padding: EdgeInsets.all(24),
                              child: Text('PDF-Seite konnte nicht geladen werden.'),
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
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          Icon(icon, size: 18, color: color ?? AppTheme.textSecondary),
          const SizedBox(width: 10),
          Expanded(child: Text(label, style: const TextStyle(color: AppTheme.textSecondary))),
          Flexible(child: Text(value, textAlign: TextAlign.end,
            style: TextStyle(fontWeight: FontWeight.w600, color: color))),
        ],
      ),
    );
  }

  Widget _vehicleHero(Map<String, dynamic>? status, Map<String, dynamic>? car) {
    final data = status ?? {};
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
        ? 'LETZTER BEKANNTER STAND'
        : socSource == 'live' ? 'LIVE-FAHRZEUGDATEN' : 'AKKUSTAND';
    final readingColor = socSource == 'last'
        ? AppTheme.warning
        : socSource == 'live' ? AppTheme.accentGreen : AppTheme.textSecondary;
    final chargingText = charging == true ? 'Wird geladen'
        : charging == false ? 'Lädt derzeit nicht' : 'Ladestatus nicht verfügbar';
    final chargingColor = charging == true
        ? AppTheme.accentGreen
        : charging == false ? AppTheme.textSecondary : AppTheme.warning;

    return Card(
      clipBehavior: Clip.antiAlias,
      margin: const EdgeInsets.only(top: 4, bottom: 18),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(28),
        side: const BorderSide(color: AppTheme.border),
      ),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.fromLTRB(20, 19, 20, 18),
        decoration: const BoxDecoration(
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
                  child: const Icon(Icons.electric_car_outlined,
                    color: AppTheme.accentTeal, size: 21),
                ),
                const SizedBox(width: 11),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('FAHRZEUGSTATUS',
                        style: TextStyle(fontSize: 11, letterSpacing: 1.5,
                          color: AppTheme.textSecondary, fontWeight: FontWeight.w700)),
                      const SizedBox(height: 3),
                      Text(vehicleName == null || vehicleName.isEmpty
                          ? 'Dein Ladecockpit' : vehicleName,
                        maxLines: 1, overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                    ],
                  ),
                ),
                if (charging == true)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
                    decoration: BoxDecoration(
                      color: AppTheme.accentGreen.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: AppTheme.accentGreen.withValues(alpha: 0.25)),
                    ),
                    child: const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.bolt, color: AppTheme.accentGreen, size: 15),
                        SizedBox(width: 4),
                        Text('LÄDT', style: TextStyle(fontSize: 10,
                          letterSpacing: 0.8, color: AppTheme.accentGreen,
                          fontWeight: FontWeight.w800)),
                      ],
                    ),
                  ),
              ],
            ),
            if (vehicleImage != null && vehicleImage.isNotEmpty) ...[
              const SizedBox(height: 12),
              SizedBox(
                height: 104,
                width: double.infinity,
                child: Image.network(
                  vehicleImage,
                  fit: BoxFit.contain,
                  alignment: Alignment.center,
                  errorBuilder: (context, error, stackTrace) => const SizedBox.shrink(),
                ),
              ),
            ],
            if (vehicleDetails.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(vehicleDetails.join('  ·  '),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: AppTheme.textSecondary, fontSize: 11)),
            ],
            const SizedBox(height: 22),
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                SizedBox(
                  width: 132,
                  height: 132,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      SizedBox.expand(
                        child: CircularProgressIndicator(
                          value: level,
                          strokeWidth: 10,
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
                            style: const TextStyle(fontSize: 34,
                              height: 1.0, fontWeight: FontWeight.w800,
                              letterSpacing: -1.2)),
                          const SizedBox(height: 5),
                          const Text('BATTERIE',
                            style: TextStyle(fontSize: 9, letterSpacing: 1.2,
                              color: AppTheme.textSecondary, fontWeight: FontWeight.w700)),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 22),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('REICHWEITE',
                        style: TextStyle(fontSize: 10, letterSpacing: 1.3,
                          color: AppTheme.textSecondary, fontWeight: FontWeight.w700)),
                      const SizedBox(height: 5),
                      Text(range == null ? '–' : '$range km',
                        maxLines: 1, softWrap: false,
                        style: const TextStyle(fontSize: 30,
                          fontWeight: FontWeight.w800, letterSpacing: -1.0)),
                      if (target != null) ...[
                        const SizedBox(height: 8),
                        Text('Ladelimit $target %',
                          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                      ],
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 20),
            Container(height: 1, color: AppTheme.border),
            const SizedBox(height: 13),
            Row(
              children: [
                Icon(
                  charging == true ? Icons.ev_station_rounded : Icons.power_rounded,
                  color: chargingColor, size: 19),
                const SizedBox(width: 9),
                Expanded(
                  child: Text(chargingText,
                    style: TextStyle(color: chargingColor,
                      fontWeight: FontWeight.w700, fontSize: 13)),
                ),
                if (power != null)
                  Text('${power.toStringAsFixed(1)} kW',
                    style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 14)),
              ],
            ),
            if (soc != null) ...[
              const SizedBox(height: 11),
              Row(
                children: [
                  Icon(socSource == 'last' ? Icons.history_rounded : Icons.sensors_rounded,
                    size: 14, color: readingColor),
                  const SizedBox(width: 6),
                  Expanded(child: Text(readingLabel,
                    style: TextStyle(fontSize: 10, letterSpacing: 0.8,
                      color: readingColor, fontWeight: FontWeight.w700))),
                  if (asOf != null)
                    Text(_dateTimeLabel(asOf),
                      style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary)),
                ],
              ),
            ],
            if (charging == true && (rate != null || finish is String)) ...[
              const SizedBox(height: 12),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                decoration: BoxDecoration(
                  color: AppTheme.accentGreen.withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(14),
                  border: Border.all(color: AppTheme.accentGreen.withValues(alpha: 0.18)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.timelapse_rounded,
                      color: AppTheme.accentGreen, size: 19),
                    const SizedBox(width: 9),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (finish is String)
                            Text('Voraussichtlich fertig · ${_dateTimeLabel(finish)}',
                              style: const TextStyle(fontSize: 12,
                                fontWeight: FontWeight.w700, color: AppTheme.textPrimary)),
                          if (rate != null) ...[
                            if (finish is String) const SizedBox(height: 3),
                            Text('Ladegeschwindigkeit · ${rate.toStringAsFixed(1)} % pro Stunde',
                              style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
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
        ? 'Keine Fahrzeugdaten'
        : socSource == 'live' ? 'Fahrzeugdaten live' : 'Letzter Stand';
    final vehicleDataColor = !hasVehicleReading
        ? AppTheme.textSecondary
        : socSource == 'live' ? AppTheme.accentGreen : AppTheme.warning;
    final vehicleDataTime = vehicleStatus['as_of']?.toString();
    final hasTeslaError = teslaError != null && teslaError.isNotEmpty;
    final hasSyncError = syncError != null && syncError.isNotEmpty;

    final teslaLabel = !teslaConfigured
        ? 'Nicht eingerichtet'
        : teslaConnected ? 'Verbunden' : 'Nicht verbunden';
    final teslaColor = teslaConnected ? AppTheme.accentGreen : AppTheme.warning;
    final haLabel = !haConfigured
        ? 'Nicht eingerichtet (optional)'
        : haOk ? 'Verbunden' : 'Nicht erreichbar';
    final haColor = !haConfigured || haOk ? AppTheme.accentGreen : AppTheme.warning;
    final hasProblem = !teslaConnected || (haConfigured && !haOk) ||
        hasTeslaError || hasSyncError;
    final summaryColor = hasProblem ? AppTheme.warning : AppTheme.accentGreen;
    final summaryLabel = hasProblem ? 'Verbindung prüfen' : 'Alles verbunden';

    return Card(
      margin: const EdgeInsets.only(bottom: 14),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          initiallyExpanded: false,
          tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
          leading: Icon(
            hasProblem ? Icons.cloud_off_outlined : Icons.cloud_done_outlined,
            color: summaryColor,
          ),
          title: const Text('Verbindungen',
            style: TextStyle(fontWeight: FontWeight.w700)),
          subtitle: Row(
            children: [
              Container(width: 7, height: 7, decoration: BoxDecoration(
                color: summaryColor, shape: BoxShape.circle)),
              const SizedBox(width: 7),
              Expanded(child: Text(summaryLabel,
                style: TextStyle(color: summaryColor, fontSize: 12))),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
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
                  'Tesla', teslaLabel, color: teslaColor)),
                IconButton(
                  tooltip: 'Status aktualisieren',
                  visualDensity: VisualDensity.compact,
                  onPressed: _loading ? null : _load,
                  icon: const Icon(Icons.refresh, size: 19),
                ),
              ],
            ),
            _statusLine(
              socSource == 'live' ? Icons.sensors_rounded :
                hasVehicleReading ? Icons.history_rounded : Icons.info_outline,
              'Fahrzeugdaten', vehicleDataLabel, color: vehicleDataColor),
            if (hasVehicleReading && vehicleDataTime != null)
              _statusLine(Icons.schedule, 'Datenstand', _dateTimeLabel(vehicleDataTime)),
            if (hasTeslaError)
              Padding(
                padding: const EdgeInsets.only(left: 28, bottom: 5),
                child: Text(teslaError,
                  style: const TextStyle(color: AppTheme.warning, fontSize: 12)),
              ),
            _statusLine(
              !haConfigured || haOk ? Icons.home_outlined : Icons.warning_amber_rounded,
              'Home Assistant', haLabel, color: haColor),
            if (haConfigured && !haOk && haError != null && haError.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(left: 28, bottom: 5),
                child: Text(haError,
                  style: const TextStyle(color: AppTheme.warning, fontSize: 12)),
              ),
            const Divider(height: 18),
            _statusLine(Icons.history, 'Letzte Synchronisation', _dateTimeLabel(sync['last'])),
            _statusLine(Icons.download_done,
              'Letzter erfolgreicher App-Abruf', _fetchTimeLabel(_lastSuccessfulFetch)),
            if (sync['next'] != null)
              _statusLine(Icons.schedule, 'Nächste Synchronisation', _dateTimeLabel(sync['next'])),
            if (hasSyncError)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.error_outline, color: AppTheme.warning, size: 18),
                    const SizedBox(width: 8),
                    Expanded(child: Text(syncError,
                      style: const TextStyle(color: AppTheme.warning, fontSize: 12))),
                  ],
                ),
              ),
            if (!hasSyncError && problem != null && problem.isNotEmpty && problem != 'None')
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text('Hinweis: $problem',
                  style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12)),
              ),
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
    final overviewMetrics = <Widget>[
      if (month?['sessions'] != null || month?['count'] != null)
        _metric('Ladevorgänge diesen Monat',
          month?['sessions'] ?? month?['count']),
      if (month?['total_cost'] != null || month?['cost'] != null)
        _metric('Gesamtkosten diesen Monat',
          month?['total_cost'] ?? month?['cost'], suffix: ' €'),
      if (month?['kwh'] != null)
        _metric('Unterwegs geladen', month?['kwh'], suffix: ' kWh'),
      if (month?['avg_price'] != null)
        _metric('Ø Preis unterwegs', month?['avg_price'], suffix: ' €/kWh'),
    ];
    const tabTitles = ['Cockpit', 'Ladevorgänge', 'Auswertungen'];

    return Scaffold(
      appBar: AppBar(
        title: Text(tabTitles[_selectedTab],
          style: const TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(onPressed: _load, tooltip: 'Aktualisieren',
            icon: const Icon(Icons.refresh)),
          IconButton(onPressed: _settings, tooltip: 'Verbindung',
            icon: const Icon(Icons.settings_outlined)),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          key: PageStorageKey('ladecockpit-tab-$_selectedTab'),
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
          children: [
            if (_loading) const LinearProgressIndicator(),
            if (_error != null) Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Icon(Icons.cloud_off, color: AppTheme.warning),
                  const SizedBox(height: 8),
                  Text(_error!),
                  const SizedBox(height: 8),
                  Wrap(spacing: 8, runSpacing: 8, children: [
                    FilledButton.icon(
                      onPressed: _loading ? null : _load,
                      icon: const Icon(Icons.refresh),
                      label: const Text('Erneut versuchen'),
                    ),
                    OutlinedButton(onPressed: _settings,
                      child: const Text('Verbindung einrichten')),
                  ]),
                ]),
              ),
            ),
            if (_data != null && _selectedTab == 0) ...[
              _vehicleHero(_map(_data?['status']), _map(_data?['car'])),
              _connectionStatus(),
              Row(
                children: [
                  Expanded(child: Text('DIESER MONAT',
                    style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      color: AppTheme.textSecondary, letterSpacing: 1.4))),
                  Text('${overviewMetrics.length} Kennzahlen',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: AppTheme.textSecondary)),
                ],
              ),
              const SizedBox(height: 8),
              if (overviewMetrics.isNotEmpty)
                GridView.count(
                  crossAxisCount: 2,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  crossAxisSpacing: 9,
                  mainAxisSpacing: 9,
                  childAspectRatio: 1.85,
                  children: overviewMetrics,
                )
              else
                const Card(
                  child: Padding(
                    padding: EdgeInsets.all(14),
                    child: Text('Für diesen Monat liegen noch keine Kennzahlen vor.',
                      style: TextStyle(color: AppTheme.textSecondary)),
                  ),
                ),
              _homeChargingSummary(_map(month?['home'])),
              _section('Letzter Ladevorgang', last),
              _section('Gesamt', totals),
              _section('Ladeprognose', forecast),
              _section('Fahrzeug', _map(_data?['car'])),
              const SizedBox(height: 12),
              Text('Daten werden direkt von deinem Ladecockpit über Tailscale abgerufen.',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: AppTheme.textSecondary)),
            ],
            if (_data != null && _selectedTab == 1)
              _sessions(_data?['sessions']),
            if (_data != null && _selectedTab == 2) ...[
              _priceRadar(_data?['slots'], _data?['sites']),
              _costDevelopment(_data?['monthly']),
              _exports(_data?['monthly']),
            ],
            if (_data == null && !_loading && _error == null)
              const Center(child: Padding(
                padding: EdgeInsets.all(32),
                child: Text('Noch keine Daten vorhanden.'))),
          ],
        ),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedTab,
        onDestinationSelected: (index) => setState(() => _selectedTab = index),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.directions_car_outlined),
            selectedIcon: Icon(Icons.directions_car),
            label: 'Cockpit',
          ),
          NavigationDestination(
            icon: Icon(Icons.ev_station_outlined),
            selectedIcon: Icon(Icons.ev_station),
            label: 'Ladevorgänge',
          ),
          NavigationDestination(
            icon: Icon(Icons.insights_outlined),
            selectedIcon: Icon(Icons.insights),
            label: 'Auswertung',
          ),
        ],
      ),
    );
  }
}
