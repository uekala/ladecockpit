import 'package:material_ui/material_ui.dart';

/// Lets the pages of an invoice or a report be enlarged: with two fingers, or with a
/// double tap that zooms in on the tapped spot and back out. Unzoomed, the list inside
/// scrolls as before.
class Zoomable extends StatefulWidget {
  const Zoomable({super.key, required this.child, this.maxScale = 5, this.doubleTapScale = 2.5});

  final Widget child;
  final double maxScale;
  final double doubleTapScale;

  @override
  State<Zoomable> createState() => _ZoomableState();
}

class _ZoomableState extends State<Zoomable> {
  final _controller = TransformationController();
  Offset _tapped = Offset.zero;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _toggle() {
    if (_controller.value.getMaxScaleOnAxis() > 1.01) {
      _controller.value = Matrix4.identity();
      return;
    }
    final scale = widget.doubleTapScale;
    // Keep the tapped spot where it is while everything around it grows.
    _controller.value = Matrix4.identity()
      ..translateByDouble(-_tapped.dx * (scale - 1), -_tapped.dy * (scale - 1), 0, 1)
      ..scaleByDouble(scale, scale, 1, 1);
  }

  @override
  Widget build(BuildContext context) => ClipRect(
        child: GestureDetector(
          onDoubleTapDown: (details) => _tapped = details.localPosition,
          onDoubleTap: _toggle,
          child: InteractiveViewer(
            transformationController: _controller,
            minScale: 1,
            maxScale: widget.maxScale,
            child: widget.child,
          ),
        ),
      );
}
