# Tracking services

Source: `src/app/application/services/tracking`

Tracking services coordinate the path from reviewed detections to editable
tracks. They validate the selected source, ask a manager to create and start
the worker, then retrieve the completed frame-indexed cache and commit it to
session storage. Algorithm details stay in
[tracking infrastructure](../../infrastructure/tracking.md).

## Starting a run

The supported input layers are A (original detector output) or B (reviewed
detections); C and D are tracking outputs and cannot be used as the source.
The usual workflow is B so user review affects tracking. When B is selected,
the manager seeds missing B frames from A using current label/confidence
filters; existing B data is not replaced by this seeding step. An empty source
is rejected instead of starting a worker with no detections.

Before creating a new worker, the manager checks that no tracking worker is
already running and clears C/D to prevent stale track output from appearing
alongside a new run. The worker receives a snapshot of detections and session
settings, so edits made afterward do not mutate the run's input.

## Committing results to C and D

When the worker completes, `sync_tracking_cache()` retrieves its processed
frame map. Layer C is overwritten with that machine output. Layer D's machine
boxes are refreshed across the full video frame range using the current
tracker-confidence filter, while manually created D annotations are preserved,
including on frames with no current machine result. This is not a blind copy:
D is the review layer and can differ intentionally from C.

The tracking handler requests synchronization before rendering the active
frame/table and selects the tracking tab after completion so the results are
visible. Import/export and direct layer editing use separate collaborators.
The four layer roles are summarized in [Video layers](../../domain/video.md);
strategy choices live in [Tracking domain](../../domain/tracking.md).
