from __future__ import annotations

import pytest

from onpe_mcp.server import onpe_2021_chat, onpe_chat, onpe_health, _norm


SMOKE_CASES = [
    (
        "2026",
        onpe_chat,
        "dame los resultados de la mesa 900100 en 2026",
        "mesa",
        ["Mesa 900100", "Roberto Sánchez Palomino", "210 votos"],
    ),
    (
        "2026",
        onpe_chat,
        "cuántos votos sacó Keiko Fujimori a nivel nacional en 2026",
        "candidate",
        ["Keiko Fujimori Higuchi", "2,877,621"],
    ),
    (
        "2021",
        onpe_2021_chat,
        "cuántos votos sacó Pedro Castillo en 2021 segunda vuelta",
        "candidate_2021",
        ["Pedro Castillo Terrones", "8,835,970", "2da vuelta"],
    ),
    (
        "2021",
        onpe_2021_chat,
        "quién ganó en Lima 2021 primera vuelta",
        "ranking_2021",
        ["Top 5 2021 1ra vuelta en LIMA", "Hernando de Soto", "Rafael López Aliaga"],
    ),
]


def test_mcp_smoke_answers_real() -> None:
    health = onpe_health().get("data", {})
    if not health.get("hydrated"):
        pytest.skip("MCP local no está hidratado")

    for year, fn, query, expected_intent, expected_phrases in SMOKE_CASES:
        result = fn(query)
        assert result["ok"] is True, f"{year}: {query}"
        data = result["data"]
        assert data["intent"] == expected_intent, f"{year}: {query}"
        answer = _norm(data["answer"])
        for phrase in expected_phrases:
            assert _norm(phrase) in answer, f"{year}: {query} -> falta '{phrase}'"
