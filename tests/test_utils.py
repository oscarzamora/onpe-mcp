from onpe_mcp.utils import (
    extract_foreign_geo_candidates,
    extract_mesa_prefix_claim,
    extract_top_n,
    validate_mesa_code,
)


def test_validate_mesa_code_normaliza() -> None:
    assert validate_mesa_code("123") == "000123"


def test_validate_mesa_code_rechaza_no_numerico() -> None:
    try:
        validate_mesa_code("12A3")
        assert False, "debe fallar"
    except ValueError:
        assert True


def test_extract_top_n_detecta_numero_en_lenguaje_natural() -> None:
    assert extract_top_n("top 3 de candidatos en suecia") == 3
    assert extract_top_n("dame los primeros 7 resultados") == 7


def test_extract_foreign_geo_candidates_normaliza_paises_y_ciudades() -> None:
    candidates = extract_foreign_geo_candidates("top 3 de candidatos en suecia")
    assert (None, "suecia") in candidates

    city_candidates = extract_foreign_geo_candidates("resultados en estocolmo")
    assert (None, "estocolmo") in city_candidates


def test_extract_mesa_prefix_claim_expande_shorthand_900k() -> None:
    assert extract_mesa_prefix_claim("mesas 900K") == "900000"
    assert extract_mesa_prefix_claim("arrancan en 900000") == "900000"
