# Video infrastructure

Source: `src/app/infrastructure/video`

A video file is a compressed stream; getting one picture out of it takes real
work. Blurzy splits that work between two classes:

| Class | Job | Thread rule |
| --- | --- | --- |
| `VideoReader` | Opens the file with PyAV, reports metadata, and decodes frames to rotated RGB arrays | **Not thread-safe.** Give each decoding thread its own instance |
| `VideoDecodeWorker` | A `QThread` that keeps a window of upcoming frames decoded in a ring buffer so playback never waits for the decoder | Owns its own reader; talks to other threads through a mutex, the buffer's lock, and one signal |

Both are attached to a runtime [Session](session.md). The session also holds a
*separate* `VideoReader` (`session.video_reader`) that supplied the metadata at
open time; the decode worker opens a second one for itself.

## Reader: metadata and frames

Opening a reader selects the first video stream and builds the domain metadata
(size, frame rate, frame count, duration). Rotation comes from stream metadata,
stream side data, or an MP4 container fallback; a user rotation is added on top,
and quarter turns swap width and height. Every returned frame is rotated and made
contiguous in memory (padding bytes from PyAV can crash `QImage`).

Two read modes exist:

- **Sequential** (`read_next_frame`) returns `(index, frame)` and counts frames
  one by one, ignoring variable-frame-rate timestamps. A new reader starts at
  index 0.
- **Indexed** (`read_frame_at_index`) decodes forward when the target is at most
  60 frames ahead of the reader's position; otherwise it seeks the container to
  the target timestamp, anchors its counter on the first decoded frame once, and
  counts sequentially again.

!!! warning "Failure shapes differ"

    Stream exhaustion raises `EndOfVideoStreamException`
    (the `read_next_frame` docstring says `ValueError`; the code raises the
    custom exception). An indexed read raises `VideoReadFrameException` for decode
    errors but returns `None` when the target cannot be reached. A permission
    error closes and reopens the file, rewinds to frame 0, and returns `None`.
    Callers must handle both shapes.

## `VideoDecodeWorker`: the playback buffer

`VideoDecodeWorker` is the piece that makes playback smooth. Decoding one frame
can take longer than a frame interval, and seeking is slower still. The worker
therefore decodes on its own thread, a little *ahead* of what the user is
watching, and stores the pictures in a
[`VideoRingBuffer`](../domain/video.md) of 90 frames. The GUI thread only ever
*looks frames up*; it does not decode during normal playback.

!!! info "Two words used below"

    **Playhead**: `PlaybackState.current_frame_index`, the frame the user is on.
    The GUI thread writes it; the worker reads it (without a lock) to decide how
    far ahead to decode. **Hard seek**: discard the buffer, jump the reader to a
    requested frame, and restart the buffer there.

### Who calls it

![Sequence of calls: the decode manager activates the worker at the playhead, the worker refills the buffer and signals the GUI; later the GUI asks the session for frames, which looks in the buffer and requests a seek only on a far miss](../../assets/api/video/callers-light.svg#only-light)
![Sequence of calls: the decode manager activates the worker at the playhead, the worker refills the buffer and signals the GUI; later the GUI asks the session for frames, which looks in the buffer and requests a seek only on a far miss](../../assets/api/video/callers-dark.svg#only-dark)

Arrows are calls or signals, top to bottom in time. Different callers use
different methods:

| Caller | Method | When |
| --- | --- | --- |
| `SessionInitializer` | construct + `start()` | Session open. The thread runs immediately but is **inactive** and just sleeps |
| `VideoDecodeWorkerManager` (Application) | `set_active(True, resume_idx)` / `set_active(False)` | On active-session switch: the old session is deactivated, the new one activated at its playhead |
| `SessionFrameAccessor` (through `Session.get_*_frame`) | `get_cached_frame_at_index`, `request_seek` | Every frame fetch: playback tick, scrub, step, detection of the current frame |
| `Session.close()` | `stop()` | Teardown |

The UI also listens: `SessionHandler` connects `signals.seek_completed` (single
shot) so that, once the first frame after opening is buffered, a paused view
renders it. The signal is emitted from the worker thread; Qt delivers it to the
GUI thread's slot.

!!! note "Ownership boundary"

    The Application manager only toggles activity. It never touches the buffer,
    the reader, or the loop. Buffer lookups and seek requests belong to the
    session's frame accessor, described in [Session](session.md#frame-access).

### The playhead, the buffer, and seeking

![The playhead sits inside a 90-slot ring buffer: frames behind it are kept until overwritten, frames ahead are filled by the worker until the newest frame reaches playhead plus 45; a seek clears the buffer and restarts the window at the target](../../assets/api/video/window-light.svg#only-light)
![The playhead sits inside a 90-slot ring buffer: frames behind it are kept until overwritten, frames ahead are filled by the worker until the newest frame reaches playhead plus 45; a seek clears the buffer and restarts the window at the target](../../assets/api/video/window-dark.svg#only-dark)

Solid arrows are the steady state; dashed arrows are the seek path. In the
steady state the worker decodes forward until its newest frame is 45 or more
frames ahead of the playhead, then pauses (the *throttle line*). As playback
moves, the gap shrinks and decoding resumes. The ring holds one contiguous index
range: once more than 90 frames are stored, the oldest is overwritten, so
roughly the last 44 frames behind the playhead stay available for stepping back.

A hard seek is requested in two cases: activation (`set_active(True)` schedules a
seek to `resume_idx`) and a far cache miss from the frame accessor.
`request_seek` records the target and clears the buffer immediately, on the
caller's thread, so stale frames cannot satisfy the lookup; the worker performs
the decode on its next loop pass.

### The decode loop

![Flowchart of the worker loop: sleep while inactive; handle a pending seek by clearing, reading the target, pushing it and emitting seek_completed; throttle when 45 frames ahead; otherwise read and push the next frame; end of stream and errors are logged paths that keep the loop running](../../assets/api/video/loop-light.svg#only-light)
![Flowchart of the worker loop: sleep while inactive; handle a pending seek by clearing, reading the target, pushing it and emitting seek_completed; throttle when 45 frames ahead; otherwise read and push the next frame; end of stream and errors are logged paths that keep the loop running](../../assets/api/video/loop-dark.svg#only-dark)

Each pass makes exactly one decision, in this order: inactive, seek, throttle,
decode. The seek request is read and cleared under the mutex, so the newest
request wins and earlier ones are dropped. After a seek, sequential reading
continues from where the reader landed, so playback proceeds without another
seek.

| Resource or limit | Value | Where it lives |
| --- | --- | --- |
| Ring buffer capacity | 90 frames | Hard-coded in the worker constructor; not configurable |
| Decode-ahead threshold | playhead + 45 | Hard-coded in `run()` |
| Idle / throttle sleep | 10 ms | Inactive and throttled passes |
| End-of-stream sleep | 100 ms | Worker stays alive after the last frame |
| Frame fetch timeout | 2 s, polled every 10 ms | Frame accessor, not the worker |
| Deactivation | clears the buffer | Releases cached image memory for background sessions |

??? warning "Failure and limitation notes (read from the code)"

    - A failed seek never emits `seek_completed`. An exception is logged; a
      reader that returns `None` is dropped **silently**. The requester then
      times out after 2 s.
    - A sequential read error is logged and retried on the next pass with no
      sleep, so a persistent error can log repeatedly.
    - The playhead is read across threads without a lock; the worker may act on a
      slightly stale value, which only affects how far ahead it decodes.
    - The worker never advances the playhead; only frame lookups on the GUI side
      do.

### Shutdown

`Session.close()` calls `stop()`: clear the running flag, `quit()`, wait up to
500 ms, `terminate()` as a last resort if the thread is stuck, then close the
worker's reader. Callers should not delete the thread before `stop()` returns.

!!! tip "Do not confuse the caches"

    The ring buffer caches decoded **pixels**. The detection worker caches
    **inference results**, and the session store holds **annotations**.
    Clearing the ring buffer, including deactivation, does not delete layers A-D.

Playback state and the buffer type belong to the [video domain](../domain/video.md).
Session wiring and teardown: [session infrastructure](session.md) and
[application managers](../application/managers.md). Signatures:
[generated API reference](../../reference/api/index.md).
