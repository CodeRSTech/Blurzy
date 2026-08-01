"""Window contracts are intentionally deferred for now.

``MainWindow`` is a concrete UI-layer collaborator, not a cross-layer boundary.
Until there is a second window implementation or a stable testing seam that
benefits from a protocol, handlers can depend on the concrete window directly.
"""

