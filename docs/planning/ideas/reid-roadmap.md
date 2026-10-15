# Tracking & Headless Redaction Roadmap

## Context & Problem Statement
Standard online trackers (Hungarian IoU, ByteTrack, Kalman/DeepSORT) operate strictly forward in time (causal). When an object detector misses a subject for several frames due to motion blur, profile turns, or partial occlusion:
1. Forward-only Kalman velocity predictions drift linearly off-target, causing failure to re-associate when the detection returns.
2. Increasing tracker `max_age` blindly causes "ghost blur boxes" to persist over empty backgrounds after a subject walks out of frame.

Because Blurzy processes complete video sessions (Layers A/B populated prior to Layer C/D tracking), tracking does not need to be restricted to causal, single-pass heuristics.

---

## Planned Enhancements (Ranked by ROI vs. Complexity)

### Phase 1: Offline Tracklet Stitching + Gaussian Smoothed Interpolation (GSI)
- **Target Component:** `TrackingResultProcessor` (`src/app/application/services/tracking/result_processor.py`)
- **Mechanism:**
  1. **Bidirectional Midpoint Stitching:** Group Layer C output into tracklets. For any tracklet $A$ ending at frame $t_1$ and tracklet $B$ starting at $t_2$ ($1 < t_2 - t_1 \le 25$), project $A$ forward to $t_{\text{mid}}$ using its tail velocity and project $B$ backward to $t_{\text{mid}}$ using its head velocity. Link matching tracklets via Hungarian assignment.
  2. **Gaussian Smoothed Interpolation (GSI):** Replace linear interpolation and jittery detector boxes across linked gaps with Gaussian kernel regression parameterized by adaptive lengthscale $\ell = \tau \log(\tau^3 / N)$.
- **Why First:** Requires zero new dependencies (pure NumPy), zero UI changes, and eliminates floating ghost boxes because unconfirmed coasting tails that never reconnect to a future detection are discarded.

### Phase 2: Lightweight Detection-Time Appearance Embeddings (Re-ID)
- **Target Components:** `DetectionEngine`, `Box` (`src/app/domain/detection/box.py`), `BBoxViewModel`
- **Mechanism:**
  - Because `DetectionWorker` already holds the decoded `RGBFrame` in memory while `TrackingWorker` operates purely on box metadata (`ListOfBoxesByFrameIndexAsDict`), compute a compact normalized feature embedding (e.g., via `torchvision.models.mobilenet_v3_small` or `OSNet` on $128 \times 64$ crops) during detection.
  - Store `embedding: tuple[float, ...] | None` on `BBoxViewModel`.
  - Combine Cosine Distance of EMA tracklet embeddings with Bidirectional Midpoint IoU during Tracklet Stitching and DeepSORT association.
- **Compute Impact:** ~2–3 ms per frame (negligible compared to Faster R-CNN ResNet50 FPN V2 inference), while keeping `TrackingWorker` 100% frame-free.

### Phase 3: Closed-Loop Optical Flow Verification for Unbridged Tails
- **Target Component:** `TrackingWorker` (`src/app/infrastructure/tracking/track_worker.py`)
- **Mechanism:** When a subject is missed right before exiting the frame (no future detection to stitch to), run Lucas-Kanade Forward-Backward optical flow on keypoints inside the last confirmed box. Terminate the track immediately when forward-backward error exceeds 2.0 px.