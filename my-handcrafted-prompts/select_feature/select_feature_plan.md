## Select feature: implementation plan

### Problem statement

The current implementation treats selection as an incidental side effect of the table, while the product actually revolves around **boxes** as the core interactive object.

That mismatch causes:

- canvas/table desynchronization
- action enablement bugs
- unreliable delete behavior
- incomplete context-menu behavior
- difficulty adding batch operations such as relabeling

### Proposed approach

Implement the feature as a box-centric selection-system refactor, then layer actions on top of it.

### Phases

#### Phase 1: Establish the selection seam

- Introduce one authoritative selection state keyed by box key.
- Scope it to the active session and active tab.
- Identify all current producers and consumers of selection:
  - bottom data panel
  - preview overlay
  - preview container
  - annotation handler
  - keyboard filter
  - context menu

#### Phase 2: Synchronize canvas and table

- Make table selection update the shared selection state.
- Make canvas selection update the shared selection state.
- Re-render table rows and overlay highlights from that same state.
- Ensure bottom action enablement derives from shared selection, not just table signals.

#### Phase 3: Make viewport transforms selection-safe

- Audit pan/zoom plumbing across preview container and bbox overlay.
- Make hit-testing, handles, and selection rendering respect transformed coordinates.
- Keep stored box geometry unchanged while panning or zooming.

#### Phase 4: Normalize actions around selection

- Remove the obsolete bottom-panel edit button.
- Retire the dedicated Delete tool mode.
- Route deletion through shared selection and the `Delete` key.
- Wire context menu actions through the same selection-aware logic used elsewhere.

#### Phase 5: Add relabel-selected capability

- Add a selection-aware **Relabel Selected** action.
- Support both Detection and Tracking tabs.
- Allow one entered label to be applied to all selected boxes.
- Expose this from the context menu and, if appropriate after UI review, a dedicated button.

#### Phase 6: Add multi-select ergonomics

- Ctrl+click toggle selection
- click-empty-space clear selection
- Shift+drag marquee additive selection

#### Phase 7: Regression coverage

- Selection sync between canvas and table
- action enablement from canvas-originated selection
- selection persistence across render refreshes
- delete-on-selection behavior
- relabel-selected behavior
- transform-safe selection behavior during pan/zoom

### Files likely involved

- `../../src/app/ui/qt/sections/bottom_data_panel.py`
- `../../src/app/ui/qt/window/window.py`
- `../../src/app/ui/uicontroller.py`
- `../../src/app/ui/handlers/annotation_handler.py`
- `../../src/app/ui/view_state/table_key_filter.py`
- `../../src/app/ui/qt/widgets/preview/preview_container.py`
- `../../src/app/ui/qt/widgets/preview/layer_bbox/layer_bbox.py`
- `../../src/app/ui/qt/widgets/preview/layer_bbox/interaction.py`
- `../../src/app/ui/qt/widgets/preview/layer_bbox/menu.py`

### Current implementation status

- Phase 1-4 are now largely implemented: selection seam, canvas/table sync, viewport-safe overlay behavior, and selection-aware actions are in place.
- Phase 6 is also partially implemented: normal table multi-select, canvas marquee selection, and group-drag behavior for selected boxes are working.
- Remaining focus is on making delete/duplicate/relabel operations fully consistent across all entry points and codifying the behavior with regression tests.

### Notes

- The context menu currently contains actions that are effectively placeholders; those should only be fully enabled once the shared selection model exists.
- `UIHandler` repopulates tables and overlay state on render, so selection must persist by key across refreshes.
- Relabeling should be modeled as a batch action on selected boxes, not as repeated single-item edits.
- Undo/redo and clipboard support remain follow-up work unless pre-existing infrastructure makes them cheap and safe to add.
