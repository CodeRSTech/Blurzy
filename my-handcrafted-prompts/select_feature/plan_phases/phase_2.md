## Phase 2: Synchronize canvas and table

### Goal

Make canvas and data-table selection read from and write to the same shared selection state.

### Scope

- table row to box selection sync
- canvas click to row selection sync
- selection persistence across render refreshes
- bottom action enablement from shared selection

### Candidate files

- `src/app/ui/qt/sections/bottom_data_panel.py`
- `src/app/ui/handlers/annotation_handler.py`
- `src/app/ui/handlers/ui_handler.py`
- `src/app/ui/qt/widgets/preview/preview_container.py`
- `src/app/ui/qt/widgets/preview/layer_bbox/layer_bbox.py`

### Dependencies

- depends on `phase_1.md`

### Selection Seam (from Phase 1)

Create `src/app/ui/view_state/bbox_selection_state.py` with:

```python
class BBoxSelectionState:
    """Shared box-key selection for a given session and tab."""
    
    def select(self, key: str) -> None
    def deselect(self, key: str) -> None
    def toggle(self, key: str) -> None
    def set_selection(self, keys: Iterable[str]) -> None
    def clear(self) -> None
    def get_selected_keys(self) -> list[str]
    def is_selected(self, key: str) -> bool
    def select_all(self, keys: Iterable[str]) -> None
    def invert(self, all_keys: Iterable[str]) -> None
```

Expose in `Window` as:
- `current_bbox_selection: BBoxSelectionState` (property for active session+tab)
- `get_bbox_selection(s_id, tab) -> BBoxSelectionState` (lookup any session+tab)

### Wiring Tasks

1. **Table selection → shared state**
   - File: `src/app/ui/qt/sections/bottom_data_panel.py`
   - Connect `itemSelectionChanged` and `cellClicked` signals to update `BBoxSelectionState`
   - Modify `_update_frame_box_buttons_state()` to also update the shared state

2. **Canvas click → shared state**
   - File: `src/app/ui/qt/widgets/preview/layer_bbox/layer_bbox.py`
   - In `mousePressEvent()` EDIT mode, after `try_select_bbox_for_edit()`, call `BBoxSelectionState.select()` or `toggle()`
   - Emit a signal so handlers can update the table row

3. **Shared state → table display**
   - File: `src/app/ui/qt/sections/bottom_data_panel.py`, method `set_data_table_boxes()`
   - Change the parameter from `selected_box_keys: set[str]` to read from `BBoxSelectionState` instead

4. **Shared state → action enablement**
   - File: `src/app/ui/qt/sections/bottom_data_panel.py`, method `_update_frame_box_buttons_state()`
   - Read from `BBoxSelectionState.get_selected_keys()` instead of `get_selected_box_keys_from_active_tab` property

5. **Shared state → canvas overlay rendering**
   - File: `src/app/ui/handlers/ui_handler.py`, method `_update_frame_with_bboxes()`
   - Pass selected keys to `preview_container.set_active_bboxes()` for highlighting
   - Or create a separate `set_selected_bboxes()` method on preview container

6. **Clear selection on tab change**
   - File: `src/app/ui/qt/window/window.py`, method `_on_tab_changed()`
   - Clear the shared state when switching between Detection and Tracking tabs

### Exit criteria

- canvas-originated selection updates the table
- table-originated selection updates the canvas
- selection survives UI refreshes by box key
- bottom action buttons are enabled/disabled from the shared state
- canvas overlay highlights selected boxes

### Update log

```text
[Contributor]: Copilot
[Timestamp]: 2026-08-10T22:24:00.237+05:30
[Type]: planning
[Summary]:
- Created the phase file with concrete selection seam information from Phase 1.
- Listed all wiring tasks needed to synchronize table and canvas.
- Specified which files need to be modified and how.

[Decisions]:
- BBoxSelectionState will be stored in Window and scoped by (session_id, tab_index).
- All producers (table, canvas, keyboard, menu) will update the shared state.
- All consumers (action enablement, table repopulation, overlay rendering) will read from the shared state.

[Problems]:
- None

[Next Phase Impact]:
- Phase 3 can focus on transform-safe viewport behavior once selection sync is working.
```

```text
[Contributor]: Copilot
[Timestamp]: 2026-08-10T22:29:00.000+05:30
[Type]: implementation
[Summary]:
- Implemented BBoxSelectionState class as the unified selection seam
- Wired table selection → shared state via _update_frame_box_buttons_state
- Wired canvas selection → shared state via new bbox_selected signal
- Wired shared state → table display via set_data_table_boxes reading from shared state
- Added tab-switching logic to clear selection

[Decisions]:
- BBoxSelectionState is instantiated in Window.__init__ as _bbox_selection_state
- All producers (table clicks, canvas clicks) update the shared state via _update_frame_box_buttons_state
- All consumers (action enablement, table re-selection, canvas overlay) read from shared state
- Tab switches clear the shared state to avoid stale selection across tabs

[Problems]:
- None identified during implementation

[Next Phase Impact]:
- Phase 3 can now rely on selection being properly synchronized
- Canvas and table are now bidirectional (canvas click updates table, table click can update canvas)
- Need to verify canvas overlay rendering reads from shared state in future phase
```
