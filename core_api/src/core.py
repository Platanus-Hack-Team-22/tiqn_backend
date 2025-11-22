"""
Core emergency call processing function.

This module provides the main function that your team member's API should call.
It handles the complete workflow: transcription → extraction → session management.
"""

import time
from typing import TypedDict

from .config import settings
from .schemas import CanonicalV2, StreamResponse
from .services.canonical import extract_with_claude
from .services.session import session_manager
from .services.transcription import transcribe_audio_chunk_whisper


class ProcessChunkResult(TypedDict, total=False):
    """Result from processing an audio chunk."""
    
    chunk_text: str
    full_transcript: str
    canonical: dict  # CanonicalV2 as dict
    timestamp: float
    session_info: dict
    convex_update: dict  # Optional: Result of real-time Convex update


async def process_audio_chunk(
    audio_chunk: bytes,
    session_id: str,
    dispatcher_id: str | None = None,
    update_convex: bool = True,
) -> ProcessChunkResult:
    """
    Main function to process an audio chunk from an emergency call.
    
    This function should be called by your WebSocket API for each audio chunk received.
    It handles the complete workflow:
    1. Transcribe audio → text
    2. Extract structured emergency data using Claude
    3. Update session state
    4. Update Convex database in real-time (if dispatcher_id provided)
    5. Return updated data
    
    Args:
        audio_chunk: Raw audio bytes (WebM format recommended)
        session_id: Unique identifier for this call session
        dispatcher_id: Convex ID of dispatcher (required for real-time Convex updates)
        update_convex: Whether to update Convex database in real-time (default: True)
    
    Returns:
        ProcessChunkResult with:
        - chunk_text: Transcribed text from this chunk
        - full_transcript: Complete transcript so far
        - canonical: Structured emergency data (31 fields)
        - timestamp: Unix timestamp
        - session_info: Session metadata (duration, chunk count)
        - convex_update: Result of Convex update (if enabled)
    
    Raises:
        ValueError: If transcription or extraction fails
        
    Example:
        ```python
        # In your WebSocket endpoint:
        from core_api.src.core import process_audio_chunk
        
        @websocket_route("/emergency/{call_id}")
        async def handle_call(websocket, call_id: str, dispatcher_id: str):
            while True:
                audio_data = await websocket.receive_bytes()
                
                result = await process_audio_chunk(
                    audio_chunk=audio_data,
                    session_id=call_id,
                    dispatcher_id=dispatcher_id,  # Real-time Convex updates!
                    update_convex=True
                )
                
                # Send structured data back to operator
                await websocket.send_json(result)
        ```
    """
    
    # Get or create session for this call
    session = session_manager.get_or_create_session(session_id)
    
    # Step 1: Transcribe audio chunk to text
    chunk_text = await transcribe_audio_chunk_whisper(audio_chunk)
    
    if not chunk_text:
        # Return current state if transcription produced no text
        return {
            "chunk_text": "",
            "full_transcript": session.full_transcript,
            "canonical": session.canonical_data.model_dump(),
            "timestamp": time.time(),
            "session_info": {
                "session_id": session_id,
                "duration_seconds": session.get_duration(),
                "chunk_count": session.chunk_count,
            },
        }
    
    # Step 2: Add to session transcript
    session.add_transcript_chunk(chunk_text)
    
    # Step 3: Extract/update canonical data using Claude AI
    updated_canonical = await extract_with_claude(
        transcript_chunk=chunk_text,
        existing_canonical=session.canonical_data,
    )
    
    # Step 4: Update session with new canonical data
    session.update_canonical(updated_canonical)
    
    # Step 5: Update Convex in real-time (if enabled and dispatcher_id provided)
    convex_update_result = None
    if update_convex and settings.CONVEX_URL and dispatcher_id:
        try:
            from .services.convex_db import get_convex_service
            
            convex = get_convex_service()
            convex_update_result = convex.update_incident_realtime(
                session_id=session_id,
                canonical_data=updated_canonical,
                full_transcript=session.full_transcript,
                dispatcher_id=dispatcher_id,
            )
        except Exception as e:
            print(f"Warning: Could not update Convex in real-time: {e}")
            convex_update_result = {"success": False, "error": str(e)}
    
    # Step 6: Build and return result
    result: ProcessChunkResult = {
        "chunk_text": chunk_text,
        "full_transcript": session.full_transcript,
        "canonical": updated_canonical.model_dump(),
        "timestamp": time.time(),
        "session_info": {
            "session_id": session_id,
            "duration_seconds": session.get_duration(),
            "chunk_count": session.chunk_count,
        },
    }
    
    # Include Convex update status if it was attempted
    if convex_update_result is not None:
        result["convex_update"] = convex_update_result
    
    return result


async def get_session_data(session_id: str) -> dict | None:
    """
    Get current data for an active session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Session data dict or None if session not found
    """
    session = session_manager.get_session(session_id)
    
    if not session:
        return None
    
    return {
        "session_id": session_id,
        "full_transcript": session.full_transcript,
        "canonical": session.canonical_data.model_dump(),
        "duration_seconds": session.get_duration(),
        "chunk_count": session.chunk_count,
        "created_at": session.created_at,
        "last_updated": session.last_updated,
    }


def end_session(
    session_id: str,
    save_to_convex: bool = True,
    dispatcher_id: str | None = None,
) -> dict | None:
    """
    End a call session and return final data.
    
    Args:
        session_id: Session identifier
        save_to_convex: Whether to save the final call data to Convex (default: True)
        dispatcher_id: Convex ID of the dispatcher handling this call (required for Convex save)
        
    Returns:
        Final session data or None if session not found
    """
    session = session_manager.remove_session(session_id)
    
    if not session:
        return None
    
    final_data = {
        "session_id": session_id,
        "full_transcript": session.full_transcript,
        "canonical": session.canonical_data.model_dump(),
        "duration_seconds": session.get_duration(),
        "chunk_count": session.chunk_count,
    }
    
    # Save to Convex if enabled and configured
    if save_to_convex and settings.CONVEX_URL:
        if not dispatcher_id:
            print("Warning: dispatcher_id required for Convex save. Skipping database save.")
            final_data["convex_save"] = {
                "success": False,
                "error": "dispatcher_id required"
            }
        else:
            try:
                from .services.convex_db import get_convex_service
                
                convex = get_convex_service()
                save_result = convex.save_emergency_call(
                    session_id=session_id,
                    full_transcript=session.full_transcript,
                    canonical_data=session.canonical_data,
                    duration_seconds=session.get_duration(),
                    chunk_count=session.chunk_count,
                    dispatcher_id=dispatcher_id,
                )
                final_data["convex_save"] = save_result
            except Exception as e:
                print(f"Warning: Could not save to Convex: {e}")
                final_data["convex_save"] = {"success": False, "error": str(e)}
    
    return final_data


def cleanup_old_sessions(max_age_seconds: float = 3600) -> int:
    """
    Remove sessions that haven't been updated recently.
    
    Args:
        max_age_seconds: Maximum age in seconds (default: 1 hour)
        
    Returns:
        Number of sessions removed
    """
    return session_manager.cleanup_old_sessions(max_age_seconds)

