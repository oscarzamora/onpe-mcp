from __future__ import annotations

import logging
import re
import time
import unicodedata
from typing import Any

# Mapa departamento-peruano-normalizado → prefijo ubigeo (2 dígitos).
# Claves en minúsculas y sin tildes para comparación directa con texto normalizado.
# Se incluye "cuzco" como alias de "cusco".
PERU_DEPARTMENTS: dict[str, str] = {
    "amazonas": "01",
    "ancash": "02",
    "apurimac": "03",
    "arequipa": "04",
    "ayacucho": "05",
    "cajamarca": "06",
    "callao": "07",
    "cusco": "08",
    "cuzco": "08",
    "huancavelica": "09",
    "huanuco": "10",
    "ica": "11",
    "junin": "12",
    "la libertad": "13",
    "lambayeque": "14",
    "lima": "15",
    "loreto": "16",
    "madre de dios": "17",
    "moquegua": "18",
    "pasco": "19",
    "piura": "20",
    "puno": "21",
    "san martin": "22",
    "tacna": "23",
    "tumbes": "24",
    "ucayali": "25",
}


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def now_ms() -> int:
    return int(time.time() * 1000)


def ok_response(data: Any, *, started_ms: int, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    payload_meta = {
        "duration_ms": max(0, now_ms() - started_ms),
    }
    if meta:
        payload_meta.update(meta)

    return {
        "ok": True,
        "data": data,
        "errors": [],
        "meta": payload_meta,
    }


def error_response(message: str, *, started_ms: int, code: str = "INTERNAL_ERROR") -> dict[str, Any]:
    return {
        "ok": False,
        "data": None,
        "errors": [{"code": code, "message": message}],
        "meta": {
            "duration_ms": max(0, now_ms() - started_ms),
        },
    }


def validate_mesa_code(codigo_mesa: str) -> str:
    code = str(codigo_mesa).strip()
    if not code.isdigit():
        raise ValueError("codigo_mesa debe contener solo dígitos")
    if len(code) > 6:
        raise ValueError("codigo_mesa no puede tener más de 6 dígitos")
    return code.zfill(6)


def _normalize_search_text(value: str) -> str:
    base = unicodedata.normalize("NFKD", value or "")
    stripped = "".join(ch for ch in base if not unicodedata.combining(ch))
    return " ".join(stripped.casefold().split())


def extract_top_n(query: str, default: int = 5, *, minimum: int = 1, maximum: int = 20) -> int:
    text = _normalize_search_text(query)
    if not text:
        return default

    patterns = (
        r"\btop\s+(\d{1,3})\b",
        r"\bprimeros?\s+(\d{1,3})\b",
        r"\b(\d{1,3})\s+primeros?\b",
        r"\b(\d{1,3})\s+top\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        try:
            value = int(match.group(1))
        except ValueError:
            continue
        return max(minimum, min(value, maximum))

    return default


def extract_foreign_geo_candidates(query: str) -> list[tuple[str | None, str]]:
    text = _normalize_search_text(query)
    if not text:
        return []

    stopwords = {
        "a",
        "al",
        "candidatos",
        "candidato",
        "ciudad",
        "con",
        "de",
        "del",
        "dame",
        "el",
        "en",
        "es",
        "esta",
        "extranjero",
        "exterior",
        "fue",
        "gan",
        "gana",
        "ganando",
        "la",
        "las",
        "los",
        "mas",
        "para",
        "pais",
        "por",
        "primeros",
        "que",
        "quien",
        "quienes",
        "resultados",
        "sobre",
        "top",
        "va",
        "votos",
    }

    candidates: list[tuple[str | None, str]] = []
    seen: set[tuple[str | None, str]] = set()

    def add(field: str | None, value: str) -> None:
        cleaned = _normalize_search_text(value)
        if not cleaned:
            return
        key = (field, cleaned)
        if key in seen:
            return
        seen.add(key)
        candidates.append(key)

    add(None, text)

    for pattern, field in (
        (r"\b(?:pais|ciudad)\s+(.+?)\s*$", None),
        (r"\b(?:en|de|del|para|por|sobre|hacia|a|al)\s+(.+?)\s*$", None),
        (r"^(.+?)\s+(?:top\s+\d+|top|primeros?(?:\s+\d+)?|candidatos?|candidato|resultados?|votos?)\s*$", None),
    ):
        match = re.search(pattern, text)
        if match:
            add(field, match.group(1))

    explicit = re.search(r"\b(pais|ciudad)\s+(.+?)\s*$", text)
    if explicit:
        field = "pais" if explicit.group(1) == "pais" else "ciudad"
        add(field, explicit.group(2))

    tokens = [token for token in text.split() if token not in stopwords and not token.isdigit()]
    if tokens:
        add(None, " ".join(tokens))
        for token in tokens:
            add(None, token)

    return candidates


def find_peru_department_prefix(query: str) -> tuple[str, str] | None:
    """Detecta un departamento peruano en la consulta.

    Retorna ``(nombre_normalizado, prefijo_ubigeo)`` o ``None`` si no hay coincidencia.
    Los nombres multi-palabra se prueban primero para evitar falsos positivos
    (p.ej. "la libertad" antes que "libertad").
    """
    q = _normalize_search_text(query)
    if not q:
        return None
    for dept, prefix in sorted(PERU_DEPARTMENTS.items(), key=lambda x: -len(x[0])):
        if dept in q:
            return dept, prefix
    return None


def extract_mesa_prefix_claim(query: str) -> str | None:
    """Extrae prefijo de mesa desde lenguaje natural para verificar afirmaciones.

    Ejemplos soportados:
    - "mesas 900K" -> "900"
    - "mesas que arrancan en 900000" -> "900000"
    - "prefijo 9001" -> "9001"
    """
    q = _normalize_search_text(query)
    if not q:
        return None

    # Shorthand común: 900K == bloque que arranca en 900000.
    k_match = re.search(r"\b(\d{3,4})\s*k\b", q)
    if k_match:
        base = int(k_match.group(1))
        expanded = str(base * 1000)
        if len(expanded) <= 6:
            return expanded
        return expanded[:6]

    num_match = re.search(r"\b(\d{3,6})\b", q)
    if num_match:
        return num_match.group(1)

    return None


# ---------------------------------------------------------------------------
# Parser de claims cuantitativos en español — alimenta `onpe_claim_verifier`.
# ---------------------------------------------------------------------------

# Palabras-número en español (para "cien mil", "un millón", etc.).
_SPANISH_NUMBER_WORDS: dict[str, int] = {
    "uno": 1, "un": 1, "una": 1,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
    "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14,
    "quince": 15, "veinte": 20, "treinta": 30, "cuarenta": 40,
    "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80,
    "noventa": 90, "cien": 100, "ciento": 100,
    "doscientos": 200, "trescientos": 300, "cuatrocientos": 400,
    "quinientos": 500, "seiscientos": 600, "setecientos": 700,
    "ochocientos": 800, "novecientos": 900,
    "mil": 1_000,
    "millon": 1_000_000, "millones": 1_000_000,
}

_THOUSAND = 1_000
_MILLION = 1_000_000


def _parse_spanish_number_phrase(text: str) -> int | None:
    """Parse cosas como 'novecientos mil', 'un millon', 'cien mil', '1.2 millones'.

    Retorna ``None`` si no se reconoce. Maneja decimales con punto o coma
    cuando aparecen seguidos de 'mil' / 'millones' (ej. "1.2 millones").
    """
    if not text:
        return None
    t = _normalize_search_text(text).replace(",", ".")

    # Caso: número decimal seguido de "millon/millones" o "mil"
    # Orden importa: probar "millon" antes que "mil" (alternancia greedy).
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(millon(?:es)?|mil)\b", t)
    if m:
        try:
            num = float(m.group(1))
        except ValueError:
            return None
        unit = m.group(2)
        factor = _MILLION if unit.startswith("millon") else _THOUSAND
        return int(round(num * factor))

    # Caso: número decimal/entero solo, posiblemente con punto como separador de miles
    m_int = re.match(r"^\s*([\d.\,]+)\s*$", t)
    if m_int:
        raw = m_int.group(1)
        digits = re.sub(r"[\.\,]", "", raw)
        if digits.isdigit() and len(digits) >= 3:
            return int(digits)

    # Caso: frase en palabras ("cien mil", "novecientos mil", "un millon")
    tokens = [tok for tok in re.split(r"\s+", t) if tok]
    if not tokens:
        return None

    # Detección simple: suma de tokens reconocidos, multiplicando por
    # "mil"/"millon" cuando aparecen.
    total = 0
    chunk = 0
    seen_word = False
    for tok in tokens:
        if tok not in _SPANISH_NUMBER_WORDS:
            continue
        seen_word = True
        val = _SPANISH_NUMBER_WORDS[tok]
        if val == _THOUSAND:
            chunk = (chunk or 1) * _THOUSAND
            total += chunk
            chunk = 0
        elif val == _MILLION:
            chunk = (chunk or 1) * _MILLION
            total += chunk
            chunk = 0
        else:
            chunk += val
    total += chunk
    if not seen_word:
        return None
    return total if total > 0 else None


def parse_quantitative_claims(query: str) -> dict[str, list[dict[str, Any]]]:
    """Extrae cifras absolutas y porcentajes de un claim en español.

    Devuelve:
        {
            "absolutos": [{"raw": "900 mil", "valor": 900000, "unidad": "votos"|"electores"|"actas"|"votantes"|None}, ...],
            "porcentajes": [{"raw": "1.2%", "valor": 1.2}, ...],
        }
    """
    text = (query or "").strip()
    if not text:
        return {"absolutos": [], "porcentajes": []}

    absolutos: list[dict[str, Any]] = []
    porcentajes: list[dict[str, Any]] = []

    norm = _normalize_search_text(text)

    # 1) Porcentajes — "1.2%", "1,2 %", "1.2 por ciento", "1.2 puntos"
    #    Nota: no usamos `\b` después de `%` porque `%` no es word-character.
    for m in re.finditer(
        r"\b(\d+(?:[\.,]\d+)?)\s*(?:%|por\s*ciento|puntos?\s+porcentuales?|\bpp\b)",
        norm,
    ):
        try:
            val = float(m.group(1).replace(",", "."))
        except ValueError:
            continue
        porcentajes.append({"raw": m.group(0).strip(), "valor": val})

    # 2) Cifras absolutas con palabra-unidad pegada.
    #    Orden importa: "millon(?:es)?" antes que "mil" en la alternancia para
    #    que "1.2 millones" no se trunque a "1.2 mil".
    abs_pattern = re.compile(
        r"\b("
        r"(?:un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|"
        r"once|doce|trece|catorce|quince|veinte|treinta|cuarenta|"
        r"cincuenta|sesenta|setenta|ochenta|noventa|"
        r"cien|ciento|doscientos|trescientos|cuatrocientos|quinientos|"
        r"seiscientos|setecientos|ochocientos|novecientos)\s+"
        r"(?:millon(?:es)?|mil)"
        r"|"
        r"\d+(?:[\.,]\d+)?\s*(?:millon(?:es)?|mil)"
        r"|"
        r"\d{1,3}(?:[\.,]\d{3})+"
        r")"
        r"(?:\s+(?:de\s+)?(votos?|votantes?|electores?|peruanos?|mesas?|actas?|ciudadanos?))?",
    )
    for m in abs_pattern.finditer(norm):
        phrase = m.group(1).strip()
        unidad_raw = (m.group(2) or "").strip().lower() or None
        valor = _parse_spanish_number_phrase(phrase)
        if not valor:
            continue
        unidad = None
        if unidad_raw:
            if unidad_raw.startswith("voto"):
                unidad = "votos"
            elif unidad_raw.startswith("votante"):
                unidad = "votantes"
            elif unidad_raw.startswith("elector"):
                unidad = "electores"
            elif unidad_raw.startswith("mesa"):
                unidad = "mesas"
            elif unidad_raw.startswith("acta"):
                unidad = "actas"
            elif unidad_raw.startswith("peruano"):
                unidad = "personas"
            elif unidad_raw.startswith("ciudadano"):
                unidad = "personas"
        absolutos.append({
            "raw": phrase + (f" {unidad_raw}" if unidad_raw else ""),
            "valor": valor,
            "unidad": unidad,
        })

    # 3) De-duplicar absolutos preservando orden por (valor,unidad)
    seen: set[tuple[int, str | None]] = set()
    deduped: list[dict[str, Any]] = []
    for it in absolutos:
        key = (it["valor"], it["unidad"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)

    return {"absolutos": deduped, "porcentajes": porcentajes}


def classify_claim_topic(query: str) -> str:
    """Clasifica el tema del claim para decidir qué denominador usar.

    Returns one of:
        - "votos_faltantes" — "faltan X votos / no se han contado"
        - "impedidos_votar" — "X no pudo/pudieron votar"
        - "margen_perdido" — "nos restaron X%" / "perdimos X votos"
        - "actas_irregulares" — "actas con patrones irregulares"
        - "general" — fallback
    """
    q = _normalize_search_text(query)
    if not q:
        return "general"
    if any(kw in q for kw in (
        "no pudo votar", "no pudieron votar", "impedid", "impedimento",
        "no votaron por culpa", "negaron el voto",
    )):
        return "impedidos_votar"
    if any(kw in q for kw in (
        "falta", "faltan", "faltaron", "sin contar", "no se han contado",
        "desaparecid", "no se contaron", "no se contabiliz",
    )):
        return "votos_faltantes"
    if any(kw in q for kw in (
        "nos quitar", "nos restaron", "perdimos", "nos robaron",
        "manipulacion", "manipularon", "manipulado", "irregular",
        "patrones irregulares", "actas observadas", "fraude",
    )):
        if any(kw in q for kw in ("acta", "actas")):
            return "actas_irregulares"
        return "margen_perdido"
    if "millon" in q or "mil " in q or "%" in q:
        return "general"
    return "general"
