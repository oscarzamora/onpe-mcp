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
        "la",
        "las",
        "los",
        "para",
        "pais",
        "por",
        "primeros",
        "resultados",
        "sobre",
        "top",
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
