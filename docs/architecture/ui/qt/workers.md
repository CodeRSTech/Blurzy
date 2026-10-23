# Qt workers

Source: `src/app/ui/qt/workers`

This package contains UI-oriented background work, currently asynchronous
detection-model loading through `ModelLoadWorker`, so model setup does not
block the window's event loop. It is distinct from video-wide detection,
tracking, decoding, and export workers, which belong to Infrastructure and
have Application contracts.

The model handler coordinates the UI worker's completion and error
presentation; model execution and session workflows are handled by the
[Application detection service](../../application/services/detection.md) and
[detection infrastructure](../../infrastructure/detection/index.md).
