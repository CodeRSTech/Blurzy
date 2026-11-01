# Tracking strategies

Implementation: `src/app/infrastructure/tracking/tracking_strategy.py`,
`hungarian_tracker.py`, `bytetrack_strategy.py`, `deepsort_strategy.py`,
`botsort_strategy.py`

Given the boxes of frame 41 and the tracks known from frame 40, a **strategy**
answers: which box continues which track, which boxes are new subjects, and
which tracks lost their subject? Every strategy exposes the same small
contract, `update_frame(frame_idx, boxes, frame, embeddings)`, so the
[worker](worker.md) can swap them without caring how they decide.

## Where this sits

![The worker maps a strategy name to a strategy and calls update_frame once per frame; only the Hungarian strategy uses the HungarianIoUTracker engine](../../../assets/api/tracking_pipeline/stack-strategies-light.svg#only-light)
![The worker maps a strategy name to a strategy and calls update_frame once per frame; only the Hungarian strategy uses the HungarianIoUTracker engine](../../../assets/api/tracking_pipeline/stack-strategies-dark.svg#only-dark)

Solid arrows are calls; the dashed arrow means "only for this strategy". The
thick box is this page. The handler chooses a name; the worker looks it up in a
fixed map and **falls back to Dummy for an unknown name**.

## Vocabulary

| Term | Meaning |
| --- | --- |
| IoU | Overlap area divided by combined area of two boxes: 1 = identical, 0 = disjoint |
| Track | A subject's running state: box, velocity, confidence, ID |
| Coast | Keep a track alive by predicting its box while no detection matches |
| `detection_backed` | `True` when a detector actually saw the box this frame |
| `time_since_update` | Frames since the last real match (0 for observations) |

Worker settings shared by the strategies: `min_iou` (0.3), `min_tracker_confidence`
(0.1) and `confidence_decay` (0.05 per missed frame). ByteTrack also reads
`min_detection_confidence`.

## Hungarian IoU

The baseline. Each frame:

![Hungarian step: predict tracks by last velocity, build an IoU matrix, solve a global assignment, reject low IoU, then matched tracks update, unmatched tracks coast and unmatched detections start new tracks](../../../assets/api/tracking_pipeline/association-light.svg#only-light)
![Hungarian step: predict tracks by last velocity, build an IoU matrix, solve a global assignment, reject low IoU, then matched tracks update, unmatched tracks coast and unmatched detections start new tracks](../../../assets/api/tracking_pipeline/association-dark.svg#only-dark)

Arrows show order within one frame. The *Hungarian algorithm* finds the
assignment of detections to tracks with the best total overlap rather than
greedily taking the best pair first.

* Matching does not compare labels; only overlap above `min_iou` counts.
* A matched track gets confidence reset to 1.0 and a new velocity from its
  centroid movement.
* An unmatched track coasts: it moves by its last velocity, loses
  `confidence_decay`, and is pruned below `min_tracker_confidence`.
* It starts over at frame 0 (internal reset).

!!! note "Coasted boxes are emitted"

    The `TrackingWorker` class docstring says Hungarian "emits only observed
    boxes". The code emits coasted boxes too, flagged `detection_backed=False`
    with `time_since_update` greater than 0. [Post-processing](post-processing.md)
    relies on that flag.

![Sequence: frame 0 starts track-1 as observed; frame 1 has no boxes so track-1 coasts with age 1 and detection_backed false; frame 2 matches again and age returns to 0](../../../assets/api/tracking_pipeline/hungarian-example-light.svg#only-light)
![Sequence: frame 0 starts track-1 as observed; frame 1 has no boxes so track-1 coasts with age 1 and detection_backed false; frame 2 matches again and age returns to 0](../../../assets/api/tracking_pipeline/hungarian-example-dark.svg#only-dark)

Time flows downward. One person is occluded for one frame and keeps the same
ID.

## The three advanced strategies

![ByteTrack, DeepSORT and BoT-SORT each shown as a three-step left-to-right chain](../../../assets/api/tracking_pipeline/strategies-light.svg#only-light)
![ByteTrack, DeepSORT and BoT-SORT each shown as a three-step left-to-right chain](../../../assets/api/tracking_pipeline/strategies-dark.svg#only-dark)

Each row is one strategy; arrows are the order of its matching stages within a
frame.

=== "ByteTrack"

    **Use weak detections to rescue identities.** Blurzy wraps the Ultralytics
    implementation (an optional dependency; construction fails with
    `ModuleNotFoundError` if absent).

    * Each frame the confidence split is set from the frame's *median*
      detection confidence (capped at 0.5), so low-light clips do not discard
      everything as "weak".
    * Strong boxes match first; weaker boxes may then extend existing tracks.
    * An app-side fallback matches by GIoU and motion when the library output
      would break or alias an identity.

    It does not use appearance.

=== "DeepSORT"

    **Recent tracks get first claim; appearance rescues the rest.** This is an
    in-house implementation (a legacy external backend is kept only for the old
    batch API).

    * Constant-velocity prediction; confirmed tracks are matched in order of
      age with IoU plus appearance cost.
    * A wider-radius recovery pass accepts unambiguous appearance matches;
      tentative tracks then use IoU only.
    * Appearance memory per track is an exponential average plus its last 30
      *isolated* vectors; the distance used is the minimum over them.
    * Coast limit defaults to `round(1 / confidence_decay)` frames (20 at 0.05).

=== "BoT-SORT"

    **Predict with a Kalman filter, match in confidence stages.**

    * State is centre, width, height and their velocities, so box *size*
      changes are predicted too.
    * Tracks start only from detections scoring at least `max(0.5, min_confidence)`.
    * High-confidence boxes match by IoU gated by appearance; remaining tracks
      then try Re-ID (cosine distance at most 0.25, with at least a 0.08 margin
      over competitors) within a size- and speed-scaled radius.
    * Low-confidence boxes finally extend tracks by motion only.
    * Coast limit is 30 frames or when confidence falls below the floor.

=== "Dummy"

    **No tracking.** Copies detections and retags them as tracking output. It
    is useful for debugging the pipeline, not for keeping identities.

Without a readable video (or with an unusable crop) the appearance-aware
strategies receive `None` vectors and fall back to motion and overlap; they
never invent appearance from geometry.

## Choosing

| Situation | Reasonable choice |
| --- | --- |
| Quick, predictable, clean detections | Hungarian IoU |
| Flickering confidence, partial occlusion | ByteTrack |
| Subjects that cross or reappear in distinct clothing | DeepSORT or BoT-SORT |
| Changing apparent size (people walking toward the camera) | BoT-SORT |

!!! warning "Guidance, not measured benchmarks"

    The table summarises each algorithm's design. The repository does not ship
    accuracy measurements, so try strategies on your own footage.

All outputs, whatever the strategy, go through the same
[post-processing](post-processing.md), which can reconnect fragments the
strategy left apart.
