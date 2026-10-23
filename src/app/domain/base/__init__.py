"""
Package for base; defines application concepts without UI or infrastructure dependencies.

See Also:
    - [`ProcessingSettingsKwargs`][app.domain.base.dtypes.ProcessingSettingsKwargs] — typed settings update shape
    - [`EmptySetGeneratedFromKeysError`][app.domain.base.exceptions.EmptySetGeneratedFromKeysError] — domain validation error

Layer: Domain.
Context: Defines application concepts without ui or infrastructure dependencies at this architectural boundary.
"""

from .dtypes import BBoxXYXYTuple, ListOfBoxes, ListOfBoxesByFrameIndexAsDict, RenderFunction, StopPlaybackFunction, \
    ProcessingSettingsKwargs
from .exceptions import EmptySetGeneratedFromKeysError

__all__ = ['BBoxXYXYTuple',
           'ListOfBoxes',
           'ListOfBoxesByFrameIndexAsDict',
           'RenderFunction',
           'StopPlaybackFunction',
           'ProcessingSettingsKwargs',
           'EmptySetGeneratedFromKeysError']
