# Bounding-box preview layer

Source: `src/app/ui/qt/widgets/preview/layer_bbox`

`AnnotationOverlayWidget` is the Qt facade for drawing and editing boxes over
the video preview. Helper modules separate image/widget coordinate
conversion, hit testing and clamping, drag/pan state transitions, context
actions, and rendering. Selection and active tool state are UI presentation
state; committed annotation changes are sent through handlers to the
appropriate editable session layer.

Outline weight is a preview-only setting. The overlay scales its pen width
with the height of the currently displayed video rectangle (the setting is
interpreted relative to a 480-pixel display height), so the outline remains
legible as the preview is resized or zoomed. This does not change box geometry
or rendered-video output.

See [Preview widgets](../preview.md) for composition,
[UI view state](../../../view_state.md) for transient selection/history, and
[Domain detection](../../../../domain/detection.md) for box origin values.
