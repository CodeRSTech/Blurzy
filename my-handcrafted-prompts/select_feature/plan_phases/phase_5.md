## Phase 5: Add relabel-selected capability

### Goal

Support batch relabeling for the current shared selection in both Detection and Tracking.

### Scope

- context action for relabel selected
- optional button if UI review justifies it
- single input applied to many selected boxes
- both Detection and Tracking tabs

### Candidate files

- `src/app/ui/handlers/annotation_handler.py`
- `src/app/ui/qt/widgets/preview/layer_bbox/menu.py`
- `src/app/ui/qt/dialogs/label.py`
- `src/app/ui/qt/sections/bottom_data_panel.py`
- relevant application-layer box update surfaces

### Dependencies

- depends on `phase_2.md`
- depends on `phase_4.md`

### Exit criteria

- user can relabel one or more selected boxes in Detection
- user can relabel one or more selected boxes in Tracking
- relabeling uses a batch flow, not repeated single-item editing

### Update log

```text
[Contributor]: Copilot
[Timestamp]: 2026-08-10T16:49:51.593+05:30
[Type]: planning
[Summary]:
- Created the phase file for batch relabeling.

[Decisions]:
- Relabeling is a core box action and should work in both Detection and Tracking.

[Problems]:
- None

[Next Phase Impact]:
- Phase 7 must include relabel-specific regression coverage.
```

```text
[Contributor]: Copilot
[Timestamp]: 2026-08-10T23:55:00.000+05:30
[Type]: implementation
[Summary]:
- Added a relabel-selected button to the bottom action row.
- Implemented a relabel flow that applies one new label to all currently selected boxes.
- Relabeling works in the currently active Detection or Tracking tab.

[Decisions]:
- Relabeling reuses the existing LabelDialog and is applied as a batch operation to the current shared selection.
- The relabel flow is not tied to the old single-box edit button anymore.

[Problems]:
- None major; relabeling now uses the shared selection model.

[Next Phase Impact]:
- Phase 7 should add regression coverage for the relabel selected flow.
```
