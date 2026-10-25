# Working on Blurzy

## Project and workflow

Blurzy is an evolving PySide6 desktop application for video detection, tracking,
annotation review/editing, and exporting video with selected subjects blurred.
Read the [README](../README.MD) for setup and the
[architecture overview](../docs/architecture/overview.md) for runtime workflows.
Check implementation and executable configuration when prose disagrees; planning
notes describe proposals, not necessarily implemented capabilities.

Preserve the four annotation layers:

| Layer | Role |
| --- | --- |
| A | Original detector output |
| B | Reviewed/editable detections seeded from A |
| C | Original tracking output, including configured post-processing |
| D | Reviewed/editable tracks seeded from C |

Tracking accepts A or B, normally reviewed B. Keep machine output separate from
user edits; inspect existing seeding/filtering rules before changing layer writes.
Blurred-video export prefers populated D and otherwise falls back to C.
Preview controls affect the editor; Render controls affect exported video.
Project Save/Load (`.blurzy` or JSON) preserves session state and references;
JSON/CSV layer interchange is a separate workflow.

## Where code belongs

| Location | Responsibility |
| --- | --- |
| `src/main.py` | Runtime configuration, logging, Qt startup, and composition |
| `src/app/ui` | Controller, adapters, handlers, Qt windows/widgets/dialogs |
| `src/app/application/application.py` | Thin facade delegating UI requests to services |
| `src/app/application/services` | Use-case decisions, validation, and coordination |
| `src/app/application/managers` | Session and selected worker lifecycles |
| `src/app/application/interfaces` | Application-owned worker/factory contracts |
| `src/app/domain` | Core data types, settings, state, and rules |
| `src/app/infrastructure` | Video I/O, model integrations, trackers, workers, storage |
| `src/app/shared` | Logging, exceptions, configuration, and shared utilities |
| `tests` | Tests organized by source layer, plus integration and docs tests |
| `docs`, `scripts/docs_reference.py`, `mkdocs.yml` | Authored guides and static API generation |
| `website/index.html` | Project homepage |

These are principal boundaries, not strictly enforced Clean Architecture.
Application currently uses concrete infrastructure implementations, and video
rendering lives in the Application export service. Follow the actual workflow;
do not introduce unrelated architectural migrations.

## Change guardrails

- Keep the Application facade thin, business decisions in services/domain, and
  UI orchestration in handlers. Reuse existing adapters, contracts, and helpers.
- Keep detection, tracking, decoding, and export work off the GUI thread.
  Workers emit signals; they must not directly access Qt widgets.
- Preserve progress reporting, cancellation, and success/error cleanup. Inspect
  the existing worker's signal contract and lifecycle before changing connections.
- Use `get_logger(area)` from `app.shared.logging_cfg`. Log failures at the
  service/worker boundary with session/operation context and exception details;
  handlers own user-facing error dialogs. Do not silently swallow failures.
- Follow nearby typing and naming conventions and `pyproject.toml` Ruff settings:
  Python 3.12 target, 120-character lines, double quotes, four-space indentation.
- Add focused regression coverage for behavior changes and update related guides
  and docstrings. Keep edits scoped; preserve unrelated work.
- For Qt overlays and stacked widgets, verify both sides of every state
  transition. `QStackedLayout.StackAll` keeps siblings visible, so selecting a
  current widget alone does not hide an overlay; explicitly manage visibility
  and test that a loaded frame removes the empty state.
- For visible UI changes, inspect the rendered states that changed (including
  empty and populated views) at the target window size. A test of initial
  construction or button signals alone does not prove that the UI updates.
  Preview annotation checks must include ordinary and selected boxes on
  low-resolution and 4K frames; test rendered pixels, not just a width helper.

See the [engineering and docstring conventions](../docs/development/documentation-style.md).

## Setup and validation

Use Python 3.12+ and a virtual environment. Run commands from the repository root:

```console
python -m venv .venv
```

Activate the environment using the current shell's syntax, then:

```console
python -m pip install -e ".[dev]"
blurzy
python -m pytest tests/domain tests/shared -q
python -m pytest -q
```

Choose the smallest relevant test subset first; the last command is the full
suite. Tests add `src` to the import path via pytest configuration.
On headless systems, set `QT_QPA_PLATFORM=offscreen` using shell-appropriate syntax.
Real Qt tests need PySide6 and native libraries; optional-dependency stubs in
`tests/conftest.py` do not establish real integration coverage.
Video integration tests may require `BLURZY_TEST_VIDEO_PATH` pointing to local
media. The default suite does not require downloading model weights.
See [test layout](../tests/README.md) and [development](../docs/development/development.md).

Keep runtime dependencies in `pyproject.toml`; `requirements.txt` delegates with
`-e .`. Documentation dependencies are separate in `requirements-docs.txt`.
Consult `.github/workflows/ci.yml` and `.github/workflows/pages.yml` for actual CI
commands and platform prerequisites; do not assume local checks exactly match CI.

## Documentation

Code must be well documented with mkdocstrings-compatible docstrings. Document
public modules, classes, and functions with useful behavioral contracts,
Google-style sections, and fenced examples where relevant.
Architecture pages explain workflows and ownership; API contracts belong in
Python docstrings.
Follow the [project docstring standard](../docs/development/documentation-style.md#4-docstring-standard)
and [Material for MkDocs reference](https://squidfunk.github.io/mkdocs-material/reference/).
Griffe parses Google-style contracts; Markdown extensions and Material render
their content. Keep annotations as the type source instead of repeating types
in every `Args:` entry. Document ownership, side effects, locking, and failure
semantics accurately; do not infer guarantees from formatting.
Use only features enabled in `mkdocs.yml`: correctly indented admonitions,
collapsible details, language-labelled fences, content tabs, figures/captions,
tables, and opt-in code annotations. Keep essential warnings visible.
Do not put article front matter in docstrings or require decorative markup.
For every code change, review affected documentation articles under `docs/` and
update them when behavior, workflows, interfaces, or architecture change.
Documentation diagrams may use Mermaid or SVG and must remain readable in both
light and dark themes. Use theme-aware Mermaid styling or equivalent light/dark
SVG variants, preserving editable sources and checking both themes.
Follow [architecture authoring](../docs/development/architecture-documentation.md)
for diagrams, themed assets, and reproducible examples, and
[reference generation](../docs/development/reference-documentation.md) for API rules.

API pages under `docs/reference/api` are virtual files generated by
`scripts/docs_reference.py`; never add handwritten pages there. Static collection
must not import Qt/ML, run inference, or download weights. Edit source docstrings
for API prose and `docs/architecture` for cross-component explanations.
Do not commit generated `site` output, local environments, logs, or model weights.

For documentation builds, install only `requirements-docs.txt` and run
`python -m mkdocs build --strict`; documentation-tooling changes also require
`python -m unittest discover -s tests -p "test_docs_reference.py"`.
An instruction-only Markdown change needs link/accuracy review, not app tests.
Keep this instruction file aligned with changes to project structure and commands.

## Versioning and release records

Version and changelog maintenance is mandatory, even during early development.
The historical 1.1.0 entry is a retrospective baseline, not a reason to leave
future changes undocumented. Follow the
[versioning policy](../CONTRIBUTING.md#versioning-and-changelog).

- For every user-visible feature, fix, or workflow change, update
  `CHANGELOG.md` in the same change. Use Unreleased for changes after the latest
  recorded version; do not leave "No unreleased changes" above pending entries.
- Use major/minor/patch intent: incompatible public contracts or file formats,
  compatible features/substantial UI changes, and compatible fixes respectively.
  Coordinate a bump once per version update, not once per file or commit.
- When advancing the application version, keep `[project].version` in
  `pyproject.toml`, `APP_VERSION` in `src/app/shared/distribution.py`, the new
  changelog heading, and the homepage version label in sync. Review other
  current-version references, build metadata, and user docs too.
- Do not bump project/layer file `format_version` for an application release
  unless the serialized schema changes. Preserve historical changelog entries
  and recorded example/tool provenance.
- Review README status tables, getting-started steps, affected architecture/API
  docs, and homepage claims. Visible UI changes also require checking the
  homepage screenshot; use approved real app captures, not stale fixtures.
- Run the version-consistency test and relevant documentation checks. A version
  edit does not authorize creating a tag, publishing a package, or a release.
