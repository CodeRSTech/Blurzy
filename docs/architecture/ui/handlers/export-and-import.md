# Export and import handlers

Implementation: `src/app/ui/handlers/export_handler.py`, `src/app/ui/handlers/import_export_handler.py`

Blurzy moves data out of a session in two unrelated ways, and each has its own
handler:

| Workflow | Handler | What leaves or enters | Runs on |
| --- | --- | --- | --- |
| **Blurred video export** (single or all sessions) | `ExportHandler` | a new `.mp4` with subjects blurred | background `QThread` |
| **Layer import / export** | `ImportExportHandler` | JSON or CSV files holding one layer's boxes | GUI thread, synchronous |

Neither is the project file. Saving and loading a whole workspace is covered in
[Session and project handlers](session-and-projects.md).

!!! info "Which layer is exported as video?"
    The renderer prefers layer **D** (reviewed tracks) when it has boxes and
    otherwise uses layer **C** (original tracking). A session with neither is
    "not ready" and cannot be exported. Layers A and B are never rendered.

## Render controls versus preview controls

`ExportHandler` also owns the six right-panel display controls. They only store a
setting and re-render the editor preview, so they look similar but differ in what
they change:

| Control | Setting stored | Used by exported video? |
| --- | --- | --- |
| Draw boxes | `draw_boxes` | No, preview only |
| Box border width | `box_border_width` | No, preview only |
| Show preview mask | `show_preview_mask` | No, preview only |
| Preview blur | `preview_blur_enabled` | No, preview only |
| Blur (render) | `blur_enabled` | **Yes**, decides whether any blur is applied |
| Blur strength | `blur_strength` | **Yes** |

Toggling the render Blur checkbox shows or hides the strength control and also
sets the preview-blur checkbox to match, so the preview follows the render choice
by default.

## Exporting one session

![Sequence for exporting one video: guards and Save dialog in the handler, ExportWorker on its own thread calling ExportService, per-frame progress signals back to the GUI, then terminal signals and cleanup](../../../assets/api/ui_handlers_workflows/export_sequence-light.svg#only-light)
![Sequence for exporting one video: guards and Save dialog in the handler, ExportWorker on its own thread calling ExportService, per-frame progress signals back to the GUI, then terminal signals and cleanup](../../../assets/api/ui_handlers_workflows/export_sequence-dark.svg#only-dark)

Time runs downward. Only `ExportWorker` and the `ExportService` call it makes run
off the GUI thread; every progress and result signal is queued back to the GUI.

1. **Guards.** `on_export` returns silently with no selected session. It shows an
   error if an export is already running ("Export In Progress") or if the session
   has no data in C or D ("No tracking results to export. Run detection and
   tracking first.").
2. **Destination.** The default file name is
   `<prefix><video name><suffix>.mp4`. Prefix and suffix come from the project's
   directory settings, falling back to the application preferences; the start
   folder comes from the last export directory. Cancelling the Save dialog ends
   the action. Otherwise the handler stores the chosen folder, prefix, and suffix
   in the project settings.
3. **Start.** The handler shows the busy state (which disables the export
   controls), creates an `ExportWorker` through its factory with the
   `ExportService`, connects five signals, and calls `start()`.
4. **Render.** On the worker thread `ExportService.export_session` creates the
   output folder if needed, opens an OpenCV `VideoWriter` (`mp4v` codec at the
   source frame rate and size), and for every frame reads it, blurs the boxes of
   the export layer when blur is enabled, and writes it. A frame that cannot be
   read is logged and **skipped**, so the output can have fewer frames than the
   source.
5. **Progress.** After each frame the service calls the worker's callback, which
   emits `progress_updated(current, total)`. The handler updates the progress bar
   and the status text "Exporting video: frame N/M".
6. **End.** Exactly one of `succeeded`, `cancelled`, or `error_occurred` fires,
   followed by the thread's `finished`, which re-enables the controls and
   releases the worker.

| Outcome | Status text | Progress label | Dialog |
| --- | --- | --- | --- |
| Success | "Export completed." | Complete | none |
| Cancelled | "Export cancelled." | Cancelled | none |
| Error | "Export failed." | Failed | "Export Failed" with the message |

!!! note "What the video contains"
    The pipeline reads and writes **video frames only**. It does not copy the
    audio track or other streams, and boxes drawn in the editor are not drawn
    into the output; only the blur is applied.

### Cancelling

The export panel has **no Cancel button**. The cancellation path exists for one
trigger: closing the window.

1. `UIController.on_close_requested` returns `True` if nothing is exporting.
2. Otherwise `confirm_export_in_progress_exit` asks "An export is currently in
   progress. Exit anyway?" (default **No**).
3. On Yes the status shows "Cancelling export...", and `stop_exports(wait=True)`
   sets the worker's stop flag and **blocks the GUI thread** until the worker
   ends.
4. The flag is checked once per frame inside the progress callback. It raises
   `ExportCancelled`, which becomes the `cancelled` signal.

`on_about_to_quit` repeats `stop_exports(wait=True)` as a final safety net.

!!! warning "Cancelled output is not cleaned up"
    The service releases the video writer but never deletes the file, so a
    cancelled or failed export can leave a partial `.mp4` on disk.

## Exporting all sessions

`on_export_all` (the Export All button or menu action) refuses with "No videos are
open." when nothing is open, and with "Export In Progress" when another export is
running. It then shows `ExportAllDialog` for the output folder, prefix, and suffix
(pre-filled from project and preference defaults), saves those choices in the
project settings, and starts an `ExportAllWorker` for **all** open sessions.

![Per-session flow inside ExportAllWorker: stop check, run detection if layer A is empty, run tracking if layer C is empty, require C or D, export, then report progress; failures are counted and the batch continues](../../../assets/api/ui_handlers_workflows/export_all_flow-light.svg#only-light)
![Per-session flow inside ExportAllWorker: stop check, run detection if layer A is empty, run tracking if layer C is empty, require C or D, export, then report progress; failures are counted and the batch continues](../../../assets/api/ui_handlers_workflows/export_all_flow-dark.svg#only-dark)

Dashed arrows are failure or cancel paths. Sessions are processed one after
another on a single worker thread.

The batch is more than a loop over the single export: **a session without
detections or tracks is detected and tracked first**, using the session's current
model, tracking strategy, and tracking source. The worker waits for each
background worker to finish before moving on.

The handler tracks three numbers only: sessions done (overall bar), frames done in
the current session (second bar, labelled with the file name), and a failure
count. A session failure is logged and counted but **does not show a dialog**; the
final status text is "Batch export completed." or
"Batch export completed with N failure(s)." or "Batch export cancelled.".

!!! warning "Limitations to know about"
    - Files are named `<prefix><name><suffix>.mp4` in a single folder with no
      uniqueness check, so two videos with the same file name overwrite each
      other, and existing files are overwritten without confirmation.
    - Cancelling is only reachable through the window-close path above. In a batch
      it also asks the in-flight detection or tracking worker to stop.
    - A session that already has layer A data skips detection, and one with layer
      C data skips tracking, so it is exported with that data as it stands even
      if settings changed since it was produced.
    - In a batch, detection is started from the `ExportAllWorker` thread, which
      has no Qt event loop. The detection service connects its `batch_ready` slot
      from the calling thread, and a minimal PySide6 reproduction of that pattern
      did not deliver queued signals to a thread without an event loop. If
      the same happens in the application, a session without existing layer A
      data would end up with no boxes to track and be reported as failed. Run
      detection first from the main window to avoid it. This is not verified
      end to end.

## Importing and exporting layer data

![Sequence for layer import and export: button opens a modal dialog, the handler routes the chosen operation through the facade to the detection or tracking service, then re-renders and updates status](../../../assets/api/ui_handlers_workflows/import_export_sequence-light.svg#only-light)
![Sequence for layer import and export: button opens a modal dialog, the handler routes the chosen operation through the facade to the detection or tracking service, then re-renders and updates status](../../../assets/api/ui_handlers_workflows/import_export_sequence-dark.svg#only-dark)

This workflow is entirely synchronous on the GUI thread: no worker, no progress
bar, no cancel.

The right panel has two buttons that open the same dialog with a different
scope:

| Button | Layers offered | Services |
| --- | --- | --- |
| Detections | A (raw) and B (reviewed) | `DetectionImportService`, `DetectionExportService` |
| Tracks | C (raw) and D (reviewed) | `TrackingImportService`, `TrackingExportService` |

1. **Dialog.** The modal `ImportExportDialog` collects: import or export, layer,
   format (`.json` or `.csv`), file path, and for imports a merge mode. It
   asks for confirmation itself before an Overwrite import. If the user accepts
   but `get_config()` is `None` (the overwrite warning was declined), the handler
   does nothing.
2. **Facade.** The handler calls `Application.import_layer` or `export_layer`,
   which coerce string values from Qt to enums and route A/B to the detection
   service and C/D to the tracking service.
3. **Service.** Import checks the file exists and the extension, parses it, and
   applies the mode to the layer. Export serializes every box in the layer. Each
   service rejects a layer outside its own pair
   (`UnsupportedLayerOperationException`) and any extension except
   `.json` and `.csv` (`UnsupportedImportExportFormatException`).
4. **Result.** An import re-renders the preview and shows "Import complete — N
   box(es) loaded into layer X." An export shows "Export complete — N box(es)...".
   The handler then remembers the file's folder in the project's last import or
   export directory. A missing file raises `FileNotFoundError`. All failures show
   an "Import / Export Failed" dialog and are logged: format and layer problems
   as warnings, everything else with a traceback.

### Import modes

| Mode | What happens to the target layer |
| --- | --- |
| Overwrite | The entire layer is replaced by the file. |
| Merge – Replace existing frames | Frames in the file replace the same frames; other frames are untouched. |
| Merge – Ignore existing frames | Only frames that currently have **no** boxes are filled. |
| Merge – Rename conflicting keys | All boxes are added; a box whose key already exists in that frame gets an `imp-` prefix on its key and id. |

!!! example "Moving detections into tracking"
    The JSON/CSV wire format is shared by both services. To use detections from a
    file as tracking output, export layer A from the **Detections** dialog, then
    open the **Tracks** dialog and import that file into layer C or D. A dialog
    never offers layers from both pairs at once, so the file is the bridge.

!!! warning "Import writes only the chosen layer"
    Importing into A does not recompute B, and importing into C does not reseed D.
    The imported data replaces or merges into exactly the layer you chose.

!!! note "Wire format is not the project format"
    JSON files carry a `format_version` and layer name in their `meta` block, but
    these are layer-interchange files. Whole-session state is stored in project
    files; see [Session and project handlers](session-and-projects.md).

## Thread summary

| Step | Thread |
| --- | --- |
| Dialogs, guards, progress widgets, layer import/export | GUI |
| Video decoding, blurring, and encoding | `ExportWorker` / `ExportAllWorker` |
| Detection/tracking inside a batch export | `ExportAllWorker` thread plus the workers it starts |
| Progress and result signals | queued to the GUI thread |

See [Detection, tracking, and model handlers](detection-and-tracking.md) for the
workers a batch export reuses, and the
[generated API reference](../../../reference/api/index.md) for exact contracts.
