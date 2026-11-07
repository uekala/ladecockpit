import 'package:flutter_test/flutter_test.dart';
import 'package:ladecockpit_mobile/main.dart';

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
}
