"""Domain utility functions and custom exceptions.

See Also:
    - [`new_passes_filter`][app.domain.helpers.functions.new_passes_filter] — applies detection filtering rules
    - [`EmptySetGeneratedFromKeysError`][app.domain.base.exceptions.EmptySetGeneratedFromKeysError] — reports invalid key-derived sets

Layer: Domain.
Context: Defines application concepts independently of UI and infrastructure implementations.
"""
from .functions import str_iterable_as_set_without_null_values, map_detections_to_bbox, new_passes_filter

__all__ = ['str_iterable_as_set_without_null_values', 'map_detections_to_bbox',
           'new_passes_filter',]
