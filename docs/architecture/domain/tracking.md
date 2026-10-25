# Tracking domain

Source: `src/app/domain/tracking`

`TrackingStrategy` names the algorithm selected for a session; it does not
implement association. Runtime options live in
[`ProcessingSettings`](export.md): detection source layer, IoU/confidence
thresholds, confidence decay, optional appearance embedding size, offline
stitching and GSI gap/smoothness, and privacy-oriented post-processing.

Tracking starts from frame-indexed detection boxes. Application validates the
source (normally editable Layer B, with A also available), then the
infrastructure worker associates boxes into identity-bearing tracks. Output
separates detection-backed observations from coast/interpolation estimates.
Application stores machine results in Layer C and keeps the user-editable
result in Layer D; see the [four-layer model](video.md) and
[Tracking services](../application/services/tracking.md).

The four currently selectable behaviors—Hungarian IoU, ByteTrack, DeepSORT,
and BoT-SORT—and the later tracklet/GSI/privacy passes are described in
[Tracking infrastructure](../infrastructure/tracking.md).
