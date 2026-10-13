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

Documentation uses MkDocs with **Material**, including dark and light modes. Install the
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
cp docs/assets/icon.ico site/favicon.ico
python -m http.server --directory site 8000
```

Visit `http://localhost:8000/` for the homepage and
`http://localhost:8000/docs/` for the documentation.

Architecture diagrams use fenced Mermaid blocks. Material renders them through
its supported SuperFences integration; the diagram source remains in Markdown.
The Material release controls the bundled Mermaid integration.

The published layout is:

- `https://CodeRSTech.github.io/Blurzy/`: project homepage,
  maintained in `website/index.html`.
- `https://CodeRSTech.github.io/Blurzy/docs/`: generated
  documentation from `docs/`, configured by `mkdocs.yml`.

The Pages workflow builds the site on pushes and pull requests, but only
deploys pushes to `master` or manual runs on `master`. In the repository's
**Settings → Pages → Build and deployment**, select **GitHub Actions** as
the source before the first deployment. Generated files in `site/` are build
artifacts and are not committed.

### Reference authoring

Reference documentation has two complementary parts:

- **Package notes** in `docs/reference/` contain architecture explanations,
  ownership rules, lifecycle notes, and diagrams. Keep the `Source:` line
  pointing to the corresponding `src/app/` package; the build adds its API link.
- **API pages** under `reference/api/` are generated in memory from every Python
  module and package in `src/app/`. Edit signatures, annotations, and docstrings
  in source, not generated Markdown. New, renamed, and removed modules update
  the inventory and navigation automatically.

The hook in `scripts/docs_reference.py` uses MkDocs' virtual file API and
mkdocstrings' static Python handler. Builds do not import the application or
install Qt/ML dependencies. `python -m mkdocs serve` watches `src/app` as well
as the documentation. Before submitting documentation-tooling changes, run:

```bash
python -m unittest discover -s tests -p "test_docs_reference.py"
python -m mkdocs build --strict
```

The Pages workflow runs both.

The **Reference** menu contains package notes; **API reference** starts directly
at application, domain, infrastructure, shared, and UI packages. Package titles
open their index pages without extra Overview links.

Public defining-module members appear even without docstrings. Module-level
runtime wiring (including loggers), private names, imported members, and
inherited Qt APIs are omitted; public constants and type aliases remain.
Package re-exports link to their defining modules. Constructors remain visible.
Explicit member inclusions/exclusions belong in `MEMBER_EXCEPTIONS` and
`MEMBER_EXCLUSIONS` in the hook; an explicit
`::: app.module.Class` directive in a handwritten page can document a selected
private method when needed.

Write Google-style `Args:`, `Returns:`, `Raises:`, and `Attributes:` sections
where useful. Use Markdown backticks for inline code and fenced blocks for
examples. Generation does not check prose against behavior: lifecycle
guarantees, signal flows, and design decisions still need human maintenance.
Missing docstrings do not fail the build, and existing docstrings can be
improved incrementally.

See [Reference documentation](engineering/reference-documentation.md) for the
source-to-page pipeline, complete examples, selection rules, and troubleshooting.
