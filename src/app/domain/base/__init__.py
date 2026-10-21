"""Package for base; defines application concepts without UI or infrastructure dependencies.

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
