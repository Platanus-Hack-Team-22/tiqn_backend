"""Canonical data extraction using Claude."""

import json
import re
from typing import Any

from anthropic import Anthropic

from ..config import settings
from ..schemas import CanonicalV2

# Street to commune mapping for Santiago, Chile
STREET_COMMUNE_HINTS = [
    (re.compile(r"\bestoril\b", re.I), "Las Condes"),
    (re.compile(r"\bapoquindo\b", re.I), "Las Condes"),
    (re.compile(r"\bbilbao\b", re.I), "Las Condes"),
    (re.compile(r"\blas\s+condes\b", re.I), "Las Condes"),
    (re.compile(r"\bkennedy\b", re.I), "Las Condes"),
    (re.compile(r"\bprovidencia\b", re.I), "Providencia"),
    (re.compile(r"\blos\s+leones\b", re.I), "Providencia"),
    (re.compile(r"\bprovidence\b", re.I), "Providencia"),
    (re.compile(r"\balameda\b", re.I), "Santiago"),
    (re.compile(r"\bmerced\b", re.I), "Santiago"),
    (re.compile(r"\bsan\s+pablo\b", re.I), "Santiago"),
    (re.compile(r"\ballamand\b", re.I), "Huechuraba"),
    (re.compile(r"\bvitacura\b", re.I), "Vitacura"),
    (re.compile(r"\bmanquehue\b", re.I), "Vitacura"),
    (re.compile(r"\bmacul\b", re.I), "Macul"),
    (re.compile(r"\bñuble\b", re.I), "Ñuñoa"),
    (re.compile(r"\birarrazaval\b", re.I), "Ñuñoa"),
    (re.compile(r"\bgrecia\b", re.I), "Ñuñoa"),
    (re.compile(r"\bla\s+florida\b", re.I), "La Florida"),
    (re.compile(r"\bgran avenida\b", re.I), "La Cisterna"),
]

SYSTEM_PROMPT = """Eres un operador experto de tiqn. Debes completar la ficha SOS y los campos de seguimiento de una emergencia a partir de la transcripción.

IMPORTANTE: Esta transcripción puede ser INCREMENTAL (solo un fragmento nuevo de una llamada en curso). Tu tarea es extraer SOLO la información nueva que aparece en este fragmento específico.

Reglas estrictas:
1. Extrae ÚNICAMENTE datos que se mencionan EXPLÍCITAMENTE en este fragmento
2. Si no existe información confirmada, deja el campo como cadena vacía ""
3. NO escribas "desconocido", "n/a" ni equivalentes - usa cadenas vacías ""
4. Si en este fragmento no aparece ningún dato nuevo, devuelve todas las cadenas vacías
5. Usa español de Chile

Campos específicos:
- direccion: solo nombre de calle (sin "emergencia", "ayuda", etc.)
- numero: solo dígitos
- comuna: nombre formal de la comuna
- depto: referencias como "oficina 111", "departamento 502"
- ubicacion_detalle: detalles del lugar ("gimnasio edificio", "cancha fútbol")
- avdi: exactamente "alerta", "verbal", "dolor" o "inconsciente" (o "" si no se menciona)
- estado_respiratorio: "respira" o "no respira" (o "" si no se menciona)
- consciente/respira: "si" o "no" (o "" si no se menciona)
- codigo: "Verde", "Amarillo" o "Rojo"
- inicio_sintomas: expresiones como "súbito", "hace 2 horas" (o "" si no se menciona)
- cantidad_rescatistas/recursos_requeridos: solo si se solicitan explícitamente
- campos médicos (historia_clinica, medicamentos, alergias, etc.): solo si se mencionan

Devuelve SOLO JSON plano, sin markdown."""


def build_user_prompt(
    transcript_chunk: str, existing_data: CanonicalV2 | None = None
) -> str:
    """Build the user prompt for Claude."""

    context = ""
    if existing_data:
        # Show existing data as context
        existing_dict = existing_data.model_dump()
        filled_fields = {k: v for k, v in existing_dict.items() if v and v != "Verde"}
        if filled_fields:
            context = f"\n\nDatos ya extraídos en fragmentos anteriores:\n{json.dumps(filled_fields, ensure_ascii=False, indent=2)}\n"

    return f"""Fragmento de transcripción (es-CL):{context}

Transcripción actual:
{transcript_chunk}

Extrae SOLO la información nueva de este fragmento y devuelve JSON con este esquema exacto:
{{
  "nombre": "",
  "apellido": "",
  "direccion": "",
  "numero": "",
  "comuna": "",
  "depto": "",
  "ubicacion_referencia": "",
  "ubicacion_detalle": "",
  "google_maps_url": "",
  "codigo": "Verde",
  "sexo": "",
  "edad": "",
  "avdi": "",
  "estado_respiratorio": "",
  "consciente": "",
  "respira": "",
  "motivo": "",
  "inicio_sintomas": "",
  "cantidad_rescatistas": "",
  "recursos_requeridos": "",
  "estado_basal": "",
  "let_dnr": "",
  "historia_clinica": "",
  "medicamentos": "",
  "alergias": "",
  "seguro_salud": "",
  "aviso_conserjeria": "",
  "signos_vitales": "",
  "checklist_url": "",
  "medico_turno": ""
}}

Recuerda: si no hay información nueva en este fragmento, devuelve todas las cadenas vacías."""


async def extract_with_claude(
    transcript_chunk: str,
    existing_canonical: CanonicalV2 | None = None,
) -> CanonicalV2:
    """Extract canonical data from transcript chunk using Claude."""

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    user_prompt = build_user_prompt(transcript_chunk, existing_canonical)

    try:
        message = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=2048,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Extract JSON from response
        content = message.content[0].text if message.content else ""

        # Parse JSON
        canonical_dict = parse_json_response(content)
        if not canonical_dict:
            # If parsing failed, return existing or default
            return existing_canonical or CanonicalV2()

        # Create new canonical object
        new_canonical = CanonicalV2(**canonical_dict)

        # Merge with existing data
        if existing_canonical:
            merged = merge_canonical_data(existing_canonical, new_canonical)
        else:
            merged = new_canonical

        # Post-process
        merged = post_process_canonical(merged, transcript_chunk)

        return merged

    except Exception as e:
        print(f"Error extracting with Claude: {e}")
        return existing_canonical or CanonicalV2()


def parse_json_response(text: str) -> dict[str, Any] | None:
    """Parse JSON from Claude's response, handling markdown code blocks."""
    # Remove markdown code blocks
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = text.strip()

    # Find JSON object
    first_brace = text.find("{")
    last_brace = text.rfind("}")

    if first_brace == -1 or last_brace == -1:
        return None

    json_text = text[first_brace : last_brace + 1]

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return None


def merge_canonical_data(existing: CanonicalV2, new_data: CanonicalV2) -> CanonicalV2:
    """Merge new canonical data with existing data."""
    existing_dict = existing.model_dump()
    new_dict = new_data.model_dump()

    # Update only non-empty fields
    for key, value in new_dict.items():
        if value and value != "Verde":  # Don't overwrite with empty or default values
            existing_dict[key] = value

    return CanonicalV2(**existing_dict)


def post_process_canonical(data: CanonicalV2, transcript: str) -> CanonicalV2:
    """Post-process canonical data for cleanup and inference."""

    # Sanitize address
    data.direccion = sanitize_direccion(data.direccion)
    data.numero = re.sub(r"[^0-9]", "", data.numero)
    data.comuna = sanitize_comuna(data.comuna)

    # Capitalize names
    data.nombre = capitalize_words(data.nombre)
    data.apellido = capitalize_words(data.apellido)
    data.medico_turno = capitalize_words(data.medico_turno)

    # Normalize medical fields
    data.sexo = normalize_sexo(data.sexo, transcript)
    data.edad = normalize_edad(data.edad, transcript)
    data.codigo = normalize_codigo(data.codigo, transcript)
    data.avdi = normalize_avdi(data.avdi, data.consciente, transcript)
    data.estado_respiratorio = normalize_respiratorio(
        data.estado_respiratorio, data.respira, transcript
    )
    data.consciente = normalize_yes_no(data.consciente)
    data.respira = normalize_yes_no(data.respira)

    # Infer comuna from street name if not set
    if not data.comuna or data.comuna.lower() in [
        "santiago",
        "región metropolitana",
        "rm",
    ]:
        for pattern, comuna in STREET_COMMUNE_HINTS:
            if pattern.search(data.direccion):
                data.comuna = comuna
                break

    # Extract address from text if missing
    if not data.direccion or not data.numero:
        extracted = extract_address_from_text(transcript)
        if not data.direccion and extracted["direccion"]:
            data.direccion = sanitize_direccion(extracted["direccion"])
        if not data.numero and extracted["numero"]:
            data.numero = re.sub(r"[^0-9]", "", extracted["numero"])
        if not data.comuna and extracted["comuna"]:
            data.comuna = sanitize_comuna(extracted["comuna"])
        if not data.depto and extracted["extra"]:
            data.depto = extracted["extra"]

    # Generate Google Maps URL
    if data.direccion or data.numero or data.comuna:
        query_parts = [data.direccion, data.numero, data.comuna, "Santiago, Chile"]
        query = ", ".join(p for p in query_parts if p)
        data.google_maps_url = (
            f"https://www.google.com/maps/search/?api=1&query={query}"
        )

    # Infer from first-person speech
    if (
        not data.consciente
        and is_first_person(transcript)
        and "inconsciente" not in transcript.lower()
    ):
        data.consciente = "si"
    if (
        not data.respira
        and is_first_person(transcript)
        and "no respira" not in transcript.lower()
    ):
        data.respira = "si"

    # Set motivo to full transcript if empty
    if not data.motivo:
        data.motivo = transcript[:500]  # Limit to first 500 chars

    return data


def sanitize_direccion(direccion: str) -> str:
    """Clean up street address."""
    s = re.sub(r"[\n\r]+", " ", direccion)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\b(ayuda|emergencia|me\s+desmayo|auxilio)\b", "", s, flags=re.I)
    s = re.sub(r"\s+y\s+(?:necesito|me|estoy|urgente).*$", "", s, flags=re.I)
    return s.strip()


def sanitize_comuna(comuna: str) -> str:
    """Clean up comuna name."""
    s = re.sub(r"[\n\r]+", " ", comuna)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.split(",")[0].strip()
    s = re.sub(r"\b(comuna\s+de|en\s+la\s+comuna\s+de)\b", "", s, flags=re.I)
    s = re.sub(r"\b(ayuda|emergencia|urgencia)\b", "", s, flags=re.I)
    return s.strip()


def capitalize_words(text: str) -> str:
    """Capitalize each word."""
    return text.strip().title() if text else ""


def normalize_yes_no(value: str) -> str:
    """Normalize yes/no values to si/no."""
    s = value.lower().strip()
    if re.match(r"^s[ií]$", s) or "si" in s:
        return "si"
    if s == "no" or "no" in s:
        return "no"
    if "inconsciente" in s:
        return "no"
    if "consciente" in s:
        return "si"
    return ""


def normalize_sexo(value: str, transcript: str) -> str:
    """Normalize sex to M/F."""
    s = value.lower()
    if re.match(r"^m(asculino)?$", s):
        return "M"
    if re.match(r"^f(emenino)?$", s):
        return "F"
    # Infer from transcript
    if re.search(r"\b(señora|mujer|femenina|niña)\b", transcript, re.I):
        return "F"
    if re.search(r"\b(señor|hombre|masculino|niño)\b", transcript, re.I):
        return "M"
    return ""


def normalize_edad(value: str, transcript: str) -> str:
    """Normalize age to numeric string."""
    match = re.search(r"(\d{1,3})", value)
    if match:
        age = int(match.group(1))
        if 0 <= age <= 120:
            return str(age)
    # Try to extract from transcript
    match = re.search(r"(\d{1,3})\s*(?:años|año)", transcript, re.I)
    if match:
        age = int(match.group(1))
        if 0 <= age <= 120:
            return str(age)
    return ""


def normalize_codigo(value: str, transcript: str) -> str:
    """Normalize triage code."""
    s = value.lower()
    if "rojo" in s:
        return "Rojo"
    if "amarillo" in s:
        return "Amarillo"
    if "verde" in s:
        return "Verde"
    # Infer from transcript
    t = transcript.lower()
    if re.search(r"\b(paro|inconsciente|no\s+respira|convulsi)", t):
        return "Rojo"
    if re.search(r"\b(dolor\s+fuerte|accidente|fractura|desmayo)", t):
        return "Amarillo"
    return "Verde"


def normalize_avdi(avdi: str, consciente: str, transcript: str) -> str:
    """Normalize AVDI scale."""
    v = avdi.lower().strip()
    if v in ["alerta", "verbal", "dolor", "inconsciente"]:
        return v
    # Infer from transcript
    t = transcript.lower()
    if re.search(r"\b(alerta|consciente|orientado)", t):
        return "alerta"
    if re.search(r"responde\s+a\s+la?\s*voz", t):
        return "verbal"
    if re.search(r"responde\s*a\s+dolor", t):
        return "dolor"
    if re.search(r"\b(inconsciente|no\s+responde)", t):
        return "inconsciente"
    # Infer from consciente field
    norm_consciente = normalize_yes_no(consciente)
    if norm_consciente == "si":
        return "alerta"
    if norm_consciente == "no":
        return "inconsciente"
    return ""


def normalize_respiratorio(estado: str, respira: str, transcript: str) -> str:
    """Normalize respiratory status."""
    v = estado.lower().strip()
    if v in ["respira", "no respira"]:
        return v
    # Use respira field
    norm_respira = normalize_yes_no(respira)
    if norm_respira == "si":
        return "respira"
    if norm_respira == "no":
        return "no respira"
    # Infer from transcript
    t = transcript.lower()
    if re.search(r"no\s+respira|paro", t):
        return "no respira"
    if re.search(r"\brespira", t):
        return "respira"
    return ""


def extract_address_from_text(text: str) -> dict[str, str]:
    """Extract address parts from text."""
    normalized = re.sub(r"\s+", " ", text)
    pattern = r"(?:vivo en|estoy en|estamos en|la dirección es|mi direccion es|nos encontramos en|ubicado en)\s+([^\.\!\?]+)"
    match = re.search(pattern, normalized, re.I)

    if not match:
        return {"direccion": "", "numero": "", "comuna": "", "extra": ""}

    segment = match.group(1)
    detail_pattern = r"([A-Za-zÁÉÍÓÚÑáéíóúñ' ]+?)\s*(\d{1,6})(?:\s*((?:oficina|departamento|depto|piso)\s*[A-Za-z0-9-]+))?(?:\s*(?:,|en\s+la\s+comuna\s+de|comuna)\s*([A-Za-zÁÉÍÓÚÑáéíóúñ' ]+))?"
    detail_match = re.search(detail_pattern, segment, re.I)

    if not detail_match:
        return {"direccion": "", "numero": "", "comuna": "", "extra": ""}

    return {
        "direccion": detail_match.group(1).strip() if detail_match.group(1) else "",
        "numero": detail_match.group(2).strip() if detail_match.group(2) else "",
        "extra": detail_match.group(3).strip() if detail_match.group(3) else "",
        "comuna": detail_match.group(4).strip() if detail_match.group(4) else "",
    }


def is_first_person(text: str) -> bool:
    """Check if text contains first-person speech."""
    return bool(
        re.search(
            r"\b(soy|estoy|necesito|me\s+llamo|hablo|vivo|puedo|llamando)\b", text, re.I
        )
    )
