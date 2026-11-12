import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:ladecockpit_mobile/main.dart';

void main() {
  testWidgets('sets the Ladecockpit app title', (tester) async {
    await tester.pumpWidget(const LadecockpitApp());
    final app = tester.widget<MaterialApp>(find.byType(MaterialApp));
    expect(app.title, 'Ladecockpit');
  });
}
