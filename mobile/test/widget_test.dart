import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ladecockpit_mobile/main.dart';

class FakeCockpitClient extends CockpitClient {
  @override
  Future<Map<String, dynamic>> invoicePages(String sessionId) async {
    throw const CockpitException('Testrechnung nicht verfügbar.');
  }

  @override
  Future<String> csvExport() async =>
      'Datum;Standort;Energie;Kosten\n2026-01-10;Station A;24.5;8.20\n';

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
            'has_invoice': true,
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

  testWidgets('opens invoice action and shows a clear error when unavailable',
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
      find.text('Station A'),
      350,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.text('Station A'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Rechnung öffnen'));
    await tester.pumpAndSettle();

    expect(find.text('Testrechnung nicht verfügbar.'), findsOneWidget);
  });

  testWidgets('previews CSV export with row count', (tester) async {
    tester.view.physicalSize = const Size(900, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(home: DashboardPage(client: FakeCockpitClient())),
    );
    await tester.pumpAndSettle();

    await tester.scrollUntilVisible(
      find.text('Alle Ladevorgänge als CSV'),
      350,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.text('Alle Ladevorgänge als CSV'));
    await tester.pumpAndSettle();

    expect(find.text('CSV-Export'), findsOneWidget);
    expect(find.textContaining('Datum;Standort;Energie;Kosten'), findsOneWidget);
    expect(find.textContaining('2 Zeilen insgesamt'), findsOneWidget);

    await tester.tap(find.text('Schließen'));
    await tester.pumpAndSettle();
    expect(find.text('CSV-Export'), findsNothing);
  });
}
