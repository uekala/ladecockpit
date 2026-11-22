import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

class CachedDashboard {
  const CachedDashboard(this.data, this.fetchedAt);

  final Map<String, dynamic> data;
  final DateTime fetchedAt;
}

/// Behält das letzte Dashboard auf dem Handy, damit die App die zuletzt
/// bekannten Zahlen zeigen kann, wenn der Server nicht erreichbar ist (VPN aus, kein Netz).
/// Die Datei liegt im privaten Speicher der App. Jeder Fehler bleibt still:
/// Ohne Cache zeigt die App einfach, was sie auch heute zeigt.
class DashboardCache {
  DashboardCache({Future<Directory> Function()? directory})
      : _directory = directory ?? getApplicationSupportDirectory;

  final Future<Directory> Function() _directory;

  Future<File> _file() async => File('${(await _directory()).path}/dashboard.json');

  Future<void> write(Map<String, dynamic> data, DateTime fetchedAt) async {
    try {
      final file = await _file();
      final tmp = File('${file.path}.tmp');
      await tmp.writeAsString(
        jsonEncode({'fetched_at': fetchedAt.toUtc().toIso8601String(), 'data': data}),
        flush: true,
      );
      await tmp.rename(file.path);
    } catch (_) {
      // No cache this time.
    }
  }

  Future<CachedDashboard?> read() async {
    try {
      final file = await _file();
      if (!await file.exists()) return null;
      final decoded = jsonDecode(await file.readAsString());
      if (decoded is! Map<String, dynamic>) return null;
      final data = decoded['data'];
      final fetchedAt = DateTime.tryParse(decoded['fetched_at']?.toString() ?? '');
      if (data is! Map<String, dynamic> || fetchedAt == null) return null;
      return CachedDashboard(data, fetchedAt);
    } catch (_) {
      return null;
    }
  }

  Future<void> clear() async {
    try {
      final file = await _file();
      if (await file.exists()) await file.delete();
    } catch (_) {
      // Nothing to clear.
    }
  }
}
