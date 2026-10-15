# Getting started

## Requirements

- Python 3.12+.
- A compatible monitor.
- Compatible model providers and weights for the intended detection features. *Hardware support varies by provider.*

??? info "Running on Ubuntu"

    On Ubuntu, Qt also needs native libraries that are not bundled in its Python
    wheel. For headless tests, install:
    ```bash
    sudo apt-get update
    sudo apt-get install --no-install-recommends -y libegl1 libopengl0 libpulse0
    ```
    A desktop session may need additional platform-plugin libraries provided by
    your distribution. The offscreen setting used in CI is for tests, not normal
    interactive use.

## Running the app

### Clone the repository

```bash
git clone https://github.com/CodeRSTech/Blurzy.git
cd Blurzy
```

### Create virtual environment

```bash
python -m venv .venv
```

#### Activate the virtual env

`source .venv/bin/activate` *(Linux/macOS)* 

`.venv\Scripts\Activate.ps1` *(Windows)*.

### Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### Run

```bash
blurzy
```

The editable installation provides the `blurzy` GUI command. Runtime
dependencies are maintained in `pyproject.toml`; `requirements.txt` delegates
to that metadata.

???+ example "Typical workflow"

    1. Open a video.
    2. Select a model and start background detection.
    3. Select a tracking strategy and run tracking.
    4. Review the resulting bounding-box annotations.
    5. Edit annotations as needed and select subjects to blur.
    6. Export output file.

???+ info

    Long-running operations use background workers and report progress in the UI.
    If a provider is unavailable, consult its installation guidance and verify its
    model weights and hardware requirements.