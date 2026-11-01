# Video export service

Implementation: `src/app/application/services/export_service.py`

`ExportService` renders the **blurred video**: it reads every frame of a
session, blurs the boxes of the chosen layer, and writes a new MP4. It is
separate from layer JSON/CSV exchange (see [Layer services](layers.md)). Note
that rendering lives in this Application service, not in infrastructure; the
[export worker](../../infrastructure/export.md) only runs it on a background
thread.

!!! info "Preview versus render"
    Preview controls change what the editor shows; **Render controls (blur
    enabled, blur strength) affect exported video**. The export uses the same
    `apply_masked_blur` helper as the preview, so the footprint matches.

## Which boxes are blurred

Export prefers **layer D** (reviewed tracks) and falls back to **layer C**
(raw tracking output) when D has no boxes. If neither has boxes,
`session_is_ready_for_export` is false and `export_session` raises
`RuntimeError`. Layers A and B are never exported.

## Rendering one video

![Check readiness, choose D or C, open a VideoWriter, loop over frames reading, blurring and writing with progress, and always release the writer](../../../assets/api/app_services/export-render-light.svg#only-light)
![Check readiness, choose D or C, open a VideoWriter, loop over frames reading, blurring and writing with progress, and always release the writer](../../../assets/api/app_services/export-render-dark.svg#only-dark)

Arrows are the order of operations; the dashed arrow is the frame loop.

1. Create the output folder if needed.
2. Open an OpenCV `VideoWriter` with codec **`mp4v`**, the source FPS, and the
   source width/height. If it cannot open, `RuntimeError` is raised.
3. For each frame index `0 .. frame_count - 1`: read the RGB frame, convert to
   BGR (OpenCV's order), fetch that frame's boxes from the chosen layer, blur
   them when `blur_enabled`, write the frame, then call the progress callback
   with `(frame_index + 1, frame_count)`.
4. Release the writer in a `finally` block.

How the blur works: all boxes on a frame are merged into one region, clipped
to the frame, blurred with a Gaussian whose kernel is `blur_strength`
(forced odd, at least 3), and blended back with a **10-pixel outward feather**
so edges are soft. Box interiors are fully blurred.

!!! warning "Limitations"
    - A frame that cannot be read is **skipped with a warning**: it is not
      written, so the output has fewer frames than the source and no
      progress is reported for it.
    - The code writes video frames only; **no audio track is copied**.
    - Docstring claims of H.264, a JSON export, or tab-separated CSV do not
      match this implementation: the codec is `mp4v` and the CSV method
      below is comma-separated.
    - If OpenCV lacks `VideoWriter_fourcc` the export fails with `RuntimeError`.

## Running it in the background

![Sequence: the handler starts ExportWorker; the service calls the progress callback; stop() sets a flag and the next callback raises ExportCancelled, ending in cancelled and finished_processing](../../../assets/api/app_services/export-cancel-light.svg#only-light)
![Sequence: the handler starts ExportWorker; the service calls the progress callback; stop() sets a flag and the next callback raises ExportCancelled, ending in cancelled and finished_processing](../../../assets/api/app_services/export-cancel-dark.svg#only-dark)

Arrows are calls or signals in time order. The worker's callback emits
`progress_updated` and, once `stop()` has been requested, raises
`ExportCancelled` from inside the render loop. The writer is released, and the
worker emits `cancelled`.

| Outcome | Signals from `ExportWorker` | Handler action |
| --- | --- | --- |
| Success | `succeeded`, then `finished_processing` | Report success |
| Cancelled | `cancelled`, then `finished_processing` | Report cancel |
| Error | `error_occurred(message)`, then `finished_processing` | Show error dialog |

The service logs failures at the worker boundary with exception details;
**handlers own the dialogs**. Cancellation is cooperative: it takes effect at
the next frame, not instantly.

!!! warning "Partial files remain"
    Neither cancellation nor failure deletes the partially written MP4.

Exporting every open session (`ExportAllWorker`) calls this same service once
per session and adds per-session signals; see
[export infrastructure](../../infrastructure/export.md).

## CSV helper

`export_annotations_csv(s_id, output_path)` writes a comma-separated file with
columns `frame_index, item_id, source, label, x1, y1, x2, y2, confidence,
color_hex`. **Nothing in the application calls it**, and it iterates
`session.state.items()`, which should be verified before relying on it.
Use the layer export services for supported annotation interchange.

API contracts: [generated reference](../../../reference/api/index.md).
