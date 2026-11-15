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

Map<String, dynamic> _session(String id, String site, String start, double kwh, double price,
        {String network = 'supercharger', String? operator}) =>
    {
      'id': id, 'site': site, 'place': site.split(',').first, 'start': start, 'end': start,
      'kwh': kwh, 'cost': double.parse((kwh * price).toStringAsFixed(2)), 'price': price,
      'list_price': price, 'currency': 'EUR', 'network': network, 'operator': operator,
      'has_invoice': true,
    };

void main() {
  late List<http.Request> requests;
  late Map<String, dynamic> data;

  Future<void> open(WidgetTester tester) async {
    data = jsonDecode(File('test/fixtures/dashboard_demo.json').readAsStringSync()) as Map<String, dynamic>;
    data['sessions'] = [
      _session('a', 'Bergstadt, Germany', '2026-10-03T10:00:00+02:00', 40, 0.40),
      _session('b', 'Bergstadt, Germany', '2026-10-09T10:00:00+02:00', 20, 0.42),
      _session('c', 'Seestadt, Germany', '2026-09-12T10:00:00+02:00', 30, 0.30),
      _session('d', 'Hafenstadt, Netherlands', '2026-09-20T10:00:00+02:00', 10, 0.60, network: 'multipass'),
    ];
    requests = [];
    tester.view.physicalSize = const Size(1080, 30000);
    tester.view.devicePixelRatio = 2.75;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final client = CockpitClient(
      httpClient: MockClient((request) async {
        requests.add(request);
        if (request.url.path == '/api/operators') {
          return http.Response(jsonEncode({'assigned': {}, 'known': ['Allego', 'Fastned', 'IONITY']}), 200,
              headers: {'content-type': 'application/json'});
        }
        if (request.url.path == '/api/operator') {
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          for (final session in (data['sessions'] as List).cast<Map<String, dynamic>>()) {
            if (session['site'] == body['site']) session['operator'] = body['operator'];
          }
          return http.Response('{}', 200, headers: {'content-type': 'application/json'});
        }
        return http.Response(jsonEncode(data), 200,
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
    await tester.tap(find.widgetWithText(NavigationDestination, 'Ladevorgänge').first);
    await _settle(tester);
  }

  String summary(WidgetTester tester) =>
      tester.widget<Text>(find.byKey(const ValueKey('session-summary'))).data!;

  testWidgets('filter chips narrow the list and the summary follows', (tester) async {
    await open(tester);
    expect(summary(tester), '4 Ladevorgänge · 100,0 kWh · 39,40 €');
    // Every card shows its price per kWh.
    expect(find.text('0,60'), findsOneWidget);
    expect(find.text('0,30'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('filter-site')));
    await _settle(tester);
    await tester.tap(find.byKey(const ValueKey('option-Bergstadt, Germany')));
    await _settle(tester);
    expect(summary(tester), '2 Ladevorgänge · 60,0 kWh · 24,40 €');
    expect(find.widgetWithText(InputChip, 'Bergstadt'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('filter-month')));
    await _settle(tester);
    await tester.tap(find.byKey(const ValueKey('option-2026-09')));
    await _settle(tester);
    expect(summary(tester), '0 Ladevorgänge · 0,0 kWh · 0,00 €');
    expect(find.text('Keine Ladevorgänge für diese Filter gefunden.'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('filter-reset')));
    await _settle(tester);
    expect(summary(tester), '4 Ladevorgänge · 100,0 kWh · 39,40 €');

    await tester.enterText(find.byKey(const ValueKey('session-search')), 'gibtsnicht');
    await _settle(tester);
    expect(find.text('Keine Ladevorgänge für „gibtsnicht“ gefunden.'), findsOneWidget);
  });

  testWidgets('the operator of a third-party station can be assigned', (tester) async {
    await open(tester);
    await tester.tap(find.text('Hafenstadt'));
    await _settle(tester);
    expect(find.text('MultiPass: Laden bei einem anderen Anbieter, abgerechnet über Tesla.'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('assign-operator')));
    await _settle(tester);
    expect(find.text('Wer betreibt diese Station?'), findsOneWidget);
    await tester.enterText(find.byKey(const ValueKey('operator-name')), 'fast');
    await _settle(tester);
    await tester.tap(find.widgetWithText(ActionChip, 'Fastned'));
    await _settle(tester);
    await tester.tap(find.byKey(const ValueKey('operator-save')));
    await _settle(tester);

    final saved = requests.singleWhere((r) => r.url.path == '/api/operator');
    expect(saved.method, 'PUT');
    expect(jsonDecode(saved.body), {'site': 'Hafenstadt, Netherlands', 'operator': 'Fastned'});
    expect(find.text('Betreiber gespeichert: Fastned'), findsOneWidget);

    // A Supercharger has no such button.
    await tester.tap(find.text('Seestadt'));
    await _settle(tester);
    expect(find.byKey(const ValueKey('assign-operator')), findsNothing);
  });
}
