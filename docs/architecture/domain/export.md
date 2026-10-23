# Export domain

Source: `src/app/domain/export`

`ProcessingSettings` is the mutable per-session configuration snapshot shared
by detection, tracking, and rendering workflows. It groups model and label
selection, confidence and tracking parameters, privacy controls, preview
choices, and export blur options. It describes configuration; it does not
perform inference or write video.

Settings travel with the [session state](session.md) and are captured in
[project documents](project.md). Application services consume them for
[tracking](../application/services/tracking.md) and
[export](../application/services/index.md); video output is rendered by the
Application export service.
