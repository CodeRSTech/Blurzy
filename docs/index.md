# Blurzy documentation

Blurzy is an early-stage PySide6 desktop application for detecting and tracking
subjects in video, reviewing annotations, and exporting video with selected
subjects blurred.

## What you can do

- Open video and review it with playback and frame-level controls.
- Run detection with supported model providers and track subjects.
- Review and edit bounding-box annotations.
- Import and export annotation data and export blurred video.
- Monitor long-running detection, tracking, and export tasks without blocking
  the desktop interface.

Model availability depends on the installed providers, model weights, and
hardware/runtime support. Blurzy does not yet claim a stable release or a
model-independent detection experience. Review annotations and exported video
before relying on the result; automated detection can miss subjects.

## Explore the project

- [Getting started](getting-started.md): install and launch the desktop app.
- [Development](development.md): run tests, build packages, and preview this site.
- [Architecture](architecture.md): understand the layers and detection flow.
- [Engineering conventions](engineering/documentation-style.md): follow the
  project's documentation style.
- [Planning notes](planning/README.md): read proposals, not implemented features
  or a committed roadmap.

[Project homepage](https://CodeRSTech.github.io/Blurzy/) ·
[Source repository](https://github.com/CodeRSTech/Blurzy)
