"""Session management for ongoing emergency calls."""

import hashlib
import json
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

        # Optimization tracking fields
        self.last_extraction_time: float = 0
        self.last_extraction_length: int = 0
        self.last_convex_update_time: float = 0
        self.last_convex_canonical_hash: str = ""

        # Interim transcript tracking
        self.live_transcript: str = ""  # Current interim + finalized text
        self.last_interim_text: str = ""  # Last interim result received
        self.last_interim_update_time: float = 0
    
    def add_transcript_chunk(self, chunk: str) -> None:
        """Add a new transcript chunk (final result)."""
        if chunk:
            self.full_transcript += " " + chunk if self.full_transcript else chunk
            self.last_updated = time.time()
            self.chunk_count += 1
            # Update live transcript to match (interim is now finalized)
            self.live_transcript = self.full_transcript
            self.last_interim_text = ""  # Clear interim since it's now final

    def update_interim_transcript(self, interim_text: str) -> bool:
        """
        Update the live transcript with interim result.

        Returns:
            True if the transcript changed (should send update), False otherwise
        """
        if not interim_text:
            return False

        # Construct live transcript: finalized + current interim
        new_live = self.full_transcript
        if new_live and interim_text:
            new_live += " " + interim_text
        elif interim_text:
            new_live = interim_text

        # Check if it changed
        if new_live == self.live_transcript:
            return False

        # Update
        self.live_transcript = new_live
        self.last_interim_text = interim_text
        self.last_interim_update_time = time.time()
        self.last_updated = time.time()

        return True

    def update_canonical(self, new_data: CanonicalV2) -> None:
        """Update canonical data."""
        self.canonical_data = new_data
        self.last_updated = time.time()
    
    def get_duration(self) -> float:
        """Get session duration in seconds."""
        return time.time() - self.created_at

    def should_extract_with_claude(
        self, chunk_text: str, min_interval: float = 5.0, min_chars: int = 50
    ) -> bool:
        """
        Determine if Claude extraction should be called (debouncing logic).

        Args:
            chunk_text: The new chunk of text
            min_interval: Minimum seconds between extractions (default: 5s)
            min_chars: Minimum new characters to trigger extraction (default: 50)

        Returns:
            True if extraction should be performed
        """
        current_time = time.time()

        # Always extract on first call
        if self.last_extraction_time == 0:
            return True

        # Check for critical keywords that force immediate extraction
        critical_keywords = [
            "emergencia",
            "direccion",
            "edad",
            "inconsciente",
            "no respira",
            "paro",
        ]
        if any(kw in chunk_text.lower() for kw in critical_keywords):
            return True

        # Check time elapsed
        time_elapsed = current_time - self.last_extraction_time
        if time_elapsed < min_interval:
            return False

        # Check if enough new content accumulated
        chars_since_last = len(self.full_transcript) - self.last_extraction_length
        if chars_since_last >= min_chars:
            return True

        return False

    def should_update_convex(
        self, canonical: CanonicalV2, min_interval: float = 3.0
    ) -> bool:
        """
        Determine if Convex update should be sent (throttling logic).

        Args:
            canonical: The canonical data to potentially update
            min_interval: Minimum seconds between updates (default: 3s)

        Returns:
            True if Convex should be updated
        """
        current_time = time.time()

        # Create hash of canonical data
        canonical_hash = hashlib.md5(
            json.dumps(canonical.model_dump(), sort_keys=True).encode()
        ).hexdigest()

        # Always update on first call
        if self.last_convex_update_time == 0:
            self.last_convex_update_time = current_time
            self.last_convex_canonical_hash = canonical_hash
            return True

        # Check if data changed
        data_changed = canonical_hash != self.last_convex_canonical_hash

        # Check time elapsed
        time_elapsed = current_time - self.last_convex_update_time
        enough_time_passed = time_elapsed >= min_interval

        # Force update every 10 seconds regardless
        force_update = time_elapsed >= 10.0

        # Update if data changed AND enough time passed, OR forced
        if (data_changed and enough_time_passed) or force_update:
            self.last_convex_update_time = current_time
            self.last_convex_canonical_hash = canonical_hash
            return True

        return False


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


