# Tracking domain

Source: `src/app/domain/tracking`

`TrackingStrategy` is the domain enumeration used to select a tracking
algorithm. Per-session tracking options—including source layer, association
thresholds, confidence decay, appearance dimension, and optional offline
stitching—are stored in [`ProcessingSettings`](export.md). The enum does not
implement an algorithm.

Algorithms, post-processing, and the worker live in
[tracking infrastructure](../infrastructure/tracking.md); Application
validation and result placement are in [Tracking services](../application/services/tracking.md).
Inputs and outputs use [detection boxes](detection.md) and [video layers](video.md).
