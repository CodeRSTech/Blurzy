# Tracking and Headless Redaction

## Current behavior

- Detection applies the current confidence/label filters before storing results in Layer A and refreshing machine-generated Layer B boxes. Labels are exact, case-sensitive matches; an empty Labels textbox permits all classes subject to the confidence filter. Existing manual Layer B annotations survive even when the frame was previously initialized as empty.
- Editing Labels refilters Layer B, not existing Layer A data. Classes excluded during detection require rerunning detection to become available; expanding Labels alone does not recover discarded results.
- Tracking requested from Layer B seeds any uninitialized, eligible frames from Layer A without replacing existing edits. Batch export falls back to Layer A when its configured tracking source is empty.
- Same-class nested detections are suppressed before tracker association with an IoMin containment threshold of 0.80; suppressed coordinates are unioned into the retained box so suppression does not expose subject pixels.
- Trackers distinguish detection-backed observations from coasted predictions. Offline stitching (default on) joins compatible tracklets across up to 25 missed frames and fills accepted gaps with GSI. Rejected or unbridged tails decay at twice the configured rate and are capped at six frames; disabling stitching uses causal coasting at the normal decay rate.
- Layer D machine boxes are refreshed from filtered Layer C output across the full video frame range after tracking, preserving manual boxes while removing stale machine tracks.
- Preview-only controls (box outlines, border width, blur-mask overlay, and optional live blur) are independent of Render controls. Export blur remains controlled by the Render panel, and disabling it gates live preview blur.

## Safety and limitations

Tracklet links use class agreement, bidirectional midpoint generalized IoU, scale similarity, one-to-one Hungarian assignment, and an ambiguity margin. Strong projected overlap can tolerate area changes up to 3x for partial occlusion. Appearance/Re-ID is not available, so geometry-only links cannot guarantee identity through ambiguous crossings. GSI changes only internal gaps; observed detections remain untouched.

## Deferred ideas

- Appearance embeddings/Re-ID for stronger long-occlusion identity matching.
- Appearance embeddings/Re-ID and forward-backward optical flow for more robust identity matching.
- Fixed high-birth/low-continuation confidence thresholds; existing user settings remain authoritative.
- Velocity-aware dilation of tracking boxes during export.
