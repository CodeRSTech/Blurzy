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

```console
git clone https://github.com/CodeRSTech/Blurzy.git
cd Blurzy
```

### Create virtual environment

```console
python -m venv .venv
```

#### Activate the virtual env

`source .venv/bin/activate` *(Linux/macOS)* 

`.venv\Scripts\Activate.ps1` *(Windows)*.

### Install dependencies

```console
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### Run

```console
blurzy
```

The editable installation provides the `blurzy` GUI command. Runtime
dependencies are maintained in `pyproject.toml`; `requirements.txt` delegates
to that metadata.

???+ example "Typical workflow"

    1. Open a video.
    2. Select an available YOLO, TorchVision, or MTCNN model and run detection.
    3. Review detections in the editable detection layer, then choose Hungarian,
       ByteTrack, DeepSORT, or BoT-SORT and run tracking.
    4. Review and edit the resulting tracks in the editable tracking layer.
    5. Adjust Preview controls for editor overlays and Render controls for
       exported-video blur.
    6. Save the project when you want to preserve session state. Import or export
       detection/tracking layers as JSON or CSV when exchanging annotations.
    7. Export the processed video and review the result.

???+ info

    Long-running operations use background workers and report progress in the UI.
    If a provider is unavailable, consult its installation guidance and verify its
    model weights and hardware requirements.

Appearance-aware tracking uses frame-derived 128-, 256-, or 512-dimensional
embeddings when a readable video path is available. Offline post-processing can
stitch compatible tracklets in both temporal directions and apply Gaussian
Smoothed Interpolation (GSI) across accepted gaps. Privacy Shield (Paranoid Mode)
adds conservative track-box sizing and temporal padding; it supplements, but
does not replace, review of the final result.