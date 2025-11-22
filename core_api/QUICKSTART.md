# Quick Start - Core Processing Function

## What This Is

This is the **core processing function** for emergency call transcription and data extraction. 

**Your team member handles:** WebSocket API, routing, authentication  
**This module handles:** Audio transcription + AI data extraction

---

## One Function Does Everything

```python
from core_api.src.core import process_audio_chunk

# In your WebSocket handler:
result = await process_audio_chunk(
    audio_chunk=audio_bytes,  # Raw audio data
    session_id="call-123"      # Unique call ID
)

# Returns structured emergency data
print(result["canonical"]["nombre"])    # "Juan"
print(result["canonical"]["direccion"]) # "Apoquindo"
print(result["canonical"]["comuna"])    # "Las Condes"
```

---

## Setup (1 minute)

1. **Install dependencies:**
```bash
cd /home/diegopollack/plat/tiqn_backend/core_api
uv sync
```

2. **Environment variables** (already set in your `.envrc`):
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export AZURE_OPENAI_API_KEY="..."
export AZURE_OPENAI_TRANSCRIBE_URL="..."
```

3. **That's it!** Your team member can now import and use the function.

---

## Usage Example

```python
from fastapi import WebSocket
from core_api.src.core import process_audio_chunk, end_session

@app.websocket("/emergency/{call_id}")
async def handle_call(websocket: WebSocket, call_id: str):
    await websocket.accept()
    
    try:
        while True:
            # Receive audio from client
            audio_data = await websocket.receive_bytes()
            
            # Process it (transcribe + extract data)
            result = await process_audio_chunk(
                audio_chunk=audio_data,
                session_id=call_id
            )
            
            # Send structured data back
            await websocket.send_json(result)
            
    except WebSocketDisconnect:
        # Cleanup when call ends
        final_data = end_session(call_id)
        print(f"Call ended: {final_data['duration_seconds']}s")
```

---

## What You Get Back

```python
{
    "chunk_text": "mi nombre es Juan...",     # Latest transcription
    "full_transcript": "hola necesito...",     # Complete transcript
    "canonical": {
        # 31 structured fields
        "nombre": "Juan",
        "apellido": "Pérez", 
        "direccion": "Apoquindo",
        "numero": "3000",
        "comuna": "Las Condes",
        "edad": "45",
        "sexo": "M",
        "codigo": "Amarillo",
        "consciente": "si",
        "respira": "si",
        "motivo": "dolor en el pecho",
        # ... and 20 more fields
    },
    "timestamp": 1700000000.123,
    "session_info": {
        "session_id": "call-123",
        "duration_seconds": 45.2,
        "chunk_count": 9
    }
}
```

---

## Full Documentation

- **`INTEGRATION_GUIDE.md`** - Complete integration guide with examples
- **`src/core.py`** - Main function implementation
- **`src/schemas.py`** - All 31 data fields documented

---

## Test It

```bash
# Start the minimal health check server
uv run fastapi dev src/main.py

# Test health endpoint
curl http://localhost:8000/
```

Or test the function directly:

```python
import asyncio
from core_api.src.core import process_audio_chunk

async def test():
    # Simulate with a text chunk
    result = await process_audio_chunk(
        audio_chunk=b"test audio data",
        session_id="test-123"
    )
    print(result)

asyncio.run(test())
```

---

## Architecture

```
Your Team Member's API
    ↓
calls: process_audio_chunk()
    ↓
1. Transcribe audio (Azure Whisper)
2. Extract data (Claude AI)
3. Manage session state
    ↓
returns: structured emergency data
```

---

## Questions?

See `INTEGRATION_GUIDE.md` for complete details and examples.

