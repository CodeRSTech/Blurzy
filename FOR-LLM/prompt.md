# Implementation Plan: "Privacy Features" Collapsible Panel, Anti-Shrink / Pre-Post Padding Post-Processing, ByteTrack Fix, and README.md Sync

## 0. Documentation & MkDocs / `mkdocstrings` Mandate (CRITICAL)
This repository builds its documentation with **MkDocs Material** and **`mkdocstrings`** (`mkdocs.yml`), governed by `scripts/docs_reference.py`, `docs/engineering/documentation-style.md`, and `docs/engineering/reference-documentation.md`:
1. **Static Analysis Compatibility (`allow_inspection: false`):**
   - `mkdocstrings` runs with `allow_inspection: false`, `docstring_style: google`, `docstring_section_style: spacy`, `show_signature_annotations: true`, and `filters: ["!^_", "^__init__$"]`.
   - Every new or modified module, class, dataclass, method, property, and function **must** have complete type annotations and a Google-style docstring (`Args:`, `Returns:`, `Raises:`, `Attributes:`, `Note:`, and `Example:`).
2. **Inline Mathematical & Algorithmic Comments:**
   - Include step-by-step inline comments for all calculations: asymmetric size-ratchet hysteresis (resisting box shrinkage while embracing expansion), top-anchor-preserving vertical extension (keeping head coverage when lower-body detection drops), pre-detection backward extrapolation ($T_{\text{pre}}$), post-detection forward hold ($T_{\text{post}}$), and safety margin inflation.
   - Use standard LaTeX math notation (`$...$` or `$$...$$`) in docstrings where helpful for MathJax (`pymdownx.arithmatex`).
3. **UI Tooltips (`setToolTip`):**
   - Every new or modified UI widget and its corresponding label in `src/app/ui/qt/sections/right_panel.py` **must** set a clear, multi-sentence tooltip via `.setToolTip(...)`.
4. **Reference Docs Verification:**
   - Ensure `python scripts/docs_reference.py` and `pytest tests/test_docs_reference.py` pass without warnings or errors.

---

## 1. Diagnose and Fix `ByteTrack` (`src/app/infrastructure/tracking/bytetrack_strategy.py`)

### Root Causes to Fix
1. **Stage 1 Threshold Starvation:**
   - In Blurzy, Layer A and Layer B detections are already filtered by `DEFAULT_YOLO_CONFIDENCE_THRESHOLD` (`0.25`), `DEFAULT_TORCH_CONFIDENCE_THRESHOLD` (`0.50`), and `settings.min_detection_confidence`.
   - If `ByteTrackStrategy` uses a hardcoded high threshold (e.g., `0.60`) that exceeds the typical confidence of incoming detections, Stage 1 receives few or no detections, and **new tracks fail to initialize** (or existing tracks fail to match in Stage 1).
2. **Adaptive Two-Stage Split & Immediate Track Emission:**
   - Refactor `ByteTrackStrategy` (`src/app/infrastructure/tracking/bytetrack_strategy.py`) so that:
     - The Stage 1 / Stage 2 confidence boundary $\tau_{\text{high}}$ adapts dynamically to the session settings and frame detections:
       $$\tau_{\text{low}} = \min(\text{min\_tracker\_confidence}, \text{min\_detection\_confidence}, 0.10)$$
       $$\tau_{\text{high}} = \max(\tau_{\text{low}} + 0.05, \min(0.50, \text{median\_frame\_conf} - 0.05))$$
       so that normal detections always qualify for Stage 1 matching and new track birth, while lower-confidence detections ($\tau_{\text{low}} \le c < \tau_{\text{high}}$) are routed to Stage 2 to rescue partially occluded subjects.
     - **No Warmup Blindness:** Newly initialized tracks from unmatched Stage 1 detections (and manual boxes) must be emitted immediately on their birth frame (`detection_backed=True, time_since_update=0`) rather than waiting 2–3 frames in a hidden tentative state that leaves the subject unblurred.
     - **GIoU + Velocity Prediction:** Use constant-velocity Kalman/kinematic state prediction `[xc, yc, w, h, vx, vy, vw, vh]` and support GIoU / center-distance fallback when fast circular motion causes standard IoU to dip below `min_iou`.
     - **Lenient Coasting:** Emit coasted boxes (`detection_backed=False, time_since_update > 0`) during short misses so `post_processor.py` can bridge gaps with GSI or apply accelerated tail decay if unbridged.
   - Add a slider in the **Tracking** panel to adjust `min_tracker_confidence` in the range `0.10..0.50` (default `0.25`) to allow users to tune Stage 1 vs. Stage 2 sensitivity.

---

## 2. Add "Privacy Features" Settings to Domain & ViewModels

### 2.1 `ProcessingSettings` (`src/app/domain/export/processing_settings.py`)
Add the following fields under a new `# --- Privacy Features ---` section in `ProcessingSettings`:
- `privacy_features_enabled: bool = False` — Master toggle for conservative/defensive redaction rules.
- `resist_box_shrinking: bool = True` — Prevents sudden bounding-box contractions (e.g., when a detector switches from full-body to torso-only) while allowing immediate expansion.
- `shrink_resistance: float = 0.85` — Damping factor $\rho \in [0.0, 0.99]$ controlling how strongly sudden width/height shrinkage is resisted (`0.0` = no resistance, `0.85` = allow at most 15% of the shrinkage per frame, `0.95` = near-ratchet lock).
- `pre_detection_padding_sec: float = 0.5` — Time in seconds ($0.0\text{–}5.0\text{ s}$) to display/backfill a track's bounding box *before* its first detection frame $n$ (covering subjects entering from occlusion on frames $n - x \dots n - 1$).
- `post_detection_padding_sec: float = 0.5` — Time in seconds ($0.0\text{–}5.0\text{ s}$) to hold/coast a track's bounding box *after* its last detection frame (covering subjects lingering in partial occlusion).
- `box_safety_padding_pct: float = 0.10` — Outward bounding-box size inflation ratio ($0.0\text{–}0.50$, i.e. $0\%\text{–}50\%$) applied when Privacy Features are active so limbs/heads near box edges remain covered.

In `ProcessingSettings.__post_init__(self)`, validate:
- `0.0 <= self.shrink_resistance <= 0.99`
- `0.0 <= self.pre_detection_padding_sec <= 5.0`
- `0.0 <= self.post_detection_padding_sec <= 5.0`
- `0.0 <= self.box_safety_padding_pct <= 0.50`
Raise `ValueError` with a descriptive message if any value is out of bounds. Map all 6 fields in `ProcessingSettings.as_view_model()`.

### 2.2 `ProcessingSettingsKwargs` (`src/app/domain/base/dtypes.py`) & `SessionSettingsViewModel` (`src/app/domain/views/session_settings_view_model.py`)
- Add all 6 fields with matching types and defaults to `ProcessingSettingsKwargs` and `SessionSettingsViewModel`.
- Document all 6 attributes in the `Attributes:` section of `ProcessingSettings` and `SessionSettingsViewModel`.

---

## 3. Implement Privacy Shield Algorithms in `post_processor.py` (`src/app/infrastructure/tracking/post_processor.py`)

Pass `fps: float = session_state.metadata.fps` (defaulting to `30.0` if `fps <= 0`) and `frame_width`, `frame_height` (from `session_state.metadata` when available) into `post_process_tracked_data(...)` in `src/app/infrastructure/tracking/post_processor.py`.

When `settings.privacy_features_enabled` is `True`, execute the following well-documented stages on each stitched tracklet:

### 3.1 Asymmetric Size Ratchet & Anchor-Preserving Anti-Shrink (`resist_box_shrinking` & `shrink_resistance`)
- **Problem Solved:** In videos where subjects wear props (e.g., kids wearing cardboard cars around their waist) or walk behind furniture, detectors alternate between full-body boxes `(x1, y1, x2, y2)` and torso/head-only boxes `(x1, y1, x2, y_mid)`.
- **Algorithm:**
  1. Walk forward along each track's timeline maintaining running envelope dimensions $(w_{\text{env}}, h_{\text{env}})$ initialized from the first confirmed box.
  2. **Embrace Expansion Immediately:** Whenever the current box width $w_t > w_{\text{env}}$ or height $h_t > h_{\text{env}}$, update $w_{\text{env}} \leftarrow w_t$ and/or $h_{\text{env}} \leftarrow h_t$ immediately.
  3. **Resist Shrinking:** When `resist_box_shrinking=True` and $w_t < w_{\text{env}}$ or $h_t < h_{\text{env}}$:
     - Compute the damped target size using $\rho = \text{shrink\_resistance} \in [0.0, 0.99]$:
       $$w_{\text{env}} \leftarrow \rho \cdot w_{\text{env}} + (1 - \rho) \cdot w_t$$
       $$h_{\text{env}} \leftarrow \rho \cdot h_{\text{env}} + (1 - \rho) \cdot h_t$$
     - **Top-Edge / Head Anchor Preservation:** Compare the top-edge shift $\vert{}\Delta y_1\vert{}$ vs. the bottom-edge shift $\vert{}\Delta y_2\vert{}$ relative to the previous frame:
       - If the bottom edge jumped upward sharply ($\Delta y_2 \ll 0$, e.g. legs disappeared behind a cardboard car while head $y_1$ remained stable), keep $y_1$ anchored at the detected top edge and extend $y_2 \leftarrow y_1 + h_{\text{env}}$ downward!
       - Conversely, if the top edge dropped downward sharply while the bottom edge was stable, keep $y_2$ anchored and extend $y_1 \leftarrow y_2 - h_{\text{env}}$ upward.
       - Otherwise, expand symmetrically around the box center $(x_c, y_c)$.
  4. **Stitching Compatibility:** Also relax the area-ratio gate in `_build_stitch_cost_matrix` when `privacy_features_enabled=True` or `resist_box_shrinking=True` so a full-body tracklet and a torso-only tracklet of the same subject stitch seamlessly.

### 3.2 Pre-Detection Backward Extrapolation (`pre_detection_padding_sec`)
- **Problem Solved:** A subject enters the scene or emerges from partial occlusion at frame $n - k$, but the detector only fires at frame $n$, leaving frames $n - k \dots n - 1$ unblurred.
- **Algorithm:**
  1. Compute $N_{\text{pre}} = \text{ int}(\text{round}(\text{pre\_detection\_padding\_sec} \times \text{fps}))$.
  2. For each stitched track whose first frame is $f_{\text{start}} > 0$ and $N_{\text{pre}} > 0$:
     - Estimate the initial velocity $(\hat{v}_x, \hat{v}_y)$ from the first up to 5 detection-backed boxes of the track, **clamped** to a safe maximum per-frame displacement (e.g., $\le 25\%$ of box width/height per frame, and damped by $0.85^k$ per step $k$) so noisy 2-frame detector jitter never shoots a box across the screen.
     - For each step $k \in \{1 \dots \min(N_{\text{pre}}, f_{\text{start}})\}$ at frame $t = f_{\text{start}} - k$:
       - Project the initial box backward to frame $t$ using the damped reverse velocity and the track's envelope width/height $(w_{\text{env}}, h_{\text{env}})$.
       - Clamp to video frame dimensions `(0, 0, frame_width, frame_height)` when dimensions are known; if the projected box center moves completely outside the frame boundaries, stop backfilling earlier.
       - Mark the backfilled box with `detection_backed=False`, `time_since_update=k`, and confidence above `min_tracker_confidence` so it passes Layer D filtering.

### 3.3 Post-Detection Forward Hold (`post_detection_padding_sec`)
- **Problem Solved:** A subject is still partially visible for $y$ seconds after the last detector hit.
- **Algorithm:**
  1. Compute $N_{\text{post}} = \text{int}(\text{round}(\text{post\_detection\_padding\_sec} \times \text{fps}))$.
  2. When `privacy_features_enabled=True` and $N_{\text{post}} > 0$, extend the unbridged tail coasting window for each track after its final detection frame $f_{\text{end}}$ up to $\min(\text{total\_frames} - 1, f_{\text{end}} + N_{\text{post}})$:
     - Project position forward using damped terminal velocity ($0.85^k$ per frame $k$ so a stopping subject doesn't drift infinitely) and maintain the envelope size $(w_{\text{env}}, h_{\text{env}})$.
     - Decay confidence gradually across the $N_{\text{post}}$ window so boxes remain above `min_tracker_confidence` for the full $T_{\text{post}}$ duration unless the box exits the frame bounds.

### 3.4 Safety Margin Box Inflation (`box_safety_padding_pct`)
- When `privacy_features_enabled=True` and `box_safety_padding_pct > 0.0`, expand each output box's width and height outward around its center by `box_safety_padding_pct` (e.g., $+10\%$), clamped to valid non-negative pixel coordinates (and `(frame_width, frame_height)` when $> 0$).

---

## 4. Add the "Privacy Features" `CollapsiblePanel` to the Right Panel UI

In `src/app/ui/qt/sections/right_panel.py` and `src/app/ui/handlers/tracking_handler.py`:

### UI Layout & Placement
Create a new `CollapsiblePanel` titled **`"Privacy Features"`** placed directly under the **Tracking** panel in `RightPanel`:

1. **Checkbox: `"Enable Privacy Shield"`** (`privacy_features_enabled: bool = False`)
   - **Tooltip:** `"Activates conservative, privacy-first tracking rules designed to eliminate missed redactions. Prevents sudden bounding-box shrinkage (e.g., when only a torso is detected instead of a full body), backfills boxes before a subject is first detected, holds boxes after the last detection, and adds a safety border."`
2. **Checkbox: `"Resist Box Shrinking"`** (`resist_box_shrinking: bool = True`, enabled when `privacy_features_enabled` is checked)
   - **Tooltip:** `"Prevents tracked bounding boxes from shrinking abruptly when a detector temporarily sees only part of a subject (such as a torso or head instead of the full body). Boxes still expand immediately when the subject grows larger."`
3. **Slider / DoubleSpinBox: `"Shrink Resistance"`** (`shrink_resistance: float = 0.85`, range `0.00..0.99`, step `0.05`, enabled when `privacy_features_enabled` and `resist_box_shrinking` are checked)
   - **Tooltip:** `"Controls how strongly bounding boxes resist contracting over short intervals (0.00 = allow normal shrinking, 0.85 = strong damping, 0.99 = lock to maximum observed size). Top/head anchors are preserved when lower-body detections drop out."`
4. **Slider / DoubleSpinBox: `"Pre-Detection Buffer (s)"`** (`pre_detection_padding_sec: float = 0.5`, range `0.0..5.0` seconds, step `0.1`, enabled when `privacy_features_enabled` is checked)
   - **Tooltip:** `"Time in seconds (0.0–5.0 s) to display and backfill a tracked bounding box BEFORE the subject's first confirmed detection. Protects subjects who were partially visible or occluded for a few frames before the detector first recognized them."`
5. **Slider / DoubleSpinBox: `"Post-Detection Hold (s)"`** (`post_detection_padding_sec: float = 0.5`, range `0.0..5.0` seconds, step `0.1`, enabled when `privacy_features_enabled` is checked)
   - **Tooltip:** `"Time in seconds (0.0–5.0 s) to keep displaying a tracked bounding box AFTER the subject's last confirmed detection. Ensures subjects remain blurred while lingering in partial occlusion or exiting the scene."`
6. **Slider / DoubleSpinBox: `"Safety Margin (%)"`** (`box_safety_padding_pct: float = 0.10`, displayed as `0%..50%` or `0.00..0.50`, enabled when `privacy_features_enabled` is checked)
   - **Tooltip:** `"Expands tracked bounding boxes outward by a safety percentage (0–50%) so fast-moving faces, hair, or limbs near the edge of a detector box never poke outside the blur mask."`

### Signal & Handler Wiring
- Emit signals from `RightPanel` for each of the 6 controls and wire them in `TrackingHandler` to `self._app.update_session_settings(s_id, ...)`.
- Dynamically enable/disable child controls in the `"Privacy Features"` panel when `"Enable Privacy Shield"` or `"Resist Box Shrinking"` is toggled.
- Ensure `RightPanel` restores all 6 controls accurately when applying a `SessionSettingsViewModel`.

---

## 5. Audit and Update `README.md` Tables (Planned Features & Known Bugs)

Inspect `README.md` (and any linked status tables in `docs/`) and update outdated tables so they accurately reflect the current state of the application:
1. **Implemented Features:**
   - Move completed capabilities out of "Planned / Todo" into implemented status:
     - Multi-Object Tracking strategies: **Hungarian**, **ByteTrack**, **DeepSORT (with Re-ID)**, and **BoT-SORT (with Re-ID)**.
     - Frame-aware `TrackingWorker` with configurable **Re-ID Appearance Embeddings (128 / 256 / 512-D)**.
     - **Offline Bidirectional Tracklet Stitching & Gaussian Smoothed Interpolation (GSI)**.
     - **Privacy Features**: anti-shrink size ratchet, pre-detection backfill, post-detection hold, and safety margin padding.
     - Split **Preview** and **Render** panels with live **Show Mask**, **Blur Preview**, and configurable **Box Border Width**.
     - Project Save / Load (`.blurzy` / JSON project persistence) and Layer Import / Export (JSON & CSV).
2. **Resolved Bugs:**
   - Mark fixed bugs as resolved (or remove them from active bug tables): Frame 0 unblurred/stale layer seeding bug, Faster R-CNN nested same-class box fragmentation ($\text{IoMin}$ containment suppression), zero-coasting unblurred flashes during short occlusions, and ByteTrack confidence threshold starvation.

---

## 6. Verification & Test Suite Requirements
1. **ByteTrack Tests (`tests/infrastructure/tracking/`):**
   - Test `ByteTrackStrategy` with detections in the `0.25–0.45` confidence range (simulating pre-filtered YOLO/Torch detections), verifying that Stage 1 initializes tracks on frame 0 without starvation and Stage 2 recovers low-confidence (`0.15`) occluded boxes.
2. **Privacy Features Scenario Tests (`tests/infrastructure/tracking/`):**
   - **Cardboard-Car Torso/Full-Body Alternation Test:** Simulate a track where frames 0–5 have a full-body box `(100, 100, 220, 400)` (`h=300`), frames 6–10 drop to a torso-only box `(105, 102, 215, 230)` (`h=128`, same top head anchor `y1≈102`), and frame 11 returns to full-body. Verify that with `privacy_features_enabled=True, resist_box_shrinking=True, shrink_resistance=0.85`, the boxes on frames 6–10 resist shrinking, preserve the head top anchor `y1`, and keep covering the lower body.
   - **Pre-Detection Backfill Test:** Simulate a subject first detected at frame 15 at `25 FPS` with `pre_detection_padding_sec=0.4` (`10` frames). Verify that frames `5..14` are backfilled with extrapolated boxes of the same track ID.
   - **Post-Detection Hold Test:** Simulate a subject last detected at frame 20 at `25 FPS` with `post_detection_padding_sec=0.4` (`10` frames) in a 40-frame video. Verify that frames `21..30` retain held boxes above `min_tracker_confidence`.
3. **UI & Documentation Tests:**
   - Verify `RightPanel` contains the `"Privacy Features"` panel, all 6 controls have non-empty tooltips, and toggling `"Enable Privacy Shield"` enables/disables child controls.
   - Run `ruff check`, `python scripts/docs_reference.py`, and `pytest` (including `tests/test_docs_reference.py`).