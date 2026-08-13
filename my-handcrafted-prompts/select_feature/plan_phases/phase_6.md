## Phase 6: Add multi-select ergonomics

### Goal

Add user-friendly multi-selection gestures once shared selection and action routing are stable.

### Scope

- Ctrl+click toggle selection
- click-empty-space clear selection
- Shift+drag marquee additive selection

### Candidate files

- `src/app/ui/qt/widgets/preview/layer_bbox/layer_bbox.py`
- `src/app/ui/qt/widgets/preview/layer_bbox/interaction.py`
- `src/app/ui/qt/widgets/preview/layer_bbox/rendering.py`
- `src/app/ui/qt/sections/bottom_data_panel.py`

### Dependencies

- depends on `phase_2.md`
- should follow `phase_3.md` and `phase_4.md`

### Exit criteria

- additive canvas selection works
- empty-space clear works
- marquee selection works and stays synchronized with the table

### Update log

```text
[Contributor]: Copilot
[Timestamp]: 2026-08-10T16:49:51.593+05:30
[Type]: planning
[Summary]:
- Created the phase file for multi-select ergonomics.

[Decisions]:
- Marquee selection should wait until transform-safe viewport behavior is understood.

[Problems]:
- None

[Next Phase Impact]:
- Phase 7 should validate marquee and toggle selection behavior.
```

```text
[Contributor]: Copilot
[Timestamp]: 2026-08-11T11:20:00.000+05:30
[Type]: implementation
[Summary]:
- Added standard multi-select behavior for the data table.
- Added canvas marquee selection and group-drag behavior for the current selection.
- Preserved existing selection during context-menu and drag interactions.

[Decisions]:
- The selection model remains the source of truth; the overlay and table simply mirror it.

[Problems]:
- The initial implementation still needs a final pass for action consistency across delete/duplicate/relabel.

[Next Phase Impact]:
- Remaining work should focus on batch actions and regression tests.
```
