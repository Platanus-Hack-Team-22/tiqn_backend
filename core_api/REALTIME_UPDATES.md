# Real-Time Incident Updates

## What You Need

To update the `incidents` table as data comes in during the call, you need:

1. **Convex Mutation** - `incidents:createOrUpdate` or `incidents:update`
2. **Python Service Update** - Call Convex after each chunk
3. **Modified Core Function** - Update database in `process_audio_chunk()`

---

## Option 1: Create Incident at Call Start, Update During Call

### Flow

```
Call Starts
  ↓
Create incident with basic info (status="incoming_call")
  ↓
Chunk 1 arrives → Update incident with name
  ↓
Chunk 2 arrives → Update incident with age
  ↓
Chunk 3 arrives → Update incident with address
  ↓
... etc (updates every 5 seconds)
  ↓
Call Ends → Final update with patient_id
```

### Convex Mutation (Your team creates this)

```typescript
// convex/incidents.ts

export const createOrUpdate = mutation({
  args: {
    // Required
    callSessionId: v.string(),
    dispatcherId: v.id("dispatchers"),
    
    // Optional - only update fields that have new data
    incidentNumber: v.optional(v.string()),
    status: v.optional(v.union(...)),
    priority: v.optional(v.union(...)),
    incidentType: v.optional(v.string()),
    description: v.optional(v.string()),
    
    // Location
    location: v.optional(v.object({
      address: v.optional(v.string()),
      district: v.optional(v.string()),
      reference: v.optional(v.string()),
    })),
    
    // Patient data (from canonical)
    patientName: v.optional(v.string()),
    patientAge: v.optional(v.number()),
    patientSex: v.optional(v.string()),
    consciousness: v.optional(v.string()),
    breathing: v.optional(v.string()),
    avdi: v.optional(v.string()),
    medicalHistory: v.optional(v.string()),
    currentMedications: v.optional(v.string()),
    allergies: v.optional(v.string()),
    fullTranscript: v.optional(v.string()),
    rawCanonicalData: v.optional(v.any()),
  },
  
  handler: async (ctx, args) => {
    const { callSessionId, dispatcherId, ...updateData } = args;
    
    // Try to find existing incident by session ID
    const existing = await ctx.db
      .query("incidents")
      .withIndex("by_session", (q) => q.eq("callSessionId", callSessionId))
      .first();
    
    if (existing) {
      // UPDATE existing incident
      await ctx.db.patch(existing._id, {
        ...updateData,
        lastUpdated: Date.now(),
      });
      return existing._id;
    } else {
      // CREATE new incident (first chunk)
      const incidentId = await ctx.db.insert("incidents", {
        callSessionId,
        dispatcherId,
        incidentNumber: args.incidentNumber || `INC-${callSessionId.slice(-8)}`,
        status: args.status || "incoming_call",
        priority: args.priority || "medium",
        location: args.location || { address: "Unknown" },
        lastUpdated: Date.now(),
        ...updateData,
      });
      return incidentId;
    }
  },
});
```

### Python Service Update

```python
# src/services/convex_db.py

class ConvexService:
    # ... existing code ...
    
    def update_incident_realtime(
        self,
        session_id: str,
        canonical_data: CanonicalV2,
        full_transcript: str,
        dispatcher_id: str,
    ) -> dict[str, Any]:
        """
        Update incident record in real-time as data comes in.
        
        Called after each audio chunk is processed.
        """
        try:
            # Build update data from canonical
            update_data = {
                "callSessionId": session_id,
                "dispatcherId": dispatcher_id,
                
                # Priority from triage code
                "priority": map_codigo_to_priority(canonical_data.codigo),
                
                # Patient info
                "patientName": f"{canonical_data.nombre} {canonical_data.apellido}".strip() or None,
                "patientAge": safe_int(canonical_data.edad),
                "patientSex": canonical_data.sexo if canonical_data.sexo in ["M", "F"] else None,
                
                # Medical status
                "consciousness": canonical_data.consciente or None,
                "breathing": canonical_data.respira or None,
                "avdi": canonical_data.avdi or None,
                "respiratoryStatus": canonical_data.estado_respiratorio or None,
                
                # Medical details
                "symptomOnset": canonical_data.inicio_sintomas or None,
                "medicalHistory": canonical_data.historia_clinica or None,
                "currentMedications": canonical_data.medicamentos or None,
                "allergies": canonical_data.alergias or None,
                "vitalSigns": canonical_data.signos_vitales or None,
                
                # Location
                "location": {
                    "address": f"{canonical_data.direccion} {canonical_data.numero}".strip() or "Unknown",
                    "district": canonical_data.comuna or None,
                    "reference": canonical_data.ubicacion_referencia or None,
                },
                "apartment": canonical_data.depto or None,
                "locationDetail": canonical_data.ubicacion_detalle or None,
                
                # Resources
                "requiredRescuers": canonical_data.cantidad_rescatistas or None,
                "requiredResources": canonical_data.recursos_requeridos or None,
                
                # Administrative
                "healthInsurance": canonical_data.seguro_salud or None,
                "conciergeNotified": canonical_data.aviso_conserjeria or None,
                
                # Incident info
                "incidentType": canonical_data.motivo or None,
                "description": build_incident_description(canonical_data),
                
                # Complete data
                "fullTranscript": full_transcript,
                "rawCanonicalData": canonical_data.model_dump(),
            }
            
            # Remove None values
            update_data = {k: v for k, v in update_data.items() if v is not None}
            
            # Call Convex mutation
            incident_id = self.client.mutation("incidents:createOrUpdate", update_data)
            
            return {
                "success": True,
                "incident_id": incident_id,
                "session_id": session_id,
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
```

### Modified Core Function

```python
# src/core.py

async def process_audio_chunk(
    audio_chunk: bytes,
    session_id: str,
    dispatcher_id: str | None = None,  # NEW: Optional dispatcher ID
    update_convex: bool = True,         # NEW: Enable real-time updates
) -> ProcessChunkResult:
    """
    Main function to process an audio chunk from an emergency call.
    
    Now includes real-time Convex updates!
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
    
    # Step 5: Update Convex in real-time (NEW!)
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
            print(f"Warning: Could not update Convex: {e}")
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
    
    # Include Convex update status if enabled
    if convex_update_result:
        result["convex_update"] = convex_update_result
    
    return result
```

### Usage Example

```python
# Your team member's WebSocket handler

@websocket("/emergency/call")
async def handle_call(websocket: WebSocket):
    session_id = str(uuid.uuid4())
    dispatcher_id = "<get-from-auth>"  # Get from authenticated user
    
    await websocket.accept()
    
    try:
        while True:
            audio_chunk = await websocket.receive_bytes()
            
            # Call your function WITH dispatcher_id
            result = await process_audio_chunk(
                audio_chunk=audio_chunk,
                session_id=session_id,
                dispatcher_id=dispatcher_id,  # Required for real-time updates
                update_convex=True,           # Enable real-time updates
            )
            
            # Check if Convex updated successfully
            if result.get("convex_update", {}).get("success"):
                print(f"✅ Incident updated in Convex: {result['convex_update']['incident_id']}")
            
            # Send to frontend
            await websocket.send_json(result)
            
    except WebSocketDisconnect:
        # Call ended - final save already done via real-time updates
        print(f"Call {session_id} ended")
```

---

## Option 2: Only Update, No Create at End

If you do real-time updates, you might **skip** the `end_session()` save since the data is already in Convex.

```python
# When call ends
except WebSocketDisconnect:
    # Just mark incident as completed
    final_data = end_session(
        session_id=session_id,
        save_to_convex=False,  # ← Don't create new records
    )
    
    # Update status to completed
    convex.client.mutation("incidents:updateStatus", {
        "callSessionId": session_id,
        "status": "completed"
    })
```

---

## Database View During Call

With real-time updates, operators/dashboard see:

**After 5 seconds (Chunk 1):**
```
Incident INC-550e8400
  Status: incoming_call
  Priority: medium
  Transcript: "hola necesito ayuda"
  Patient Name: ""
  Location: "Unknown"
```

**After 10 seconds (Chunk 2):**
```
Incident INC-550e8400
  Status: incoming_call
  Priority: medium
  Transcript: "hola necesito ayuda mi nombre es Juan Pérez"
  Patient Name: "Juan Pérez"  ← Updated!
  Location: "Unknown"
```

**After 20 seconds (Chunk 4):**
```
Incident INC-550e8400
  Status: incoming_call
  Priority: medium
  Transcript: "...estoy en Apoquindo 3000"
  Patient Name: "Juan Pérez"
  Patient Age: 45  ← New!
  Location: "Apoquindo 3000, Las Condes"  ← Updated!
  Consciousness: "si"  ← New!
```

---

## Summary

✅ **Schema**: Add patient/medical fields to `incidents` table  
✅ **Mutation**: Create `incidents:createOrUpdate` in Convex  
✅ **Python**: Add `update_incident_realtime()` method  
✅ **Core**: Modify `process_audio_chunk()` to call update  
✅ **Usage**: Pass `dispatcher_id` when calling the function  

**Result:** Database updates every 5 seconds as caller speaks! 🎉

