import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:ladecockpit_mobile/main.dart';
import 'package:ladecockpit_mobile/theme/app_theme.dart';
import 'package:ladecockpit_mobile/update_check.dart';

Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 250));
  }
}

void main() {
  testWidgets('sessions show the place and can be searched', (tester) async {
    final data = jsonDecode(File('test/fixtures/dashboard_demo.json').readAsStringSync())
        as Map<String, dynamic>;
    final sessions = (data['sessions'] as List).cast<Map<String, dynamic>>();
    sessions[0]['site'] = 'Moers, Germany';
    sessions[0]['place'] = 'Moers';
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
    await tester.tap(find.widgetWithText(NavigationDestination, 'Ladevorgänge').first);
    await _settle(tester);

    expect(find.text('Moers'), findsOneWidget);
    expect(find.text('Moers, Germany'), findsNothing);
    expect(find.text('IONITY Weiskirchen'), findsWidgets);

    await tester.enterText(find.byKey(const ValueKey('session-search')), 'ionity');
    await _settle(tester);
    expect(find.text('IONITY Weiskirchen'), findsWidgets);
    expect(find.text('Moers'), findsNothing);
    expect(find.text('Mainz'), findsNothing);

    // The country still finds the session, although the list shows only the place.
    await tester.enterText(find.byKey(const ValueKey('session-search')), 'moers germ');
    await _settle(tester);
    expect(find.text('Moers'), findsOneWidget);
    expect(find.text('IONITY Weiskirchen'), findsNothing);
  });
}
