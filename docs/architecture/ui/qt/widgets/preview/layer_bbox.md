# Bounding-box preview layer

Source: `src/app/ui/qt/widgets/preview/layer_bbox`

`AnnotationOverlayWidget` is the Qt facade for drawing and editing boxes over
the video preview. Helper modules separate image/widget coordinate
conversion, hit testing and clamping, drag/pan state transitions, context
actions, and rendering. Selection and active tool state are UI presentation
state; committed annotation changes are sent through handlers to the
appropriate editable session layer.

All preview annotation outlines and captions are painted in widget coordinates,
not baked into the source video frame. This keeps 4K footage from shrinking
labels and outlines into near-invisible details when fitted into the editor.
Annotation colors match the table swatches; outlines have a dark contrast halo
and captions use white text on a dark backing.

Outline weight is a preview-only setting. The overlay scales its pen width
with the height of the currently displayed video rectangle (the setting is
interpreted relative to a 480-pixel display height), so the outline remains
legible as the preview is resized or zoomed. This does not change box geometry
or rendered-video output.
Caption text retains the current UI font size during zoom, with long captions
elided and positioned inside the visible canvas. Selection and edit handles
are painted above the ordinary annotations.

See [Preview widgets](../preview.md) for composition,
[UI view state](../../../view_state.md) for transient selection/history, and
[Domain detection](../../../../domain/detection.md) for box origin values.
