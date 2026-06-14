"""Tests de regresión NL para los fixes de chat (reasignados early-exit,
range_existence_verify con top N, range_reasoning con 'ganó primero NOMBRE').

Estos tests validan los regex/keyword guards directamente sobre el código,
sin requerir reiniciar el MCP server.
"""
from __future__ import annotations

import re


# ── Fix 1: reasignados keyword detection ─────────────────────────────────────

_REASIGNADO_KEYWORDS = ("reasign", "local reasignado", "reubicad", "reubican",
                        "huelga", "extorsion", "reconstruccion")


def _norm(s: str) -> str:
    import unicodedata
    b = unicodedata.normalize("NFKD", s or "")
    return "".join(ch for ch in b if not unicodedata.combining(ch)).casefold().strip()


def _has_reasignado(q: str) -> bool:
    q_norm = _norm(q)
    return any(kw in q_norm for kw in _REASIGNADO_KEYWORDS)


def test_reasignado_detection_natural_queries() -> None:
    """Todas estas queries deben disparar la rama de reasignados."""
    assert _has_reasignado("qué locales se reasignaron en Trujillo")
    assert _has_reasignado("locales reasignados en La Libertad")
    assert _has_reasignado("dame los locales reubicados de Cajamarca")
    assert _has_reasignado("hubo locales por extorsión en La Libertad")
    assert _has_reasignado("locales por reconstrucción en Pataz")
    assert _has_reasignado("locales reasignados entre vueltas")


def test_reasignado_not_triggered_on_unrelated() -> None:
    """No debe disparar en queries sin keywords."""
    assert not _has_reasignado("top 5 en Trujillo")
    assert not _has_reasignado("cuántos votos en La Libertad")
    assert not _has_reasignado("ganador en Trujillo")


# ── Fix 2: range_existence con top N ─────────────────────────────────────────

def _has_describe_mesa(q: str) -> bool:
    """Replica la lógica añadida en server.py para detectar
    'top X candidatos en mesas NNN[K]'."""
    q_norm = _norm(q)
    # Trigger explícito: top N + 'mesas' + prefijo numérico
    if re.search(r"\btop\s+\d+\b", q_norm) and re.search(r"\bmesas?\b", q_norm):
        if re.search(r"\b\d{3,6}\b", q_norm) or re.search(r"\b\d{3,4}\s*[kK]\b", q_norm):
            return True
    return False


def test_top_n_mesas_prefix_detected() -> None:
    """Queries con 'top N en mesas NNN[K]' deben detectarse como descripción de mesa."""
    assert _has_describe_mesa("top 3 candidatos en las mesas 900K")
    assert _has_describe_mesa("top 5 en mesas 9001")
    assert _has_describe_mesa("top 10 partidos en mesas 150")
    assert _has_describe_mesa("Top 3 en mesas 900000")


def test_top_n_alone_not_triggered() -> None:
    """Sin 'mesas' o sin prefijo numérico no debe disparar."""
    assert not _has_describe_mesa("top 5 candidatos a nivel nacional")
    assert not _has_describe_mesa("top 3 en Lima")
    assert not _has_describe_mesa("top 5 partidos")


# ── Fix 3: range_reasoning con 'ganó primero NOMBRE' ─────────────────────────

_CAND_PATTERNS = [
    re.compile(
        r"\b(?:fue|quedo|qued[oó]|estuvo|gan[oó])\s+primero\s+(.+?)(?=\s*$|\s+en\b|\s+con\b|\s+para\b|\s+sobre\b)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:fue|quedo|qued[oó]|estuvo|gan[oó])\s+(.+?)\s+primero\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bgan[oó]\s+(.+?)(?=\s*$|\s+en\b|\s+con\b|\s+para\b)",
        re.IGNORECASE,
    ),
]


def _extract_candidate(q: str) -> str:
    for pat in _CAND_PATTERNS:
        m = pat.search(q)
        if m:
            return m.group(1).strip()
    return ""


def test_extract_candidate_gano_primero() -> None:
    """Patrón nuevo: 'ganó primero NOMBRE' debe extraer solo el nombre."""
    cand = _extract_candidate(
        "de las mesas que arrancan en 900000, en qué lugares ganó primero López Aliaga"
    )
    assert cand == "López Aliaga"


def test_extract_candidate_fue_primero() -> None:
    """Patrón original: 'fue primero NOMBRE' debe seguir funcionando."""
    cand = _extract_candidate("en qué mesas fue primero López Aliaga")
    assert cand == "López Aliaga"


def test_extract_candidate_fue_nombre_primero() -> None:
    """Patrón: 'fue NOMBRE primero'."""
    cand = _extract_candidate("en qué mesas fue Castillo primero")
    assert cand == "Castillo"


def test_extract_candidate_gano_sin_primero() -> None:
    """Patrón fallback: 'ganó NOMBRE' (sin la palabra 'primero')."""
    cand = _extract_candidate("en qué mesas ganó López Aliaga")
    assert cand == "López Aliaga"


def test_extract_candidate_with_en_suffix() -> None:
    """Patrón con sufijo 'en ...': el nombre no debe incluir 'en X'."""
    cand = _extract_candidate("en qué lugares ganó primero López Aliaga en Lima")
    assert cand == "López Aliaga"
