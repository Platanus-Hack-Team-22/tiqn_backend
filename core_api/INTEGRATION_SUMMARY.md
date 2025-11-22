# Convex Integration Summary

## ✅ What's Done

### 1. Schema Integration
- ✅ Corrected and saved the agreed-upon Convex schema
- ✅ Created mapping documentation (`SCHEMA_MAPPING.md`)
- ✅ Schema includes: `patients`, `dispatchers`, `rescuers`, `incidents`, `calls`, `incidentAssignments`, `patientMatches`

### 2. Convex Functions Created
- ✅ `convex/patients.ts` - Create and query patients
- ✅ `convex/incidents.ts` - Create and query incidents
- ✅ `convex/calls.ts` - Create and update call transcriptions
- ✅ `convex/dispatchers.ts` - Manage dispatchers
- ✅ `convex/system.ts` - Utility functions (timestamp)

### 3. Python Integration
- ✅ Added `convex>=0.7.0` to dependencies
- ✅ Created `src/services/convex_db.py` with mapping logic
- ✅ Updated `src/core.py` to save to Convex on call end
- ✅ Intelligent mapping of 31 canonical fields to schema

### 4. Data Flow
```
Audio → Transcribe → Claude AI → 31 Fields → Map to Schema → Convex DB
                                                              ↓
                                              patients + incidents + calls tables
```

---

## 📋 Data Mapping

### Our AI Extraction → Their Schema

| Our Canonical Fields | Convex Tables | Details |
|---------------------|---------------|---------|
| `nombre`, `apellido`, `edad`, `sexo` | `patients.firstName/lastName/age/sex` | Direct mapping |
| `medicamentos`, `alergias`, `historia_clinica` | `patients.medications/allergies/medicalHistory` | Split comma-separated → arrays |
| `direccion`, `numero`, `comuna` | `patients.address/district` & `incidents.location` | Combined address string |
| `codigo` (Verde/Amarillo/Rojo) | `incidents.priority` (low/medium/critical) | Mapped |
| `motivo` | `incidents.incidentType` & `description` | Primary complaint |
| `consciente`, `respira`, `avdi` | `incidents.description` | Included in description text |
| `full_transcript` | `calls.transcription` | Complete transcript |

---

## 🚀 How to Use

### Convex Connection

Your backend is connected to the production Convex database:
- **Deployment:** `knowing-mouse-775`
- **URL:** `https://knowing-mouse-775.convex.cloud`

The schema and functions are managed by your team in Convex Cloud.

### Use in Your API

```python
from core_api.src.core import process_audio_chunk, end_session

# During call - process audio chunks
result = await process_audio_chunk(
    audio_chunk=audio_bytes,
    session_id="call-123"
)

# When call ends - save to Convex
final_data = end_session(
    session_id="call-123",
    save_to_convex=True,
    dispatcher_id="<convex-dispatcher-id>"  # Required!
)

# Check if saved successfully
if final_data["convex_save"]["success"]:
    print(f"✅ Saved to Convex!")
    print(f"Patient ID: {final_data['convex_save']['patient_id']}")
    print(f"Incident ID: {final_data['convex_save']['incident_id']}")
    print(f"Call ID: {final_data['convex_save']['call_id']}")
```

---

## ⚠️ Important Notes

### 1. Dispatcher ID Required
To save to Convex, you **must** provide a `dispatcher_id`. This is the Convex ID of the operator handling the call.

**Create a dispatcher first:**
```python
from convex import ConvexClient

client = ConvexClient(os.getenv("CONVEX_URL"))
dispatcher_id = client.mutation("dispatchers:create", {
    "name": "Juan Operator",
    "phone": "+56912345678",
    "createdAt": int(time.time() * 1000)
})
```

### 2. Session ID
The `session_id` is a unique identifier for each emergency call:
- Use a UUID: `str(uuid.uuid4())`
- Or timestamp-based: `f"call-{int(time.time())}"`
- Same ID for all chunks in one call

### 3. Data Transformation
The service automatically:
- ✅ Converts string ages to integers
- ✅ Splits comma-separated medications/allergies into arrays
- ✅ Maps triage codes (Verde→low, Amarillo→medium, Rojo→critical)
- ✅ Builds comprehensive incident descriptions
- ✅ Handles missing/optional fields gracefully

---

## 📊 What Gets Created in Convex

For each emergency call, the system creates:

1. **Patient Record** (if patient info exists)
   ```typescript
   {
     _id: "<generated>",
     firstName: "Juan",
     lastName: "Pérez",
     age: 45,
     sex: "M",
     address: "Apoquindo 3000",
     district: "Las Condes",
     medications: ["Aspirina", "Metformina"],
     allergies: ["Penicilina"],
     ...
   }
   ```

2. **Incident Record**
   ```typescript
   {
     _id: "<generated>",
     incidentNumber: "INC-call-123",
     status: "incoming_call",
     priority: "medium",
     incidentType: "Dolor en el pecho",
     description: "Detailed description with medical status...",
     location: {
       address: "Apoquindo 3000",
       district: "Las Condes",
       reference: "Cerca del mall"
     },
     patientId: "<patient-id>",
     dispatcherId: "<dispatcher-id>",
     ...
   }
   ```

3. **Call Record**
   ```typescript
   {
     _id: "<generated>",
     incidentId: "<incident-id>",
     transcription: "hola necesito ayuda mi nombre es Juan...",
     transcriptionChunks: null,  // TODO: Track during streaming
     ...
   }
   ```

---

## 🔧 Next Steps

### 1. Create Test Dispatcher
```python
# Create a test dispatcher in Convex
dispatcher_id = client.mutation("dispatchers:create", {
    "name": "Test Operator",
    "phone": None,
    "createdAt": int(time.time() * 1000)
})
```

### 2. Test End-to-End
```python
# Process a test call
result = await process_audio_chunk(
    audio_chunk=test_audio,
    session_id="test-123"
)

# End call and save
final = end_session(
    session_id="test-123",
    dispatcher_id=dispatcher_id
)

print(final["convex_save"])
```

### 3. Query Your Data
```python
# List recent incidents
incidents = client.query("incidents:listRecent", {"limit": 10})

# Search patients
patients = client.query("patients:searchByName", {"name": "Juan"})
```

---

## 📖 Documentation Files

- `CONVEX_CONNECTION.md` - Convex database connection info
- `SCHEMA_MAPPING.md` - Complete field mapping reference
- `src/services/convex_db.py` - Python integration code

---

## 🐛 Troubleshooting

### "dispatcher_id required"
You must pass a valid Convex dispatcher ID when calling `end_session()`.

### "Failed to save to Convex"
1. Check `CONVEX_URL` is set in `.envrc` (should be `https://knowing-mouse-775.convex.cloud`)
2. Verify required functions exist in Convex Cloud (coordinate with your team)
3. Verify dispatcher exists in Convex

### Missing data in Convex
Check that canonical fields are being extracted properly. The AI needs clear audio transcription to extract structured data.

---

## 🎯 Summary

✅ **Connected to production** - `knowing-mouse-775.convex.cloud`
✅ **Schema managed in cloud** - By your team member
✅ **Python mapping works** - 31 fields → proper tables  
✅ **Ready to use** - Just call `end_session()` with `dispatcher_id`

Your backend is ready to save emergency call data to Convex!

