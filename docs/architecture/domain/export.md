# Export domain

Source: `src/app/domain/export`

`ProcessingSettings` is the mutable per-session configuration used by
detection, tracking, preview, and render workflows. It is configuration data,
not a worker or algorithm. Settings are exposed to widgets through a view-model
snapshot and saved/restored as part of project session data.

| Group | Examples | Used by |
| --- | --- | --- |
| Detection | Model name, minimum detection confidence, selected labels | Engine selection and A/B result filtering |
| Tracking | Strategy, source layer, minimum IoU, tracker-confidence floor, confidence decay | Input selection, association, and coast retention |
| Offline refinement | Stitching toggle, maximum gap, GSI smoothness | Linking tracklets and interpolating missing frames |
| Privacy coverage | Shrink resistance, pre/post padding seconds, safety padding percentage | Post-processing boxes in tracking output |
| Preview | Draw outlines, outline width, preview mask, live preview blur | Editor presentation only |
| Render | Export blur enabled and blur strength | Blurred video output |

The domains are intentionally distinct: turning on an outline or preview mask
does not enable exported blur, and render settings do not redefine tracking
input. Numeric settings are validated when created; the currently supported
Re-ID dimensions are 128, 256, or 512. See
[Tracking infrastructure](../infrastructure/tracking.md) for how tracking and
privacy options affect generated boxes,
[Application export](../application/services/index.md) for video rendering,
and [Session](session.md) for per-video state ownership.

The initial privacy defaults are coverage enabled = false, shrink resistance
enabled with a 0.85 damping factor, 0.5 seconds of padding before/after observed
tracks, and 10% safety inflation. Render blur starts disabled with a strength
of 15 pixels; the preview blur toggle is separate and also starts disabled.
These options express policy for a session, not a promise of detection
completeness.
