## Select feature: refined product definition

### Core idea

The most important UI object is the **box** itself.

Users draw boxes, edit boxes, select boxes, relabel boxes, duplicate boxes, and delete boxes.
Because of that, this feature should be designed around a **shared box-selection model** instead of around isolated UI widgets.

### Current problems

1. Canvas selection and data-tab selection are not synchronized.
2. Bottom action buttons only react reliably to table-originated selection.
3. Pan/zoom changes the viewport, but overlay behavior does not fully track that transformed view.
4. The dedicated Delete tool mode is unreliable.
5. Several context-menu actions exist conceptually, but are not wired consistently.
6. The old `Edit Selected` button is obsolete and should be removed.

### Primary goal

Make selection a first-class, box-centric capability that works consistently across:

- canvas
- data tab
- context menu
- keyboard shortcuts
- bottom action row

### Must-have behavior

#### 1. Shared selection

- Selecting a box on the canvas must select the corresponding row in the active data tab.
- Selecting a row in the data tab must select the corresponding box on the canvas.
- Deselecting from either surface must update the other surface immediately.
- Selection must survive routine frame re-renders by box key, not by row index.

#### 2. View-only pan/zoom

- Pan and zoom must affect how boxes are viewed and interacted with on the canvas.
- Pan and zoom must **not** mutate the stored box data.
- Hit-testing, highlighting, drag handles, and future marquee selection must all respect the transformed viewport.

#### 3. Multi-selection

- Ctrl+click on canvas should toggle a box in the current selection.
- Clicking empty canvas space should clear selection.
- Shift+drag should create a marquee rectangle for additive multi-selection.
- Multi-selection must stay synchronized with the data tab.

#### 4. Action enablement

The bottom action row must enable or disable actions from the **shared selection state**, regardless of whether selection started on the table or the canvas.

#### 5. Delete behavior

- The broken Delete tool mode should be removed or retired.
- Deletion should happen through selection-driven actions instead:
  - `Delete` key
  - context menu
  - existing delete button

#### 6. Context menu wiring

Right-click actions should operate on the box or boxes represented by the current shared selection model.

At minimum, the context menu should support:

- Delete selected
- Duplicate to next frame
- Duplicate to previous frame
- Delete next occurrences (tracking only)
- Delete previous occurrences (tracking only)
- Select all
- Deselect all
- Invert selection
- Relabel selected

#### 7. Relabel selected boxes

This is now a core requirement.

- User selects one or more boxes.
- User triggers **Relabel Selected** from context menu or a button.
- User enters one replacement label.
- All selected boxes receive that label.
- This should work in **both Detection and Tracking** tabs.

The relabel flow should be batch-oriented and selection-aware, not tied to the removed `Edit Selected` button.

### UI decisions

- Remove `self.edit_item_btn` from the bottom panel.
- Keep edit capability through direct manipulation and/or context-driven single-item edit flows.
- Prefer a new selection-aware relabel action over reviving the old edit button.

### Keyboard shortcuts

First-wave shortcuts:

- `Delete` — delete selected boxes
- `Ctrl + A` — select all
- `Ctrl + D` — deselect all
- `Ctrl + I` — invert selection

Possible later shortcuts:

- `Ctrl + Z` — undo
- `Ctrl + Y` — redo
- `Ctrl + C` — copy selected boxes
- `Ctrl + V` — paste copied boxes

Reset shortcuts can remain separate and are lower priority than getting core selection right.

### Explicit de-prioritized items

These are valuable, but should not block the core selection feature:

- Undo / redo
- Clipboard copy / paste
- Add-mode label chosen once before repeated box drawing

### Current implementation status

As of 2026-08-11, the refactor has moved beyond the initial seam and now covers the core box-selection experience:

- Shared selection state is the authoritative source for canvas/table sync.
- Select-all, deselect-all, and invert-selection are wired through the shared model.
- The data table supports standard multi-select behavior.
- The canvas supports marquee selection and group dragging for the current selection.
- The overlay visually highlights the shared selection so table and canvas stay visually aligned.

The remaining work is mostly around making batch actions (delete, duplicate, relabel) fully consistent across the canvas, table, bottom action row, and context menu.

### Developer notes

- Code changes should be documented well enough that future work on selection and annotation actions remains understandable.
- The implementation should be phased because selection, transform handling, and action routing are tightly coupled and likely to churn during development.
- Planning artifacts for this refactor live under `my-handcrafted-prompts/select_feature/`, with one phase file per phase under `my-handcrafted-prompts/select_feature/plan_phases/`.
