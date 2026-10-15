# Tracking and Headless Redaction

## Current behavior

- Detection keeps raw model output in Layer A and applies the current confidence/label filters when seeding editable Layer B.
- New batch and current-frame detections eagerly populate uninitialized Layer B frames. The frame-view seeder remains as a compatibility path for older sessions.
- Tracking requested from Layer B seeds any uninitialized, eligible frames from Layer A without replacing existing edits. Batch export falls back to Layer A when its configured tracking source is empty.
- The tracker keeps coasted state internally for re-association but does not publish coast-only boxes. Completed tracks are post-processed in the tracking worker thread: compatible tracklets may be joined across gaps of at most 25 frames and bounded gaps are filled using bidirectional, Gaussian-weighted motion estimates.
- Layer D is seeded from Layer C after tracking, only for frames not already initialized, and with the current tracker-confidence filter.

## Safety and limitations

Tracklet links use class agreement, midpoint generalized IoU, area similarity, one-to-one Hungarian assignment, and an ambiguity margin. Appearance/Re-ID is not available, so geometry-only links cannot guarantee identity through ambiguous crossings. Interpolation is limited to gaps bracketed by linked observations; the processor does not extrapolate an unbridged tail or alter observed boxes.

## Deferred ideas

- Appearance embeddings/Re-ID for stronger long-occlusion identity matching.
- Forward-backward optical flow for misses with no later detection.
- Fixed high-birth/low-continuation confidence thresholds; existing user settings remain authoritative.
- Velocity-aware dilation of tracking boxes during export.
