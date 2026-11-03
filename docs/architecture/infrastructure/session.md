# Session infrastructure

Source: `src/app/infrastructure/session`

Opening a video in Blurzy creates a **session**: everything the app needs to
work on that one video, in one object. The infrastructure `Session` bundles a
playback/settings state, the four annotation layers, a decode worker that feeds
frames, and optional detection and tracking workers.

!!! info "Session state is not the entire session"

    The domain [`SessionState`](../domain/session.md) holds metadata, playback,
    settings, and an annotation id counter. It cannot store annotations or decode
    a frame. The infrastructure `Session` assembles those runtime collaborators
    around it.

## What a session holds

![SessionManager creates an empty Session; SessionInitializer attaches state, reader and decode worker. The Session holds its id, state, data store, reader, decode worker, frame accessor, and optional detection and tracking workers](../../assets/api/session/structure-light.svg#only-light)
![SessionManager creates an empty Session; SessionInitializer attaches state, reader and decode worker. The Session holds its id, state, data store, reader, decode worker, frame accessor, and optional detection and tracking workers](../../assets/api/session/structure-dark.svg#only-dark)

Solid arrow: creation. Dashed arrow: later attachment. Boxes inside `Session`
are attributes it owns or references.

| Collaborator | Owns or coordinates | Does not own |
| --- | --- | --- |
| `SessionState` | Metadata, playback position, settings, annotation id counter | Decoder, workers, layers |
| `SessionDataStore` | Layers A-D and synchronized machine/manual box operations | Pixels or project-file writing |
| `SessionFrameAccessor` | Current/next/previous/indexed frame lookup, seek request, wait | Decoding, inference, tracking |
| Reader and workers | Media I/O and long-running processing | Direct Qt widget updates |

Until the initializer runs, `state`, `video_reader`, and `video_decode_worker`
are `None`; frame and playback methods raise `RuntimeError` with a message
pointing at `SessionInitializer`. Detection/tracking engines and workers are set
later by their own workflows and may remain `None`.

## Lifecycle

![Sequence: SessionManager creates a session shell, the initializer attaches reader and state and starts the decode worker; on close the session stops its workers, closes its reader, and the manager removes it and re-picks the active id](../../assets/api/session/lifecycle-light.svg#only-light)
![Sequence: SessionManager creates a session shell, the initializer attaches reader and state and starts the decode worker; on close the session stops its workers, closes its reader, and the manager removes it and re-picks the active id](../../assets/api/session/lifecycle-dark.svg#only-dark)

Construction is split on purpose: `Session(s_id)` opens no files and starts no
threads, so tests can build one cheaply. The initializer then opens a
`VideoReader`, builds `SessionState` from its metadata, and starts the
[decode worker](video.md#videodecodeworker-the-playback-buffer) (inactive until
the Application activates it).

### Teardown

`Session.close()` stops the detection worker, the tracking worker, then the
decode worker (each only if present), and finally closes `video_reader`. The
manager's `discard_session` or `close_all` calls it, removes the session from its
dictionary, and, if the active session was removed, picks the first remaining
session or an empty id.

!!! warning "Limitations"

    - `close()` does not guard against one `stop()` raising; a failure there
      would skip later steps.
    - The layer store is not saved by closing. Persistence is the
      [project workflow](project.md).
    - The session is a `QObject` with child objects; Qt owns the destruction
      order of its children.

## Annotation layers: `SessionDataStore`

The store keeps `dict[layer][frame_index] -> list of boxes` for the four layers:

| Layer | Role | Typically written by |
| --- | --- | --- |
| A | Original detector output | Detection (raw copy) |
| B | Reviewed/editable detections, seeded from A | Detection (machine boxes), user edits, resets |
| C | Original tracking output | Tracking result processing |
| D | Reviewed/editable tracks, seeded from C | Tracking (machine boxes), user edits, resets |

These roles are workflow conventions. The store itself accepts any layer in any
method; the application services decide what to write where.

![Detection writes A raw and B as machine boxes; tracking reads A or B, writes C whole and D as machine boxes; resets copy A to B and C to D with filtering; users edit B and D](../../assets/api/session/layers-light.svg#only-light)
![Detection writes A raw and B as machine boxes; tracking reads A or B, writes C whole and D as machine boxes; resets copy A to B and C to D with filtering; users edit B and D](../../assets/api/session/layers-dark.svg#only-dark)

Solid arrows are the normal write path; dashed arrows are optional or
user-triggered flows (reset/re-filter, and choosing tracking input).

### Seeding without losing manual work

Machine output must never overwrite a user's hand-drawn boxes, so several
operations differ in how they treat boxes marked manual:

| Operation | Target is replaced | Manual boxes in target |
| --- | --- | --- |
| `replace_machine_boxes_at_frame_index` / `_for_frames` | machine boxes only | Kept (same objects) |
| `apply_filters_to_layers` (re-filter A to B or C to D) | per frame, **only if the count changes** | Cloned and kept |
| `overwrite_source_layer_to_target_layer` (reset) | whole layer, cleared first | **Lost** unless the caller saves them |
| `overwrite_layer_with_dict_of_boxes` | whole layer | Lost |
| `clear_layer_by_name(keep_manual=True)` | machine boxes | Kept |

Machine boxes copied between layers are **cloned**, so editing B never mutates A.

??? note "Worked example: tracking refreshes layer D"

    Layer D frame 10 holds one manual box and two old machine boxes. A new
    tracking run produces three boxes for frame 10. `replace_machine_boxes_for_frames`
    filters those by the current settings, clones the survivors, and assigns
    `[manual box] + [cloned machine boxes]`. Every frame in `0..frame_count-1`
    is processed, including frames with no tracks, so manual boxes persist
    everywhere and empty frames become initialized-empty entries.

### Locking and live data

All store methods take a reentrant lock (`data_lock`), so detection or tracking
workers and the GUI thread can use them concurrently. **The lock protects each
call, not what you do with the result:** getters return the *live* list or
mapping after releasing the lock. Hold `store.data_lock` around any multi-step
read, and mutate through store methods.

!!! danger "Not transactional"

    There is no rollback. `load_project_payload` clears all four layers before
    parsing, so a bad box leaves partial data. Bulk operations that raise midway
    leave earlier frames updated. Missing-frame reads return `[]` without
    creating an entry; indexing the mapping returned by
    `get_all_boxes_for_layer_as_dict_of_lists` does create one.

`to_project_payload` and `load_project_payload` convert layers to and from plain
dictionaries for [project files](project.md). Empty frames are omitted when
saving, so "initialized but empty" is not preserved across a save.

## Frame access

`SessionFrameAccessor` turns a frame request into a ring-buffer lookup, a seek,
and a bounded wait. It lives on the **calling** thread (usually the GUI thread),
not in the worker.

![Flowchart: clamp the index, return on buffer hit; otherwise request a seek if the index is more than one frame from the playhead or the current frame is missing, then poll every 10 ms for up to 2 seconds, returning the frame or None](../../assets/api/session/frame-access-light.svg#only-light)
![Flowchart: clamp the index, return on buffer hit; otherwise request a seek if the index is more than one frame from the playhead or the current frame is missing, then poll every 10 ms for up to 2 seconds, returning the frame or None](../../assets/api/session/frame-access-dark.svg#only-dark)

On success the accessor writes the playhead and `current_frame_data` in
`SessionState`; on timeout it logs an error and returns `None`.

| Method | Index requested |
| --- | --- |
| `get_frame_by_index` | Given (clamped) |
| `get_current_frame` | Playhead, only if no frame is cached in state |
| `get_next_frame` / `get_previous_frame` | Playhead +1 / -1 (clamped at the ends) |
| `get_buffered_frame` (and `Session.has_buffered_frame`) | Same as next: it **advances** the playhead on success |

!!! warning "Blocking behaviour to be aware of"

    - Every miss blocks the caller for up to 2 seconds. The playback tick uses
      `has_buffered_frame`; on an underrun it therefore waits instead of
      skipping the tick immediately.
    - A miss within one frame of the playhead does **not** request a seek (it
      assumes the worker is about to produce it) unless no current frame is cached.
      Stepping *back* past the oldest buffered frame is such a miss, so it waits
      the full timeout and returns `None` (from reading the code).

Details of the worker side are in [Video infrastructure](video.md). Project
reopen and restore decisions belong to the Application project workflow.
See also the [generated API reference](../../reference/api/index.md).
