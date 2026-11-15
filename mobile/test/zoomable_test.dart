import 'package:flutter_test/flutter_test.dart';
import 'package:ladecockpit_mobile/zoomable.dart';
import 'package:material_ui/material_ui.dart';

void main() {
  testWidgets('two fingers enlarge the pages, one finger still scrolls them', (tester) async {
    final scroll = ScrollController();
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Zoomable(
          child: ListView.builder(
            controller: scroll,
            itemCount: 6,
            itemBuilder: (context, index) => Container(
              key: ValueKey('page-$index'),
              height: 400,
              margin: const EdgeInsets.all(8),
              color: Colors.white,
            ),
          ),
        ),
      ),
    ));
    final page = find.byKey(const ValueKey('page-0'));
    final before = tester.getRect(page).width;

    // One finger: the list scrolls as before.
    await tester.drag(find.byType(ListView), const Offset(0, -300));
    await tester.pump();
    expect(scroll.offset, greaterThan(100));
    await tester.drag(find.byType(ListView), const Offset(0, 600));
    await tester.pump();
    expect(scroll.offset, 0);
    expect(tester.getRect(page).width, before);

    // Two fingers moving apart: the page gets larger.
    final center = tester.getCenter(find.byType(Zoomable));
    final first = await tester.startGesture(center - const Offset(40, 0));
    final second = await tester.startGesture(center + const Offset(40, 0));
    await tester.pump();
    for (var i = 0; i < 6; i++) {
      await first.moveBy(const Offset(-20, 0));
      await second.moveBy(const Offset(20, 0));
      await tester.pump();
    }
    await first.up();
    await second.up();
    await tester.pumpAndSettle();
    expect(tester.getRect(page).width, greaterThan(before * 1.5));
  });
}
