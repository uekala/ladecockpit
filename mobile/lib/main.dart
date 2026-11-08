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

void main() => runApp(const LadecockpitApp());

class LadecockpitApp extends StatelessWidget {
  const LadecockpitApp({super.key});

  @override
  Widget build(BuildContext context) {
    const seed = Color(0xFF43C6AC);
    return MaterialApp(
      title: 'Ladecockpit',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: seed, brightness: Brightness.dark),
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFF101416),
        cardTheme: CardThemeData(
          color: const Color(0xFF1A2224),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        ),
      ),
      home: const DashboardPage(),
    );
  }
}

class CockpitClient {
  static const _storage = FlutterSecureStorage();
  static const _urlKey = 'server_url';
  static const _passwordKey = 'app_password';

  Future<String?> get serverUrl => _storage.read(key: _urlKey);
  Future<String?> get password => _storage.read(key: _passwordKey);

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
    final response = await http.get(uri, headers: await _headers(json: true))
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
    final response = await http.get(uri, headers: await _headers())
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
    final response = await http.get(uri, headers: await _headers())
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
    final response = await http.get(uri, headers: await _headers(json: true))
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
    final response = await http.get(uri, headers: headers)
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
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title, style: Theme.of(context).textTheme.labelMedium?.copyWith(color: Colors.white60)),
          const SizedBox(height: 8),
          Text('$text$suffix', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700)),
        ]),
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
      if (distanceKeys.contains(key)) return '$number km';
      if (key == 'avg_kw') return '$number kW';
      if (key == 'rate_pct_day') return '$number %/Tag';
      if (key == 'dist_day') return '$number km/Tag';
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
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(4, 18, 4, 4),
        child: Text(title, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
      ),
      Card(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: Column(children: [
            for (var i = 0; i < entries.length; i++) ...[
              if (i > 0) const Divider(height: 1),
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 9),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Expanded(child: Text(_sectionLabel(entries[i].key),
                    style: const TextStyle(color: Colors.white70))),
                  const SizedBox(width: 12),
                  Flexible(child: Text(_sectionValue(entries[i].key, entries[i].value),
                    textAlign: TextAlign.end,
                    style: const TextStyle(fontWeight: FontWeight.w600))),
                ]),
              ),
            ],
          ]),
        ),
      ),
    ]);
  }

  Map<String, dynamic>? _map(dynamic value) =>
      value is Map<String, dynamic> ? value : null;

  Widget _sessionMetric(String label, String value, IconData icon) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 16, color: Colors.white54),
        const SizedBox(width: 6),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: Theme.of(context).textTheme.labelSmall?.copyWith(color: Colors.white54)),
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
                style: Theme.of(context).textTheme.labelMedium?.copyWith(color: Colors.white60)),
            ],
          ),
        ),
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
        if (_sessionMonthFilter != 'all' || _sessionNetworkFilter != 'all' || _sessionSiteFilter != 'all')
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
                padding: const EdgeInsets.fromLTRB(16, 13, 16, 14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Icon(
                        invoice ? Icons.receipt_long_outlined : Icons.ev_station,
                        color: invoice ? Theme.of(context).colorScheme.primary : Colors.white60,
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
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.white60),
                            ),
                          ],
                        ),
                      ),
                      const Icon(Icons.chevron_right, color: Colors.white38),
                    ]),
                    if (metrics.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      const Divider(height: 1),
                      const SizedBox(height: 10),
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
              style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.white54)),
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
        Expanded(child: Text(label, style: const TextStyle(color: Colors.white60))),
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
      builder: (dialogContext) => AlertDialog(
        title: Text(site, maxLines: 2, overflow: TextOverflow.ellipsis),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Icon(Icons.ev_station, size: 18,
                  color: Theme.of(context).colorScheme.primary),
                const SizedBox(width: 8),
                Expanded(child: Text(network,
                  style: TextStyle(color: Theme.of(context).colorScheme.primary))),
              ]),
              _detailGroup('ZEITRAUM', timingRows),
              _detailGroup('ENERGIE UND KOSTEN', costRows),
              _detailGroup('STANDORT', locationRows),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Schließen'),
          ),
          if (invoice && sessionId != null)
            FilledButton.icon(
              onPressed: () {
                Navigator.pop(dialogContext);
                _showInvoice(sessionId, site);
              },
              icon: const Icon(Icons.receipt_long),
              label: const Text('Rechnung öffnen'),
            ),
        ],
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

    Widget priceValue(dynamic value) =>
        Text(value is num ? '${value.toStringAsFixed(3)} €/kWh' : 'Noch keine Daten',
          style: const TextStyle(fontWeight: FontWeight.w600));

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
            child: Text('Tarif nach Ladezeit', style: TextStyle(color: Colors.white70)),
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
                  color: isCheapest ? Colors.greenAccent : Colors.white60),
                title: Text('$label${isCheapest ? ' · Günstigste Zeit' : ''}'),
                subtitle: Text('${range.isEmpty ? 'Zeitfenster' : range} · $count Ladevorgänge'),
                trailing: priceValue(slot['avg_price']),
              ),
            );
          }),
        ],
        if (sites.isNotEmpty) ...[
          const Padding(
            padding: EdgeInsets.fromLTRB(4, 14, 4, 6),
            child: Text('Deine häufigsten Ladestandorte',
              style: TextStyle(color: Colors.white70)),
          ),
          ...sites.map((site) {
            final label = site['label']?.toString() ??
                site['site']?.toString() ?? 'Unbekannter Standort';
            final network = site['network'] == 'multipass' ? 'MultiPass' : 'Supercharger';
            final count = site['sessions'] is num ? (site['sessions'] as num).round() : 0;
            final kwh = _numberLabel(site['kwh'], digits: 1, suffix: ' kWh');
            final address = site['address']?.toString();
            final isCheapest = site['avg_price'] is num &&
                lowestSitePrice != null && site['avg_price'] == lowestSitePrice;
            return Card(
              child: ListTile(
                leading: Icon(isCheapest ? Icons.savings_outlined : Icons.ev_station,
                  color: isCheapest ? Colors.greenAccent : Colors.white60),
                title: Text('$label${isCheapest ? ' · Günstigster' : ''}',
                  maxLines: 2, overflow: TextOverflow.ellipsis),
                subtitle: Text('$network · $count Ladevorgänge · $kwh'
                  '${address != null && address.isNotEmpty ? '\n$address' : ''}'),
                isThreeLine: address != null && address.isNotEmpty,
                trailing: priceValue(site['avg_price']),
              ),
            );
          }),
        ],
        const Padding(
          padding: EdgeInsets.fromLTRB(4, 4, 4, 0),
          child: Text('Preiswerte basieren auf den erfassten Rechnungsdaten und sind keine Live-Tarife.',
            style: TextStyle(color: Colors.white54, fontSize: 12)),
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
            body: ListView.builder(
              itemCount: pages,
              itemBuilder: (context, index) => Padding(
                padding: const EdgeInsets.all(8),
                child: FutureBuilder<Uri>(
                  future: _client.monthReportPageUri(month, index + 1),
                  builder: (context, snapshot) {
                    if (!snapshot.hasData) {
                      return SizedBox(
                        height: 240,
                        child: Center(child: snapshot.hasError
                          ? const Text('Seite konnte nicht geladen werden.')
                          : const CircularProgressIndicator()),
                      );
                    }
                    return Image.network(snapshot.data.toString(), headers: headers,
                      fit: BoxFit.contain,
                      errorBuilder: (_, __, ___) => const Padding(
                        padding: EdgeInsets.all(24),
                        child: Text('Seite konnte nicht geladen werden.'),
                      ));
                  },
                ),
              ),
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
      Text(label, style: const TextStyle(color: Colors.white70, fontSize: 11)),
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

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 22, 4, 8),
          child: Text('Kostenentwicklung',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
        ),
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
                  final energy = publicEnergy + homeEnergy;
                  final hasHomeEnergy = homeEnergyKnown && homeEnergy > 0;
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
                    if (currentOrdinal != null && previousOrdinal != null &&
                        currentOrdinal - previousOrdinal == 1) {
                      final previousTotal = totalCost(previous);
                      if (previousTotal > 0) {
                        final difference = total - previousTotal;
                        final percentage = difference / previousTotal * 100;
                        final sign = difference > 0 ? '+' : '';
                        comparison = '$sign${difference.toStringAsFixed(2)} € ($sign${percentage.toStringAsFixed(1)} %) gegenüber Vormonat';
                        comparisonColor = difference > 0 ? Colors.orangeAccent :
                            difference < 0 ? Colors.greenAccent : Colors.white54;
                      } else {
                        comparison = 'Vormonat ohne erfasste Kosten – kein Prozentvergleich';
                        comparisonColor = Colors.white54;
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
                              style: const TextStyle(color: Colors.white70))),
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
                                      Expanded(child: Container(color: Colors.white12)),
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
                        Padding(
                          padding: const EdgeInsets.only(left: 54, top: 3),
                          child: Text(
                            '${(publicEnergy + (homeEnergyKnown ? homeEnergy : 0)).toStringAsFixed(1)} kWh erfasst · ${amount(month['sessions']).round()} öffentliche Ladevorgänge'
                            '\nÖffentlich: ${publicCost.toStringAsFixed(2)} € · Zuhause: $homeCostLabel'
                            '\nEnergie: öffentlich ${publicEnergy.toStringAsFixed(1)} kWh · zuhause ${homeEnergyKnown ? homeEnergy.toStringAsFixed(1) + ' kWh' : 'nicht erfasst'}',
                            style: const TextStyle(color: Colors.white54, fontSize: 11)),
                        ),
                        if (comparison != null)
                          Padding(
                            padding: const EdgeInsets.only(left: 54, top: 3),
                            child: Text(comparison, style: TextStyle(color: comparisonColor, fontSize: 11)),
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
                    style: TextStyle(color: Colors.white54, fontSize: 11))),
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
            leading: const Icon(Icons.table_chart_outlined),
            title: const Text('Alle Ladevorgänge als CSV'),
            subtitle: const Text('Excel-kompatibler Export der gesamten Ladehistorie'),
            trailing: const Icon(Icons.copy),
            onTap: _showCsvExport,
          ),
        ),
        ...months.map((month) {
          final key = month['key'].toString();
          final count = month['sessions'] is num ? (month['sessions'] as num).round() : 0;
          final energy = _numberLabel(month['kwh'], digits: 1, suffix: ' kWh');
          return Card(
            child: ListTile(
              leading: const Icon(Icons.picture_as_pdf_outlined),
              title: Text(key),
              subtitle: Text('$count Ladevorgänge · $energy'),
              trailing: Wrap(
                spacing: 0,
                children: [
                  IconButton(
                    tooltip: 'Rechnungen als ZIP teilen',
                    onPressed: () => _shareInvoiceZip(key),
                    icon: const Icon(Icons.folder_zip_outlined),
                  ),
                  IconButton(
                    tooltip: 'Monatsbericht ansehen',
                    onPressed: () => _showMonthlyReport(key),
                    icon: const Icon(Icons.picture_as_pdf_outlined),
                  ),
                ],
              ),
              onTap: () => _showMonthlyReport(key),
            ),
          );
        }),
        const Padding(
          padding: EdgeInsets.fromLTRB(4, 4, 4, 0),
          child: Text('Monatsberichte enthalten die Kostenübersicht und vorhandene Rechnungen.',
            style: TextStyle(color: Colors.white54, fontSize: 12)),
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
            body: ListView.builder(
              itemCount: pages,
              itemBuilder: (context, index) => Padding(
                padding: const EdgeInsets.all(8),
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
          Icon(icon, size: 18, color: color ?? Colors.white70),
          const SizedBox(width: 10),
          Expanded(child: Text(label, style: const TextStyle(color: Colors.white70))),
          Flexible(child: Text(value, textAlign: TextAlign.end,
            style: TextStyle(fontWeight: FontWeight.w600, color: color))),
        ],
      ),
    );
  }

  Widget _vehicleHero(Map<String, dynamic>? status) {
    final data = status ?? {};
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
        ? 'Letzter bekannter Akkustand'
        : socSource == 'live' ? 'Live-Akkustand' : 'Akkustand';
    final readingColor = socSource == 'last'
        ? Colors.orangeAccent
        : socSource == 'live' ? Colors.greenAccent : Colors.white70;
    final chargingText = charging == true ? 'Wird geladen'
        : charging == false ? 'Lädt derzeit nicht' : 'Ladestatus nicht verfügbar';
    final chargingColor = charging == true ? Colors.greenAccent
        : charging == false ? Colors.white70 : Colors.orangeAccent;

    return Card(
      clipBehavior: Clip.antiAlias,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(18),
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft, end: Alignment.bottomRight,
            colors: [Color(0xFF203B39), Color(0xFF172326)],
          ),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.directions_car_filled_outlined, color: Colors.white70),
            const SizedBox(width: 8),
            const Expanded(child: Text('FAHRZEUGSTATUS',
              style: TextStyle(fontSize: 12, letterSpacing: 1.3, color: Colors.white70))),
            if (charging == true) const Icon(Icons.bolt, color: Colors.greenAccent),
          ]),
          if (soc != null) ...[
            const SizedBox(height: 7),
            Row(children: [
              Icon(socSource == 'last' ? Icons.history : Icons.sensors,
                size: 14,
                color: readingColor),
              const SizedBox(width: 6),
              Expanded(child: Text(readingLabel,
                style: TextStyle(fontSize: 12,
                  color: readingColor))),
            ]),
            if (asOf != null)
              Padding(
                padding: const EdgeInsets.only(left: 20, top: 2),
                child: Text('Messzeitpunkt: ${_dateTimeLabel(asOf)}',
                  style: const TextStyle(color: Colors.white54, fontSize: 11)),
              ),
          ],
          const SizedBox(height: 18),
          Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
            SizedBox(
              width: 112, height: 112,
              child: Stack(alignment: Alignment.center, children: [
                SizedBox.expand(child: CircularProgressIndicator(
                  value: level,
                  strokeWidth: 9,
                  backgroundColor: Colors.white12,
                  valueColor: AlwaysStoppedAnimation<Color>(
                    soc == null ? Colors.white24 : Colors.greenAccent),
                )),
                Column(mainAxisSize: MainAxisSize.min, children: [
                  Text(soc == null ? '–' : '${soc.round()}%',
                    style: const TextStyle(fontSize: 30, fontWeight: FontWeight.bold)),
                  const Text('Akku', style: TextStyle(fontSize: 12, color: Colors.white70)),
                ]),
              ]),
            ),
            const SizedBox(width: 22),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Reichweite', style: TextStyle(color: Colors.white70)),
              const SizedBox(height: 3),
              Text(range == null ? '–' : '$range km',
                style: const TextStyle(fontSize: 27, fontWeight: FontWeight.bold)),
              if (target != null)
                Text('Ladelimit $target %', style: const TextStyle(color: Colors.white60, fontSize: 12)),
            ])),
          ]),
          const SizedBox(height: 18),
          Container(height: 1, color: Colors.white12),
          const SizedBox(height: 12),
          Row(children: [
            Icon(charging == true ? Icons.ev_station : Icons.power_off,
              color: chargingColor, size: 19),
            const SizedBox(width: 8),
            Expanded(child: Text(chargingText,
              style: TextStyle(color: chargingColor, fontWeight: FontWeight.w600))),
            if (power != null) Text('${power.toStringAsFixed(1)} kW',
              style: const TextStyle(fontWeight: FontWeight.bold)),
          ]),
          if (charging == true && rate != null)
            Padding(padding: const EdgeInsets.only(top: 7),
              child: Text('Ladegeschwindigkeit: ${rate.toStringAsFixed(1)} % pro Stunde',
                style: const TextStyle(color: Colors.white70, fontSize: 12))),
          if (charging == true && finish is String)
            Padding(padding: const EdgeInsets.only(top: 5),
              child: Text('Voraussichtlich fertig: ${_dateTimeLabel(finish)}',
                style: const TextStyle(color: Colors.white70, fontSize: 12))),
        ]),
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
    final hasTeslaError = teslaError != null && teslaError.isNotEmpty;
    final hasSyncError = syncError != null && syncError.isNotEmpty;

    final teslaLabel = !teslaConfigured
        ? 'Nicht eingerichtet'
        : teslaConnected ? 'Verbunden' : 'Nicht verbunden';
    final teslaColor = teslaConnected ? Colors.greenAccent : Colors.orangeAccent;
    final haLabel = !haConfigured
        ? 'Nicht eingerichtet (optional)'
        : haOk ? 'Verbunden' : 'Nicht erreichbar';
    final haColor = !haConfigured || haOk ? Colors.greenAccent : Colors.orangeAccent;

    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 14, 12, 14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.sync, size: 19),
                const SizedBox(width: 8),
                Expanded(child: Text('Verbindung & Synchronisation',
                  style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold))),
                IconButton(
                  tooltip: 'Status aktualisieren',
                  visualDensity: VisualDensity.compact,
                  onPressed: _loading ? null : _load,
                  icon: const Icon(Icons.refresh, size: 20),
                ),
              ],
            ),
            const SizedBox(height: 4),
            _statusLine(teslaConnected ? Icons.check_circle : Icons.cloud_off,
              'Tesla', teslaLabel, color: teslaColor),
            if (hasTeslaError)
              Padding(
                padding: const EdgeInsets.only(left: 28, bottom: 5),
                child: Text(teslaError, style: const TextStyle(color: Colors.orangeAccent, fontSize: 12)),
              ),
            _statusLine(!haConfigured || haOk ? Icons.home_outlined : Icons.warning_amber_rounded,
              'Home Assistant', haLabel, color: haColor),
            if (haConfigured && !haOk && haError != null && haError.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(left: 28, bottom: 5),
                child: Text(haError, style: const TextStyle(color: Colors.orangeAccent, fontSize: 12)),
              ),
            const Divider(height: 18),
            _statusLine(Icons.history, 'Letzte Synchronisation', _dateTimeLabel(sync['last'])),
            _statusLine(Icons.download_done, 'Letzter erfolgreicher App-Abruf', _fetchTimeLabel(_lastSuccessfulFetch)),
            if (sync['next'] != null)
              _statusLine(Icons.schedule, 'Nächste Synchronisation', _dateTimeLabel(sync['next'])),
            if (hasSyncError)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.error_outline, color: Colors.orangeAccent, size: 18),
                    const SizedBox(width: 8),
                    Expanded(child: Text(syncError,
                      style: const TextStyle(color: Colors.orangeAccent, fontSize: 12))),
                  ],
                ),
              ),
            if (!hasSyncError && problem != null && problem.isNotEmpty && problem != 'None')
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text('Hinweis: $problem',
                  style: const TextStyle(color: Colors.white60, fontSize: 12)),
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

    return Scaffold(
      appBar: AppBar(
        title: const Text('Ladecockpit', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(onPressed: _load, tooltip: 'Aktualisieren', icon: const Icon(Icons.refresh)),
          IconButton(onPressed: _settings, tooltip: 'Verbindung', icon: const Icon(Icons.settings_outlined)),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
          children: [
            if (_loading) const LinearProgressIndicator(),
            if (_error != null) Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Icon(Icons.cloud_off, color: Colors.orange),
                  const SizedBox(height: 8),
                  Text(_error!),
                  const SizedBox(height: 8),
                  Wrap(spacing: 8, runSpacing: 8, children: [
                    FilledButton.icon(
                      onPressed: _loading ? null : _load,
                      icon: const Icon(Icons.refresh),
                      label: const Text('Erneut versuchen'),
                    ),
                    OutlinedButton(onPressed: _settings, child: const Text('Verbindung einrichten')),
                  ]),
                ]),
              ),
            ),
            if (_data != null) ...[
              _connectionStatus(),
              _vehicleHero(_map(_data?['status'])),
              Text('ÜBERSICHT', style: Theme.of(context).textTheme.labelLarge?.copyWith(color: Colors.white60, letterSpacing: 1.4)),
              const SizedBox(height: 8),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                childAspectRatio: 1.65,
                children: [
                  _metric('Ladevorgänge diesen Monat', month?['sessions'] ?? month?['count']),
                  _metric('Gesamtkosten diesen Monat', month?['total_cost'] ?? month?['cost'], suffix: ' €'),
                  _metric('Unterwegs geladen', month?['kwh'], suffix: ' kWh'),
                  _metric('Ø Preis unterwegs', month?['avg_price'], suffix: ' €/kWh'),
                  if (_map(month?['home']) != null) ...[
                    _metric('Zu Hause geladen', _map(month?['home'])?['kwh'], suffix: ' kWh'),
                    _metric('Heimladekosten', _map(month?['home'])?['cost'], suffix: ' €'),
                  ],
                ],
              ),
              _section('Letzter Ladevorgang', last),
              _section('Gesamt', totals),
              _section('Ladeprognose', forecast),
              _section('Fahrzeug', _map(_data?['car'])),
              _priceRadar(_data?['slots'], _data?['sites']),
              _sessions(_data?['sessions']),
              _costDevelopment(_data?['monthly']),
              _exports(_data?['monthly']),
              const SizedBox(height: 16),
              Text('Daten werden direkt von deinem Ladecockpit über Tailscale abgerufen.',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.white54)),
            ],
            if (_data == null && !_loading && _error == null)
              const Center(child: Padding(padding: EdgeInsets.all(32), child: Text('Noch keine Daten vorhanden.'))),
          ],
        ),
      ),
    );
  }
}
