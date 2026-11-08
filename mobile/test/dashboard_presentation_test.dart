import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ladecockpit_mobile/main.dart';

class DashboardFixtureClient extends CockpitClient {
  DashboardFixtureClient(this.payload);

  final Map<String, dynamic> payload;

  @override
  Future<Map<String, dynamic>> dashboard() async => payload;
}

void main() {
  Future<void> pumpDashboard(
    WidgetTester tester,
    Map<String, dynamic> payload,
  ) async {
    tester.view.physicalSize = const Size(900, 1800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData.dark(),
        home: DashboardPage(client: DashboardFixtureClient(payload)),
      ),
    );
    await tester.pumpAndSettle();
  }

  testWidgets('shows live vehicle status and charging details', (tester) async {
    await pumpDashboard(tester, {
      'status': {
        'soc': 72,
        'soc_source': 'live',
        'as_of': '2026-11-08T07:00:00Z',
        'range': 420,
        'target': 80,
        'charging': true,
        'power': 115.4,
        'rate': 45.0,
      },
    });

    expect(find.text('FAHRZEUGSTATUS'), findsOneWidget);
    expect(find.text('Live-Akkustand'), findsOneWidget);
    expect(find.text('72%'), findsOneWidget);
    expect(find.text('420 km'), findsOneWidget);
    expect(find.text('Ladelimit 80 %'), findsOneWidget);
    expect(find.text('Wird geladen'), findsOneWidget);
    expect(find.text('115.4 kW'), findsOneWidget);
    expect(find.text('Ladegeschwindigkeit: 45.0 % pro Stunde'), findsOneWidget);
  });

  testWidgets('distinguishes a cached battery reading from live data',
      (tester) async {
    await pumpDashboard(tester, {
      'status': {
        'soc': 64,
        'soc_source': 'last',
        'as_of': '2026-11-08T06:30:00Z',
        'charging': false,
      },
    });

    expect(find.text('Letzter bekannter Akkustand'), findsOneWidget);
    expect(find.text('64%'), findsOneWidget);
    expect(find.text('Live-Akkustand'), findsNothing);
    expect(find.text('Lädt derzeit nicht'), findsOneWidget);
  });

  testWidgets('uses a neutral placeholder when battery data is unavailable',
      (tester) async {
    await pumpDashboard(tester, {
      'status': {
        'soc': null,
        'charging': null,
      },
    });

    expect(find.text('FAHRZEUGSTATUS'), findsOneWidget);
    expect(find.text('–'), findsNWidgets(4));
    expect(find.text('0%'), findsNothing);
    expect(find.text('Ladestatus nicht verfügbar'), findsOneWidget);
  });

  testWidgets('formats charging detail labels and units in German',
      (tester) async {
    await pumpDashboard(tester, {
      'last_charge': {
        'soc': 72.5,
        'kwh': 24.56,
        'price': 0.389,
      },
    });

    expect(find.text('Akkustand'), findsOneWidget);
    expect(find.text('72.5 %'), findsOneWidget);
    expect(find.text('Geladene Energie'), findsOneWidget);
    expect(find.text('24.6 kWh'), findsOneWidget);
    expect(find.text('Preis pro kWh'), findsOneWidget);
    expect(find.text('0.389 €/kWh'), findsOneWidget);
  });
}
