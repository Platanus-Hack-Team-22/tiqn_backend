"""Audio transcription services using Azure Speech and OpenAI Whisper."""

import asyncio
import io
from typing import AsyncGenerator

import azure.cognitiveservices.speech as speechsdk
import httpx

from ..config import settings


async def transcribe_audio_chunk_whisper(
    audio_data: bytes, content_type: str = "audio/webm", filename: str = "audio.webm"
) -> str:
    """Transcribe audio chunk using Azure OpenAI Whisper."""

    if not settings.AZURE_OPENAI_API_KEY or not settings.AZURE_OPENAI_TRANSCRIBE_URL:
        raise ValueError("Azure OpenAI credentials not configured")

    # Create form data
    files = {"file": (filename, io.BytesIO(audio_data), content_type)}
    data = {
        "model": "whisper-1",
        "language": "es",
        "response_format": "json",
        "prompt": "Contexto: Servicio de emergencias Hatzalah Chile. El audio describe una emergencia y datos del paciente o solicitante. Usa español de Chile. Reconoce nombres y direcciones típicas de Santiago de Chile y comunas de la Región Metropolitana.",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            settings.AZURE_OPENAI_TRANSCRIBE_URL,
            files=files,
            data=data,
            headers={
                "api-key": settings.AZURE_OPENAI_API_KEY,
            },
        )

        if response.status_code != 200:
            raise ValueError(f"Transcription failed: {response.text}")

        result = response.json()
        return result.get("text", "")


async def transcribe_audio_stream_azure(
    audio_stream: AsyncGenerator[bytes, None],
    session_id: str,
) -> AsyncGenerator[tuple[str, bool], None]:
    """
    Transcribe audio stream using Azure Speech SDK.

    Yields tuples of (text, is_final).
    """

    if not settings.AZURE_SPEECH_KEY or not settings.AZURE_SPEECH_REGION:
        raise ValueError("Azure Speech credentials not configured")

    # Configure Azure Speech
    speech_config = speechsdk.SpeechConfig(
        subscription=settings.AZURE_SPEECH_KEY,
        region=settings.AZURE_SPEECH_REGION,
    )
    speech_config.speech_recognition_language = "es-CL"

    # Create push stream
    push_stream = speechsdk.audio.PushAudioInputStream()
    audio_config = speechsdk.audio.AudioConfig(stream=push_stream)

    # Create recognizer
    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )

    # Add emergency phrases for better recognition
    phrase_list = speechsdk.PhraseListGrammar.from_recognizer(recognizer)
    emergency_phrases = [
        "tiqn",
        "emergencia",
        "ambulancia",
        "consciente",
        "inconsciente",
        "respira",
        "no respira",
        "alerta",
        "verbal",
        "dolor",
        "AVDI",
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
    ]
    for phrase in emergency_phrases:
        phrase_list.addPhrase(phrase)

    # Results queue
    results_queue: asyncio.Queue[tuple[str, bool] | None] = asyncio.Queue()

    # Event handlers
    def recognizing_handler(evt: speechsdk.SpeechRecognitionEventArgs) -> None:
        """Handle interim results."""
        if evt.result.reason == speechsdk.ResultReason.RecognizingSpeech:
            asyncio.create_task(results_queue.put((evt.result.text, False)))

    def recognized_handler(evt: speechsdk.SpeechRecognitionEventArgs) -> None:
        """Handle final results."""
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            asyncio.create_task(results_queue.put((evt.result.text, True)))

    def session_stopped_handler(evt: speechsdk.SessionEventArgs) -> None:
        """Handle session end."""
        asyncio.create_task(results_queue.put(None))

    # Connect handlers
    recognizer.recognizing.connect(recognizing_handler)
    recognizer.recognized.connect(recognized_handler)
    recognizer.session_stopped.connect(session_stopped_handler)

    # Start continuous recognition
    recognizer.start_continuous_recognition()

    # Feed audio stream
    async def feed_audio() -> None:
        """Feed audio chunks to recognizer."""
        try:
            async for chunk in audio_stream:
                push_stream.write(chunk)
            push_stream.close()
        except Exception as e:
            print(f"Error feeding audio: {e}")
            push_stream.close()

    # Start feeding audio in background
    feed_task = asyncio.create_task(feed_audio())

    # Yield results
    try:
        while True:
            result = await results_queue.get()
            if result is None:
                break
            yield result
    finally:
        recognizer.stop_continuous_recognition()
        await feed_task


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
