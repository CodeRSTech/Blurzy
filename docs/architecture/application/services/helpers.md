# Layer service helpers

Source: `src/app/application/services/helpers`

Small, stateless functions shared by the detection and tracking layer services.
They hold the rules that must be identical for layers A/B and C/D: how a
reviewed layer is seeded, how loose inputs become enums, how boxes become files,
and how imported boxes merge into a layer. For the workflow they serve, read
[Layer services](layers.md) first.

!!! note "Annotation data only"
    These helpers handle boxes in layers. They do not save projects or render video;
    see [Session and project services](session-project.md) and [Export services](export.md).

## Where this sits

![Handler calls Application, which calls layer services; services call helpers, which read and write the session data store](../../../assets/api/layer_services/sits-light.svg#only-light)
![Handler calls Application, which calls layer services; services call helpers, which read and write the session data store](../../../assets/api/layer_services/sits-dark.svg#only-dark)

Helpers are the second-to-last box: plain functions called by the services, with
no Qt, no workers and no UI dependency. The [big picture](../../big-picture.md)
shows the full stack.

## Worked example: a frame is opened and seeded

When the user steps to frame 40 in the Tracking tab, the controller asks for
that tab's boxes. `UnifiedLayerService.get_tab_frame_boxes_for_session_id`
calls `seed_layer_frame_from_layer(C, D, session, 40)`:

1. D has no entry for frame 40, and C has two boxes.
2. One box is below the minimum tracker confidence, so one clone is stored in D.
3. The service returns D's boxes; the UI table and overlay show that single track.

Opening frame 40 again finds the entry and changes nothing, so edits survive.
The decision flow is drawn in [Seeding](layers.md#seeding-filling-b-from-a-and-d-from-c);
the import equivalent, with a sequence diagram, is in
[Layer services](layers.md#worked-example-importing-corrected-detections).

!!! warning "Current limitations"
    * Seeding reads thresholds from settings at that moment; frames seeded
      earlier are not changed when settings change.
    * `ensure_layer_enum` accepts any valid layer; supported-layer checks live in each service.
    * `MERGE_RENAME` does not deduplicate collisions within one file.

## What each helper does

| Module | Public functions / types | Used by |
| --- | --- | --- |
| `layer_seeding` | `seed_layer_frame_from_layer` | `UnifiedLayerService`, `TrackingLayerService` |
| `import_mode` | `ImportMode` | Import dialog, `Application`, import services |
| `layer_coercion` | `ensure_layer_enum`, `ensure_import_mode` | `Application`, import/export services, handler |
| `layer_io` | `serialize_layer_to_json/csv`, `deserialize_layer_from_json/csv`, `apply_import_to_layer` | Import and export services |

Helpers take a session or store as an argument and keep no state of their own.
Their log output uses the `Application->LayerSeeding` area (seeding) and the callers' areas.

## `seed_layer_frame_from_layer(source, target, session, frame_index)`

Initialises one frame of an editable layer (B from A, D from C):

1. Acquire the session data lock (reentrant, so callers already holding it are fine).
2. If the target frame already has an entry (even an empty list), stop.
3. If the source frame has no boxes, stop; nothing is created.
4. Otherwise clone each source box that passes `new_passes_filter` for the target
   layer and store the list in the target.

Cloning keeps edits in B/D from mutating A/C. The filter thresholds come from the
session settings at the moment of seeding. Later changes to those settings
do not rewrite already-seeded frames; use the unified service's
re-filter or reset instead.

## `ImportMode`

A `str` enum whose values (`overwrite`, `merge_replace`, `merge_ignore`,
`merge_rename`) double as labels in the dialog through `display_label`. Behaviour of
each mode is shown with an example in
[Import modes](layers.md#import-modes).

## Coercion

Qt can deliver enums as plain strings (for example through `QComboBox.currentData()`
or signal arguments). The two `ensure_*` functions make that harmless:

```python
from app.application.services.helpers.layer_coercion import ensure_layer_enum

ensure_layer_enum("b")   # VideoDataLayer.B
ensure_layer_enum("B")   # VideoDataLayer.B
ensure_layer_enum("x")   # ValueError
```

Resolution order is the enum itself, then the lower-cased *value*, then a
case-insensitive *name*. Unknown input raises `ValueError` rather than being
guessed. They do **not** check which layers a service supports; that is the
service's job.

## JSON and CSV I/O (`layer_io`)

| Function | Contract |
| --- | --- |
| `serialize_layer_to_json(name, data, path)` | Writes `{meta, frames}`; skips empty frames; returns the box count |
| `serialize_layer_to_csv(name, data, path)` | One row per box under a fixed header; `name` is unused and kept for symmetry |
| `deserialize_layer_from_json(path)` | Reads only `frames`; returns `{frame_index: [boxes]}` |
| `deserialize_layer_from_csv(path)` | Same result shape; empty confidence becomes `None` |
| `apply_import_to_layer(store, layer, incoming, mode)` | Applies the mode to the store and returns boxes written |

Serialisers create missing parent directories and overwrite existing files. JSON
boxes go through `box_to_dict` / `dict_to_box` in `app.shared.box_io`; CSV
rows are built directly. Field layouts and examples are in
[File formats](layers.md#file-formats).

`apply_import_to_layer` is the only place the four modes are implemented.
`OVERWRITE` replaces the layer through the store, `MERGE_REPLACE` and
`MERGE_IGNORE` assign whole frame lists, and `MERGE_RENAME` appends clones
(adding `imp-` to `key` and `id` on collision). Imported boxes are stored as
parsed for the replace modes and cloned for rename.

!!! warning "Failure semantics"
    Deserialisers complete before any layer is touched, so a malformed file
    raises (`json.JSONDecodeError`, `KeyError`, or `ValueError` for an unknown
    `source`) and leaves the layer unchanged. Merging itself is not
    transactional: an error part-way through `OVERWRITE` can leave the layer
    cleared or partially loaded. Helpers raise; logging and dialogs belong to
    the services and handler (see [failure paths](layers.md#failure-paths)).

See the [generated API reference](../../../reference/api/index.md) for signatures.
