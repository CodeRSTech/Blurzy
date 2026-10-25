# Qt workers

Source: `src/app/ui/qt/workers`

`ModelLoadWorker` performs the potentially slow setup of a selected model away
from the Qt window's event loop. It emits completion or error signals so the
model-selection UI can remain responsive while loading. The handler owns the
user-facing progress/error response and applies the selected model after a
successful result.

This UI worker is intentionally different from video-wide detection,
tracking, decoding, and export workers. Those implement infrastructure
workflows, are started through Application services/managers, and report
results via application-owned contracts. The model-loading worker exists to
keep UI setup asynchronous; it does not read video frames or populate Layers A
and B.

See [UI handlers](../handlers.md),
[Detection services](../../application/services/detection.md), and
[detection infrastructure](../../infrastructure/detection/index.md).
