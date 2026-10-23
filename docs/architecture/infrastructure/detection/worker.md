# Detection worker

Source: `src/app/infrastructure/detection/worker`

`DetectionWorker` processes a session's frames away from the GUI event loop,
calling the selected engine and caching detections by frame. It reports
progress, result batches, completion, and errors through Qt signals; callers
can request a stop and query the result cache through the Application worker
contract. The detection service consumes batches and writes them to session
layers.

Model inference belongs to the [engine](engine.md), and batch-to-layer
behavior belongs to [Detection services](../../application/services/detection.md). Cancellation
is cooperative with the worker loop; it does not interrupt a model call.
