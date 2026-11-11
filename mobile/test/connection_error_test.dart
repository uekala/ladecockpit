import 'dart:async';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:ladecockpit_mobile/main.dart';

void main() {
  group('connectionErrorMessage', () {
    test('explains request timeouts', () {
      expect(
        connectionErrorMessage(TimeoutException('timed out')),
        contains('Zeitüberschreitung'),
      );
    });

    test('explains unreachable servers and VPN connectivity', () {
      final message = connectionErrorMessage(const SocketException('no route'));
      expect(message, contains('Server nicht erreichbar'));
      expect(message, contains('VPN/Tailscale'));
      expect(message, contains('no route'));
    });

    test('explains HTTPS handshake failures', () {
      final message = connectionErrorMessage(
        const HandshakeException('bad certificate'),
      );
      expect(message, contains('HTTPS-Zertifikat'));
    });

    test('explains HTTP transport failures', () {
      expect(
        connectionErrorMessage(const HttpException('connection reset')),
        contains('connection reset'),
      );
    });

    test('explains invalid server responses', () {
      expect(
        connectionErrorMessage(const FormatException('invalid json')),
        contains('ungültige Antwort'),
      );
    });

    test('puts the diagnosis of unknown errors on its own line', () {
      final message = connectionErrorMessage(StateError('kaputt'));
      expect(message, startsWith('Verbindung fehlgeschlagen.\nDiagnose: StateError'));
      expect(message, contains('kaputt'));
      expect(message, isNot(contains(r'\n')));
    });

    test('keeps actionable authentication messages', () {
      const error = CockpitException('Anmeldung fehlgeschlagen. Passwort prüfen.');
      expect(connectionErrorMessage(error), error.message);
    });
  });
}
