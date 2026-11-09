import 'package:flutter_test/flutter_test.dart';
import 'package:ladecockpit_mobile/document_response.dart';

void main() {
  group('parseDocumentPagesResponse', () {
    test('accepts valid invoice metadata and preserves additional fields', () {
      final result = parseDocumentPagesResponse(
        200,
        '{"pages":3,"filename":"invoice.pdf"}',
        documentLabel: 'die Rechnung',
      );

      expect(result['pages'], 3);
      expect(result['filename'], 'invoice.pdf');
    });

    test('accepts valid monthly report metadata', () {
      final result = parseDocumentPagesResponse(
        200,
        '{"pages":2}',
        documentLabel: 'den Monatsbericht',
      );

      expect(result['pages'], 2);
    });

    test('maps unauthorized and forbidden responses to an auth error', () {
      for (final status in [401, 403]) {
        expect(
          () => parseDocumentPagesResponse(
            status, '{}', documentLabel: 'die Rechnung',
          ),
          throwsA(isA<CockpitException>().having(
            (error) => error.message,
            'message',
            contains('Anmeldung fehlgeschlagen'),
          )),
        );
      }
    });

    test('uses the invoice-specific message when no invoice exists', () {
      expect(
        () => parseDocumentPagesResponse(
          404,
          '',
          documentLabel: 'die Rechnung',
          notFoundMessage: 'Die Rechnung ist noch nicht verfügbar.',
        ),
        throwsA(isA<CockpitException>().having(
          (error) => error.message,
          'message',
          contains('noch nicht verfügbar'),
        )),
      );
    });

    test('reports other HTTP errors with their status code', () {
      expect(
        () => parseDocumentPagesResponse(
          503, '', documentLabel: 'den Monatsbericht',
        ),
        throwsA(isA<CockpitException>().having(
          (error) => error.message,
          'message',
          contains('503'),
        )),
      );
    });

    test('rejects a JSON array instead of an object', () {
      expect(
        () => parseDocumentPagesResponse(
          200, '[]', documentLabel: 'die Rechnung',
        ),
        throwsA(isA<CockpitException>()),
      );
    });

    test('rejects missing or non-integer page counts', () {
      for (final body in ['{}', '{"pages":"2"}', '{"pages":2.5}']) {
        expect(
          () => parseDocumentPagesResponse(
            200, body, documentLabel: 'die Rechnung',
          ),
          throwsA(isA<CockpitException>()),
        );
      }
    });

    test('rejects zero and negative page counts', () {
      for (final body in ['{"pages":0}', '{"pages":-1}']) {
        expect(
          () => parseDocumentPagesResponse(
            200, body, documentLabel: 'die Rechnung',
          ),
          throwsA(isA<CockpitException>()),
        );
      }
    });

    test('classifies malformed JSON as a format error', () {
      expect(
        () => parseDocumentPagesResponse(
          200, '{invalid', documentLabel: 'die Rechnung',
        ),
        throwsA(isA<FormatException>()),
      );
    });
  });
}
