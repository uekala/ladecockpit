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

Future<void> _open(WidgetTester tester) async {
  final data = jsonDecode(File('test/fixtures/dashboard_demo.json').readAsStringSync())
      as Map<String, dynamic>;
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
}

void main() {
  testWidgets('the cockpit compares the month with a combustion car and checks the setup', (tester) async {
    await _open(tester);
    expect(find.byKey(const ValueKey('fuel-compare')), findsOneWidget);
    expect(find.text('Gespart'), findsWidgets);
    expect(find.byKey(const ValueKey('setup-check')), findsOneWidget);
    expect(find.text('Einrichtung prüfen'), findsOneWidget);
  });

  testWidgets('tips are cards that lead to the sessions; the radar has a chip per site', (tester) async {
    await _open(tester);
    await tester.tap(find.widgetWithText(NavigationDestination, 'Auswertung').first);
    await _settle(tester);
    expect(find.text('Was auffällt'), findsOneWidget);
    expect(find.byKey(const ValueKey('radar-sites')), findsOneWidget);
    expect(find.text('Alle Standorte'), findsWidgets);
    expect(find.byKey(const ValueKey('per100-chart')), findsOneWidget);
    expect(find.byKey(const ValueKey('backup-share')), findsNothing);   // not in the demo
    await tester.tap(find.text('Zu den Ladevorgängen').first);
    await _settle(tester);
    expect(find.byKey(const ValueKey('session-search')), findsOneWidget);
  });
}
