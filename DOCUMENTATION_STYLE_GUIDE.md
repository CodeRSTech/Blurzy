# EazyBlur Documentation Style Guide

## Overview

This document defines the **modern documentation styling** used throughout EazyBlur, with emphasis on consistency, clarity, and developer experience. The codebase is transitioning to this new standard incrementally, starting with fresh files like `session.py`.

---

## Phase 1 Engineering Conventions (Handlers / Services / Workers)

### 0. Responsibilities and Signal Ownership

- **Handlers (`src/app/ui/handlers`)**
  - Own Qt slot orchestration and UI state transitions.
  - Connect to worker signals and always handle success/failure/cancel cleanup.
  - Never implement core business logic that belongs in services.
- **Services (`src/app/application/services`)**
  - Own domain/application decisions and validation.
  - May create/configure workers, but should stay UI-agnostic.
- **Workers (`src/app/infrastructure/*worker.py`)**
  - Run heavy/background work only.
  - Emit progress + completion/error signals; never access Qt widgets directly.

### 1. Progress Signal Pattern

For long operations (detect / track / export), expose:

- `progress_updated(current: int, total: int)` when granular progress is available
- `finished_processing()` in `finally`
- `error_occurred(msg: str)` on failure
- optional `cancelled()` for user-initiated cancellation flows

UI handlers must:

1. Set progress state visible/busy at start
2. Update progress in slot callbacks
3. Reset/hide progress on all terminal paths (success, error, cancellation)

### 2. Logging and Exception Pattern

- Log once at service/worker boundary with context (`session`, `operation`).
- Use `logger.opt(exception=exc)` (or equivalent) for stack traces.
- Show user-facing dialog errors in handlers, not in services/workers.
- Avoid swallowing exceptions silently; convert to signal/error message.

### 3. TODO/FIXME Policy

- `TODO`: planned work with clear intent and target area.
- `FIXME`: known defect or incomplete behavior affecting correctness/UX.
- Keep each TODO/FIXME actionable and short.
- Remove TODO/FIXME as soon as implemented; do not leave stale comments.

### 4. Docstring Standard

- Keep simple methods to one-line docstrings.
- Use multi-line docstrings for lifecycle/flow-heavy methods.
- Document trigger/source signal for slots and emitted side effects where useful.
- Prefer describing **why** and lifecycle guarantees over repeating obvious code.

---

## 1. One-Liner Docstrings

### Rule: Simple, Direct Purpose

Every method should have a **single-line docstring** that completes the sentence: *"This method..."*

#### Format
```python
def method_name(self) -> ReturnType:
    """Clear description of what this method does."""
    ...
```

#### Variable Formatting

Use **backticks** (`` `variable` ``) for:
- Parameter names
- Variable names
- Return values
- Layer/class names

Use **formatting directives** for emphasis:
- `**bold text**` — for critical concepts (e.g., `**ALWAYS**`, `**DO NOT**`)
- `*italic text*` — for gentle emphasis
- `>>` or `→` — for flow/direction

#### Examples

✅ **GOOD:**
```python
def get_layer_by_name(self, layer_name: DataLayer) -> BoxesByFrameIndex:
    """Fetch all bounding boxes grouped by frame index for the specified ``layer_name``."""
    return self.data.get_all_boxes_for_layer_as_dict_of_lists(layer_name)

def has_boxes_for_layer(self, layer_name: DataLayer) -> bool:
    """Check if ``layer_name`` contains **any** bounding boxes."""
    return self.data.has_boxes_for_layer(layer_name)

```

❌ **BAD:**
```python
def get_layer_by_name(self, layer_name):
    """Get layer"""  # Vague, no variable formatting
    ...

def has_boxes_for_layer(self, layer_name):
    """Returns true or false if boxes exist"""  # Awkward grammar, no formatting
    ...
```

---

## 2. Flow Documentation with Section Blocks

### Rule: Structured Step-by-Step Comments

For methods with multiple logical steps, use **section dividers** to organize flow. This pattern is used consistently in `session.py` and `service.py`.

#### Format

```python
def complex_operation(self):
    """High-level summary of what this method does."""
    
    # ============================================================================
    # 1. STEP NAME — Brief description
    # ============================================================================
    # Additional context or rationale if needed
    step_1_result = do_something()
    
    # ============================================================================
    # 2. NEXT STEP NAME — What happens here
    # ============================================================================
    if step_1_result is None:
        logger.warning("Step 1 failed, proceeding with fallback")
    
    # ============================================================================
    # 3. FINAL STEP — Wrap up
    # ============================================================================
    return process_result(step_1_result)
```

#### Rules for Step Blocks

1. **Use ALL CAPS for step names**: `# 1. FETCH SESSION INSTANCE`
2. **Precede with `# =============...` (60+ `=` chars)**
3. **Number steps sequentially**: `# 1.`, `# 2.`, etc.
4. **Add brief explanation after the dash**: `# 1. STEP NAME — What it does`
5. **Include context comments above if needed** — especially for non-obvious logic
6. **One blank line before and after the section block**

#### Real Examples from Codebase

**From `session.py` (lines 197–243):**
```python
def get_frame_by_index(self, frame_index: int) -> RGBFrame | None:
    """Fetches a specific frame directly from the O(1) Ring Buffer, or triggers a seek."""
    
    # ====================================
    # 1. Check if frame at index is cached
    # ====================================
    cached_frame = decode_worker.get_cached_frame_at_index(safe_idx)
    if cached_frame is not None:
        session_state.playback.current_frame_index = safe_idx
        return cached_frame
    
    # ====================================
    # 2. Cache Miss
    # ====================================
    is_sequential_underrun = abs(safe_idx - session_state.playback.current_frame_index) <= 1
    if not is_sequential_underrun:
        decode_worker.request_seek(safe_idx)
    
    # ====================================
    # 3. Wait for worker to catch up
    # ====================================
    attempts = 0
    while attempts < 200:  # 2.0 second timeout
        cached_frame = decode_worker.get_cached_frame_at_index(safe_idx)
        if cached_frame is not None:
            return cached_frame
        time.sleep(0.01)
        attempts += 1
```

**From `service.py` (lines 57–117):**

```python
def detect_current_frame(self, s_id: SessionId) -> None:
    """
    Detect objects in the current frame of the ``Session`` specified by the ``SessionId``
    using the currently set detection model. If no model is set, skip detection and
    clear any existing detection layers.
    """

    # ============================================================================
    # 1. FETCH SESSION INSTANCE
    # ============================================================================
    session = self._app.get_session_by_id(s_id)

    # ============================================================================
    # 2. CHECK MODEL NAME
    # ============================================================================
    if session.state.session_settings.model_name_is_null:
        logger.info("Detect current frame skipped: model is None")
        return

    # ... (continues with steps 3–6)
```

---

## 3. Inline Comments for Non-Obvious Logic

### Rule: Explain *Why*, Not *What*

**The code shows WHAT happens; comments explain WHY.**

#### Format

```python
# [NOTE] Explanation of design decision or gotcha
# This bypass directly accesses the ring buffer through a new method
cached_frame = decode_worker.get_cached_frame_at_index(safe_idx)

# [FIXME] Known issue or debt item
# Currently, the progress is merely logged, wire it into a progress indicator within the UI
logger.info("Detection worker processed {}/{} frames.", processed_frames, total_frames)

# [TODO] Future work or enhancement
# Extract the timeout-loop out of `Session` and move it into `VideoDecodeWorker`
```

#### Tags

Use these prefixes for special comments:

| Tag | Usage | Example |
|-----|-------|---------|
| `[NOTE]` | Design decision, architectural rationale | `# [NOTE] Even though we start the worker here, it will only be active when session becomes active` |
| `[FIXME]` | Known bug or incomplete feature | `# [FIXME] Currently, progress is merely logged, wire it into a progress indicator` |
| `[TODO]` | Future enhancement or refactoring | `# [TODO] Extract timeout-loop into VideoDecodeWorker` |
| `[NEW]` | Recently added or changed behavior | `# [NEW] Use the new method to bypass direct buffer access` |
| `[DEPRECATED]` | Old code to be removed | `# [DEPRECATED] This approach is superseded by the streaming API` |

### 3.1 IMPORTANT: Critical Warnings Block

For **critical warnings** about thread safety, memory management, or other gotchas that **MUST** be understood before modifying code, use the boxed IMPORTANT template:

```python
# ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
# ┃                                  IMPORTANT                         ┃
# ┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
# ┃ Because the worker is parentless (required by moveToThread()),     ┃
# ┃ Qt will NOT automatically delete it when the main class is         ┃
# ┃ destroyed. We must manually orchestrate a synchronized teardown    ┃
# ┃ to prevent memory leaks and thread crashes.                        ┃
# ┃                                                                    ┃
# ┃ The mandatory shutdown sequence must always follow this order:     ┃
# ┃ 1. Stop the worker: Signal it to finish its current loop.          ┃
# ┃ 2. Quit the thread: Tell the QThread event loop to stop.           ┃
# ┃ 3. Wait for exit: Block the main thread until OS closes thread.    ┃
# ┃ 4. Delete the worker: Safely free the parentless worker memory.    ┃
# ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

**Use IMPORTANT blocks for:**
- Thread safety constraints
- Memory management gotchas
- Object lifetime issues
- Strict ordering requirements
- Cross-layer architectural rules

**Real example from `model_handler.py`:**
```python
@Slot()
def _cleanup(self) -> None:
    # ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    # ┃                                  IMPORTANT                    ┃
    # ┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
    # ┃ Do NOT call deleteLater() on active threads or workers.      ┃
    # ┃ Must call quit() → wait() before deleting memory.            ┃
    # ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
    
    # 1. Stop and join the thread
    if self._model_load_thread is not None and self._model_load_thread.isRunning():
        self._model_load_thread.quit()
        self._model_load_thread.wait()
    
    # 2. Schedule worker deletion
    if self._model_load_worker is not None:
        self._model_load_worker.deleteLater()
```

---

## 4. Multi-Line Docstrings (For Complex Methods)

### Rule: When a One-Liner Isn't Enough

Use triple-quoted docstrings for methods that need more explanation (especially in infrastructure/application layers).

#### Format (Google Style)

```python
def complex_method(self, param1: str, param2: int) -> dict:
    """
    Brief one-line summary.
    
    Longer explanation of the method's behavior, including:
    - Key preconditions
    - Side effects
    - Unusual return values
    
    Args:
        ``param1``: Description with ``backticks`` for variables.
        ``param2``: Another parameter description.
    
    Returns:
        A ``dict`` mapping frame indices to detection results.
    
    Raises:
        ``ValueError``: If ``param2`` is negative.
    """
```

#### Example from Infrastructure

```python
def start_detection_worker_for_session_id(self, s_id: SessionId) -> None:
    """
    Starts a background ``DetectionWorker`` for the session specified by ``s_id``.
    
    This method initializes the detection engine, creates a worker thread,
    and begins processing frames in the background. **DO NOT** call this
    if a worker is already running; check ``session.has_running_detection_worker`` first.
    
    Args:
        ``s_id``: The ``SessionId`` identifying the target session.
    
    Raises:
        ``WorkerAlreadyRunningException``: If a detection worker is already active.
        ``NullModelNameException``: If no detection model has been selected.
    """
```

---

## 5. Class-Level Documentation

### Rule: Describe Purpose and Responsibilities

Every class should have a docstring explaining its role in the architecture.

#### Format

```python
@final
class Session(QObject):
    """
    Manages the state and lifecycle of a single video processing session.
    
    Responsibilities:
    - Holds ``SessionState`` (playback, settings, annotations)
    - Manages ``VideoDecodeWorker`` for frame buffering
    - Provides frame access methods (``get_current_frame``, ``get_frame_by_index``)
    - Manages detection layer CRUD operations
    - Coordinates with detection and tracking workers
    """
```

#### Example: Full Class Documentation

```python
@final
class DetectionService:
    """
    Orchestrates model-based object detection across sessions.
    
    Responsibilities:
    - Create and manage ``DetectionEngine`` instances per session
    - Start background ``DetectionWorker`` threads
    - Route detection batches back to session data stores
    - Handle model switching and layer clearing
    
    Design Notes:
    - Although ``Session`` holds the ``DetectionEngine``, this service
      creates and manages it to keep ``Session`` decoupled from detection logic.
    """
```

---

## 6. Documenting Signals and Slots in PySide6

### Rule: Trace the Signal Cascade

Qt applications use **signals and slots** to communicate between objects. Documentation must clearly show:
1. **Where the signal originates** (top-level event or emit)
2. **Which slot receives it** (and where it lives)
3. **What signal it emits next** (cascade/chain)
4. **The overall flow** from user action to final state change

### 6.1 Top-Level Slots (Entry Points)

**Top-level slots** are triggered by built-in Qt events (button clicks, menu actions, etc.) and usually emit signals that cascade downstream. These should include **complete signal flow documentation**.

#### Format

```python
from PySide6.QtCore import pyqtSignal, Slot

class MyWidget(QWidget):
    # ════════════════════════════════════════════════════════════════════════
    # SIGNALS: Emitted when actions complete
    # ════════════════════════════════════════════════════════════════════════
    action_completed = pyqtSignal(str)  # Emits result
    
    @Slot()
    def on_button_clicked(self) -> None:
        """
        Handle button click and trigger downstream signal cascade.
        
        **Signal Cascade:**
        ```
        QButton.clicked (Qt built-in event)
          └──> MyWidget.on_button_clicked() [this slot]
                  └──> Perform action
                  └──> Emit MyWidget.action_completed(result)
                          └──> Connected slot in caller (e.g., Controller.on_action_completed)
        ```
        
        Signal Flow: ``QButton.clicked`` → ``on_button_clicked()`` 
        → ``action_completed`` → downstream handlers
        """
        result = self._do_work()
        self.action_completed.emit(result)
```

#### Real Example from Codebase

```python
class TopRow(QWidget):
    # ════════════════════════════════════════════════════════════════════════
    # SIGNALS
    # ════════════════════════════════════════════════════════════════════════
    open_videos_requested = pyqtSignal(list)  # Emits list[str] (file paths)
    
    @Slot()
    def choose_video_files(self) -> None:
        """
        Open file browser and request video files to be opened.
        
        **Signal Cascade (Complete Flow):**
        ```
        TopRow.choose_button.clicked (Qt built-in)
          └──> TopRow.choose_video_files() [this slot — entry point]
                  ├── Launch QFileDialog.getOpenFileNames()
                  └──> Emit TopRow.open_videos_requested(paths: list[str])
                          └──> SessionHandler.on_open_videos(paths: list[str])
                                  └──> SessionHandler processes and opens sessions
                                          └──> Calls App.open_videos(paths)
        ```
        
        Signal Flow: ``choose_button.clicked`` → ``choose_video_files()`` 
        → ``open_videos_requested`` → ``SessionHandler.on_open_videos()``
        """
        paths, _ = QFileDialog.getOpenFileNames(
            self._parent,
            "Open Video Files",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.wmv *.m4v);;All Files (*)",
        )
        if paths:
            self.open_videos_requested.emit(paths)
```

### 6.2 Mid-Level Slots (Intermediate Handlers)

**Mid-level slots** receive signals from upstream and emit signals downstream. They should document:
- **Which signal triggered this slot** (the "input")
- **Brief description of what it does**
- **Which signal it emits next** (the "output")

#### Format

```python
@Slot(list)
def on_open_videos(self, paths: list[str]) -> None:
    """
    Receive file paths and initiate session creation.
    
    **Triggered By:**
			``UIController.open_videos_requested``
    
    **Flow:**
    ```
    on_open_videos(paths) [this slot]
      ├── Validate paths
      └──> Emit/Call App.open_videos(paths)
              └──> SessionManager.create_session_from_video_path()
    ```
    
    **Downstream:** Calls ``App.open_videos()`` which cascades to ``SessionManager``
    """
    # ====================================================================
    # 1. VALIDATE PATHS
    # ====================================================================
    if not paths:
        logger.warning("No files selected")
        return
    
    # ====================================================================
    # 2. OPEN VIDEOS IN APP
    # ====================================================================
    self._app.open_videos(paths)
```

### 6.3 Low-Level Slots (Leaf Nodes)

**Low-level slots** typically do not emit signals; they perform final actions (update UI, log, etc.). They should document:
- **Which signal triggered this slot**
- **What it does**
- **No downstream signals** (or very few)

#### Format

```python
@Slot(SessionId)
def on_session_created(self, s_id: SessionId) -> None:
    """
    Update UI to reflect newly created session.
    
    **Triggered By:**
			``SessionManager.session_created``
    
    **Action:** Refresh the sessions list in the UI and make the new session active.
    
    **Downstream:** None (leaf node — updates UI state only)
    """
    # ====================================================================
    # 1. UPDATE UI
    # ====================================================================
    self._refresh_sessions_list()
    self._set_active_session(s_id)
    
    # ====================================================================
    # 2. LOG
    # ====================================================================
    logger.info("Session {} created and set active", s_id)
```

### 6.4 Signal Declaration with Documentation

Every signal should have a docstring explaining what it emits and when:

```python
class SessionManager(QObject):
    # ════════════════════════════════════════════════════════════════════════
    # SIGNALS
    # ════════════════════════════════════════════════════════════════════════
    
    session_created = pyqtSignal(SessionId)
    """
    Emitted when a new ``Session`` is successfully created.
    
    **Emitted by:** ``SessionManager.create_session_from_video_path()``
    
    **Payload:** ``SessionId`` — the ID of the newly created session
    
    **Downstream Handlers:** 
    - ``UIController.on_session_created()``
    - ``App.handle_active_session_changed()``
    """
    
    session_closed = pyqtSignal(SessionId)
    """
    Emitted when a ``Session`` is closed and cleaned up.
    
    **Emitted by:** ``SessionManager.close_session()``
    
    **Payload:** ``SessionId`` — the ID of the closed session
    
    **Downstream Handlers:** ``UIController.on_session_closed()``
    """
    
    detection_completed = pyqtSignal(SessionId, dict)
    """
    Emitted when background detection finishes for a frame.
    
    **Emitted by:** ``DetectionService.on_detection_batch_ready()`` (via ``DetectionWorker``)
    
    **Payload:** ``(SessionId, dict)`` — session ID and detection results {frame_index: [detections]}
    
    **Downstream Handlers:** ``AnnotationHandler.on_detection_completed()``
    """
```

### 6.5 Complete Signal Chain Example

Here's a **complete, documented signal chain** showing the entire flow from user action to state update:

```python
# ════════════════════════════════════════════════════════════════════════════════
# FILE: src/app/ui/handlers/session_handler.py
# ════════════════════════════════════════════════════════════════════════════════

@Slot(list)
def on_open_videos(self, paths: list[str]) -> None:
    """
    Receive file paths and create new sessions for each video.
    
    **Signal Cascade (Complete Flow):**
    ```
    TopRow.choose_button.clicked [Qt built-in event]
      └──> TopRow.choose_video_files() [top-level slot]
              └──> Emit TopRow.open_videos_requested(paths)
                      └──> SessionHandler.on_open_videos(paths) [this slot — mid-level]
                              └──> Call App.open_videos(paths)
                                      └──> SessionManager.create_session_from_video_path(path)
                                              └──> Emit SessionManager.session_created(s_id)
                                                      └──> UIController.on_session_created(s_id) [leaf slot]
                                                              └──> Update UI
    ```
    
    **Triggered By:**
			``TopRow.open_videos_requested`` signal
    
    **Downstream:** Indirectly triggers ``SessionManager.session_created`` → ``UIController.on_session_created()``
    """
    # ====================================================================
    # 1. VALIDATE PATHS
    # ====================================================================
    if not paths:
        logger.warning("No video files selected")
        return
    
    # ====================================================================
    # 2. DELEGATE TO APP TO OPEN VIDEOS
    # ====================================================================
    # [NOTE] App.open_videos() cascades to SessionManager, which emits signals
    try:
        self._app.open_videos(paths)
    except Exception as e:
        logger.opt(exception=e).error("Failed to open videos")
        self._show_error_dialog("Could not open video files", str(e))

# ════════════════════════════════════════════════════════════════════════════════
# FILE: src/app/ui/uicontroller.py
# ════════════════════════════════════════════════════════════════════════════════

@Slot(SessionId)
def on_session_created(self, s_id: SessionId) -> None:
    """
    Handle newly created session and update UI.
    
    **Triggered By:**
			``SessionManager.session_created`` signal
    
    **Downstream:** None (leaf node — final UI update)
    """
    # ====================================================================
    # 1. SET ACTIVE SESSION
    # ====================================================================
    self.app.active_session_id = s_id
    
    # ====================================================================
    # 2. INITIALIZE PLAYBACK
    # ====================================================================
    self.playback_handler.initialize_playback(s_id)
    
    # ====================================================================
    # 3. REFRESH UI
    # ====================================================================
    self.ui_handler.render_frame(s_id)
    logger.info("Session {} is now active", s_id)
```

### 6.6 Signal/Slot Documentation Checklist

When documenting signals and slots, verify:

- [ ] **Top-level slots include complete signal cascade** (from Qt event → all downstream handlers)
- [ ] **Mid-level slots document origin signal** (which signal triggered this?)
- [ ] **Mid-level slots document downstream signals** (what signal does this emit?)
- [ ] **Low-level slots note they are "leaf nodes"** (no further signal cascade)
- [ ] **Signal declarations have docstrings** explaining payload and downstream handlers
- [ ] **Signal flow uses tree/arrow format** (``→`` or ``├──``, ``└──``) for clarity
- [ ] **Backticks format signal names:** `` `signal_name` ``, `` `SlotName()` ``
- [ ] **Origin and destination are explicit** (no guessing where signal comes from)

---

## 7. File Organization Rule

Every `.py` file should have this structure, with careful attention to `__init__()` methods:

```python
"""One-line module docstring explaining the file's purpose."""

from __future__ import annotations

# Standard library imports
import sys
from typing import TYPE_CHECKING, final, override

# Third-party imports
from PySide6.QtCore import QObject, pyqtSignal, Slot

# Local imports
if TYPE_CHECKING:
    from app.domain.session import SessionId

from app.infrastructure.session.session_data_store import SessionDataStore
from app.shared.logging_cfg import get_logger

logger = get_logger("ModuleName")

# ============================================================================
# CLASSES
# ============================================================================

@final
class MyClass(QObject):
    """Class docstring with responsibilities and design notes."""
    
    # ════════════════════════════════════════════════════════════════════════
    # SIGNALS
    # ════════════════════════════════════════════════════════════════════════
    action_completed = pyqtSignal(str)
    """Emitted when action completes. Payload: result string."""
    
    def __init__(self):
        """Initialize the class with required dependencies."""
        super().__init__()
        
        # [Rest of __init__ follows hierarchical ASCII detection pattern below]
```

### 7.1 ASCII Box-Drawing for `__init__()` — The Session.py Pattern

For **complex `__init__()` methods** with multiple attribute initialization sections, use hierarchical ASCII boxes to show grouping:

```python
def __init__(self, s_id: SessionId) -> None:
    """Initialize the session with required workers and state."""
    super().__init__()
    
    # ┌─ SESSION ID AND DATA STORE ──────────────────────────────────┐
    # Core identifiers and data persistence layer
    self.s_id = s_id
    self.data = SessionDataStore(s_id=self.s_id, parent=self)
    
    # ├── VIDEO READER ──────────────────────────────────────────────────────┐
    # Handles video file I/O. Used by DetectionService to read current frame.
    # Also extracts metadata for SessionState initialization.
    try:
        self.video_reader = VideoReader(self.s_id.path)
    except Exception as e:
        logger.opt(exception=e).error("Failed to initialize VideoReader")
        raise e
    
    # ├─ SESSION STATE ──────────────────────────────────────────────────────┐
    # Playback state, settings, and annotations. Initialized with metadata 
    # from VideoReader (not directly from VideoReader to maintain Clean Architecture).
    self.state = SessionState(self.s_id, self.video_reader.metadata)
    
    # ├─ VIDEO DECODE WORKER ────────────────────────────────────────────────┐
    # Background worker that pre-buffers frames using a ring buffer.
    # Started here but only truly active when session becomes active.
    # [NOTE] Workers should ideally be injected rather than created here.
    self.video_decode_worker = VideoDecodeWorker(
        self.s_id.path, 
        self.state.playback, 
        parent=self
    )
    self.video_decode_worker.start()
    
    # ├─ DETECTION AND TRACKING WORKERS ─────────────────────────────────────┐
    # Lazily initialized — created when user starts detection/tracking.
    # [NOTE] DetectionService creates/manages these, not Session directly.
    self.detection_engine = None
    self.detection_worker = None
    self.tracking_worker = None
```

**Benefits of this pattern:**
- Visual hierarchy makes dependencies clear
- Comments explain *why* each attribute exists
- Reader can understand initialization order at a glance
- Easy to spot missing cleanup in `close()` method

#### ASCII Box Characters Reference

| Character | Name | Usage |
|-----------|------|-------|
| `┌` | Box corner (top-left) | Start of a new attribute group |
| `├` | Box junction (left-mid) | Sub-attribute or nested level |
| `└` | Box corner (bottom-left) | Last item in a section |
| `─` | Box horizontal line | Connects labels |
| `┐` | Box corner (top-right) | End delimiter (optional) |
| `┤` | Box junction (right-mid) | Right-side connection (optional) |
| `┘` | Box corner (bottom-right) | End of section (optional) |

**Typical patterns:**
```
# ┌─ FIRST GROUP ──────────────────┐
# Self-contained initialization
# ├── SUB-GROUP ─────────────────────────┐
# Nested or dependent initialization
# ├─ THIRD GROUP ──────────────────────────────────┐
# Another top-level group
# └─ FINAL CLEANUP ────────────────────────────────┐
# Last group or initialization step
```

---

## 8. Checklist for Documentation Compliance

When writing or reviewing code, verify:

- [ ] **Every public method has a one-liner docstring**
- [ ] **Variables in docstrings use backticks:** `` `variable` ``
- [ ] **Complex methods use section blocks** with `# ====` dividers
- [ ] **Section blocks are numbered and ALL CAPS:** `# 1. STEP NAME`
- [ ] **Inline comments use tags** (`[NOTE]`, `[FIXME]`, `[TODO]`, etc.)
- [ ] **Critical warnings use IMPORTANT blocks** (for thread safety, memory management, etc.)
- [ ] **Non-obvious logic has a "why" comment**, not just a "what" comment
- [ ] **Classes have docstrings** describing responsibilities
- [ ] **Method docstrings are concise** (fit in one line when possible)
- [ ] **Multi-line docstrings follow Google Style** (Args, Returns, Raises)
- [ ] **All signals have docstrings** (payload, emission point, downstream handlers)
- [ ] **Top-level slots include signal cascade diagram**
- [ ] **Mid-level slots document origin and downstream signals**
- [ ] **Low-level slots note they are leaf nodes**
- [ ] **`__init__()` methods use ASCII box grouping** for multiple attributes
- [ ] **IMPORTANT blocks use box-drawing characters** for critical sections

---

## 9. Refactoring with Copilot: A Workflow

### Step 1: Load the File
Ask Copilot:
```
Analyze this Python file for documentation coverage. 
Identify methods without docstrings or with incomplete documentation.
```

### Step 2: Generate Docstrings
Ask Copilot:
```
Generate one-liner docstrings for these methods using the EazyBlur style guide:
- Format variables in backticks
- Use bold/italic for emphasis
- Keep it to one line

Here are the methods: [paste method signatures]
```

### Step 3: Add Flow Sections
Ask Copilot:
```
This method has 5 logical steps. Reformat it with section blocks using the style:
# ============================================================================
# 1. STEP NAME — Description
# ============================================================================

Here's the method: [paste code]
```

### Step 4: Document Signals and Slots
Ask Copilot:
```
This is a PySide6 UI file with signals and slots. Using the style guide, 
document all signals and slots including:
- Signal cascade for top-level slots (entry points)
- Origin/downstream signals for mid-level slots
- Signal declarations with payload documentation

Here's the file: [paste code]
```

### Step 5: Review and Iterate
Ask Copilot:
```
Review this documentation against the EazyBlur style guide. 
Are there any inconsistencies or areas that could be clearer?
Suggest improvements.
```

---

## 10. Quick Reference: Backtick Usage

| Context | Example |
|---------|---------|
| Parameter | ``frame_index`` |
| Variable | ``current_frame`` |
| Enum/Layer | ``DataLayer.A`` |
| Class | ``DetectionEngine`` |
| Method | ``get_frame_by_index()`` |
| Constant | ``MAX_BUFFER_SIZE`` |
| Return type | Returns a ``dict`` of results |
| Signal | `` `action_completed` `` signal |
| Slot | `` `on_button_clicked()` `` slot |

---

## 11. Next Steps

1. **Review existing files** — Compare against this guide
2. **Update older files incrementally** — Start with core infrastructure files
3. **Document all UI signals/slots** — Priority for handlers and controllers
4. **Use the IMPORTANT block** for critical thread/memory warnings
5. **Use the ASCII box pattern** in `__init__()` methods for clarity
6. **Use Copilot for bulk refactoring** — Ask it to apply the style to entire modules
7. **Create PR templates** — Include documentation checklist
8. **Add pre-commit hooks** (optional) — Check for missing docstrings

---

## Summary

The **modern EazyBlur documentation style** emphasizes:

1. ✅ **Clarity** — One-liner docstrings with backtick-formatted variables
2. ✅ **Structure** — Numbered section blocks (`# 1. STEP NAME`) for multi-step methods
3. ✅ **Context** — Inline tags (`[NOTE]`, `[FIXME]`, `[TODO]`) for design decisions
4. ✅ **Critical Warnings** — Boxed IMPORTANT blocks for thread safety and memory management
5. ✅ **Architecture** — Class-level docstrings explaining responsibilities
6. ✅ **Signal Tracing** — Complete signal cascades showing data flow through slots
7. ✅ **Initialization Clarity** — ASCII boxes in `__init__()` showing attribute grouping and dependencies
8. ✅ **Consistency** — Uniform style across all layers (Domain, Application, Infrastructure, UI)

This is *aspirational* — files like `session.py`, `model_handler.py`, `service.py`, `application.py`, and `session_handler.py` demonstrate this standard. Use this guide to bring the rest of the codebase in line incrementally.
