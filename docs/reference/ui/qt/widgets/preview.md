# Preview widgets

Source: `src/app/ui/qt/widgets/preview/`

`PreviewContainer` composes the video display with the interactive
annotation-overlay widget. The video widget presents the current frame; the
overlay maps image coordinates into widget space for drawing and hit testing,
then emits user actions for handlers to apply through Application workflows.
Preview-only mask and blur presentation is separate from exported-video
render settings.

The overlay's geometry and edit state are described in
[Bounding-box preview layer](preview/layer_bbox.md); its presentation state is
in [UI view state](../../view_state.md). The [main window](../window.md) owns
the surrounding layout.
