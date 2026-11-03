# Tracking infrastructure

Source: `src/app/infrastructure/tracking`

A detector looks at each frame on its own, so it cannot say that the person in
frame 40 is the same person as in frame 41. **Tracking adds that memory.** It
reads detections for every frame, decides which boxes belong to the same
subject, and gives each subject a stable ID and colour. Blurred export needs
this: you select a subject once and every frame of that subject is blurred.

This page is the map. Deeper pages cover each part:

| Page | Question it answers |
| --- | --- |
| [Tracking worker](tracking/worker.md) | How does the background thread run, report progress, stop, and fail? |
| [Tracking strategies](tracking/strategies.md) | How does each algorithm match boxes between frames? |
| [Appearance embeddings](tracking/reid.md) | How does the app describe what a subject looks like? |
| [Post-processing](tracking/post-processing.md) | How are broken tracks repaired after the frame loop? |

## Where this sits

![The tracking handler calls the Application facade and tracking service; the worker manager creates the tracking worker on a background thread; progress signals return to the handler and the result processor reads the finished data and writes Layers C and D](../../assets/api/tracking_pipeline/stack-overview-light.svg#only-light)
![The tracking handler calls the Application facade and tracking service; the worker manager creates the tracking worker on a background thread; progress signals return to the handler and the result processor reads the finished data and writes Layers C and D](../../assets/api/tracking_pipeline/stack-overview-dark.svg#only-dark)

Solid arrows are calls; the dashed arrow is Qt signals travelling back from the
worker thread. The thick box is this article's subject. Infrastructure only
computes tracks; **Application decides which layer receives them**. See
[Tracking services](../application/services/tracking.md) and the
[domain tracking settings](../domain/tracking.md).

!!! info "Layers touched"

    Tracking reads **Layer A** (original detections) or, normally, **Layer B**
    (reviewed detections). The finished tracks become **Layer C** (original
    tracking output) and seed **Layer D** (reviewed/editable tracks). Export
    prefers D and falls back to C. See [Video layers](../domain/video.md).

!!! warning "Starting tracking clears Layers C and D"

    Application clears both C and D *before* the worker is created. Manual
    edits in D from an earlier run are discarded at that moment, and if the
    run fails or is stopped the layers stay empty. Earlier documentation said
    D edits were preserved. The result processor does keep manual D boxes when
    it refreshes D, but after the start-time clear there are none to keep.

## The pipeline

![Pipeline: snapshot of Layer A or B, remove nested duplicates, frame loop, offline post-processing, optional privacy coverage, result held by the worker, Application writes Layer C and refreshes D](../../assets/api/tracking_pipeline/pipeline-light.svg#only-light)
![Pipeline: snapshot of Layer A or B, remove nested duplicates, frame loop, offline post-processing, optional privacy coverage, result held by the worker, Application writes Layer C and refreshes D](../../assets/api/tracking_pipeline/pipeline-dark.svg#only-dark)

Arrows show processing order; the dashed box is off by default. The frame loop
finishes completely before post-processing begins, so repairs can use frames
*after* a gap. Layer writes happen only at the end, in Application.

1. **Snapshot and de-duplicate.** The worker deep-copies the input and
   suppresses nested same-class boxes (a torso inside a full-body box).
2. **Frame loop.** For each frame the worker reads pixels, computes an
   appearance vector per box, and asks the chosen strategy to assign IDs.
3. **Post-processing.** Fragments of the same subject are linked, short gaps
   are filled, and short coast tails are added.
4. **Privacy coverage** (optional) enlarges and extends boxes for safer blur.

### Observed versus predicted boxes

Every output box says whether a detector actually saw it. `detection_backed`
is `True` for an observation; a *coasted* box is a prediction made while the
subject was missing, with `detection_backed=False` and `time_since_update`
counting missed frames. Post-processing keeps only observations
(`detection_backed` and age 0) when it rebuilds tracks, so a guess is never
mistaken for evidence.

## Choosing a strategy

| Strategy | Association evidence | Uses appearance to match? |
| --- | --- | --- |
| Hungarian IoU | Overlap with each track's predicted box | No |
| ByteTrack | Motion, strong then weak detections | No |
| DeepSORT | Motion/overlap in age order, appearance memory | When vectors exist |
| BoT-SORT | Kalman motion, confidence groups, appearance | When vectors exist |
| Dummy | None: copies detections | No |

Details and diagrams are in [Tracking strategies](tracking/strategies.md).
Appearance vectors are computed for **every** strategy, because
post-processing also uses them to stitch tracks (see
[Appearance embeddings](tracking/reid.md)).

## Worked example: one subject, end to end

Follow one person who walks behind a pillar. The numbers are illustrative.

![Sequence from the user clicking Track through handler, adapter and facade, service, worker manager and worker thread, back to the handler's sync and the service writing Layer C and refreshing D](../../assets/api/tracking_pipeline/e2e-light.svg#only-light)
![Sequence from the user clicking Track through handler, adapter and facade, service, worker manager and worker thread, back to the handler's sync and the service writing Layer C and refreshing D](../../assets/api/tracking_pipeline/e2e-dark.svg#only-dark)

Time flows downward; each arrow is a call or signal. The first half runs on
the GUI thread; only the worker's own box runs on the background thread.

??? example "Frame by frame"

    The detector saw the person in frames 0-10, lost them behind the pillar
    for frames 11-13, and found them again in frames 14-20 (Layer B).

    1. **Start.** Application checks that no tracker is running and that the
       source layer is A or B and not empty, seeds missing B frames from A,
       clears C and D, and builds the worker. The constructor copies the data
       and de-duplicates boxes (on the GUI thread).
    2. **Frames 0-10.** The strategy opens `track-1` and matches it each frame.
       Every box is observed.
    3. **Frames 11-13.** Nothing matches. The strategy emits predicted boxes
       with `detection_backed=False` and falling confidence.
    4. **Frame 14.** A new box appears. Depending on the strategy it may
       rejoin `track-1` or start `track-2`.
    5. **Post-processing.** If it became `track-2`, the linker sees one
       fragment ending at frame 10 and another starting at 14 (a three-frame
       gap), checks class, motion, size and appearance, and accepts. The ID
       `track-1` is carried across and frames 11-13 are filled by
       interpolation (see [Post-processing](tracking/post-processing.md)).
    6. **Finish.** `progress_updated` reports the final count,
       `finished_processing` fires, and the handler calls
       `sync_tracking_cache()`. Application writes the frame map into Layer C
       and refreshes Layer D from it.

## Limitations

!!! warning "Things to know"

    * Tracking quality is bounded by detection quality: a subject never
      detected is never tracked or blurred.
    * Stopping is cooperative and results of a stopped run are discarded; see
      [the worker lifecycle](tracking/worker.md#stopping-and-failure).
    * Gap filling and privacy padding add *estimated* boxes, not detector
      output. They improve coverage but are not ground truth.
