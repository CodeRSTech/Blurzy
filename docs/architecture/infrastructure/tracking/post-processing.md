# Tracking post-processing

Implementation: `src/app/infrastructure/tracking/post_processor.py`

A strategy decides frame by frame with only the past in view. A person hidden
by a pillar for a few frames may come back under a new ID, leaving two broken
tracks and a gap with no blur. **`TrackingPostProcessor` runs once, after every
frame has been seen**, so it can use the future to repair the past. It works on
plain boxes and vectors; it knows nothing about Qt or layers.

## Where this sits

![The worker passes the raw frame map to TrackingPostProcessor; the service later reads the result and the result processor writes Layers C and D](../../../assets/api/tracking_pipeline/stack-post-light.svg#only-light)
![The worker passes the raw frame map to TrackingPostProcessor; the service later reads the result and the result processor writes Layers C and D](../../../assets/api/tracking_pipeline/stack-post-dark.svg#only-dark)

Solid arrows are calls or data flow. The thick box is this page. Post-processing
runs on the worker thread, inside `run()`.

!!! warning "Settings errors appear late"

    The post-processor is constructed in `run()` only after the whole frame loop
    finishes, so an invalid setting (`ValueError`) is reported through
    `error_occurred` after the full pass, not when the worker is constructed.
    See [the worker page](worker.md#stopping-and-failure).

## The stages

![Strategy output; keep observations; split into tracklets; link tracklets; fill gaps with GSI; bounded coast tails; optional privacy coverage; final frame map](../../../assets/api/tracking_pipeline/postprocess-light.svg#only-light)
![Strategy output; keep observations; split into tracklets; link tracklets; fill gaps with GSI; bounded coast tails; optional privacy coverage; final frame map](../../../assets/api/tracking_pipeline/postprocess-dark.svg#only-dark)

Arrows are the order of processing; the dashed box is optional.

1. **Keep observations.** Only boxes with `detection_backed=True` and
   `time_since_update == 0` survive. Predictions made by the strategy are
   dropped here and may be re-created below.
2. **Split into tracklets.** A *tracklet* is an unbroken run of frames for one
   ID. An ID that disappears and returns yields several tracklets.
3. **Link.** Pair earlier tracklets with later ones (below).
4. **Fill gaps (GSI).** Interpolate boxes across each accepted link.
5. **Coast tails.** Add short bounded predictions after unlinked ends.
6. **Privacy coverage** (optional).

Linked tracklets are renamed to the earliest tracklet's ID, colour and key.

## Linking tracklets

A link joins tracklet *A* (ending first) to tracklet *B* when all of these hold:

| Check | Rule |
| --- | --- |
| Gap | 1 to `max_stitch_gap` missing frames (default 25, up to 60) |
| Class | Same label at the end of A and start of B |
| Appearance | If both have vectors, cosine similarity at least 0.45 |
| Geometry | Both end boxes projected by motion to the gap's midpoint must overlap (GIoU above 0), unless appearance is strong (at least 0.75) |
| Scale | Box areas within 2x (3x if overlap is good or appearance strong; 6x in privacy or anti-shrink mode) |
| Cost | A weighted cost of geometry, appearance and size at most 0.35 |
| Ambiguity | No competing link within 0.05 of the chosen cost |

All candidates are solved together with the Hungarian algorithm, so one
tracklet cannot be claimed twice. If two candidates are nearly tied, **neither
is linked**: leaving a gap is preferred to swapping two people.

![Sequence: tracklet A ends at frame 10 and B starts at 14; the link solver accepts; GSI fills frames 11 to 13 with boxes marked not detection-backed; B is renamed to A's ID; coast tails are added; the final map returns](../../../assets/api/tracking_pipeline/gap-example-light.svg#only-light)
![Sequence: tracklet A ends at frame 10 and B starts at 14; the link solver accepts; GSI fills frames 11 to 13 with boxes marked not detection-backed; B is renamed to A's ID; coast tails are added; the final map returns](../../../assets/api/tracking_pipeline/gap-example-dark.svg#only-dark)

Time flows downward. This is an illustrative timeline, not recorded output.

??? example "Frames 10-14 in a table"

    | Frame | Evidence | If the link is accepted |
    | --- | --- | --- |
    | 10 | Last observation of A | Kept as observed |
    | 11-13 | Nothing | Three GSI boxes under A's ID, `detection_backed=False` |
    | 14 | First observation of B | Kept, relabelled with A's ID |

    If any check fails, 11-13 receive no GSI boxes. A short coast tail may still
    follow frame 10.

## Gaussian-smoothed interpolation (GSI)

For each missing frame, each endpoint box is projected forward or backward by
its local motion; the two estimates are blended with Gaussian weights so the
nearer endpoint counts more:

$$
w_L = \exp\left(-\frac{d_L^2}{2\sigma^2}\right), \qquad
w_R = \exp\left(-\frac{d_R^2}{2\sigma^2}\right), \qquad
B_t = \frac{w_L\widehat{B}_{L,t}+w_R\widehat{B}_{R,t}}{w_L+w_R}
$$

$d_L$ and $d_R$ are frame distances to the observed endpoints and $\sigma$ is
`gsi_smoothness` (default 10). Because it uses a later observation it is an
*offline reconstruction*, not a live prediction and not detector output.

## Coast tails

Where there is no accepted bridge, the post-processor adds predictions after a
tracklet ends:

| Stitching | Tail |
| --- | --- |
| Enabled (default) | At most 6 frames, confidence decays at twice `confidence_decay`, stops when it would fall below `min_tracker_confidence` |
| Disabled | No links or GSI; the strategy's own coasts are kept (those above the confidence floor), plus tails to the end of the video |

A tail stops early when a detected box of the same class appears in that frame,
so it never adds a ghost beside a different subject. Tails also stop at the
next fragment of the same ID.

## Privacy coverage

Off by default. When enabled it runs last and only widens coverage:

| Control | Effect |
| --- | --- |
| Shrink resistance | Boxes expand immediately but contract slowly (default 0.85) |
| Pre/post padding | Extra boxes before the first and after the last observation (default 0.5 s each, up to 5 s) |
| Safety padding | Enlarges each box (default 10 %, up to 50 %) and clamps to the frame |

!!! warning "Coverage is not completeness"

    These controls enlarge or extend existing tracks. They cannot find a subject
    the detector never saw, and generated boxes are not ground truth.

??? example "Units"

    At 30 FPS, 0.5 s is 15 frames on each side. A 100 x 200 px box with 10 %
    safety padding becomes about 110 x 220 px before clipping, with the extra
    split evenly across opposite edges.

## Outputs

The result is a frame-sorted map from `0` to `total_frames - 1`. Observed boxes
keep their detector data; generated boxes (GSI, coasts, padding) carry
`detection_backed=False`. Application writes it to Layer C and refreshes D; see
[Tracking services](../../application/services/tracking.md).
