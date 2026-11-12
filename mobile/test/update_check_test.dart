import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ladecockpit_mobile/update_check.dart';

Map<String, dynamic> _release(String tag, {List<Map<String, dynamic>> assets = const [], bool prerelease = false}) => {
      'tag_name': tag,
      'html_url': 'https://github.com/uekala/ladecockpit/releases/tag/$tag',
      'draft': false,
      'prerelease': prerelease,
      'assets': assets,
    };

const _apk = {
  'name': 'ladecockpit-0.12.8.apk',
  'browser_download_url': 'https://github.com/uekala/ladecockpit/releases/download/v0.12.8/ladecockpit-0.12.8.apk',
};
const _sha = {
  'name': 'ladecockpit-0.12.8.apk.sha256',
  'browser_download_url': 'https://github.com/uekala/ladecockpit/releases/download/v0.12.8/ladecockpit-0.12.8.apk.sha256',
};

void main() {
  group('version comparison', () {
    test('parses plain and v-prefixed versions', () {
      expect(parseVersion('0.12.7'), [0, 12, 7]);
      expect(parseVersion('v1.2.3'), [1, 2, 3]);
      expect(parseVersion(''), isNull);
      expect(parseVersion('0.12'), isNull);
      expect(parseVersion('0.12.7-beta'), isNull);
    });

    test('compares numerically, not as text', () {
      expect(isNewerVersion('v0.12.10', '0.12.9'), isTrue);
      expect(isNewerVersion('v0.13.0', '0.12.99'), isTrue);
      expect(isNewerVersion('v1.0.0', '0.99.99'), isTrue);
      expect(isNewerVersion('v0.12.7', '0.12.7'), isFalse);
      expect(isNewerVersion('v0.12.6', '0.12.7'), isFalse);
      expect(isNewerVersion('garbage', '0.12.7'), isFalse);
      expect(isNewerVersion('v0.12.8', ''), isFalse);
    });
  });

  group('release parsing', () {
    test('links the APK of a newer release', () {
      final update = updateFromRelease(_release('v0.12.8', assets: [_sha, _apk]), '0.12.7');
      expect(update, isNotNull);
      expect(update!.version, '0.12.8');
      expect(update.downloadUrl, _apk['browser_download_url']);
    });

    test('falls back to the release page without an APK', () {
      final update = updateFromRelease(_release('v0.12.8', assets: [_sha]), '0.12.7');
      expect(update!.downloadUrl, 'https://github.com/uekala/ladecockpit/releases/tag/v0.12.8');
    });

    test('ignores the same, older and pre-releases', () {
      expect(updateFromRelease(_release('v0.12.7', assets: [_apk]), '0.12.7'), isNull);
      expect(updateFromRelease(_release('v0.12.6', assets: [_apk]), '0.12.7'), isNull);
      expect(updateFromRelease(_release('v0.12.8', assets: [_apk], prerelease: true), '0.12.7'), isNull);
      expect(updateFromRelease('nonsense', '0.12.7'), isNull);
    });
  });

  group('checker', () {
    UpdateChecker checker(http.Client client, {String version = '0.12.7', bool android = true}) =>
        _TestChecker(client, version: version, android: android);

    test('reports a newer release', () async {
      var calls = 0;
      final client = MockClient((request) async {
        calls++;
        expect(request.url.toString(), 'https://api.github.com/repos/uekala/ladecockpit/releases/latest');
        return http.Response(jsonEncode(_release('v0.12.8', assets: [_apk])), 200);
      });
      final update = await checker(client).check();
      expect(update?.version, '0.12.8');
      expect(calls, 1);
    });

    test('does not ask GitHub on iOS, in test builds or when switched off', () async {
      final client = MockClient((request) async => fail('GitHub must not be asked'));
      expect(await checker(client, android: false).check(), isNull);
      expect(await checker(client, version: '').check(), isNull);
      final off = checker(client);
      await off.setEnabled(false);
      expect(await off.check(), isNull);
    });

    test('stays quiet when GitHub fails', () async {
      final down = MockClient((request) async => http.Response('rate limited', 403));
      expect(await checker(down).check(), isNull);
      final broken = MockClient((request) async => throw http.ClientException('offline'));
      expect(await checker(broken).check(), isNull);
    });
  });
}

/// Keeps the on/off setting in memory instead of the secure storage plugin.
class _TestChecker extends UpdateChecker {
  _TestChecker(http.Client client, {required String version, required bool android})
      : super(httpClient: client, currentVersion: version, isAndroid: android);

  bool _enabled = true;

  @override
  Future<bool> get enabled async => _enabled;

  @override
  Future<void> setEnabled(bool value) async => _enabled = value;
}
