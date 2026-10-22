# Qt widgets

Source: `src/app/ui/qt/widgets/`

Custom widgets provide reusable controls and the video preview surface.
`PreviewContainer` composes the video display and interactive annotation
overlay; the overlay handles box drawing, hit testing, selection, and edit
gestures, while handlers route resulting actions into the application. These
widgets render and collect interaction rather than owning annotation data.

## Packages

- [Feedback widgets](widgets/feedback.md)
- [Preview](widgets/preview.md)
- [Bounding-box preview layer](widgets/preview/layer_bbox.md)

The containing [Qt sections](sections.md) and [handlers](../handlers.md)
connect widgets to the rest of the UI. Related transient interaction data is
described in [UI view state](../view_state.md).
