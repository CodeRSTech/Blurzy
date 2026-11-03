# Tracking worker

Implementation: `src/app/infrastructure/tracking/track_worker.py`

Tracking a whole video takes longer than a window can stay frozen.
`TrackingWorker` runs the slow loop on a background thread: it reads frames in
order, asks the selected [strategy](strategies.md) to assign IDs, then repairs
the tracks with [post-processing](post-processing.md). It reports progress with
Qt signals and **never touches widgets or annotation layers**. Application
decides what happens to its output; see
[Tracking services](../../application/services/tracking.md).

## Where this sits

![The worker thread inside the tracking stack: handler connects signals, adapter and facade call the service, the manager creates the worker and attaches it to the session](../../../assets/api/tracking_pipeline/stack-worker-light.svg#only-light)
![The worker thread inside the tracking stack: handler connects signals, adapter and facade call the service, the manager creates the worker and attaches it to the session](../../../assets/api/tracking_pipeline/stack-worker-dark.svg#only-dark)

Solid arrows are calls; the dashed arrow is signals from the worker back to the
handler. The thick box is the subject of this page.

## Who creates and owns it

![GUI thread contains the manager, handler and service; the worker thread runs the worker's run method and the selected strategy; manager creates the worker, signals return to the handler, and the service reads results with get_tracked_data](../../../assets/api/tracking_pipeline/ownership-light.svg#only-light)
![GUI thread contains the manager, handler and service; the worker thread runs the worker's run method and the selected strategy; manager creates the worker, signals return to the handler, and the service reads results with get_tracked_data](../../../assets/api/tracking_pipeline/ownership-dark.svg#only-dark)

Solid arrows are calls; the dashed arrow is Qt signals. Only `run()` and the
strategy it calls execute on the worker thread.

* `TrackingWorker` **is a `QThread`**. `start()` runs `run()` on the new thread.
* `TrackingWorkerManager` creates it (with `start=True`), stores it on the
  session, and clears Layers C and D first.
* The handler then connects `progress_updated`, `finished_processing` and
  `error_occurred`.
* `VideoReader` is opened inside `run()` and closed in its `finally`, so
  decoding also stays off the GUI thread.

!!! warning "Construction happens on the GUI thread"

    The constructor deep-copies the input detections, runs nested-box
    de-duplication on every frame, copies the settings, and builds the strategy
    **before the thread starts**. On long videos with many boxes this is
    GUI-thread work. A missing optional dependency (for example `ultralytics`
    for ByteTrack) raises `ModuleNotFoundError` here, so it surfaces as a
    start failure in the handler, not through `error_occurred`.

    See [Nested-box de-duplication](#nested-box-de-duplication).

## The lifecycle

![States: created, running, post-processing, completed, failed, stop requested, all converging on finished_processing](../../../assets/api/tracking_pipeline/states-light.svg#only-light)
![States: created, running, post-processing, completed, failed, stop requested, all converging on finished_processing](../../../assets/api/tracking_pipeline/states-dark.svg#only-dark)

Solid arrows are the normal path; dashed arrows are early exits. Every path
ends in `finished_processing()` because it is emitted from a `finally` block.

| Signal | Payload | When |
| --- | --- | --- |
| `progress_updated` | `(done, total)` | After each frame, and once more with the result's frame count when post-processing finishes |
| `error_occurred` | message | Any exception inside `run()` |
| `finished_processing` | none | Always, last |

!!! note "No progress during post-processing"

    The frame loop reports progress, then post-processing runs silently. The
    handler shows an indeterminate busy bar, so the UI looks idle for a moment
    on long clips before the final tick.

## One frame of the loop

![Per-frame steps: check stop flag, read frame, embed each box, update the strategy, store result, keep isolated appearance vectors, emit progress](../../../assets/api/tracking_pipeline/frame-step-light.svg#only-light)
![Per-frame steps: check stop flag, read frame, embed each box, update the strategy, store result, keep isolated appearance vectors, emit progress](../../../assets/api/tracking_pipeline/frame-step-dark.svg#only-dark)

Arrows show the order of one iteration; the dashed arrow leaves the loop.

* **Reading.** A `VideoReader` is created only if the session path is a real
  file. Otherwise tracking continues without pixels: every embedding is `None`
  and appearance cannot help.
* **Embedding.** Each box is cropped and described by the
  [appearance embedder](reid.md); the vectors are passed to every strategy.
* **Isolated appearance.** For post-processing the worker keeps a vector only
  for observed boxes whose IoU with every other box in the frame is below
  0.25. Overlapping subjects would otherwise contaminate each other's
  appearance.

## Stopping and failure

!!! warning "`stop()` only sets a flag"

    `stop()` does not interrupt anything. It sets `_stop_requested`; the loop
    checks the flag at the *start of the next frame* and returns. Meanwhile the
    manager has **already detached** the worker from the session, so the stopped
    worker's result is never fetched. The call sites are session close and the
    export-all job; the tracking panel has no stop button. The flag is not
    checked during post-processing: a stop requested then lets post-processing
    run to completion.

    The class docstring calls `stop()` "reserved for future use"; the code and
    callers above show it is used.

![Failure paths: a missing dependency fails in the constructor and is shown by the start handler; run-time failures emit error_occurred then finished_processing; a stop emits only finished_processing; the handler still syncs the cache](../../../assets/api/tracking_pipeline/failures-light.svg#only-light)
![Failure paths: a missing dependency fails in the constructor and is shown by the start handler; run-time failures emit error_occurred then finished_processing; a stop emits only finished_processing; the handler still syncs the cache](../../../assets/api/tracking_pipeline/failures-dark.svg#only-dark)

Solid arrows are the failure paths; "no error" marks a stop that is not a
failure. The handler owns the dialog.

!!! danger "`finished_processing` also fires after an error"

    The handler's `finished_processing` slot unconditionally calls
    `sync_tracking_cache()`. After an error the worker's tracked data is still
    empty, so **an empty result is written into Layer C and Layer D is
    refreshed from it**. The user sees an error dialog and then an empty
    Tracking tab. After a stop, the detached worker cannot be found, so the sync
    raises `TrackingWorkerNotFoundException` instead.

!!! note "Bad settings fail inside `run()`"

    The constructor docstring says `ValueError` for a bad post-processing
    setting is raised at construction. In the code the
    [post-processor](post-processing.md) is created inside `run()`, after the
    whole frame loop. A bad value therefore wastes the full pass and is
    reported through `error_occurred`, not as a constructor exception.

![Sequence for an unreadable video: the reader raises, the worker logs it, emits error_occurred then finished_processing, the handler shows a dialog and the service writes an empty result to C](../../../assets/api/tracking_pipeline/worker-error-light.svg#only-light)
![Sequence for an unreadable video: the reader raises, the worker logs it, emits error_occurred then finished_processing, the handler shows a dialog and the service writes an empty result to C](../../../assets/api/tracking_pipeline/worker-error-dark.svg#only-dark)

Time flows downward. This is the unreadable-video case: a file that exists but
cannot be decoded.

## Nested-box de-duplication

A detector can report a torso and a full body for the same person. Two boxes
would become two tracks and two IDs. `suppress_nested_same_class_boxes` runs per
frame in the constructor:

* Boxes are ranked by manual origin, confidence, then area. A box is merged
  into a kept same-label box that is at least as large and as confident when
  the intersection covers at least **80 %** of the *smaller* box (IoMin; IoU
  would under-rate a torso inside a body).
* Manual boxes are never suppressed.
* The suppressed box's bounds are unioned into the kept box so no pixel of the
  subject becomes uncovered. Inputs are cloned, not mutated.

![Sequence in which the worker constructor passes a frame with a full-body and a torso box to the suppressor, which merges them into one box with union bounds before the frame loop runs](../../../assets/api/tracking_pipeline/dedup-example-light.svg#only-light)
![Sequence in which the worker constructor passes a frame with a full-body and a torso box to the suppressor, which merges them into one box with union bounds before the frame loop runs](../../../assets/api/tracking_pipeline/dedup-example-dark.svg#only-dark)

Time flows downward. The strategy later sees one box where the detector
reported two.

??? example "Numbers"

    A full-body box of 891 x 1690 px and a torso box of 863 x 864 px overlap
    on 740,448 px². IoMin is about 0.993 (above 0.80) while IoU is only about
    0.49, so the torso is merged and the kept box grows 6 px to the left. The
    full worked arithmetic is in the function's API docstring.

## Reading the result

`get_tracked_data()` returns a deep copy under a mutex. `is_complete()` is
`True` only after post-processing stored the result; it stays `False` after an
error or a stop seen in the frame loop.

!!! info "Docstring correction"

    The class docstring says the Hungarian strategy emits "observed boxes
    only". In the code it also emits coasted (predicted) boxes with
    `detection_backed=False`; post-processing is what separates them. See
    [Tracking strategies](strategies.md#hungarian-iou).
