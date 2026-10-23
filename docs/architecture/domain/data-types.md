# Domain data types

Shared domain aliases describe common shapes passed between domain,
application, infrastructure, and UI code. They keep familiar concepts
consistent without introducing additional runtime objects.

| Type | Shape or role | Typical use |
| --- | --- | --- |
| `BBoxXYXYTuple` | Four integer pixel coordinates `(x1, y1, x2, y2)` | Box geometry used by detections, view models, annotation editing, and preview geometry. |
| `ListOfBoxes` | A list of `BBoxViewModel` values | Boxes for one frame, passed to table and rendering consumers. |
| `ListOfBoxesByFrameIndexAsDict` | Frame index to `ListOfBoxes` mapping | Per-frame detection or tracking data exchanged with tracking strategies and session services. |
| `RenderFunction` | Callback receiving a `SessionId` | Requests rendering for the session whose displayed frame changed. |
| `StopPlaybackFunction` | Callback with no arguments | Provides a playback-stop action to consumers that need it. |
| `ProcessingSettingsKwargs` | Partial mapping of settings names to typed values | Allows callers to update a subset of detection, tracking, privacy, preview, or render settings. |

These aliases describe boundaries and payloads; the owning domain packages
define the richer values such as `BBoxViewModel`, `SessionId`, and
`ProcessingSettings`. See [base types](base.md) and the generated API reference
for exact annotations and settings fields.
