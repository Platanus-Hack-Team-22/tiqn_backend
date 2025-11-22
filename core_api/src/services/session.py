"""Session management for ongoing emergency calls."""

import time
from typing import Dict

from ..schemas import CanonicalV2


class CallSession:
    """Represents an ongoing emergency call session."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.full_transcript = ""
        self.canonical_data = CanonicalV2()
        self.created_at = time.time()
        self.last_updated = time.time()
        self.chunk_count = 0
    
    def add_transcript_chunk(self, chunk: str) -> None:
        """Add a new transcript chunk."""
        if chunk:
            self.full_transcript += " " + chunk if self.full_transcript else chunk
            self.last_updated = time.time()
            self.chunk_count += 1
    
    def update_canonical(self, new_data: CanonicalV2) -> None:
        """Update canonical data."""
        self.canonical_data = new_data
        self.last_updated = time.time()
    
    def get_duration(self) -> float:
        """Get session duration in seconds."""
        return time.time() - self.created_at


class SessionManager:
    """Manages active call sessions."""
    
    def __init__(self):
        self._sessions: Dict[str, CallSession] = {}
    
    def create_session(self, session_id: str) -> CallSession:
        """Create a new call session."""
        session = CallSession(session_id)
        self._sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> CallSession | None:
        """Get an existing session."""
        return self._sessions.get(session_id)
    
    def get_or_create_session(self, session_id: str) -> CallSession:
        """Get existing session or create new one."""
        session = self.get_session(session_id)
        if session is None:
            session = self.create_session(session_id)
        return session
    
    def remove_session(self, session_id: str) -> CallSession | None:
        """Remove and return a session."""
        return self._sessions.pop(session_id, None)
    
    def cleanup_old_sessions(self, max_age_seconds: float = 3600) -> int:
        """Remove sessions older than max_age_seconds."""
        now = time.time()
        to_remove = [
            sid for sid, session in self._sessions.items()
            if now - session.last_updated > max_age_seconds
        ]
        for sid in to_remove:
            self._sessions.pop(sid, None)
        return len(to_remove)
    
    def get_active_count(self) -> int:
        """Get number of active sessions."""
        return len(self._sessions)


# Global session manager
session_manager = SessionManager()


