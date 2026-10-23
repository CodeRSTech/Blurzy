"""
DEFENSIVE GUARDS: Layer Type Coercion

Problem Traced
==============

VideoDataLayer is a str-based enum with lowercase values ("a", "b", "c", "d"):
    class VideoDataLayer(str, Enum):
        A = "a"
        B = "b"
        C = "c"
        D = "d"

When VideoDataLayer enums pass through Qt's signal/slot system or configuration
objects, they may be coerced to plain Python strings. This caused:
    AttributeError: 'str' object has no attribute 'name'

when the handler tried to format status messages using cfg.layer.name.


Solution: Multi-Layer Defensive Guards
=======================================

1. NEW: _layer_coercion.py
   ├─ ensure_layer_enum(layer: VideoDataLayer | str) -> VideoDataLayer
   └─ Accepts both enums and strings; coerces back to enum
      • Tries lowercase string (e.g., "a" → VideoDataLayer.A)
      • Tries name matching case-insensitive (e.g., "A", "LAYER_A")
      • Raises ValueError if unable to coerce

2. Service Methods Updated (all accept str | enum):
   ├─ DetectionExportService.export_layer()
   ├─ DetectionImportService.import_layer()
   ├─ TrackingExportService.export_layer()
   └─ TrackingImportService.import_layer()
   
   Each now:
   ├─ Coerces layer parameter at entry: layer = ensure_layer_enum(layer)
   ├─ Logs the enum safely using f"{layer}" (works with str-enum)
   └─ Uses layer.value for serialization (lowercase, immutable)

3. Application Facade Updated:
   ├─ Application.import_layer(layer: VideoDataLayer | str)
   ├─ Application.export_layer(layer: VideoDataLayer | str)
   └─ Both coerce at entry before dispatching to services

4. Handler Updated:
   ├─ ImportExportHandler._do_import() coerces cfg.layer before using .name
   └─ ImportExportHandler._do_export() coerces cfg.layer before using .name


Why This Works
==============

✓ Dialog passes cfg.layer as VideoDataLayer enum (or accidentally as string)
✓ Handler immediately coerces to enum before accessing .name
✓ Application coerces again for safety
✓ Each service coerces at entry point
✓ String-enum __str__() method allows logging either form safely
✓ layer.value is always safe (immutable, lowercase)


Logging Pattern
===============

Before fix (WRONG):
    try:
        total = _write_file(layer.value, data, file_path)
    except AttributeError:
        if isinstance(layer, str):
            logger.warning("detected string layer: '{}'", layer)
            total = _write_file(layer, data, file_path)

After fix (RIGHT):
    layer = ensure_layer_enum(layer)  # Fail-fast at entry
    total = _write_file(layer.value, data, file_path)
    logger.info("exported from layer '{}'", layer)  # str-enum works in f-strings


Testing Guidance
================

Scenarios to verify:
    1. Export detection layer via UI button → check enum coercion
    2. Import detection layer via file picker → check cfg.layer type
    3. Cross-layer import (A→C, B→D) → ensure coercion at each boundary
    4. Log messages show layer names correctly (A, B, C, D)
    5. No AttributeError on .name access in status messages

Debug tip: Search logs for "Coerced" if you add logging to ensure_layer_enum()
"""

