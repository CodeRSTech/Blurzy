# Project Save and Recovery

## What this is

A way to save the current working state of Blurzy and reopen it later.

That saved state would usually include:

- opened videos
- current frame positions
- annotations
- tracking results
- selected model-related settings
- export choices that matter to the session

## Why this is a must

Video annotation work is rarely a one-shot task. People stop, review, come back later, or hand the job to someone else.

If the app cannot save and restore progress cleanly, users risk losing time and repeating work. That is one of the fastest ways to make a useful tool feel unsafe.

## Simple example

A user labels frames for 90 minutes, closes the app, and comes back tomorrow. With project save and recovery, they reopen the project and continue exactly where they left off.

## Why it matters for Blurzy

Blurzy already supports complex multi-step work: detection, tracking, manual edits, and export. That level of workflow benefits heavily from persistence, not just in-memory session switching.
