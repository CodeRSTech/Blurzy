# Detection models

Source: `src/app/infrastructure/detection/model`

This package isolates provider-specific model loading and output conversion
from the rest of the application. The engine asks the loader for one named
wrapper; the wrapper uses its provider library and mapper to return Blurzy's
common `DetectionResult` values. Callers therefore handle a stable result
shape, while the wrappers remain responsible for provider-specific input,
weights, thresholds, and output formats.

The current integrations include Ultralytics YOLO, TorchVision, and MTCNN
variants. These are not interchangeable capabilities: for example, a face
detector and a general object detector do not recognize the same classes.
Supported model names are maintained in the literal registries in `names.py`,
which the generated API catalog reads rather than duplicating in this guide.

Provider wrappers also differ in failure behavior. A YOLO inference exception
is logged and converted into an empty result list, while load failures raise a
detection-model error and other uncaught exceptions can propagate. An empty
list therefore does not always distinguish “no objects” from inference
failure. See the [engine guide](engine.md) for the call boundary, example, and
failure behavior; dependencies and locally available weights depend on the
chosen integration and runtime.
