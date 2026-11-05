import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
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

  Future<Map<String, dynamic>> dashboard() async {
    final base = await serverUrl;
    if (base == null || base.isEmpty) {
      throw const CockpitException('Bitte zuerst die Serveradresse einrichten.');
    }
    final secret = await password ?? '';
    final headers = <String, String>{'Accept': 'application/json'};
    if (secret.isNotEmpty) {
      headers['Authorization'] = 'Basic ${base64Encode(utf8.encode('ladecockpit:$secret'))}';
    }
    final response = await http.get(Uri.parse('$base/api/dashboard'), headers: headers)
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
                hintText: 'http://100.x.y.z:8000',
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
