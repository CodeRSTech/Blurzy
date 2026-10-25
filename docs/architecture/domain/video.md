# Video domain

Source: `src/app/domain/video`

This package defines video metadata, playback position/status, navigation
direction, annotation-layer identifiers and UI groups, and a bounded ring
buffer for sequential frame access. These types describe state and data
boundaries; opening files and decoding pixels are Infrastructure responsibilities.

## Four annotation and tracking layers

The A/B/C/D split preserves machine output separately from user corrections:

| Layer | Meaning | Typical writer |
| --- | --- | --- |
| **A** | Detector-produced boxes, retained as the machine detection source for review and tracking. Current detection settings (selected labels and minimum confidence) are applied before storage. | Detection batch processor |
| **B** | Reviewed/editable detections seeded from A. Machine boxes can be refreshed; manual edits remain user-owned. This is normally the tracking input. | Detection workflow and annotation handlers |
| **C** | Machine tracking output, including configured post-processing such as tracklet stitching and GSI. | Tracking result synchronization |
| **D** | Reviewed/editable tracks seeded or refreshed from C. Manual D annotations are preserved across machine refresh. | Tracking workflow and annotation handlers |

Detection normally flows A → B. Tracking accepts A or B (normally B) and
produces C → D. A and C are the machine-result layers; B and D are where the
user reviews and edits. “Original” here means the retained machine result at
that stage; it does not mean raw unfiltered provider tensors. Detection
label/confidence selection is applied before A is stored.

Blurred-video export chooses populated D first and falls back to C when D is
empty. Detection annotation interchange can instead use its detection layer.
Preview controls are separate from Render settings; visibility of an editor
overlay does not determine which boxes or blur settings are used in exported
video.

## Frame cache and session values

The ring buffer retains a bounded window of decoded frame indices for playback.
It is a cache, not project persistence: it can be cleared and refilled from the
source video. `SessionState` holds playback and settings alongside metadata;
the infrastructure [session](../infrastructure/session.md) owns the live
reader, workers, and annotation store.

See [detection](detection.md), [tracking](tracking.md),
[ProcessingSettings](export.md), and the
[video decode workflow](../infrastructure/video.md).
