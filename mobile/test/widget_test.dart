import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ladecockpit_mobile/main.dart';

class FakeCockpitClient extends CockpitClient {
  @override
  Future<Map<String, dynamic>> dashboard() async => {
        'sessions': [
          {
            'id': 'session-multipass',
            'site': 'Station A',
            'network': 'multipass',
            'start': '2026-01-10T10:00:00Z',
            'kwh': 24.5,
            'cost': 8.20,
            'currency': 'EUR',
            'has_invoice': false,
          },
          {
            'id': 'session-supercharger',
            'site': 'Station B',
            'network': 'supercharger',
            'start': '2026-01-12T12:00:00Z',
            'kwh': 30.0,
            'cost': 10.50,
            'currency': 'EUR',
            'has_invoice': false,
          },
        ],
        'monthly': [],
      };
}

void main() {
  testWidgets('shows the Ladecockpit app bar', (tester) async {
    await tester.pumpWidget(const LadecockpitApp());

    expect(find.text('Ladecockpit'), findsOneWidget);
  });

  testWidgets('exposes connection settings and refresh actions', (tester) async {
    await tester.pumpWidget(const LadecockpitApp());

    expect(find.byTooltip('Verbindung'), findsOneWidget);
    expect(find.byTooltip('Aktualisieren'), findsOneWidget);
  });

  testWidgets('filters charging sessions by network and resets filters',
      (tester) async {
    tester.view.physicalSize = const Size(900, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(home: DashboardPage(client: FakeCockpitClient())),
    );
    await tester.pumpAndSettle();

    await tester.scrollUntilVisible(
      find.text('Alle Netzwerke'),
      350,
      scrollable: find.byType(Scrollable).first,
    );
    expect(find.text('2 / 2'), findsOneWidget);

    await tester.tap(find.text('Alle Netzwerke'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('MultiPass').last);
    await tester.pumpAndSettle();

    expect(find.text('1 / 2'), findsOneWidget);
    expect(find.text('Station A'), findsOneWidget);
    expect(find.text('Station B'), findsNothing);

    await tester.tap(find.text('Filter zurücksetzen'));
    await tester.pumpAndSettle();

    expect(find.text('2 / 2'), findsOneWidget);
    expect(find.text('Station A'), findsOneWidget);
    expect(find.text('Station B'), findsOneWidget);
  });
}
