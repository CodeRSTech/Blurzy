# Tracking interfaces

Source: `src/app/application/interfaces/tracking/`

The tracking factory creates the background worker for a selected strategy;
the worker contract starts or stops that run, reports whether it is active,
and provides tracked results keyed by frame. Application services own the
workflow around this contract, including session validation and moving
completed results into session layers.

The implementation and strategy behavior are described in
[tracking infrastructure](../../infrastructure/tracking.md), with its
orchestration in [Tracking services](../services/tracking.md).
