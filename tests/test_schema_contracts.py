"""
Contrato de schemas ONPE.
Valida que los payloads de la API ONPE siguen la forma esperada definida en schemas/.
Si ONPE cambia el payload (tipos, campos requeridos), estos tests lo detectan primero.
"""
import json
from pathlib import Path

import pytest

try:
    import jsonschema
    from jsonschema import validate, ValidationError
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

pytestmark = pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")

SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"


def _load_schema(filename: str) -> dict:
    return json.loads((SCHEMAS_DIR / filename).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_registry():
    """Construye un registry local con todos los schemas en schemas/ para resolver $ref."""
    try:
        from referencing import Registry, Resource
        import referencing.jsonschema as rjs

        resources = []
        for schema_file in SCHEMAS_DIR.glob("*.json"):
            raw = json.loads(schema_file.read_text(encoding="utf-8"))
            schema_id = raw.get("$id") or schema_file.name
            # También registrar con el nombre relativo que usan los $ref
            resources.append((schema_id, Resource.from_contents(raw)))
            resources.append((f"./{schema_file.name}", Resource.from_contents(raw)))
            resources.append((schema_file.name, Resource.from_contents(raw)))
        return Registry().with_resources(resources)
    except ImportError:
        return None


_REGISTRY = _build_registry()


def _validate(payload: dict, schema: dict):
    """Valida payload contra schema con resolución de $ref local."""
    if _REGISTRY is not None:
        try:
            from jsonschema import Draft202012Validator
            validator = Draft202012Validator(schema, registry=_REGISTRY)
            validator.validate(payload)
            return
        except TypeError:
            pass
    validate(instance=payload, schema=schema)


# ---------------------------------------------------------------------------
# Schema: onpe.acta.min
# ---------------------------------------------------------------------------

ACTA_SCHEMA = _load_schema("onpe.acta.min.schema.json")


class TestActaMinSchema:
    """Payloads de acta individual (un registro de una mesa)."""

    def test_acta_valida_completa(self):
        payload = {
            "idEleccion": 10,
            "descripcionEstadoActa": "Contabilizada",
            "codigoMesa": "900100",
            "idUbigeo": "010101",
            "nombreLocalVotacion": "I.E. San José",
            "totalElectoresHabiles": 200,
            "totalVotosEmitidos": 180,
            "totalVotosValidos": 170,
            "detalle": [
                {"adCodigo": "01", "adVotos": 90, "adAgrupacionPolitica": "Partido A", "adDescripcion": "Candidato A"},
                {"adCodigo": "02", "adVotos": 80, "adAgrupacionPolitica": "Partido B", "adDescripcion": "Candidato B"},
            ],
        }
        _validate(payload, ACTA_SCHEMA)

    def test_acta_votos_como_string(self):
        """ONPE a veces devuelve votos como string en lugar de int."""
        payload = {
            "idEleccion": 10,
            "descripcionEstadoActa": "Contabilizada",
            "codigoMesa": "900100",
            "totalElectoresHabiles": "200",
            "totalVotosEmitidos": "180",
            "totalVotosValidos": "170",
            "detalle": [
                {"adCodigo": "01", "adVotos": "90"},
            ],
        }
        _validate(payload, ACTA_SCHEMA)

    def test_acta_campos_nulos(self):
        """Campos opcionales pueden ser null."""
        payload = {
            "idEleccion": 10,
            "descripcionEstadoActa": "En proceso",
            "codigoMesa": "900100",
            "idUbigeo": None,
            "nombreLocalVotacion": None,
            "totalElectoresHabiles": None,
            "totalVotosEmitidos": None,
            "totalVotosValidos": None,
            "detalle": [],
        }
        _validate(payload, ACTA_SCHEMA)

    def test_acta_sin_campos_requeridos_falla(self):
        """Falta idEleccion → ValidationError."""
        payload = {
            "descripcionEstadoActa": "Contabilizada",
            "codigoMesa": "900100",
            "detalle": [],
        }
        with pytest.raises(ValidationError):
            _validate(payload, ACTA_SCHEMA)

    def test_acta_sin_detalle_falla(self):
        payload = {
            "idEleccion": 10,
            "descripcionEstadoActa": "Contabilizada",
            "codigoMesa": "900100",
        }
        with pytest.raises(ValidationError):
            _validate(payload, ACTA_SCHEMA)

    def test_acta_detalle_campo_extra_permitido(self):
        """additionalProperties=true: campos extra no rompen el schema."""
        payload = {
            "idEleccion": 10,
            "descripcionEstadoActa": "Contabilizada",
            "codigoMesa": "900100",
            "detalle": [
                {"adCodigo": "01", "adVotos": 10, "campoNuevoFuturo": "valor"},
            ],
            "campoNuevoEnRaiz": True,
        }
        _validate(payload, ACTA_SCHEMA)

    def test_acta_eleccion_id_como_string_falla(self):
        """idEleccion debe ser integer, no string."""
        payload = {
            "idEleccion": "10",  # ← tipo incorrecto
            "descripcionEstadoActa": "Contabilizada",
            "codigoMesa": "900100",
            "detalle": [],
        }
        with pytest.raises(ValidationError):
            _validate(payload, ACTA_SCHEMA)


# ---------------------------------------------------------------------------
# Schema: onpe.actas.buscar.mesa.response
# ---------------------------------------------------------------------------

RESPONSE_SCHEMA = _load_schema("onpe.actas.buscar.mesa.response.schema.json")


class TestBuscarMesaResponseSchema:
    """Payload de respuesta completa del endpoint buscar-mesa."""

    def test_respuesta_valida(self):
        payload = {
            "success": True,
            "message": "OK",
            "data": [
                {
                    "idEleccion": 10,
                    "descripcionEstadoActa": "Contabilizada",
                    "codigoMesa": "900100",
                    "detalle": [],
                }
            ],
        }
        _validate(payload, RESPONSE_SCHEMA)

    def test_respuesta_data_vacia(self):
        """data puede ser lista vacía (mesa sin actas)."""
        payload = {"success": True, "message": "Sin datos", "data": []}
        _validate(payload, RESPONSE_SCHEMA)

    def test_respuesta_sin_data_falla(self):
        """data es requerido."""
        payload = {"success": True, "message": "OK"}
        with pytest.raises(ValidationError):
            _validate(payload, RESPONSE_SCHEMA)

    def test_respuesta_success_null_permitido(self):
        """success y message son opcionales/nullable."""
        payload = {"success": None, "message": None, "data": []}
        _validate(payload, RESPONSE_SCHEMA)

    def test_respuesta_multiples_actas(self):
        """Varias actas (una por elección) en la misma respuesta."""
        acta = {
            "idEleccion": 10,
            "descripcionEstadoActa": "Contabilizada",
            "codigoMesa": "900100",
            "detalle": [{"adCodigo": "01", "adVotos": 50}],
        }
        payload = {
            "success": True,
            "message": "OK",
            "data": [acta, {**acta, "idEleccion": 13}],
        }
        _validate(payload, RESPONSE_SCHEMA)

    def test_respuesta_acta_invalida_dentro_de_data_falla(self):
        """Acta sin codigoMesa dentro de data → ValidationError."""
        payload = {
            "success": True,
            "data": [
                {
                    "idEleccion": 10,
                    "descripcionEstadoActa": "Contabilizada",
                    # falta codigoMesa
                    "detalle": [],
                }
            ],
        }
        with pytest.raises(ValidationError):
            _validate(payload, RESPONSE_SCHEMA)


# ---------------------------------------------------------------------------
# Contrato de respuesta MCP (ok_response / error_response shape)
# ---------------------------------------------------------------------------

class TestMcpResponseShape:
    """Valida que ok_response y error_response mantienen el contrato interno."""

    def test_ok_response_shape(self):
        from onpe_mcp.utils import ok_response, now_ms
        result = ok_response({"foo": "bar"}, started_ms=now_ms())
        assert result["ok"] is True
        assert "data" in result
        assert "errors" in result
        assert "meta" in result
        assert isinstance(result["errors"], list)
        assert "duration_ms" in result["meta"]

    def test_error_response_shape(self):
        from onpe_mcp.utils import error_response, now_ms
        result = error_response("algo falló", started_ms=now_ms(), code="TEST_ERR")
        assert result["ok"] is False
        assert result["data"] is None
        assert len(result["errors"]) == 1
        assert result["errors"][0]["code"] == "TEST_ERR"
        assert "duration_ms" in result["meta"]

    def test_ok_response_data_preserved(self):
        from onpe_mcp.utils import ok_response, now_ms
        data = {"intent": "mesa", "answer": "Mesa 900100", "result": {"votos": 100}}
        result = ok_response(data, started_ms=now_ms())
        assert result["data"]["intent"] == "mesa"
        assert result["data"]["result"]["votos"] == 100
