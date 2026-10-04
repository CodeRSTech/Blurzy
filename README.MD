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

| Layer | Responsibility |
| --- | --- |
| `src/app/domain` | Core video, session, detection, tracking, and export types |
| `src/app/application` | Workflows and services coordinating domain operations |
| `src/app/infrastructure` | Video, model, tracking, and export integrations/workers |
| `src/app/ui` | PySide6 window, widgets, handlers, and UI controller |

A typical detection flow starts in a UI handler, delegates through the
application facade and detection service, then runs in an infrastructure
worker. Worker signals carry progress and results back to the UI. See
[`docs/architecture.md`](docs/architecture.md) for a guided code map and
[`tests/README.md`](tests/README.md) for the test layout.

## Contributing

Start with the development setup above, run the tests relevant to your change,
and include a concise description of user-visible behavior in your pull
request. The focused notes in [`docs/engineering`](docs/engineering/) describe
the existing documentation and exception-handling conventions.
