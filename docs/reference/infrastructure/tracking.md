# Tracking infrastructure

Source: `src/app/infrastructure/tracking/`

Tracking workers execute selected strategies over frame-indexed detections.
Implementations include Hungarian-style matching, ByteTrack, DeepSORT, and
BoT-SORT. Before association, per-frame input is deduplicated by same-class
intersection-over-minimum-area containment; boxes suppressed as nested
duplicates are unioned into the retained bounds to preserve coverage.

Strategy outputs tag detection-backed observations separately from coasted
predictions. When offline stitching is enabled (the default), the worker links
compatible tracklets across up to 25 missed frames and uses Gaussian Smoothed
Interpolation (GSI) to replace coast drift inside accepted gaps. Unbridged tails
decay at twice the configured per-frame confidence penalty and are capped at six
frames. Disabling offline stitching bypasses linking and GSI and produces
causal, normally decaying coast estimates. The maximum gap and GSI smoothness
are session settings.

When the session has a local video file, the worker reads its frames and
extracts frame-aware appearance embeddings for DeepSORT, BoT-SORT, and offline
tracklet linking. The configured vectors are 128, 256, or 512 dimensions.
Linking combines appearance evidence with geometry and size checks; appearance
vectors are used only when valid frame crops are available. If the session
path is absent or is not a file, the worker proceeds without frame-derived
appearance features. A file that exists but cannot be opened is reported as a
worker error rather than silently treated as a no-frame fallback.

The worker consumes detections from an Application-selected source layer and
returns frame-indexed results for Application services to place in Layers C
and D. See [Tracking services](../application/services/tracking.md),
[tracking contracts](../application/interfaces/tracking.md), and
[tracking domain values](../domain/tracking.md).
