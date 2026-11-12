import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ladecockpit_mobile/main.dart';
import 'package:ladecockpit_mobile/theme/app_theme.dart';
import 'package:ladecockpit_mobile/update_check.dart';

/// Renders every tab and every expandable card with the demo answer of the
/// server and with each part of it missing. A build error shows up as a grey
/// box in release builds; here it fails the test with the widget that threw.
Map<String, dynamic> _demo() => jsonDecode(
      File('test/fixtures/dashboard_demo.json').readAsStringSync(),
    ) as Map<String, dynamic>;

var _printedOverflow = false;

Future<List<String>> _renderAll(WidgetTester tester, Map<String, dynamic> data) async {
  final errors = <String>[];
  final previous = FlutterError.onError;
  FlutterError.onError = (details) {
    final message = details.exceptionAsString().split('\n').first;
    final text = details.toString();
    final at = RegExp(r'The relevant error-causing widget was:\s*\n\s*(.+)').firstMatch(text)?.group(1)?.trim() ??
        details.context?.toDescription() ?? '';
    final creator = RegExp(r'creator: ([^\n]{0,400})').firstMatch(text)?.group(1) ?? '';
    errors.add('$message @ $at ${creator.isEmpty ? '' : '[$creator]'}');
    if (message.contains('overflowed') && !_printedOverflow) {
      _printedOverflow = true;
      // ignore: avoid_print
      print(details.toDiagnosticsNode().toStringDeep().split('\n').take(8).join('\n'));
    }
  };
  try {
    tester.view.physicalSize = const Size(1080, 2392);
    tester.view.devicePixelRatio = 2.75;
    final client = CockpitClient(
      httpClient: MockClient((request) async => http.Response(
            jsonEncode(data),
            200,
            headers: {'content-type': 'application/json; charset=utf-8'},
          )),
      serverUrlProvider: () async => 'http://192.168.1.20:8077',
      passwordProvider: () async => 'secret',
    );
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.dark,
      home: DashboardPage(client: client, updates: UpdateChecker(isAndroid: false)),
    ));
    await _settle(tester);
    for (final tab in ['Cockpit', 'Ladevorgänge', 'Auswertung']) {
      final destination = find.widgetWithText(NavigationDestination, tab);
      if (destination.evaluate().isNotEmpty) {
        await tester.tap(destination.first);
        await _settle(tester);
      }
      await _expandAll(tester);
    }
  } finally {
    FlutterError.onError = previous;
    tester.view.resetPhysicalSize();
    tester.view.resetDevicePixelRatio();
  }
  return errors.toSet().toList();
}

Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 250));
  }
}

Future<void> _expandAll(WidgetTester tester) async {
  final tiles = find.byType(ExpansionTile, skipOffstage: false);
  final count = tiles.evaluate().length;
  for (var i = 0; i < count; i++) {
    final tile = find.byType(ExpansionTile, skipOffstage: false);
    if (i >= tile.evaluate().length) break;
    final header = find.descendant(of: tile.at(i), matching: find.byType(ListTile)).first;
    await tester.ensureVisible(header);
    await tester.pump();
    await tester.tap(header, warnIfMissed: false);
    await _settle(tester);
  }
}

void main() {
  testWidgets('demo dashboard renders without errors', (tester) async {
    final errors = await _renderAll(tester, _demo());
    expect(errors, isEmpty, reason: errors.join('\n'));
  });

  final keys = _demo().keys.where((key) => key != 'mode').toList();
  for (final key in keys) {
    testWidgets('dashboard without "$key" renders without errors', (tester) async {
      final data = _demo()..remove(key);
      final errors = await _renderAll(tester, data);
      expect(errors, isEmpty, reason: errors.join('\n'));
    });
    testWidgets('dashboard with "$key": null renders without errors', (tester) async {
      final data = _demo()..[key] = null;
      final errors = await _renderAll(tester, data);
      expect(errors, isEmpty, reason: errors.join('\n'));
    });
  }

  testWidgets('dashboard without any sessions renders without errors', (tester) async {
    final data = _demo();
    data['sessions'] = <dynamic>[];
    data['monthly'] = <dynamic>[];
    data['last_charge'] = null;
    final errors = await _renderAll(tester, data);
    expect(errors, isEmpty, reason: errors.join('\n'));
  });

  test('fixture is valid', () {
    expect(kIsWeb, isFalse);
    expect(_demo()['sessions'], isA<List>());
  });
}
