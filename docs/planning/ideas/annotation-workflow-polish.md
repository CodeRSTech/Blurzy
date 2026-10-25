# Annotation Workflow Polish

!!! info "Current status"

    Canvas/table selection, annotation actions, and multi-selection are already
    implemented. This proposal is now about validating consistency and edge
    cases; track-specific occurrence deletion remains a known issue.

## What is an Annotation

An annotation is a box drawn around an object in a video frame, with a label, confidence score, or other metadata that describes what the object is. Annotations are used to train and evaluate machine learning models for object detection and tracking.

## What this is

A complete and reliable box-editing workflow where selection, deletion, relabeling, and batch actions behave the same way everywhere in the UI.

This includes:

The table records areas for continued workflow review. The application already
provides canvas/table selection and annotation actions; the entries identify
consistency and edge-case validation rather than implying those workflows are
entirely absent. See [UI handlers](../../architecture/ui/handlers.md) and
[preview widgets](../../architecture/ui/qt/widgets/preview.md) for current
interaction boundaries.

| Area                     | Goal                                                               | Progress so far                                     | Key issues so far                                                                                |
|--------------------------|--------------------------------------------------------------------|-----------------------------------------------------|--------------------------------------------------------------------------------------------------|
| Canvas and table sync    | Keep selections and edits consistent between the canvas and table. | Selection and table handlers are implemented; verify cross-layer edge cases. | Confirm behavior when switching between detection and tracking tabs. |
| Selection-driven actions | Make actions behave consistently based on the current selection.   | Selection state and actions are implemented.         | Validate mixed and stale selections. |
| Context menu actions     | Ensure context menu actions perform the expected operation.        | Context-menu actions are implemented.                | Continue regression testing. |
| Delete and relabel       | Make deletion and relabeling predictable.                          | Delete and relabel flows are implemented.            | Track-specific occurrence deletion remains a known edge case. |
| Batch operations         | Make batch actions safe and obvious.                               | Multi-selection actions are available.               | Validate behavior on empty and mixed selections. |

## Why this is a must

Annotation is the heart of this app. If the user cannot confidently select, change, and manage boxes, the rest of the pipeline becomes less valuable.

Even strong detection and tracking do not fully help if the last-mile correction workflow feels fragile.

## Simple example

Suppose a user selects 6 wrong boxes on the canvas. They should be able to:

1. see those same 6 rows highlighted in the table
2. right-click once
3. relabel or delete the whole group

If any part of that flow is inconsistent, the task becomes slow and error-prone.

## Why it matters for Blurzy

Reliable selection and editing are central to the annotation workflow, so this is a useful area for future product work.
