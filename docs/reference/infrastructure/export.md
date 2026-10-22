# Export infrastructure

Source: `src/app/infrastructure/export/`

`ExportWorker` runs a single-session video export on a background Qt thread.
It delegates frame rendering to the Application `ExportService`, reports
progress and outcome, and supports cooperative cancellation through the
service's progress callback. `ExportAllWorker` processes its requested
sessions sequentially through the detect/track/export workflow and can stop
the batch; its stop behavior is not equivalent to interrupting an active
render operation.

The current video-rendering implementation is
`src/app/application/services/export_service.py`; annotation file interchange
is separate. See [export contracts](../application/interfaces/export.md),
[Application service helpers](../application/services/helpers.md), and
[tracking infrastructure](tracking.md).
