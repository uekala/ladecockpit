import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ladecockpit_mobile/main.dart';

void main() {
  group('CockpitClient HTTP requests', () {
    late List<http.Request> requests;

    CockpitClient client({
      int status = 200,
      String body = '{"pages":2}',
      List<int>? bytes,
    }) {
      requests = [];
      final mock = MockClient((request) async {
        requests.add(request);
        return http.Response.bytes(
          bytes ?? utf8.encode(body),
          status,
          headers: {'content-type': 'application/json'},
        );
      });
      return CockpitClient(
        httpClient: mock,
        serverUrlProvider: () async => 'https://cockpit.example/',
        passwordProvider: () async => 'secret',
      );
    }

    test('dashboard sends GET, JSON Accept and Basic Auth', () async {
      final api = client(body: '{"mode":"live"}');
      final result = await api.dashboard();

      expect(result['mode'], 'live');
      expect(requests.single.method, 'GET');
      expect(requests.single.url.path, '/api/dashboard');
      expect(requests.single.headers['accept'], 'application/json');
      expect(
        requests.single.headers['authorization'],
        'Basic ${base64Encode(utf8.encode('ladecockpit:secret'))}',
      );
    });

    test('CSV export returns the response text and authenticates', () async {
      final api = client(body: 'date,kwh\n2026-11-01,12.5');
      expect(await api.csvExport(), 'date,kwh\n2026-11-01,12.5');
      expect(requests.single.url.path, '/api/export.csv');
      expect(requests.single.headers['authorization'], isNotEmpty);
    });

    test('invoice ZIP preserves binary bytes', () async {
      final api = client(bytes: [0x50, 0x4b, 0x03, 0x04, 0xff]);
      expect(await api.invoiceZip('2026-11'), [0x50, 0x4b, 0x03, 0x04, 0xff]);
      expect(requests.single.url.path, '/api/invoices/2026-11.zip');
      expect(requests.single.headers['authorization'], isNotEmpty);
    });

    test('invoice and report metadata requests use authenticated API paths', () async {
      final api = client();
      expect((await api.invoicePages('session/1'))['pages'], 2);
      expect(requests.single.url.path, '/api/invoice/session%2F1/pages');

      requests.clear();
      expect((await api.monthReportPages('2026-11'))['pages'], 2);
      expect(requests.single.url.path, '/api/report/2026-11/pages');
      expect(requests.single.headers['authorization'], isNotEmpty);
    });

    test('maps unauthorized CSV and ZIP responses to actionable errors', () async {
      final csvApi = client(status: 401, body: 'unauthorized');
      await expectLater(
        csvApi.csvExport(),
        throwsA(isA<CockpitException>().having(
          (error) => error.message,
          'message',
          contains('Anmeldung fehlgeschlagen'),
        )),
      );

      final zipApi = client(status: 401, body: 'unauthorized');
      await expectLater(
        zipApi.invoiceZip('2026-11'),
        throwsA(isA<CockpitException>().having(
          (error) => error.message,
          'message',
          contains('Anmeldung fehlgeschlagen'),
        )),
      );
    });

    test('reports missing invoice ZIPs distinctly', () async {
      final api = client(status: 404, body: 'not found');
      await expectLater(
        api.invoiceZip('2026-11'),
        throwsA(isA<CockpitException>().having(
          (error) => error.message,
          'message',
          contains('keine Rechnungen'),
        )),
      );
    });

    test('classifies private and public hosts for cleartext HTTP', () {
      const private = [
        '100.64.0.1',
        '100.127.255.254',
        'ladecockpit.example-tailnet.ts.net',
        '10.0.0.5',
        '172.16.0.1',
        '172.31.255.254',
        '192.168.1.20',
        '127.0.0.1',
        'localhost',
        'homeassistant',
        'homeassistant.local',
        'nas.home.arpa',
        'server.internal',
        'fd7a:115c:a1e0::1',
        '[fd7a:115c:a1e0::1]',
        '::1',
        'HomeAssistant.Local.',
      ];
      const public = [
        'example.com',
        '8.8.8.8',
        '100.63.255.255',
        '100.128.0.1',
        '172.15.0.1',
        '172.32.0.1',
        '192.169.0.1',
        '2001:db8::1',
        'ts.net.example.com',
        'local.example.com',
        '',
      ];
      for (final host in private) {
        expect(CockpitClient.allowsCleartextHttp(host), isTrue, reason: host);
      }
      for (final host in public) {
        expect(CockpitClient.allowsCleartextHttp(host), isFalse, reason: host);
      }
    });

    test('allows cleartext HTTP only inside private networks', () async {
      for (final url in [
        'http://100.101.102.103:8077',
        'http://ladecockpit.example-tailnet.ts.net:8077',
        'http://192.168.1.20:8077',
        'http://[fd7a:115c:a1e0::1]:8077',
      ]) {
        final api = CockpitClient(
          httpClient: MockClient((request) async {
            expect(request.url.host, Uri.parse(url).host);
            return http.Response('{"mode":"live"}', 200);
          }),
          serverUrlProvider: () async => url,
          passwordProvider: () async => 'secret',
        );
        expect((await api.dashboard())['mode'], 'live');
      }

      final blocked = CockpitClient(
        httpClient: MockClient((request) async {
          fail('HTTP request to a public host must be blocked');
        }),
        serverUrlProvider: () async => 'http://example.com',
        passwordProvider: () async => 'secret',
      );
      await expectLater(
        blocked.dashboard(),
        throwsA(isA<CockpitException>().having(
          (error) => error.message,
          'message',
          contains('nur im eigenen Netz erlaubt'),
        )),
      );
    });

    test('rejects invalid server URLs before sending a request', () async {
      final api = CockpitClient(
        httpClient: MockClient((request) async {
          fail('No request should be sent for an invalid URL');
        }),
        serverUrlProvider: () async => 'not-a-url',
        passwordProvider: () async => 'secret',
      );
      await expectLater(
        api.dashboard(),
        throwsA(isA<CockpitException>()),
      );
    });
  });
}
