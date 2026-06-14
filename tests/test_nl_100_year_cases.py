from __future__ import annotations

from typing import Any

import pytest

import onpe_mcp.server as server_module


_BASE_2021 = [
    "resultados 2021",
    "top 5 2021",
    "quien gano en 2021",
    "votos de castillo 2021",
    "votos de keiko 2021",
    "mesa 000001 2021",
    "primera vuelta 2021 top nacional",
    "segunda vuelta 2021 top nacional",
    "resultados 2021 en lima",
    "votacion 2021 en cusco",
]
_BASE_2026 = [
    "resultados 2026",
    "top 5 2026",
    "quien gano en 2026",
    "votos de lopez aliaga 2026",
    "votos de keiko 2026",
    "mesa 900100 2026",
    "primera vuelta 2026 top nacional",
    "segunda vuelta 2026 top nacional",
    "resultados 2026 en lima",
    "votacion 2026 en cusco",
]

YEAR_CASES: list[tuple[str, int | None]] = []
for i in range(1, 6):
    for q in _BASE_2021:
        YEAR_CASES.append((f"{q} caso {i}", 2021))
    for q in _BASE_2026:
        YEAR_CASES.append((f"{q} caso {i}", 2026))

assert len(YEAR_CASES) == 100


@pytest.mark.parametrize(("query", "expected_year"), YEAR_CASES)
def test_resolve_query_year_100_cases(query: str, expected_year: int | None) -> None:
    assert server_module._resolve_query_year(server_module._norm(query)) == expected_year


@pytest.mark.parametrize(
    ("query", "expected_round"),
    [
        ("resultados 2021 primera vuelta", 1),
        ("resultado 2021 1ra vuelta", 1),
        ("top 2021 1a vuelta", 1),
        ("resultado 2021 segunda vuelta", 2),
        ("resultado 2021 2da vuelta", 2),
        ("resultado 2021 2a vuelta", 2),
        ("ballotage 2021", 2),
        ("balotaje 2021", 2),
        ("votos castillo 2021", 1),
        ("votos castillo 2021 en lima", 1),
    ],
)
def test_infer_2021_vuelta(query: str, expected_round: int) -> None:
    assert server_module._infer_2021_vuelta(server_module._norm(query)) == expected_round


def test_onpe_chat_routes_to_2021_handler(monkeypatch) -> None:
    calls: list[str] = []

    def _fake_2021_chat(query: str, vuelta: int | None = None) -> dict[str, Any]:
        calls.append(query)
        return {"ok": True, "data": {"intent": "ranking_2021", "answer": "ok"}, "errors": [], "meta": {"duration_ms": 1}}

    monkeypatch.setattr(server_module, "onpe_2021_chat", _fake_2021_chat)
    out = server_module.onpe_chat("dame top 5 de 2021 en lima")
    assert out["ok"] is True
    assert out["data"]["intent"] == "ranking_2021"
    assert calls and "2021" in calls[0]
