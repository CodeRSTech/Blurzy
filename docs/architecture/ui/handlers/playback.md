# Playback handler

Implementation: `src/app/ui/handlers/playback_handler.py`

Pressing **Play** looks simple, but smooth playback needs three things to line
up: a timer that decides *when* to show the next frame, a background decoder
that has already prepared that frame, and a render step that paints it.
`PlaybackHandler` is the GUI-thread piece that owns the timer and the transport
buttons; it does not decode anything itself.

## Where it sits

![PlaybackHandler calls the UIController, Application facade, SessionService, and SessionManager to reach the session and frame accessor, which the decode worker fills](../../../assets/api/ui_handlers/sits_playback-light.svg#only-light)
![PlaybackHandler calls the UIController, Application facade, SessionService, and SessionManager to reach the session and frame accessor, which the decode worker fills](../../../assets/api/ui_handlers/sits_playback-dark.svg#only-dark)

Arrows are calls. The decode worker runs on its own thread and fills the
buffer; see [video infrastructure](../../infrastructure/video.md) for how.
For the whole stack, see the [big picture](../../big-picture.md).

## Structure

![Transport panel signals reach PlaybackHandler, which starts and stops a QTimer, tells the Application facade to step or seek, and asks the UIController to render](../../../assets/api/ui_handlers/playback_structure-light.svg#only-light)
![Transport panel signals reach PlaybackHandler, which starts and stops a QTimer, tells the Application facade to step or seek, and asks the UIController to render](../../../assets/api/ui_handlers/playback_structure-dark.svg#only-dark)

The transport panel emits button signals that the handler connects directly.
The seek slider is the exception: its `seek_pos_changed` signal is connected by
`UIController`, which forwards to `on_seek`.

## Playing or stopped

![Stopped and playing states with the events that move between them](../../../assets/api/ui_handlers/playback_states-light.svg#only-light)
![Stopped and playing states with the events that move between them](../../../assets/api/ui_handlers/playback_states-dark.svg#only-dark)

Arrows are state transitions. Stepping to the next or previous frame, or
seeking, **stops** playback first and then moves a single frame.

## What one timer tick does

![Decision flow of one playback tick: check selection, last frame, buffered frame, then render or skip](../../../assets/api/ui_handlers/playback_tick-light.svg#only-light)
![Decision flow of one playback tick: check selection, last frame, buffered frame, then render or skip](../../../assets/api/ui_handlers/playback_tick-dark.svg#only-dark)

Each tick first checks that a session is selected and that it is not at the
last frame. It then asks the Application whether a buffered frame is ready; that
call also advances the frame index when it succeeds. A ready frame is rendered,
and a missing one is skipped so the next tick can try again.

!!! warning "Current behaviour"

    - The buffered-frame check can **block the GUI thread for up to about 2
      seconds** while it waits for the decode worker, so a slow decoder can
      stall the window rather than only dropping a frame.
    - Seeking fires only when the slider is released, stops playback, and does
      not resume it; a `FIXME` in the code records this.
    - `PlaybackHandler.render_frame_requested` is declared but never emitted.

## Worked example: pressing Play

![Sequence from the Play click through the handler, timer, Application, session, and decode worker to the rendered frame](../../../assets/api/ui_handlers/playback_example-light.svg#only-light)
![Sequence from the Play click through the handler, timer, Application, session, and decode worker to the rendered frame](../../../assets/api/ui_handlers/playback_example-dark.svg#only-dark)

1. The click reaches `on_play`, which asks the Application to mark the session
   as playing and reads the frame interval derived from the video's frame rate.
2. The handler starts its `QTimer` with that interval and updates the status
   bar.
3. Meanwhile the decode worker keeps the ring buffer ahead of the playhead.
4. Every tick consumes one buffered frame and calls
   `UIController.render_frame_for_session_id`, which repaints the preview, frame
   label, slider, and status bar (see [rendering](window-and-dialogs.md#the-render-pipeline)).
5. At the last frame, on an error, or when another session is selected, the
   handler stops the timer and playback state.

!!! note "Ownership"

    The handler owns the timer and button wiring. The session owns the playhead
    and playing flag, and the decode worker owns the buffer.
    Session switching is described in [session handlers](session-and-projects.md).
