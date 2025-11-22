"""Pydantic schemas for emergency data extraction."""

from pydantic import BaseModel, Field


class CanonicalV2(BaseModel):
    """Structured emergency data format for Hatzalah Chile."""

    # Personal Information
    nombre: str = Field(default="", description="First name")
    apellido: str = Field(default="", description="Last name")
    sexo: str = Field(default="", description="Sex: M or F")
    edad: str = Field(default="", description="Age (numeric string)")

    # Location
    direccion: str = Field(default="", description="Street name")
    numero: str = Field(default="", description="Street number")
    comuna: str = Field(default="", description="Municipality/district")
    depto: str = Field(default="", description="Apartment/office number")
    ubicacion_referencia: str = Field(default="", description="Location reference")
    ubicacion_detalle: str = Field(default="", description="Location details")
    google_maps_url: str = Field(default="", description="Generated Google Maps URL")

    # Medical Assessment
    codigo: str = Field(default="Verde", description="Triage code: Verde, Amarillo, Rojo")
    avdi: str = Field(default="", description="AVPU scale: alerta, verbal, dolor, inconsciente")
    estado_respiratorio: str = Field(default="", description="respira or no respira")
    consciente: str = Field(default="", description="si or no")
    respira: str = Field(default="", description="si or no")
    motivo: str = Field(default="", description="Chief complaint/reason for call")
    inicio_sintomas: str = Field(default="", description="Symptom onset time")

    # Resources
    cantidad_rescatistas: str = Field(default="", description="Number of responders needed")
    recursos_requeridos: str = Field(default="", description="Required resources")

    # Medical History
    estado_basal: str = Field(default="", description="Baseline condition")
    let_dnr: str = Field(default="", description="DNR/advance directives")
    historia_clinica: str = Field(default="", description="Clinical history")
    medicamentos: str = Field(default="", description="Current medications")
    alergias: str = Field(default="", description="Allergies")

    # Administrative
    seguro_salud: str = Field(default="", description="Health insurance")
    aviso_conserjeria: str = Field(default="", description="Building concierge notification")
    signos_vitales: str = Field(default="", description="Vital signs")
    checklist_url: str = Field(default="", description="Checklist URL")
    medico_turno: str = Field(default="", description="On-duty physician")


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

