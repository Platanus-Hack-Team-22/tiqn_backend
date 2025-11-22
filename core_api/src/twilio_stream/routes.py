import base64
import json
import logging
import struct

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..core import end_session, process_audio_chunk

router = APIRouter()

logger = logging.getLogger("twilio_stream")
logging.basicConfig(level=logging.INFO)

# Constants for Audio Processing
SAMPLE_RATE = 8000
CHANNELS = 1
SAMPLE_WIDTH = 1  # 8-bit Mulaw
CHUNK_DURATION_SEC = 5  # Process every 5 seconds
CHUNK_SIZE = SAMPLE_RATE * SAMPLE_WIDTH * CHUNK_DURATION_SEC  # 40,000 bytes


def create_wav_header(data_length: int) -> bytes:
    """
    Create a WAV header for 8kHz Mu-Law Mono audio.
    """
    # RIFF Chunk
    header = b"RIFF"
    header += struct.pack("<I", 36 + data_length)  # ChunkSize
    header += b"WAVE"

    # fmt Chunk
    header += b"fmt "
    header += struct.pack("<I", 16)  # Subchunk1Size (16 for PCM/Mulaw)
    header += struct.pack("<H", 7)  # AudioFormat (7 = MULAW)
    header += struct.pack("<H", CHANNELS)  # NumChannels
    header += struct.pack("<I", SAMPLE_RATE)  # SampleRate
    header += struct.pack("<I", SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH)  # ByteRate
    header += struct.pack("<H", CHANNELS * SAMPLE_WIDTH)  # BlockAlign
    header += struct.pack("<H", 8)  # BitsPerSample (8 for Mulaw)

    # data Chunk
    header += b"data"
    header += struct.pack("<I", data_length)  # Subchunk2Size

    return header


@router.websocket("/twilio-stream")
async def twilio_stream_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    # TODO: De-hardcode this. Ideally extract from query params or session context.
    dispatcher_id = "js7crtvfa7c5ctm6j09q8n16sh7vwrtk"

    stream_sid = None
    audio_buffer = bytearray()
    frame_count = 0

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

            elif event_type == "media":
                payload = data.get("media", {}).get("payload")
                if payload:
                    chunk = base64.b64decode(payload)
                    audio_buffer.extend(chunk)
                    frame_count += 1

                    # Process if buffer exceeds chunk size
                    if len(audio_buffer) >= CHUNK_SIZE:
                        logger.info(
                            f"Processing audio chunk: {len(audio_buffer)} bytes"
                        )

                        if stream_sid:
                            # Create WAV container
                            wav_data = (
                                create_wav_header(len(audio_buffer)) + audio_buffer
                            )

                            try:
                                # Process audio chunk
                                await process_audio_chunk(
                                    audio_chunk=bytes(wav_data),
                                    session_id=stream_sid,
                                    dispatcher_id=dispatcher_id,
                                    update_convex=True,
                                    audio_content_type="audio/wav",
                                    audio_filename="audio.wav",
                                )
                            except Exception as e:
                                logger.error(f"Error processing audio chunk: {e}")

                        # Reset buffer
                        audio_buffer = bytearray()

            elif event_type == "stop":
                logger.info(
                    f"Media Stream stopped. Total frames received: {frame_count}"
                )
                # Process remaining audio if any
                if len(audio_buffer) > 0 and stream_sid:
                    logger.info(
                        f"Processing final audio chunk: {len(audio_buffer)} bytes"
                    )
                    wav_data = create_wav_header(len(audio_buffer)) + audio_buffer
                    try:
                        await process_audio_chunk(
                            audio_chunk=bytes(wav_data),
                            session_id=stream_sid,
                            dispatcher_id=dispatcher_id,
                            update_convex=True,
                            audio_content_type="audio/wav",
                            audio_filename="audio.wav",
                        )
                    except Exception as e:
                        logger.error(f"Error processing final audio chunk: {e}")

                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected. Total frames received: {frame_count}")
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}")
    finally:
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
