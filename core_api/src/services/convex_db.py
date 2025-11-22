"""Convex database service for saving emergency call data."""

import logging
from typing import Any
from convex import ConvexClient

from ..config import settings
from ..schemas import CanonicalV2

logger = logging.getLogger(__name__)


def split_string_to_array(value: str) -> list[str]:
    """Split comma-separated string into array, filtering empty values."""
    if not value or not value.strip():
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def map_codigo_to_priority(codigo: str) -> str:
    """Map triage code to priority level."""
    mapping = {
        "Verde": "low",
        "Amarillo": "medium",
        "Rojo": "critical",
    }
    return mapping.get(codigo, "medium")


def safe_int(value: str) -> int | None:
    """Safely convert string to int."""
    try:
        return int(value) if value else None
    except (ValueError, TypeError):
        return None


def build_incident_description(canonical: CanonicalV2) -> str:
    """Build comprehensive incident description from canonical data."""
    parts = []
    
    # Primary complaint
    if canonical.motivo:
        parts.append(f"Motivo: {canonical.motivo}")
    
    # Medical status
    status_parts = []
    if canonical.consciente:
        status_parts.append(f"Consciente: {canonical.consciente}")
    if canonical.respira:
        status_parts.append(f"Respira: {canonical.respira}")
    if canonical.avdi:
        status_parts.append(f"AVDI: {canonical.avdi}")
    if canonical.estado_respiratorio:
        status_parts.append(f"Estado respiratorio: {canonical.estado_respiratorio}")
    
    if status_parts:
        parts.append("Estado: " + ", ".join(status_parts))
    
    # Timing
    if canonical.inicio_sintomas:
        parts.append(f"Inicio: {canonical.inicio_sintomas}")
    
    # Additional details
    if canonical.ubicacion_detalle:
        parts.append(f"Ubicación detalle: {canonical.ubicacion_detalle}")
    if canonical.depto:
        parts.append(f"Depto/Oficina: {canonical.depto}")
    if canonical.aviso_conserjeria:
        parts.append(f"Conserjería: {canonical.aviso_conserjeria}")
    
    return "\n".join(parts) if parts else canonical.motivo or ""


class ConvexService:
    """Service for interacting with Convex database."""
    
    def __init__(self):
        """Initialize Convex client."""
        if not settings.CONVEX_URL:
            raise ValueError("CONVEX_URL not configured")
        
        self.client = ConvexClient(settings.CONVEX_URL)
    
    def save_emergency_call(
        self,
        session_id: str,
        full_transcript: str,
        canonical_data: CanonicalV2 | dict,
        duration_seconds: float,
        chunk_count: int,
        dispatcher_id: str,  # Required - the operator handling the call
    ) -> dict[str, Any]:
        """
        Save emergency call data to Convex database.
        
        This creates:
        1. A patient record (if new patient data exists)
        2. An incident record
        3. A call record with transcription
        
        Args:
            session_id: Unique call identifier
            full_transcript: Complete transcript of the call
            canonical_data: Structured emergency data (31 fields)
            duration_seconds: Call duration
            chunk_count: Number of audio chunks processed
            dispatcher_id: Convex ID of the dispatcher handling this call
            
        Returns:
            Dict with created IDs and success status
        """
        # Convert CanonicalV2 to dict if needed
        if isinstance(canonical_data, CanonicalV2):
            canonical = canonical_data
        else:
            canonical = CanonicalV2(**canonical_data)
        
        try:
            # Step 1: Create patient record (if we have patient data)
            patient_id = None
            if canonical.nombre or canonical.apellido:
                patient_data = {
                    "firstName": canonical.nombre or "Unknown",
                    "lastName": canonical.apellido or "",
                    "age": safe_int(canonical.edad),
                    "sex": canonical.sexo if canonical.sexo in ["M", "F"] else None,
                    "address": f"{canonical.direccion} {canonical.numero}".strip() if canonical.direccion else None,
                    "city": None,  # Not extracted yet
                    "district": canonical.comuna or None,
                    "coordinates": None,  # TODO: Parse from google_maps_url
                    "medicalHistory": split_string_to_array(canonical.historia_clinica),
                    "medications": split_string_to_array(canonical.medicamentos),
                    "allergies": split_string_to_array(canonical.alergias),
                    "bloodType": None,  # Not extracted
                    "emergencyContact": None,  # Not extracted yet
                    "photoUrl": None,
                    "notes": canonical.estado_basal or None,
                    "createdAt": self.client.query("system:now"),
                    "updatedAt": self.client.query("system:now"),
                }
                
                # Remove None values
                patient_data = {k: v for k, v in patient_data.items() if v is not None}
                
                # Save patient
                patient_id = self.client.mutation("patients:create", patient_data)
            
            # Step 2: Create incident record
            incident_data = {
                "status": "incoming_call",
                "priority": map_codigo_to_priority(canonical.codigo),
                "incidentType": canonical.motivo or "Emergency Call",
                "description": build_incident_description(canonical),
                "address": f"{canonical.direccion} {canonical.numero}".strip() or "Unknown",
                "district": canonical.comuna or None,
                "reference": canonical.ubicacion_referencia or None,
                "dispatcherId": dispatcher_id,
                "patientId": patient_id,
            }
            
            # Save incident
            incident_id = self.client.mutation("incidents:create", incident_data)
            
            # Step 3: Create call record with transcription
            call_data = {
                "incidentId": incident_id,
                "transcription": full_transcript,
                "transcriptionChunks": None,  # TODO: Track chunks during streaming
                "createdAt": self.client.query("system:now"),
            }
            
            call_id = self.client.mutation("calls:create", call_data)
            
            return {
                "success": True,
                "patient_id": patient_id,
                "incident_id": incident_id,
                "call_id": call_id,
                "session_id": session_id,
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to save to Convex: {e}",
            }
    
    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        """Get incident by Convex ID."""
        try:
            return self.client.query("incidents:get", {"id": incident_id})
        except Exception as e:
            print(f"Error fetching incident: {e}")
            return None
    
    def get_patient(self, patient_id: str) -> dict[str, Any] | None:
        """Get patient by Convex ID."""
        try:
            return self.client.query("patients:get", {"id": patient_id})
        except Exception as e:
            print(f"Error fetching patient: {e}")
            return None
    
    def list_recent_incidents(self, limit: int = 10) -> list[dict[str, Any]]:
        """List recent incidents."""
        try:
            return self.client.query("incidents:listRecent", {"limit": limit})
        except Exception as e:
            print(f"Error listing incidents: {e}")
            return []
    
    def update_incident_realtime(
        self,
        session_id: str,
        canonical_data: CanonicalV2,
        full_transcript: str,
        dispatcher_id: str,
    ) -> dict[str, Any]:
        """
        Update incident record in real-time as data comes in.
        
        This is called after EACH audio chunk is processed, updating the incident
        with the latest extracted data. Creates the incident on first call.
        
        Args:
            session_id: Unique call identifier
            canonical_data: Latest extracted emergency data
            full_transcript: Current complete transcript
            dispatcher_id: Convex ID of dispatcher handling the call
            
        Returns:
            Dict with success status and incident ID
        """
        # Convert CanonicalV2 to dict if needed
        if isinstance(canonical_data, CanonicalV2):
            canonical = canonical_data
        else:
            canonical = CanonicalV2(**canonical_data)
        
        try:
            logger.info(f"Creating/Updating incident for session {session_id}")
            # Build update data from canonical
            update_data = {
                "callSessionId": session_id,
                "dispatcherId": dispatcher_id,
                
                # Priority from triage code
                "priority": map_codigo_to_priority(canonical.codigo),
                
                # Patient info
                "firstName": canonical.nombre or None,
                "lastName": canonical.apellido or None,
                "patientAge": safe_int(canonical.edad),
                "patientSex": canonical.sexo if canonical.sexo in ["M", "F"] else None,
                
                # Medical status
                "consciousness": canonical.consciente or None,
                "breathing": canonical.respira or None,
                "avdi": canonical.avdi or None,
                "respiratoryStatus": canonical.estado_respiratorio or None,
                
                # Medical details
                "symptomOnset": canonical.inicio_sintomas or None,
                "medicalHistory": canonical.historia_clinica or None,
                "currentMedications": canonical.medicamentos or None,
                "allergies": canonical.alergias or None,
                "vitalSigns": canonical.signos_vitales or None,
                
                # Location (separate fields, not nested object)
                "address": f"{canonical.direccion} {canonical.numero}".strip() or None,
                "district": canonical.comuna or None,
                "reference": canonical.ubicacion_referencia or None,
                "apartment": canonical.depto or None,
                
                # Resources
                "requiredRescuers": canonical.cantidad_rescatistas or None,
                "requiredResources": canonical.recursos_requeridos or None,
                
                # Administrative
                "healthInsurance": canonical.seguro_salud or None,
                "conciergeNotified": canonical.aviso_conserjeria or None,
                
                # Incident info
                "incidentType": canonical.motivo or None,
                "description": build_incident_description(canonical),
                
                # Complete data
                "fullTranscript": full_transcript,
                "rawCanonicalData": canonical.model_dump(),
            }
            
            # Remove None values for cleaner database
            update_data = {k: v for k, v in update_data.items() if v is not None}
            
            # Call Convex mutation (creates if doesn't exist, updates if it does)
            incident_id = self.client.mutation("incidents:createOrUpdate", update_data)
            logger.info(f"Successfully updated incident {incident_id}")
            
            return {
                "success": True,
                "incident_id": incident_id,
                "session_id": session_id,
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to update incident in Convex: {e}",
            }
    
    def close(self):
        """Close the Convex client connection."""
        if hasattr(self, 'client'):
            self.client.close()


# Global Convex service instance
_convex_service: ConvexService | None = None


def get_convex_service() -> ConvexService:
    """Get or create the global Convex service instance."""
    global _convex_service
    
    if _convex_service is None:
        _convex_service = ConvexService()
    
    return _convex_service
