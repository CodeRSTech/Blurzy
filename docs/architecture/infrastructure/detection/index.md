# Infrastructure detection

Source: `src/app/infrastructure/detection`

Detecting objects in a video is three separate jobs, and Blurzy keeps them in
three packages so that each can change without the others noticing:

| Package | Job | Page |
| --- | --- | --- |
| `model` | Load one provider's network and translate its output into `DetectionResult` values | [Models and providers](model.md) |
| `engine` | Hold the selected model and answer "what is in this one image?" | [Engine](engine.md) |
| `worker` | Loop over video frames on a background thread, batch results, report progress | [Worker](worker.md) |

## Where this sits

![The Application layer starts a DetectionWorker, which calls DetectionEngine; the engine asks load_detection_model for a YOLO, Torch, MTCNN or Dummy wrapper; every wrapper returns the same list of DetectionResult](../../../assets/api/detection_model/package-map-light.svg#only-light)
![The Application layer starts a DetectionWorker, which calls DetectionEngine; the engine asks load_detection_model for a YOLO, Torch, MTCNN or Dummy wrapper; every wrapper returns the same list of DetectionResult](../../../assets/api/detection_model/package-map-dark.svg#only-dark)

Arrows read top to bottom as ownership and call direction. The four provider
boxes are **alternatives**: one is chosen when the engine is built, not run
in sequence. Whatever is chosen, callers receive the same result shape.

!!! info "Ownership boundaries"

    - The engine does not iterate video; the worker does.
    - Neither decides annotation layers. The Application
      [Detection service](../../application/services/detection.md) stores batches
      as Layer A (original detector output) and seeds Layer B (reviewed,
      editable detections). See [Video layers](../../domain/video.md).
    - Selecting a model is a UI/Application workflow; the model package only
      knows how to turn a name into a wrapper.

## Reading order

1. [Models and providers](model.md): how a name such as `YOLOv8n` becomes a
   wrapper, what each provider family does, and how mappers normalise output.
2. [Engine](engine.md): the one-image boundary and its failure behaviour.
3. [Worker](worker.md): the frame loop, caching and batch signals.
