"""Session infrastructure — Session container, thread-safe data store.

Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""
from .session_data_store import SessionDataStore
from .session import Session
from .frame_access import SessionFrameAccessor

__all__ = ['Session', 'SessionDataStore', 'SessionFrameAccessor']
