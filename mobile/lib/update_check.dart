import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

/// Version of this build. Release builds get it from the release tag
/// (`--dart-define=LADECOCKPIT_VERSION=0.12.8`); test builds have none and
/// never look for updates.
const appVersion = String.fromEnvironment('LADECOCKPIT_VERSION');

const _latestReleaseUrl = 'https://api.github.com/repos/uekala/ladecockpit/releases/latest';

class UpdateInfo {
  const UpdateInfo({required this.version, required this.downloadUrl, required this.pageUrl});

  final String version;

  /// Direct link to the APK, or the release page when the release has no APK.
  final String downloadUrl;
  final String pageUrl;
}

/// Parses "0.12.7" or "v0.12.7" into numbers; null for anything else.
List<int>? parseVersion(String value) {
  final match = RegExp(r'^v?(\d+)\.(\d+)\.(\d+)$').firstMatch(value.trim());
  if (match == null) return null;
  return [for (var i = 1; i <= 3; i++) int.parse(match.group(i)!)];
}

/// True when [candidate] is a higher version than [current].
bool isNewerVersion(String candidate, String current) {
  final a = parseVersion(candidate);
  final b = parseVersion(current);
  if (a == null || b == null) return false;
  for (var i = 0; i < 3; i++) {
    if (a[i] != b[i]) return a[i] > b[i];
  }
  return false;
}

/// Asks GitHub once per app start whether a newer release exists.
/// Only the public release information is fetched; nothing about the user,
/// the car or the charging data leaves the phone.
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

  /// Update checks only make sense for release builds on Android:
  /// iOS has no APK, and test builds carry no version.
  bool get supported => _isAndroid && parseVersion(_current) != null;

  Future<bool> get enabled async => (await _storage.read(key: _enabledKey)) != 'off';

  Future<void> setEnabled(bool value) =>
      _storage.write(key: _enabledKey, value: value ? 'on' : 'off');

  /// Returns the newer release, or null when there is none, the check is
  /// switched off or not supported, or GitHub cannot be reached.
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

/// Picks the update out of GitHub's "latest release" answer.
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
