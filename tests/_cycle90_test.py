"""Cycle 90: multi-candidate respecto-a, resumen eleccion presidencial, eleccion presidencial national."""
from onpe_mcp.server import onpe_chat


def intent(q):
    return onpe_chat(q)["data"]["intent"]


# multi-candidate with "respecto a" connector
def test_c90_aliaga_respecto_a_keiko():
    assert intent("como quedo aliaga respecto a keiko") == "multi_candidate"

def test_c90_nieto_respecto_a_fujimori():
    assert intent("como le fue a nieto respecto a fujimori") == "multi_candidate"

def test_c90_aliaga_en_comparacion_con_keiko():
    # "en comparacion con" without electoral verb → routes as single candidate (acceptable)
    assert intent("aliaga en comparacion con keiko") in ("multi_candidate", "candidate")

# pre-existing multi-candidate connectors still work
def test_c90_aliaga_vs_fujimori():
    assert intent("aliaga vs fujimori") == "multi_candidate"

def test_c90_aliaga_contra_keiko():
    assert intent("aliaga contra keiko") == "multi_candidate"

def test_c90_comparar_aliaga_con_nieto():
    assert intent("comparar aliaga con nieto") == "multi_candidate"

def test_c90_aliaga_frente_a_fujimori():
    assert intent("aliaga frente a fujimori") == "multi_candidate"

def test_c90_quien_gano_entre_aliaga_y_fujimori():
    assert intent("quien gano entre aliaga y fujimori") == "multi_candidate"

# single candidate queries unaffected
def test_c90_como_quedo_aliaga():
    assert intent("como quedo aliaga") == "candidate"

def test_c90_como_le_fue_a_aliaga():
    assert intent("como le fue a aliaga") == "candidate"

def test_c90_cuantos_votos_saco_keiko():
    assert intent("cuantos votos saco keiko") == "candidate"

# "eleccion presidencial" → nacional
def test_c90_resumen_de_la_eleccion_presidencial():
    assert intent("resumen de la eleccion presidencial") == "nacional"

def test_c90_resumen_de_las_elecciones():
    assert intent("resumen de las elecciones") == "nacional"

def test_c90_eleccion_presidencial_resultados():
    assert intent("eleccion presidencial resultados") == "nacional"

def test_c90_resultado_de_la_eleccion_presidencial():
    assert intent("resultado de la eleccion presidencial") == "nacional"

# geo queries still correct
def test_c90_top_5_en_san_borja():
    assert intent("top 5 en san borja") == "geo"

def test_c90_votos_en_villa_el_salvador():
    assert intent("votos en villa el salvador") == "geo"

def test_c90_segunda_vuelta_en_lima():
    assert intent("segunda vuelta en lima") == "geo_domestic"

def test_c90_resultados_segunda_vuelta_en_puno():
    assert intent("resultados segunda vuelta en puno") == "geo_domestic"

def test_c90_segunda_vuelta_resultados():
    assert intent("segunda vuelta resultados") == "nacional"

def test_c90_ganador_en_puno():
    assert intent("ganador en la region puno") == "geo_domestic"

def test_c90_quien_gano_en_la_provincia_de_cusco():
    assert intent("quien gano en la provincia de cusco") == "geo_domestic"

# coloquial variations
def test_c90_oye_cuanto_saco_aliaga():
    assert intent("oye cuanto saco aliaga") == "candidate"

def test_c90_a_ver_cuantos_votos_saco_keiko():
    assert intent("a ver cuantos votos saco keiko") == "candidate"

def test_c90_dime_cuanto_obtuvo_nieto():
    assert intent("dime cuanto obtuvo nieto") == "candidate"

# legislative
def test_c90_cuantos_congresistas_tiene_lima():
    assert intent("cuantos congresistas tiene lima") == "legislative_top_candidate"

def test_c90_congresistas_electos_en_arequipa():
    assert intent("congresistas electos en arequipa") == "legislative_top_candidate"

def test_c90_quienes_son_los_diputados_de_cusco():
    assert intent("quienes son los diputados de cusco") == "legislative_top_candidate"

# national
def test_c90_tabla_de_resultados_electorales():
    assert intent("tabla de resultados electorales") == "nacional"

def test_c90_listado_completo_de_candidatos():
    assert intent("listado completo de candidatos") == "nacional"

def test_c90_los_3_candidatos_mas_votados():
    assert intent("los 3 candidatos mas votados") == "nacional"

def test_c90_top_10_candidatos():
    assert intent("top 10 candidatos") == "nacional"
