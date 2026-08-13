# Annotation Workflow Polish

## What this is

A complete and reliable box-editing workflow where selection, deletion, relabeling, and batch actions behave the same way everywhere in the UI.

This includes:

- canvas and table staying in sync
- selection-driven actions working consistently
- context menu actions doing real work
- delete and relabel behaving predictably
- batch operations feeling safe and obvious

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

Your handcrafted selection notes already show this area as a major product seam. That makes it a must-finish component, not just a nice extra.
