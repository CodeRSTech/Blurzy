# Tracking infrastructure

Source: `src/app/infrastructure/tracking/`

Tracking workers execute selected strategies over frame-indexed detections.
Implementations include Hungarian-style matching, ByteTrack, and DeepSORT
adapters. Before association, per-frame input is deduplicated by same-class
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

Linking is geometry-based and rejects ambiguous assignments; it cannot
guarantee identity through visually similar crossings because the tracking
worker receives boxes rather than frame pixels.
