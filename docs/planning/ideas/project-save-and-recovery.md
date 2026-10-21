# Project Save and Recovery

!!! success "Current status"

    Project save and load are implemented through `ProjectService`, domain project
    documents, and the infrastructure `ProjectStore`. The original proposal below
    records the motivation and intended scope; consult the current application
    documentation for exact restore behavior and limitations.

## What this is

A way to save the current working state of Blurzy and reopen it later.

That saved state would usually include:

- opened videos
- current frame positions
- annotations
- tracking results
- selected model-related settings
- export choices that matter to the session

## Original motivation

When this proposal was written, the concern was that multi-step video
annotation work could not be reliably resumed after closing the application.
Video annotation work is rarely a one-shot task: people stop, review, come back
later, or hand the job to someone else.

The implemented project workflow addresses that need by saving session data
and restoring available sessions. Exact behavior for unavailable or invalid
sessions is described in [Architecture](../../architecture.md#projects-and-persistence).

## Simple example

A user labels frames for 90 minutes, closes the app, and comes back tomorrow. With project save and recovery, they reopen the project and continue exactly where they left off.

## Why it mattered for Blurzy

The original proposal recognized that detection, tracking, manual edits, and
export benefit from persistence beyond in-memory session switching. Project
save/load is now part of the implemented workflow.
