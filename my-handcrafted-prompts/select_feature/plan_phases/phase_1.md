## Phase 1: Establish the selection seam

### Goal

Define one authoritative selection state keyed by box key and identify every place that currently creates, consumes, or assumes selection.

### Scope

- active session + active tab selection ownership
- table selection producers
- canvas selection producers
- action enablement consumers
- render refresh consumers
- context menu and keyboard consumers

### Candidate files

- `src/app/ui/qt/sections/bottom_data_panel.py`
- `src/app/ui/qt/window/window.py`
- `src/app/ui/uicontroller.py`
- `src/app/ui/handlers/annotation_handler.py`
- `src/app/ui/qt/widgets/preview/preview_container.py`
- `src/app/ui/qt/widgets/preview/layer_bbox/layer_bbox.py`
- `src/app/ui/view_state/table_key_filter.py`

### Exit criteria

- a single selection seam is chosen
- current producers and consumers are mapped
- phase 2 can implement synchronization without re-deciding selection ownership

### Update log

```text
[Contributor]: Copilot
[Timestamp]: 2026-08-10T16:49:51.593+05:30
[Type]: planning
[Summary]:
- Created the phase file and defined the selection-seam objective.

[Decisions]:
- Selection should be keyed by box key and scoped to active session plus active tab.

[Problems]:
- None

[Next Phase Impact]:
- Phase 2 should treat this file as the source of truth for selection ownership.
```

```text
[Contributor]: Copilot
[Timestamp]: 2026-08-10T22:24:00.237+05:30
[Type]: implementation
[Summary]:
- Completed Phase 1 investigation of current selection architecture.
- Analyzed all producers and consumers of selection state.
- Documented findings in phase_1_findings.md.
- Proposed BBoxSelectionState as the unified selection seam.

[Decisions]:
- Selection seam: new BBoxSelectionState class in src/app/ui/view_state/bbox_selection_state.py
- Scoped by (session_id, tab_index) pair.
- Exposed via Window property for access by all consumers.
- Table selection, canvas clicks, context menu, keyboard all update shared state.

[Problems]:
- None; architecture is clear and straightforward.

[Next Phase Impact]:
- Phase 2 can now implement synchronization by wiring table/canvas producers to BBoxSelectionState
- Phase 2 should update action enablement consumers to read from shared state
- Phase 2 should update canvas overlay rendering to highlight selected boxes from shared state
```
