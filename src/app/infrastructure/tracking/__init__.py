"""Multi-object tracking infrastructure — tracker strategies and background worker.

See Also:
    - [`TrackingWorker`][app.infrastructure.tracking.track_worker.TrackingWorker] — dispatches frames to tracker strategies
    - [`TrackingService`][app.application.services.tracking.service.TrackingService] — coordinates tracking use cases

Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""

from app.infrastructure.tracking.bytetrack_strategy import ByteTrackStrategy
from app.infrastructure.tracking.botsort_strategy import BotSortStrategy
from app.infrastructure.tracking.deepsort_strategy import DeepSortStrategy
from app.infrastructure.tracking.reid_extractor import (
    PartBasedAppearanceEmbedder,
    ReIDExtractorProtocol,
    cosine_distance,
    cosine_similarity,
    update_ema_embedding,
)
from app.infrastructure.tracking.track_worker import TrackingWorker

__all__ = [
    "TrackingWorker",
    "ByteTrackStrategy",
    "BotSortStrategy",
    "DeepSortStrategy",
    "PartBasedAppearanceEmbedder",
    "ReIDExtractorProtocol",
    "cosine_distance",
    "cosine_similarity",
    "update_ema_embedding",
]
