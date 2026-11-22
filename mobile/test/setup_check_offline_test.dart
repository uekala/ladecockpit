import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ladecockpit_mobile/main.dart';
import 'package:ladecockpit_mobile/theme/app_theme.dart';
import 'package:ladecockpit_mobile/update_check.dart';
import 'package:material_ui/material_ui.dart';

Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 250));
  }
}

/// Öffnet das Cockpit mit den Demodaten, geändert, wie der Test es braucht; gibt die gesendeten Anfragen zurück.
Future<List<http.Request>> _open(WidgetTester tester, void Function(Map<String, dynamic> data) change) async {
  final data = jsonDecode(File('test/fixtures/dashboard_demo.json').readAsStringSync())
      as Map<String, dynamic>;
  change(data);
  final requests = <http.Request>[];
  tester.view.physicalSize = const Size(1080, 30000);
  tester.view.devicePixelRatio = 2.75;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final client = CockpitClient(
    httpClient: MockClient((request) async {
      requests.add(request);
      final body = request.url.path.startsWith('/api/hint') ? {'hidden': <String>[]} : data;
      return http.Response(jsonEncode(body), 200,
          headers: {'content-type': 'application/json; charset=utf-8'});
    }),
    serverUrlProvider: () async => 'http://192.168.1.20:8077',
    passwordProvider: () async => 'secret',
  );
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.dark,
    home: DashboardPage(client: client, updates: UpdateChecker(isAndroid: false)),
  ));
  await _settle(tester);
  return requests;
}

/// Die Einrichtungsprüfung, wie der Server sie schickt, während das Auto offline ist: kein Problem, ein Tipp.
void _carOffline(Map<String, dynamic> data) {
  final checks = data['setup']['checks'] as Map<String, dynamic>;
  checks['hints'] = [
    {'id': 'no_home', 'level': 'tip', 'text': 'Lädst du auch zu Hause?', 'dismissable': true},
  ];
  for (final entity in (checks['entities'] as List).cast<Map<String, dynamic>>()) {
    entity['ok'] = true;
    entity['problem'] = null;
  }
  for (final step in (checks['steps'] as List).cast<Map<String, dynamic>>()) {
    if (step['id'] == 'entities') step['status'] = 'done';
  }
  checks['offline'] = '21.11. 21:12';
  final status = data['status'] as Map<String, dynamic>;
  status['soc_source'] = 'last';
  status['charging'] = null;
  status.remove('power');
  status.remove('rate');
  status.remove('finish');
}

void main() {
  testWidgets('an offline car is no warning, and a tip can be hidden', (tester) async {
    final requests = await _open(tester, _carOffline);
    expect(find.text('Auto offline'), findsOneWidget);
    expect(find.text('Ladestatus nicht verfügbar'), findsNothing);
    expect(find.textContaining('Entitäten prüfen'), findsNothing);
    expect(find.text('1 Tipps für mehr Auswertungen'), findsOneWidget);

    await tester.tap(find.text('Einrichtung prüfen'));
    await _settle(tester);
    await tester.tap(find.byKey(const ValueKey('hint-hide-no_home')));
    await _settle(tester);
    final put = requests.firstWhere((request) => request.method == 'PUT');
    expect(put.url.path, '/api/hint');
    expect(jsonDecode(put.body), {'id': 'no_home', 'hidden': true});
    expect(find.text('Tipp ausgeblendet'), findsOneWidget);
  });

  testWidgets('hidden tips can be shown again', (tester) async {
    final requests = await _open(tester, (data) {
      final checks = data['setup']['checks'] as Map<String, dynamic>;
      checks['hidden'] = 2;
    });
    await tester.tap(find.byKey(const ValueKey('hints-show')));
    await _settle(tester);
    final delete = requests.firstWhere((request) => request.method == 'DELETE');
    expect(delete.url.path, '/api/hints/hidden');
  });

  testWidgets('a missing charging state while the car is online stays a warning', (tester) async {
    await _open(tester, (data) {
      final status = data['status'] as Map<String, dynamic>;
      status['charging'] = null;
      status.remove('power');
    });
    expect(find.text('Ladestatus nicht verfügbar'), findsOneWidget);
    expect(find.text('Auto offline'), findsNothing);
  });
}
