# Detection worker

Source: `src/app/infrastructure/detection/worker/`

`DetectionWorker` reads video frames, runs inference through the selected
engine, and emits result batches and progress from a background Qt thread.

**Expand this stub with:** thread lifecycle, batch size, cancellation, and
signal ownership.

