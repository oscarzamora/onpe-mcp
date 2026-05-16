from __future__ import annotations

from typing import Any

from onpe_mcp.onpe_api import OnpeApiClient


def test_get_mesa_prefiere_contabilizada_del_id_solicitado(monkeypatch) -> None:
    client = OnpeApiClient()
    calls: list[tuple[str, dict[str, Any] | None]] = []

    def fake_get_json(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        calls.append((path, params))
        return {
            "data": [
                {
                    "idEleccion": 10,
                    "descripcionEstadoActa": "Contabilizada",
                    "codigoMesa": "000123",
                    "idUbigeo": "150101",
                    "nombreLocalVotacion": "LOCAL 1",
                    "totalElectoresHabiles": "100",
                    "totalVotosEmitidos": "90",
                    "totalVotosValidos": "88",
                    "detalle": [
                        {"adCodigo": "80", "adVotos": "1"},
                        {"adCodigo": "81", "adVotos": 2},
                        {"adCodigo": "82", "adVotos": "3"},
                        {"adCodigo": "1", "adAgrupacionPolitica": "P1", "adDescripcion": "PARTIDO 1", "adVotos": "77"},
                    ],
                },
                {
                    "idEleccion": 10,
                    "descripcionEstadoActa": "Pendiente",
                    "codigoMesa": "000123",
                    "detalle": [],
                },
            ]
        }

    monkeypatch.setattr(client, "_get_json", fake_get_json)

    result = client.get_mesa("000123", id_eleccion=10)

    assert calls == [("/actas/buscar/mesa", {"codigoMesa": "000123"})]
    assert result["found"] is True
    assert result["mesa_data"]["estado_acta"] == "Contabilizada"
    assert result["mesa_data"]["blancos"] == 1
    assert result["mesa_data"]["nulos"] == 2
    assert result["mesa_data"]["impugnados"] == 3
    assert result["agrupaciones"] == [{"partido_id": "P1", "nombre": "PARTIDO 1"}]
    assert result["votos"] == [{"codigo_mesa": "000123", "partido_id": "P1", "votos": 77}]


def test_get_mesa_devuelve_found_false_si_no_hay_data() -> None:
    client = OnpeApiClient()

    def fake_get_json(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"data": []}

    client._get_json = fake_get_json  # type: ignore[method-assign]

    result = client.get_mesa("000123", id_eleccion=10)

    assert result["found"] is False
    assert result["mesa_data"] is None
    assert result["agrupaciones"] == []
    assert result["votos"] == []