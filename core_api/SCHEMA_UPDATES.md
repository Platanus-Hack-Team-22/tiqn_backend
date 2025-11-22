# Incidents Table Schema Updates

## Fields to Add to `incidents` Table

Add these fields to store patient/medical data extracted during the call:

```typescript
incidents: defineTable({
  // === EXISTING FIELDS ===
  incidentNumber: v.string(),
  status: v.union(...),
  priority: v.union(...),
  incidentType: v.optional(v.string()),
  description: v.optional(v.string()),
  location: v.object({...}),
  dispatcherId: v.id("dispatchers"),
  patientId: v.optional(v.id("patients")),
  
  // === NEW FIELDS - Patient Information (extracted during call) ===
  
  // Patient Basic Info
  patientName: v.optional(v.string()),        // nombre + apellido combined
  patientAge: v.optional(v.number()),         // edad
  patientSex: v.optional(v.string()),         // sexo (M/F)
  
  // Medical Status (real-time updates)
  consciousness: v.optional(v.string()),      // consciente (si/no)
  breathing: v.optional(v.string()),          // respira (si/no)
  avdi: v.optional(v.string()),               // AVPU scale: alerta/verbal/dolor/inconsciente
  respiratoryStatus: v.optional(v.string()),  // estado_respiratorio (respira/no respira)
  
  // Medical Details
  symptomOnset: v.optional(v.string()),       // inicio_sintomas
  medicalHistory: v.optional(v.string()),     // historia_clinica
  currentMedications: v.optional(v.string()), // medicamentos
  allergies: v.optional(v.string()),          // alergias
  vitalSigns: v.optional(v.string()),         // signos_vitales
  
  // Location Details (from canonical)
  apartment: v.optional(v.string()),          // depto
  locationDetail: v.optional(v.string()),     // ubicacion_detalle
  
  // Resources & Response
  requiredRescuers: v.optional(v.string()),   // cantidad_rescatistas
  requiredResources: v.optional(v.string()),  // recursos_requeridos
  
  // Administrative
  healthInsurance: v.optional(v.string()),    // seguro_salud
  conciergeNotified: v.optional(v.string()),  // aviso_conserjeria
  
  // Call Metadata
  callSessionId: v.optional(v.string()),      // session_id for tracking
  fullTranscript: v.optional(v.string()),     // Updated in real-time
  lastUpdated: v.number(),                    // Timestamp of last update
  
  // Raw data for auditing (optional)
  rawCanonicalData: v.optional(v.any()),      // Complete canonical object
})
  .index("by_dispatcher", ["dispatcherId"])
  .index("by_patient", ["patientId"])
  .index("by_status", ["status"])
  .index("by_session", ["callSessionId"]);  // NEW: Find by session_id
```

## Why These Fields?

These fields allow the operator/dashboard to see:
- **Real-time medical status** as caller speaks
- **Progressive data collection** (name appears after 10s, age after 15s, etc.)
- **Search and filter** by medical conditions
- **Resource planning** before dispatch
- **Complete audit trail** with timestamps

## Alternative: Minimal Approach

If you want to keep the schema smaller, you could just add:

```typescript
incidents: defineTable({
  // ... existing fields ...
  
  // Store everything in these 2 fields:
  canonicalData: v.optional(v.any()),     // All 31 fields as JSON
  fullTranscript: v.optional(v.string()), // Live transcript
  lastUpdated: v.number(),                // Last update timestamp
  callSessionId: v.optional(v.string()),  // Session tracking
})
```

This is simpler but makes querying harder (can't filter by "all conscious patients" easily).

## Recommended Approach

**Use individual fields** for data you want to query/filter on:
- Patient name, age, sex
- Medical status (consciousness, breathing)
- Priority-related fields

**Use `rawCanonicalData`** for everything else as backup.

---

## Implementation Steps

1. ✅ Update schema in Convex Cloud (your team member does this)
2. ✅ Create mutation: `incidents:createOrUpdate` (see below)
3. ✅ Modify Python to call update after each chunk
4. ✅ Test real-time updates

See code examples in the sections below.

