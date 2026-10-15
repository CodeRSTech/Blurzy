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
- Run detection with supported model providers and track detections.
- Review and edit bounding-box annotations.
- Import and export annotation data, and export blurred video.
- Keep long-running work off the UI thread and surface progress in the app.

Blurzy is actively evolving. Model availability depends on the installed
providers and their hardware/runtime support; the project does not currently
claim a stable release or a model-independent detection experience.

## Website and documentation

- [Project homepage](https://CodeRSTech.github.io/Blurzy/)
- [Documentation](https://CodeRSTech.github.io/Blurzy/docs/)

The documentation is generated with MkDocs Material, with dark and light modes.
API reference pages are generated from Python source; see the
[reference documentation guide](docs/engineering/reference-documentation.md).
To preview it:

```bash
python -m pip install -r requirements-docs.txt
python -m mkdocs serve
```

The Pages workflow checks documentation builds on pull requests and deploys
the homepage and documentation on `master`. Select **GitHub Actions** under
**Settings → Pages → Build and deployment** to enable publication. See the
[documentation development guide](docs/development.md) for the complete site
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

The source follows four broad layers:

| Layer                    | Responsibility                                             |
|--------------------------|------------------------------------------------------------|
| `src/app/domain`         | Core video, session, detection, tracking, and export types |
| `src/app/application`    | Workflows and services coordinating domain operations      |
| `src/app/infrastructure` | Video, model, tracking, and export integrations/workers    |
| `src/app/ui`             | PySide6 window, widgets, handlers, and UI controller       |

A typical detection flow starts in a UI handler, delegates through the
application facade and detection service, then runs in an infrastructure
worker. Worker signals carry progress and results back to the UI. See
[`docs/architecture.md`](docs/architecture.md) for a guided code map and
[`tests/README.md`](tests/README.md) for the test layout.

## Planned features

| Feature                                                                       | Priority | Status     |
|-------------------------------------------------------------------------------|----------|------------|
| Preserve source audio in exported videos (audio is currently stripped)        | High     | 🟡 Planned |
| Resume background detection for heavy models without rerunning completed work | High     | 🟡 Planned |
| Identify detections using appearance features (Re-ID)                         | Medium   | 🟡 Planned |
| Implement offline StrongSORT + GSI                                            | High     | 🟡 Planned |

## Bugs

| Bug                                                                                                                                                     | Priority | Status |
|---------------------------------------------------------------------------------------------------------------------------------------------------------|----------|--------|
| "Start Tracking" button does NOT ask user to run detections first                                                                                       | Medium   | �      |
| Timeout waiting for worker to supply frame n-1 when at frame n (backward seek problem) in app.infrastructure.session.frame_access:get_frame_by_index:83 | High     | �      |

## Future additions: beyond detection and tracking

> This section is not a list of implemented features or promised
releases. 

- **Improve coverage:** Re-detect when tracks become uncertain or scenes change;
  smooth boxes, add margins, and fill only short gaps. Mark predictions clearly
  and flag uncertain intervals for review.
- **Make corrections easier:** Add a review timeline, keyframe and range-based
  editing, and track split/merge tools. Appearance-aware tracking could help
  with identity switches, but a track ID is not a verified identity.
- **Expand redaction options:** Explore shapes, pixelation, solid fill,
  segmentation, and specialized face, plate, or text detection. Incomplete
  masks and model errors can still expose sensitive content.
- **Consider audio separately:** Manual muting or tones could be followed by
  optional transcription, with explicit privacy choices and synchronization
  checks.
- **Support longer workflows:** Presets, resumable jobs, checkpoints, and
  hardware-aware processing could save time, but require care with sensitive
  data and reduced-resolution results.
- **Improve export controls:** Offer quality and audio options, metadata
  handling, and a pre-export review. Keep outputs separate from originals and
  explain unresolved issues.

Start with coverage, review, and correction; evaluate larger model and audio
features before investing in them. Test against manually reviewed footage with
small subjects, motion, occlusion, low light, scene cuts, and varied frame
rates. Measure missed-redaction intervals, coverage, excess masking, track
errors, review effort, and processing cost. No detector, tracker, or setting
guarantees anonymization.

### Suggested priorities and evaluation

The most useful first investment is likely **coverage and correction**:
padding, bounded gap handling, uncertainty navigation, and range-based edits.
These improve the existing workflow before introducing expensive new models.
Next, explore masking choices, presets, and export controls. Appearance-aware
tracking, segmentation, OCR, and audio processing are larger experiments whose
value should be demonstrated on representative footage.

Evaluate proposed changes against a manually reviewed reference set containing
small subjects, fast motion, crossings, occlusions, low light, camera cuts, and
different frame rates. Compare against the existing pipeline, not just a
successful demonstration clip.

| Measure                                                   | What it tells us                                                       |
|-----------------------------------------------------------|------------------------------------------------------------------------|
| Missed-redaction frames and longest uncovered interval    | How often, and for how long, a sensitive region is exposed             |
| Sensitive-region coverage and excess masked area          | Whether masks cover the target without unnecessarily hiding the scene  |
| Identity switches and fragmented tracks                   | Whether track-based redaction remains attached to the intended subject |
| Mask jitter and drift                                     | Whether masks stay stable and aligned during movement                  |
| Review time, correction count, and warning usefulness     | Whether automation actually reduces the user's workload                |
| Processing speed, peak memory, and output synchronization | Whether the workflow is practical on supported hardware                |

Keep observed detections, automated predictions, manual corrections, and
review status distinguishable. No detector, tracker, or redaction setting
should be presented as a guarantee of anonymization.

## Contributing

Start with the development setup above, run the tests relevant to your change,
and include a concise description of user-visible behavior in your pull
request. The focused notes in [`docs/engineering`](docs/engineering/) describe
the existing documentation and exception-handling conventions.
