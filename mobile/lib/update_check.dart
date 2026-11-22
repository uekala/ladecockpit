import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

/// Version dieses Builds. Release-Builds bekommen sie aus dem Release-Tag
/// (`--dart-define=LADECOCKPIT_VERSION=0.12.8`); Test-Builds haben keine und
/// suchen nie nach Updates.
const appVersion = String.fromEnvironment('LADECOCKPIT_VERSION');

const _latestReleaseUrl = 'https://api.github.com/repos/uekala/ladecockpit/releases/latest';

class UpdateInfo {
  const UpdateInfo({required this.version, required this.downloadUrl, required this.pageUrl});

  final String version;

  /// Direkter Link zur APK oder die Release-Seite, wenn das Release keine APK hat.
  final String downloadUrl;
  final String pageUrl;
}

/// Zerlegt "0.12.7" oder "v0.12.7" in Zahlen; null für alles andere.
List<int>? parseVersion(String value) {
  final match = RegExp(r'^v?(\d+)\.(\d+)\.(\d+)$').firstMatch(value.trim());
  if (match == null) return null;
  return [for (var i = 1; i <= 3; i++) int.parse(match.group(i)!)];
}

/// True, wenn [candidate] eine höhere Version als [current] ist.
bool isNewerVersion(String candidate, String current) {
  final a = parseVersion(candidate);
  final b = parseVersion(current);
  if (a == null || b == null) return false;
  for (var i = 0; i < 3; i++) {
    if (a[i] != b[i]) return a[i] > b[i];
  }
  return false;
}

/// Fragt GitHub einmal pro App-Start, ob es ein neueres Release gibt.
/// Abgerufen werden nur die öffentlichen Release-Informationen; nichts über den Nutzer,
/// das Auto oder die Ladedaten verlässt das Handy.
class UpdateChecker {
  UpdateChecker({
    http.Client? httpClient,
    FlutterSecureStorage storage = const FlutterSecureStorage(),
    String? currentVersion,
    bool? isAndroid,
  })  : _http = httpClient ?? http.Client(),
        _storage = storage,
        _current = currentVersion ?? appVersion,
        _isAndroid = isAndroid ?? Platform.isAndroid;

  static const _enabledKey = 'update_check';

  final http.Client _http;
  final FlutterSecureStorage _storage;
  final String _current;
  final bool _isAndroid;

  /// Update-Prüfungen ergeben nur für Release-Builds auf Android Sinn:
  /// iOS hat keine APK, und Test-Builds tragen keine Version.
  bool get supported => _isAndroid && parseVersion(_current) != null;

  Future<bool> get enabled async => (await _storage.read(key: _enabledKey)) != 'off';

  Future<void> setEnabled(bool value) =>
      _storage.write(key: _enabledKey, value: value ? 'on' : 'off');

  /// Gibt das neuere Release zurück, oder null, wenn es keines gibt, die Prüfung
  /// abgeschaltet oder nicht unterstützt ist oder GitHub nicht erreichbar ist.
  Future<UpdateInfo?> check() async {
    if (!supported || !await enabled) return null;
    try {
      final response = await _http.get(
        Uri.parse(_latestReleaseUrl),
        headers: {'Accept': 'application/vnd.github+json', 'User-Agent': 'Ladecockpit-App'},
      ).timeout(const Duration(seconds: 10));
      if (response.statusCode != 200) return null;
      return updateFromRelease(jsonDecode(response.body), _current);
    } catch (_) {
      return null;
    }
  }
}

/// Sucht das Update aus GitHubs Antwort „latest release“ heraus.
UpdateInfo? updateFromRelease(dynamic release, String currentVersion) {
  if (release is! Map) return null;
  final tag = release['tag_name'];
  final page = release['html_url'];
  if (tag is! String || page is! String) return null;
  if (release['draft'] == true || release['prerelease'] == true) return null;
  if (!isNewerVersion(tag, currentVersion)) return null;
  final version = tag.startsWith('v') ? tag.substring(1) : tag;
  var download = page;
  final assets = release['assets'];
  if (assets is List) {
    for (final asset in assets) {
      if (asset is Map &&
          asset['name'] is String &&
          RegExp(r'^ladecockpit-.*\.apk$').hasMatch(asset['name'] as String) &&
          asset['browser_download_url'] is String) {
        download = asset['browser_download_url'] as String;
        break;
      }
    }
  }
  return UpdateInfo(version: version, downloadUrl: download, pageUrl: page);
}
