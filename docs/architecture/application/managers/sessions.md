# Session lifecycle managers

Source: `src/app/application/managers`

A **session** is everything Blurzy holds for one open video: the reader, the
playback/settings state, annotation layers A–D, and background workers. Three
small classes create, switch and close sessions. Their parent overview is
[Application managers](../managers.md).

## Where this sits

![Request path: session handler, UIController, Application facade, SessionService, session managers highlighted, then Session and decode worker](../../../assets/api/managers/stack-light.svg#only-light)
![Request path: session handler, UIController, Application facade, SessionService, session managers highlighted, then Session and decode worker](../../../assets/api/managers/stack-dark.svg#only-dark)

For sessions the "service" box is `SessionService`, and `SessionManager` is also
called by the facade directly (open, close, project restore).

| Class | Job in one sentence |
| --- | --- |
| `SessionManager` | Keeps the `dict` of sessions and the id of the active one |
| `SessionInitializer` | Turns an empty `Session` shell into a usable one |
| `VideoDecodeWorkerManager` | Makes sure only the active session's decode thread is buffering |

## Creating a session

![Flow: duplicate check, bare Session shell, initializer builds reader, state and decode worker, then registers the session or logs a skip on failure](../../../assets/api/managers/create-light.svg#only-light)
![Flow: duplicate check, bare Session shell, initializer builds reader, state and decode worker, then registers the session or logs a skip on failure](../../../assets/api/managers/create-dark.svg#only-dark)

Solid arrows are the success path; dashed arrows are rejected or failed paths.

1. The session id *is* the video path (`SessionId(path)`). A path that is
   already open raises `SessionAlreadyExistsException`; `SessionService.open_videos`
   catches it and skips that path.
2. `Session(s_id)` is a **bare shell**: constructing it opens no files and
   starts no threads, so tests can create one cheaply.
3. `SessionInitializer.initialize` attaches, in order: a `VideoReader`, a
   `SessionState` built from the reader's metadata, and a `VideoDecodeWorker`
   parented to the session and started.
4. Only after initialization succeeds is the session put in the dictionary.

!!! note "The decode worker starts asleep"
    `start()` launches the thread, but the worker's `_is_active` flag is
    `False`, so it only sleeps in 10 ms steps. It decodes nothing until the
    session becomes active.

## Switching the active session

![Flow: setting the active id, same-id guard, Application notification, SessionService, then decode worker manager deactivates the old session and activates the new one](../../../assets/api/managers/switch-light.svg#only-light)
![Flow: setting the active id, same-id guard, Application notification, SessionService, then decode worker manager deactivates the old session and activates the new one](../../../assets/api/managers/switch-dark.svg#only-dark)

Assigning `SessionManager.active_session_id` stores the new id and calls
`Application.handle_active_session_changed(old, new)` →
`SessionService` → `VideoDecodeWorkerManager.switch_active_session`. Assigning
the id that is already active is a no-op. The first activation has `old = None`.

### Decode worker states

![States of a decode worker: constructed, started but inactive, active, and stopped](../../../assets/api/managers/decode-states-light.svg#only-light)
![States of a decode worker: constructed, started but inactive, active, and stopped](../../../assets/api/managers/decode-states-dark.svg#only-dark)

Arrows are transitions; labels name the call that causes them.

| Call | Effect in `VideoDecodeWorker` |
| --- | --- |
| `activate(s_id)` | `set_active(True, resume_idx=current_frame_index)` schedules a seek to the playhead and refills the 90-frame ring buffer |
| `deactivate(s_id)` | `set_active(False)` clears the buffer immediately to release memory |

Both calls catch `ValueError` from the worker, log a warning, and return, so a
switch never raises because a worker was in a transient state.

## Closing sessions

![Flow: close_all or discard_session calls Session.close which stops detection, tracking and decode workers then closes the reader; then the manager forgets the sessions](../../../assets/api/managers/close-light.svg#only-light)
![Flow: close_all or discard_session calls Session.close which stops detection, tracking and decode workers then closes the reader; then the manager forgets the sessions](../../../assets/api/managers/close-dark.svg#only-dark)

`Session.close()` stops the workers in the order shown and then closes the
reader. `close_all()` is used when the application shuts down and before a
project is restored. `discard_session()` removes one session and is used when a
session fails to restore from a project.

## Worked example: user opens a video

See the [sequence diagram on the overview](../managers.md#worked-example-opening-a-video).

1. The user chooses a file. `SessionHandler.on_open_videos` stops all playback
   and calls `Application.open_videos`.
2. `SessionService.open_videos` calls the manager for each path, collects
   successes, and, if no session is active, calls `initialize_active_session`.
3. That assigns the first session's id, which runs the switch flow: the
   decode worker is activated at frame 0.
4. Back in the handler, default preferences are applied, new sessions are
   adopted as Qt children, the first frame is requested and the lists are
   refreshed.

## Failure and cleanup paths

| Situation | Current behaviour |
| --- | --- |
| Duplicate path | `SessionAlreadyExistsException`; no new session |
| `ZeroStreamsInVideoException` | Logged as error; the video is skipped |
| `VideoFileOpenException`, `VideoStreamStateException` | Logged as warning; skipped |
| Any other exception during initialization | Propagates to the caller; the handler shows an error dialog |
| Worker `ValueError` on activate/deactivate | Logged as warning, ignored |

## Limitations and discrepancies

!!! warning "Skipped videos still count as opened"
    `create_session_from_video_path` swallows the three open errors and returns
    nothing, and `SessionService.open_videos` records the path as opened
    anyway. If every video fails there is no `NoNewOpenedSessionsException` and
    no dialog; the failure appears only in the log.

!!! warning "Discard and close do not switch decode workers"
    `discard_session` (when the active session is removed) and `close_all`
    assign the active id directly. `handle_active_session_changed` is **not**
    called, so after discarding the active session the first remaining session
    becomes active but its decode worker keeps whatever state it had (inactive
    if it was never activated or was deactivated).

!!! warning "Partial initialization is not unwound"
    If `VideoDecodeWorker` construction fails after the `VideoReader` was
    opened, the shell is dropped without `Session.close()`; the reader is not
    closed explicitly. Each session also opens a **second** `VideoReader`
    inside its decode worker.

!!! warning "`Session.close()` is not failure-isolated"
    Workers are stopped one after another without `try/except`; an exception
    from one `stop()` prevents later workers and the reader from being closed.
    `VideoDecodeWorker.stop()` waits 500 ms and then calls `terminate()` as a
    last resort.

API details: [`SessionManager`](../../../reference/api/index.md).
