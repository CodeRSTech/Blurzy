# Detection domain

Source: `src/app/domain/detection/`

`Box` is the shared bounding-box value used by detection and tracking;
`DetectionResult` represents one model inference result, and `BoxSource`
classifies whether a displayed box came from detection, tracking, or manual
annotation. `AnnotationContextActions` names the editing actions available to
the annotation workflow. UI-facing rows are represented separately by
[`BBoxViewModel`](views.md).

Application services convert inference results into session layer data. The
four layer roles are summarized in [Architecture](../../architecture.md);
related values include [video layers](video.md) and
[tracking strategy](tracking.md).
