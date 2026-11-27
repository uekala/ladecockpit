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
  for (var i = 0; i < 8; i++) {
    await tester.pump(const Duration(milliseconds: 250));
  }
}

/// The analysis tab on a phone-sized screen, so the price radar is far below the tips and the
/// list has not built it yet.
Future<void> _openAnalysis(WidgetTester tester, [void Function(Map<String, dynamic> data)? change]) async {
  final data = jsonDecode(File('test/fixtures/dashboard_demo.json').readAsStringSync())
      as Map<String, dynamic>;
  change?.call(data);
  tester.view.physicalSize = const Size(1080, 2400);
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

bool _onScreen(WidgetTester tester, Finder finder) {
  final rect = tester.getRect(finder);
  final screen = tester.view.physicalSize / tester.view.devicePixelRatio;
  return rect.top >= 0 && rect.top < screen.height;
}

void main() {
  testWidgets('the first tip leads to the price radar further down', (tester) async {
    await _openAnalysis(tester);
    await tester.tap(find.text('Zum Preisradar').first);
    await _settle(tester);
    expect(find.byKey(const ValueKey('radar-sites')), findsOneWidget);
    expect(_onScreen(tester, find.byKey(const ValueKey('radar-sites'))), isTrue);
  });

  testWidgets('a tip about a site opens the radar of that site', (tester) async {
    await _openAnalysis(tester, (data) {
      final tips = (data['insights'] as List).cast<Map<String, dynamic>>();
      tips.firstWhere((tip) => tip['kind'] == 'site')['action'] = {'go': 'radar', 'site': 'Mainz'};
    });
    await tester.tap(find.text('Radar für Mainz'));
    await _settle(tester);
    final chip = find.widgetWithText(ChoiceChip, 'Mainz · 3');
    expect(chip, findsOneWidget);
    expect(tester.widget<ChoiceChip>(chip).selected, isTrue);
    expect(_onScreen(tester, find.byKey(const ValueKey('radar-sites'))), isTrue);
  });
}
