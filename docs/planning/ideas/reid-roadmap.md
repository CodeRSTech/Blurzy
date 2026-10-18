# Tracking & Headless Redaction Roadmap

???+ abstract "Context & Problem Statement"

    Standard online trackers (Hungarian IoU, ByteTrack, Kalman/DeepSORT) operate strictly forward in time (causal). When an object detector misses a subject for several frames due to motion blur, profile turns, or partial occlusion:
    1. Forward-only Kalman velocity predictions drift linearly off-target, causing failure to re-associate when the detection returns.
    2. Increasing tracker `max_age` blindly causes "ghost blur boxes" to persist over empty backgrounds after a subject walks out of frame.
    Because Blurzy processes complete video sessions (Layers A/B populated prior to Layer C/D tracking), tracking does not need to be restricted to causal, single-pass heuristics.

## Implemented tracking capabilities

- **Offline tracklet stitching and GSI:** `src/app/infrastructure/tracking/post_processor.py` links compatible tracklets bidirectionally using projected geometry and optional appearance embeddings, then fills accepted gaps with Gaussian Smoothed Interpolation.
- **Frame-aware Re-ID:** `TrackingWorker` extracts appearance embeddings from decoded video frames through `PartBasedAppearanceEmbedder`. DeepSORT, BoT-SORT, and offline stitching can use these embeddings; embedding dimensions are configurable as 128, 256, or 512.
- **Privacy Shield:** Optional post-processing applies anti-shrink sizing, bounded pre-detection extrapolation, post-detection holds, and safety-margin inflation.

## Deferred enhancement

### Closed-Loop Optical Flow Verification for Unbridged Tails
- **Target Component:** `TrackingWorker` (`src/app/infrastructure/tracking/track_worker.py`)
- **Mechanism:** When a subject is missed right before exiting the frame (no future detection to stitch to), run Lucas-Kanade Forward-Backward optical flow on keypoints inside the last confirmed box. Terminate the track immediately when forward-backward error exceeds 2.0 px.
- **Caution:** Optical-flow termination needs validation on representative motion and occlusion data; it must not silently remove redaction coverage.