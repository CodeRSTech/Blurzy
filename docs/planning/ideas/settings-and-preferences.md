# Settings and Preferences

!!! info "Current status"

    Blurzy has a Preferences dialog and session-level processing settings.
    The ideas below describe possible improvements and additional defaults, not
    the absence of a settings UI. See the
    [Qt dialog notes](../../architecture/ui/qt/dialogs.md) and
    [processing settings](../../architecture/domain/export.md) for current
    presentation and configuration details.

## What this is

A dedicated settings area where users can control app-wide behavior instead of re-tuning the app every time they open it.

Typical settings here would include:

- default detection model
- preferred provider or model family
- GPU on/off
- logging level
- export defaults
- UI defaults such as fullscreen on launch

## Original motivation

This proposal began from the need for a dedicated settings area, rather than
repeating configuration each time the app opens. Blurzy now has a Preferences
dialog and session-level processing settings.

The remaining opportunity is to evaluate which additional values should be
persisted as app-wide defaults and how they should interact with per-session
settings.

## Simple example

If a reviewer opens 20 videos every day and always uses the same model and export folder, a settings window saves them from repeating the same setup 20 times.

## Why it matters for Blurzy

Preferences and session settings support repeatable workflows; this proposal
captures potential additions and refinements, not a missing settings window.
