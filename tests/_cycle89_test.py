"""Cycle 89: blancos+nulos geo, ganador/vencedor nacional, verbo-prefix candidate guard, resultados nacionales."""
from onpe_mcp.server import onpe_chat


def intent(q):
    return onpe_chat(q)["data"]["intent"]


# blancos y nulos + dept → geo_domestic
def test_c89_blancos_nulos_lima():
    assert intent("blancos y nulos en lima") == "geo_domestic"

def test_c89_nulos_blancos_arequipa():
    assert intent("nulos y blancos en arequipa") == "geo_domestic"

def test_c89_votos_blancos_en_cusco():
    assert intent("votos blancos en cusco") == "geo_domestic"

def test_c89_votos_nulos_en_piura():
    assert intent("votos nulos en piura") == "geo_domestic"

def test_c89_votos_viciados_en_puno():
    assert intent("votos viciados en puno") == "geo_domestic"

# blancos y nulos sin geo → nacional
def test_c89_blancos_nulos_sin_geo():
    assert intent("blancos y nulos") == "nacional"

def test_c89_votos_blancos_sin_geo():
    assert intent("cuantos votos blancos hubo") == "nacional"

def test_c89_cuantos_nulos():
    assert intent("cuantos nulos hay a nivel nacional") == "nacional"

# el ganador / vencedor / presidente electo → nacional
def test_c89_cuantos_votos_saco_el_ganador():
    assert intent("cuantos votos saco el ganador") == "nacional"

def test_c89_cuantos_votos_obtuvo_el_presidente_electo():
    assert intent("cuantos votos obtuvo el presidente electo") == "nacional"

def test_c89_cuantos_votos_tuvo_el_vencedor():
    assert intent("cuantos votos tuvo el vencedor") == "nacional"

def test_c89_cuantos_votos_obtuvo_el_ganador():
    assert intent("cuantos votos obtuvo el ganador") == "nacional"

def test_c89_quien_fue_el_ganador():
    assert intent("quien fue el ganador") == "nacional"

def test_c89_cuantos_votos_logro_el_lider():
    assert intent("cuantos votos logro el lider") == "nacional"

# real candidate queries still work (no regression)
def test_c89_aliaga_saco_cuantos_votos():
    assert intent("aliaga saco cuantos votos") == "candidate"

def test_c89_cuantos_votos_tuvo_aliaga():
    assert intent("cuantos votos tuvo aliaga") == "candidate"

def test_c89_cuantos_votos_obtuvo_fujimori():
    assert intent("cuantos votos obtuvo fujimori") == "candidate"

def test_c89_cuantos_votos_saco_nieto():
    assert intent("cuantos votos saco nieto") == "candidate"

def test_c89_cuantos_votos_saco_lopez_aliaga_en_lima():
    assert intent("cuantos votos saco lopez aliaga en lima") == "candidate"

def test_c89_resultados_de_aliaga():
    assert intent("resultados de aliaga") == "candidate"

# resultados nacionales → nacional (not candidate)
def test_c89_resultados_nacionales():
    assert intent("resultados nacionales") == "nacional"

def test_c89_resultados_electorales():
    assert intent("resultados electorales") == "nacional"

# geo queries with electoral modifiers
def test_c89_resultados_electorales_en_moquegua():
    assert intent("resultados electorales en moquegua") == "geo_domestic"

def test_c89_resultados_electorales_en_el_peru():
    assert intent("resultados electorales en el peru") == "nacional"

def test_c89_votos_validos_totales_nacional():
    assert intent("votos validos totales a nivel nacional") == "nacional"

def test_c89_votos_blancos_nacional():
    assert intent("votos blancos a nivel nacional") == "nacional"

# geo + valid queries
def test_c89_como_cerraron_votos_piura():
    assert intent("como cerraron los votos en piura") == "geo_domestic"

def test_c89_votos_cierre_cusco():
    assert intent("votos al cierre en cusco") == "geo_domestic"

def test_c89_quien_gano_elecciones():
    assert intent("quien gano las elecciones") == "nacional"

def test_c89_quien_perdio_elecciones():
    assert intent("quien perdio las elecciones") == "nacional"

# candidate combos with geo
def test_c89_aliaga_y_fujimori_en_loreto():
    assert intent("aliaga y fujimori en loreto") == "multi_candidate"

def test_c89_comparacion_aliaga_fujimori():
    assert intent("comparacion entre aliaga y fujimori en lima") == "multi_candidate"

# cuantos viciados/nulos por dept
def test_c89_cuantos_viciados_en_loreto():
    assert intent("cuantos viciados en loreto") == "geo_domestic"

def test_c89_cuantos_nulos_en_cusco():
    assert intent("cuantos nulos en cusco") == "geo_domestic"
