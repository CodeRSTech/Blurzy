# Changelog

Notable project changes are recorded here. This changelog may not include every change.

## Unreleased

No unreleased changes.

## 1.1.0

Blurzy's early history was iterated on directly without a changelog, so this
entry summarizes the feature set as it stands rather than every individual
commit. See `git log` for the complete commit history.

### Detection, tracking, and annotations

- Added detection support across multiple model providers and introduced the
  four-layer annotation model: raw detections (Layer A), reviewed/editable
  detections (Layer B), raw tracking output (Layer C), and reviewed/editable
  tracks (Layer D).
- Added multi-object tracking with Hungarian, ByteTrack, DeepSORT, and
  BoT-SORT, including appearance-aware tracking with configurable 128-, 256-,
  and 512-dimensional Re-ID embeddings.
- Added bidirectional tracklet stitching and Gaussian Smoothed Interpolation
  (GSI) to fill accepted tracking gaps.
- Added the optional Privacy Shield, with anti-shrink boxes, pre-detection
  backfill, post-detection holds, and safety-margin padding.
- Added undo/redo, copy/paste, and multi-item selection for annotation editing.

### Project and session workflow

- Added `SessionManager` and `SessionFrameAccessor` for video session and
  frame access, including a fix for videos with zero streams.
- Added `.blurzy`/JSON project save and load, and JSON/CSV import/export for
  annotation and tracking layers.
- Added persistent app preferences and session defaults, including a
  scrollable Settings dialog.

### UI and export

- Added separate Preview and Render panels for box outlines, border width,
  mask preview, live blur, and export blur.
- Added a detection progress label showing percentage and ETA in `hh:mm:ss`
  format.
- Added blurred-video export, preferring reviewed tracks (Layer D) and falling
  back to raw tracking output (Layer C).
- Kept long-running detection, tracking, and export work off the UI thread
  using background workers that report progress through Qt signals.

### Packaging, documentation, and tooling

- Added `pyproject.toml` packaging metadata, the `dev` and `dist` optional
  dependency groups, and a PyInstaller-based distribution build.
- Added the MkDocs Material documentation site, generated API reference pages,
  and the GitHub Pages deployment workflow for the homepage and documentation.
- Added the automated test suite, organized to mirror the `src` layer
  structure, with CI running it on each pull request.
