"""Cycle 91: electores/ciudadanos votaron → nacional; statistical/regional queries."""
from onpe_mcp.server import onpe_chat


def intent(q):
    return onpe_chat(q)["data"]["intent"]


# cuantos electores/ciudadanos votaron → nacional
def test_c91_cuantos_electores_votaron():
    assert intent("cuantos electores votaron") == "nacional"

def test_c91_cuantos_ciudadanos_votaron():
    assert intent("cuantos ciudadanos votaron") == "nacional"

def test_c91_cuantos_peruanos_sufragaron():
    assert intent("cuantos peruanos sufragaron") == "nacional"

def test_c91_cuantas_personas_participaron():
    assert intent("cuantas personas participaron") == "nacional"

def test_c91_cuantos_peruanos_fueron_a_votar():
    assert intent("cuantos peruanos fueron a votar") == "nacional"

# geo guard: electores + dept → geo_domestic
def test_c91_cuantos_electores_en_lima():
    assert intent("cuantos electores votaron en lima") == "geo_domestic"

def test_c91_cuantos_ciudadanos_en_puno():
    assert intent("cuantos ciudadanos participaron en puno") == "geo_domestic"

def test_c91_cuantos_votantes_en_arequipa():
    assert intent("cuantos votantes hubo en arequipa") == "geo_domestic"

# statistical queries → nacional
def test_c91_promedio_votos():
    assert intent("promedio de votos por candidato") == "nacional"

def test_c91_varianza_votos():
    assert intent("varianza de votos entre candidatos") == "nacional"

def test_c91_cuantos_votos_en_total():
    assert intent("cuantos votos en total hubo") == "nacional"

def test_c91_suma_total_votos():
    assert intent("suma total de votos") == "nacional"

def test_c91_total_votos_emitidos():
    assert intent("total de votos emitidos") == "nacional"

def test_c91_total_votos_validos():
    assert intent("total de votos validos") == "nacional"

# regional/macro → nacional
def test_c91_resultados_en_la_sierra():
    assert intent("resultados en la sierra") == "nacional"

def test_c91_resultados_en_la_selva():
    assert intent("resultados en la selva") == "nacional"

def test_c91_votos_en_la_costa_peruana():
    assert intent("votos en la costa peruana") == "nacional"

# year-based queries
def test_c91_resultados_elecciones_2026():
    assert intent("resultados elecciones 2026") == "nacional"

def test_c91_elecciones_2026_lima():
    assert intent("elecciones 2026 lima") == "geo_domestic"

def test_c91_candidatos_elecciones_2026():
    assert intent("candidatos elecciones 2026") == "nacional"

# candidate percentage by dept
def test_c91_porcentaje_aliaga_en_loreto():
    assert intent("porcentaje de aliaga en loreto") == "candidate"

def test_c91_porcentaje_keiko_en_arequipa():
    assert intent("porcentaje de keiko en arequipa") == "candidate"

# multi-candidate with "se dice que"
def test_c91_se_dice_que_nieto_tuvo_mas_votos_que_aliaga():
    assert intent("se dice que nieto tuvo mas votos que aliaga") == "multi_candidate"

# geo sub-district queries
def test_c91_top_5_en_san_borja():
    assert intent("top 5 en san borja") in ("geo", "geo_domestic")

def test_c91_votos_en_villa_el_salvador():
    assert intent("votos en villa el salvador") in ("geo", "geo_domestic")

# regression: national still correct
def test_c91_quien_gano_las_elecciones():
    assert intent("quien gano las elecciones") == "nacional"

def test_c91_resultados_nacionales():
    assert intent("resultados nacionales") == "nacional"
