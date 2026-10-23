# Bounding box

A bounding box describes where an object appears in a video frame. Blurzy uses
the `BBoxXYXYTuple` format: `(x1, y1, x2, y2)`, where the first point is the
top-left corner and the second is the bottom-right corner in image pixels.

![An example XYXY box with its coordinates and view-model attributes](../../assets/api/box/bounding-box-light.svg#only-light)
![An example XYXY box with its coordinates and view-model attributes](../../assets/api/box/bounding-box-dark.svg#only-dark)

`Box` is the shared domain value for detection and tracking data.
`DetectionResult` specializes it for model inference output. Before a detection
is presented to the UI, it is converted into a `BBoxViewModel`: the item's
identity becomes `id`, its origin is recorded as `source`, and the label,
coordinates, confidence, and display color are carried across. The view model
also provides presentation-oriented metadata, including a selection key and
tracking observation state.

The diagram uses a detection as an example. Tracking and manually created boxes
use the same visual geometry, while their source and other metadata depend on
how the box was produced.

See [detection values](detection.md) and [view models](views.md) for the
package-level roles; the generated API reference documents their full fields
and behavior.
