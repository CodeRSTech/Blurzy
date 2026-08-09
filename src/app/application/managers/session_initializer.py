"""Session runtime bootstrapper.

This helper keeps ``Session`` construction side-effect free by moving the
expensive runtime setup out of ``Session.__init__`` and into the application
layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from app.domain.session import SessionState
from app.infrastructure.video.decode_worker import VideoDecodeWorker
from app.infrastructure.video.reader import VideoReader
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.infrastructure.session.session import Session

logger = get_logger("Application->SessionInitializer")


@final
class SessionInitializer:
    """Build and attach the runtime collaborators for a ``Session``.

    Responsibilities:
        - Open the video reader for the session path.
        - Build ``SessionState`` from the reader metadata.
        - Create and start the session's decode worker.

    The initializer intentionally keeps object construction separate from
    lifetime management so tests can instantiate ``Session`` without opening
    files or starting threads.
    """

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    def initialize(self, session: Session) -> Session:
        """Attach the video reader, runtime view_state, and decode worker.

        Args:
            session: The bare ``Session`` shell created by ``SessionManager``.

        Returns:
            The same session instance after its runtime collaborators have been
            attached.
        """
        logger.debug("Initializing runtime collaborators for session {}", session.s_id)

        video_reader = VideoReader(session.s_id.path)
        session.video_reader = video_reader
        session.state = SessionState(session.s_id, video_reader.metadata)

        decode_worker = VideoDecodeWorker(
            session.s_id.path,
            session.state.playback,
            parent=session,
        )
        decode_worker.start()
        session.video_decode_worker = decode_worker

        logger.debug("Session {} runtime collaborators initialized", session.s_id)
        return session

