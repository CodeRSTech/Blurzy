# Layer services

Source: `src/app/application/services`

Principal modules: `unified_layer_service.py`, `detection/{layer,importing,exporting}.py`, `tracking/{layer_service,import_service,export_service}.py` and the [helpers](helpers.md).

Blurzy never overwrites what a model produced. Every box lives in one of four
**annotation layers**, and the services on this page decide which layer a user
action may touch, how reviewed layers are filled from machine output, and how
layers move to and from JSON/CSV files.

!!! note "Not video export"
    "Export" here means saving **annotation boxes** to a `.json` or `.csv` file.
    Rendering a blurred video is a separate workflow: see [Export services](export.md).
    Saving the whole session is covered in [Session and project services](session-project.md).

## Where this sits

![Import/export handler calls the Application facade, which routes to the layer services; they use helpers to read and write the session data store; no manager or worker is involved](../../../assets/api/layer_services/sits-light.svg#only-light)
![Import/export handler calls the Application facade, which routes to the layer services; they use helpers to read and write the session data store; no manager or worker is involved](../../../assets/api/layer_services/sits-dark.svg#only-dark)

Solid arrows are calls; dashed arrows are optional or post-call. For the whole
stack see the [big picture](../../big-picture.md). Layer services are the
application-layer step between UI handlers and the session's data store. Unlike
detection and tracking, nothing here runs on a worker thread.

## The four layers

![Layer A feeds editable layer B; layer C feeds editable layer D; the tracker reads A or B; blurred-video export reads D when populated and otherwise C](../../../assets/api/layer_services/layers-light.svg#only-light)
![Layer A feeds editable layer B; layer C feeds editable layer D; the tracker reads A or B; blurred-video export reads D when populated and otherwise C](../../../assets/api/layer_services/layers-dark.svg#only-dark)

Solid arrows copy boxes from a machine layer to its reviewed layer. Dashed
arrows show which layer another workflow reads.

| Layer | Holds | Written by | Edited by the user? |
| --- | --- | --- | --- |
| **A** | Original detector output | Detection workflow, or an import | No |
| **B** | Reviewed detections, seeded from A | Seeding, reset, user edits, import | Yes |
| **C** | Original tracker output (after configured post-processing) | Tracking workflow, or an import | No |
| **D** | Reviewed tracks, seeded from C | Seeding, reset, user edits, import | Yes |

Keeping *machine output* (A, C) apart from *reviewed output* (B, D) means a
user can always reset a frame and get the model's answer back. Tracking accepts
A or B as input, normally the reviewed B. Blurred-video export prefers a
populated D and falls back to C.

!!! warning "Immutable is enforced only where services check it"
    The unified service rejects edits to A and C with an exception.
    `DataStore` methods themselves do not, and file import deliberately **can**
    write A and C (see [Importing](#importing-a-layer)). Treat "read-only" as a
    rule of the editing API, not a storage-level lock.

## Who does what

| Piece | Responsibility |
| --- | --- |
| `UnifiedLayerService` | Layer-agnostic editing of B and D: move, relabel, copy to neighbour frame, paste, delete, reset, restore history snapshots, re-filter |
| `DetectionLayerService` | Adds a manual box to B at the current frame |
| `TrackingLayerService` | Deletes a track from later or earlier frames of D |
| `Detection/TrackingImportService` | Reads a file into A/B or C/D |
| `Detection/TrackingExportService` | Writes A/B or C/D to a file |
| [Helpers](helpers.md) | Seeding, coercion, `ImportMode`, JSON/CSV read/write and merge |

The detection and tracking services are separate classes with the same shape;
`Application.import_layer` / `export_layer` picks one by layer (A, B → detection;
C, D → tracking). Services reach session data through an application adapter and
never touch Qt widgets; the [import/export handler](#failure-paths) owns the dialog.

!!! info "Docstring drift"
    `DetectionLayerService` and `TrackingLayerService` docstrings describe CRUD,
    reset and filtering responsibilities. In the code today, `DetectionLayerService`
    only exposes `add_manual_box_to_layer_b_at_current_frame_index`, and
    `TrackingLayerService` only `delete_tracks_by_id_and_direction`; the rest of
    the editing lives in `UnifiedLayerService`.

## Seeding: filling B from A and D from C

A reviewed layer starts out as a **filtered clone** of its machine layer.

* **Eager seeding:** when detection or tracking finishes, the result
  processors write A (or C) and refresh B (or D) in the same step. Existing
  manual boxes in the reviewed layer survive; machine boxes are re-filtered
  from the source.
* **Compatibility seeding:** when the UI asks for a frame of tab B or D,
  `get_tab_frame_boxes_for_session_id` calls `seed_layer_frame_from_layer`.
  It exists for older sessions and for frames that were never initialised.

![Reading a frame: if the target frame is already initialised nothing changes; otherwise source boxes that pass the filter are cloned into the target](../../../assets/api/layer_services/seeding-light.svg#only-light)
![Reading a frame: if the target frame is already initialised nothing changes; otherwise source boxes that pass the filter are cloned into the target](../../../assets/api/layer_services/seeding-dark.svg#only-dark)

The whole check-and-write happens under the session's reentrant data lock, so
two readers cannot seed the same frame twice. Arrows are the decision path for
one frame.

**What "passes the filter" means** (`new_passes_filter`):

| Target | A box is dropped when |
| --- | --- |
| B | its confidence is below the minimum detection confidence, **or** a label selection exists and the box label is not in it |
| D | its confidence is below the minimum tracker confidence |

!!! note "A frame is initialised even when empty"
    Seeding tests whether the target frame has an *entry*, not whether it has
    boxes. If a user deletes every box in a B frame, the empty entry stops the
    frame from being re-seeded from A. A missing or empty source frame creates no
    target entry at all.

### Reset: the deliberate overwrite

| Method | Effect |
| --- | --- |
| `reset_all_for_layer(B or D)` | Clears the target, then copies every non-empty source frame back through the filter |
| `reset_frame_for_layer(B, n)` | Replaces frame *n* with filtered clones of A's frame *n* |
| `reset_frame_for_layer(D, n)` | Replaces frame *n* with clones of C's frame *n*, then purges boxes under the minimum tracker confidence |
| `apply_filters_to_layer_by_layer(B or D)` | Re-filters from A or C using current settings and returns the number of frames whose box count changed |

!!! danger "Reset discards manual boxes and edits"
    Resets overwrite the target; manual boxes in the reset frame(s) are lost.
    Passing A or C raises `ImmutableLayerOperationException`; any other layer
    raises `UnsupportedLayerOperationException`.

## Editing through the unified API

`UnifiedLayerService` maps the UI's *tab* to a layer: **Detection → B**,
**Tracking → D**. Callers say "tab" and "current frame"; the service resolves
the session and the frame from playback state.

* **Manual and copied boxes** get `source = MANUAL`, confidence `1.0`, an id of
  `manual-<n>` and key `manual:manual-<n>`, with `n` taken from the session's
  `next_annotation_id` counter (incremented for each box).
* **Copy to adjacent frame** clones the selected keys, gives each a fresh manual
  identity, and appends them to the next or previous frame. At the first or
  last frame it silently does nothing, as it does when no key matches.
* **Deleting a track** (`delete_tracks_by_id_and_direction`) walks the frames
  after (or before) the current one, seeds each D frame from C first, then
  removes boxes with that track id. The current frame is untouched, and
  emptied frames stay initialised so the track does not reappear.
* **Move/relabel** act on the current frame; relabelling an unknown key raises
  `UnknownFrameItemException`.

!!! warning "Not every method guards the layer"
    `copy_boxes_to_adjacent_frame_by_direction`, `get_layer_box_by_key` and
    `apply_filters_to_layer_by_layer` reject layers other than B/D.
    `change_xyxy_for_boxes_at_current_idx_by_keys_and_dxdy` and
    `update_current_frame_box_xyxy` pass any layer through to the store, so
    callers must pass B or D themselves.

## Importing a layer

![A handler calls Application, which coerces inputs, checks the layer and file, reads JSON or CSV, applies the import mode to the store, and returns a count; errors travel back to the handler](../../../assets/api/layer_services/pipeline-light.svg#only-light)
![A handler calls Application, which coerces inputs, checks the layer and file, reads JSON or CSV, applies the import mode to the store, and returns a count; errors travel back to the handler](../../../assets/api/layer_services/pipeline-dark.svg#only-dark)

Solid arrows are the success path; dashed arrows are exceptions. Import
runs **synchronously on the GUI thread** (there is no worker, progress or
cancellation), so a very large file blocks the window until it finishes.

1. **Coerce.** Qt can turn enums into strings, so `ensure_layer_enum` and
   `ensure_import_mode` accept `"a"`, `"A"`, `"merge_replace"` or `"MERGE_REPLACE"`.
2. **Guard.** Detection services accept only A and B; tracking services only C and D.
   Anything else raises `UnsupportedLayerOperationException`.
3. **Check the file.** A missing path raises `FileNotFoundError`; an extension
   other than `.json`/`.csv` (case-insensitive) raises
   `UnsupportedImportExportFormatException`.
4. **Parse** the whole file into `{frame_index: [boxes]}`.
5. **Apply** the mode to the layer under the store's data lock and return the
   number of boxes written.

### Worked example: importing corrected detections

A user opens **Import / Export** on the detections panel, picks layer B, a
`.json` file and *Merge – Replace existing frames*.

![Sequence from the user through the handler, Application, detection import service, layer_io and the data store back to a redrawn frame](../../../assets/api/layer_services/import_sequence-light.svg#only-light)
![Sequence from the user through the handler, Application, detection import service, layer_io and the data store back to a redrawn frame](../../../assets/api/layer_services/import_sequence-dark.svg#only-dark)

Arrows run in call order. The handler passes the dialog's choices to
`Application.import_layer`, which coerces them and routes A/B to the detection
service. After the box count returns, the handler asks the controller to
re-render the current frame and updates the status text, so the user sees the
change immediately. The handler also remembers the file's folder as the last
import directory.

### Import modes

![One example file with frames 3 and 5 applied to a layer with frames 3 and 4 under each of the four modes](../../../assets/api/layer_services/modes-light.svg#only-light)
![One example file with frames 3 and 5 applied to a layer with frames 3 and 4 under each of the four modes](../../../assets/api/layer_services/modes-dark.svg#only-dark)

| Mode | Behaviour | Use when |
| --- | --- | --- |
| `OVERWRITE` | Clears the whole layer, then loads the file | The file is the truth |
| `MERGE_REPLACE` | Frames in the file replace the same frames; others untouched | Re-importing corrected frames |
| `MERGE_IGNORE` | Fills only frames that currently hold **no boxes** | Gap-filling without touching existing work |
| `MERGE_RENAME` | Appends every box; a box whose `key` already exists on that frame is cloned with `imp-` prefixed on both `key` and `id` | Combining without losing either side |

??? note "Details and edge cases"
    * The returned count is boxes *written*; `MERGE_IGNORE` does not count skipped frames.
    * `MERGE_RENAME` compares against keys present *before* the import, so two
      colliding boxes within the same file are not deduplicated against each other.
    * Re-importing the same file in `MERGE_RENAME` repeatedly will add
      `imp-` copies each time for already-present keys (only one prefix is applied per import).
    * `OVERWRITE` and `MERGE_*` replace stored lists; the dialog asks for
      confirmation of overwrite before the service is called.

### Importing into A or C does not refresh B or D

Import writes only the chosen layer. If the matching B or D frame is
already initialised, it keeps its old content: re-seed with a reset if you want
the reviewed layer to follow the imported machine data. After an import the
handler re-renders the current frame and updates the status text.

## File formats

Both formats are **layer-agnostic**: they carry boxes, not the layer they came
from, so a file exported from A can be imported into B, or even across the
detection/tracking boundary if the user picks that in the dialog. Frame
indexes are zero-based.

=== "JSON"
    ```json
    {
      "meta": {"exported_layer": "b", "format_version": "1.0",
               "total_frames": 1, "total_boxes": 1},
      "frames": {
        "12": [{"id": "manual-3", "source": "manual", "label": "person",
                "bbox_xyxy": [10, 20, 110, 220], "color_hex": "#00ff00",
                "confidence": 1.0, "key": "manual:manual-3"}]
      }
    }
    ```
    Only non-empty frames are written. On import only `frames` is read;
    `meta` is not validated, and `format_version` is not checked.

=== "CSV"
    ```text
    frame_index,id,source,label,x1,y1,x2,y2,confidence,color_hex,key
    12,manual-3,manual,person,10,20,110,220,1.0000,#00ff00,manual:manual-3
    ```
    One row per box. Confidence is written with four decimals, empty when
    `None`. Coordinates are read back as integers.

!!! note "Not the project or layer-file schema"
    This interchange `format_version` (`"1.0"`) belongs to the box files above and is
    unrelated to `.blurzy` project files. See
    [Project persistence](../../infrastructure/project.md).

Exports create missing parent folders and overwrite an existing file without
asking (the dialog is responsible for any confirmation). The export count is
the number of boxes written; exporting an empty layer writes a valid file with
zero boxes.

## Failure paths

| Situation | Raised by | Result |
| --- | --- | --- |
| Layer/mode string not recognised | `ensure_*` | `ValueError` |
| Layer outside the service's pair | Import/export service | `UnsupportedLayerOperationException` |
| File missing | Import service | `FileNotFoundError` |
| Extension not `.json`/`.csv` | `_load_file` / `_write_file` | `UnsupportedImportExportFormatException` |
| Malformed JSON, missing field, unknown `source`, non-numeric CSV cell | `layer_io` / `box_io` | `json.JSONDecodeError`, `KeyError`, `ValueError` — **before** the layer is changed |
| Edit of A or C via reset | `UnifiedLayerService` | `ImmutableLayerOperationException` |
| Unknown box key on relabel | `UnifiedLayerService` | `UnknownFrameItemException` |

Parsing finishes before any merge, so a bad file leaves the layer untouched.
The services log successes at info level and let exceptions propagate;
the import/export handler catches them, writes a log entry, and shows the
error dialog. Services never open dialogs themselves.

!!! warning "Limits"
    * A failure *during* merge (rare, for example a store error) can leave a
      layer partly written: `OVERWRITE` clears the target first and is not restored.
    * Import/export is not cancellable, has no progress callback, and has no
      frame-range filter.
    * Source comments in the import services describe the layer guard as "soft
      (warning only)"; the code actually **raises**.

## See also

* [Layer service helpers](helpers.md): the functions used above
* [Detection services](detection.md) and [Tracking services](tracking.md): how A and C are produced and eagerly seed B and D
* [Export services](export.md): blurred-video rendering that reads D (or C)
* [Generated API reference](../../../reference/api/index.md)
