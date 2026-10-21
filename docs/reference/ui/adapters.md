# UI adapters

Source: `src/app/ui/adapters/`

`UIApplicationAdapter` wraps the concrete Application facade for UI handlers,
and `UIControllerAdapter` provides a narrow controller-facing facade. These
adapters keep handlers working through UI-owned contracts rather than reaching
into the implementation. The older adapter module is a compatibility shim;
there is not currently a concrete main-window adapter.

The contracts are described in [UI interfaces](interfaces.md), and the
controller/handler composition is summarized in [UI](index.md). Application
contracts and their runtime bindings are documented in
[Application adapters](../application/adapters.md).
