# Detection worker

Source: `src/app/infrastructure/detection/worker`

Running a neural network on every frame of a video takes minutes. If that ran
on the GUI thread the window would freeze. `DetectionWorker` does the slow
loop on a background thread: it reads frames in order, asks the selected
[detection engine](engine.md) about each one, keeps the answers, and sends
batches and progress to the rest of the app through Qt signals.

Its job is deliberately narrow. **It never chooses annotation layers, edits
boxes, or touches widgets.** The Application
[detection service](../../application/services/detection.md) decides what
happens to the results; they become Layer A (original detector output) and
the machine part of Layer B (reviewed/editable detections). See
[Video layers](../../domain/video.md).

## Who creates and owns the worker

![The detection handler calls the Application facade, which delegates to DetectionService on the GUI thread; the service creates a DetectionWorker thread that reads frames and calls the engine](../../../assets/api/detection_worker/ownership-light.svg#only-light)
![The detection handler calls the Application facade, which delegates to DetectionService on the GUI thread; the service creates a DetectionWorker thread that reads frames and calls the engine](../../../assets/api/detection_worker/ownership-dark.svg#only-dark)

Solid arrows are calls or creation; the dashed arrow means "keeps a reference".
Boxes grouped under *GUI thread* run on the Qt event loop; the worker's
`run()` is the only code in this picture on the background thread.

* `DetectionWorker` **is itself a `QThread`** (not a plain object moved to a
  thread). Calling `start()` runs `run()` on the new thread. The class
  docstring's `moveToThread` example does not match the code or how the app
  uses it.
* `DetectionService` creates it through a factory, connects `batch_ready` and
  `progress_updated`, starts it, and stores it on the session. The handler
  then connects `progress_updated`, `finished_processing`, and
  `error_occurred` for UI feedback.
* Before creating it the service rejects a second run
  (`WorkerAlreadyRunningException`) or a missing model
  (`NullModelNameException`), then clears all layers and (re)creates the
  engine for the session.
* The `VideoReader` is opened inside `run()` and closed in its `finally`, so
  decoding also stays on the worker thread. The engine is shared by reference,
  not copied.

## The per-frame loop

![Flow of run(): check stop flag, read next frame, detect, cache under mutex, add to batch, emit a batch every 30 frames, emit progress, then loop; end of stream or stop flushes the partial batch and cleans up](../../../assets/api/detection_worker/frame-loop-light.svg#only-light)
![Flow of run(): check stop flag, read next frame, detect, cache under mutex, add to batch, emit a batch every 30 frames, emit progress, then loop; end of stream or stop flushes the partial batch and cleans up](../../../assets/api/detection_worker/frame-loop-dark.svg#only-dark)

Solid arrows are the normal path for one frame; dashed arrows leave the loop.
Diamonds are decisions.

1. **Check** `_stop_requested`; leave the loop if set.
2. **Read** the next frame. The reader's own frame index is used as the key.
   `EndOfVideoStreamException` marks the stream as complete, calls `stop()`,
   and leaves the loop.
3. **Detect** with `engine.detect(frame)`: one model call per frame.
4. **Cache** the result in `_detections_by_frame_index` while holding a
   mutex, and add it to the current batch.
5. **Batch**: at 30 frames emit `batch_ready` and start a new batch.
6. **Progress**: emit `progress_updated(done, total, ETA)` after every frame.

!!! note "The cache is written by the loop, read by others"

    The loop never looks results up, so there is no cache hit/miss decision
    inside it. The cache exists for outside callers: `get_detections(i)`
    returns a copy of one frame's list, or `None` when the frame is not yet
    processed; `get_all_detections()` returns a copy of everything. Both take
    the same mutex, so reads are safe while processing continues. The
    Application's batch path does not use them; it consumes `batch_ready`.
    The cache grows for the worker's lifetime (no eviction).

!!! example "A 65-frame video"

    | Batch | Zero-based frame indices | Frames in batch |
    | --- | --- | ---: |
    | First full batch | 0-29 | 30 |
    | Second full batch | 30-59 | 30 |
    | Final flush at stream end | 60-64 | 5 |

    A batch is **not** one 30-image model call: `detect(frame)` runs once per
    frame and results are only grouped for delivery.

## Signals, progress, and stopping

![Sequence: the GUI side starts the worker, which emits batch_ready every 30 frames and progress_updated per frame; stop() sets a flag, the worker finishes its frame, flushes the partial batch, and emits finished_processing](../../../assets/api/detection_worker/signals-light.svg#only-light)
![Sequence: the GUI side starts the worker, which emits batch_ready every 30 frames and progress_updated per frame; stop() sets a flag, the worker finishes its frame, flushes the partial batch, and emits finished_processing](../../../assets/api/detection_worker/signals-dark.svg#only-dark)

Arrows show who calls or emits to whom; time runs downward.

| Signal | Payload | Meaning |
| --- | --- | --- |
| `batch_ready` | session ID, `{frame index: detections}`, elapsed seconds | A batch for the service to store |
| `progress_updated` | frames done, total frames, ETA in ms | Position after each frame; independent of batches |
| `error_occurred` | message | An exception reached the worker's handler |
| `finished_processing` | none | `run()` is leaving; says nothing about success |

* The ETA is a running average since the start (elapsed / frames done ×
  frames left). When the frame count is unknown (`<= 0`) the total reported
  is the current frame and the ETA is `None`, although the signal is declared
  with a `float`.
* `batch_ready`'s time value is measured from the **start of the run**, not
  per batch, so it grows; the service only logs it.
* `stop()` only sets a flag. It is checked between frames, so the model call
  in flight completes first. `start()` on a running worker is a no-op, and a
  fresh `start()` resets the stop/complete flags.
* `is_complete()` is true only if the end of the stream was reached.
* Stopping happens via the session (closing it calls `stop()`; so does
  switching the detection model, which then drops its worker reference
  without waiting). Neither path joins the thread. Frames already delivered
  are not rolled back.

!!! warning "Thread delivery of the service slots"

    `DetectionService` is a plain Python object with `@Slot`-decorated
    methods, not a `QObject`. Its docstring says the batch slot runs on the
    main thread, but the code does not guarantee a queued hop to the GUI
    thread for these connections. Check this before adding anything in those
    slots that is not thread-safe. UI handler slots on `QObject`s do not have
    this issue.

## From batch to Layer A

![batch_ready reaches DetectionService, whose batch processor skips frames where Layer A already has boxes, otherwise filters by selected labels and minimum confidence and writes Layer A and refreshes machine boxes in Layer B](../../../assets/api/detection_worker/layer-a-flow-light.svg#only-light)
![batch_ready reaches DetectionService, whose batch processor skips frames where Layer A already has boxes, otherwise filters by selected labels and minimum confidence and writes Layer A and refreshes machine boxes in Layer B](../../../assets/api/detection_worker/layer-a-flow-dark.svg#only-dark)

Solid arrows are the data path; the dashed arrow is the skip.

For each frame the processor first checks whether Layer A already has boxes
there; if so the frame is skipped (A is never overwritten). Otherwise it maps
the results to boxes, keeps those that pass the session's chosen labels (empty
selection allows all) and minimum detection confidence, appends them to **A**,
and replaces the *machine* boxes in **B**, leaving manual boxes alone.
Because the service clears all layers before starting a run, skipping mainly
matters for repeated or overlapping batches. A batch for a session that was
just closed is silently dropped (`KeyError`).

## Failure and cleanup paths

![Two exits from run(): a stop or end of stream flushes the partial batch; an exception logs and emits error_occurred without flushing; both end in finally, which closes the reader and emits finished_processing](../../../assets/api/detection_worker/failure-light.svg#only-light)
![Two exits from run(): a stop or end of stream flushes the partial batch; an exception logs and emits error_occurred without flushing; both end in finally, which closes the reader and emits finished_processing](../../../assets/api/detection_worker/failure-dark.svg#only-dark)

Solid arrows are the exits; the dashed box is the normal stop path.

* **Stop or end of stream** → the partial batch **is** flushed, then cleanup.
* **Exception** (reading, `detect`, anything in the loop) → logged with its
  traceback, `error_occurred(str(e))` emitted, and the partial batch is
  **not** flushed. Earlier batches stay stored.
* **Always** → `reader.close()` then `finished_processing`. The handler uses
  it to clear the busy indicator and shows an error dialog only from
  `error_occurred`; the worker itself never opens dialogs.
* A provider may swallow its own inference errors (YOLO returns an empty
  list), so an empty result does not always mean "no objects"; see
  [Detection models](model.md).

!!! info "Limitations"

    No pause/resume, no retry of a failed frame, and no per-frame error
    isolation: one raised exception ends the run. Cancellation latency is one
    frame of decode plus inference.
