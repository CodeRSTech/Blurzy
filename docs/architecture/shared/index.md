# Shared utilities

Source: `src/app/shared`

Shared code provides cross-cutting support used by multiple layers: logging
and startup configuration, shared exceptions, image/frame helpers, box
serialization, masked blur primitives, and distribution/resource utilities.
These helpers support the application but do not own session workflows or
domain policy.

Keep additions small, stable, and broadly reusable. Session and workflow
decisions belong in [Application](../application/index.md), core types and
rules in [Domain](../domain/index.md), and widget-specific helpers in
[UI](../ui/index.md). For example, shared masked-blur primitives are consumed
by both preview and export code, while annotation import/export orchestration
remains in [Application services](../application/services/index.md).

