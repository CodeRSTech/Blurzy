# Bounding-box preview layer

Source: `src/app/ui/qt/widgets/preview/layer_bbox/`

`AnnotationOverlayWidget` is the Qt facade for drawing and editing boxes over
the video preview. Helper modules separate image/widget coordinate
conversion, hit testing and clamping, drag/pan state transitions, context
actions, and rendering. Selection and active tool state are UI presentation
state; committed annotation changes are sent through handlers to the
appropriate editable session layer.

See [Preview widgets](../preview.md) for composition,
[UI view state](../../../view_state.md) for transient selection/history, and
[Domain detection](../../../../domain/detection.md) for box origin values.
