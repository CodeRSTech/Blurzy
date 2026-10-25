# Tracking infrastructure

Source: `src/app/infrastructure/tracking`

Tracking turns detections from one selected layer into frame-indexed subject
tracks. The worker snapshots its input, processes frames on a background Qt
thread, then runs an offline refinement pass before exposing results to
Application services. Application validates the selected input (A or B) and
places the resulting machine output in C while maintaining editable D; see
[Tracking services](../application/services/tracking.md).

## The tracking pass

Before association, the worker suppresses nested same-class duplicates within
each frame. Containment is measured against the smaller box's area; suppressed
boxes are unioned into the retained bounds to preserve their visible coverage.
Each strategy then receives the boxes in frame order. Detection-backed outputs
are distinguished from coasted predictions with observation metadata, so later
processing can use actual observations without mistaking a prediction for one.

| Strategy | How it maintains identity | Practical distinction |
| --- | --- | --- |
| **Hungarian IoU** | Builds a track-to-detection IoU matrix and uses a global Hungarian assignment. Matches below the configured IoU threshold are rejected; unmatched detections start tracks, while unmatched tracks coast using their last centroid velocity and decay in confidence. | Simple motion/overlap baseline; active coast states are marked as predictions. |
| **ByteTrack** | Wraps Ultralytics' ByteTrack association. Blurzy adapts its confidence split to each frame, associates the stronger group first, then uses weaker detections to recover unmatched tracks. A bounded motion-based fallback reconciles IDs when library output cannot safely continue an identity. | Can use lower-confidence detections for association without treating every weak box as a new track. |
| **DeepSORT** | Gives recently observed confirmed tracks first claim in an age cascade using motion/IoU and appearance cost. It then tries unambiguous wider-radius appearance recovery, followed by tentative-track IoU matching. Per-track appearance memory uses normalized embeddings and is updated only from isolated observations. | Appearance can help recover a subject after larger movement or occlusion. |
| **BoT-SORT** | Predicts track position and size with a Kalman filter, matches high-confidence detections using overlap with gated appearance evidence, attempts conservative appearance re-identification for remaining tracks, then uses lower-confidence detections for motion-only recovery. | Combines Kalman motion, two confidence bands, and conservative Re-ID. |
| **Dummy** | Copies and retags detections as tracking output without associating identities across frames. | Useful as a pass-through/debug strategy, not persistent multi-object tracking. |

Hungarian, DeepSORT, and BoT-SORT create boxes for still-active unmatched
tracks with `detection_backed=False` and an increasing `time_since_update`.
ByteTrack also normalizes backend/coast outputs into that metadata. Downstream
post-processing uses this distinction to avoid treating a prediction as a new
observation.

DeepSORT and BoT-SORT use frame-derived appearance embeddings when a local
video can be read. Embeddings are aligned to the input boxes and only valid
crops contribute. Linking combines appearance with class, projected geometry,
box scale, and ambiguity checks; it does not equate similar appearance with
identity by itself. Configured embedding dimensions are 128, 256, or 512. If
the session path is missing or is not a file, tracking continues without
frame-derived appearance; an existing but unreadable file is a worker error.

## Offline stitching and GSI

With offline stitching enabled (the default), the post-processor extracts
continuous runs of observed boxes into tracklets. It considers later
same-class fragments with a gap no longer than the configured maximum (25
frames by default). Candidate links must pass projected geometry and scale
checks, and the global assignment is rejected when a competing link is too
ambiguous. Appearance embeddings can strengthen or reject a candidate.

For an accepted link, the same identity is carried across the gap and missing
boxes are interpolated from both endpoints. Each endpoint box is projected
toward the missing frame using its local motion estimate; Gaussian weights
make nearer endpoint estimates contribute more:

$$
w_L = \exp\left(-\frac{d_L^2}{2\sigma^2}\right), \qquad
w_R = \exp\left(-\frac{d_R^2}{2\sigma^2}\right)
$$

$$
B_t = \frac{w_L\widehat{B}_{L,t}+w_R\widehat{B}_{R,t}}{w_L+w_R}
$$

Here $d_L$ and $d_R$ are frame distances to the observed endpoints, $\sigma$
is the configured GSI smoothness, and each $\widehat{B}$ is that endpoint's
projected `xyxy` box. This is an offline operation: it uses a later observation
to refine earlier missing frames, so it is not a live prediction.

Unbridged tails are limited to six extra frames and decay confidence twice as
quickly as the configured per-frame penalty. When offline stitching is
disabled, the processor preserves causal strategy coasts and uses the normal
confidence decay instead; no cross-gap linking or GSI interpolation is done.

## Privacy-oriented coverage controls

When enabled, privacy post-processing runs after track stitching. It can:

- resist sudden box shrinkage by expanding immediately when boxes grow and
  damping contraction of a running width/height envelope;
- project a short configurable interval before the first observation and hold
  coverage after the last, using endpoint motion that is damped each frame;
- enlarge boxes by a configurable safety percentage and clamp them to known
  frame bounds.

Temporal padding is configured in seconds and converted using the video frame
rate. Generated padding confidence declines toward the configured floor.
These are conservative coverage heuristics, not a guarantee that detection
found every subject or that the resulting boxes are ground truth.
Defaults are stitching enabled, a maximum gap of 25 frames, GSI smoothness 10,
shrink resistance 0.85, 0.5 seconds of pre- and post-detection padding, and
10% safety padding. Settings validation allows gaps up to 60 frames, padding
up to five seconds on either side, and safety padding up to 50%.

The worker returns frame-indexed results only after processing completes;
Application writes those results to C and seeds/refreshes machine boxes in D
while preserving user-created D annotations. See the [tracking settings](../domain/tracking.md)
and [four annotation layers](../domain/video.md).
