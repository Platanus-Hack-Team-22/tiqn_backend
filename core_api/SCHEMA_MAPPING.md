# Schema Mapping - AI Extraction to Convex Database

## Overview

Our AI extracts **31 structured fields** from emergency call transcripts. This document shows how these fields map to the Convex database schema.

---

## Data Flow

```
Audio Chunk → Transcribe → Extract with Claude → Map to Schema → Save to Convex
```

---

## Mapping: Our Canonical Data → Convex Schema

### 1. Patient Information → `patients` table

| Our Field | Their Field | Transformation |
|-----------|-------------|----------------|
| `nombre` | `firstName` | Direct |
| `apellido` | `lastName` | Direct |
| `edad` | `age` | String → Number |
| `sexo` | `sex` | "M" or "F" (already matches) |
| `medicamentos` | `medications` | String → Array |
| `alergias` | `allergies` | String → Array |
| `historia_clinica` | `medicalHistory` | String → Array |
| `direccion` + `numero` | `address` | Combine strings |
| `comuna` | `district` | Direct |

**Example:**
```python
canonical = {
    "nombre": "Juan",
    "apellido": "Pérez",
    "edad": "45",
    "sexo": "M",
    "medicamentos": "Aspirina, Metformina",
    "alergias": "Penicilina"
}

# Maps to:
patient = {
    "firstName": "Juan",
    "lastName": "Pérez",
    "age": 45,
    "sex": "M",
    "medications": ["Aspirina", "Metformina"],
    "allergies": ["Penicilina"],
    "address": canonical.direccion + " " + canonical.numero,
    "district": canonical.comuna
}
```

---

### 2. Incident Information → `incidents` table

| Our Field | Their Field | Transformation |
|-----------|-------------|----------------|
| `codigo` | `priority` | Verde→low, Amarillo→medium, Rojo→critical |
| `motivo` | `incidentType` + `description` | Use for both |
| `direccion` + `numero` | `location.address` | Combine |
| `comuna` | `location.district` | Direct |
| `ubicacion_referencia` | `location.reference` | Direct |
| `google_maps_url` | `location.coordinates` | Parse lat/lng from URL |

**Priority Mapping:**
```python
def map_codigo_to_priority(codigo: str) -> str:
    mapping = {
        "Verde": "low",
        "Amarillo": "medium",
        "Rojo": "critical"
    }
    return mapping.get(codigo, "medium")
```

**Example:**
```python
canonical = {
    "codigo": "Amarillo",
    "motivo": "Dolor en el pecho",
    "direccion": "Apoquindo",
    "numero": "3000",
    "comuna": "Las Condes",
    "ubicacion_referencia": "Cerca del mall"
}

# Maps to:
incident = {
    "priority": "medium",
    "incidentType": "Dolor en el pecho",
    "description": "Dolor en el pecho",
    "location": {
        "address": "Apoquindo 3000",
        "district": "Las Condes",
        "reference": "Cerca del mall"
    }
}
```

---

### 3. Transcription → `calls` table

| Our Field | Their Field | Transformation |
|-----------|-------------|----------------|
| `full_transcript` | `transcription` | Direct |
| Audio chunks | `transcriptionChunks` | Convert to array format |

**Example:**
```python
# Our data:
session = {
    "full_transcript": "hola necesito ayuda mi nombre es Juan...",
    "chunk_count": 5
}

# Maps to:
call = {
    "transcription": "hola necesito ayuda mi nombre es Juan...",
    "transcriptionChunks": [
        {"offset": 0, "speaker": "caller", "text": "hola necesito ayuda"},
        {"offset": 5000, "speaker": "caller", "text": "mi nombre es Juan"},
        # ... etc
    ]
}
```

---

## Fields NOT Used (Yet)

These canonical fields don't have direct mappings in their schema:

| Our Field | Notes |
|-----------|-------|
| `depto` | Could add to `location.reference` |
| `ubicacion_detalle` | Could add to `location.reference` |
| `avdi` | Could add to `incident.description` |
| `estado_respiratorio` | Could add to `incident.description` |
| `consciente` | Could add to `incident.description` |
| `respira` | Could add to `incident.description` |
| `inicio_sintomas` | Could add to `incident.description` |
| `cantidad_rescatistas` | Not in schema yet |
| `recursos_requeridos` | Not in schema yet |
| `estado_basal` | Could add to `patients.notes` |
| `let_dnr` | Could add to `patients.notes` |
| `seguro_salud` | Not in schema yet |
| `aviso_conserjeria` | Could add to `incident.description` |
| `signos_vitales` | Not in schema yet |
| `checklist_url` | Not in schema yet |
| `medico_turno` | Not in schema yet |

**Recommendation:** Store complete canonical data in `incident.description` or add a `rawCanonicalData` field for full audit trail.

---

## Complete Integration Example

```python
# After processing audio chunks:
final_data = end_session("call-123")

# Map to Convex schema:
{
    # Create patient record
    "patient": {
        "firstName": final_data.canonical.nombre,
        "lastName": final_data.canonical.apellido,
        "age": int(final_data.canonical.edad) if final_data.canonical.edad else None,
        "sex": final_data.canonical.sexo,
        "address": f"{final_data.canonical.direccion} {final_data.canonical.numero}",
        "district": final_data.canonical.comuna,
        "medications": split_medications(final_data.canonical.medicamentos),
        "allergies": split_allergies(final_data.canonical.alergias),
        "medicalHistory": split_history(final_data.canonical.historia_clinica),
    },
    
    # Create incident record
    "incident": {
        "incidentNumber": generate_incident_number(),
        "status": "incoming_call",
        "priority": map_codigo(final_data.canonical.codigo),
        "incidentType": final_data.canonical.motivo,
        "description": build_description(final_data.canonical),
        "location": {
            "address": f"{final_data.canonical.direccion} {final_data.canonical.numero}",
            "district": final_data.canonical.comuna,
            "reference": final_data.canonical.ubicacion_referencia,
        },
    },
    
    # Create call record
    "call": {
        "transcription": final_data.full_transcript,
        "transcriptionChunks": build_chunks(session),
    }
}
```

---

## Data Loss Prevention

To prevent losing data that doesn't map cleanly, we recommend:

1. **Add `rawCanonicalData` to incidents:**
   ```typescript
   incidents: defineTable({
     // ... existing fields
     rawCanonicalData: v.optional(v.any()), // Store complete AI extraction
   })
   ```

2. **Or store in description:**
   ```python
   description = f"""
   {canonical.motivo}
   
   Estado: Consciente={canonical.consciente}, Respira={canonical.respira}
   AVDI: {canonical.avdi}
   Inicio: {canonical.inicio_sintomas}
   """
   ```

---

## Next Steps

1. ✅ Schema corrected and saved
2. ⏳ Create Convex mutations for saving data
3. ⏳ Update `src/services/convex_db.py` with mapping logic
4. ⏳ Test integration end-to-end

