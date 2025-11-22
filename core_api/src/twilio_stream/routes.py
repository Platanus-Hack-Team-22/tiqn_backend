import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

logger = logging.getLogger("twilio_stream")
logging.basicConfig(level=logging.INFO)


@router.websocket("/twilio-stream")
async def twilio_stream_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection accepted")

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
                frame_count += 1
                if frame_count % 100 == 0:
                    logger.info(f"Received {frame_count} audio frames")

            elif event_type == "stop":
                logger.info(
                    f"Media Stream stopped. Total frames received: {frame_count}"
                )
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected. Total frames received: {frame_count}")
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {e}")
