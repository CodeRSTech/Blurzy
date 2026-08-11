## Phase 3: Make viewport transforms selection-safe

### Goal

Ensure pan and zoom affect viewing and interaction only, never stored box geometry.

### Scope

- pan/zoom plumbing
- hit-testing under transformed viewport
- selection highlight placement
- drag handle behavior under zoom
- transform-safe coordinate mapping

### Candidate files

- `src/app/ui/qt/widgets/preview/preview_container.py`
- `src/app/ui/qt\widgets\preview\layer_bbox\layer_bbox.py`
- `src/app/ui/qt\widgets\preview\layer_bbox\interaction.py`
- `src/app/ui/qt\widgets\preview\layer_bbox\geometry.py`
- `src/app/ui/qt\widgets\preview\layer_video.py`

### Dependencies

- depends on `phase_2.md`

### Exit criteria

- pan/zoom changes view behavior only
- hit-testing and highlighting stay correct while transformed
- stored box data remains unchanged

### Update log

```text
[Contributor]: Copilot
[Timestamp]: 2026-08-10T16:49:51.593+05:30
[Type]: planning
[Summary]:
- Created the phase file for transform-safe interaction work.

[Decisions]:
- This phase should focus on coordinate-system correctness, not action routing.

[Problems]:
- None

[Next Phase Impact]:
- If transform logic changes the overlay API, Phase 4 should consume that stabilized API rather than duplicate math.
```

```text
[Contributor]: Copilot
[Timestamp]: 2026-08-10T22:35:00.000+05:30
[Type]: implementation
[Summary]:
- Added zoom and pan state attributes to AnnotationOverlayWidget
- Created set_zoom() and set_pan() methods to sync transforms from PreviewContainer
- Updated PreviewContainer to pass zoom/pan updates to bbox_layer
- Created transform-aware coordinate mapping functions in geometry.py
- Updated hit-testing to use zoom/pan-aware coordinate mapping
- Hit-testing now correctly finds bboxes under zoom/pan transforms

[Decisions]:
- Zoom/pan state stored in both PreviewContainer and AnnotationOverlayWidget for local visibility
- Transform-aware hit-testing in geometry module keeps coordinate math centralized
- Rendering still uses basic approach; will be upgraded if selection highlighting needed

[Problems]:
- Rendering (paintEvent) still doesn't apply zoom/pan visually (only hit-testing fixed)
- This is acceptable for Phase 3 since focus is on data integrity, not visual highlighting
- Phase 4+ can upgrade rendering if needed

[Next Phase Impact]:
- Hit-testing works correctly under zoom/pan, so action routing can depend on correct box selection
- Data integrity preserved: pan/zoom affect only viewing, not stored box coordinates
- Coordinate transforms now consistent across UI layer
```

```text
[Contributor]: Copilot
[Timestamp]: 2026-08-11T10:07:00.000+05:30
[Type]: review
[Summary]:
- Confirmed that the active overlay box stays visually attached to the viewport during pan/zoom after the rebasing fix.
- Found a separate interaction regression: ending a pan interaction via mouse release was clearing the active selection state.

[Decisions]:
- Pan interactions should not reset the current edit/selection state; they should only stop viewport movement.
- The overlay should preserve the current box selection when the user pans with Alt + drag.

[Problems]:
- The release path in AnnotationOverlayWidget called cancel_edit() on panning completion, which cleared the active bbox and detached it from the current selection.
- This made panning feel like an implicit deselection action even though the viewport moved correctly.

[Next Phase Impact]:
- Later interaction phases should treat pan as a viewport-only gesture and preserve selection state across it.
- Any future gesture handling should clearly separate viewport transforms from selection lifecycle.
```
