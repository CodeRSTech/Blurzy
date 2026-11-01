# Detection services

Source: `src/app/application/services/detection`

Detection finds objects in video frames. The Application side does not run the
neural network; it **decides when detection may start, hands frames to a
worker, and files the results into annotation layers**. There are two paths:
detect the frame on screen, or detect the whole video in the background.

| Part | Plain-language role |
| --- | --- |
| `DetectionService` | Entry point: model choice, start/validate background runs, receive batches |
| `DetectionExecutionService` | The one-frame path |
| `DetectionBatchProcessor` | Filters one worker batch and writes it into layers A and B |
| [Engine manager](../managers.md) | Creates or updates the session's `DetectionEngine` |
| [Detection worker](../../infrastructure/detection/worker.md) | Background thread that reads frames and runs the engine |

Layer A holds the detector output that passed the label/confidence filters;
layer B is the reviewable copy seeded from it. Machine output and manual edits
stay separate; see [Video layers](../../domain/video.md).

## Whole-video detection

![Sequence: the handler starts DetectionService, which clears layers, prepares the engine and starts the worker; batches return and are processed into A and B](../../../assets/api/app_services/detection-run-light.svg#only-light)
![Sequence: the handler starts DetectionService, which clears layers, prepares the engine and starts the worker; batches return and are processed into A and B](../../../assets/api/app_services/detection-run-dark.svg#only-dark)

Arrows are calls or signals in time order. `DetectionService` connects only
`batch_ready` and `progress_updated`; **the UI handler connects
`finished_processing` and `error_occurred`** and owns the dialogs.

1. **Reject bad requests.** A session with a running detection worker raises
   `WorkerAlreadyRunningException`; a null model name raises
   `NullModelNameException`. Both are logged as warnings first.
2. **Clear all layers (A-D)** of the session. A new run never mixes with stale
   output, **including tracks (C/D) and manual edits** in B and D.
3. **Create or update the engine** through the engine manager. A missing engine
   afterwards raises `RuntimeError`.
4. **Create, connect, and start** the worker; it is stored on the session.
5. **Batches arrive.** The worker emits `batch_ready` every **30 frames** (plus
   a final partial batch) and the service passes each to the batch processor.
   A `KeyError` (for example the session was closed meanwhile) drops that
   batch silently.
6. **Progress** is only logged by the service; the handler updates the
   progress bar.

!!! warning "Failure paths"
    Start failures reach the handler as exceptions and become an error dialog.
    A worker-side failure is signalled through `error_occurred`, handled by the
    handler. The service does not retry or roll back partial A/B data.

## What happens to one batch

![Flow: skip frames that already have A boxes; otherwise map, filter, add to A, replace machine boxes in B, and report counts](../../../assets/api/app_services/detection-batch-light.svg#only-light)
![Flow: skip frames that already have A boxes; otherwise map, filter, add to A, replace machine boxes in B, and report counts](../../../assets/api/app_services/detection-batch-dark.svg#only-dark)

Arrows follow one frame's decisions; the final report counts frames and boxes.

- A frame whose layer A already has boxes is **skipped**, never overwritten.
  After a normal start the layers were just cleared, so skips are rare.
- Raw `DetectionResult` values become box values, then pass the session's
  **chosen labels** (an empty list means all classes) and **minimum detection
  confidence**. Layer B's predicate is used for both layers.
- Filtered boxes are **added to A** and **replace the machine boxes in B**;
  manual B boxes survive the replacement.

!!! example "Worked example"
    Labels = `person`, minimum confidence 0.5. A frame yields a `person` at
    0.9, a `person` at 0.3, and a `car` at 0.95. Only the first reaches A and
    B, so that frame adds one box to `written_boxes`.

## Current-frame detection

![Flow: skip if no model or undecodable frame; otherwise detect, filter, add to A and replace machine boxes in B](../../../assets/api/app_services/detection-single-light.svg#only-light)
![Flow: skip if no model or undecodable frame; otherwise detect, filter, add to A and replace machine boxes in B](../../../assets/api/app_services/detection-single-dark.svg#only-dark)

`DetectionService.detect_current_frame_and_populate_layer_b_at_current_index`
(a legacy name) delegates to `DetectionExecutionService`. It runs in the
caller's thread, so it blocks until the engine returns. Unlike the batch path
it **does not skip a frame that already has A boxes**: it adds boxes to A and
refreshes B's machine boxes even when the frame was initialised earlier.

!!! note "Quiet returns"
    A null model or an undecodable frame is logged and the method returns
    without raising, so the UI sees no error.

## Changing the model

`set_detection_model_for_session_id` stops and detaches any running worker,
calls `session.reset_model`, then creates/updates the engine. Switching models
**clears layers B and D** (keeping manual boxes only when requested); choosing
`"None"` clears **all** layers and removes the engine.

Interchange of detection layers (JSON/CSV) is separate; see
[Layer services](layers.md). Model integration is described in
[Detection engine](../../infrastructure/detection/engine.md). API contracts:
[generated reference](../../../reference/api/index.md).
