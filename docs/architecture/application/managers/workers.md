# Engine and tracking worker managers

Source: `src/app/application/managers`

Two managers own heavyweight, per-session objects: the **detection engine**
(a loaded model) and the **tracking worker** (a background thread that links
detections into tracks). Parent overview: [Application managers](../managers.md).

## Where this sits

![Request path: handler, UIController or adapter, Application facade, detection or tracking service, managers highlighted, then engine, worker and layer store](../../../assets/api/managers/stack-light.svg#only-light)
![Request path: handler, UIController or adapter, Application facade, detection or tracking service, managers highlighted, then engine, worker and layer store](../../../assets/api/managers/stack-dark.svg#only-dark)

Here the "service" is `DetectionService` / `TrackingService`; the
infrastructure side is `DetectionEngine`, `TrackingWorker` and the session's
layer store.

## Detection engine reuse and replacement

![Flow: if the session has no engine, create one through the factory; otherwise call set_model on the existing engine; remove sets the engine to None; load failures propagate](../../../assets/api/managers/engine-light.svg#only-light)
![Flow: if the session has no engine, create one through the factory; otherwise call set_model on the existing engine; remove sets the engine to None; load failures propagate](../../../assets/api/managers/engine-dark.svg#only-dark)

Solid arrows are the create/update decision; dashed arrows are failure and
removal paths.

- **`create_or_update(s_id, model_name)`**: the first call creates an engine
  with `DetectionEngineAdapterFactory`; later calls keep the same engine object
  and call `set_model`, which reloads the model inside it.
- **`remove(s_id)`**: sets `session.detection_engine = None`. This is what
  `DetectionService` does when the model name is `"None"`.
- The engine is also created lazily: single-frame detection calls
  `create_or_update` when `session.detection_engine` is `None`.

!!! note "Ordering is the caller's job"
    `DetectionService.set_detection_model_for_session_id` stops and clears the
    session's detection worker, resets the model's layers, and only then
    updates or removes the engine. The manager itself does not stop workers.

## Tracking worker lifecycle

![Flow of TrackingWorkerManager.start: checks for a running worker, supported source layer, empty source, then clears C and D and creates the worker; each rejection raises an exception](../../../assets/api/managers/tracking-start-light.svg#only-light)
![Flow of TrackingWorkerManager.start: checks for a running worker, supported source layer, empty source, then clears C and D and creates the worker; each rejection raises an exception](../../../assets/api/managers/tracking-start-dark.svg#only-dark)

Solid arrows are the happy path; dashed boxes are exceptions raised to the
service and then to the handler, which shows the dialog.

1. **Guard.** A session with a running tracker cannot start another.
2. **Source layer.** Only **A** or **B** are accepted. For **B**, any frame
   missing from B is first seeded from A using cloned boxes that pass the B
   filter; frames already in B (including manual edits) are left alone.
3. **Empty check.** An empty source raises `EmptyLayerException`.
4. **Clear C and D.** `session.data.clear_layers_by_name([C, D])` removes the
   previous tracking output *and* the reviewed tracks, so earlier D edits are
   discarded on every run.
5. **Create.** The factory builds a `TrackingWorker` with `start=True`. The
   worker **deep-copies** the source boxes and the settings at construction, so
   later edits to A/B or to settings do not affect a running job.

### Stop and read

- `stop(s_id)` calls `worker.stop()`, then clears `session.tracking_worker`.
  `stop()` only sets a flag that the worker checks once per frame and before
  post-processing; the thread is not joined here. A `ValueError` is logged and
  the worker reference is kept.
- `get_tracked_data(s_id)` returns the worker's results as a **deep copy made
  under the worker's mutex**, so the GUI thread never sees a half-written
  result. It raises `TrackingWorkerNotFoundException` when there is no worker.
  The manager does not write layer C; `TrackingService.sync_tracking_cache`
  does, and seeds only uninitialized D frames.

## Worked example: running tracking

![Sequence from the user clicking Run tracking through the handler, service, manager and worker thread, then syncing layer C and refreshing the UI](../../../assets/api/managers/track-sequence-light.svg#only-light)
![Sequence from the user clicking Run tracking through the handler, service, manager and worker thread, then syncing layer C and refreshing the UI](../../../assets/api/managers/track-sequence-dark.svg#only-dark)

Arrows between the handler and the worker are Qt signals delivered to the GUI
thread; the others are ordinary calls.

1. `TrackingHandler` validates the UI, shows the loading state, and requests
   the start through the Application.
2. The manager seeds B if needed, clears C/D, and starts the worker.
3. The handler connects `progress_updated`, `finished_processing` and
   `error_occurred` **after** the start call returns.
4. When the worker finishes, `_on_tracking_finished` calls
   `sync_tracking_cache`, which reads the copy through the manager and writes C
   (and seeds D). The handler then selects the tracking tab and re-renders.

## Failure and cleanup paths

| Where | Current behaviour |
| --- | --- |
| Start rejected (running, layer, empty) | Exception to the handler; layers untouched |
| Worker factory raises (e.g. missing optional tracker dependency) | Exception to the handler; C/D are already cleared; no worker attached |
| Error inside the worker thread | Logged with traceback; `error_occurred` then `finished_processing` are emitted |
| `Session.close()` | Calls `tracking_worker.stop()` (flag only) |

## Limitations and discrepancies

!!! warning "Clear-before-create"
    C and D are cleared before the worker is created. If creation fails, the
    old tracks are already gone.

!!! warning "Finished signal also fires after errors and stops"
    The worker's `finally` block always emits `finished_processing`, and the
    handler's finished slot does not check `is_complete()`. After an error or
    a stop, `sync_tracking_cache` therefore reads an empty result and overwrites
    C with nothing.

!!! warning "Stopping is cooperative"
    `TrackingWorker.stop()` only sets a flag; the manager does not wait for the
    thread. `TrackingWorkerManager.switch_active_session` exists but is not
    called by the services in the code searched; tracking is not stopped
    automatically on session switch.

!!! warning "A failed model switch is not atomic"
    `DetectionEngine.set_model` records the new name before loading, so a
    failed reload leaves the previous model active under the new name. The
    manager does not roll back and does not coordinate with in-flight
    inference.
