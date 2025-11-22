# Coordinate with Your Team - Real-Time Updates

## ✅ What's Done (Your Python Backend)

Your Python backend is now ready to update the `incidents` table in real-time as data comes in!

**Changes Made:**
1. ✅ Added `update_incident_realtime()` method to `ConvexService`
2. ✅ Modified `process_audio_chunk()` to accept `dispatcher_id` and `update_convex` parameters
3. ✅ Automatically updates Convex after each audio chunk is processed
4. ✅ Returns `convex_update` status in the result

---

## 🎯 What Your Team Needs to Do

### 1. Update Convex Schema (Incidents Table)

Your team member needs to add these fields to the `incidents` table in Convex Cloud:

```typescript
incidents: defineTable({
  // === EXISTING FIELDS (keep these) ===
  incidentNumber: v.string(),
  status: v.union(...),
  priority: v.union(...),
  incidentType: v.optional(v.string()),
  description: v.optional(v.string()),
  location: v.object({...}),
  dispatcherId: v.id("dispatchers"),
  patientId: v.optional(v.id("patients")),
  
  // === NEW FIELDS - Add these for real-time updates ===
  
  // Call Tracking
  callSessionId: v.optional(v.string()),      // Session ID from your Python backend
  lastUpdated: v.number(),                    // Timestamp of last update
  
  // Patient Info (extracted during call)
  patientName: v.optional(v.string()),        // nombre + apellido
  patientAge: v.optional(v.number()),         // edad
  patientSex: v.optional(v.string()),         // sexo (M/F)
  
  // Medical Status
  consciousness: v.optional(v.string()),      // consciente (si/no)
  breathing: v.optional(v.string()),          // respira (si/no)
  avdi: v.optional(v.string()),               // AVPU scale
  respiratoryStatus: v.optional(v.string()),  // estado_respiratorio
  
  // Medical Details
  symptomOnset: v.optional(v.string()),       // inicio_sintomas
  medicalHistory: v.optional(v.string()),     // historia_clinica
  currentMedications: v.optional(v.string()), // medicamentos
  allergies: v.optional(v.string()),          // alergias
  vitalSigns: v.optional(v.string()),         // signos_vitales
  
  // Location Details
  apartment: v.optional(v.string()),          // depto
  locationDetail: v.optional(v.string()),     // ubicacion_detalle
  
  // Resources
  requiredRescuers: v.optional(v.string()),   // cantidad_rescatistas
  requiredResources: v.optional(v.string()),  // recursos_requeridos
  
  // Administrative
  healthInsurance: v.optional(v.string()),    // seguro_salud
  conciergeNotified: v.optional(v.string()),  // aviso_conserjeria
  
  // Complete Data
  fullTranscript: v.optional(v.string()),     // Live transcript
  rawCanonicalData: v.optional(v.any()),      // All 31 fields as JSON
})
  .index("by_dispatcher", ["dispatcherId"])
  .index("by_patient", ["patientId"])
  .index("by_status", ["status"])
  .index("by_session", ["callSessionId"]);  // NEW INDEX - Important!
```

---

### 2. Create Convex Mutation

Your team needs to create this mutation in Convex:

**File:** `convex/incidents.ts`

```typescript
import { mutation } from "./_generated/server";
import { v } from "convex/values";

export const createOrUpdate = mutation({
  args: {
    // Required
    callSessionId: v.string(),
    dispatcherId: v.id("dispatchers"),
    
    // Optional - only provided fields will be updated
    priority: v.optional(v.union(
      v.literal("low"),
      v.literal("medium"),
      v.literal("high"),
      v.literal("critical")
    )),
    
    // Patient data
    patientName: v.optional(v.string()),
    patientAge: v.optional(v.number()),
    patientSex: v.optional(v.string()),
    consciousness: v.optional(v.string()),
    breathing: v.optional(v.string()),
    avdi: v.optional(v.string()),
    respiratoryStatus: v.optional(v.string()),
    
    // Medical details
    symptomOnset: v.optional(v.string()),
    medicalHistory: v.optional(v.string()),
    currentMedications: v.optional(v.string()),
    allergies: v.optional(v.string()),
    vitalSigns: v.optional(v.string()),
    
    // Location
    location: v.optional(v.object({
      address: v.string(),
      district: v.optional(v.string()),
      reference: v.optional(v.string()),
    })),
    apartment: v.optional(v.string()),
    locationDetail: v.optional(v.string()),
    
    // Resources
    requiredRescuers: v.optional(v.string()),
    requiredResources: v.optional(v.string()),
    
    // Administrative
    healthInsurance: v.optional(v.string()),
    conciergeNotified: v.optional(v.string()),
    
    // Incident info
    incidentType: v.optional(v.string()),
    description: v.optional(v.string()),
    
    // Complete data
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
      // CREATE new incident (first chunk of call)
      const incidentId = await ctx.db.insert("incidents", {
        callSessionId,
        dispatcherId,
        incidentNumber: `INC-${callSessionId.slice(-8)}`,
        status: "incoming_call",
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

---

### 3. Update Their WebSocket Handler

Your team member needs to pass `dispatcher_id` when calling your function:

**Before:**
```python
result = await process_audio_chunk(
    audio_chunk=audio_data,
    session_id=call_id
)
```

**After:**
```python
result = await process_audio_chunk(
    audio_chunk=audio_data,
    session_id=call_id,
    dispatcher_id=dispatcher_id,  # ← Add this!
    update_convex=True             # ← Enable real-time updates
)

# Check if Convex updated successfully
if result.get("convex_update", {}).get("success"):
    print(f"✅ Incident updated: {result['convex_update']['incident_id']}")
else:
    print(f"⚠️ Convex update failed: {result.get('convex_update', {}).get('error')}")
```

**How to get `dispatcher_id`:**
```python
# Get from authenticated user session
dispatcher_id = request.user.convex_id  # Or however they track operators

# Or create/get dispatcher at start of shift
dispatcher_id = convex.query("dispatchers:getByEmail", {
    "email": operator_email
})["_id"]
```

---

## 📊 What Happens Now

### Before (Old Flow)
```
Audio Chunk → Process → Return to UI
Audio Chunk → Process → Return to UI
Audio Chunk → Process → Return to UI
Call Ends → Save everything to Convex
```

### After (New Flow with Real-Time Updates)
```
Audio Chunk → Process → Update Convex → Return to UI
Audio Chunk → Process → Update Convex → Return to UI
Audio Chunk → Process → Update Convex → Return to UI
Call Ends → Data already in Convex!
```

**Every 5 seconds**, the incident record updates with:
- ✅ Latest transcript
- ✅ New patient data (name, age, address)
- ✅ Medical status (consciousness, breathing)
- ✅ Updated priority
- ✅ Complete canonical data

---

## 🧪 Testing

### 1. Test Without Real-Time Updates (Works Now)
```python
# Disable Convex updates
result = await process_audio_chunk(
    audio_chunk=audio_data,
    session_id=call_id,
    update_convex=False  # No Convex updates
)
```

### 2. Test With Real-Time Updates (After Convex Changes)
```python
# Enable Convex updates
result = await process_audio_chunk(
    audio_chunk=audio_data,
    session_id=call_id,
    dispatcher_id="<test-dispatcher-id>",
    update_convex=True
)

# Check result
assert result["convex_update"]["success"] == True
print(f"Incident ID: {result['convex_update']['incident_id']}")
```

### 3. Verify in Convex Dashboard

After processing a few chunks, check Convex Dashboard to see:
- Incident record with `callSessionId`
- Fields updating in real-time
- `fullTranscript` growing with each chunk
- `lastUpdated` timestamp changing

---

## 🔧 Configuration

### Enable/Disable Real-Time Updates

**Enable (default):**
```python
result = await process_audio_chunk(
    audio_chunk=audio_data,
    session_id=call_id,
    dispatcher_id=dispatcher_id,
    update_convex=True  # ← Default
)
```

**Disable (for testing):**
```python
result = await process_audio_chunk(
    audio_chunk=audio_data,
    session_id=call_id,
    update_convex=False  # ← No database updates
)
```

### Only Update at End of Call

If you prefer to only save at the end:

```python
# During call - no Convex updates
result = await process_audio_chunk(
    audio_chunk=audio_data,
    session_id=call_id,
    update_convex=False
)

# At end of call - save once
final_data = end_session(
    session_id=call_id,
    dispatcher_id=dispatcher_id,
    save_to_convex=True
)
```

---

## 📖 Documentation

- **`SCHEMA_UPDATES.md`** - List of fields to add to schema
- **`REALTIME_UPDATES.md`** - Complete implementation guide
- **`HOW_IT_WORKS.md`** - Updated with real-time flow
- **`src/services/convex_db.py`** - Python implementation
- **`src/core.py`** - Modified process function

---

## ✅ Summary

**Your backend is ready!** Your team just needs to:
1. Add fields to `incidents` schema in Convex Cloud
2. Create `incidents:createOrUpdate` mutation
3. Pass `dispatcher_id` when calling your function
4. Deploy and test!

**Benefits:**
- ✨ Operators see data fill in real-time
- 📊 Dashboard shows live incident status
- 🔍 Can query/filter by medical conditions during call
- 💾 Complete audit trail with timestamps
- 🚀 No waiting until call ends to see data

