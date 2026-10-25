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
- Follow the existing code's typing, naming, and layering conventions (see
  [`docs/architecture/overview.md`](docs/architecture/overview.md) for the
  package boundaries).
- Describe the problem, the approach, and any manual verification in the
  pull-request description.

Please do not include test video files, model weights, or other large
generated artifacts in a pull request unless they are necessary to explain
the change.
