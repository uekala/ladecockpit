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

Map<String, dynamic> _slot(String id, String label, String range, double price, int sessions) =>
    {'id': id, 'label': label, 'range': range, 'avg_price': price, 'sessions': sessions, 'kwh': 30.0 * sessions};

Map<String, dynamic> _site(String name, double price, int sessions) => {
      'site': name, 'label': name, 'avg_price': price, 'sessions': sessions,
      'kwh': 30.0 * sessions, 'network': 'supercharger',
    };

Future<void> _open(WidgetTester tester, List slots, List sites, [Map<String, dynamic>? tariffs]) async {
  final data = jsonDecode(File('test/fixtures/dashboard_demo.json').readAsStringSync())
      as Map<String, dynamic>;
  data['slots'] = slots;
  data['sites'] = sites;
  if (tariffs != null) data['tariffs'] = tariffs;
  tester.view.physicalSize = const Size(1080, 30000);
  tester.view.devicePixelRatio = 2.75;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final client = CockpitClient(
    httpClient: MockClient((request) async => http.Response(jsonEncode(data), 200,
        headers: {'content-type': 'application/json; charset=utf-8'})),
    serverUrlProvider: () async => 'http://192.168.1.20:8077',
    passwordProvider: () async => 'secret',
  );
  await tester.pumpWidget(MaterialApp(
    theme: AppTheme.dark,
    home: DashboardPage(client: client, updates: UpdateChecker(isAndroid: false)),
  ));
  await _settle(tester);
  await tester.tap(find.widgetWithText(NavigationDestination, 'Auswertung').first);
  await _settle(tester);
}

void main() {
  testWidgets('the lowest price is named the cheapest, with a note when it rests on one session', (tester) async {
    await _open(tester, [
      _slot('morning', 'Morgens', '6–11 Uhr', 0.30, 1),
      _slot('midday', 'Mittags', '11–16 Uhr', 0.376, 5),
      _slot('afternoon', 'Nachmittags', '16–20 Uhr', 0.405, 10),
    ], [
      _site('Moers', 0.41, 9),
      _site('Gelsenkirchen', 0.36, 2),
      _site('Venlo', 0.29, 1),
    ]);

    expect(find.text('Hier lädst du am günstigsten'), findsOneWidget);
    expect(find.text('Ladezeit · Morgens, 6–11 Uhr (nur 1 Ladevorgang)'), findsOneWidget);
    expect(find.text('Standort · Venlo (nur 1 Ladevorgang)'), findsOneWidget);
    expect(find.text('Morgens · Günstigste Zeit'), findsOneWidget);
    expect(find.text('Mittags · Günstigste Zeit'), findsNothing);
    expect(find.text('6–11 Uhr · 1 Ladevorgang · noch wenig aussagekräftig'), findsOneWidget);
    expect(find.text('11–16 Uhr · 5 Ladevorgänge'), findsOneWidget);
    // Zwei Nachkommastellen, wie jeder andere Preis in der App.
    expect(find.text('0,30 €/kWh'), findsWidgets);
    expect(find.text('0,38 €/kWh'), findsWidgets);
    expect(find.text('0,376 €/kWh'), findsNothing);
  });

  testWidgets('no note when enough sessions stand behind the cheapest', (tester) async {
    await _open(tester, [
      _slot('midday', 'Mittags', '11–16 Uhr', 0.376, 5),
      _slot('evening', 'Abends', '20–24 Uhr', 0.44, 2),
    ], [
      _site('Moers', 0.41, 9),
      _site('Gelsenkirchen', 0.36, 2),
    ]);

    expect(find.text('Ladezeit · Mittags, 11–16 Uhr'), findsOneWidget);
    expect(find.text('Standort · Gelsenkirchen'), findsOneWidget);
    expect(find.text('Mittags · Günstigste Zeit'), findsOneWidget);
  });

  testWidgets('off-peak and peak price per site', (tester) async {
    await _open(tester, [_slot('midday', 'Mittags', '11–16 Uhr', 0.40, 5)], [_site('Moers', 0.41, 9)], {
      'sites': [
        {'site': 'Moers', 'site_name': 'Moers, Germany', 'offpeak': 0.28, 'peak': 0.46,
         'off_times': ['06:00', '23:00'], 'saving': 9.0},
      ],
      'saving': 9.0, 'peak_kwh': 50.0,
    });
    expect(find.text('Nacht- und Tagpreis je Standort'), findsOneWidget);
    expect(find.text('Nebenzeit erlebt um 06:00, 23:00 Uhr'), findsOneWidget);
    expect(find.text('0,28 €'), findsOneWidget);
    expect(find.text('0,46 €'), findsOneWidget);
    expect(find.text('Deine 50 kWh aus der Hauptzeit an diesen Standorten hätten in der Nebenzeit 9,00 € weniger gekostet.'),
        findsOneWidget);
  });

  testWidgets('says how the tariffs will show up when none are known yet', (tester) async {
    await _open(tester, [_slot('midday', 'Mittags', '11–16 Uhr', 0.40, 5)], [_site('Moers', 0.41, 9)],
        {'sites': []});
    expect(find.text('Sobald du an einem Standort einmal nachts und einmal tagsüber geladen hast, stehen hier seine beiden Preise.'),
        findsOneWidget);
  });
}
