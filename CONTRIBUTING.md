# Contributing

Thanks for helping improve Blurzy. Bug reports, documentation improvements, and
focused code changes are welcome.

## Development setup

Use Python 3.12 or newer. From the repository root, create and activate a
virtual environment, then install the project and development tools:

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

The editable install provides the `blurzy` GUI command. PyTorch and the
model-provider packages can have platform-specific requirements; consult the
relevant provider's installation guidance if its models are unavailable.
`requirements.txt` remains available for existing workflows and installs the
project from the same `pyproject.toml` metadata.

## Running tests

```bash
python -m pytest -q
```

On headless Linux, set `QT_QPA_PLATFORM=offscreen` first. Choose a smaller,
relevant subset while iterating, for example:

```bash
python -m pytest tests/domain tests/shared -q
```

Video worker integration tests are skipped unless `BLURZY_TEST_VIDEO_PATH`
points to suitable local media. The default suite does not require downloading
model weights. See [`tests/README.md`](tests/README.md) for the full test
layout.

### Qt UI regression checks

Test state transitions, not only initial rendering or emitted button signals.
For example, a preview's empty-state overlay must disappear after a frame is
shown and return when the frame is cleared. This regression was missed because
`QStackedLayout.StackAll` keeps every child visible: changing its current widget
does not hide the empty-state sibling, and the existing test covered only the
empty-state action. Explicitly manage overlay visibility and assert the
empty-to-loaded-to-empty transition in a focused Qt test.

When changing layout or styling, inspect the affected populated and empty states
in the running application at the intended window size; automated widget tests
do not catch every clipping or overlap issue.

## Documentation

Documentation uses MkDocs Material and is built from `docs/` plus generated
API reference pages from `src` docstrings. Install the documentation-only
dependencies and preview locally:

```bash
python -m pip install -r requirements-docs.txt
python -m mkdocs build --strict
```

Update the relevant guide under `docs/` when you change workflows, interfaces,
or architecture, and keep docstrings in `src` accurate, since they feed the
generated API reference. See
[`docs/development/development.md`](docs/development/development.md) and
[`docs/development/documentation-style.md`](docs/development/documentation-style.md)
for the complete workflow and docstring conventions.

## Before opening a pull request

- Run `python -m pytest -q` (or the smallest relevant subset) and make sure it
  passes.
- If you changed documentation or docstrings, run
  `python -m mkdocs build --strict`.
- `ruff` settings are configured in `pyproject.toml`; run `ruff check .` and
  `ruff format .` if you have Ruff installed.
- Keep changes focused and add or update tests when behavior changes.
- Follow the versioning and changelog policy below. Review README statuses,
  user guides, and homepage text/screenshots when behavior or visible UI changes.
- Follow the existing code's typing, naming, and layering conventions (see
  [`docs/architecture/overview.md`](docs/architecture/overview.md) for the
  package boundaries).
- Describe the problem, the approach, and any manual verification in the
  pull-request description.

Please do not include test video files, model weights, or other large
generated artifacts in a pull request unless they are necessary to explain
the change.

## Versioning and changelog

Version maintenance is part of implementation, not an optional release cleanup.
Early history was not versioned consistently; `1.1.0` in `CHANGELOG.md` is a
retrospective baseline. Preserve it, and record new changes as they happen.

Use `MAJOR.MINOR.PATCH` with semantic-versioning intent while the application
remains early-stage: major for incompatible public contracts or file formats,
minor for compatible features or substantial UI/workflow additions, patch for
compatible fixes. Version numbers do not imply a privacy guarantee or a stable
product; review exported results.

For every user-visible change, add a concise entry under **Unreleased** in
`CHANGELOG.md`, using Added, Changed, Fixed, or other relevant categories.
Replace "No unreleased changes" when adding entries. Documentation-only changes
need an entry when they materially change installation or user guidance, but
typo-only edits do not require an application-version bump.

When preparing a version update:

1. Choose the next version from the accumulated changes and update
   `[project].version` in `pyproject.toml` and `APP_VERSION` in
   `src/app/shared/distribution.py` together. The latter is used by Qt and
   bundled applications.
2. Move the relevant Unreleased entries into a dated version heading
   (`## X.Y.Z - YYYY-MM-DD`). Maintain one coordinated bump per version cycle,
   not a bump for every commit. A dated entry records repository changes; it
   does not by itself mean a package or GitHub release has been published.
3. Update the current-version label in `website/index.html` and review README
   statuses, getting-started instructions, affected architecture docs,
   docstrings, and build/distribution references. Refresh the homepage capture
   after visible UI changes, using an approved real application screenshot.
4. Run `python -m pytest tests/shared/test_distribution.py -q` and the applicable
   documentation checks.

Application versions and serialized `format_version` values are independent.
Only change a file-format version when its schema changes, with explicit
compatibility/migration handling. Do not rewrite old changelog versions or
example environment metadata to match the current app. Installed package
metadata can remain stale after editing an editable checkout's version until
the environment is reinstalled; do not report it as current source metadata.

Creating tags, publishing packages, and creating GitHub releases are separate
actions requiring maintainer approval.
