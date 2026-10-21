# Tracking services

Source: `src/app/application/services/tracking/`

Tracking services validate source data, start a strategy worker, process its
output, and coordinate import/export or layer operations. Raw tracking output
is synchronized to Layer C; editable results use Layer D. When a new tracking
run completes, Layer D's machine-generated boxes are refreshed for the session's
full frame range using the current tracker-confidence filter. Manual Layer D
annotations are retained, including on frames with no current machine track.

`TrackingHandler` synchronizes the worker cache before rendering the active
frame and tracking table. The tracking tab is selected after completion so the
new output is immediately visible.

See [Tracking interfaces](../interfaces/tracking.md) for the worker boundary,
[tracking infrastructure](../../infrastructure/tracking.md) for algorithms
and post-processing, and [tracking domain types](../../domain/tracking.md) for
strategy selection.
