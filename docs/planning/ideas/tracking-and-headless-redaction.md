# Tracking and Headless Redaction

## Current behavior

- Detection applies the current confidence/label filters before storing results in Layer A and refreshing machine-generated Layer B boxes. Labels are exact, case-sensitive matches; an empty Labels textbox permits all classes subject to the confidence filter. Existing manual Layer B annotations survive even when the frame was previously initialized as empty.
- Editing Labels refilters Layer B, not existing Layer A data. Classes excluded during detection require rerunning detection to become available; expanding Labels alone does not recover discarded results.
- Tracking requested from Layer B seeds any uninitialized, eligible frames from Layer A without replacing existing edits. Batch export falls back to Layer A when its configured tracking source is empty.
- Same-class nested detections are suppressed before tracker association with an IoMin containment threshold of 0.80; suppressed coordinates are unioned into the retained box so suppression does not expose subject pixels.
- Trackers distinguish detection-backed observations from coasted predictions. Offline stitching (default on) joins compatible tracklets across up to 25 missed frames and fills accepted gaps with GSI. Rejected or unbridged tails decay at twice the configured rate and are capped at six frames; disabling stitching uses causal coasting at the normal decay rate.
- The frame-aware `TrackingWorker` extracts configurable 128-, 256-, or 512-dimensional appearance embeddings for DeepSORT, BoT-SORT, and appearance-aware offline stitching. Hungarian and ByteTrack remain motion-based strategies.
- The optional Privacy Shield resists abrupt box shrinkage, preserves the head/top anchor when lower-body detections drop out, backfills a bounded interval before first detection, holds boxes after the last detection, and adds a clamped safety margin.
- ByteTrack adapts its high/low association thresholds to session settings and per-frame confidence, emits detector-qualified births immediately, and uses GIoU plus predicted-center distance to recover plausible fast-motion matches.
- Layer D machine boxes are refreshed from filtered Layer C output across the full video frame range after tracking, preserving manual boxes while removing stale machine tracks.
- Preview-only controls (box outlines, border width, blur-mask overlay, and optional live blur) are independent of Render controls. Export blur remains controlled by the Render panel, and disabling it gates live preview blur.

## Safety and limitations

Tracklet links use class agreement, bidirectional midpoint generalized IoU, scale similarity, one-to-one Hungarian assignment, and an ambiguity margin. Appearance-aware links can tolerate larger scale changes, while geometry-only Hungarian and ByteTrack associations cannot guarantee identity through ambiguous crossings. GSI changes only internal gaps; observed detections are preserved unless the optional Privacy Shield is enabled.

## Deferred ideas

- Forward-backward optical-flow verification for uncertain unbridged tails.
- A manual review workflow for long or ambiguous intervals; automated track IDs are not verified identities.
- Velocity-aware dilation of export masks beyond the configured Privacy Shield margin.
