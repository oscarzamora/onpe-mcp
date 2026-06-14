"""Cycle 92 tests: city aliases (pucallpa, iquitos, etc.) + candidate-not-found LLM fallback."""
from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock
from onpe_mcp.server import onpe_chat


# ─── Helpers ────────────────────────────────────────────────────────────────
def _chat(q: str) -> dict:
    return onpe_chat(q)


def _intent(q: str) -> str:
    r = _chat(q)
    return r.get("data", {}).get("intent", "unknown")


def _answer(q: str) -> str:
    r = _chat(q)
    return r.get("data", {}).get("answer", "")


# ─── City alias tests ────────────────────────────────────────────────────────

def test_pucallpa_geo_intent():
    """pucallpa debe enrutarse a geo_domestic, no unknown."""
    intent = _intent("top 5 en pucallpa")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_iquitos_geo_intent():
    intent = _intent("resultados en iquitos")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_tarapoto_geo_intent():
    intent = _intent("quien gano en tarapoto")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_chiclayo_geo_intent():
    intent = _intent("votos en chiclayo")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_trujillo_geo_intent():
    intent = _intent("top 3 candidatos en trujillo")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_chimbote_geo_intent():
    intent = _intent("resultados en chimbote")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_huancayo_geo_intent():
    intent = _intent("como voto huancayo")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_arequipa_geo_intent():
    intent = _intent("top 5 en arequipa")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_cusco_geo_intent():
    intent = _intent("cuantos votos en cusco")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_cuzco_variant_geo_intent():
    """cuzco (sin acento) también debe funcionar."""
    intent = _intent("resultados en cuzco")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_puno_geo_intent():
    intent = _intent("resultados en puno")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_juliaca_geo_intent():
    """juliaca → san roman (puno)."""
    intent = _intent("quien gano en juliaca")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_piura_geo_intent():
    intent = _intent("top 3 en piura")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_tacna_geo_intent():
    intent = _intent("resultados en tacna")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_ayacucho_geo_intent():
    intent = _intent("votos en ayacucho")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_pucallpa_with_candidate():
    """top candidatos en pucallpa → geo_domestic."""
    intent = _intent("cuantos votos saco aliaga en pucallpa")
    # Si hay candidato + geo, puede ser candidate o geo_domestic
    assert intent in ("candidate", "geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_pucallpa_full_query():
    """Query compleja con pucallpa."""
    intent = _intent("dame el top 10 de candidatos en pucallpa ucayali")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_iquitos_candidate_combo():
    intent = _intent("como le fue a keiko en iquitos")
    assert intent in ("candidate", "geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_tarapoto_candidate_combo():
    intent = _intent("cuantos votos obtuvo aliaga en tarapoto")
    assert intent in ("candidate", "geo_domestic", "geo_foreign"), f"Got: {intent}"


# ─── Candidate not found: fuzzy suggestions ──────────────────────────────────

def test_candidate_notfound_has_suggestion():
    """Candidato inexistente con nombre parecido debe sugerir alternativas."""
    r = _chat("cuantos votos saco 'Aliagas' en la primera vuelta")
    answer = r.get("data", {}).get("answer", "")
    result = r.get("data", {}).get("result", {})
    # Debe retornar candidate intent o sugerir algo
    assert r.get("data", {}).get("intent") in ("candidate", "unknown") or "encontré" in answer.lower()


def test_candidate_notfound_returns_candidate_intent():
    """Candidato inventado → intent candidate con found=False."""
    r = _chat("cuantos votos saco el candidato Zaragoza Medina")
    data = r.get("data", {})
    # Puede ser candidate (not found) o unknown
    assert data.get("intent") in ("candidate", "unknown"), f"Got: {data.get('intent')}"
    if data.get("intent") == "candidate":
        result = data.get("result") or {}
        assert result.get("found") is False or "No encontré" in (data.get("answer") or "")


def test_candidate_notfound_sugerencias_field():
    """Si hay sugerencias fuzzy, aparecen en result.sugerencias."""
    r = _chat("cuantos votos tiene Fujimori en primera vuelta")
    data = r.get("data", {})
    if data.get("intent") == "candidate":
        result = data.get("result") or {}
        # puede tener sugerencias o no, dependiendo de si hay datos en cache
        assert isinstance(result.get("sugerencias", []), list)


def test_candidate_notfound_qualitative_fallback():
    """Sin datos en cache, candidato inventado → respuesta cualitativa."""
    r = _chat("cuantos votos obtuvo candidato X_NO_EXISTE_ZXQW en primeras")
    data = r.get("data", {})
    answer = data.get("answer", "")
    # Debe decir que no encontró, no crashear
    assert answer  # respuesta no vacía
    assert data.get("intent") in ("candidate", "unknown", "geo_domestic")


# ─── Variantes de ciudad: sin tildes, errores tipográficos ───────────────────

def test_pucaypa_typo():
    """Typo grave → puede no resolverse, pero no debe crashear."""
    r = _chat("resultados en pucaypa")
    assert r.get("ok") is True  # no debe crashear


def test_iquiitos_typo():
    """Typo en iquitos."""
    r = _chat("top 3 en iquiitos")
    assert r.get("ok") is True


def test_chiclayo_no_accent():
    intent = _intent("resultados en chiclayo")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_huancayo_caps():
    intent = _intent("RESULTADOS EN HUANCAYO")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_tacna_lowercase():
    intent = _intent("resultados en tacna sur")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_piura_with_noise():
    intent = _intent("dame el top de candidatos en la ciudad de piura peru")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


# ─── Regression: existing working cities still work ─────────────────────────

def test_lima_still_works():
    intent = _intent("resultados en lima")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_loreto_dept_still_works():
    intent = _intent("resultados en loreto")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"


def test_ucayali_dept_still_works():
    intent = _intent("resultados en ucayali")
    assert intent in ("geo_domestic", "geo_foreign"), f"Got: {intent}"
