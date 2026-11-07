import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:http/http.dart' as http;

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
    final secret = await password ?? '';
    final headers = <String, String>{'Accept': json ? 'application/json' : '*/*'};
    if (secret.isNotEmpty) {
      headers['Authorization'] = 'Basic ${base64Encode(utf8.encode('ladecockpit:$secret'))}';
    }
    return headers;
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
    if (response.statusCode == 401) {
      throw const CockpitException('Anmeldung fehlgeschlagen. Bitte App-Passwort prüfen.');
    }
    if (response.statusCode == 404) {
      throw const CockpitException('Die Rechnung ist auf dem Server noch nicht verfügbar.');
    }
    if (response.statusCode != 200) {
      throw CockpitException('Rechnung konnte nicht geladen werden (HTTP ${response.statusCode}).');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic> || decoded['pages'] is! int) {
      throw const CockpitException('Ungültige Antwort für die Rechnung.');
    }
    return decoded;
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
    if (response.statusCode == 401) {
      throw const CockpitException('Anmeldung fehlgeschlagen. Bitte App-Passwort prüfen.');
    }
    if (response.statusCode != 200) {
      throw CockpitException('Monatsbericht nicht verfügbar (HTTP ${response.statusCode}).');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic> || decoded['pages'] is! int) {
      throw const CockpitException('Ungültige Antwort für den Monatsbericht.');
    }
    return decoded;
  }

  Future<Uri> monthReportPageUri(String month, int page) =>
      _endpoint('/api/report/$month/page/$page.png');

  Future<Map<String, dynamic>> dashboard() async {
    final uri = await _endpoint('/api/dashboard');
    final headers = await _headers(json: true);
    final response = await http.get(uri, headers: headers)
        .timeout(const Duration(seconds: 20));
    if (response.statusCode == 401) {
      throw const CockpitException('Anmeldung fehlgeschlagen. Bitte App-Passwort prüfen.');
    }
    if (response.statusCode != 200) {
      throw CockpitException('Server antwortet mit HTTP ${response.statusCode}.');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is! Map<String, dynamic>) {
      throw const CockpitException('Ungültige Antwort vom Ladecockpit.');
    }
    return decoded;
  }
}

class CockpitException implements Exception {
  const CockpitException(this.message);
  final String message;
  @override
  String toString() => message;
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
  String _sessionMonthFilter = 'all';
  String _sessionNetworkFilter = 'all';
  String _sessionSiteFilter = 'all';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() { _loading = true; _error = null; });
    try {
      final data = await _client.dashboard();
      if (mounted) setState(() => _data = data);
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
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

  Widget _section(String title, Map<String, dynamic>? values) {
    if (values == null || values.isEmpty) return const SizedBox.shrink();
    final entries = values.entries.where((e) => e.value is! Map && e.value is! List).take(6).toList();
    if (entries.isEmpty) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(4, 18, 4, 4),
        child: Text(title, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
      ),
      ...entries.map((e) => Card(
        child: ListTile(
          dense: true,
          title: Text(e.key.replaceAll('_', ' ')),
          trailing: Text(_value(e.value), style: const TextStyle(fontWeight: FontWeight.w600)),
        ),
      )),
    ]);
  }

  Map<String, dynamic>? _map(dynamic value) =>
      value is Map<String, dynamic> ? value : null;

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

    final filtered = items.where((session) {
      final monthMatches = _sessionMonthFilter == 'all' ||
        monthKey(session) == _sessionMonthFilter;
      final networkMatches = _sessionNetworkFilter == 'all' ||
        (session['network']?.toString() ?? 'supercharger') == _sessionNetworkFilter;
      final siteMatches = _sessionSiteFilter == 'all' ||
        (session['site']?.toString() ?? '') == _sessionSiteFilter;
      return monthMatches && networkMatches && siteMatches;
    }).toList();

    Widget filterField(String label, String value, List<DropdownMenuItem<String>> options,
        ValueChanged<String?> onChanged, {double width = 150}) {
      return SizedBox(
        width: width,
        child: DropdownButtonFormField<String>(
          value: value,
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

    // If the data set changes, do not leave a selected filter pointing at a missing option.
    if (_sessionMonthFilter != 'all' && !months.contains(_sessionMonthFilter)) {
      _sessionMonthFilter = 'all';
    }
    if (_sessionNetworkFilter != 'all' && !networks.contains(_sessionNetworkFilter)) {
      _sessionNetworkFilter = 'all';
    }
    if (_sessionSiteFilter != 'all' && !sites.contains(_sessionSiteFilter)) {
      _sessionSiteFilter = 'all';
    }

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
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            filterField('Zeitraum', _sessionMonthFilter, monthOptions,
              (value) => setState(() => _sessionMonthFilter = value ?? 'all'), width: 165),
            filterField('Netzwerk', _sessionNetworkFilter, networkOptions,
              (value) => setState(() => _sessionNetworkFilter = value ?? 'all'), width: 165),
            filterField('Standort', _sessionSiteFilter, siteOptions,
              (value) => setState(() => _sessionSiteFilter = value ?? 'all'), width: 210),
          ],
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
          final kwh = number(session['kwh']);
          final cost = number(session['cost'], digits: 2);
          final currency = session['currency']?.toString() ?? 'EUR';
          final invoice = session['has_invoice'] == true;
          return Card(
            child: ListTile(
              onTap: () => _showSessionDetails(session),
              leading: Icon(
                invoice ? Icons.receipt_long_outlined : Icons.ev_station,
                color: invoice ? Theme.of(context).colorScheme.primary : Colors.white60,
              ),
              title: Text(site, maxLines: 1, overflow: TextOverflow.ellipsis),
              subtitle: Text('${dateLabel(session['start'])} · $network${invoice ? ' · Rechnung öffnen' : ''}'),
              trailing: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text('$kwh kWh', style: const TextStyle(fontWeight: FontWeight.w600)),
                  Text('$cost $currency', style: Theme.of(context).textTheme.bodySmall),
                ],
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

  Future<void> _showSessionDetails(Map<String, dynamic> session) async {
    final site = session['site']?.toString() ?? 'Unbekannter Standort';
    final currency = session['currency']?.toString() ?? 'EUR';
    final network = session['network'] == 'multipass' ? 'MultiPass' : 'Supercharger';
    final invoice = session['has_invoice'] == true;
    final sessionId = session['id']?.toString();

    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(site, maxLines: 2, overflow: TextOverflow.ellipsis),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(network, style: TextStyle(color: Theme.of(context).colorScheme.primary)),
              const SizedBox(height: 12),
              _detailRow('Beginn', _dateTimeLabel(session['start'])),
              _detailRow('Ende', _dateTimeLabel(session['end'])),
              _detailRow('Ladedauer', _durationLabel(session['duration_min'])),
              const Divider(height: 18),
              _detailRow('Geladene Energie', _numberLabel(session['kwh'], suffix: ' kWh')),
              _detailRow('Gesamtkosten', _numberLabel(session['cost'], suffix: ' $currency')),
              _detailRow('Ladekosten', _numberLabel(session['charge_cost'], suffix: ' $currency')),
              _detailRow('Standgebühren', _numberLabel(session['idle'], suffix: ' $currency')),
              _detailRow('Gutschrift', _numberLabel(session['credit'], suffix: ' $currency')),
              _detailRow('Preis pro kWh', _numberLabel(session['price'], digits: 3, suffix: ' $currency/kWh')),
              _detailRow('Durchschnittsleistung', _numberLabel(session['avg_kw'], suffix: ' kW')),
              if (session['start_soc'] != null)
                _detailRow('Start-Ladestand', _numberLabel(session['start_soc'], digits: 0, suffix: ' %')),
              if ((session['operator'] ?? '').toString().isNotEmpty)
                _detailRow('Betreiber', session['operator'].toString()),
              if ((session['address'] ?? '').toString().isNotEmpty)
                _detailRow('Adresse', session['address'].toString()),
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
        ? rawSlots.whereType<Map<String, dynamic>>().toList()
        : <Map<String, dynamic>>[];
    final sites = rawSites is List
        ? rawSites.whereType<Map<String, dynamic>>().take(8).toList()
        : <Map<String, dynamic>>[];
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
            return Card(
              child: ListTile(
                dense: true,
                title: Text(label),
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
            return Card(
              child: ListTile(
                leading: const Icon(Icons.ev_station, color: Colors.white60),
                title: Text(label, maxLines: 2, overflow: TextOverflow.ellipsis),
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
                  OutlinedButton(onPressed: _settings, child: const Text('Verbindung einrichten')),
                ]),
              ),
            ),
            if (_data != null) ...[
              _connectionStatus(),
              Text('ÜBERSICHT', style: Theme.of(context).textTheme.labelLarge?.copyWith(color: Colors.white60, letterSpacing: 1.4)),
              const SizedBox(height: 8),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                childAspectRatio: 1.65,
                children: [
                  _metric('Ladevorgänge diesen Monat', month?['sessions'] ?? month?['count']),
                  _metric('Kosten diesen Monat', month?['cost'], suffix: ' €'),
                  _metric('Geladen diesen Monat', month?['kwh'], suffix: ' kWh'),
                  _metric('Ø Preis', month?['avg_price'], suffix: ' €/kWh'),
                ],
              ),
              _section('Letzter Ladevorgang', last),
              _section('Gesamt', totals),
              _section('Ladeprognose', forecast),
              _section('Fahrzeug', _map(_data?['car'])),
              _priceRadar(_data?['slots'], _data?['sites']),
              _sessions(_data?['sessions']),
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
