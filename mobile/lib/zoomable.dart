import 'package:material_ui/material_ui.dart';

/// Lässt die Seiten einer Rechnung oder eines Berichts vergrößern: mit zwei Fingern oder mit einem
/// Doppeltipp, der auf die angetippte Stelle hinein- und wieder herauszoomt. Nicht gezoomt scrollt
/// die Liste darin wie bisher.
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
    // Die angetippte Stelle bleibt, wo sie ist, während alles um sie herum wächst.
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
