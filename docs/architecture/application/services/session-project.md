# Session and project services

Implementation: `src/app/application/services/session_service.py`,
`src/app/application/services/project_service.py`

A **session** is one open video together with its settings, playback position,
and annotation layers A-D. A **project** is a saved collection of sessions.
`SessionService` handles everyday session actions; `ProjectService` saves and
restores whole sessions. Both are created by the `Application` facade.

!!! info "Not the same as layer import/export"
    A project file keeps session state and *references* to videos (paths), not
    the video pixels. Exchanging a single layer as JSON/CSV is a separate
    workflow; see [Layer services](layers.md).

## SessionService

| Operation | Behaviour |
| --- | --- |
| `open_videos(paths)` | Opens each path through the facade; **skips already-open videos** (logged), raises `NoNewOpenedSessionsException` if none were new, and activates a session if none is active |
| `handle_active_session_changed(old, new)` | Delegates to the decode-worker manager |
| `update_session_settings(s_id, **kwargs)` | Sets settings by name with validation (below) |
| `session_by_id_has_*` | Read-only checks: buffered frame, running detection worker, running tracking worker |
| `start_session_playback(s_id)` | Sets the session's playing flag |

![Session tab change: SessionService delegates to the decode worker manager, which does nothing if the session is unchanged, otherwise pauses the old decode worker and resumes the new one](../../../assets/api/app_services/session-switch-light.svg#only-light)
![Session tab change: SessionService delegates to the decode worker manager, which does nothing if the session is unchanged, otherwise pauses the old decode worker and resumes the new one](../../../assets/api/app_services/session-switch-dark.svg#only-dark)

Arrows are calls; the decision is made inside the
[video decode worker manager](../managers.md). Only the active session buffers
frames, which saves CPU and memory. `SessionService` never creates detection or
tracking workers; those belong to their own services.

### Settings updates are forgiving, not strict

`update_session_settings` applies each keyword independently:

- an **unknown** setting name is logged as a warning and skipped;
- a value whose type differs from the current value is warned about and
  skipped, except an `int` is accepted for a `float` field (not for `bool`);
- everything else is applied with `setattr`.

!!! warning "Silent to the caller"
    Skipped keys do not raise or return a result. A caller (for example a
    slider handler) cannot tell that a value was rejected except via the log.

## ProjectService

`ProjectService` holds the current project path, the project directories
(last import/export folders and export prefix/suffix), and a `ProjectStore`
that reads and writes the JSON document (`format_version` `"1.0"`).

![Save: capture each session, build a ProjectDocument, write JSON with ProjectStore](../../../assets/api/app_services/project-save-light.svg#only-light)
![Save: capture each session, build a ProjectDocument, write JSON with ProjectStore](../../../assets/api/app_services/project-save-dark.svg#only-dark)

Saving captures, per session: video path, current frame, next annotation id,
settings, and layers (`to_project_payload`), plus the active session path and
directory settings. The path becomes the current project path only after the
write succeeds.

![Load: validate the file, close all sessions, then per video skip if missing, restore or discard on error, and return a report](../../../assets/api/app_services/project-load-light.svg#only-light)
![Load: validate the file, close all sessions, then per video skip if missing, restore or discard on error, and return a report](../../../assets/api/app_services/project-load-dark.svg#only-dark)

Arrows show the control flow of loading. Dashed = exception path.

1. **Validate** with `ProjectStore.load`; a wrong `format_version` or
   malformed structure raises `ProjectFormatException` before anything is
   closed.
2. **Close every open session**: loading replaces the workspace.
3. For each saved video, a **missing file is skipped**; otherwise the video is
   opened and settings, frame index, annotation counter, and layers restored.
4. **Any exception during one session's restore** discards that session and
   skips it (logged as a warning); other sessions still load.
5. The saved active session becomes active when restored; otherwise the first
   restored session is chosen.
6. The caller gets a `ProjectLoadReport` (`restored_sessions`,
   `skipped_session_paths`); **handlers own the dialog** that tells the user
   what was skipped.

!!! tip "Settings compatibility"
    Saved settings are filtered to fields `ProcessingSettings` still knows;
    unknown keys are logged and ignored, so older or newer files load
    without crashing. A failure in step 1 or in saving (for example `OSError`)
    propagates to the caller.

!!! warning "Limitations"
    - `ProjectStore.save` writes the target file directly, not via a temporary
      file, so a crash mid-write can leave a damaged project.
    - Videos are referenced by path; moving a video makes that session skip on
      load.
    - `clear_project` closes all sessions and resets the path and directories.

See also [Infrastructure: project store](../../infrastructure/project.md),
[Domain: project](../../domain/project.md), and the
[generated API reference](../../../reference/api/index.md).
