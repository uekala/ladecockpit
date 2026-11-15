import 'package:material_ui/material_ui.dart';

/// Lets the pages of an invoice or a report be enlarged with two fingers.
/// Unzoomed, the list inside scrolls as before.
class Zoomable extends StatelessWidget {
  const Zoomable({super.key, required this.child, this.maxScale = 5});

  final Widget child;
  final double maxScale;

  @override
  Widget build(BuildContext context) => ClipRect(
        child: InteractiveViewer(
          minScale: 1,
          maxScale: maxScale,
          child: child,
        ),
      );
}
