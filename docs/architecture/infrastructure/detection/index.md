# Infrastructure detection

Source: `src/app/infrastructure/detection`

Detection infrastructure forms a three-step boundary between model providers
and application workflows:

1. **Models** load provider libraries and map provider outputs into
   `DetectionResult` values.
2. **Engine** resolves a selected model and gives callers one-image inference.
3. **Worker** reads video frames, invokes the engine off the GUI thread, caches
   results, and emits bounded batches for Application to store.

The engine does not iterate video, while the worker does not decide the
annotation layer policy. See the
[Detection service](../../application/services/detection.md) for how those
batches become A/B data.

## Packages

- [Engine](engine.md)
- [Models and providers](model.md)
- [Worker](worker.md)
