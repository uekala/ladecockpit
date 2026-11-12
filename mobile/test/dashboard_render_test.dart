import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ladecockpit_mobile/dashboard_cache.dart';
import 'package:ladecockpit_mobile/l10n.dart';
import 'package:ladecockpit_mobile/main.dart';
import 'package:ladecockpit_mobile/theme/app_theme.dart';
import 'package:ladecockpit_mobile/update_check.dart';

/// Renders every tab and every expandable card with the demo answer of the
/// server and with each part of it missing. A build error shows up as a grey
/// box in release builds; here it fails the test with the widget that threw.
Map<String, dynamic> _demo() => jsonDecode(
      File('test/fixtures/dashboard_demo.json').readAsStringSync(),
    ) as Map<String, dynamic>;

Map<String, dynamic> _demoEnglish() => jsonDecode(
      File('test/fixtures/dashboard_demo_en.json').readAsStringSync(),
    ) as Map<String, dynamic>;

Future<List<String>> _renderAll(WidgetTester tester, Map<String, dynamic> data,
    {List<String> tabs = const ['Cockpit', 'Ladevorgänge', 'Auswertung'], Set<String>? seen}) async {
  final errors = <String>[];
  final previous = FlutterError.onError;
  FlutterError.onError = (details) {
    final message = details.exceptionAsString().split('\n').first;
    final text = details.toString();
    final at = RegExp(r'The relevant error-causing widget was:\s*\n\s*(.+)').firstMatch(text)?.group(1)?.trim() ??
        details.context?.toDescription() ?? '';
    final creator = RegExp(r'creator: ([^\n]{0,400})').firstMatch(text)?.group(1) ?? '';
    errors.add('$message @ $at ${creator.isEmpty ? '' : '[$creator]'}');

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
    for (final tab in tabs) {
      final destination = find.widgetWithText(NavigationDestination, tab);
      if (destination.evaluate().isNotEmpty) {
        await tester.tap(destination.first);
        await _settle(tester);
      }
      await _expandAll(tester);
      seen?.addAll(tester
          .widgetList<Text>(find.byType(Text, skipOffstage: false))
          .map((text) => text.data ?? text.textSpan?.toPlainText() ?? ''));
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
    final headers = find.descendant(of: tile.at(i), matching: find.byType(ListTile));
    if (headers.evaluate().isEmpty) continue;
    final header = headers.first;
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

  testWidgets('cockpit cards show readable summaries and German numbers', (tester) async {
    tester.view.physicalSize = const Size(1080, 16000);
    tester.view.devicePixelRatio = 2.75;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final client = CockpitClient(
      httpClient: MockClient((request) async => http.Response(
            jsonEncode(_demo()),
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
    expect(find.text('Weiterstadt · 10.11. · 9,54 €'), findsOneWidget);
    expect(find.text('11 Ladevorgänge · 368,5 kWh · 169,48 €'), findsOneWidget);
    expect(find.text('Model 3 · Pearl White Multi-Coat · 18″ Photon'), findsOneWidget);
    expect(find.text('82,02 €'), findsWidgets);
    expect(find.text('0,47 €/kWh'), findsWidgets);
    expect(find.textContaining('https://'), findsNothing);
    expect(find.textContaining('demo-1010'), findsNothing);
  });

  testWidgets('shows the last figures the phone kept when the server is unreachable', (tester) async {
    tester.view.physicalSize = const Size(1080, 16000);
    tester.view.devicePixelRatio = 2.75;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final cache = _MemoryCache()..stored = CachedDashboard(_demo(), DateTime(2026, 11, 12, 18, 30));
    final client = CockpitClient(
      httpClient: MockClient((request) async => throw const SocketException('Network is unreachable')),
      serverUrlProvider: () async => 'http://192.168.1.20:8077',
      passwordProvider: () async => 'secret',
    );
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.dark,
      home: DashboardPage(client: client, updates: UpdateChecker(isAndroid: false), cache: cache),
    ));
    await _settle(tester);
    expect(find.text('Keine Verbindung zum Server'), findsOneWidget);
    expect(find.text('Letzter Stand · 12.11.2026, 18:30 Uhr'), findsOneWidget);
    expect(find.text('Weiterstadt · 10.11. · 9,54 €'), findsOneWidget);
    expect(cache.writes, 0);
  });

  testWidgets('keeps a copy after a successful load and lists the year overview', (tester) async {
    tester.view.physicalSize = const Size(1080, 16000);
    tester.view.devicePixelRatio = 2.75;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final cache = _MemoryCache();
    final client = CockpitClient(
      httpClient: MockClient((request) async => http.Response(
            jsonEncode(_demo()),
            200,
            headers: {'content-type': 'application/json; charset=utf-8'},
          )),
      serverUrlProvider: () async => 'http://192.168.1.20:8077',
      passwordProvider: () async => 'secret',
    );
    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.dark,
      home: DashboardPage(client: client, updates: UpdateChecker(isAndroid: false), cache: cache),
    ));
    await _settle(tester);
    expect(cache.writes, 1);
    expect(cache.stored?.data['mode'], 'demo');
    expect(find.textContaining('Letzter Stand'), findsNothing);
    await tester.tap(find.widgetWithText(NavigationDestination, 'Auswertung').first);
    await _settle(tester);
    expect(find.text('Jahresübersicht 2026'), findsOneWidget);
  });

  testWidgets('an English server gives an English app', (tester) async {
    addTearDown(() => appLanguage = 'de');
    final seen = <String>{};
    final errors = await _renderAll(tester, _demoEnglish(),
        tabs: const ['Cockpit', 'Sessions', 'Reports'], seen: seen);
    expect(errors, isEmpty, reason: errors.join('\n'));
    expect(appLanguage, 'en');
    expect(seen, containsAll(['MONTH OVERVIEW', 'Last session', 'Price radar', 'Reports & export',
      'Year overview 2026', 'Connections']));
    // No German may be left on any tab or in any opened card.
    final german = RegExp(r'[äöüÄÖÜß]|\b(und|oder|nicht|keine|Ladevorg|Verbind|Rechnung|Kosten|Monat|Standort|Zeitraum|Preis|Uhr)');
    final leftovers = seen.where(german.hasMatch).toList();
    expect(leftovers, isEmpty, reason: leftovers.join('\n'));
  });

  test('fixture is valid', () {
    expect(kIsWeb, isFalse);
    expect(_demo()['sessions'], isA<List>());
  });
}

/// Stands in for the file on the phone.
class _MemoryCache extends DashboardCache {
  CachedDashboard? stored;
  int writes = 0;

  @override
  Future<void> write(Map<String, dynamic> data, DateTime fetchedAt) async {
    writes++;
    stored = CachedDashboard(data, fetchedAt);
  }

  @override
  Future<CachedDashboard?> read() async => stored;

  @override
  Future<void> clear() async => stored = null;
}
