# Export infrastructure

Source: `src/app/infrastructure/export`

Exporting a video means decoding every frame, blurring the chosen subjects,
and re-encoding the result. For a long clip that takes minutes, so it must not
run on the GUI thread. The two classes in this package, `ExportWorker` and
`ExportAllWorker`, are `QThread` wrappers that run the export off the UI thread
and report progress with Qt signals.

**The workers do not render anything.** The frame loop lives in the Application
[`ExportService`](../application/services/export.md); the workers call it,
translate its progress callback into signals, and turn exceptions into
outcomes the UI can show.

## Where this sits

![The export handler creates a worker thread; the worker calls ExportService, which reads layers and the video reader from the Session and writes the output MP4. The batch worker also calls Application to detect and track](../../assets/api/export/context-light.svg#only-light)
![The export handler creates a worker thread; the worker calls ExportService, which reads layers and the video reader from the Session and writes the output MP4. The batch worker also calls Application to detect and track](../../assets/api/export/context-dark.svg#only-dark)

Arrows mean "calls or creates". The handler owns dialogs and worker
lifetime; the worker owns the thread, signals and cancellation flag; the service
owns the render loop. Only the worker's `run()` executes on the background thread.

!!! info "Not the same as annotation interchange"

    Blurred-video export is separate from JSON/CSV layer interchange and from
    saving a `.blurzy` project. Those workflows do not use these workers.

## What gets rendered

![Pick layer D else C once, open an mp4v writer, then for each frame read, convert to BGR, fetch boxes, blur if enabled, write, call the progress callback; finally release the writer](../../assets/api/export/render-pipeline-light.svg#only-light)
![Pick layer D else C once, open an mp4v writer, then for each frame read, convert to BGR, fetch boxes, blur if enabled, write, call the progress callback; finally release the writer](../../assets/api/export/render-pipeline-dark.svg#only-dark)

Solid arrows are the order of work for one frame; the dashed arrow loops to the
next frame. Implemented in `ExportService._render_blurred_video`.

1. **Layer choice, once per export.** Layer D (reviewed tracks) is used if it
   holds any boxes; otherwise Layer C (original tracker output); otherwise the
   export raises `RuntimeError`. There is no per-frame fallback: if D is chosen,
   a frame with no D boxes is written unblurred even if C has boxes there.
2. **Encode settings.** OpenCV `VideoWriter` with the `mp4v` fourcc, the
   source frame rate and the source width and height.
3. **Per frame.** The reader returns an RGB array by random access, the loop
   converts it to BGR, fetches the chosen layer's boxes for that index, and, when
   `blur_enabled` is set and boxes exist, calls the shared masked blur with
   `blur_strength`. Preview styling does not affect this path.
4. **Progress.** After writing frame `i`, the callback receives
   `(i + 1, frame_count)`.
5. **Cleanup.** `writer.release()` runs in a `finally` block.

!!! warning "Skipped frames shorten the output"

    If the reader returns no frame for an index, the loop logs a warning and
    continues: nothing is written and the progress callback is not called for
    that index. The video can therefore be shorter than the source and the
    progress bar can jump.

## One session: signals and lifecycle

![User clicks Export, the handler checks readiness and asks for a path, starts ExportWorker, which calls ExportService; each frame's callback becomes a progress_updated signal; then succeeded, finished_processing and native finished](../../assets/api/export/export-sequence-light.svg#only-light)
![User clicks Export, the handler checks readiness and asks for a path, starts ExportWorker, which calls ExportService; each frame's callback becomes a progress_updated signal; then succeeded, finished_processing and native finished](../../assets/api/export/export-sequence-dark.svg#only-dark)

Time runs downward. Arrows between the worker and handler are Qt signals
delivered to the GUI thread. `ExportWorker` exposes:

| Signal | Emitted when |
| --- | --- |
| `progress_updated(current, total)` | Each frame, from the progress callback |
| `succeeded()` | `export_session` returned normally |
| `cancelled()` | The callback raised `ExportCancelled` |
| `error_occurred(msg)` | Any other exception; logged with traceback first |
| `finished_processing()` | Always last, from a `finally` in `run()` |

!!! danger "`finished_processing` is not thread termination"

    The signal is emitted from inside `run()`, before the thread has exited.
    The handler keeps the worker referenced and the controls busy until Qt's
    native `QThread.finished` arrives, and only then calls `deleteLater()`.
    Deleting a running `QThread` can abort the process.

## Cancelling

![UIController asks the handler to stop; the handler calls worker stop which sets a flag; the next progress callback raises; the worker emits cancelled then finished_processing; the handler waits and deletes the worker](../../assets/api/export/cancel-light.svg#only-light)
![UIController asks the handler to stop; the handler calls worker stop which sets a flag; the next progress callback raises; the worker emits cancelled then finished_processing; the handler waits and deletes the worker](../../assets/api/export/cancel-dark.svg#only-dark)

`stop()` only sets `_stop_requested`. Nothing is interrupted: the flag is read
at the next progress callback, which happens **after** the current frame has been
read, blurred and written. The callback raises `ExportCancelled`
(single export) or `RuntimeError("Batch export cancelled.")` (batch). The
exception unwinds through the service's `finally`, which releases the writer,
and the worker reports cancellation.

!!! warning "Cancel and failure leave the partial MP4 on disk"

    Neither the service, the workers nor the handler delete the output file.
    After a cancel or a mid-render error, a truncated `.mp4` may remain at the
    chosen path, and a later export to the same path overwrites it. Treat the
    file as incomplete unless `succeeded()` (or `session_finished`) was received.

## Exporting many sessions

![For each session: emit session_started, run detection if layer A is empty, run tracking if C is empty, check readiness, export to prefix+name+suffix.mp4, then emit session_finished or session_failed and progress_updated](../../assets/api/export/batch-flow-light.svg#only-light)
![For each session: emit session_started, run detection if layer A is empty, run tracking if C is empty, check readiness, export to prefix+name+suffix.mp4, then emit session_finished or session_failed and progress_updated](../../assets/api/export/batch-flow-dark.svg#only-dark)

Each pass of the loop handles one session; the dashed arrow starts the next.
`ExportAllWorker` processes sessions strictly one after another, calling the
Application facade for each stage. It waits (`QThread.wait()`) for the detection
and tracking worker threads the facade starts, so the batch thread blocks while
they run.

- **Detection** runs only when Layer A has no boxes.
- **Tracking** runs only when Layer C has no boxes, using the session's
  configured strategy and source layer. If the source is B, B is empty and A has
  boxes, A is used instead.
- **Readiness** is the same D-or-C test the render loop uses; failing it raises
  and becomes `session_failed`.
- **File name** is `{prefix}{video basename without extension}{suffix}.mp4` inside
  the chosen directory.

| Signal | Payload | Meaning |
| --- | --- | --- |
| `session_started` | `s_id` | Work on this session began |
| `session_export_progress_updated` | `s_id, frame, total` | Per-frame progress of the current export |
| `session_finished` | `s_id` | This session exported |
| `session_failed` | `s_id, message` | This session failed; the batch continues |
| `progress_updated` | `done, total` | Sessions completed (success or failure) |
| `cancelled` | none | Emitted after the loop when a stop was requested |
| `finished_processing` | none | Always last |

Session identifiers travel as Python-object payloads so the `SessionId` survives
queued connections.

!!! note "Batch cancel"

    `stop()` sets the flag and also calls `stop()` on the current session's
    detection and tracking workers. The flag is re-checked between stages and at
    each export callback, so an in-progress render ends at its next frame. A stop
    is not reported as a session failure: the loop breaks, then emits
    `cancelled` and `finished_processing`. Sessions not yet started are skipped,
    and `progress_updated` is not emitted for the interrupted session.

## Worked example

!!! example "Three sessions"

    Sessions `a.mp4`, `b.mp4` and `c.mp4`; prefix `blur_`, suffix `_v1`, output
    directory `out/`. `a` has reviewed Layer D tracks, `b` has only detections
    (A), and `c` has no detections and tracking finds nothing.

    1. `session_started(a)`. A and C are populated, so no preparation runs. The
       render uses **D**. Frames stream as `session_export_progress_updated`,
       then `session_finished(a)` and `progress_updated(1, 3)`. Output:
       `out/blur_a_v1.mp4`.
    2. `session_started(b)`. A exists but C is empty, so tracking runs first
       (source B if populated, otherwise A). D has not been seeded, so the export
       uses **C**. `session_finished(b)`, `progress_updated(2, 3)`.
    3. `session_started(c)`. Detection and tracking run but leave C empty, so the
       readiness check raises. The error is logged and `session_failed(c, ...)`
       fires, then `progress_updated(3, 3)`. No file is written because rendering
       never started.
    4. `finished_processing()`. Had the user stopped during step 2, the loop would
       break, `cancelled` would fire, `c` would never start, and `b`'s partial
       MP4 would stay on disk.

## Known discrepancies

!!! warning "Source and docstrings disagree"

    - The `ExportService` class docstring describes **H.264** video, a JSON
      export and **tab-separated** CSV. The code writes **`mp4v`** video; the
      JSON exporter is commented out; and the CSV writer uses Python's default
      **comma** delimiter.
    - `ExportService.export_annotations_csv` is never called from the
      application, so no workflow produces that CSV today.
    - The `ExportAllWorker` docstring says the detection cache is synced after
      detection; that call is commented out in the code, while
      `sync_tracking_cache` is still called after tracking.

See also: [Video export service](../application/services/export.md),
[tracking infrastructure](tracking.md), [Video layers](../domain/video.md), and the
[API reference](../../reference/api/index.md).
