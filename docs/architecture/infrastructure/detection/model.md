# Detection models

Source: `src/app/infrastructure/detection/model`

A detection model is a trained neural network that looks at an image and
guesses which objects it contains and where. Each library that supplies such a
network (Ultralytics, TorchVision, MTCNN) has its own way to load weights, accept
an image and return predictions. This package hides those differences behind
one contract, `BaseDetectionModel.detect(frame, chosen_labels)`, which always
returns a list of `DetectionResult` values (pixel box, label, confidence, item id,
colour).

## Where this sits

![ModelHandler starts ModelLoadWorker, which calls the Application facade, DetectionService, DetectionEngineManager and DetectionEngine; the engine calls load_detection_model, which constructs a provider wrapper and mapper](../../../assets/api/detection_model/context-light.svg#only-light)
![ModelHandler starts ModelLoadWorker, which calls the Application facade, DetectionService, DetectionEngineManager and DetectionEngine; the engine calls load_detection_model, which constructs a provider wrapper and mapper](../../../assets/api/detection_model/context-dark.svg#only-dark)

Arrows are calls down the stack, from a user picking a model in the UI to the
point where a wrapper is constructed. The model package is the bottom of that
chain; it knows nothing about sessions, layers or widgets. See
[Engine](engine.md) for the one-image boundary above it.

## How a model name becomes a wrapper

![Decision chain: the string None gives the dummy model; a name in TORCH_MODELS gives TorchDetectionModel; in ULTRALYTICS_YOLO_MODELS gives YoloDetectionModel; MTCNN-Tensorflow or MTCNN-Pytorch gives the matching MTCNN wrapper; anything else raises DetectionModelError](../../../assets/api/detection_model/dispatch-light.svg#only-light)
![Decision chain: the string None gives the dummy model; a name in TORCH_MODELS gives TorchDetectionModel; in ULTRALYTICS_YOLO_MODELS gives YoloDetectionModel; MTCNN-Tensorflow or MTCNN-Pytorch gives the matching MTCNN wrapper; anything else raises DetectionModelError](../../../assets/api/detection_model/dispatch-dark.svg#only-dark)

Diamonds are checks made in order by `load_detection_model` in `loader.py`;
the first match wins. The registries are plain literals in `names.py`:

| Registry | Maps a display name to | Used by |
| --- | --- | --- |
| `TORCH_MODELS` | `(torchvision function, weights class)` names | `TorchDetectionModel` |
| `ULTRALYTICS_YOLO_MODELS` | a `.pt` weights file name | `YoloDetectionModel` |
| `MTCNN_MODELS` | a tuple of two names, no extra data | `MTCNNTFDetectionModel`, `MTCNNTorchDetectionModel` |

The display name is the UI's dropdown text and the key used throughout the
app; `helpers.py` builds the dropdown list (`"None"` plus every registry key)
and classifies a name into a provider group (`torch`, `yolo`, `mtcnn`, or `all`)
for the provider filter. To add a model, add a registry entry; to add a provider
family, add a package and a branch in the loader.

!!! note "Commented-out entries"

    `names.py` keeps YOLOv6 and YOLO-NAS entries commented out. They are not
    selectable and fall through to `DetectionModelError`.

## Inside one provider package

![A wrapper builds a loader factory once in its constructor, which imports the library and loads weights; detect calls the library, and the mapper filters raw predictions into DetectionResult values](../../../assets/api/detection_model/anatomy-light.svg#only-light)
![A wrapper builds a loader factory once in its constructor, which imports the library and loads weights; detect calls the library, and the mapper filters raw predictions into DetectionResult values](../../../assets/api/detection_model/anatomy-dark.svg#only-dark)

Every provider package has the same three parts:

- **Wrapper (`model.py`)** implements `BaseDetectionModel`. Its constructor
  builds a loader and mapper (both injectable for tests) and **loads the weights
  immediately**, so constructing a wrapper is the slow step.
- **Loader factory (`loader_factory.py`)** imports the provider library lazily
  inside `create()`, so an uninstalled library only fails when its model is
  selected, and wraps any failure in `DetectionModelError`.
- **Mapper (`mapper.py`)** drops predictions below the confidence threshold or
  outside the optional label list and builds `DetectionResult` values.

## The four provider families

| Family | Library | Input handling | Threshold | Labels | Item id | Colour |
| --- | --- | --- | --- | --- | --- | --- |
| YOLO | Ultralytics | RGB array passed directly; `iou=0.45` | 0.25 | From the model's own `names` | `yolo-{n}` | `#8080F0` |
| Torch | TorchVision | `to_tensor(frame)`, `no_grad` | 0.50 | From weights metadata `categories` | `torch-{n}` | `#808080` |
| MTCNN-TF | `mtcnn` | RGB array | 0.90 | Always `person` | `mtcnn-tf-{n}` | `#80F080` |
| MTCNN-Torch | `facenet_pytorch` | PIL image from the array; GPU if available | 0.90 | Always `person` | `mtcnn-torch-{n}` | `#80F080` |
| Dummy | none | ignored | n/a | none | n/a | n/a |

`{n}` is the index within the current frame's raw output, so item ids are only
meaningful per frame. Thresholds are the `DEFAULT_*_CONFIDENCE_THRESHOLD`
constants in `names.py`.

!!! warning "Models are not interchangeable"

    YOLO and Torch models are general object detectors with a fixed class list
    (the COCO-style categories shipped with their weights). The MTCNN wrappers
    detect **faces** and label every one `person`, so selecting a label such as
    `car` with MTCNN returns nothing. `DummyDetectionModel` is chosen by the string
    `"None"` and always returns an empty list; it is the "detection disabled"
    option, not an error.

## Failures

![Loading failures from an unknown name or a missing library become DetectionModelError, shown by the handler as Model Load Failed; during inference YOLO and MTCNN catch and log and return an empty list, while Torch inference errors are not caught here](../../../assets/api/detection_model/failure-light.svg#only-light)
![Loading failures from an unknown name or a missing library become DetectionModelError, shown by the handler as Model Load Failed; during inference YOLO and MTCNN catch and log and return an empty list, while Torch inference errors are not caught here](../../../assets/api/detection_model/failure-dark.svg#only-dark)

The left column is loading, the right column is running a frame; the two have
different policies.

!!! danger "An empty list is ambiguous"

    A YOLO or MTCNN inference exception is logged at warning level and returned
    as `[]`, which is indistinguishable from "nothing detected". Individual
    predictions that fail to map are skipped with a warning. Torch is different:
    only the tensor conversion is guarded, so an error inside the network call
    propagates to the caller (in a detection run, the worker reports it through
    its error signal). The logs are the only place to tell a clean empty frame
    from a failed one.

## Selecting a model at runtime

![User picks YOLOv8n; the handler warns about manual edits, updates settings and starts a ModelLoadWorker thread; the service stops the old worker, resets model layers and asks the engine to load the model; the handler is signalled when finished or failed](../../../assets/api/detection_model/load-sequence-light.svg#only-light)
![User picks YOLOv8n; the handler warns about manual edits, updates settings and starts a ModelLoadWorker thread; the service stops the old worker, resets model layers and asks the engine to load the model; the handler is signalled when finished or failed](../../../assets/api/detection_model/load-sequence-dark.svg#only-dark)

Weights can take seconds to load (and the first use of an Ultralytics or
TorchVision model may download them), so the load runs on a helper thread
rather than the GUI thread; the handler shows progress and owns any error
dialog. The [Detection service](../../application/services/detection.md) decides
what happens to existing layers when the model changes.

## Worked example

!!! example "`YOLOv8n` on one frame"

    1. The engine calls `load_detection_model("YOLOv8n")`. `"None"`, the Torch
       registry and nothing else match; `ULTRALYTICS_YOLO_MODELS["YOLOv8n"]` is
       `"yolov8n.pt"`.
    2. `YoloDetectionModel("yolov8n.pt")` runs `YoloModelLoaderFactory.create`,
       which imports `ultralytics` and calls `YOLO("yolov8n.pt")`. A missing
       package or bad weights raises `DetectionModelError`.
    3. Later, `detect(frame, ["person"])` calls the network with `conf=0.25`,
       `iou=0.45`. Suppose it finds a person at `(40.2, 60.9, 180.5, 300.1)` with
       score 0.91 and a dog with score 0.88.
    4. `YoloDetectionMapper` truncates the box to integers
       `(40, 60, 180, 300)`, looks the class index up in `names`, drops the dog
       because `dog` is not in `["person"]`, and returns one
       `DetectionResult(item_id="yolo-0", label="person", confidence=0.91, ...)`.

## Known limitations

!!! warning "Source observations to verify before relying on them"

    - `MTCNNTFDetectionModel.detect` calls `MTCNN.detect_faces` on the class and
      never uses the instance it loaded (`self._model`), and its mapper reads the
      library's `box` directly as `x1, y1, x2, y2`. The `mtcnn` package documents
      `box` as `[x, y, width, height]`, so TensorFlow-MTCNN boxes may be
      mis-sized. This has not been confirmed by a run.
    - `TorchDetectionModel.detect` is annotated as returning `list[Box]` but
      returns `DetectionResult` values.
    - The package `__init__` exports `YoloDetectionModel`, `TorchDetectionModel`
      and the dummy but not the MTCNN wrappers; import those from their
      subpackages.

For exact signatures see the [API reference](../../../reference/api/index.md).
