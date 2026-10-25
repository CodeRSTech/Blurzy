# Blurzy

Blurzy is an early-stage desktop video application for detecting and tracking
subjects, reviewing and editing annotations, and exporting video with selected
subjects blurred. It brings those steps into one PySide6 workflow, with
background workers for long-running detection, tracking, and export tasks.

The project grew through hands-on prototyping: its layered design separates
video/ML integrations from application workflows and the desktop interface, so
experiments can be refined without putting all of that complexity in the UI.

## What it can do

- Open and review video, with playback and frame-level controls.
- Run detection with supported model providers, then review and edit bounding-box annotations.
- Track subjects with Hungarian, ByteTrack, DeepSORT, or BoT-SORT; appearance-aware tracking uses
  configurable 128-, 256-, or 512-dimensional Re-ID embeddings.
- Stitch compatible tracklets bidirectionally and use Gaussian Smoothed Interpolation (GSI) to fill
  accepted gaps.
- Enable the optional Privacy Shield for anti-shrink boxes, pre-detection backfill, post-detection
  holds, and safety-margin padding.
- Use separate Preview and Render panels for box outlines, border width, mask preview, live blur,
  and export blur.
- Configure persistent app preferences and session defaults in a screen-bounded Settings dialog with
  a scrollable form.
- Save and load `.blurzy` or JSON projects; import and export annotation and tracking layers as JSON
  or CSV.
- Keep long-running work off the UI thread and surface progress in the app.

Blurzy is actively evolving. Model availability depends on the installed
providers and their hardware/runtime support; the project does not currently
claim a stable release or a model-independent detection experience.

## Website and documentation

- [Project homepage](https://CodeRSTech.github.io/Blurzy/)
- [Documentation](https://CodeRSTech.github.io/Blurzy/docs/)

The documentation is generated with MkDocs Material, with dark and light modes.
API reference pages are generated from Python source; see the
[reference documentation guide](docs/development/reference-documentation.md).
To preview it:

```bash
python -m pip install -r requirements-docs.txt
python -m mkdocs serve
```

The Pages workflow checks documentation builds on pull requests and deploys
the homepage and documentation on `master`. Select **GitHub Actions** under
**Settings → Pages → Build and deployment** to enable publication. See the
[documentation development guide](docs/development/development.md) for the complete site
build and preview commands.

## Get started

Blurzy requires Python 3.12 or newer. Create a virtual environment, then
install the package and development tools:

```bash
python -m venv .venv
```

Activate the environment, then run:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
blurzy
```

The editable install provides the `blurzy` GUI command as well. On Linux, run
the app from a graphical desktop session. PyTorch and model-provider support
can have platform-specific requirements; consult the relevant provider's
installation guidance if its models are unavailable.

## Development

Run the automated test suite from the repository root:

```bash
python -m pytest -q
```

The default suite is intended for local development and CI; it does not require
downloading model weights. Some video/GUI integration tests require Qt and
appropriate test media. Run a focused subset while iterating, for example:

```bash
python -m pytest tests/domain tests/shared -q
```

`pyproject.toml` is the canonical source for package dependencies and the
`dev` extra. `requirements.txt` remains available for existing workflows and
installs the project from that metadata.

For a distributable build:

```bash
python -m pip install -e ".[dist]"
python -m build
```

## Architecture

The source is organized into four Clean Architecture layers, supported by a
cross-cutting `shared` package:

| Layer                    | Responsibility                                             |
|--------------------------|------------------------------------------------------------|
| `src/app/domain`         | Core video, session, detection, tracking, and export types |
| `src/app/application`    | Workflows and services coordinating domain operations      |
| `src/app/infrastructure` | Video, model, tracking, and export integrations/workers    |
| `src/app/ui`             | PySide6 window, widgets, handlers, and UI controller       |

A typical detection flow starts in a UI handler, delegates through the
application facade and detection service, then runs in an infrastructure
worker. Worker signals carry progress and results back to the UI. See
[`docs/architecture/overview.md`](docs/architecture/overview.md) for a guided code map and
[`tests/README.md`](tests/README.md) for the test layout.

The annotation pipeline keeps raw detections in Layer A, editable detections
in B, raw tracked output in C, and editable tracks in D. Tracking normally uses
reviewed detections from B; users can inspect and edit the final output in D.
Project Save/Load preserves session state, while JSON/CSV import/export
exchanges detection and tracking layers. Preview controls affect the editor;
Render controls affect exported video.

## Planning

Product proposals and follow-up work are collected in the
[planning notes](docs/planning/README.md), including ideas previously listed
here and areas where planned capabilities are already implemented.

## Implemented tracking and privacy features

| Capability              | Current implementation                                                               |
|-------------------------|--------------------------------------------------------------------------------------|
| Multi-object tracking   | Hungarian, ByteTrack, DeepSORT with Re-ID, and BoT-SORT with Re-ID                   |
| Frame-aware tracking    | `TrackingWorker` decodes frames for configurable 128/256/512-D appearance embeddings |
| Offline gap recovery    | Bidirectional tracklet stitching and Gaussian Smoothed Interpolation (GSI)           |
| Privacy Shield          | Anti-shrink sizing, pre-detection backfill, post-detection hold, and safety padding  |
| Preview and render      | Separate panels for Show Mask, Blur Preview, Box Border Width, and export blur       |
| Project and layer files | `.blurzy`/JSON project persistence and JSON/CSV layer import/export                  |
## Bugs

| Bug                                                                                                                                     | Priority | Status                                   |
|-----------------------------------------------------------------------------------------------------------------------------------------|----------|------------------------------------------|
| Settings window is not scrollable and goes out of bounds vertically on FHD display                                                      | High     | Resolved                                 | 
| "Start Tracking" does not prompt the user to run detections first                                                                       | Medium   | Open                                     |
| Video export closes the app upon completion                                                                                             | Medium   | Open                                     |
| Backward seek times out waiting for frame `n-1` in `get_frame_by_index`                                                                 | Low      | Open                                     |
| `app.ui.handlers.annotation_handler.AnnotationHandler._delete_occurrences` does not remove all occurrences of a track from the timeline | Low      | Open                                     |
| Frame 0 unblurred or stale layer seeding during tracking                                                                                | Medium   | Resolved                                 |
| Nested same-class detections fragment tracks instead of being containment-suppressed                                                    | Medium   | Resolved                                 |
| Short occlusions cause unblurred flashes when no coast is emitted                                                                       | Medium   | Resolved                                 |
| ByteTrack's fixed confidence thresholds starve track initialization                                                                     | Medium   | Resolved                                 |
| Late first detection leaves earlier subject frames unredacted                                                                           | Medium   | Mitigated when Privacy Shield is enabled |
