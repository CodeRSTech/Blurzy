# Phase 1: Selection Seam Analysis

## Current Selection Architecture

### 1. Selection State Producers

#### Table (BottomDataPanelContainer)
- **File:** `src/app/ui/qt/sections/bottom_data_panel.py`
- **Mechanism:** Qt `QTableWidget.selectionModel()` and `itemSelectionChanged` signals
- **Scope:** Per active tab (Detection or Tracking)
- **Key extraction:** `get_selected_box_keys_from_active_tab` property
  - Reads from `selectionModel().selectedRows()`
  - Extracts box keys from row 0 column's `UserRole` data
  - Returns list of box keys by iterating selected rows

#### Canvas (AnnotationOverlayWidget)
- **File:** `src/app/ui/qt/widgets/preview/layer_bbox/layer_bbox.py`
- **Mechanism:** Transient `self._editing_bbox_id` on canvas click
- **Scope:** Single box during edit-mode interaction
- **Key extraction:** Line 262 `try_select_bbox_for_edit()` → emits no signal, only updates internal state
- **Problem:** Canvas does NOT synchronize selection back to the table; it only tracks which box is being edited

### 2. Selection State Consumers

#### Action Enablement (Bottom Panel Buttons)
- **File:** `src/app/ui/qt/sections/bottom_data_panel.py`, method `_update_frame_box_buttons_state()`
- **Consumes:** `get_selected_box_keys_from_active_tab` property
- **Enables/Disables:**
  - `edit_box_btn` if exactly one box selected
  - `delete_box_btn`, `copy_to_next_btn`, `copy_to_prev_btn`, etc. if ≥1 box selected
- **Problem:** Only triggers on table signals (`itemSelectionChanged`, `cellClicked`)

#### Annotation Handler (AnnotationHandler)
- **File:** `src/app/ui/handlers/annotation_handler.py`
- **Methods:**
  - `on_edit_selected()` line 258
  - `on_delete_selected()` line 274
  - `handle_nudge_key()` line 215
  - `copy_to_direction()` line 483
- **Consumes:** `self._window.selected_frame_box_keys` → fetches from `Window.selected_frame_box_keys` property
- **Problem:** All slots are driven by table/button clicks or keyboard; canvas selection does NOT trigger these

#### UI Rendering (UIHandler)
- **File:** `src/app/ui/handlers/ui_handler.py`, method `_update_frame_with_bboxes()`
- **Behavior:** 
  - Line 282: Creates `active_bboxes` dict from all boxes in the current frame
  - Line 283: Calls `preview_container.set_active_bboxes(active_bboxes)`
  - **Problem:** Passes ALL boxes, not just selected boxes; canvas overlay treats all boxes as "active" for rendering purposes
- **Problem:** Selection state is not used during render; the table repopulation at line 298 uses the same `set_boxes_for_tab()` which internally preserves selection by key, but the overlay never gets the selection information

#### Table Repopulation (Bottom Data Panel)
- **File:** `src/app/ui/qt/sections/bottom_data_panel.py`, method `set_data_table_boxes()`
- **Behavior:**
  - Reads `selected_box_keys: set[str]` parameter (line 262)
  - Iterates through new boxes, matches by key (line 283)
  - Re-selects rows if `item.key in selected_box_keys` (line 289)
  - **Design:** Selection is preserved by key across renders
- **Call sites:**
  - `set_data_boxes_for_tab()` line 251: captures selection before render
  - `set_tracker_data_boxes()` line 231: captures selection before render

### 3. Selection State Ownership

**Current:** Table owns selection state; canvas has only transient edit state
- Table's `QTableWidget.selectionModel()` is the only persistent selection store
- Canvas clicks only update `_editing_bbox_id` for visual feedback, no cross-sync
- Window delegates to bottom panel: `Window.selected_frame_box_keys` → `bottom_panel.get_selected_box_keys_from_active_tab`

### 4. Selection Scope

- **Session scope:** `self._window.selected_s_id` from `BottomDataPanelContainer.selected_s_id`
- **Tab scope:** `self._window.active_tab_index` from `BottomDataPanelContainer.active_tab_index`
- **Key format:** `box.key` (e.g., "manual:123" or "track:track-uid")
- **No session+tab-specific container:** Selection is scattered across Window, BottomPanel, and AnnotationHandler

### 5. Render Refresh Impact

**Critical behavior:** Table selection is preserved by box key during frame refresh
- Line 251 in `set_data_boxes_for_tab()`: saves current selection as `set[str]` BEFORE clearing table
- Line 254: calls `set_data_table_boxes(boxes, data_table, selected_box_keys)`
- Line 283-284 in `set_data_table_boxes()`: re-selects rows where `item.key in selected_box_keys`

**But canvas is cleared on every render:**
- `UIHandler.render_saved_frame()` line 163: calls `_draw_boxes_on_frame_for_session_id()`
- No attempt to preserve canvas `_editing_bbox_id` across render
- Canvas overlay is stateless with respect to selection

### 6. Context Menu and Keyboard

#### Context Menu (layer_bbox/menu.py)
- **No selection awareness:** Actions like "Delete", "Select All" are placeholder (NO_OP)
- **Line 30:** `AnnotationContextActions.NO_OP.value` for "Select All", "Deselect All", "Invert Selection"
- **Handler:** `annotation_handler.on_preview_context_action()` line 413 routes actions but has no shared selection model to operate on

#### Keyboard (FrameTableKeyFilter)
- **File:** `src/app/ui/view_state/table_key_filter.py`
- **Scope:** Installed on data tables only
- **Behavior:** Passes only `handle_nudge_key()` events; table must have focus
- **Problem:** No Delete key handler, no multi-select shortcuts

---

## Selection Seam Recommendation

### Proposed Seam: BBoxSelectionState

Create a new, lightweight selection container that lives in a stable location accessible to all consumers:

```python
# src/app/ui/view_state/bbox_selection_state.py

class BBoxSelectionState:
    """Shared box-key selection for a given session and tab."""
    
    def __init__(self):
        self._selected_keys: set[str] = set()
    
    def select(self, key: str) -> None:
        """Add a box to the selection."""
        self._selected_keys.add(key)
    
    def deselect(self, key: str) -> None:
        """Remove a box from the selection."""
        self._selected_keys.discard(key)
    
    def toggle(self, key: str) -> None:
        """Toggle a box in the selection."""
        if key in self._selected_keys:
            self._selected_keys.discard(key)
        else:
            self._selected_keys.add(key)
    
    def set_selection(self, keys: Iterable[str]) -> None:
        """Replace the entire selection."""
        self._selected_keys = set(keys)
    
    def clear(self) -> None:
        """Clear the entire selection."""
        self._selected_keys.clear()
    
    def get_selected_keys(self) -> list[str]:
        """Return the current selection as a list."""
        return list(self._selected_keys)
    
    def is_selected(self, key: str) -> bool:
        """Check if a key is selected."""
        return key in self._selected_keys
    
    def select_all(self, keys: Iterable[str]) -> None:
        """Select all boxes from a given set."""
        self._selected_keys.update(keys)
    
    def invert(self, all_keys: Iterable[str]) -> None:
        """Invert selection against a full set."""
        all_keys_set = set(all_keys)
        self._selected_keys = all_keys_set - self._selected_keys
```

### Placement Strategy

1. **Create** `src/app/ui/view_state/bbox_selection_state.py` with the state class
2. **Instantiate** in `Window` or `UIController`:
   - One `BBoxSelectionState` per active session+tab pair
   - Keyed by `(session_id, tab_index)` in a dict
3. **Expose** via property on `Window`:
   - `current_bbox_selection: BBoxSelectionState` (read-only)
   - `get_bbox_selection(s_id, tab) -> BBoxSelectionState` (lookup)
4. **Connect** producers:
   - Table selection changes → update shared state
   - Canvas clicks → update shared state
5. **Connect** consumers:
   - Action enablement reads from shared state
   - Handler methods read from shared state
   - Render refresh preserves selection from shared state
   - Canvas overlay highlights selected boxes from shared state

---

## Producer/Consumer Mapping

| Producer | Current Mechanism | Future Target |
|----------|-------------------|----------------|
| Table click | `QTableWidget.selectionModel()` signal | → `BBoxSelectionState.select()` |
| Canvas single click | `_editing_bbox_id` (transient) | → `BBoxSelectionState.toggle()` (or select) |
| Context menu action | None (NO_OP) | → `BBoxSelectionState` operations |
| Keyboard shortcut | None yet | → `BBoxSelectionState` operations |

| Consumer | Current Read | Future Read |
|----------|--------------|-------------|
| Action enablement | `get_selected_box_keys_from_active_tab` property | → `current_bbox_selection.get_selected_keys()` |
| Handler methods | `self._window.selected_frame_box_keys` | → `self._window.current_bbox_selection.get_selected_keys()` |
| Table repopulation | Saved `selected_box_keys` set | → `current_bbox_selection.get_selected_keys()` |
| Canvas overlay | None | → `current_bbox_selection` for highlight rendering |

---

## Exit Criteria Status

- [x] Single selection seam chosen: `BBoxSelectionState` container
- [x] Producers and consumers mapped
- [x] Phase 2 can proceed to wiring without re-deciding ownership
