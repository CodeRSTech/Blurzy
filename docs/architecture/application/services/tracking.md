# Tracking services

Source: `src/app/application/services/tracking`

Tracking links detections of the same object across frames into **tracks**
(a stable ID per object). The Application tracking services start a worker from
reviewed detections and commit its finished tracks into layers C and D.
Algorithm details are in [tracking infrastructure](../../infrastructure/tracking.md).

![Sequence: the handler starts TrackingService, the manager validates and seeds, the worker runs, then the handler requests sync into C and D](../../../assets/api/app_services/tracking-run-light.svg#only-light)
![Sequence: the handler starts TrackingService, the manager validates and seeds, the worker runs, then the handler requests sync into C and D](../../../assets/api/app_services/tracking-run-dark.svg#only-dark)

Arrows are calls or signals in time order. The **tracking handler** connects
the worker's signals and later calls `sync_tracking_cache`; the services never
connect them.

| Part | Role |
| --- | --- |
| `TrackingService` | Facade-facing entry: coverage check, start, sync |
| [`TrackingWorkerManager`](../managers.md) | Validates the source, clears C/D, creates the worker |
| `TrackingResultProcessor` | Writes finished tracks into C and D |

## Before starting: coverage check

`get_detection_frame_coverage` returns `(frames with A entries, total frames)`.
An **empty A entry counts as processed**; a missing entry does not. The UI uses
it to offer **Okay** or **Proceed Anyway** on partial coverage before anything
is cleared; running detection must finish first.

!!! note "Evidence, not proof"
    Imported or older projects only provide stored entries, not proof that a
    detection run completed.

## Starting a run

The service logs the request, rejects an empty session id
(`InvalidSessionIdException`), and delegates to the manager, which:

1. rejects a second run (`TrackingWorkerAlreadyRunningException`);
2. accepts only **A or B** as source (`UnsupportedLayerException` for C/D);
3. for B, **seeds missing B frames from A** with filtered clones; existing B
   frames are never replaced;
4. rejects an empty source (`EmptyLayerException`);
5. **clears C and D**;
6. builds the worker from the source layer, session state, and strategy; the
   adapter starts it immediately (`start=True`).

![Source layers A and B feed the TrackingWorker; its output overwrites C, and D's machine boxes are replaced from C](../../../assets/api/app_services/tracking-layers-light.svg#only-light)
![Source layers A and B feed the TrackingWorker; its output overwrites C, and D's machine boxes are replaced from C](../../../assets/api/app_services/tracking-layers-dark.svg#only-dark)

Arrows show data flow. B is the usual input so human review influences the
tracks; the dashed arrow is the alternative (A as input).

!!! warning "C and D are cleared before the worker finishes"
    Earlier manual D edits are lost when a new run starts, and a failed run
    leaves C/D empty. The worker deep-copies the source detections and the
    session settings at construction, so later edits do not change that run.

## Committing results

When the worker emits `finished_processing`, the handler calls
`sync_tracking_cache`, which fetches the worker's frame-indexed tracks
(`TrackingWorkerNotFoundException` if there is no worker) and asks the result
processor to:

- **overwrite C** with the tracks (machine output, never hand-edited);
- **replace D's machine boxes** across the whole frame range using the current
  tracker-confidence filter, **keeping manual D boxes**.

D can therefore differ from C on purpose. After syncing, the handler selects
the tracking tab and re-renders the frame. A worker failure arrives through
`error_occurred`, handled by the handler's `_on_tracking_failed`.

## Editing D afterwards

Directional deletion of a track's occurrences edits only D, excluding the
current frame. Display IDs such as `-4` resolve to stored keys such as
`track:-4`. Frames missing from D in older projects are first seeded from C
with the same filter; deleting the last box leaves an initialised empty frame
so later reads cannot resurrect it from C. That logic belongs to the tracking
layer service; see [Layer services](layers.md). Layer roles:
[Video layers](../../domain/video.md); strategies:
[Tracking domain](../../domain/tracking.md).
