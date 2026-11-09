import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:ladecockpit_mobile/main.dart';

void main() {
  group('cockpitRequestHeaders', () {
    test('does not send Authorization when no password is configured', () {
      final headers = cockpitRequestHeaders(null, json: true);

      expect(headers['Accept'], 'application/json');
      expect(headers.containsKey('Authorization'), isFalse);
    });

    test('creates HTTP Basic credentials using the Ladecockpit user name', () {
      final headers = cockpitRequestHeaders('test-secret');

      expect(headers['Accept'], '*/*');
      expect(
        headers['Authorization'],
        'Basic ${base64Encode(utf8.encode('ladecockpit:test-secret'))}',
      );
    });

    test('uses the JSON Accept header when requested', () {
      expect(
        cockpitRequestHeaders('', json: true)['Accept'],
        'application/json',
      );
    });
  });

  group('parseDashboardResponse', () {
    test('maps a successful dashboard object without dropping nested values', () {
      final dashboard = parseDashboardResponse(
        200,
        '{"mode":"live","month":{"cost":12.5},"sessions":[{"site":"Marl"}]}',
      );

      expect(dashboard['mode'], 'live');
      expect(dashboard['month'], {'cost': 12.5});
      expect(dashboard['sessions'], [{'site': 'Marl'}]);
    });

    test('reports unauthorized responses as authentication errors', () {
      expect(
        () => parseDashboardResponse(401, '{}'),
        throwsA(isA<CockpitException>().having(
          (error) => error.message,
          'message',
          contains('Anmeldung fehlgeschlagen'),
        )),
      );
    });

    test('reports forbidden responses as authentication or permission errors', () {
      expect(
        () => parseDashboardResponse(403, '{}'),
        throwsA(isA<CockpitException>().having(
          (error) => error.message,
          'message',
          contains('Zugriffsrechte'),
        )),
      );
    });

    test('reports other HTTP errors with their status code', () {
      expect(
        () => parseDashboardResponse(503, 'unavailable'),
        throwsA(isA<CockpitException>().having(
          (error) => error.message,
          'message',
          contains('503'),
        )),
      );
    });

    test('rejects a valid JSON response that is not an object', () {
      expect(
        () => parseDashboardResponse(200, '[]'),
        throwsA(isA<CockpitException>().having(
          (error) => error.message,
          'message',
          contains('Ungültige Antwort'),
        )),
      );
    });

    test('lets malformed JSON be classified as a format error', () {
      expect(
        () => parseDashboardResponse(200, '{invalid'),
        throwsA(isA<FormatException>()),
      );
    });
  });
}
