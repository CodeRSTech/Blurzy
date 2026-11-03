# Infrastructure view models

Source: `src/app/infrastructure/views`

The session list on the left of the window needs a title and a one-line
description for each open video. This package holds the single function that
produces them: `list_of_session_list_view_models(sessions)` turns runtime
[`Session`](session.md) objects into
[`SessionFileListViewModel`](../domain/views.md) values.

| Field | Source |
| --- | --- |
| `s_id` | `session.s_id` |
| `title` | `session.s_id.basename` |
| `subtitle` | `"{width}x{height} \| {fps:.2f} fps \| {frame_count} frames"` from `session.state.metadata` |

It is a pure read of session metadata: no Qt, no I/O, no selection state. The
caller is `SessionHandler`, which passes the result to the session-list widget on
the GUI thread.

!!! warning "Limitation"

    The function reads `session.state.metadata` directly, so every session must
    already be initialized. A session shell whose `state` is still `None` raises
    `AttributeError`.

Other UI-facing value models live in [Domain view models](../domain/views.md);
transient selection and history live in [UI view state](../ui/view_state.md).
Session ownership is described in [session infrastructure](session.md).
