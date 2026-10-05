# Getting started

## Requirements

- Python 3.12 or newer.
- A graphical desktop session for the PySide6 interface.
- Compatible model providers and model weights for the detection features you
  intend to use. Hardware support varies by provider.

On Ubuntu, Qt also needs native libraries that are not bundled in its Python
wheel. For headless tests, install:

```bash
sudo apt-get update
sudo apt-get install --no-install-recommends -y libegl1 libopengl0 libpulse0
```

A desktop session may need additional platform-plugin libraries provided by
your distribution. The offscreen setting used in CI is for tests, not normal
interactive use.

## Install and launch

From a checkout of the repository, create a virtual environment:

```bash
python -m venv .venv
```

Activate it with `source .venv/bin/activate` on Linux/macOS, or
`.venv\Scripts\Activate.ps1` in Windows PowerShell. Then install and launch:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
blurzy
```

The editable installation provides the `blurzy` GUI command. Runtime
dependencies are maintained in `pyproject.toml`; `requirements.txt` delegates
to that metadata.

## Typical workflow

1. Open a video and inspect its frames using the playback controls.
2. Select an available detection provider and run detection.
3. Run tracking and review the resulting bounding-box annotations.
4. Edit annotations as needed and select subjects to blur.
5. Export annotation data or blurred video, then review the output.

Long-running operations use background workers and report progress in the UI.
If a provider is unavailable, consult its installation guidance and verify its
model weights and hardware requirements.
