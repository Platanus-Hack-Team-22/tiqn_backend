# How The Emergency Call Processing Works - Step by Step

## Overview

Your app processes emergency call audio in real-time, transcribes it, extracts structured data using AI, and saves everything to Convex. Here's the complete flow:

---

## 📞 Complete Call Flow

```
1. Call Starts → WebSocket Opens
2. Audio Chunks Arrive (every 5 seconds)
3. Each Chunk: Transcribe → Extract → Update
4. Call Ends → Save to Convex
```

---

## Step-by-Step: From Audio to Database

### STEP 1: Call Begins - Your Team's WebSocket API

```python
# Your team member's WebSocket API receives connection
@websocket("/emergency/call")
async def handle_call(websocket: WebSocket):
    # Generate unique session ID for this call
    session_id = str(uuid.uuid4())  # e.g., "550e8400-e29b-41d4-a716-446655440000"
    
    await websocket.accept()
    # Now waiting for audio chunks...
```

**What happens:**
- ✅ Emergency call connects via WebSocket
- ✅ System generates unique `session_id` for tracking this call
- ✅ WebSocket stays open for the entire call duration

---

### STEP 2: Audio Chunk Arrives (Every ~5 Seconds)

```python
# Your team's WebSocket receives binary audio data
audio_chunk = await websocket.receive_bytes()  # 5 seconds of audio
```

**What arrives:**
- 📦 Binary audio data (WebM, WAV, or MP3 format)
- ⏱️ Typically 5 seconds worth of audio
- 🔄 This repeats every 5 seconds throughout the call

---

### STEP 3: Your Core Function is Called

```python
from core_api.src.core import process_audio_chunk

# Your team member calls YOUR function
result = await process_audio_chunk(
    audio_chunk=audio_chunk,    # Binary audio data
    session_id=session_id       # Same ID for entire call
)
```

**Location:** `src/core.py` → `process_audio_chunk()`

---

### STEP 4: Inside `process_audio_chunk()` - The Magic Happens

#### 4a. Session Management
```python
# Get or create session for this call
session = session_manager.get_or_create_session(session_id)
```

**What happens:**
- If this is the **first chunk**: Creates new session object
- If **subsequent chunk**: Retrieves existing session
- Session stores: full transcript, canonical data, chunk count, timestamps

**Location:** `src/services/session.py` → `CallSession`

---

#### 4b. Transcribe Audio → Text
```python
# Transcribe audio chunk using Azure OpenAI Whisper
chunk_text = await transcribe_audio_chunk_whisper(audio_chunk)
# Returns: "hola necesito ayuda mi nombre es Juan Pérez"
```

**What happens:**
1. Sends audio to Azure OpenAI Whisper API
2. Uses Spanish (Chile) language model
3. Context prompt: "Emergency service, Hatzalah Chile, Santiago locations"
4. Returns transcribed text

**API Call:**
```
POST https://smartup-strawberry.openai.azure.com/openai/deployments/gpt-4o-mini-transcribe/audio/transcriptions
Headers: api-key: <AZURE_OPENAI_API_KEY>
Body: audio file + language=es + prompt
Response: {"text": "hola necesito ayuda..."}
```

**Time:** ~1-3 seconds

**Location:** `src/services/transcription.py` → `transcribe_audio_chunk_whisper()`

---

#### 4c. Add to Transcript
```python
# Append new text to session's full transcript
session.add_transcript_chunk(chunk_text)
```

**What happens:**
- Adds space + new text to existing transcript
- Updates `session.full_transcript`
- Increments `session.chunk_count`
- Updates `session.last_updated` timestamp

**Example:**
```python
# Chunk 1: "hola necesito ayuda"
# Chunk 2: "mi nombre es Juan Pérez"
# Full transcript: "hola necesito ayuda mi nombre es Juan Pérez"
```

---

#### 4d. Extract Structured Data with Claude AI
```python
# Extract emergency data from new transcript chunk
updated_canonical = await extract_with_claude(
    transcript_chunk=chunk_text,           # Just this chunk's text
    existing_canonical=session.canonical_data,  # Previous data
)
```

**What happens:**

1. **Builds Claude Prompt:**
   ```python
   System: "You are a Hatzalah Chile emergency operator. Extract ONLY new data from this chunk."
   
   User: "Previous data: {nombre: 'Juan'}
   
   New transcript chunk: 'tengo 45 años y estoy en Apoquindo 3000'
   
   Extract JSON with these fields: nombre, apellido, edad, direccion, numero, comuna, ..."
   ```

2. **Calls Claude API:**
   ```
   POST https://api.anthropic.com/v1/messages
   Model: claude-3-5-sonnet-20241022
   Temperature: 0 (deterministic)
   Max tokens: 2048
   ```

3. **Claude Returns JSON:**
   ```json
   {
     "nombre": "",        // Already extracted, no new data
     "apellido": "",      // Not mentioned in this chunk
     "edad": "45",        // ← NEW! Extracted from "tengo 45 años"
     "sexo": "",
     "direccion": "Apoquindo",  // ← NEW!
     "numero": "3000",    // ← NEW!
     "comuna": "Las Condes",  // ← INFERRED from "Apoquindo"
     // ... 24 more fields
   }
   ```

4. **Merges with Existing Data:**
   ```python
   existing = {nombre: "Juan", edad: "", direccion: ""}
   new_data = {nombre: "", edad: "45", direccion: "Apoquindo"}
   
   merged = {nombre: "Juan", edad: "45", direccion: "Apoquindo"}
   # Only non-empty fields overwrite
   ```

5. **Post-Processing:**
   - Capitalizes names: "juan" → "Juan"
   - Normalizes medical fields: "consciente si" → "si"
   - Infers commune from street: "Apoquindo" → "Las Condes"
   - Generates Google Maps URL
   - Extracts address patterns from text
   - Infers first-person status

**Time:** ~1-2 seconds

**Location:** `src/services/canonical.py` → `extract_with_claude()`

---

#### 4e. Update Session
```python
# Save updated canonical data to session
session.update_canonical(updated_canonical)
```

**What happens:**
- Replaces session's canonical data with merged result
- Updates `session.last_updated` timestamp

---

#### 4f. Build Response
```python
# Prepare response for WebSocket
result = {
    "chunk_text": chunk_text,           # "tengo 45 años..."
    "full_transcript": session.full_transcript,  # Complete so far
    "canonical": updated_canonical.model_dump(),  # All 31 fields
    "timestamp": time.time(),           # Unix timestamp
    "session_info": {
        "session_id": session_id,
        "duration_seconds": session.get_duration(),  # Time since first chunk
        "chunk_count": session.chunk_count           # Number of chunks processed
    }
}

return result
```

**Response Example:**
```json
{
  "chunk_text": "tengo 45 años y estoy en Apoquindo 3000",
  "full_transcript": "hola necesito ayuda mi nombre es Juan Pérez tengo 45 años y estoy en Apoquindo 3000",
  "canonical": {
    "nombre": "Juan",
    "apellido": "Pérez",
    "edad": "45",
    "sexo": "M",
    "direccion": "Apoquindo",
    "numero": "3000",
    "comuna": "Las Condes",
    "codigo": "Verde",
    "consciente": "si",
    "respira": "si",
    "motivo": "hola necesito ayuda mi nombre es Juan Pérez tengo 45 años...",
    // ... 20 more fields
  },
  "timestamp": 1732287654.123,
  "session_info": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "duration_seconds": 15.2,
    "chunk_count": 3
  }
}
```

---

### STEP 5: Response Sent Back to WebSocket

```python
# Your team's WebSocket handler sends result to frontend
await websocket.send_json(result)
```

**What happens:**
- Operator's UI receives structured data
- Form fields auto-fill as person speaks
- Transcript displays in real-time
- Updates every ~5 seconds with new chunks

---

### STEP 6: Loop Repeats for Each Chunk

```python
# This happens continuously during the call:
while call_active:
    audio_chunk = await websocket.receive_bytes()  # Next 5 seconds
    result = await process_audio_chunk(audio_chunk, session_id)
    await websocket.send_json(result)
    
# Each iteration:
# - Adds to transcript
# - Extracts more data
# - Refines existing data
# - Updates operator's screen
```

**Call Progress Example:**

| Chunk | Duration | Transcript Added | Data Extracted |
|-------|----------|------------------|----------------|
| 1 | 5s | "hola necesito ayuda" | motivo |
| 2 | 10s | "mi nombre es Juan Pérez" | nombre, apellido |
| 3 | 15s | "tengo 45 años" | edad |
| 4 | 20s | "estoy en Apoquindo 3000" | direccion, numero, comuna |
| 5 | 25s | "me duele el pecho" | motivo (updated) |

---

### STEP 7: Call Ends - WebSocket Disconnects

```python
# Caller hangs up or operator ends call
except WebSocketDisconnect:
    # Call ended
```

---

### STEP 8: Save to Convex Database

```python
from core_api.src.core import end_session

# Your team's API calls this when call ends
final_data = end_session(
    session_id=session_id,
    save_to_convex=True,
    dispatcher_id="<convex-dispatcher-id>"  # ID of operator handling call
)
```

**Location:** `src/core.py` → `end_session()`

---

### STEP 9: Inside `end_session()` - Database Save

#### 9a. Retrieve and Remove Session
```python
# Get final session data
session = session_manager.remove_session(session_id)

final_data = {
    "session_id": session_id,
    "full_transcript": session.full_transcript,
    "canonical": session.canonical_data.model_dump(),
    "duration_seconds": session.get_duration(),
    "chunk_count": session.chunk_count,
}
```

#### 9b. Save to Convex
```python
from src.services.convex_db import get_convex_service

convex = get_convex_service()
save_result = convex.save_emergency_call(
    session_id=session_id,
    full_transcript=session.full_transcript,
    canonical_data=session.canonical_data,
    duration_seconds=session.get_duration(),
    chunk_count=session.chunk_count,
    dispatcher_id=dispatcher_id,
)
```

**Location:** `src/services/convex_db.py` → `save_emergency_call()`

---

### STEP 10: Inside Convex Save - 3 Records Created

#### 10a. Create Patient Record
```python
# Map canonical data to patient schema
patient_data = {
    "firstName": canonical.nombre,           # "Juan"
    "lastName": canonical.apellido,          # "Pérez"
    "age": int(canonical.edad),              # 45
    "sex": canonical.sexo,                   # "M"
    "address": f"{canonical.direccion} {canonical.numero}",  # "Apoquindo 3000"
    "district": canonical.comuna,            # "Las Condes"
    "medications": ["Aspirina", "Metformina"],  # Split from canonical.medicamentos
    "allergies": ["Penicilina"],             # Split from canonical.alergias
    "medicalHistory": ["Hipertensión"],      # Split from canonical.historia_clinica
    "createdAt": timestamp,
    "updatedAt": timestamp,
}

# Call Convex mutation
patient_id = client.mutation("patients:create", patient_data)
```

**Convex API Call:**
```
POST https://knowing-mouse-775.convex.cloud
Function: patients:create
Result: Patient ID (e.g., "j123abc456def")
```

---

#### 10b. Create Incident Record
```python
# Map canonical data to incident schema
incident_data = {
    "incidentNumber": "INC-550e8400",  # Last 8 chars of session_id
    "status": "incoming_call",
    "priority": "medium",  # Mapped from canonical.codigo "Amarillo"
    "incidentType": canonical.motivo,  # "Dolor en el pecho"
    "description": build_incident_description(canonical),  # Detailed description
    "location": {
        "address": "Apoquindo 3000",
        "district": "Las Condes",
        "reference": canonical.ubicacion_referencia,
    },
    "createdAt": timestamp,
    "dispatcherId": dispatcher_id,  # Operator handling this call
    "patientId": patient_id,        # Link to patient record
}

# Call Convex mutation
incident_id = client.mutation("incidents:create", incident_data)
```

**Description Built:**
```
Motivo: Dolor en el pecho
Estado: Consciente: si, Respira: si, AVDI: alerta
Inicio: Súbito
```

**Convex API Call:**
```
POST https://knowing-mouse-775.convex.cloud
Function: incidents:create
Result: Incident ID (e.g., "k789xyz012abc")
```

---

#### 10c. Create Call Record
```python
# Save transcription
call_data = {
    "incidentId": incident_id,
    "transcription": full_transcript,  # Complete transcript
    "transcriptionChunks": None,       # TODO: Track during streaming
    "createdAt": timestamp,
}

# Call Convex mutation
call_id = client.mutation("calls:create", call_data)
```

**Convex API Call:**
```
POST https://knowing-mouse-775.convex.cloud
Function: calls:create
Result: Call ID (e.g., "m345pqr678stu")
```

---

### STEP 11: Return Final Result

```python
return {
    "success": True,
    "session_id": session_id,
    "full_transcript": "hola necesito ayuda...",
    "canonical": {...},  # All 31 fields
    "duration_seconds": 125.4,
    "chunk_count": 25,
    "convex_save": {
        "success": True,
        "patient_id": "j123abc456def",
        "incident_id": "k789xyz012abc",
        "call_id": "m345pqr678stu",
        "incident_number": "INC-550e8400"
    }
}
```

---

## 🎯 Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. CALLER                                                       │
│    └─> Phone Call to Emergency Number                          │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. YOUR TEAM'S API (WebSocket)                                 │
│    └─> Receives call, generates session_id                     │
│    └─> Streams audio chunks (5s intervals)                     │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. YOUR CORE FUNCTION: process_audio_chunk()                   │
│    ┌────────────────────────────────────────────────────────┐  │
│    │ 3a. Session Manager                                    │  │
│    │     └─> Get/Create session                            │  │
│    └────────────────────────────────────────────────────────┘  │
│    ┌────────────────────────────────────────────────────────┐  │
│    │ 3b. Azure Whisper API                                  │  │
│    │     └─> Transcribe audio → text                       │  │
│    │     └─> Time: ~1-3s                                    │  │
│    └────────────────────────────────────────────────────────┘  │
│    ┌────────────────────────────────────────────────────────┐  │
│    │ 3c. Add to Transcript                                  │  │
│    │     └─> Append new text to full transcript            │  │
│    └────────────────────────────────────────────────────────┘  │
│    ┌────────────────────────────────────────────────────────┐  │
│    │ 3d. Claude AI Extraction                               │  │
│    │     └─> Extract 31 structured fields                  │  │
│    │     └─> Merge with existing data                      │  │
│    │     └─> Time: ~1-2s                                    │  │
│    └────────────────────────────────────────────────────────┘  │
│    ┌────────────────────────────────────────────────────────┐  │
│    │ 3e. Return Result                                      │  │
│    │     └─> Transcript + Canonical Data                   │  │
│    └────────────────────────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. OPERATOR'S UI                                                │
│    └─> Form auto-fills (nombre, edad, direccion...)            │
│    └─> Transcript displays                                     │
│    └─> Updates every 5 seconds                                 │
└─────────────────────────────────────────────────────────────────┘
                        │
                        │ (Repeats for each chunk)
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. CALL ENDS (WebSocket Disconnects)                           │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. YOUR CORE FUNCTION: end_session()                           │
│    ┌────────────────────────────────────────────────────────┐  │
│    │ 6a. Get Final Session Data                            │  │
│    │     └─> Full transcript                               │  │
│    │     └─> All canonical fields                          │  │
│    │     └─> Duration, chunk count                         │  │
│    └────────────────────────────────────────────────────────┘  │
│    ┌────────────────────────────────────────────────────────┐  │
│    │ 6b. Save to Convex                                     │  │
│    │     └─> Create Patient                                │  │
│    │     └─> Create Incident                               │  │
│    │     └─> Create Call                                   │  │
│    └────────────────────────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. CONVEX DATABASE (knowing-mouse-775)                         │
│    ┌─────────────────────────────────────────────────────┐    │
│    │ patients table                                      │    │
│    │   - Juan Pérez, 45, M                              │    │
│    │   - Apoquindo 3000, Las Condes                     │    │
│    │   - Medications, Allergies                         │    │
│    └─────────────────────────────────────────────────────┘    │
│    ┌─────────────────────────────────────────────────────┐    │
│    │ incidents table                                     │    │
│    │   - INC-550e8400                                   │    │
│    │   - Priority: medium                               │    │
│    │   - Location: Apoquindo 3000                       │    │
│    │   - Links to patient & dispatcher                  │    │
│    └─────────────────────────────────────────────────────┘    │
│    ┌─────────────────────────────────────────────────────┐    │
│    │ calls table                                         │    │
│    │   - Full transcription                             │    │
│    │   - Links to incident                              │    │
│    └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Timing Breakdown

For a typical 2-minute call with 24 chunks:

| Activity | Per Chunk | Total (24 chunks) |
|----------|-----------|-------------------|
| Audio recording | 5s | 120s (2 min) |
| Transcription (Whisper) | 1-3s | 24-72s |
| AI Extraction (Claude) | 1-2s | 24-48s |
| Total processing | 2-5s | 48-120s |
| Convex save (end) | - | 1-2s |

**Latency:** 2-5 seconds per chunk  
**Total call:** ~2 minutes  
**Total processing:** ~1-2 minutes (happens in real-time)

---

## 🔑 Key Files

| File | What It Does |
|------|--------------|
| `src/core.py` | Main entry point: `process_audio_chunk()`, `end_session()` |
| `src/services/transcription.py` | Calls Azure Whisper API |
| `src/services/canonical.py` | Calls Claude AI, extracts 31 fields |
| `src/services/session.py` | Manages call sessions in memory |
| `src/services/convex_db.py` | Saves to Convex database |
| `src/schemas.py` | Defines CanonicalV2 (31 fields) |
| `src/config.py` | Environment variables |

---

## ✅ Summary

1. ✅ **Audio arrives** → Your team's WebSocket API
2. ✅ **They call** → Your `process_audio_chunk()` function
3. ✅ **You transcribe** → Azure Whisper API
4. ✅ **You extract** → Claude AI (31 fields)
5. ✅ **You return** → Structured data back to WebSocket
6. ✅ **Repeat** → Every 5 seconds during call
7. ✅ **Call ends** → Your `end_session()` saves to Convex
8. ✅ **Database** → 3 records created (patient, incident, call)

**Your app handles steps 3-7. Your team handles steps 1-2 and displays the results!**

