# TIQN Emergency Services API

TO RUN uv run fastapi dev src/main.py
FastAPI backend for real-time audio transcription and emergency data extraction for Hatzalah Chile.

a

## Features

- 🎙️ **Real-time WebSocket streaming** - Transcribe audio chunks as they arrive (~5 second intervals)
- 🤖 **Claude AI integration** - Intelligent extraction of 31 structured emergency data fields
- 🌐 **Azure Speech Services** - High-quality Spanish (Chile) transcription
- 📁 **File upload support** - Fallback for complete audio file processing
- 🔄 **Incremental updates** - AI merges new information with existing call data
- 📊 **Session management** - Track multiple ongoing emergency calls

## Requirements

- Python 3.13+
- `uv` package manager
- PostgreSQL database
- Azure Speech Services account
- Azure OpenAI account (for Whisper)
- Anthropic API key (for Claude)

## Quick Start

### 1. Install Dependencies

```bash
uv sync
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Required environment variables:

- `DATABASE_URL` - PostgreSQL connection string
- `AZURE_SPEECH_KEY` - Azure Speech Services subscription key
- `AZURE_SPEECH_REGION` - Azure region (e.g., "eastus")
- `AZURE_OPENAI_API_KEY` - Azure OpenAI API key
- `AZURE_OPENAI_TRANSCRIBE_URL` - Whisper endpoint URL
- `ANTHROPIC_API_KEY` - Anthropic API key for Claude

### 3. Run Development Server

```bash
uv run fastapi dev src/main.py
```

The API will be available at:

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### WebSocket Streaming

#### `WS /stream/transcribe/{session_id}`

Real-time audio transcription with incremental data extraction.

**Client workflow:**

1. Connect to WebSocket
2. Send audio chunks as binary data (every ~5 seconds)
3. Receive JSON responses with transcript + canonical data
4. Close connection when call ends

**Response format:**

```json
{
  "chunk_text": "El paciente está en Apoquindo 3000",
  "full_transcript": "Hola, tengo una emergencia. El paciente está en Apoquindo 3000",
  "canonical": {
    "nombre": "",
    "apellido": "",
    "direccion": "Apoquindo",
    "numero": "3000",
    "comuna": "Las Condes",
    ...
  },
  "timestamp": 1234567890.123
}
```

**Example (JavaScript):**

```javascript
const ws = new WebSocket("ws://localhost:8000/stream/transcribe/call-123");

// Send audio chunks (e.g., from MediaRecorder)
mediaRecorder.ondataavailable = (event) => {
  if (event.data.size > 0) {
    ws.send(event.data);
  }
};

// Receive updates
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Transcript:", data.chunk_text);
  console.log("Location:", data.canonical.direccion, data.canonical.numero);
};
```

### HTTP Endpoints

#### `POST /transcribe/token`

Get temporary Azure Speech token for client-side SDK.

**Response:**

```json
{
  "token": "eyJ0eXAi...",
  "region": "eastus",
  "endpoint": "https://eastus.api.cognitive.microsoft.com",
  "expires_in": 600
}
```

#### `POST /transcribe/audio`

Upload audio file for transcription and data extraction.

**Request:**

- Content-Type: `multipart/form-data`
- Field: `file` (audio file, max 25 MB)
- Supported formats: webm, wav, mp3, mp4

**Response:**

```json
{
  "text": "Hola, mi nombre es Juan Pérez...",
  "json": {
    "nombre": "Juan",
    "apellido": "Pérez",
    ...
  },
  "duration_seconds": 5
}
```

#### `POST /transcribe/text`

Extract canonical data from existing transcript text.

**Request:**

```json
{
  "text": "El paciente es un hombre de 65 años, consciente, con dolor en el pecho"
}
```

**Response:**

```json
{
  "text": "El paciente es un hombre de 65 años...",
  "json": {
    "sexo": "M",
    "edad": "65",
    "consciente": "si",
    "motivo": "dolor en el pecho",
    ...
  },
  "duration_seconds": 2
}
```

### Session Management

#### `GET /stream/session/{session_id}`

Get current status of a streaming session.

#### `DELETE /stream/session/{session_id}`

End session and retrieve final data.

#### `GET /stream/sessions`

List all active sessions.

## Data Structure

The canonical emergency data includes 31 fields:

**Personal:**

- nombre, apellido, sexo, edad

**Location:**

- direccion, numero, comuna, depto, ubicacion_referencia, ubicacion_detalle, google_maps_url

**Medical:**

- codigo (triage: Verde/Amarillo/Rojo)
- avdi (AVPU: alerta/verbal/dolor/inconsciente)
- estado_respiratorio, consciente, respira
- motivo, inicio_sintomas

**Resources:**

- cantidad_rescatistas, recursos_requeridos

**History:**

- estado_basal, let_dnr, historia_clinica, medicamentos, alergias

**Administrative:**

- seguro_salud, aviso_conserjeria, signos_vitales, checklist_url, medico_turno

## Architecture

### Real-Time Flow

```
Client (MediaRecorder)
    ↓ audio chunks (~5s)
WebSocket Endpoint
    ↓
Azure Speech / Whisper
    ↓ transcript chunk
Claude AI
    ↓ extract new data
Merge with session data
    ↓ updated canonical
Client (real-time updates)
```

### Key Components

- **Session Manager** - Tracks ongoing calls, maintains state
- **Transcription Service** - Azure Speech SDK integration
- **Canonical Service** - Claude AI for structured data extraction
- **Post-processing** - Address sanitization, comuna inference, triage assignment

## Development

### Run Tests

```bash
uv run pytest
```

### Code Formatting

```bash
uv run ruff check .
uv run ruff format .
```

### Running Migrations

```bash
alembic upgrade head
```

### Create New Migration

```bash
alembic revision --autogenerate -m "description"
```

## Deployment

### Using Docker

```bash
docker build -t tiqn-api .
docker run -p 8000:8000 --env-file .env tiqn-api
```

### Production Server

```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Configuration

### Azure Speech Services

1. Create Speech Service in Azure Portal
2. Enable Spanish (es-CL) language
3. Copy subscription key and region

### Azure OpenAI

1. Deploy Whisper model
2. Get endpoint URL and API key
3. Format: `https://{resource}.openai.azure.com/openai/deployments/{whisper}/audio/transcriptions?api-version=2024-08-01-preview`

### Anthropic Claude

1. Sign up at https://console.anthropic.com
2. Create API key
3. Recommended model: `claude-3-5-sonnet-20241022`

## Troubleshooting

### WebSocket Connection Issues

- Check CORS settings in `main.py`
- Verify client is sending binary data (not JSON)
- Check audio format is supported

### Transcription Errors

- Verify Azure credentials are correct
- Check audio quality and format
- Ensure audio is Spanish language

### Extraction Issues

- Verify Anthropic API key is valid
- Check API rate limits
- Review Claude model name

## License

Proprietary - Hatzalah Chile

## Support

For issues or questions, contact the development team.
