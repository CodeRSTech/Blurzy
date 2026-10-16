# Annotation Workflow Polish

## What is an Annotation

An annotation is a box drawn around an object in a video frame, with a label, confidence score, or other metadata that describes what the object is. Annotations are used to train and evaluate machine learning models for object detection and tracking.

## What this is

A complete and reliable box-editing workflow where selection, deletion, relabeling, and batch actions behave the same way everywhere in the UI.

This includes:

Replace the bullet list with this table. The current content doesn’t document implementation progress, so the progress and issue columns are marked as not yet documented or to be validated.

| Area                     | Goal                                                               | Progress so far                                     | Key issues so far                                                                                |
|--------------------------|--------------------------------------------------------------------|-----------------------------------------------------|--------------------------------------------------------------------------------------------------|
| Canvas and table sync    | Keep selections and edits consistent between the canvas and table. | Not documented                                      | Neither the canvas nor the tab (detection/tracking) reflects changes when switching across tabs. |
| Selection-driven actions | Make actions behave consistently based on the current selection.   | Not documented                                      | N/A                                                                                              |
| Context menu actions     | Ensure context menu actions perform the expected operation.        | Nearly all perform as expected, needs verification. | N/A                                                                                              |
| Delete and relabel       | Make deletion and relabeling predictable.                          | Not documented                                      | Will require further assessment for feasibility analysis                                         |
| Batch operations         | Make batch actions safe and obvious.                               | Not documented                                      | N/A                                                                                              |

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
