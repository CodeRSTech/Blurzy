# Blurzy

> Blurzy is a PySide6 desktop app for video detection, tracking, annotation, and exporting video with blurred subjects.

---
## 📚 Overview

* 📖 **[User Documentation](https://github.com/your-org/your-repo/wiki)** — Getting started guides and API references.
* 🛠️ **[Developer Guide](CONTRIBUTING.md)** — Set up your local environment and submission guidelines.
* 📋 **[Changelog](CHANGELOG.md)** — Recent updates and release history.

---
### Tests 📠  

All tests pass locally.
---

## 🎯 Documentation Feature Backlog

We treat documentation as a first-class feature. Below is our active backlog for documentation improvements, new guides, and structural updates.

> **Status Key:**
> - 🟢 **Completed** — Live in the repo/wiki
> - 🟡 **In Progress** — Currently being worked on
> - ⚪ **Backlog** — Planned, open for contributions
> - 🔴 **Blocked** — On hold pending code changes or clarification

### 🚀 Upcoming & In-Progress

| Status | Feature / Document Topic                                                | Priority | Rationale                                 | Issue / PR |
|:------:|:------------------------------------------------------------------------|:--------:|:------------------------------------------|:----------:|
|   🟢   | **Implement Export feature**                                            |   High   | Makes app _complete_ to a certain extent  | Unassigned |
|   🟢   | **Import/Export detection results**                                     |   High   | Bypass Detection worker overhead          | Unassigned |
|   ⚪   | **Define constants at one place**                                       |  Medium  | Improve maintainability and reduce errors | Unassigned |
|   ⚪   | **Delegate creation of view models to a separate service**              |  Medium  | Make code independent of view models      | Unassigned |
|   ⚪   | **Audit/Split `app.ui.qt.widgets.layer_bbox`**                          |  Medium  | Improve maintainability and reduce error | Unassigned |
|   🟡   | **Audit/Split `app.ui.infastructure.session.session` responsibilities** |   Low    | Improve code organization and clarity     | Unassigned |
|   ⚪   | **Create PRs for aforementioned items**                                 |   Low    | Helps track progress and contributions    | Unassigned |## 📋 Feature Ideas & Wishlist

* [x] Phase out using references to `Application` in app services with `ApplicationAdapter`
* [x] Optimize `src.app.infrastructure` imports via `__init__.py` to reduce circular dependencies
* [ ] Refine the UI and potentially UX
* [ ] Add another dropdown just above "Model", called "Provider", which has "Torch models", "YOLO models" and "MTCNN Models".
---

## ⚡ Quickstart

### Install dependencies

```bash
pip install -r requirements.txt
```

### ▶️ Run

```bash
python src/main.py
```

---

## 🔄 Startup logging configuration

Blurzy now validates its startup logging configuration before importing the UI stack.

- `BLURZY_LOG_CONSOLE_LEVEL` — console sink level (`TRACE`, `DEBUG`, `INFO`, `SUCCESS`, `WARNING`, `ERROR`, `CRITICAL`)
- `BLURZY_LOG_FILE_LEVEL` — file sink level (same allowed values)
- `BLURZY_LOG_FILE_PATH` — writable log file path (default: `logs/app.log`)
- `BLURZY_LOG_ENABLED_AREAS` — optional comma-separated logger area allow-list

If one of these values is invalid, startup now fails fast with an explicit error message instead of silently falling back.

---

## 🧮 Architecture Overview

Code is organized into four layers:

- `src/app/domain`: core types, session state, view models
- `src/app/application`: `Application` facade and services (detection/tracking/export/session)
- `src/app/infrastructure`: workers and external integrations (video decode, ML, export)
- `src/app/ui`: Qt windows, containers, handlers, and controller

Main runtime flow:

1. UI action in `MainWindow` / right panel
2. Handler in `src/app/ui/handlers/*`
3. `Application` delegation call
4. Service + worker execution
5. Signals back to UI for progress/state updates

---

## Key Workflows

### 1) Detect

1. Open one or more videos.
2. Select a detection model in the right panel.
3. Run:
   - **Detect Current Frame** for one frame
   - **Start Background Detection** for full-session processing
4. Watch detection progress in the Detection section progress bar.

### 2) Track

1. Select source layer + tracking strategy.
2. Start tracking from the right panel.
3. Tracking shows an in-progress state and completes with a final progress update.

### 3) Export

- **Single export:** uses frame-level export progress.
- **Batch export (Export All):**
  - per-session progress (current session export)
  - overall progress (sessions completed / total)

## UI Progress + Loading UX

- Detection, tracking, and export all surface progress in UI.
- Model loading uses an inline spinner indicator and runs in a worker thread.
- Progress/loading states are reset on success, failure, and cancellation paths.

---

## Troubleshooting

### `ModuleNotFoundError` for PySide6 / av / torch

Reinstall dependencies in the active virtualenv:

```bash
pip install -r requirements.txt
```

### Tests not running locally

This repo uses `pytest`-style tests under `tests/`, but several tests expect local media paths and optional environment setup.
Adjust test input paths and install test dependencies before running.

Quick checklist:

1. Install test tools: `pip install pytest pytest-qt`
2. Ensure Qt dependency is installed (`PySide6`)
3. Run from repo root with module path:
   - `PYTHONPATH=src python -m pytest -q`
4. Update hardcoded local media paths in tests to files available on your machine

---

## 💡 How to Propose a Docs Feature

Notice a gap in our docs or have an idea for a guide? We’d love your input!

1. Check the [Documentation Backlog](#-documentation-feature-backlog) above to see if it's already planned.
2. Open a new issue using our **[Documentation Proposal Template](https://github.com/your-org/your-repo/issues/new?template=doc_proposal.md)**.
3. To take on an unassigned item from the table above, comment directly on the issue or open a PR referencing the item!

---
