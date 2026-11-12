import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

class CachedDashboard {
  const CachedDashboard(this.data, this.fetchedAt);

  final Map<String, dynamic> data;
  final DateTime fetchedAt;
}

/// Keeps the last dashboard on the phone, so the app can show the latest
/// known figures when the server cannot be reached (VPN off, no network).
/// The file lives in the app's private storage. Every failure is silent:
/// without a cache the app simply shows what it shows today.
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
