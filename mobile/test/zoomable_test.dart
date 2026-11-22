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

    // Ein Finger: Die Liste scrollt wie bisher.
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

  testWidgets('a double tap zooms in and a second one back out', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Zoomable(
          child: ListView(children: const [
            SizedBox(key: ValueKey('page'), height: 400),
          ]),
        ),
      ),
    ));
    final page = find.byKey(const ValueKey('page'));
    final before = tester.getRect(page);
    final spot = before.center;

    await tester.tapAt(spot);
    await tester.pump(const Duration(milliseconds: 60));
    await tester.tapAt(spot);
    await tester.pumpAndSettle();
    final zoomed = tester.getRect(page);
    expect(zoomed.width, closeTo(before.width * 2.5, 1));
    // Die angetippte Stelle bleibt unter dem Finger.
    expect(zoomed.center.dx, closeTo(spot.dx, 1));

    await tester.tapAt(spot);
    await tester.pump(const Duration(milliseconds: 60));
    await tester.tapAt(spot);
    await tester.pumpAndSettle();
    expect(tester.getRect(page).width, closeTo(before.width, 1));
  });
}
