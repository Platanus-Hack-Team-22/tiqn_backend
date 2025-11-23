"""Pydantic schemas for emergency data extraction."""

from typing import Optional
from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    """Geographical coordinates."""

    lat: float
    lng: float


class CanonicalV2(BaseModel):
    """Structured emergency data format for tiqn."""

    # Status & Priority (optional for backward compatibility)
    status: Optional[str] = Field(
        default=None,
        description="Incident status: incoming_call, confirmed, rescuer_assigned, in_progress, completed, cancelled, active",
    )
    priority: Optional[str] = Field(
        default=None,
        description="Priority level: low, medium, high, critical",
    )

    # Basic Info
    incidentType: Optional[str] = Field(
        default=None, description="Type of incident"
    )
    description: Optional[str] = Field(
        default=None, description="Incident description"
    )

    # Location (split into separate fields)
    address: Optional[str] = Field(default=None, description="Street address")
    district: Optional[str] = Field(default=None, description="Municipality/district")
    reference: Optional[str] = Field(default=None, description="Location reference")
    coordinates: Optional[Coordinates] = Field(
        default=None, description="Geographic coordinates"
    )

    # Relationships
    dispatcherId: Optional[str] = Field(
        default=None, description="Dispatcher ID (can be ID or string from Python)"
    )
    patientId: Optional[str] = Field(
        default=None, description="Patient ID (Convex reference)"
    )

    # Real-time call tracking
    callSessionId: Optional[str] = Field(
        default=None, description="Call session identifier"
    )
    externalCallId: Optional[str] = Field(
        default=None, description="Alias for callSessionId from Python backend"
    )
    liveTranscript: Optional[str] = Field(
        default=None, description="Real-time interim transcript updates"
    )
    lastUpdated: Optional[int] = Field(default=None, description="Last update timestamp")

    # Patient info (extracted during call)
    firstName: Optional[str] = Field(default=None, description="First name")
    lastName: Optional[str] = Field(default=None, description="Last name")
    patientAge: Optional[int] = Field(default=None, description="Age")
    patientSex: Optional[str] = Field(default=None, description="Sex: M or F")

    # Medical status
    consciousness: Optional[str] = Field(
        default=None, description="Consciousness level (si/no)"
    )
    breathing: Optional[str] = Field(
        default=None, description="Breathing status (si/no)"
    )
    avdi: Optional[str] = Field(
        default=None, description="AVPU scale: alerta, verbal, dolor, inconsciente"
    )
    respiratoryStatus: Optional[str] = Field(
        default=None, description="respira or no respira"
    )

    # Medical details
    symptomOnset: Optional[str] = Field(
        default=None, description="Symptom onset time"
    )
    medicalHistory: Optional[str] = Field(default=None, description="Clinical history")
    currentMedications: Optional[str] = Field(
        default=None, description="Current medications"
    )
    allergies: Optional[str] = Field(default=None, description="Allergies")
    vitalSigns: Optional[str] = Field(default=None, description="Vital signs")

    # Location details
    apartment: Optional[str] = Field(
        default=None, description="Apartment/office number"
    )

    # Resources
    requiredRescuers: Optional[str] = Field(
        default=None, description="Number of responders needed"
    )
    requiredResources: Optional[str] = Field(
        default=None, description="Required resources"
    )

    # Administrative
    healthInsurance: Optional[str] = Field(default=None, description="Health insurance")
    conciergeNotified: Optional[str] = Field(
        default=None, description="Building concierge notification"
    )

    # Complete data
    fullTranscript: Optional[str] = Field(default=None, description="Full transcript")
    rawCanonicalData: Optional[dict] = Field(
        default=None, description="Raw canonical data"
    )

    # Legacy fields (kept for backward compatibility)
    nombre: str = Field(default="", description="First name (legacy)")
    apellido: str = Field(default="", description="Last name (legacy)")
    sexo: str = Field(default="", description="Sex: M or F (legacy)")
    edad: str = Field(default="", description="Age (numeric string, legacy)")
    direccion: str = Field(default="", description="Street name (legacy)")
    numero: str = Field(default="", description="Street number (legacy)")
    comuna: str = Field(default="", description="Municipality/district (legacy)")
    depto: str = Field(default="", description="Apartment/office number (legacy)")
    ubicacion_referencia: str = Field(
        default="", description="Location reference (legacy)"
    )
    ubicacion_detalle: str = Field(default="", description="Location details (legacy)")
    google_maps_url: str = Field(
        default="", description="Generated Google Maps URL (legacy)"
    )
    codigo: str = Field(
        default="Verde", description="Triage code: Verde, Amarillo, Rojo (legacy)"
    )
    estado_respiratorio: str = Field(
        default="", description="respira or no respira (legacy)"
    )
    consciente: str = Field(default="", description="si or no (legacy)")
    respira: str = Field(default="", description="si or no (legacy)")
    motivo: str = Field(default="", description="Chief complaint/reason for call (legacy)")
    inicio_sintomas: str = Field(default="", description="Symptom onset time (legacy)")
    cantidad_rescatistas: str = Field(
        default="", description="Number of responders needed (legacy)"
    )
    recursos_requeridos: str = Field(
        default="", description="Required resources (legacy)"
    )
    estado_basal: str = Field(default="", description="Baseline condition (legacy)")
    let_dnr: str = Field(default="", description="DNR/advance directives (legacy)")
    historia_clinica: str = Field(default="", description="Clinical history (legacy)")
    medicamentos: str = Field(default="", description="Current medications (legacy)")
    alergias: str = Field(default="", description="Allergies (legacy)")
    seguro_salud: str = Field(default="", description="Health insurance (legacy)")
    aviso_conserjeria: str = Field(
        default="", description="Building concierge notification (legacy)"
    )
    signos_vitales: str = Field(default="", description="Vital signs (legacy)")
    checklist_url: str = Field(default="", description="Checklist URL (legacy)")
    medico_turno: str = Field(default="", description="On-duty physician (legacy)")


class TranscriptionChunk(BaseModel):
    """Real-time transcription chunk from streaming."""

    session_id: str
    chunk_text: str
    timestamp: float
    is_final: bool = False


class StreamResponse(BaseModel):
    """Response sent back through WebSocket for each chunk."""

    chunk_text: str
    full_transcript: str
    canonical: CanonicalV2
    timestamp: float


class TokenResponse(BaseModel):
    """Azure Speech Service token response."""

    token: str
    region: str | None
    endpoint: str | None
    expires_in: int = 600


class TranscriptionResponse(BaseModel):
    """File-based transcription response."""

    text: str
    canonical_data: CanonicalV2
    duration_seconds: int
