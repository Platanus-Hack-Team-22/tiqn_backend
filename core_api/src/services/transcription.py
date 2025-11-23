"""Audio transcription services using Azure Speech SDK."""

import asyncio
from typing import AsyncGenerator

import azure.cognitiveservices.speech as speechsdk

from ..config import settings


async def transcribe_audio_stream_azure(
    audio_stream: AsyncGenerator[bytes, None],
    session_id: str,
    audio_format: str = "mulaw",
) -> AsyncGenerator[tuple[str, bool], None]:
    """
    Transcribe audio stream using Azure Speech SDK.

    Args:
        audio_stream: AsyncGenerator yielding audio bytes
        session_id: Unique session identifier for logging
        audio_format: Audio format - "mulaw" for Twilio (8kHz Mu-law) or "pcm16" for standard PCM

    Yields tuples of (text, is_final).
    """
    import logging
    logger = logging.getLogger(__name__)

    if not settings.AZURE_SPEECH_KEY or not settings.AZURE_SPEECH_REGION:
        raise ValueError("Azure Speech credentials not configured")

    # Configure Azure Speech
    speech_config = speechsdk.SpeechConfig(
        subscription=settings.AZURE_SPEECH_KEY,
        region=settings.AZURE_SPEECH_REGION,
    )
    speech_config.speech_recognition_language = "es-CL"

    # Configure audio format based on input type
    if audio_format == "mulaw":
        # Twilio sends 8kHz Mu-law mono
        stream_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=8000,
            bits_per_sample=16,  # Azure expects 16-bit after Mu-law decompression
            channels=1,
            wave_stream_format=speechsdk.AudioStreamWaveFormat.MULAW,
        )
    else:
        # Standard 16kHz PCM mono (default for most applications)
        stream_format = speechsdk.audio.AudioStreamFormat(
            samples_per_second=16000,
            bits_per_sample=16,
            channels=1,
        )

    # Create push stream with explicit format
    push_stream = speechsdk.audio.PushAudioInputStream(stream_format=stream_format)
    audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

    # Create recognizer
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )

    # Add emergency phrases for better recognition
    phrase_list = speechsdk.PhraseListGrammar.from_recognizer(recognizer)
    emergency_phrases = [
        "emergencia",
        "ambulancia",
        "consciente",
        "inconsciente",
        "respira",
        "no respira",
        "alerta",
        "verbal",
        "dolor",
        "paciente",
        "direccion",
        "comuna",
        "Las Condes",
        "Providencia",
        "Vitacura",
        "Santiago",
        "Ñuñoa",
        "Apoquindo",
        "Los Leones",
        "MUT",
    ]
    for phrase in emergency_phrases:
        phrase_list.addPhrase(phrase)

    # Results queue
    results_queue: asyncio.Queue[tuple[str, bool] | None] = asyncio.Queue()

    # Get the event loop for thread-safe task creation
    loop = asyncio.get_event_loop()

    # Event handlers (called from SDK threads, need thread-safe queue operations)
    def recognizing_handler(evt: speechsdk.SpeechRecognitionEventArgs) -> None:
        """Handle interim results."""
        if evt.result.reason == speechsdk.ResultReason.RecognizingSpeech:
            # Thread-safe: schedule task in the event loop
            asyncio.run_coroutine_threadsafe(
                results_queue.put((evt.result.text, False)), loop
            )

    def recognized_handler(evt: speechsdk.SpeechRecognitionEventArgs) -> None:
        """Handle final results."""
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            # Thread-safe: schedule task in the event loop
            asyncio.run_coroutine_threadsafe(
                results_queue.put((evt.result.text, True)), loop
            )
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            logger.warning(f"No speech recognized in session {session_id}")

    def session_stopped_handler(evt: speechsdk.SessionEventArgs) -> None:
        """Handle session end."""
        logger.info(f"Azure Speech session stopped for {session_id}")
        asyncio.run_coroutine_threadsafe(results_queue.put(None), loop)

    def canceled_handler(evt: speechsdk.SpeechRecognitionCanceledEventArgs) -> None:
        """Handle recognition cancellation/errors."""
        logger.error(f"Azure Speech recognition canceled for {session_id}: {evt.reason}")
        if evt.reason == speechsdk.CancellationReason.Error:
            logger.error(f"Error details: {evt.error_details}")
        asyncio.run_coroutine_threadsafe(results_queue.put(None), loop)

    # Connect handlers
    recognizer.recognizing.connect(recognizing_handler)
    recognizer.recognized.connect(recognized_handler)
    recognizer.session_stopped.connect(session_stopped_handler)
    recognizer.canceled.connect(canceled_handler)

    # Start continuous recognition
    logger.info(f"Starting Azure Speech recognition for session {session_id}")
    recognizer.start_continuous_recognition()

    # Feed audio stream
    async def feed_audio() -> None:
        """Feed audio chunks to recognizer."""
        try:
            chunk_count = 0
            async for chunk in audio_stream:
                push_stream.write(chunk)
                chunk_count += 1
            logger.info(f"Finished feeding {chunk_count} audio chunks for session {session_id}")
            push_stream.close()
        except Exception as e:
            logger.error(f"Error feeding audio for session {session_id}: {e}")
            push_stream.close()
            # Signal error by putting None in queue
            asyncio.run_coroutine_threadsafe(results_queue.put(None), loop)

    # Start feeding audio in background
    feed_task = asyncio.create_task(feed_audio())

    # Yield results
    try:
        while True:
            result = await results_queue.get()
            if result is None:
                logger.info(f"Recognition ended for session {session_id}")
                break
            yield result
    finally:
        # Cleanup
        logger.info(f"Cleaning up Azure Speech resources for session {session_id}")
        try:
            recognizer.stop_continuous_recognition()
        except Exception as e:
            logger.error(f"Error stopping recognizer: {e}")

        # Wait for feed task to complete
        try:
            await asyncio.wait_for(feed_task, timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning(f"Feed task timeout for session {session_id}")
            feed_task.cancel()


async def get_azure_speech_token() -> dict[str, str | int]:
    """Get temporary Azure Speech Service token."""

    if not settings.AZURE_SPEECH_KEY:
        raise ValueError("AZURE_SPEECH_KEY not configured")

    region = settings.AZURE_SPEECH_REGION
    endpoint = settings.AZURE_SPEECH_ENDPOINT

    # Build token URL
    if endpoint:
        token_url = f"{endpoint.rstrip('/')}/sts/v1.0/issueToken"
    elif region:
        token_url = f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
    else:
        raise ValueError("AZURE_SPEECH_REGION or AZURE_SPEECH_ENDPOINT required")

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            token_url,
            headers={
                "Ocp-Apim-Subscription-Key": settings.AZURE_SPEECH_KEY,
                "Content-Length": "0",
            },
        )

        if response.status_code != 200:
            raise ValueError(f"Token request failed: {response.text}")

        token = response.text.strip()

        return {
            "token": token,
            "region": region or "",
            "endpoint": endpoint or "",
            "expires_in": 600,
        }
