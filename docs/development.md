# Development

## Tests

Install the development extra as described in [Getting started](getting-started.md).
From the repository root, run:

```bash
python -m pytest -q
```

On headless Linux, use:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

The CI workflow installs Qt's native EGL, OpenGL, and PulseAudio libraries and
checks real Qt imports before running pytest. Without those libraries, the
optional-dependency stubs can hide an import failure and pytest-qt can report
that PySide6 has no `QtGui` attribute.

For focused iteration:

```bash
python -m pytest tests/domain tests/shared -q
```

Tests mirror the source layers. Some optional dependencies use lightweight
stubs; video worker integration tests are skipped unless
`BLURZY_TEST_VIDEO_PATH` points to suitable local media. Model-inference tests
may require model weights and compatible hardware. The default suite does not
require downloading model weights.

## Package builds

```bash
python -m pip install -e ".[dist]"
python -m build
```

## Documentation and homepage

Documentation uses MkDocs with the Bootswatch **Darkly** theme. Install the
documentation tools separately; this does not install the desktop/ML stack:

```bash
python -m pip install -r requirements-docs.txt
python -m mkdocs serve
```

Open the URL printed by MkDocs for the documentation preview. To build and
preview the complete Pages artifact, including the project homepage:

```bash
python -m mkdocs build --strict
cp website/index.html site/index.html
python -m http.server --directory site 8000
```

Visit `http://localhost:8000/` for the homepage and
`http://localhost:8000/docs/` for the documentation.

Architecture diagrams use fenced Mermaid blocks. MkDocs renders them with the
Mermaid2 plugin and loads the pinned Mermaid JavaScript module from unpkg in
the browser; the diagram source remains in the Markdown files.

The published layout is:

- `https://CodeRSTech.github.io/Blurzy-development/`: project homepage,
  maintained in `website/index.html`.
- `https://CodeRSTech.github.io/Blurzy-development/docs/`: generated
  documentation from `docs/`, configured by `mkdocs.yml`.

The Pages workflow builds the site on pushes and pull requests, but only
deploys pushes to `master` or manual runs on `master`. In the repository's
**Settings → Pages → Build and deployment**, select **GitHub Actions** as
the source before the first deployment. Generated files in `site/` are build
artifacts and are not committed.
