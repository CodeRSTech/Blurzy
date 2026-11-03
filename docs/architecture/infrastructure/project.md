# Project persistence

Source: `src/app/infrastructure/project`

A Blurzy **project** file remembers your work: which videos are open, where you
were, your settings, and every annotation in layers A-D. `ProjectStore` is the
small file boundary that turns a domain `ProjectDocument` into JSON text and
back. It does *not* open videos, create sessions, or decide what is restorable;
the Application `ProjectService` does that.

## Save and load

![Save: ProjectService captures sessions, each store produces a layer payload, ProjectStore writes JSON. Load: ProjectStore validates the file, ProjectService reopens each video and restores settings, playhead and counter, the store rebuilds layers, and a report lists restored and skipped sessions](../../assets/api/project/save-load-light.svg#only-light)
![Save: ProjectService captures sessions, each store produces a layer payload, ProjectStore writes JSON. Load: ProjectStore validates the file, ProjectService reopens each video and restores settings, playhead and counter, the store rebuilds layers, and a report lists restored and skipped sessions](../../assets/api/project/save-load-dark.svg#only-dark)

Arrows are data flow, top to bottom. The dashed arrow is the failure path.

| Step | Owner | Notes |
| --- | --- | --- |
| Capture | `ProjectService` | One entry per session with an initialized state: video path, playhead, annotation counter, settings, layers |
| Layer payload | [`SessionDataStore`](session.md#annotation-layers-sessiondatastore) | Plain dicts for A-D; empty frames omitted |
| Write | `ProjectStore.save` | Creates the parent folder, then `json.dump(asdict(project), indent=2)`, UTF-8 |
| Validate | `ProjectStore.load` | Root must be an object; `format_version` must equal `"1.0"` |
| Restore | `ProjectService` | Closes all sessions first, then restores each entry and picks the active session |

The `.blurzy` extension (or `.json`) is chosen by the UI and Application; the
store accepts any path and writes JSON regardless.

## What the store validates

`ProjectStore` checks only the document shell: version string, that
`directories` is an object, that `sessions` is a list of objects, a non-empty
string `video_path`, and that `settings` and `layers` are objects. Missing
optional fields get defaults. It raises `ProjectFormatException` for these
shape problems and lets `OSError`, `json.JSONDecodeError`, and
integer-conversion errors propagate.

!!! warning "Shallow validation"

    Box content inside `layers` and the keys of `settings` are **not** checked
    here. A malformed box fails later in `load_project_payload`, which has
    already cleared the session's layers; `ProjectService` then discards that
    session and reports its path as skipped. Writing is also not atomic: a
    failure while saving can leave a truncated file.

## Failure behaviour on load

| Situation | Result |
| --- | --- |
| Wrong version, not JSON, bad shape | The whole load raises; no session is touched (the store raises before restore begins) |
| Video file missing on disk | That session is skipped, logged, and listed in the report |
| Restore error for one session | That session is discarded, logged, listed as skipped; others continue |
| Active session path not restored | The first restored session becomes active |

The UI handler decides how to show the report; infrastructure only raises or
returns data.

## Related pages

The persisted shape is in [Project domain](../domain/project.md). Live session
and layer storage is in [session infrastructure](session.md). Layer JSON/CSV
import and export is a separate workflow in
[Application service helpers](../application/services/helpers.md). See the
[generated API reference](../../reference/api/index.md) for signatures.

Both layer data and `format_version` are project-file concerns: an application
release does not change `format_version` unless the serialized schema changes.
