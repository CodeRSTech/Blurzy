# Video Transform Controls

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

The transport controls already expose rotation buttons, but the current implementation is still placeholder-only. That makes this a visible gap in the user experience.
