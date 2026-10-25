# Detection domain

Source: `src/app/domain/detection`

`DetectionResult` is the provider-neutral value returned for one model
prediction. It carries a label, confidence, box coordinates, and an identifier;
the detection engine and provider mapper keep their library-specific result
objects behind that boundary. The shared `Box` geometry is reused by detection
and tracking, while `BoxSource` records whether a view-model box represents
detection, tracking, or manual annotation.

Before displaying or editing a result, the application maps it to a
`BBoxViewModel`. That value adds presentation and interaction metadata such as
an identity key, source, display color, and tracking observation age. This
conversion is why an inference result and an editable annotation are related
but not the same object. See [Bounding box](bounding-box.md) and
[view models](views.md).

The detection service applies selected-label and confidence filters before it
stores machine results in A and refreshes B's machine boxes. User-created
boxes remain separate from model output; see the
[four-layer workflow](video.md) and [Detection services](../application/services/detection.md).
