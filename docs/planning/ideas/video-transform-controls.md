# Video Transform Controls

!!! info "Current status"

    Video rotation is implemented: the reader applies source metadata rotation
    and user-requested rotation from the transport controls. Further fit-to-screen,
    zoom/pan, and view-state polish remain possible product improvements. See
    [video infrastructure](../../architecture/infrastructure/video.md) and the
    [UI handlers](../../architecture/ui/handlers.md).

## What this is

Reliable controls for how the user views the video, especially when the source media is rotated or awkward to inspect.

This area can include:

- rotate clockwise / counter-clockwise
- fit-to-screen behavior
- zoom and pan polish
- clear visual feedback about current view state

## Why this is a must

Good annotation depends on good viewing. If a user cannot quickly orient the video the right way, every downstream action becomes harder.

A missing or placeholder transform flow also makes the app feel unfinished, even when the detection pipeline works.

## Simple example

If a phone video opens sideways, the user should be able to rotate it immediately and continue working. They should not have to mentally compensate or preprocess the video elsewhere first.

## Why it matters for Blurzy

The existing controls address rotation, while reliable fit, zoom, and pan
behavior still merits evaluation against common annotation workflows.
