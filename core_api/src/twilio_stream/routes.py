import asyncio
import base64
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..core import end_session, process_text_chunk
from ..services.transcription import transcribe_audio_stream_azure

router = APIRouter()

logger = logging.getLogger("twilio_stream")
logging.basicConfig(level=logging.INFO)


@router.websocket("/twilio-stream")
async def twilio_stream_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for Twilio Media Streams.
    Uses Azure Speech SDK for real-time continuous recognition.
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    # Extract dispatcher_id from query params
    dispatcher_id = websocket.query_params.get("dispatcher_id")
    if not dispatcher_id:
        logger.warning("No dispatcher_id provided in query params. Using fallback.")
        dispatcher_id = "js7crtvfa7c5ctm6j09q8n16sh7vwrtk"

    logger.info(f"Using dispatcher_id: {dispatcher_id}")

    stream_sid = None
    frame_count = 0
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()

    async def audio_stream_generator() -> AsyncGenerator[bytes, None]:
        """Generate audio chunks from the queue for Azure Speech SDK."""
        while True:
            chunk = await audio_queue.get()
            if chunk is None:
                logger.info("Audio stream ended")
                break
            yield chunk

    async def process_transcriptions(session_id: str) -> None:
        """Process transcription results from Azure Speech SDK."""
        try:
            # Start Azure Speech recognition with streaming audio
            async for text, is_final in transcribe_audio_stream_azure(
                audio_stream=audio_stream_generator(),
                session_id=session_id,
                audio_format="mulaw",  # Twilio sends Mu-law encoded audio
            ):
                # Only process final results (ignore interim results)
                if is_final and text:
                    logger.info(f"Final transcription: {text}")
                    try:
                        # Process the transcribed text
                        await process_text_chunk(
                            chunk_text=text,
                            session_id=session_id,
                            dispatcher_id=dispatcher_id,
                            update_convex=True,
                        )
                    except Exception as e:
                        logger.error(f"Error processing transcription: {e}")
        except Exception as e:
            logger.error(f"Error in transcription processing: {e}")

    transcription_task = None

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            event_type = data.get("event")

            if event_type == "connected":
                logger.info(f"Twilio Media Stream connected: {data}")

            elif event_type == "start":
                stream_sid = data.get("start", {}).get("streamSid")
                logger.info(f"Media Stream started. Stream SID: {stream_sid}")

                # Start transcription processing in background
                if stream_sid:
                    transcription_task = asyncio.create_task(
                        process_transcriptions(stream_sid)
                    )
                    logger.info("Started Azure Speech recognition task")

            elif event_type == "media":
                payload = data.get("media", {}).get("payload")
                if payload:
                    # Decode Twilio's base64-encoded audio
                    chunk = base64.b64decode(payload)
                    # Feed directly to Azure Speech SDK (no buffering)
                    await audio_queue.put(chunk)
                    frame_count += 1

            elif event_type == "stop":
                logger.info(f"Media Stream stopped. Total frames received: {frame_count}")
                # Signal end of audio stream
                await audio_queue.put(None)
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected. Total frames received: {frame_count}")
        # Signal end of audio stream
        await audio_queue.put(None)
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}")
        await audio_queue.put(None)
    finally:
        # Wait for transcription task to complete
        if transcription_task:
            try:
                await asyncio.wait_for(transcription_task, timeout=5.0)
                logger.info("Transcription task completed")
            except asyncio.TimeoutError:
                logger.warning("Transcription task timeout, canceling")
                transcription_task.cancel()
            except Exception as e:
                logger.error(f"Error waiting for transcription task: {e}")

        # Cleanup and save session
        if stream_sid:
            logger.info(f"Ending session for Stream SID: {stream_sid}")
            try:
                end_session(
                    session_id=stream_sid,
                    save_to_convex=True,
                    dispatcher_id=dispatcher_id,
                )
            except Exception as e:
                logger.error(f"Error ending session: {e}")
