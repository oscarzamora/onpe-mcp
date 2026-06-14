"""Cycle 88: geo override phrases, participacion, avance, resultados finales/totales/definitivos, que paso en las elecciones."""
from onpe_mcp.server import onpe_chat


def intent(q):
    return onpe_chat(q)["data"]["intent"]


# participacion electoral + dept → geo_domestic
def test_c88_participacion_electoral_lima():
    assert intent("cuanto fue la participacion electoral en lima") == "geo_domestic"

def test_c88_participacion_electoral_arequipa():
    assert intent("participacion electoral en arequipa") == "geo_domestic"

def test_c88_participacion_electoral_cusco():
    assert intent("participacion electoral en cusco") == "geo_domestic"

def test_c88_participacion_en_elecciones_lima():
    assert intent("participacion en las elecciones de lima") == "geo_domestic"

def test_c88_participacion_porcentaje_piura():
    assert intent("que porcentaje de participacion hubo en piura") == "geo_domestic"

def test_c88_participacion_madre_de_dios():
    assert intent("que tan alta fue la participacion en madre de dios") == "geo_domestic"

def test_c88_participacion_puno():
    assert intent("cuanto fue la participacion en puno") == "geo_domestic"

def test_c88_porcentaje_participacion_cusco():
    assert intent("porcentaje de participacion en cusco") == "geo_domestic"

def test_c88_participacion_loreto():
    assert intent("participacion electoral en loreto") == "geo_domestic"

# participacion sin geo → nacional
def test_c88_participacion_electoral_sin_geo():
    assert intent("participacion electoral") == "nacional"

def test_c88_porcentaje_participacion_sin_geo():
    assert intent("porcentaje de participacion") == "nacional"

# avance del conteo + dept → geo_domestic
def test_c88_avance_conteo_ancash():
    assert intent("avance del conteo en ancash") == "geo_domestic"

def test_c88_avance_conteo_loreto():
    assert intent("avance del conteo en loreto") == "geo_domestic"

def test_c88_como_va_conteo_loreto():
    assert intent("como va el conteo en loreto") == "geo_domestic"

def test_c88_avance_escrutinio_tacna():
    assert intent("avance del escrutinio en tacna") == "geo_domestic"

# avance sin geo → nacional
def test_c88_avance_conteo_sin_geo():
    assert intent("avance del conteo") == "nacional"

# resultados finales/totales/definitivos + dept → geo_domestic
def test_c88_resultados_finales_puno():
    assert intent("resultados finales en puno") == "geo_domestic"

def test_c88_resultados_totales_arequipa():
    assert intent("resultados totales en arequipa") == "geo_domestic"

def test_c88_resultados_definitivos_lima():
    assert intent("resultados definitivos en lima") == "geo_domestic"

def test_c88_resultados_parciales_cusco():
    assert intent("resultados parciales en cusco") == "geo_domestic"

def test_c88_resultados_oficiales_ica():
    assert intent("resultados oficiales en ica") == "geo_domestic"

def test_c88_resultados_actualizados_piura():
    assert intent("resultados actualizados en piura") == "geo_domestic"

# que paso en las elecciones
def test_c88_que_paso_elecciones_puno():
    assert intent("que paso en las elecciones en puno") == "geo_domestic"

def test_c88_como_fue_elecciones_arequipa():
    assert intent("como fue en las elecciones en arequipa") == "geo_domestic"

def test_c88_que_paso_elecciones_sin_geo():
    assert intent("que paso en las elecciones") == "nacional"

# como quedo + geo (from cycle 88 fixes)
def test_c88_como_quedo_conteo_puno():
    assert intent("como quedo el conteo en puno") == "geo_domestic"

def test_c88_como_quedo_votacion_arequipa():
    assert intent("como quedo la votacion en arequipa") == "geo_domestic"

def test_c88_como_quedo_resultado_lima():
    assert intent("como quedo el resultado en lima") == "geo_domestic"

def test_c88_como_van_resultados_cusco():
    assert intent("como van los resultados en cusco") == "geo_domestic"

def test_c88_como_quedo_conteo_sin_geo():
    assert intent("como quedo el conteo") == "nacional"

def test_c88_como_van_resultados_sin_geo():
    assert intent("como van los resultados") == "nacional"

# porcentaje de mesas / conteo (no dep) → nacional
def test_c88_porcentaje_mesas_escrutadas():
    assert intent("porcentaje de mesas escrutadas") == "nacional"

def test_c88_total_mesas_escrutadas():
    assert intent("total de mesas escrutadas") == "nacional"

def test_c88_porcentaje_escrutinio():
    assert intent("porcentaje de escrutinio") == "nacional"

# candidatos con mas votos + geo
def test_c88_candidatos_mas_votos_lima():
    assert intent("candidatos con mas votos en lima") == "geo_domestic"

def test_c88_candidatos_mas_votados_arequipa():
    assert intent("candidatos mas votados en arequipa") == "geo_domestic"

def test_c88_candidatos_mas_votos_sin_geo():
    assert intent("candidatos con mas votos") == "nacional"

# regression: basic geo + nacional still work
def test_c88_resultados_nacionales():
    assert intent("resultados nacionales") == "nacional"

def test_c88_top_3_loreto():
    assert intent("top 3 en loreto") == "geo_domestic"

def test_c88_resultados_piura():
    assert intent("resultados en piura") == "geo_domestic"
