# Preview widgets

Source: `src/app/ui/qt/widgets/preview`

`PreviewContainer` composes the video display with the interactive
annotation-overlay widget. The video widget presents the current frame without
rasterized box outlines or captions; the overlay paints all annotation visuals
at canvas resolution. It maps image coordinates into widget space for drawing and hit testing,
then emits user actions for handlers to apply through Application workflows.
Preview-only mask and blur presentation is separate from exported-video
render settings.

Outlines and table data follow the active tab (B for detections, D for tracks).
Mask and live-blur regions instead follow the export source: populated D,
otherwise C, selected for the video as a whole rather than per frame. Live blur
also requires both the editor's preview-blur setting and Render's blur-enabled
setting; the mask is controlled independently. Do not infer that every visible
detection outline will be blurred merely because the Detection tab is active.
See the [export layer selection](../../../infrastructure/export.md) and
[getting-started workflow](../../../../getting-started.md).

The empty-state overlay is explicitly hidden when a frame is displayed and
restored when a message clears the frame. The stack uses `StackAll` to keep the
video and annotation layers visible together; selecting the annotation layer
alone does not hide the empty state.

The overlay's geometry and edit state are described in
[Bounding-box preview layer](preview/layer_bbox.md); its presentation state is
in [UI view state](../../view_state.md). The [main window](../window.md) owns
the surrounding layout.
