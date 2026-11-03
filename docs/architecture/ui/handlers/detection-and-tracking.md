# Detection, tracking, and model handlers

Implementation: `src/app/ui/handlers/detection_handler.py`, `src/app/ui/handlers/tracking_handler.py`, `src/app/ui/handlers/model_handler.py`

Detection finds objects in frames (layers **A** and **B**). Tracking links those
detections across frames into identities (layers **C** and **D**). Both are slow,
so they run in background `QThread` workers. Choosing which detection model to use
is a third, separate step handled by `ModelHandler`.

Handlers are the UI half of each workflow. They validate what the user may do
right now, start work through the Application facade, then listen to worker
signals and update progress bars, status text, dialogs, and the preview.

!!! info "Layers and ownership"
    A and C are machine output; B and D are the editable, reviewed copies seeded
    from them. Tracking reads A or B (B by default). Export prefers D and falls
    back to C. Handlers never write layers themselves; the services do. For the
    layer model see the [architecture overview](../../overview.md).

## Which actions touch which layers

| Action | Layers cleared | Layers written |
| --- | --- | --- |
| Detect current frame | none | A for this frame; machine boxes in B for this frame (manual B boxes kept) |
| Detect all frames (start) | **all of A, B, C, D, including manual boxes** | later, per batch: A and B, only for frames with no A boxes yet |
| Change model | B and D (manual boxes kept if "Keep manual annotations" is ticked); choosing `None` skips the dialog, keeps manual boxes in B and D, and fully clears A and C | none |
| Start tracking (start) | **all of C and D, including manual boxes** | on success: C; machine boxes in D |
| Confidence or label change | none | B re-filtered |

!!! danger "Starting a run discards edits"
    *Detect All Frames* clears every layer without a confirmation and without
    `keep_manual`. *Start Tracking* clears all of C and D, so manual track edits
    are lost. Only the incomplete-detection prompt can stop a tracking run; there
    is no "overwrite your edits?" prompt in either handler.

## Detection

`DetectionHandler` is connected to four right-panel controls:

| Control | Slot | Effect |
| --- | --- | --- |
| Detect (current frame) | `on_detect_current_frame` | one frame, synchronous |
| Detect All Frames | `on_start_background_detection` | whole video in a worker |
| Minimum confidence | `on_min_confidence_changed` | store setting, re-filter B, re-render |
| Chosen labels | `on_chosen_labels_changed` | store comma-separated labels, re-filter B, re-render; show the "tracking config is stale" warning if C already has boxes |

### Current frame (GUI thread)

![Detect current frame: the handler calls the facade, the execution service runs the engine on the GUI thread, filters results, writes layers A and B, and the handler re-renders](../../../assets/api/ui_handlers_workflows/detect_frame_sequence-light.svg#only-light)
![Detect current frame: the handler calls the facade, the execution service runs the engine on the GUI thread, filters results, writes layers A and B, and the handler re-renders](../../../assets/api/ui_handlers_workflows/detect_frame_sequence-dark.svg#only-dark)

Everything runs in the click handler, so the window is unresponsive while the
model infers on one frame. The execution service does nothing when the model is
`None`, and creates the engine if it does not exist yet. A `DomainException`
becomes a "Detection Failed" dialog logged as a warning; any other exception is
logged with a traceback and also shown.

### All frames (background worker)

![Detect all: handler starts the service, the service clears layers and starts DetectionWorker, the worker emits batch and progress signals to the GUI thread, and finished_processing ends the busy state](../../../assets/api/ui_handlers_workflows/detect_all_sequence-light.svg#only-light)
![Detect all: handler starts the service, the service clears layers and starts DetectionWorker, the worker emits batch and progress signals to the GUI thread, and finished_processing ends the busy state](../../../assets/api/ui_handlers_workflows/detect_all_sequence-dark.svg#only-dark)

Solid arrows are calls or signals; only the worker and its engine calls run off
the GUI thread.

1. **Handler.** Sets the progress bar busy, shows "Starting background
   detection...", and calls `start_detection_worker(s_id)` via the UI adapter.
2. **Service.** `DetectionService` rejects a start if a worker is already running
   (`WorkerAlreadyRunningException`) or no model is set (`NullModelNameException`),
   clears all layers, creates or updates the session's `DetectionEngine`, and
   creates the `DetectionWorker`. The engine is created on the **GUI thread**, so
   first-time model loading can block the window here.
3. **Worker.** The worker opens its **own** `VideoReader`, reads frames
   sequentially, runs `engine.detect()`, and emits `batch_ready` every 30 frames
   and `progress_updated(processed, total, eta_msecs)` after every frame.
4. **Batches.** The service's slot receives each batch and writes A and B for
   frames that do not already have A boxes, after applying the label and minimum
   confidence settings.
5. **Progress.** The handler shows the bar, "Detecting frames: N/M", and the ETA.
6. **End.** `finished_processing` always fires last, whether the run completed,
   was stopped, or failed. The handler turns the busy indicator off and refreshes
   the status bar.

![State machine for the detection progress indicator: Idle, Starting, Running, Failed, with a Rejected state where the busy indicator stays on](../../../assets/api/ui_handlers_workflows/detection_progress_states-light.svg#only-light)
![State machine for the detection progress indicator: Idle, Starting, Running, Failed, with a Rejected state where the busy indicator stays on](../../../assets/api/ui_handlers_workflows/detection_progress_states-dark.svg#only-dark)

Dashed arrows are error paths; red outlines mark states that show an error dialog.

!!! note "Why signals reach the GUI thread"
    The handler connects worker signals from the GUI thread, so Qt queues each
    emission onto the GUI event loop. The service's batch slot is a plain Python
    method, not a `QObject`; with PySide6 such a callable runs in the thread that
    made the connection. That is the GUI thread for a click in the window. See
    the limitation on batch export below.

!!! warning "Limitations (from source)"
    - **No cancel button.** Nothing in the UI calls `DetectionWorker.stop()`. A
      run ends by finishing, by failing, by a model change (which stops the old
      worker), or when the session closes.
    - **The preview does not refresh at the end.** Neither progress nor finish
      calls a frame render, so detections appear on the current frame when you
      next navigate or edit.
    - **Rejected starts leave the indicator on.** The handler turns the busy
      indicator on *before* calling the service and only turns it off in the
      worker-finished and worker-failed slots. An exception from the start call
      (already running, no model selected) shows the error dialog but does not
      reset the indicator.
    - **Layer A is filtered.** Both detection paths apply the label and confidence
      filter before writing layer A, so A holds filtered detector output.
    - The handler connects its signals *after* `start()`, so a worker that fails
      before that line would lose its signal.

## Choosing a model

![Model change: warning dialog, then ModelLoadWorker moved to a QThread loads the engine in the background and signals finished or failed back to the handler](../../../assets/api/ui_handlers_workflows/model_change_sequence-light.svg#only-light)
![Model change: warning dialog, then ModelLoadWorker moved to a QThread loads the engine in the background and signals finished or failed back to the handler](../../../assets/api/ui_handlers_workflows/model_change_sequence-dark.svg#only-dark)

`right_panel.model_changed` calls `ModelHandler.on_model_changed`.

1. **Warn.** Unless the user ticked "Don't ask again" or chose `None`, a
   `ModelChangeWarningDialog` explains that results will be cleared. It offers
   "Keep manual annotations" (ticked by default). Rejecting it resets the model
   combo to the session's previous model and stops.
2. **Load in the background.** The handler stores the new model name in the
   session settings and creates a `QThread` plus a `ModelLoadWorker`
   (`moveToThread`, `thread.started` runs the worker). The worker calls
   `Application.set_detection_model()`, which stops any running detection worker,
   clears B and D, and builds the engine, which loads the weights. Weights can
   be large, which is why this is off the GUI thread.
3. **Success.** `finished(s_id, name)` clears the detection table, updates the
   status bar, and re-renders.
4. **Failure.** `failed(s_id, name, error)` logs an error and shows "Model Load
   Failed".
5. **Cleanup.** `thread.finished` stops the loading spinner and deletes the
   worker and thread. `UIController.on_about_to_quit` calls `ModelHandler.close()`
   to wait for a running load.

!!! warning "Limitations"
    - A second model change while one is loading shows "Model Change Failed"
      ("A model is already loading.") but the combo box keeps the new selection.
    - The new model name is stored in settings **before** loading. If loading
      fails, the setting and the combo still show the new name and the layers
      were already reset. The UI does not roll back.

## Tracking

`TrackingHandler` owns the Start Tracking action and **a dozen tuning controls**
(strategy, source layer, IoU, confidence thresholds, stitching, smoothing,
privacy padding, ...). Each tuning slot stores one value with
`update_session_settings` and, if layer C already has boxes, shows the "settings
changed after tracking" warning. Changing the strategy also toggles the IoU
widgets (shown for Hungarian only). These slots do not run tracking.

### Guards before the worker starts

![Decision flow for Start Tracking: session must be active, tracking and detection must not be running, and incomplete detection coverage needs explicit confirmation](../../../assets/api/ui_handlers_workflows/tracking_guards-light.svg#only-light)
![Decision flow for Start Tracking: session must be active, tracking and detection must not be running, and incomplete detection coverage needs explicit confirmation](../../../assets/api/ui_handlers_workflows/tracking_guards-dark.svg#only-dark)

Dashed arrows lead out without starting. The "Action Not Allowed" dialogs say
to wait for tracking or detection to finish. Coverage counts frames that have an
entry in layer A, including frames whose result is empty. "Okay" and closing the
dialog both leave existing tracking untouched; only **Proceed Anyway** continues.

A missing selected or active session id raises `InvalidSessionIdException` out
of the slot, uncaught by the handler.

### The run

![Tracking run: handler calls the service, the manager clears C and D and starts TrackingWorker, progress signals update the UI, and on finish the handler syncs the cache into C and D](../../../assets/api/ui_handlers_workflows/tracking_sequence-light.svg#only-light)
![Tracking run: handler calls the service, the manager clears C and D and starts TrackingWorker, progress signals update the UI, and on finish the handler syncs the cache into C and D](../../../assets/api/ui_handlers_workflows/tracking_sequence-dark.svg#only-dark)

1. **UI first.** The handler sets the loading state, an indeterminate busy bar,
   and "Tracking in progress...", and hides the stale-settings warning.
2. **Service.** `TrackingWorkerManager.start` raises
   `TrackingWorkerAlreadyRunningException`, `EmptyLayerException` (nothing in the
   source layer), or `UnsupportedLayerException`. With source B it first seeds B
   from filtered A for frames that have no B entry. It then clears C and D and
   creates a `TrackingWorker` that **deep-copies** the source boxes and the
   settings, so later edits do not affect the run.
3. **Worker thread.** For each frame it reads the video (its own `VideoReader`),
   extracts appearance embeddings, and updates the selected strategy, emitting
   `progress_updated(current, total)`. After the last frame it runs post-processing
   (stitching, smoothing, padding, as configured) and stores the result under a
   mutex.
4. **Progress.** The first progress signal gives a determinate bar and
   "Tracking in progress: N/M".
5. **Finish.** `finished_processing` runs `_on_tracking_finished`, which calls
   `sync_tracking_cache` to copy the worker's result into **C** and the filtered
   machine boxes into **D**, ends the loading state, switches the bottom panel to
   the Tracking tab, and renders. Layers are only written at this point; a
   stopped or failed run leaves C and D empty because they were cleared at start.
6. **Failure.** `error_occurred` ends the loading state and shows "Tracking
   Error". Because `finished_processing` still follows, the finish slot also
   runs and attempts the sync; if the worker produced no result, the sync copies
   an empty result.

!!! warning "Limitations"
    - There is **no cancel control** for tracking in the UI.
    - Starting tracking erases all of D, including manual track edits.
    - If starting raises, the handler resets the loading state and shows "Tracking
      Failed!".
    - Like detection, signals are connected after `start()`.

## Threads at a glance

| Step | Thread |
| --- | --- |
| Handlers, dialogs, progress widgets, layer clearing, engine creation for Detect All, current-frame detection | GUI |
| Model weight loading (`ModelLoadWorker`) | background `QThread` |
| Frame reading and inference for Detect All (`DetectionWorker`) | its own `QThread` |
| Frame reading, tracking, post-processing (`TrackingWorker`) | its own `QThread` |
| Batch writes into A and B, tracking sync into C and D | GUI (queued signals) |

Layer data is protected by the session data store lock, so the GUI can read while
workers finish. Related reading: [session and project handlers](session-and-projects.md),
[export and import handlers](export-and-import.md), and the
[detection engine](../../infrastructure/detection/engine.md). Contracts are in the
[generated reference](../../../reference/api/index.md).
