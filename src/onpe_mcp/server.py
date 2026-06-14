# pyright: reportMissingImports=false

from __future__ import annotations

import difflib
import logging
from typing import Any
import re
import unicodedata

try:
    from mcp.server.fastmcp import FastMCP
except Exception:  # pragma: no cover
    FastMCP = None  # type: ignore[assignment]

from .config import Settings
from .gateway import GatewayError, OnpeScraperGateway
from .knowledge_base import get_context_notes, get_fallback_qualitative, data_tier_label
from .onpe_api import OnpeApiClient, OnpeApiError
from .storage import DataStore
from .utils import (
    configure_logging,
    error_response,
    extract_foreign_geo_candidates,
    extract_mesa_prefix_claim,
    extract_top_n,
    find_peru_department_prefix,
    now_ms,
    ok_response,
    parse_quantitative_claims,
    classify_claim_topic,
    validate_mesa_code,
)
from onpe_mcp.storage import _CITY_ALIASES as _STATIC_CITY_ALIASES


settings = Settings.from_env()
configure_logging(settings.log_level)
logger = logging.getLogger("onpe_mcp")

gateway = OnpeScraperGateway(settings)
store = DataStore(settings.data_dir)
onpe_api = OnpeApiClient()

# Verificar si los datos SV están cargados
try:
    _sv_total = store.total_mesas_sv_local()
except Exception:
    _sv_total = 0

try:
    gateway.ensure_ready()
except GatewayError as exc:
    # Degraded mode: onpescraper no disponible (sin red, sin git, etc.)
    # El servidor arranca igual — usa onpe_api directamente y ATuManera CSV como fuente.
    logger.warning(
        "onpescraper no disponible: %s. "
        "Operando en modo degradado: live API + ATuManera CSV. "
        "Para hidratar la DB llama a onpe_bootstrap_atu_manera.",
        exc,
    )

if FastMCP is None:  # pragma: no cover
    raise RuntimeError(
        "No se pudo importar 'mcp.server.fastmcp'. Instala dependencias con: pip install -e ."
    )

mcp = FastMCP("onpe-mcp")

# Flag de sesión: el catálogo extranjero solo se sincroniza una vez por proceso.
_foreign_catalog_synced: bool = False


def _is_local_only() -> bool:
    return bool(settings.local_only)


# Patrones para detectar consultas de votos por candidato sin keyword "candidato".
# Compilados una vez a nivel de módulo para evitar overhead por llamada.
_CANDIDATE_VOTE_PATTERNS = [
    # "cuántos votos sacó/tuvo/obtuvo/logró/consiguió/recibió/juntó X"
    # incluye plural "sacaron/tuvieron/obtuvieron" para multi-candidato
    # acepta "en total", "fue que" intercalados: "cuántos votos fue que obtuvo X"
    # acepta typos b/v frecuentes en español peruano: tubo/obtubo/obtubieron
    # acepta "había/habría obtenido" (pluscuamperfecto / condicional compuesto)
    re.compile(
        r"\bcu[aá]ntos?\s+(?:votos?|sufragios?)\s+(?:en\s+total\s+|fue\s+que\s+|se\s+|habr?[ií]a\s+|hab[ií]a\s+)?(?:tuvo|tuvieron|tubo|tubieron|sac[oó]|sacaron|tiene|tienen|obtuvo|obtuvieron|obtubo|obtubieron|gan[oó]|ganaron|logr[oó]|lograron|consigui[oó]|consiguieron|recibi[oó]|recibieron|junt[oó]|juntaron|lleva|llevan|lleba|lleban|llev[oó]|llevaron|acumula|acumulan|acumul[oó]|sum[oó]|sumaron|lleg[oó]|llegaron|alcanz[oó]|alcanzaron|adjudic[oó]|adjudicados?|asign[oó]|asignados?|otorg[oó]|otorgados?|atribuy[oó]|capt[oó]|captaron|hizo|hicieron|reuni[oó]|reunieron|jal[oó]|jalaron|chap[oó]|chaparon|pesc[oó]|pescaron|dispone|disponia|dispuso|obtenido|logrado|conseguido|sacado|ganado|recibido|juntado|alcanzado|captado)\s+(.+?)(?:\s+(?:en|a\s+nivel|para)\b.*)?$",
        re.IGNORECASE,
    ),
    # "cuánto sacó/obtuvo X" / "que porcentaje obtuvo X" / "que resultado tuvo X"
    # acepta palabras intermedias: "cuanto porcentaje saco X", "cuantos puntos tuvo X"
    # acepta "habia/habria sacado" (pluscuamperfecto / condicional)
    # Nota: "total" eliminado del trailing para evitar capturar solo "en" en "cuanto saco en total el X"
    re.compile(
        r"\b(?:cu[aá]ntos?\s+(?:habr?[ií]a\s+|hab[ií]a\s+)?(?:\w+\s+)?|qu[eé]\s+(?:porcentaje|puntaje|puntos?|lugar|posici[oó]n|resultado[s]?)\s+(?:de\s+votos?\s+)?)(?:sac[oó]|sacado|obtuvo|obtenido|logr[oó]|logrado|llev[oó]|llevado|anot[oó]|junt[oó]|juntado|consigui[oó]|conseguido|recibi[oó]|recibido|tiene|tuvo|lleg[oó]|llegado|alcanz[oó]|alcanzado)\s+(.+?)(?:\s+(?:en|a\s+nivel|en\s+total)\b.*)?$",
        re.IGNORECASE,
    ),
    # "votos de X" / "votos totales de X" / "número de votos de X"
    re.compile(
        r"\bvotos?\s+(?:totales?\s+)?(?:de|que\s+(?:sac[oó]|tuvo|obtuvo|logr[oó]))\s+(.+?)(?:\s+(?:en|a\s+nivel|total|nacional)\b.*)?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bn[uú]mero\s+de\s+votos?\s+(?:de|que\s+(?:sac[oó]|tuvo|obtuvo|junt[oó]|logr[oó]))\s+(.+?)(?:\s+(?:en|a\s+nivel|total|nacional)\b.*)?$",
        re.IGNORECASE,
    ),
    # "que numero de votos junto/obtuvo X"
    re.compile(
        r"\bqu[eé]\s+n[uú]mero\s+de\s+votos?\s+(?:junt[oó]|tuvo|obtuvo|sac[oó]|logr[oó]|recibi[oó]|alcanz[oó])\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$",
        re.IGNORECASE,
    ),
    # "votos en la elección de X" → candidato X
    re.compile(
        r"\bvotos?\s+en\s+(?:la\s+)?elecci[oó]n\s+de\s+(.+?)(?:\s+(?:en|a\s+nivel|total|nacional)\b.*)?$",
        re.IGNORECASE,
    ),
    # "qué resultados/votos/porcentaje tuvo/obtuvo/sacó X"
    re.compile(
        r"\bqu[eé]\s+(?:result(?:ados?|[oó])|votos?|porcentaje|puntuaci[oó]n|puntaje|lugar|posici[oó]n|tanto\s+apoyo|apoyo|respaldo)\s+(?:tuvo|obtuvo|sac[oó]|logr[oó]|consigui[oó]|recibi[oó]|alcanz[oó])\s+(.+?)$",
        re.IGNORECASE,
    ),
    # "que saco/obtuvo/logro NAME" — sin palabra intermedia entre "que" y verbo
    re.compile(
        r"\bqu[eé]\s+(?:sac[oó]|obtuvo|logr[oó]|tuvo|consigui[oó]|recibi[oó]|alcanz[oó]|lleg[oó]|jal[oó])\s+(?:el\s+partido\s+|el\s+|la\s+)?([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,40}?)(?:\s+(?:en|a\s+nivel)\b.*)?$",
        re.IGNORECASE,
    ),
    # "que tanto saco/obtuvo NAME" — "que tanto" directo sin palabra intermedia
    re.compile(
        r"\bqu[eé]\s+tanto\s+(?:sac[oó]|obtuvo|logr[oó]|tuvo|recibi[oó]|alcanz[oó]|consigui[oó]|lleg[oó])\s+(?:el\s+partido\s+|el\s+|la\s+)?([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,40}?)(?:\s+(?:en|a\s+nivel)\b.*)?$",
        re.IGNORECASE,
    ),
    # "que tanto apoyo/respaldo tuvo/logró X"
    re.compile(
        r"\bqu[eé]\s+tanto\s+(?:apoyo|respaldo|votos?|porcentaje|aceptacion)\s+(?:tuvo|obtuvo|logr[oó]|recibi[oó]|sac[oó]|alcanz[oó])\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$",
        re.IGNORECASE,
    ),
    # "que tanto voto/votaron por/la gente por NAME" — coloquial sin "cuantos votos"
    re.compile(
        r"\b(?:cu[aá]nto|qu[eé]\s+tanto)\s+vot[oó](?:\s+\w+){0,4}\s+(?:por|a\s+favor\s+de)\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,35}?)(?:\s*[.,?!]|$)",
        re.IGNORECASE,
    ),
    # "voto[ron] por NAME" / "votaron a favor de NAME"
    re.compile(
        r"\bvotaron?\s+(?:por|a\s+favor\s+de)\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,35}?)(?:\s+(?:en|a\s+nivel)\b.*)?$",
        re.IGNORECASE,
    ),
    # "votos a favor de NAME" / "cuantos votos a favor de NAME"
    re.compile(
        r"\bvotos?\s+a\s+favor\s+de\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,35}?)(?:\s+(?:en|a\s+nivel)\b.*)?$",
        re.IGNORECASE,
    ),
    # "resultados de X" / "resultados nacionales de X" / "puntaje de X" / "resultados del X" / "resultados para X" / "porcentaje de X"
    re.compile(
        r"\b(?:result(?:ados?|[oó])(?:\s+(?:electorales?|nacionales?|totales?|parciales?|finales?|provisorios?|oficiales?))?\s+(?:de|del|para)|puntaje\s+(?:de|del)|porcentaje\s+(?:de|del|que\s+obtuvo|que\s+sac[oó]))\s+(.+?)(?:\s+(?:en|a\s+nivel|total|nacional)\b.*)?$",
        re.IGNORECASE,
    ),
    # "votación de X" / "votación total de X"
    re.compile(
        r"\bvotaci[oó]n\s+(?:total\s+)?(?:de\s+)?(.+?)(?:\s+(?:en|a\s+nivel|total|nacional)\b.*)?$",
        re.IGNORECASE,
    ),
    # "marcador de X" / "puntuación de X" / "performance de X" / "ranking de X"
    re.compile(
        r"\b(?:marcador|puntuaci[oó]n|performance|ranking|resumen\s+de\s+votos)\s+de\s+(.+?)(?:\s+(?:en|a\s+nivel|total|nacional)\b.*)?$",
        re.IGNORECASE,
    ),
    # "qué lugar sacó X" / "cuál fue el lugar de X" / "en qué posición quedó X"
    re.compile(
        r"\b(?:qu[eé]\s+(?:lugar|posici[oó]n|puesto)\s+(?:sac[oó]|tiene|obtuvo|qued[oó])|cu[aá]l\s+(?:fue|es)\s+(?:el|la)\s+(?:lugar|posici[oó]n|puesto)\s+de)\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$",
        re.IGNORECASE,
    ),
    # "a cuanto llegó/llego X" / "hasta cuanto llego X en el conteo" / "en cuanto quedó X"
    re.compile(
        r"\b(?:a|en)\s+cu[aá]nto\s+(?:lleg[oó]|qued[oó]|termin[oó]|acab[oó]|cerr[oó])\s+(.+?)(?:\s+(?:en|a\s+nivel|total|en\s+el)\b.*)?$",
        re.IGNORECASE,
    ),
    # "a cuanto llego X" original (mantener compatibilidad)
    re.compile(
        r"\ba\s+cu[aá]nto(?:s|\s+votos?)?\s+lleg[oó]\s+(.+?)(?:\s+(?:en|a\s+nivel|total|en\s+el)\b.*)?$",
        re.IGNORECASE,
    ),
    # "en la primera/segunda vuelta X cuantos votos" — el período precede al candidato
    re.compile(
        r"\ben\s+la\s+(?:primera|segunda|primera|primer)\s+vuelta\s+(.+?)\s+cu[aá]ntos?\s+votos?\s+(?:sac[oó]|tuvo|obtuvo|logr[oó]|consigui[oó])?",
        re.IGNORECASE,
    ),
    # "X cuántos votos" (order reversed) — also "X cuántos lleva/tiene/acumula"
    # Trailing allows "en GEO" at end (e.g., "Fujimori cuanto llevo en Lima")
    re.compile(
        r"^(.+?)\s+cu[aá]ntos?\s*(?:votos?\s*)?(?:sac[oó]|tuvo|tiene|obtuvo|lleva|llev[oó]|lleg[oó]|acumula|sum[oó]|consigui[oó]|jal[oó])?(?:\s+en\s+\S.*)?$",
        re.IGNORECASE,
    ),
    # "que salio/resulto/quedo NAME en las elecciones" — "que salio Aliaga"
    re.compile(
        r"\bqu[eé]\s+(?:sali[oó]|result[oó]|qued[oó]|le\s+fue|puntaje\s+tuvo)\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,35}?)(?:\s+en\b.*)?$",
        re.IGNORECASE,
    ),
    # "NAME que tan alto/bien llego/quedo" — coloquial
    re.compile(
        r"^([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,35}?)\s+(?:qu[eé]\s+tan\s+\w+|c[oó]mo)\s+(?:lleg[oó]|sali[oó]|qued[oó]|termin[oó])",
        re.IGNORECASE,
    ),
    # Bare "NAME en GEO" / "NAME en GEO?" — fallback for queries sin verbo
    re.compile(
        r"^([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{2,40}?)\s+en\s+\w",
        re.IGNORECASE,
    ),
    # "NAME PLACE votos/resultados/porcentaje" — bare 3-token candidate+geo pattern
    re.compile(
        r"^([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,30}?)\s+[A-Za-záéíóúñÁÉÍÓÚÑ]{3,}\s+(?:votos?|resultados?|porcentaje|datos?)\b",
        re.IGNORECASE,
    ),
    # "NAME votos en GEO" — candidate name (≤3 words) before "votos en"
    re.compile(
        r"^([A-Za-záéíóúñÁÉÍÓÚÑ]+(?:\s+[A-Za-záéíóúñÁÉÍÓÚÑ]+){0,2})\s+votos?\s+en\s+\w",
        re.IGNORECASE,
    ),
    # "candidato NAME en GEO" / "candidato NAME" — explicit candidate label
    # Stop before interrogative words ("cuantos votos tuvo") to avoid capturing them
    re.compile(
        r"\bcandidato\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{2,40}?)(?:\s+(?:cu[aá]ntos?|qu[eé]|c[oó]mo|en|a\s+nivel)\b.*)?$",
        re.IGNORECASE,
    ),
    # "votos NAME" — reversed order (votos before name)
    re.compile(
        r"^votos?\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,35})$",
        re.IGNORECASE,
    ),
    # "NAME votos" — bare name followed by votos (order reversed, no verb)
    re.compile(
        r"^([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,35})\s+votos?\s*$",
        re.IGNORECASE,
    ),
    # "NAME resultados" — reversed order (resultados after name)
    re.compile(
        r"^([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,35})\s+resultados?$",
        re.IGNORECASE,
    ),
    # "resultados NAME" — bare "resultados" + candidate name (no preposition)
    re.compile(
        r"^resultados?\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,35})$",
        re.IGNORECASE,
    ),
    # "NAME qué tal / cómo le fue" — coloquial candidate inquiry
    re.compile(
        r"^([A-Za-záéíóúñÁÉÍÓÚÑ]+(?:\s+[A-Za-záéíóúñÁÉÍÓÚÑ]+){0,2})\s+(?:qu[eé]\s+tal|c[oó]mo\s+(?:le\s+)?(?:fue|quedo|qued[oó]|va))\b",
        re.IGNORECASE,
    ),
    # "sobre/acerca de NAME en GEO" / "datos sobre NAME"
    re.compile(
        r"\b(?:sobre|acerca\s+de|datos?\s+(?:de|sobre))\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{2,40}?)(?:\s+(?:en|a\s+nivel)\b.*)?$",
        re.IGNORECASE,
    ),
    # "le fue a NAME en GEO" / "qué tal le fue a NAME" — coloquial sin sujeto al inicio
    re.compile(
        r"\b(?:qu[eé]\s+tal\s+)?le\s+fu[eé]\s+a\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,30}?)(?:\s+(?:en|a\s+nivel)\b.*)?$",
        re.IGNORECASE,
    ),
    # "cómo quedó/fue NAME en GEO" / "como salio NAME en" — coloquial con verbo+nombre
    re.compile(
        r"\bc[oó]mo\s+(?:qued[oó]?|fue|sali[oó]|termin[oó])\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,30}?)(?:\s+en\b.*)?$",
        re.IGNORECASE,
    ),
    # "votos de/del/para NAME en GEO" — "votos de RLA en Lima"
    re.compile(
        r"\bvotos?\s+(?:de[l]?|para|por)\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,40}?)(?:\s+(?:en|a\s+nivel)\b.*)?$",
        re.IGNORECASE,
    ),
    # Passive voice: "votos fueron adjudicados/asignados/otorgados a NAME"
    re.compile(
        r"\bvotos?\s+(?:le\s+)?(?:fueron|han\s+sido|fueron\s+le)\s+(?:adjudicados?|asignados?|otorgados?|atribuidos?|dados?|entregados?)\s+a\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,40}?)(?:\s+(?:en|a\s+nivel)\b.*)?$",
        re.IGNORECASE,
    ),
    # "cuantos votos le fueron adjudicados/asignados a NAME"
    re.compile(
        r"\bcu[aá]ntos?\s+votos?\s+(?:le\s+)?(?:fueron|han\s+sido)\s+(?:adjudicados?|asignados?|otorgados?|atribuidos?|dados?)\s+a\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,40}?)(?:\s+(?:en|a\s+nivel)\b.*)?$",
        re.IGNORECASE,
    ),
    # "cuantos le dieron/pusieron/sacaron a NAME" — coloquial sin "votos"
    re.compile(
        r"\bcu[aá]ntos?\s+(?:le\s+)?(?:dieron|daban|pusieron|sacaron|quitaron|cargaron)\s+(?:a\s+|los?\s+)?([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,40}?)(?:\s+(?:en|a\s+nivel)\b.*)?$",
        re.IGNORECASE,
    ),
    # "cuantos votos NAME" — bare form without verb (e.g. "cuantos votos Aliaga")
    re.compile(
        r"\bcu[aá]ntos?\s+votos?\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,40}?)(?:\s+(?:en|a\s+nivel)\b.*)?$",
        re.IGNORECASE,
    ),
    # "sufragios obtenidos/logrados por NAME" / "sufragios de NAME" — variante con sufragios
    re.compile(
        r"\bsufragios?\s+(?:obtenidos?\s+(?:por|de)|logrados?\s+(?:por|de)|de|para|por)\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,40}?)(?:\s+(?:en|a\s+nivel)\b.*)?$",
        re.IGNORECASE,
    ),
]

# Aliases culturales/coloquiales para candidatos.
# Clave: expresión normalizada (lowercase, sin tildes).
# Valor: fragmento del nombre canónico del candidato en candidato.txt.
# Se usa cuando el candidato pedido no existe en 2026 para dar una sugerencia.
_CANDIDATE_CULTURAL_ALIASES: dict[str, str] = {
    # Pedro Castillo (2021) → su equivalente "del sombrero" en 2026 es Roberto Sánchez
    "pedro castillo": "sanchez",
    "castillo":       "sanchez",
    # Referencias directas al sombrero
    "sombrero":                 "sanchez",
    "del sombrero":             "sanchez",
    "el del sombrero":          "sanchez",
    "el sombrero":              "sanchez",
    "hombre del sombrero":      "sanchez",
    "candidato del sombrero":   "sanchez",
    "candidato sombrero":       "sanchez",
}

# Expresiones que NO son nombres de candidato aunque coincidan con patrones de voto.
# Ej: "resultados de peruanos en Argentina" → "peruanos" no es candidato.
_NON_CANDIDATE_EXPRESSIONS: frozenset[str] = frozenset({
    "peruanos", "peruanas", "ciudadanos", "ciudadanas", "electores",
    "votantes", "personas", "residentes", "extranjeros", "candidatos", "candidato",
    "todos", "nadie", "alguien",
    # Stop words que aparecen antes de "en" en queries geo puras
    "resultados", "resultado", "top", "primero", "primer", "segundo",
    "tercero", "cuarto", "quinto", "primeros", "votos", "voto",
    "informacion", "info", "dato", "datos",
    # Pronombres/palabras interrogativas
    "ganador", "ganadores", "quien", "quienes", "quienes ganaron",
    "quienes son", "que candidato", "cual candidato",
    # Frases nacionales que pueden capturar el patrón bare "X en GEO"
    "mas votados", "los mas votados", "votados", "mas votos",
    "los que mas votos", "el mas votado",
    # Tipos de votos que NO son candidatos
    "nulos", "blancos", "viciados", "impugnados",
    "votos nulos", "votos blancos", "votos viciados",
    # Palabras electorales que NO son nombres de candidato
    "elecciones", "eleccion", "comicios", "sufragio",
    "votacion", "votaciones", "sufragios",  # "resultado de la votacion en X" no es un candidato
    "congreso", "asamblea", "parlamento",
    "vuelta", "primera vuelta", "segunda vuelta",  # ej: "resultados de segunda vuelta en Piura"
    "primera", "segunda",  # evitar captura de "segunda vuelta resultados" como candidato "segunda"
    "tanto", "ambos", "ambas",  # ej: "tanto Keiko como Aliaga"
    # Palabras geográficas que no son nombres de candidato
    "region", "departamento", "provincia", "distrito", "localidad", "municipio",
    "municipalidad",
    "diaspora", "inmigrantes", "migrantes", "comunidad", "compatriotas",
    # Pronombres relativos que no son nombres de candidato
    "que", "cual", "cuales",  # "el que gano en Arequipa" → geo, no candidato
    # Palabras de código/número que no son candidato
    "codigo", "codigos", "numero", "numeros", "id",
    # Colectivos y verbos coloquiales que no son nombres de candidato
    "me", "oye", "cuanto", "cuantos", "cuanta", "cuantas",
    "gente", "pueblo", "poblacion",
    "puedes", "puede", "puedo", "podria", "dime", "sabes", "sabe", "entiendo",
    "paso", "paso en",  # verbo "pasó" coloquial en preguntas geográficas
    "como",  # verbo/pronombre — capturado por Pattern 9 como "como quedo" antes del nuevo patrón
    # Palabras que NUNCA son candidatos
    "pais", "exterior", "extranjero", "extranjera",
    "nivel", "nacional", "nacionales",  # "a nivel nacional" / "resultados nacionales"
    "electorales", "electoral",  # "resultados electorales"
    # Roles genéricos de resultado electoral (no son nombres propios)
    "ganador", "ganadora", "ganadores", "ganadoras", "el ganador", "la ganadora",
    "vencedor", "vencedora", "vencedores", "el vencedor", "la vencedora",
    "lider", "lideres", "el lider",
    "presidente electo", "presidente electa", "el presidente electo",
    "segundo lugar", "primer lugar", "tercer lugar",
    # Verbos existenciales / auxiliares que no son nombres de candidato
    "hubo", "habia", "habian", "habia habido", "hobo", "hay", "habia",
    "hubo", "tenia", "tuve", "existen", "existio",
    "dame", "deme", "danos", "muestra", "mostrar", "muestrame", "digame",
    "resumen", "estadistica", "estadisticas", "tabla", "listado", "grafico",
    "distribucion", "reporte", "informe",
    # Adjetivos de resultado que NO son nombres de candidato
    "finales", "final", "definitivos", "definitivo", "provisorios", "provisorio",
    "parciales", "parcial", "totales", "total", "generales", "general",
    "preliminares", "preliminar", "oficiales", "oficial", "actualizados", "actualizado",
    # Participios de conteo electoral que no son candidatos
    "emitidos", "emitido", "computados", "computado", "contabilizados", "contabilizado",
    "procesados", "procesado", "validos", "valido", "invalidos", "invalido",
    "sufragados", "sufragado", "depositados", "depositado",
    # Sustantivos de proceso/estadística que no son candidatos
    "participacion", "abstenciones", "abstencion", "concurrencia", "asistencia",
    "ranking", "clasificacion", "posicion", "posiciones",
    # Sustantivos de avance/proceso que no son candidatos
    "avance", "recuento", "conteo", "acumulado", "acumulados", "acumulada",
    "preliminar", "provisorio", "definitivo",
    "escrutinio", "escrutados", "escrutadas", "escrutado", "escrutada",
    "viciados", "viciado", "observados", "observado", "impugnados", "impugnado",
    # Formas singulares de participio que no son candidatos
    "votado", "mas votado", "mas votados",
    # Departamentos peruanos — nunca son nombres de candidato
    "lima", "arequipa", "callao", "cusco", "cuzco", "piura", "la libertad",
    "junin", "puno", "cajamarca", "lambayeque", "loreto", "ica", "ucayali",
    "ancash", "san martin", "amazonas", "tacna", "moquegua", "huancavelica",
    "apurimac", "tumbes", "madre de dios", "pasco", "huanuco", "ayacucho",
})
_MULTI_CANDIDATE_PATTERN = re.compile(
    r"\bvotos?\s+(?:de\s+)?(.+?)\s+(?:y|e)\s+(.+?)(?:\s+(?:en|a\s+nivel|total)\b.*)?$"
    r"|\b(.+?)\s+y\s+(.+?)\s+cu[aá]ntos?\s+votos?"
    r"|\bcomparar?\s+(?:a\s+)?(?:votos?\s+(?:de\s+)?)?(.+?)\s+(?:y|con|versus|vs\.?)\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\b([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,40}?)\s+y\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,40}?)\s+en\b"
    r"|\b(.+?)\s+versus\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\b(.+?)\s+vs\.?\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\bdiferencia\s+(?:de\s+votos?\s+)?entre\s+(.+?)\s+y\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\bentre\s+(.+?)\s+y\s+(.+?)(?:\s+(?:en|a\s+nivel|quien)\b.*)?$"
    r"|\b(.+?)\s+frente\s+a\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\b(.+?)\s+contra\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\b(.+?)\s+o\s+(.+?)\s+(?:quien|cu[aá]l|cu[aá]ntos?)\s+(?:sac[oó]|tuvo|obtuvo|tiene|tiene\s+m[aá]s|gan[oó]|logr[oó]|va|lleva|lidera|est[aá])"
    r"|\bgan[oó]\s+(.+?)\s+o\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\bquien\s+(?:sac[oó]|tuvo|obtuvo|tiene)\s+m[aá]s\s+(.+?)\s+o\s+(.+?)(?:\?|$)"
    r"|\b(.+?)\s+cu[aá]ntos?\s+votos?\s+(?:y|e)\s+(.+?)\s+cu[aá]ntos?\s+votos?"
    r"|\b(?:si\s+)?(.+?)\s+(?:le\s+)?gan[oó]\s+(?:a|contra)\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\btanto\s+(.+?)\s+como\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\b(.+?)\s+(?:tuvo|sac[oó]|obtuvo|tiene)\s+m[aá]s\s+votos?\s+que\s+(.+?)(?:\s+(?:en|a\s+nivel|verdad|no\s*\?|cierto)\b.*)?$"
    r"|\bcu[aá]ntos?\s+m[aá]s\s+votos?\s+(?:tuvo|sac[oó]|obtuvo|tiene|lleva)\s+(.+?)\s+que\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\bcu[aá]nto\s+m[aá]s\s+(?:sac[oó]|tuvo|obtuvo|lleva|tiene)\s+(.+?)\s+que\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\bcompar[ae]\s+(.+?)\s+con\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\b(.+?)\s+m[aá]s\s+que\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\b(.+?)\s+y\s+(.+?)\s+(?:quien(?:es)?|cu[aá]l(?:es)?)\s+(?:van|gano|tiene|saco|obtuvo|est[aá]n?|lider[oó]|qued[oó])\b"
    r"|\b(.+?)\s+y\s+(.+?)\s+quienes?\s+(?:sac[oó]|sacaron|obtuv[io]eron?|gan[oó]|ganaron|tienen?|llevan?|jalaron?)\b"
    r"|\b(.+?)\s+y\s+(.+?)\s+comparaci[oó]n\s+(?:de\s+)?votos?\b"
    r"|\bcomparaci[oó]n\s+(?:de\s+votos?\s+)?(?:de\s+|entre\s+)?(.+?)\s+y\s+(.+?)(?:\s*$|\s+(?:en|a\s+nivel)\b)",
    re.IGNORECASE,
)


def _try_bootstrap_snapshot_on_startup() -> None:
    """Hidratación automática al arrancar.

    Regla: si la DB está VACÍA la hidratación es MANDATORIA — se intenta
    independientemente de bootstrap_on_startup.  El flag solo controla si se
    hace un refresh proactivo cuando la DB ya tiene datos.

    Prioridad:
      1. onpescraper local (más actual — datos vivos scrapeados)
      2. ATuManera CSV público (fallback — snapshot estático desde GitHub)
      3. Aviso crítico — servidor opera en modo degradado (solo live API).
    """
    from pathlib import Path as _Path

    def _run_atu_manera_bootstrap(reason: str) -> dict:
        try:
            csv_path = _Path(settings.atu_manera_csv_path) if settings.atu_manera_csv_path else None
            result = store.bootstrap_from_atu_manera_csv(csv_path, id_eleccion=12, force=False)
            logger.info("atu_manera_bootstrap reason=%s result=%s", reason, result)
            return result
        except Exception:
            logger.exception("Falló bootstrap ATuManera CSV (reason=%s)", reason)
            return {}

    # ── Verificar estado actual de la DB ────────────────────────────────────
    try:
        total = store.total_mesas_local()
    except Exception:
        total = 0

    is_empty = total == 0

    # DB con datos + bootstrap deshabilitado → no hacer nada más
    if not is_empty and not settings.bootstrap_on_startup:
        logger.debug("DB tiene %d mesas y bootstrap_on_startup=False — omitiendo refresh.", total)
        return

    onpescraper_output = settings.output_dir
    onpescraper_has_data = (onpescraper_output / "mesas_data.txt").exists()

    # ── Paso 1: onpescraper (fuente más actual) ──────────────────────────────
    if onpescraper_has_data:
        try:
            result = store.bootstrap_from_onpescraper(
                output_dir=onpescraper_output,
                source_dir=settings.source_dir,
                include_votes=settings.bootstrap_include_votes,
                source="startup",
                id_eleccion=10,
                force=False,
            )
            mesas_after = result.get("mesas", 0) if isinstance(result, dict) else 0
            logger.info(
                "onpescraper_bootstrap_startup result=%s mesas_after=%s", result, mesas_after
            )
            if mesas_after > 0:
                is_empty = False
        except Exception:
            logger.exception("Falló bootstrap desde onpescraper al iniciar")
    else:
        logger.info(
            "onpescraper output no disponible en %s.", onpescraper_output,
        )

    # ── Paso 2: ATuManera CSV habilitado explícitamente ──────────────────────
    if settings.atu_manera_bootstrap:
        _run_atu_manera_bootstrap("env_enabled")
        is_empty = store.total_mesas_local() == 0

    # ── Paso 3 (MANDATORIO): si DB sigue vacía → descarga ATuManera CSV ──────
    if is_empty:
        logger.warning(
            "DB vacía al arrancar — hidratación MANDATORIA. "
            "Descargando ATuManera CSV (~92 766 mesas, 1-3 min según red)."
        )
        result = _run_atu_manera_bootstrap("cold_start_mandatory")
        mesas_loaded = result.get("mesas", 0) if isinstance(result, dict) else 0
        if mesas_loaded > 0:
            logger.info("Hidratacion cold-start completada: %d mesas cargadas.", mesas_loaded)
        else:
            logger.critical(
                "HIDRATACION FALLIDA: no se pudo cargar datos desde ninguna fuente. "
                "El servidor opera en modo degradado (solo live API). "
                "Para hidratar manualmente llama a onpe_bootstrap_snapshot() o "
                "onpe_bootstrap_atu_manera()."
            )



_try_bootstrap_snapshot_on_startup()

# Si el catálogo extranjero ya tiene datos en SQLite, no es necesario re-sincronizar.
try:
    with store._connect() as _startup_conn:
        _fcat_count = _startup_conn.execute(
            "SELECT COUNT(*) AS c FROM foreign_catalog"
        ).fetchone()["c"]
    if _fcat_count > 0:
        _foreign_catalog_synced = True
except Exception:
    pass


def _norm(text: str) -> str:
    base = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(ch for ch in base if not unicodedata.combining(ch))
    return stripped.casefold().strip()


# Muletillas verbales que se eliminan del INICIO de la query para normalizar
# lenguaje natural antes del matching NLU.
_FILLER_START = re.compile(
    r"^(?:"
    r"a\s+ver[,\s]+"
    r"|(?:me\s+)?(?:puedes?\s+)?(?:decir|dime|cuéntame|cuentame|mostrarme|muéstrame|mostrar|ver)[,\s]+"
    r"|(?:puedes?\s+)?(?:mostrarme|muéstrame|mostrar|ver)[,\s]+"
    r"|(?:quiero|quisiera|necesito|podri[aá]s?\s+decirme|podr[íi]a[s]?\s+decirme)\s+(?:saber\s+|ver\s+)?"
    r"|(?:oye|oiga|escucha)[,\s]+"
    r"|(?:ponme|dame|muestrame|muéstrame|dime)[,\s]+"
    r"|sabes?\s+"
    r"|(?:por\s+favor[,\s]+)?"
    r"|(?:dime\s+)?"
    r"|(?:(?:me\s+)?(?:puedes?|podr[íi]as?)\s+(?:decirme\s+|mostrarme?\s+|ver\s+)?)?"
    r")",
    re.IGNORECASE,
)
# Muletillas o cortesías al FINAL
_FILLER_END = re.compile(
    r"(?:[,\s]+(?:por\s+favor|porfavor|gracias|please))+$",
    re.IGNORECASE,
)


def _strip_filler(text: str) -> str:
    """Elimina muletillas verbales de inicio/fin para normalizar lenguaje natural.
    Itera hasta estabilizarse para manejar cadenas de muletillas (ej: 'oye sabes cuanto')."""
    t = text.strip()
    for _ in range(5):  # máximo 5 pases
        t2 = _FILLER_START.sub("", t)
        t2 = _FILLER_END.sub("", t2).strip()
        if not t2:
            break
        if t2 == t:
            break
        t = t2
    return t if t else text.strip()


def _geo_query_cache_key(field: str | None, expr: str, top_n: int) -> str:
    return f"field={field or 'any'}|expr={_norm(expr)}|top={top_n}"


def _resolve_foreign_geo_query(query: str) -> tuple[str | None, str, list[dict[str, str]]] | None:
    for field, expr in extract_foreign_geo_candidates(query):
        matches = store.find_foreign_ubigeos(expr, field=field)
        if matches:
            return field, expr, matches
    return None


def _resolve_domestic_geo_query(q: str) -> tuple[str, set[str]] | None:
    """Resuelve una geo doméstica peruana. Primero tabla ubigeo_reniec, luego prefijos por departamento,
    luego fallback estático contra _CITY_ALIASES (sin DB — funciona aunque la DB esté vacía)."""
    reniec_result = store.find_domestic_ubigeos_by_geo_name(q)
    if reniec_result is not None:
        geo_name, ubigeos = reniec_result
        return geo_name, set(ubigeos)
    dept_result = find_peru_department_prefix(q)
    if dept_result is not None:
        dept_name, dept_prefix = dept_result
        ubigeos = set(store.find_ubigeos_by_prefix(dept_prefix))
        return dept_name, ubigeos
    # Fallback estático: no requiere DB. Escanea la query buscando alias conocidos.
    # Garantiza que NLU detecte intent=geo_domestic aunque la DB esté vacía (ej. CI).
    q_norm = _norm(q)
    for alias_key in _STATIC_CITY_ALIASES:
        if re.search(r"\b" + re.escape(alias_key) + r"\b", q_norm):
            return alias_key, set()
    return None


def _coverage_verdict(coverage_pct: float) -> str:
    if coverage_pct >= 90:
        return "completo"
    if coverage_pct >= 50:
        return "parcial"
    if coverage_pct > 0:
        return "muestra_pequena"
    return "sin_datos"


def _auto_hydrate_mesas(mesa_codes: list[str], id_eleccion: int, timeout: int) -> int:
    """Hidrata mesas faltantes desde ONPE API. Retorna cuántas se hidrataron exitosamente."""
    if _is_local_only():
        return 0
    hydrated = 0
    for code in mesa_codes:
        try:
            data = onpe_api.get_mesa(code, id_eleccion=id_eleccion, timeout=timeout)
            store.upsert_mesa_bundle(code, data, source="auto_hydrate", id_eleccion=id_eleccion)
            hydrated += 1
        except Exception:
            logger.debug("auto_hydrate: falló mesa %s", code)
    return hydrated


def _resolve_sv_dpto_from_query(q: str) -> tuple[str, str] | None:
    """Resuelve un departamento usando los ubigeos ONPE (no INEI) del scraper SV.

    Lee `sv_resumen_cobertura` (que tiene `nombre_departamento` y `ubigeo` ONPE)
    y matchea por palabra completa normalizada contra la query.

    Returns (nombre_dpto, prefijo_2dig) o None.
    """
    try:
        with store._connect() as conn:
            rows = conn.execute(
                "SELECT ubigeo, nombre_departamento FROM sv_resumen_cobertura WHERE nombre_departamento != ''"
            ).fetchall()
    except Exception:
        return None
    q_n = _norm(q)
    best: tuple[str, str] | None = None
    best_len = 0
    for r in rows:
        nm_raw = str(r["nombre_departamento"] or "").strip()
        nm_norm = _norm(nm_raw)
        if not nm_norm:
            continue
        if re.search(r"\b" + re.escape(nm_norm) + r"\b", q_n):
            if len(nm_norm) > best_len:
                best = (nm_raw, str(r["ubigeo"])[:2])
                best_len = len(nm_norm)
    return best


def _detect_jee_intent(q: str, q_norm: str) -> dict[str, Any] | None:
    """Detecta intent SV de actas observadas / envío al JEE / escenario "todas aceptadas".

    Retorna dict listo para ok_response (con keys intent/answer/result/source) o
    None si la query no aplica.
    """
    has_jee = bool(
        "jee" in q_norm
        or "jurado electoral especial" in q_norm
        or "jurado electoral nacional" in q_norm
        or re.search(r"\bact[ao]s?\s+observad", q_norm)
        or re.search(r"\bmesa[s]?\s+observad", q_norm)
        or re.search(r"\bact[ao]s?\s+(?:para\s+)?env[ií]o\b", q_norm)
        or re.search(r"\bmesa[s]?\s+(?:para\s+)?env[ií]o\b", q_norm)
        or re.search(
            r"\b(?:si|cuando|que\s+pasa\s+si).{0,30}(?:acepta[a-z]*|aprueba[a-z]*|valid[a-z]+).{0,30}(?:todas|las|observad|jee|actas|mesas)\b",
            q_norm,
        )
        or re.search(r"\bestado\s+de\s+(?:las\s+)?act[ao]s?\b", q_norm)
        or re.search(r"\bestado\s+de\s+(?:las\s+)?mesa[s]?\b", q_norm)
        or re.search(r"\bescenario\s+jee\b", q_norm)
    )
    if not has_jee:
        return None

    # Si total mesas SV == 0, indicar bootstrap pendiente
    if store.total_mesas_sv_local() == 0:
        return {
            "intent": "sv_not_bootstrapped",
            "answer": (
                "⚠️ No hay datos de segunda vuelta en la base local. "
                "Ejecuta **onpe_sv_bootstrap()** para cargar los datos."
            ),
        }

    # Resolver filtro geográfico opcional (solo departamento)
    ubigeo_prefix: str | None = None
    geo_label = "nacional"
    dept_match = _resolve_sv_dpto_from_query(q)
    if dept_match:
        geo_label, ubigeo_prefix = dept_match

    result = store.get_sv_estado_actas(ubigeo_prefix=ubigeo_prefix, top_geo=10)
    tot = result["totales"]
    esc = result["escenario_jee_aceptadas"]
    margen_a = esc["margen_si_aceptadas"]
    margen_act = esc["margen_actual"]
    pendientes_e = tot["para_envio_jee_E"]
    pendientes_p = tot["pendientes_P"]
    contab = tot["contabilizadas_C"]
    mesas_tot = tot["mesas"]

    # Generar respuesta legible
    lines = [
        f"**Estado de actas — segunda vuelta 2026** ({geo_label}):\n",
        f"- **Contabilizadas (C):** {contab:,} mesas",
        f"- **Para envío al JEE (E):** {pendientes_e:,} mesas observadas",
    ]
    if pendientes_p:
        lines.append(f"- **Pendientes (P):** {pendientes_p:,} mesas")
    lines.append(f"- **Total:** {mesas_tot:,} mesas")

    if margen_a.get("lider") and margen_a.get("ventaja") is not None:
        # Buscar nombres legibles del top 2
        top2 = [r for r in esc["con_jee_aceptadas"] if r["partido_id"] not in ("80", "81", "82")][:2]
        if len(top2) >= 2:
            t0, t1 = top2[0], top2[1]
            lines.append("")
            lines.append('**Escenario "si el JEE acepta todas las observadas":**')
            lines.append(
                f"- {t0['nombre']}: {t0['votos']:,} ({t0['pct_validos']:.2f}%)"
            )
            lines.append(
                f"- {t1['nombre']}: {t1['votos']:,} ({t1['pct_validos']:.2f}%)"
            )
            ventaja_a = margen_a["ventaja"]
            ventaja_pp_a = margen_a["ventaja_pp"]
            lider_nombre_a = margen_a.get("lider_nombre") or t0["nombre"]
            lines.append(
                f"- Margen proyectado: **+{ventaja_a:,} votos ({ventaja_pp_a:+.3f} pp)** a favor de {lider_nombre_a}."
            )
            if margen_act.get("lider") and margen_act.get("ventaja") is not None:
                lines.append(
                    f"  (Margen actual solo con C: {margen_act['ventaja']:+,} votos, "
                    f"{margen_act['ventaja_pp']:+.3f} pp.)"
                )

    if not ubigeo_prefix and result.get("geo_top_jee"):
        lines.append("")
        lines.append("**Concentración de mesas observadas (top 5):**")
        for g in result["geo_top_jee"][:5]:
            nm = g.get("nombre") or g.get("dpto_prefix")
            lines.append(
                f"- {nm}: {g['mesas_E']:,} mesas ({g['electores_E']:,} electores)"
            )

    lines.append("")
    lines.append(
        "⚠️ Escenario teórico: el JEE puede anular, recontar o reasignar votos. "
        "No es un pronóstico, solo la suma directa de lo ya reportado."
    )

    return {
        "intent": "sv_estado_actas",
        "answer": "\n".join(lines),
        "result": result,
        "source": "sqlite_sv",
    }


def _build_coverage_block(
    q_norm: str,
    id_eleccion: int,
    timeout: int,
    *,
    prefix: str | None = None,
    ubigeos: set[str] | None = None,
) -> dict[str, Any]:
    """Computa cobertura, hidrata si es necesario y retorna bloque coverage completo."""
    metrics = store.get_coverage_metrics(prefix=prefix, ubigeos=ubigeos)
    hydrated = 0
    if (
        settings.auto_hydrate_on_demand
        and metrics["total_mesas"] > 0
        and metrics["coverage_pct"] < 90
    ):
        uncovered = store.get_uncovered_mesas(
            prefix=prefix,
            ubigeos=ubigeos,
            limit=settings.auto_hydrate_max_mesas,
        )
        if uncovered:
            hydrated = _auto_hydrate_mesas(uncovered, id_eleccion, timeout)
            if hydrated > 0:
                metrics = store.get_coverage_metrics(prefix=prefix, ubigeos=ubigeos)
    verdict = _coverage_verdict(metrics["coverage_pct"])
    return {**metrics, "verdict": verdict, "hydrated_this_call": hydrated}


def _hydrate_missing_city_department_by_prefix(mesa_prefix: str, id_eleccion: int) -> int:
    """Completa ciudad/departamento faltantes por ubigeo consultando ONPE y cacheando en SQLite."""
    if _is_local_only():
        return 0
    missing_ubigeos = store.find_ubigeos_missing_city_or_department_by_mesa_prefix(mesa_prefix, limit=50)
    if not missing_ubigeos:
        return 0

    upserts = 0
    for ubigeo in missing_ubigeos:
        try:
            location = onpe_api.resolve_location_by_ubigeo(ubigeo, id_eleccion=id_eleccion)
            if location and store.upsert_ubigeo_location(location):
                upserts += 1
        except Exception:
            logger.exception("Falló hidratación de ubicación para ubigeo=%s", ubigeo)
    return upserts


def _hydrate_missing_city_department_by_ubigeo_prefix(ubigeo_prefix: str, id_eleccion: int) -> int:
    """Completa ciudad/departamento faltantes por prefijo de ubigeo (departamento)."""
    if _is_local_only():
        return 0
    missing_ubigeos = store.find_ubigeos_missing_city_or_department_by_ubigeo_prefix(
        ubigeo_prefix,
        limit=50,
    )
    if not missing_ubigeos:
        return 0

    upserts = 0
    for ubigeo in missing_ubigeos:
        try:
            location = onpe_api.resolve_location_by_ubigeo(ubigeo, id_eleccion=id_eleccion)
            if location and store.upsert_ubigeo_location(location):
                upserts += 1
        except Exception:
            logger.exception("Falló hidratación de ubicación (prefijo ubigeo) para ubigeo=%s", ubigeo)
    return upserts


@mcp.tool()
def onpe_get_mesa(
    codigo_mesa: str,
    id_eleccion: int = 10,
    timeout: int = 30,
    base_url: str | None = None,
    force_live: bool = False,
) -> dict[str, Any]:
    """Consulta una mesa ONPE y devuelve cabecera, agrupaciones y votos."""
    started_ms = now_ms()
    try:
        code = validate_mesa_code(codigo_mesa)
        id_eleccion = max(1, int(id_eleccion))
        timeout = max(1, min(int(timeout), 120))
        if _is_local_only() and force_live:
            return error_response(
                "force_live no está permitido en modo local-only.",
                started_ms=started_ms,
                code="LOCAL_ONLY_MODE",
            )

        cached = None if force_live else store.get_cached_mesa(code, settings.cache_ttl_seconds)
        if cached is not None:
            logger.info("tool=onpe_get_mesa codigo_mesa=%s source=cache", code)
            return ok_response(cached, started_ms=started_ms, meta={"source": "sqlite_cache"})

        local_bundle = store.get_mesa_from_local(code)
        if local_bundle is not None:
            return ok_response(local_bundle, started_ms=started_ms, meta={"source": "local_db"})

        if _is_local_only():
            return error_response(
                f"No hay datos locales para la mesa {code}.",
                started_ms=started_ms,
                code="DATA_NOT_AVAILABLE_LOCAL",
            )

        data = onpe_api.get_mesa(
            code,
            id_eleccion=id_eleccion,
            timeout=timeout,
            base_url=base_url,
        )
        store.upsert_mesa_bundle(
            code,
            data,
            source=base_url or "https://resultadoelectoral.onpe.gob.pe/presentacion-backend",
            id_eleccion=id_eleccion,
        )
        mesa_data = data.get("mesa_data") or {}
        ubigeo = str(mesa_data.get("ubigeo") or "").strip()
        if ubigeo:
            try:
                location = onpe_api.resolve_location_by_ubigeo(ubigeo, id_eleccion=id_eleccion)
                if location:
                    store.upsert_ubigeo_location(location)
            except Exception:
                logger.exception("No se pudo hidratar ubicación para ubigeo=%s", ubigeo)
        store.append_raw_event(
            "onpe_get_mesa",
            {
                "codigo_mesa": code,
                "id_eleccion": id_eleccion,
                "found": bool(data.get("found")),
            },
        )
        logger.info("tool=onpe_get_mesa codigo_mesa=%s found=%s", code, data.get("found"))
        return ok_response(data, started_ms=started_ms, meta={"source": "onpe_live"})
    except ValueError as exc:
        return error_response(str(exc), started_ms=started_ms, code="VALIDATION_ERROR")
    except GatewayError as exc:
        return error_response(str(exc), started_ms=started_ms, code="GATEWAY_ERROR")
    except Exception as exc:  # pragma: no cover
        logger.exception("Error inesperado en onpe_get_mesa")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_get_mesas_batch(
    codigos_mesa: list[str],
    id_eleccion: int = 10,
    timeout: int = 30,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Consulta varias mesas y devuelve resultados por item, sin abortar por errores individuales."""
    started_ms = now_ms()
    try:
        if not isinstance(codigos_mesa, list) or not codigos_mesa:
            raise ValueError("codigos_mesa debe ser una lista no vacía")

        if len(codigos_mesa) > settings.max_batch_size:
            raise ValueError(
                f"El lote excede el máximo permitido ({settings.max_batch_size})."
            )

        id_eleccion = max(1, int(id_eleccion))
        timeout = max(1, min(int(timeout), 120))

        items: list[dict[str, Any]] = []
        found = 0

        for raw_code in codigos_mesa:
            try:
                code = validate_mesa_code(str(raw_code))
                mesa = store.get_cached_mesa(code, settings.cache_ttl_seconds)
                if mesa is None:
                    mesa = store.get_mesa_from_local(code)
                if mesa is None and _is_local_only():
                    raise ValueError(f"No hay datos locales para la mesa {code}.")
                if mesa is None:
                    mesa = onpe_api.get_mesa(
                        code,
                        id_eleccion=id_eleccion,
                        timeout=timeout,
                        base_url=base_url,
                    )
                if mesa.get("found"):
                    found += 1
                items.append({"codigo_mesa": code, "ok": True, "result": mesa, "error": None})
            except Exception as item_exc:
                items.append(
                    {
                        "codigo_mesa": str(raw_code),
                        "ok": False,
                        "result": None,
                        "error": str(item_exc),
                    }
                )

        response_data = {
            "total": len(items),
            "found": found,
            "not_found": len(items) - found,
            "items": items,
        }
        logger.info("tool=onpe_get_mesas_batch total=%s found=%s", len(items), found)
        return ok_response(response_data, started_ms=started_ms)
    except ValueError as exc:
        return error_response(str(exc), started_ms=started_ms, code="VALIDATION_ERROR")
    except GatewayError as exc:
        return error_response(str(exc), started_ms=started_ms, code="GATEWAY_ERROR")
    except Exception as exc:  # pragma: no cover
        logger.exception("Error inesperado en onpe_get_mesas_batch")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_health() -> dict[str, Any]:
    """Verifica rutas críticas e importación del backend scraper."""
    started_ms = now_ms()
    try:
        scraper_root = settings.scraper_root
        source_dir = settings.source_dir
        output_dir = settings.output_dir

        total_mesas = 0
        total_votos = 0
        total_mesas_2021_v1 = 0
        total_mesas_2021_v2 = 0
        try:
            total_mesas = store.total_mesas_local()
            with store._connect() as _c:
                total_votos = int((_c.execute("SELECT COUNT(*) AS c FROM votos").fetchone() or {"c": 0})["c"])
            total_mesas_2021_v1 = store.total_mesas_2021(1)
            total_mesas_2021_v2 = store.total_mesas_2021(2)
        except Exception:
            pass

        hydrated = total_mesas > 0
        onpescraper_has_data = (output_dir / "mesas_data.txt").exists()

        if hydrated:
            next_step = None
        elif onpescraper_has_data:
            next_step = "Llama a onpe_bootstrap_snapshot() para cargar datos de onpescraper (más actualizado)."
        else:
            next_step = (
                "Llama a onpe_bootstrap_atu_manera() para descargar las 92,766 mesas (~2-5 min). "
                "O clona https://github.com/oscarzamora/onpeescraper en carpeta hermana y llama onpe_bootstrap_snapshot()."
            )

        checks = {
            "scraper_root_exists": scraper_root.exists(),
            "source_dir_exists": source_dir.exists(),
            "output_dir_exists": output_dir.exists(),
            "sqlite_db_exists": store.db_path.exists(),
            "onpescraper_has_data": onpescraper_has_data,
            "db_hydrated": hydrated,
        }

        import_ok = True
        import_error = None
        try:
            gateway._ensure_import()
        except Exception as exc:
            import_ok = False
            import_error = str(exc)

        status = "ok" if hydrated and import_ok else ("degraded" if hydrated else "not_hydrated")

        data = {
            "status": status,
            "hydrated": hydrated,
            "total_mesas_local": total_mesas,
            "total_votos_local": total_votos,
            "total_mesas_2021_v1": total_mesas_2021_v1,
            "total_mesas_2021_v2": total_mesas_2021_v2,
            "next_step": next_step,
            "checks": checks,
            "import_onpe_scraper_ok": import_ok,
            "import_onpe_scraper_error": import_error,
            "paths": {
                "scraper_root": str(scraper_root),
                "source_dir": str(source_dir),
                "output_dir": str(output_dir),
                "data_dir": str(settings.data_dir),
                "sqlite_db": str(store.db_path),
            },
            "limits": {
                "max_batch_size": settings.max_batch_size,
                "cache_ttl_seconds": settings.cache_ttl_seconds,
                "geo_query_cache_ttl_seconds": settings.geo_query_cache_ttl_seconds,
            },
        }

        return ok_response(data, started_ms=started_ms)
    except Exception as exc:  # pragma: no cover
        logger.exception("Error inesperado en onpe_health")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_sync_foreign_catalog(id_eleccion: int | None = None) -> dict[str, Any]:
    """Sincroniza país/ciudad extranjero directamente desde API ONPE hacia SQLite."""
    started_ms = now_ms()
    try:
        if _is_local_only():
            return error_response(
                "onpe_sync_foreign_catalog está deshabilitado en modo local-only.",
                started_ms=started_ms,
                code="LOCAL_ONLY_MODE",
            )
        election_id, rows = onpe_api.build_foreign_catalog(id_eleccion)
        upserted = store.upsert_foreign_catalog(rows)
        store.append_raw_event(
            "onpe_sync_foreign_catalog",
            {
                "id_eleccion": election_id,
                "rows": len(rows),
                "upserted": upserted,
            },
        )
        return ok_response(
            {
                "id_eleccion": election_id,
                "rows": len(rows),
                "upserted": upserted,
            },
            started_ms=started_ms,
        )
    except OnpeApiError as exc:
        return error_response(str(exc), started_ms=started_ms, code="ONPE_API_ERROR")
    except Exception as exc:  # pragma: no cover
        logger.exception("Error inesperado en onpe_sync_foreign_catalog")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_sync_domestic_catalog(id_eleccion: int | None = None) -> dict[str, Any]:
    """Sincroniza el catálogo completo de ubigeos domésticos (departamentos/provincias/distritos)
    directamente desde la API ONPE hacia SQLite. Permite consultas por ciudades como Pucallpa,
    Iquitos, Tarapoto, etc. aunque no sean nombres de distritos en RENIEC."""
    started_ms = now_ms()
    try:
        if _is_local_only():
            return error_response(
                "onpe_sync_domestic_catalog está deshabilitado en modo local-only.",
                started_ms=started_ms,
                code="LOCAL_ONLY_MODE",
            )
        election_id, rows = onpe_api.build_domestic_catalog(id_eleccion)
        upserted = store.upsert_domestic_ubigeos_from_api(rows)
        store.append_raw_event(
            "onpe_sync_domestic_catalog",
            {
                "id_eleccion": election_id,
                "rows": len(rows),
                "upserted": upserted,
            },
        )
        return ok_response(
            {
                "id_eleccion": election_id,
                "rows": len(rows),
                "upserted": upserted,
            },
            started_ms=started_ms,
        )
    except OnpeApiError as exc:
        return error_response(str(exc), started_ms=started_ms, code="ONPE_API_ERROR")
    except Exception as exc:
        logger.exception("Error inesperado en onpe_sync_domestic_catalog")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_bootstrap_snapshot(include_votes: bool = True, force: bool = False) -> dict[str, Any]:
    """Importa snapshot local de onpescraper hacia SQLite para acelerar consultas (sin bloquear fallback live API)."""
    started_ms = now_ms()
    try:
        result = store.bootstrap_from_onpescraper(
            output_dir=settings.output_dir,
            source_dir=settings.source_dir,
            include_votes=bool(include_votes),
            source="manual_tool",
            id_eleccion=10,
            force=bool(force),
        )
        return ok_response(result, started_ms=started_ms, meta={"source": "onpescraper_snapshot"})
    except Exception as exc:  # pragma: no cover
        logger.exception("Error inesperado en onpe_bootstrap_snapshot")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_bootstrap_atu_manera(
    csv_path: str = "",
    force: bool = False,
) -> dict[str, Any]:
    """Importa las 92,766 mesas presidenciales desde el CSV público de ATuManera/Peru_elecciones2026.

    Fuente: https://github.com/ATuManera/Peru_elecciones2026
    Si csv_path está vacío, intenta descargarlo desde GitHub (requiere conexión).
    Pasa force=true para reimportar aunque ya haya mesas en la base.
    """
    started_ms = now_ms()
    try:
        from pathlib import Path as _Path
        resolved_path = _Path(csv_path) if csv_path else None
        result = store.bootstrap_from_atu_manera_csv(
            resolved_path,
            id_eleccion=12,
            force=bool(force),
        )
        return ok_response(result, started_ms=started_ms, meta={"source": "atu_manera_csv"})
    except Exception as exc:
        logger.exception("Error inesperado en onpe_bootstrap_atu_manera")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_sv_bootstrap(force: bool = False) -> dict[str, Any]:
    """Importa todos los datos de segunda vuelta 2026 desde el scraper local hacia SQLite.

    Carga mesas, votos, agrupaciones, ubicaciones, locales reasignados y resúmenes geográficos.
    También calcula agregaciones CTAS (distrito, ciudad) y siembra el mapa de transferencia.
    Si force=false y ya hay datos, solo retorna estadísticas.
    """
    started_ms = now_ms()
    try:
        result = store.bootstrap_segunda_vuelta(
            sv_output_dir=settings.sv_output_dir,
            sv_resumen_dir=settings.sv_resumen_dir,
            force=bool(force),
        )
        store.append_raw_event("onpe_sv_bootstrap", result)
        return ok_response(result, started_ms=started_ms)
    except Exception as exc:
        logger.exception("Error en onpe_sv_bootstrap")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_sv_refresh() -> dict[str, Any]:
    """Recarga los datos de segunda vuelta desde el scraper local (incremental UPSERT).

    Usar cuando el scraper ha actualizado sus archivos con nuevas mesas contabilizadas.
    Hace UPSERT de todos los archivos y reconstruye las tablas CTAS (distrito, ciudad).
    """
    started_ms = now_ms()
    try:
        result = store.onpe_sv_refresh_from_scraper(
            sv_output_dir=settings.sv_output_dir,
            sv_resumen_dir=settings.sv_resumen_dir,
        )
        store.append_raw_event("onpe_sv_refresh", result)
        return ok_response(result, started_ms=started_ms)
    except Exception as exc:
        logger.exception("Error en onpe_sv_refresh")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_sv_get_mesa(codigo_mesa: str) -> dict[str, Any]:
    """Consulta una mesa de segunda vuelta 2026 desde el cache local.

    Retorna cabecera, votos y ubicación de la mesa en segunda vuelta.
    """
    started_ms = now_ms()
    try:
        code = validate_mesa_code(codigo_mesa)
        result = store.get_mesa_sv_from_local(code)
        if result is None:
            return error_response(
                f"Mesa {code} no encontrada en cache local de segunda vuelta. "
                "Ejecuta onpe_sv_bootstrap() primero.",
                started_ms=started_ms,
                code="NOT_FOUND",
            )
        return ok_response(result, started_ms=started_ms, meta={"source": "local_db_sv"})
    except ValueError as exc:
        return error_response(str(exc), started_ms=started_ms, code="VALIDATION_ERROR")
    except Exception as exc:
        logger.exception("Error en onpe_sv_get_mesa")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_sv_resultados_geo(
    nivel: str = "nacional",
    ubigeo: str | None = None,
    nombre: str | None = None,
    top_n: int = 10,
) -> dict[str, Any]:
    """Consulta resultados de segunda vuelta 2026 por nivel geográfico.

    nivel: 'nacional' | 'departamento' | 'provincia' | 'distrito' | 'ciudad' | 'continente' | 'pais_exterior'
    ubigeo: código de ubigeo (ej: '150000' para Lima)
    nombre: nombre del departamento/provincia/ciudad/país (búsqueda parcial)
    top_n: cantidad de resultados a retornar (default 10)
    """
    started_ms = now_ms()
    try:
        nivel = str(nivel or "nacional").lower().strip()
        top_n = max(1, min(int(top_n), 50))
        rows = store.query_sv_geo(nivel=nivel, ubigeo=ubigeo, nombre=nombre, top_n=top_n)
        meta = {"nivel": nivel, "ubigeo": ubigeo, "nombre": nombre, "rows": len(rows)}
        return ok_response({"nivel": nivel, "resultados": rows}, started_ms=started_ms, meta=meta)
    except Exception as exc:
        logger.exception("Error en onpe_sv_resultados_geo")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_sv_cobertura() -> dict[str, Any]:
    """Retorna cobertura de actas contabilizadas por departamento en segunda vuelta 2026."""
    started_ms = now_ms()
    try:
        rows = store.get_sv_cobertura()
        total_depts = len(rows)
        return ok_response(
            {"total_departamentos": total_depts, "cobertura": rows},
            started_ms=started_ms,
        )
    except Exception as exc:
        logger.exception("Error en onpe_sv_cobertura")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_sv_reasignados(dpto: str | None = None, motivo: str | None = None) -> dict[str, Any]:
    """Consulta locales de votación reasignados para segunda vuelta 2026.

    Estos locales cambiaron por razones como reconstrucción, extorsión, etc.
    Filtros opcionales: dpto (nombre del departamento), motivo (texto del motivo).
    """
    started_ms = now_ms()
    try:
        rows = store.get_sv_reasignados(dpto=dpto, motivo=motivo)
        total_mesas = sum(int(r.get("mesas_afectadas", 0)) for r in rows)
        return ok_response(
            {
                "total_locales": len(rows),
                "total_mesas_afectadas": total_mesas,
                "locales": rows,
            },
            started_ms=started_ms,
        )
    except Exception as exc:
        logger.exception("Error en onpe_sv_reasignados")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_sv_estado_actas(
    ubigeo_prefix: str | None = None,
    top_geo: int = 10,
) -> dict[str, Any]:
    """Resumen de actas SV por estado (C/E/P) y escenario JEE-aceptadas.

    Útil para responder: "¿cuántas mesas están para envío al JEE?",
    "¿qué pasaría si el JEE acepta todas las observadas?", "¿dónde se concentran
    las mesas observadas?".

    Args:
        ubigeo_prefix: filtra por prefijo de ubigeo (2 dígitos = departamento,
            6 dígitos = distrito). None = nacional.
        top_geo: cantidad de departamentos a mostrar en `geo_top_jee` (solo
            cuando no se filtra por ubigeo). 0 desactiva el listado.

    Devuelve:
        - totales (mesas, contabilizadas_C, para_envio_jee_E, pendientes_P, ...)
        - por_estado (lista con descripción de cada código de estado)
        - votos_jee_pendientes (votos pre-contados en mesas E por partido)
        - escenario_jee_aceptadas: comparativa "actual" vs "si JEE acepta todas
          las E", con márgenes en votos y puntos porcentuales
        - geo_top_jee (top departamentos con mesas observadas)
        - fecha_actualizacion (timestamp ONPE oficial)
    """
    started_ms = now_ms()
    try:
        top_geo = max(0, min(int(top_geo or 0), 30))
        result = store.get_sv_estado_actas(
            ubigeo_prefix=ubigeo_prefix, top_geo=top_geo
        )
        store.append_raw_event("onpe_sv_estado_actas", {
            "ubigeo_prefix": ubigeo_prefix,
            "totales": result.get("totales"),
        })
        return ok_response(result, started_ms=started_ms)
    except Exception as exc:
        logger.exception("Error en onpe_sv_estado_actas")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_estado_actas(
    id_eleccion: int = 10,
    ubigeo_prefix: str | None = None,
    top_geo: int = 10,
) -> dict[str, Any]:
    """Resumen de actas por estado (C/E/P) — 1V o 2V.

    Tool genérica que delega en `onpe_sv_estado_actas` cuando id_eleccion
    apunta a segunda vuelta, y en `storage.get_estado_actas_1v` cuando es
    primera vuelta. Útil para refutar claims de "mesas sin contar" o
    "votos desaparecidos" con cifras oficiales.

    Args:
        id_eleccion: 10 = primera vuelta · 11 = segunda vuelta.
        ubigeo_prefix: filtra por prefijo (2 dígitos = departamento,
            6 dígitos = distrito). None = nacional.
        top_geo: top departamentos con mesas no-contabilizadas (0 desactiva).

    Devuelve estructura uniforme con:
        - totales: {mesas, contabilizadas_C, observadas_E/para_envio_jee_E,
                    pendientes_P, electores_habiles, votos_emitidos}
        - por_estado: lista con descripción y conteos por código
        - escrutinio_cerrado: True si 100% de actas están Contabilizadas
        - pct_contabilizadas: float 0-100
        - fecha_actualizacion: timestamp ONPE oficial
    """
    started_ms = now_ms()
    try:
        top_geo = max(0, min(int(top_geo or 0), 30))
        id_e = int(id_eleccion or 10)
        if id_e == 10:
            result = store.get_estado_actas_1v(
                ubigeo_prefix=ubigeo_prefix, top_geo=top_geo
            )
        elif id_e == 11:
            result = store.get_sv_estado_actas(
                ubigeo_prefix=ubigeo_prefix, top_geo=top_geo
            )
            # Anota id_eleccion en el resultado SV para coherencia
            result.setdefault("id_eleccion", 11)
        else:
            raise ValueError(
                f"id_eleccion={id_e} no soportado. Use 10 (1V) o 11 (2V)."
            )
        store.append_raw_event("onpe_estado_actas", {
            "id_eleccion": id_e,
            "ubigeo_prefix": ubigeo_prefix,
            "totales": result.get("totales"),
        })
        return ok_response(result, started_ms=started_ms)
    except ValueError as exc:
        return error_response(str(exc), started_ms=started_ms, code="INVALID_ARGUMENT")
    except Exception as exc:
        logger.exception("Error en onpe_estado_actas")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_margen_pase(
    partido: str,
    id_eleccion: int = 10,
    top_n: int = 8,
) -> dict[str, Any]:
    """Brecha del partido vs puestos vecinos en 1V (pase a 2da vuelta).

    Útil para refutar claims cuantitativos: "perdimos 1.2% / 100 mil
    votos". Devuelve el margen real con denominadores múltiples (% padrón,
    % emitidos, % válidos) y un `claim_helper` que muestra cuántos votos
    equivale cada porcentaje, para detectar inconsistencias matemáticas.

    Args:
        partido: partido_id (ej. "35") o nombre/alias (ej. "renovacion popular",
            "lopez aliaga", "keiko"). Matching accent-insensitive.
        id_eleccion: 10 (1V). El concepto de "pase" no aplica a SV.
        top_n: cuántos partidos mostrar en `ranking_top` (1-25).

    Devuelve:
        - candidato_objetivo: posición y % del partido consultado.
        - margen_vs_anterior: cuántos votos lo separan del puesto inmediato
          superior (`null` si está 1ro).
        - margen_vs_lider: cuántos votos lo separan del puesto 1.
        - ranking_top: ranking compacto con porcentajes.
        - claim_helper: cifra de votos equivalente para 0.5%, 1%, 1.2%, 2%, 5%.
    """
    started_ms = now_ms()
    try:
        result = store.get_margen_pase(
            partido=partido, id_eleccion=int(id_eleccion or 10), top_n=int(top_n or 8)
        )
        store.append_raw_event("onpe_margen_pase", {
            "partido": partido,
            "id_eleccion": id_eleccion,
            "posicion": result["candidato_objetivo"]["posicion"],
        })
        return ok_response(result, started_ms=started_ms)
    except ValueError as exc:
        return error_response(str(exc), started_ms=started_ms, code="INVALID_ARGUMENT")
    except Exception as exc:
        logger.exception("Error en onpe_margen_pase")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_claim_verifier(
    claim_text: str,
    id_eleccion: int = 10,
) -> dict[str, Any]:
    """Cruza un claim cuantitativo en español contra las cifras oficiales ONPE.

    Detecta cifras absolutas ("900 mil votos", "1 millón", "100,000") y
    porcentajes ("1.2%", "1,2 por ciento") y los compara con los
    denominadores reales (padrón, emitidos, válidos, blancos+nulos,
    actas no contabilizadas). Emite un veredicto por cada cifra detectada.

    Útil para refutar narrativas tipo:
        - "Faltan 900 mil votos sin contar"
        - "Más de un millón no pudo votar"
        - "Nos restaron 1.2% / 100 mil votos"
        - "Miles de actas irregulares"

    Args:
        claim_text: texto crudo del claim (ej. una declaración política).
        id_eleccion: 10 (1V, default). 11 (SV) solo es informativo en esta tool.

    Devuelve:
        - claim_text, tema_detectado, cifras_detectadas
        - referencia_oficial: padrón / emitidos / válidos / actas_no_C
        - veredictos: lista por cada cifra con
              {tipo, valor_claim, mejor_interpretacion, factor_inflacion,
               cifra_oficial_mas_cercana, conclusion}
        - margen_pase_2v: bloque del competidor más cercano (si aplica al tema).
    """
    started_ms = now_ms()
    try:
        id_e = int(id_eleccion or 10)
        # Hoy solo 1V: SV tiene su propia tool (sv_estado_actas) con C/E/P
        if id_e != 10:
            raise ValueError(
                "Por ahora claim_verifier solo opera sobre 1V (id_eleccion=10). "
                "Para SV use onpe_sv_estado_actas / onpe_sv_resultados."
            )

        text = (claim_text or "").strip()
        if not text:
            raise ValueError("claim_text no puede estar vacío")

        cifras = parse_quantitative_claims(text)
        tema = classify_claim_topic(text)

        totales = store.get_totales_nacionales_1v()
        estado = store.get_estado_actas_1v(top_geo=0)
        padron = totales["electores_habiles"]
        emitidos = totales["votos_emitidos"]
        validos = totales["votos_validos"]
        blancos = totales["votos_blancos"]
        nulos = totales["votos_nulos"]
        ausentes = totales["ausentismo_total"]

        actas_no_c = estado["totales"]["mesas"] - estado["totales"]["contabilizadas_C"]
        observadas = estado["totales"].get("observadas_E", 0)
        pendientes = estado["totales"].get("pendientes_P", 0)

        veredictos: list[dict[str, Any]] = []

        def _ratio_label(val: float) -> str:
            if val >= 50:
                return "claim invariablemente falso (>50× la cifra real)"
            if val >= 10:
                return "claim groseramente exagerado (>10×)"
            if val >= 3:
                return "claim significativamente inflado (3-10×)"
            if val >= 1.5:
                return "claim moderadamente inflado (1.5-3×)"
            if val >= 0.95:
                return "claim consistente con cifra oficial (±5%)"
            return "claim subestima la cifra oficial"

        # ----- Veredicto de cifras ABSOLUTAS -----
        for c in cifras["absolutos"]:
            v = int(c["valor"])
            unidad = c.get("unidad")
            ranking = []  # candidatos con su distancia

            # Comparar contra denominadores relevantes según tema y unidad
            if tema == "votos_faltantes":
                # Compara contra mesas/votos NO contabilizados
                if unidad == "actas" or unidad == "mesas":
                    real = actas_no_c
                    label = "actas no contabilizadas en 1V"
                else:
                    real = 0  # en 1V no quedan votos pendientes
                    label = "votos pendientes de contar en 1V"
                ratio = (v / real) if real else float("inf") if v > 0 else 1.0
                ranking.append({
                    "concepto": label,
                    "valor_oficial": real,
                    "factor_inflacion": round(ratio, 3) if real else None,
                    "veredicto": _ratio_label(ratio) if real else (
                        "CLAIM IMPOSIBLE: cifra oficial es 0 (escrutinio cerrado)"
                    ),
                })
            elif tema == "impedidos_votar":
                # Compara contra ausentismo y contra "0 mesas no instaladas"
                ratio_ausentes = (v / ausentes) if ausentes else float("inf")
                ranking.append({
                    "concepto": "ausentismo total (voluntario, NO impedimento)",
                    "valor_oficial": ausentes,
                    "factor_inflacion": round(ratio_ausentes, 3),
                    "veredicto": (
                        "incluso comparado contra TODO el ausentismo voluntario, "
                        + _ratio_label(ratio_ausentes)
                    ),
                })
                mesas_no_inst = pendientes  # P en 1V ≈ mesas no instaladas
                ranking.append({
                    "concepto": "electores en mesas NO instaladas (1V)",
                    "valor_oficial": int(mesas_no_inst * 300),
                    "factor_inflacion": None,
                    "veredicto": (
                        f"Mesas no instaladas: {mesas_no_inst}. "
                        "Si reclama impedimento, debe identificar mesas específicas."
                    ),
                })
            elif tema in {"margen_perdido", "actas_irregulares"}:
                ranking.append({
                    "concepto": "votos no contabilizados (1V)",
                    "valor_oficial": 0,
                    "factor_inflacion": None,
                    "veredicto": (
                        "En 1V el 100% de actas están Contabilizadas — no existen "
                        "votos 'desaparecidos' del sistema oficial."
                    ),
                })

            # Comparaciones "interpretaciones generosas"
            interpretaciones: list[dict[str, Any]] = []
            for label, real in (
                ("votos en blanco (1V)", blancos),
                ("votos nulos (1V)", nulos),
                ("blancos+nulos", blancos + nulos),
                ("ausentismo total", ausentes),
            ):
                if not real:
                    continue
                ratio = (v / real)
                interpretaciones.append({
                    "concepto": label,
                    "valor_oficial": real,
                    "ratio_claim_vs_real": round(ratio, 3),
                })
            interpretaciones.sort(
                key=lambda x: abs(1 - x["ratio_claim_vs_real"])
            )

            veredictos.append({
                "tipo": "cifra_absoluta",
                "valor_claim": v,
                "valor_claim_raw": c["raw"],
                "unidad": unidad,
                "veredicto_principal": ranking[0] if ranking else None,
                "veredictos_alternativos": ranking[1:],
                "interpretaciones_alternativas": interpretaciones[:3],
            })

        # ----- Veredicto de PORCENTAJES -----
        for p in cifras["porcentajes"]:
            pct = float(p["valor"])
            equivalencias = {
                "pct_padron_=>_votos": int(round(pct / 100 * padron)),
                "pct_emitidos_=>_votos": int(round(pct / 100 * emitidos)),
                "pct_validos_=>_votos": int(round(pct / 100 * validos)),
            }
            # Si en el mismo claim hay también un valor absoluto, valida consistencia
            inconsistencia = None
            if cifras["absolutos"]:
                claimed_abs = max(c["valor"] for c in cifras["absolutos"])
                base_validos = equivalencias["pct_validos_=>_votos"]
                base_padron = equivalencias["pct_padron_=>_votos"]
                if base_validos and base_padron:
                    # ¿cuál denominador haría el claim coherente?
                    ratios = {
                        "padron": claimed_abs / base_padron if base_padron else None,
                        "emitidos": claimed_abs / equivalencias["pct_emitidos_=>_votos"]
                            if equivalencias["pct_emitidos_=>_votos"] else None,
                        "validos": claimed_abs / base_validos if base_validos else None,
                    }
                    # Si NINGÚN denominador hace coincidir (todos lejos de 1.0),
                    # entonces el claim es internamente inconsistente.
                    if all(
                        (r is None) or abs(1 - r) > 0.20 for r in ratios.values()
                    ):
                        inconsistencia = {
                            "claim_porcentaje": pct,
                            "claim_votos_absolutos": claimed_abs,
                            "votos_que_correspondrian": equivalencias,
                            "veredicto": (
                                "INCONSISTENCIA INTERNA: los dos números del claim "
                                "no pueden ser ciertos simultáneamente bajo ningún "
                                "denominador oficial (padrón / emitidos / válidos)."
                            ),
                        }
            veredictos.append({
                "tipo": "porcentaje",
                "valor_claim_pct": pct,
                "valor_claim_raw": p["raw"],
                "equivalencias_en_votos": equivalencias,
                "inconsistencia_con_absoluto": inconsistencia,
            })

        # ----- Bloque margen-pase si el tema lo amerita -----
        margen_pase = None
        try:
            # Heurística: si el claim menciona partido/candidato 2026 y tema=margen_perdido,
            # devolvemos el bloque para Renovación Popular como caso más común.
            q_norm_full = (text or "").lower()
            partido_aliases = {
                "lopez aliaga": "renovacion popular",
                "rafael lopez": "renovacion popular",
                "renovacion popular": "renovacion popular",
                "renovacion": "renovacion popular",
                "keiko": "fuerza popular",
                "fujimori": "fuerza popular",
                "fuerza popular": "fuerza popular",
                "sanchez": "juntos por el peru",
                "juntos por el peru": "juntos por el peru",
                "nieto": "partido del buen gobierno",
                "belmont": "partido civico obras",
            }
            target = None
            for alias, real in partido_aliases.items():
                if alias in q_norm_full:
                    target = real
                    break
            if target and tema in {"margen_perdido", "general", "actas_irregulares"}:
                margen_pase = store.get_margen_pase(partido=target, id_eleccion=10, top_n=5)
        except Exception:  # noqa: BLE001 — bloque opcional
            margen_pase = None

        # ----- Conclusión textual lista para chat -----
        bullets: list[str] = []
        bullets.append(
            f"📊 Cifras oficiales 1V: padrón {padron:,} · emitidos {emitidos:,} · "
            f"válidos {validos:,} · blancos {blancos:,} · nulos {nulos:,}."
        )
        bullets.append(
            f"🗳️ Cobertura de actas: {estado['pct_contabilizadas']}% "
            f"(contabilizadas {estado['totales']['contabilizadas_C']:,} / "
            f"{estado['totales']['mesas']:,}). "
            + ("Escrutinio CERRADO." if estado["escrutinio_cerrado"] else "")
        )
        for v in veredictos:
            if v["tipo"] == "cifra_absoluta" and v.get("veredicto_principal"):
                p = v["veredicto_principal"]
                bullets.append(
                    f"❌ '{v['valor_claim_raw']}' → "
                    f"oficial '{p['concepto']}' = {p['valor_oficial']:,}. "
                    f"{p['veredicto']}"
                )
            elif v["tipo"] == "porcentaje":
                if v.get("inconsistencia_con_absoluto"):
                    bullets.append(
                        f"⚠️ {v['inconsistencia_con_absoluto']['veredicto']}"
                    )

        result = {
            "claim_text": text,
            "tema_detectado": tema,
            "cifras_detectadas": cifras,
            "referencia_oficial": {
                "padron_habil": padron,
                "votos_emitidos": emitidos,
                "votos_validos": validos,
                "votos_blancos": blancos,
                "votos_nulos": nulos,
                "ausentismo_total": ausentes,
                "actas_no_contabilizadas": actas_no_c,
                "mesas_observadas_E": observadas,
                "mesas_pendientes_P": pendientes,
                "pct_contabilizadas": estado["pct_contabilizadas"],
            },
            "veredictos": veredictos,
            "margen_pase_2v": margen_pase,
            "answer": "\n".join(bullets),
            "fecha_actualizacion": totales["fecha_actualizacion"],
        }
        store.append_raw_event("onpe_claim_verifier", {
            "claim_text": text[:200],
            "tema_detectado": tema,
            "n_cifras": len(cifras["absolutos"]) + len(cifras["porcentajes"]),
        })
        return ok_response(result, started_ms=started_ms)
    except ValueError as exc:
        return error_response(str(exc), started_ms=started_ms, code="INVALID_ARGUMENT")
    except Exception as exc:
        logger.exception("Error en onpe_claim_verifier")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_sv_comparacion_mesa(codigo_mesa: str) -> dict[str, Any]:
    """Compara los resultados de primera vuelta vs segunda vuelta para la misma mesa.

    Muestra electores habiles, votos emitidos, votos validos y resultados por partido en ambas vueltas.
    """
    started_ms = now_ms()
    try:
        code = validate_mesa_code(codigo_mesa)
        result = store.get_comparacion_mesa(code)
        if result["primera_vuelta"] is None and result["segunda_vuelta"] is None:
            return error_response(
                f"Mesa {code} no encontrada ni en primera ni en segunda vuelta.",
                started_ms=started_ms,
                code="NOT_FOUND",
            )
        return ok_response(result, started_ms=started_ms)
    except ValueError as exc:
        return error_response(str(exc), started_ms=started_ms, code="VALIDATION_ERROR")
    except Exception as exc:
        logger.exception("Error en onpe_sv_comparacion_mesa")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_sv_comparacion_geo(ubigeo_prefix: str) -> dict[str, Any]:
    """Compara resultados primera vuelta vs segunda vuelta por prefijo de ubigeo.

    Útil para comparar resultados al nivel de departamento (6 dígitos, ej: '150000'),
    provincia (4 dígitos + '00', ej: '1501'), etc.
    """
    started_ms = now_ms()
    try:
        prefix = str(ubigeo_prefix or "").strip()
        if not prefix:
            raise ValueError("ubigeo_prefix no puede estar vacío")
        result = store.get_comparacion_geo(prefix)
        return ok_response(result, started_ms=started_ms)
    except ValueError as exc:
        return error_response(str(exc), started_ms=started_ms, code="VALIDATION_ERROR")
    except Exception as exc:
        logger.exception("Error en onpe_sv_comparacion_geo")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_sv_proyeccion_transferencia(
    ubigeo_prefix: str | None = None,
    mesa_prefix: str | None = None,
) -> dict[str, Any]:
    """Proyección de transferencia de votos de primera a segunda vuelta.

    Usa el modelo NNLS calibrado (86,124 mesas) para estimar cómo los votos
    de primera vuelta se distribuirían entre Keiko Fujimori y Roberto Sánchez.

    Modos de filtrado (mutuamente exclusivos):
      - ubigeo_prefix: filtra por ubigeo (ej: '150000' Lima).
      - mesa_prefix:  filtra por prefijo del código de mesa (ej: '9', '900', '9001').
                       Acepta shorthand '900K' / '9K' que se interpreta como
                       el bloque cuyo primer dígito es 9 (mesas 900000-999999).
                       Devuelve además observación 2V real y error del modelo.
      - Sin ningún parámetro: proyección nacional agregada.

    Nota: ~9% de abstención entre vueltas está incorporado en los pesos.
    """
    started_ms = now_ms()
    try:
        if ubigeo_prefix and mesa_prefix:
            raise ValueError("Pasa solo uno de ubigeo_prefix o mesa_prefix, no ambos")

        # Modo mesa_prefix: cálculo on-demand desde votos crudos
        if mesa_prefix:
            raw = str(mesa_prefix).strip()
            if not raw:
                raise ValueError("mesa_prefix no puede estar vacío")
            # Normalización shorthand: 'NNNK' / 'NK' → primer dígito (bloque).
            # Ej: '900K' → '9' (bloque 900000-999999). '700K' → '7'.
            _k_match = re.fullmatch(r"(\d{1,4})\s*[kK]", raw)
            if _k_match:
                normalized = _k_match.group(1)[0]
            else:
                normalized = raw
            if not normalized.isdigit():
                raise ValueError(
                    f"mesa_prefix debe ser numérico tras normalizar (recibido {raw!r} → {normalized!r}). "
                    "Ejemplos válidos: '9', '900', '9001', '900000', '900K'."
                )
            result = store.get_proyeccion_sv_by_mesa_prefix(normalized)
            pred = result["proyeccion_nnls_nacional"]
            obs = result["segunda_vuelta_observada"]
            err = result["error_modelo"]
            pool = result["primera_vuelta"]["pool_total_1v"]
            answer_lines = [
                f"**Proyección 1V→2V para mesas con prefijo '{normalized}'** ({result['primera_vuelta']['mesas']:,} mesas, {result['primera_vuelta']['electores_habiles']:,} electores):",
                "",
                f"- Pool 1V total: {pool:,} votos",
                f"- Predicción NNLS nacional: Keiko {pred['keiko']:,} | Sánchez {pred['sanchez']:,}",
                f"- Observado 2V:             Keiko {obs['keiko']:,} | Sánchez {obs['sanchez']:,}",
                (
                    f"- Error modelo: Keiko {err['keiko_abs']:+,} ({err['keiko_pct']}%), "
                    f"Sánchez {err['sanchez_abs']:+,} ({err['sanchez_pct']}%)"
                ),
            ]
            return ok_response(
                {
                    "mesa_prefix": normalized,
                    "raw_input": raw,
                    "proyeccion": result,
                    "answer": "\n".join(answer_lines),
                },
                started_ms=started_ms,
            )

        with store._connect() as _pconn:
            _pcount = _pconn.execute("SELECT COUNT(*) AS c FROM proyeccion_sv_by_ubigeo").fetchone()["c"]
        if _pcount == 0:
            store.rebuild_proyeccion_sv()

        rows = store.get_proyeccion_sv(ubigeo_prefix=ubigeo_prefix)
        if not rows:
            return ok_response(
                {
                    "ubigeo_prefix": ubigeo_prefix,
                    "proyeccion": [],
                    "message": "No hay datos de proyección. Ejecuta onpe_sv_bootstrap() y asegúrate de tener datos de primera vuelta.",
                },
                started_ms=started_ms,
            )

        if not ubigeo_prefix:
            row = rows[0]
            total = int(row.get("votos_1v_total") or 0)
            pk = int(row.get("votos_proyectados_keiko") or 0)
            ps = int(row.get("votos_proyectados_sanchez") or 0)
            answer = (
                f"Proyección nacional de transferencia de votos (modelo NNLS, 86K mesas):\n"
                f"- Keiko Fujimori: {pk:,} votos proyectados ({pk/total*100:.1f}% del total 1V)\n"
                f"- Roberto Sánchez: {ps:,} votos proyectados ({ps/total*100:.1f}%)\n"
                f"- Blancos/nulos/abstención: {total-pk-ps:,} estimados"
            ) if total > 0 else "Sin datos de primera vuelta para proyectar."
        else:
            answer = f"Proyección de transferencia para ubigeo_prefix='{ubigeo_prefix}': {len(rows)} ubigeos."

        return ok_response(
            {"ubigeo_prefix": ubigeo_prefix, "proyeccion": rows, "answer": answer},
            started_ms=started_ms,
        )
    except ValueError as exc:
        return error_response(str(exc), started_ms=started_ms, code="VALIDATION_ERROR")
    except Exception as exc:
        logger.exception("Error en onpe_sv_proyeccion_transferencia")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_sv_resultados() -> dict[str, Any]:
    """Conteo actual de la SEGUNDA VUELTA 2026 desde el cache local hidratado.

    Cache-first: usa siempre los datos hidratados en SQLite (tablas sv_resumen_nacional,
    mesas_sv, votos_sv) — no consulta ONPE en vivo. Esto garantiza respuestas
    consistentes y reproducibles.

    Retorna tres bloques:
      - oficial: cifras certificadas por ONPE (solo actas Contabilizadas).
      - desglose_por_estado: votos por código_estado_acta (C=Contabilizada,
        E=En proceso, P=Pendiente).
      - proyectado_con_crudo: total agregado C+E (incluye votos escaneados de actas
        E aún no certificadas oficialmente).
    """
    started_ms = now_ms()
    try:
        result = store.get_sv_conteo_actual()
        oficial = result.get("oficial", {})
        proy = result.get("proyectado_con_crudo", {})
        candidatos = oficial.get("candidatos", [])

        # Construir answer legible
        lines = ["**Resultado SEGUNDA VUELTA 2026 — cache hidratado**", ""]
        if oficial.get("pct_contabilizadas") is not None:
            lines.append(
                f"📊 Cobertura oficial ONPE: {oficial['actas_contabilizadas']:,} / "
                f"{oficial['total_actas']:,} actas ({oficial['pct_contabilizadas']:.4f}%)"
            )
            lines.append(f"🗳️ Participación: {oficial.get('participacion', 0):.2f}%")
            lines.append(f"🕐 Último refresh ONPE: {oficial.get('fecha_actualizacion')}")
            lines.append("")
        lines.append("**Cifras OFICIALES (certificadas):**")
        for c in candidatos:
            lines.append(
                f"  • {c['nombre']}: {c['votos_validos']:,} votos "
                f"({c['pct_votos_validos']:.4f}%)"
            )
        if proy:
            lines.append("")
            lines.append("**Proyectado con crudo capturado (C + E):**")
            lines.append(
                f"  • Keiko: {proy['keiko']:,} ({proy['pct_keiko']:.4f}%)"
            )
            lines.append(
                f"  • Sánchez: {proy['sanchez']:,} ({proy['pct_sanchez']:.4f}%)"
            )
            lines.append(
                f"  • Margen Keiko–Sánchez: {proy['margen_keiko_sanchez']:+,d} votos"
            )
        if result.get("cache_hidratado_al"):
            lines.append("")
            lines.append(f"_cache_hidratado_al: {result['cache_hidratado_al']}_")

        return ok_response(
            {**result, "answer": "\n".join(lines)},
            started_ms=started_ms,
            meta={"source": "sqlite_sv_cache"},
        )
    except Exception as exc:
        logger.exception("Error en onpe_sv_resultados")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_2021_bootstrap(force: bool = False) -> dict[str, Any]:
    """Hidrata las elecciones presidenciales 2021 (1V y 2V) desde peruvoto2021."""
    started_ms = now_ms()
    try:
        result = store.bootstrap_elecciones_2021(settings.voto2021_root, force=bool(force))
        return ok_response(result, started_ms=started_ms, meta={"source": "peruvoto2021_csv"})
    except Exception as exc:
        logger.exception("Error en onpe_2021_bootstrap")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_2021_export_mesas(
    vuelta: int,
    departamento: str | None = None,
    provincia: str | None = None,
    distrito: str | None = None,
    ubigeo_prefix: str | None = None,
    mesa_prefix: str | None = None,
    limit: int = 1000,
    offset: int = 0,
) -> dict[str, Any]:
    """Raw data 2021 — cabecera por mesa (geo + electores/emitidos/válidos/blancos/nulos).

    Diseñado para que cualquier consumidor pueda hacer análisis estadístico
    arbitrario (Pandas/R/Power BI/etc.) sin depender de agregaciones pre-computadas.

    Args:
        vuelta: 1 (primera vuelta) o 2 (segunda vuelta).
        departamento / provincia / distrito: filtros exactos (case-insensitive).
        ubigeo_prefix: filtra por prefijo de ubigeo (ej. "15" = Lima).
        mesa_prefix:  filtra por prefijo de código de mesa (ej. "9" = rural 9XXXXX).
        limit: máximo de filas (default 1000, máx 100,000).
        offset: paginación. has_more=True indica que faltan más.

    Returns:
        {ok, data: {vuelta, total, offset, limit, returned, has_more, schema, rows[]}, ...}
        Cada fila contiene: vuelta, codigo_mesa, ubigeo, departamento, provincia,
        distrito, estado_acta, tipo_observacion, electores_habiles, votos_emitidos,
        votos_validos, blancos, nulos, impugnados.
    """
    started_ms = now_ms()
    try:
        if int(vuelta) not in (1, 2):
            raise ValueError("vuelta debe ser 1 o 2")
        result = store.export_mesas_2021(
            vuelta=int(vuelta),
            departamento=departamento,
            provincia=provincia,
            distrito=distrito,
            ubigeo_prefix=ubigeo_prefix,
            mesa_prefix=mesa_prefix,
            limit=int(limit),
            offset=int(offset),
        )
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2021"})
    except Exception as exc:
        logger.exception("Error en onpe_2021_export_mesas")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_2021_export_votos(
    vuelta: int,
    partido_ids: list[str] | None = None,
    departamento: str | None = None,
    provincia: str | None = None,
    distrito: str | None = None,
    ubigeo_prefix: str | None = None,
    mesa_prefix: str | None = None,
    limit: int = 5000,
    offset: int = 0,
) -> dict[str, Any]:
    """Raw data 2021 — una fila por (mesa × partido) con votos + geo enriquecido.

    Args:
        vuelta: 1 o 2.
        partido_ids: lista opcional de partido_id (ej ["PC","K","RL"]). None = todos.
        Otros filtros igual que `onpe_2021_export_mesas`.
        limit: default 5000, máx 100,000. Útil para análisis por chunks.

    Returns:
        {ok, data: {vuelta, total, offset, limit, returned, has_more, schema, rows[]}}
        Cada fila contiene: vuelta, codigo_mesa, partido_id, nombre_partido, candidato,
        votos, ubigeo, departamento, provincia, distrito, mesa_votos_validos.

    Tip: combina con `onpe_2021_summary` (denominadores) y `onpe_2021_export_partidos`
    (catálogo) para tener todo lo necesario y calcular HHI, NNLS, correlaciones,
    bootstrap del margen, etc. sin depender del MCP para la analítica.
    """
    started_ms = now_ms()
    try:
        if int(vuelta) not in (1, 2):
            raise ValueError("vuelta debe ser 1 o 2")
        result = store.export_votos_2021(
            vuelta=int(vuelta),
            partido_ids=partido_ids,
            departamento=departamento,
            provincia=provincia,
            distrito=distrito,
            ubigeo_prefix=ubigeo_prefix,
            mesa_prefix=mesa_prefix,
            limit=int(limit),
            offset=int(offset),
        )
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2021"})
    except Exception as exc:
        logger.exception("Error en onpe_2021_export_votos")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_2021_export_partidos(vuelta: int | None = None) -> dict[str, Any]:
    """Catálogo de partidos y candidatos 2021 (1V y/o 2V).

    Args:
        vuelta: 1 o 2 (filtra). None = devuelve ambos.

    Returns:
        {ok, data: {vuelta, total, schema, rows[]}}
        Cada fila: vuelta, partido_id, nombre_partido, candidato.
    """
    started_ms = now_ms()
    try:
        if vuelta is not None and int(vuelta) not in (1, 2):
            raise ValueError("vuelta debe ser 1, 2 o None")
        result = store.export_partidos_2021(vuelta=vuelta if vuelta is None else int(vuelta))
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2021"})
    except Exception as exc:
        logger.exception("Error en onpe_2021_export_partidos")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_2021_summary(vuelta: int) -> dict[str, Any]:
    """Resumen agregado nacional 2021 (totales + por partido) — usar como denominadores.

    Args:
        vuelta: 1 o 2.

    Returns:
        {ok, data: {vuelta, mesas, electores_habiles, votos_emitidos, votos_validos,
                    votos_blancos, votos_nulos, votos_impugnados,
                    participacion_pct, validez_pct, por_partido[]}}
        Cada item en por_partido: {partido_id, nombre_partido, candidato,
                                   total_votos, pct_validos}.
    """
    started_ms = now_ms()
    try:
        if int(vuelta) not in (1, 2):
            raise ValueError("vuelta debe ser 1 o 2")
        result = store.summary_2021(vuelta=int(vuelta))
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2021"})
    except Exception as exc:
        logger.exception("Error en onpe_2021_summary")
        return error_response(str(exc), started_ms=started_ms)


# ════════════════════════════════════════════════════════════════════════════
# RAW DATA & ANALYTICS — 2026 1V y 2V
#
# Mismo patrón que los `onpe_2021_*`. Soportan filtros geo/mesa_prefix/estado +
# paginación + schema explícito. Diseñados para que un asistente externo pueda
# consumir datos crudos y construir análisis arbitrarios (HHI, NNLS, bootstrap,
# correlaciones, etc.) sin depender de agregaciones pre-computadas.
# ════════════════════════════════════════════════════════════════════════════

# ── 2026 1V — Raw data ──────────────────────────────────────────────────────

@mcp.tool()
def onpe_export_mesas(
    departamento: str | None = None,
    provincia: str | None = None,
    distrito: str | None = None,
    ubigeo_prefix: str | None = None,
    mesa_prefix: str | None = None,
    estado_acta: str | None = None,
    limit: int = 1000,
    offset: int = 0,
) -> dict[str, Any]:
    """Raw data 2026 1V — cabecera por mesa (geo + electores/emitidos/válidos/blancos/nulos).

    Filtros: departamento / provincia / distrito (case-insensitive),
    ubigeo_prefix (ej "15" = Lima), mesa_prefix (ej "9" = bloque 9XXXXX),
    estado_acta (Contabilizada / Observada / Pendiente / etc).

    Paginación: limit (default 1000, máx 100,000) + offset. has_more = true → quedan más.
    """
    started_ms = now_ms()
    try:
        result = store.export_mesas_2026_1v(
            departamento=departamento, provincia=provincia, distrito=distrito,
            ubigeo_prefix=ubigeo_prefix, mesa_prefix=mesa_prefix,
            estado_acta=estado_acta, limit=int(limit), offset=int(offset),
        )
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2026_1v"})
    except Exception as exc:
        logger.exception("Error en onpe_export_mesas")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_export_votos(
    partido_ids: list[str] | None = None,
    departamento: str | None = None,
    provincia: str | None = None,
    distrito: str | None = None,
    ubigeo_prefix: str | None = None,
    mesa_prefix: str | None = None,
    estado_acta: str | None = None,
    limit: int = 5000,
    offset: int = 0,
) -> dict[str, Any]:
    """Raw data 2026 1V — una fila por (mesa × partido) con geo y partido enriquecidos.

    Args:
        partido_ids: lista opcional de partido_id (ej ["10","8"]). None = todos.
        Demás filtros iguales que onpe_export_mesas.
    """
    started_ms = now_ms()
    try:
        result = store.export_votos_2026_1v(
            partido_ids=partido_ids,
            departamento=departamento, provincia=provincia, distrito=distrito,
            ubigeo_prefix=ubigeo_prefix, mesa_prefix=mesa_prefix,
            estado_acta=estado_acta, limit=int(limit), offset=int(offset),
        )
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2026_1v"})
    except Exception as exc:
        logger.exception("Error en onpe_export_votos")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_export_partidos() -> dict[str, Any]:
    """Catálogo de partidos 2026 1V. Cada fila incluye is_candidate=false
    para 80 (blanco), 81 (nulo), 82 (impugnado)."""
    started_ms = now_ms()
    try:
        result = store.export_partidos_2026_1v()
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2026_1v"})
    except Exception as exc:
        logger.exception("Error en onpe_export_partidos")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_summary() -> dict[str, Any]:
    """Resumen agregado nacional 2026 1V (totales + por partido)."""
    started_ms = now_ms()
    try:
        result = store.summary_2026_1v()
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2026_1v"})
    except Exception as exc:
        logger.exception("Error en onpe_summary")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_resultados_geo(
    nivel: str = "departamento",
    filtro: str | None = None,
    top_n: int = 5,
) -> dict[str, Any]:
    """Top N candidatos 1V por nivel geográfico (nacional/departamento/provincia/distrito).

    Análogo a `onpe_sv_resultados_geo` pero para la 1ra vuelta 2026.
    Ej: nivel='departamento', filtro='LIMA', top_n=5.
    """
    started_ms = now_ms()
    try:
        result = store.resultados_geo_2026_1v(
            nivel=nivel, filtro=filtro, top_n=int(top_n),
        )
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2026_1v"})
    except Exception as exc:
        logger.exception("Error en onpe_resultados_geo")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_cobertura() -> dict[str, Any]:
    """Cobertura 2026 1V por departamento: % de actas Contabilizadas. Análogo a `onpe_sv_cobertura`."""
    started_ms = now_ms()
    try:
        result = store.cobertura_2026_1v()
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2026_1v"})
    except Exception as exc:
        logger.exception("Error en onpe_cobertura")
        return error_response(str(exc), started_ms=started_ms)


# ── 2026 2V — Raw data ──────────────────────────────────────────────────────

@mcp.tool()
def onpe_sv_export_mesas(
    departamento: str | None = None,
    provincia: str | None = None,
    distrito: str | None = None,
    ubigeo_prefix: str | None = None,
    mesa_prefix: str | None = None,
    codigo_estado_acta: str | None = None,
    limit: int = 1000,
    offset: int = 0,
) -> dict[str, Any]:
    """Raw data 2026 2V — cabecera por mesa (geo + electores + emit + válidos + estado).

    Filtros: departamento / provincia / distrito / ubigeo_prefix / mesa_prefix
    y codigo_estado_acta (C=Contabilizada, E=En proceso, P=Pendiente, etc).
    """
    started_ms = now_ms()
    try:
        result = store.export_mesas_2026_sv(
            departamento=departamento, provincia=provincia, distrito=distrito,
            ubigeo_prefix=ubigeo_prefix, mesa_prefix=mesa_prefix,
            codigo_estado_acta=codigo_estado_acta,
            limit=int(limit), offset=int(offset),
        )
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2026_sv"})
    except Exception as exc:
        logger.exception("Error en onpe_sv_export_mesas")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_sv_export_votos(
    partido_ids: list[str] | None = None,
    departamento: str | None = None,
    provincia: str | None = None,
    distrito: str | None = None,
    ubigeo_prefix: str | None = None,
    mesa_prefix: str | None = None,
    codigo_estado_acta: str | None = None,
    limit: int = 5000,
    offset: int = 0,
) -> dict[str, Any]:
    """Raw data 2026 2V — una fila por (mesa × partido) con geo y partido enriquecidos."""
    started_ms = now_ms()
    try:
        result = store.export_votos_2026_sv(
            partido_ids=partido_ids,
            departamento=departamento, provincia=provincia, distrito=distrito,
            ubigeo_prefix=ubigeo_prefix, mesa_prefix=mesa_prefix,
            codigo_estado_acta=codigo_estado_acta,
            limit=int(limit), offset=int(offset),
        )
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2026_sv"})
    except Exception as exc:
        logger.exception("Error en onpe_sv_export_votos")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_sv_export_partidos() -> dict[str, Any]:
    """Catálogo de partidos 2026 2V (binario PC vs FP + blanco/nulo/impugnado)."""
    started_ms = now_ms()
    try:
        result = store.export_partidos_2026_sv()
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2026_sv"})
    except Exception as exc:
        logger.exception("Error en onpe_sv_export_partidos")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_sv_summary() -> dict[str, Any]:
    """Resumen agregado nacional 2V 2026 (cifras OFICIALES de actas Contabilizadas)."""
    started_ms = now_ms()
    try:
        result = store.summary_2026_sv()
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2026_sv"})
    except Exception as exc:
        logger.exception("Error en onpe_sv_summary")
        return error_response(str(exc), started_ms=started_ms)


# ── Catálogos / Listados ────────────────────────────────────────────────────

@mcp.tool()
def onpe_list_departamentos() -> dict[str, Any]:
    """Lista los 25 departamentos peruanos disponibles + #provincias y #distritos."""
    started_ms = now_ms()
    try:
        result = store.list_departamentos()
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_geo"})
    except Exception as exc:
        logger.exception("Error en onpe_list_departamentos")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_list_partidos(vuelta: int = 1) -> dict[str, Any]:
    """Lista todos los partidos para una vuelta 2026 (1 = 38 partidos, 2 = 2 partidos)."""
    started_ms = now_ms()
    try:
        if int(vuelta) not in (1, 2):
            raise ValueError("vuelta debe ser 1 o 2")
        result = store.list_partidos(vuelta=int(vuelta))
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2026"})
    except Exception as exc:
        logger.exception("Error en onpe_list_partidos")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_list_foreign_geo() -> dict[str, Any]:
    """Lista continentes/países/ciudades con voto extranjero (foreign_catalog)."""
    started_ms = now_ms()
    try:
        result = store.list_foreign_geo()
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_geo"})
    except Exception as exc:
        logger.exception("Error en onpe_list_foreign_geo")
        return error_response(str(exc), started_ms=started_ms)


# ── Analítica genérica ───────────────────────────────────────────────────────

@mcp.tool()
def onpe_top_candidato_geo(
    vuelta: int,
    partido_id: str | None = None,
    candidato_query: str | None = None,
    nivel: str = "distrito",
    top_n: int = 10,
) -> dict[str, Any]:
    """Top N geos (distrito/provincia/departamento) donde un candidato es más fuerte.

    Args:
        vuelta: 1 (2026 1V) o 2 (2026 2V).
        partido_id: ID del partido (ej "10" para JxP en 2026). OR
        candidato_query: substring del nombre del partido/candidato.
        nivel: 'distrito' (default), 'provincia' o 'departamento'.
        top_n: máximo 100.
    """
    started_ms = now_ms()
    try:
        if int(vuelta) not in (1, 2):
            raise ValueError("vuelta debe ser 1 o 2")
        result = store.top_candidato_geo(
            vuelta=int(vuelta), partido_id=partido_id,
            candidato_query=candidato_query, nivel=nivel, top_n=int(top_n),
        )
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2026"})
    except Exception as exc:
        logger.exception("Error en onpe_top_candidato_geo")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_stats_participacion(
    vuelta: int,
    departamento: str | None = None,
) -> dict[str, Any]:
    """Distribución estadística de la participación (votos_emitidos/electores) por mesa.

    Devuelve media, σ, mediana, p10/p25/p75/p90, min/max. Útil para detectar
    departamentos con baja participación o outliers.
    """
    started_ms = now_ms()
    try:
        if int(vuelta) not in (1, 2):
            raise ValueError("vuelta debe ser 1 o 2")
        result = store.stats_participacion(
            vuelta=int(vuelta), departamento=departamento,
        )
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2026"})
    except Exception as exc:
        logger.exception("Error en onpe_stats_participacion")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_audit_votos_consistency(vuelta: int, limit: int = 100) -> dict[str, Any]:
    """Audita mesas donde Σ votos partido ≠ votos_validos (errores de captura/integridad)."""
    started_ms = now_ms()
    try:
        if int(vuelta) not in (1, 2):
            raise ValueError("vuelta debe ser 1 o 2")
        result = store.audit_votos_consistency(
            vuelta=int(vuelta), limit=int(limit),
        )
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2026"})
    except Exception as exc:
        logger.exception("Error en onpe_audit_votos_consistency")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_audit_coverage(vuelta: int) -> dict[str, Any]:
    """Matriz de cobertura por departamento: mesas sin votos hidratados ('huecos')."""
    started_ms = now_ms()
    try:
        if int(vuelta) not in (1, 2):
            raise ValueError("vuelta debe ser 1 o 2")
        result = store.audit_coverage(vuelta=int(vuelta))
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2026"})
    except Exception as exc:
        logger.exception("Error en onpe_audit_coverage")
        return error_response(str(exc), started_ms=started_ms)


# ════════════════════════════════════════════════════════════════════════════
# GEO LOOKUP + LISTAR MESAS/LOCALES + COMPARACIONES CROSS-YEAR
# ════════════════════════════════════════════════════════════════════════════

@mcp.tool()
def onpe_lookup_ubigeo(geo_name: str) -> dict[str, Any]:
    """Busca el código UBIGEO de un nombre geográfico (dpto/provincia/distrito).

    Match exacto primero, luego fuzzy (substring). Devuelve hasta 50 matches
    con el nivel detectado. Soporta alias (ej "iquitos" → provincia Maynas).

    Args:
        geo_name: nombre del dpto / provincia / distrito (case + accent insensitive).
    """
    started_ms = now_ms()
    try:
        result = store.lookup_ubigeo(str(geo_name or ""))
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_geo"})
    except Exception as exc:
        logger.exception("Error en onpe_lookup_ubigeo")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_listar_mesas_por_geo(
    anio: int = 2026,
    vuelta: int = 1,
    departamento: str | None = None,
    provincia: str | None = None,
    distrito: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    """Lista mesas (cabecera ligera) en una geo (dpto/prov/distrito).

    Args:
        año: 2021 o 2026 (años hidratados en cache).
        vuelta: 1 (default) o 2.
        departamento / provincia / distrito: al menos uno. Case-insensitive.
        limit: máx 5000.
        offset: paginación.

    Si el año no está disponible, devuelve `available=false` con el motivo.
    """
    started_ms = now_ms()
    try:
        result = store.listar_mesas_por_geo(
            año=int(anio), vuelta=int(vuelta),
            departamento=departamento, provincia=provincia, distrito=distrito,
            limit=int(limit), offset=int(offset),
        )
        return ok_response(result, started_ms=started_ms, meta={"source": f"sqlite_{anio}"})
    except Exception as exc:
        logger.exception("Error en onpe_listar_mesas_por_geo")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_listar_locales_por_geo(
    anio: int = 2026,
    vuelta: int = 1,
    departamento: str | None = None,
    provincia: str | None = None,
    distrito: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Lista locales de votación únicos en una geo, con #mesas y #electores por local.

    Para 2021 devuelve un mensaje informativo: el CSV oficial PCM no incluye
    nombre de local de votación, solo ubigeo + distrito.
    """
    started_ms = now_ms()
    try:
        result = store.listar_locales_por_geo(
            año=int(anio), vuelta=int(vuelta),
            departamento=departamento, provincia=provincia, distrito=distrito,
            limit=int(limit),
        )
        return ok_response(result, started_ms=started_ms, meta={"source": f"sqlite_{anio}"})
    except Exception as exc:
        logger.exception("Error en onpe_listar_locales_por_geo")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_mesa_geo_lookup(
    codigo_mesa: str,
    anio: int = 2026,
    vuelta: int = 1,
) -> dict[str, Any]:
    """Lookup ligero: dada una mesa, devuelve SOLO geo + estado (sin votos).

    Útil para responder preguntas tipo "Mesa 900100 en qué distrito está" o
    "validar si la mesa X corresponde al distrito Y".
    """
    started_ms = now_ms()
    try:
        result = store.mesa_geo_lookup(str(codigo_mesa), año=int(anio), vuelta=int(vuelta))
        return ok_response(result, started_ms=started_ms, meta={"source": f"sqlite_{anio}"})
    except Exception as exc:
        logger.exception("Error en onpe_mesa_geo_lookup")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_2021_comparacion_mesa(codigo_mesa: str) -> dict[str, Any]:
    """Compara una mesa entre 1ra y 2da vuelta de 2021 (análogo a `onpe_sv_comparacion_mesa`)."""
    started_ms = now_ms()
    try:
        result = store.comparacion_mesa_2021(str(codigo_mesa))
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_2021"})
    except Exception as exc:
        logger.exception("Error en onpe_2021_comparacion_mesa")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_comparacion_mesa_cross_year(
    codigo_mesa: str,
    anio_a: int,
    anio_b: int,
    vuelta_a: int = 1,
    vuelta_b: int = 1,
) -> dict[str, Any]:
    """Compara una mesa entre dos años distintos (ej. 2021 vs 2026).

    Para años no hidratados (2006/2011/2016) devuelve `available=false` con motivo.
    Devuelve cabecera + top-5 candidatos en cada lado.
    """
    started_ms = now_ms()
    try:
        result = store.comparacion_mesa_cross_year(
            str(codigo_mesa),
            año_a=int(anio_a), año_b=int(anio_b),
            vuelta_a=int(vuelta_a), vuelta_b=int(vuelta_b),
        )
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_cross_year"})
    except Exception as exc:
        logger.exception("Error en onpe_comparacion_mesa_cross_year")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_comparacion_geo_cross_year(
    geo_name: str,
    nivel: str = "departamento",
    anio_a: int = 2021,
    anio_b: int = 2026,
    vuelta_a: int = 2,
    vuelta_b: int = 2,
    top_n: int = 5,
) -> dict[str, Any]:
    """Compara top-N candidatos en una geo (dpto/prov/distrito) entre dos años.

    Ej: compara Miraflores 2V 2021 vs 2V 2026. Útil para análisis de continuidad
    o cambio de preferencias geográficas entre ciclos electorales.
    """
    started_ms = now_ms()
    try:
        result = store.comparacion_geo_cross_year(
            nivel=str(nivel), geo_name=str(geo_name),
            año_a=int(anio_a), año_b=int(anio_b),
            vuelta_a=int(vuelta_a), vuelta_b=int(vuelta_b),
            top_n=int(top_n),
        )
        return ok_response(result, started_ms=started_ms, meta={"source": "sqlite_cross_year"})
    except Exception as exc:
        logger.exception("Error en onpe_comparacion_geo_cross_year")
        return error_response(str(exc), started_ms=started_ms)


def _infer_2021_vuelta(q_norm: str) -> int:
    if any(k in q_norm for k in ("segunda vuelta", "2da vuelta", "2a vuelta", "ballotage", "balotaje")):
        return 2
    if any(k in q_norm for k in ("primera vuelta", "1ra vuelta", "1a vuelta")):
        return 1
    return 1


def _resolve_query_year(q_norm: str) -> int | None:
    years = re.findall(r"\b(20\d{2})\b", q_norm or "")
    if not years:
        return None
    if "2021" in years:
        return 2021
    if "2026" in years:
        return 2026
    return None


def _extract_geo_fragment_2021(q: str, q_norm: str) -> str | None:
    m = re.search(r"\ben\s+([A-Za-zÁÉÍÓÚÑáéíóúñ\s]{3,60})$", q.strip())
    if m:
        return m.group(1).strip()
    m2 = re.search(r"\b(?:en|de)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ\s]{3,60})\b", q)
    if m2:
        cand = m2.group(1).strip()
        if _norm(cand) not in {"la", "el", "peru", "2021"}:
            return cand
    return None


@mcp.tool()
def onpe_2021_chat(query: str, vuelta: int | None = None) -> dict[str, Any]:
    """Interfaz conversacional para elecciones presidenciales 2021 (1V/2V)."""
    started_ms = now_ms()
    try:
        q = str(query or "").strip()
        if len(q) < 3:
            return ok_response(
                {
                    "intent": "unknown_2021",
                    "answer": (
                        "Puedo responder sobre 2021: mesa, top nacional, top por departamento/provincia/distrito, "
                        "y votos por candidato (1ra o 2da vuelta)."
                    ),
                },
                started_ms=started_ms,
            )

        total_2021 = store.total_mesas_2021()
        if total_2021 == 0:
            return ok_response(
                {
                    "intent": "db_not_hydrated_2021",
                    "answer": (
                        "La base 2021 aún no está hidratada. Ejecuta **onpe_2021_bootstrap()** "
                        "para cargar 1ra y 2da vuelta desde peruvoto2021."
                    ),
                },
                started_ms=started_ms,
            )

        q_norm = _norm(q)
        round_2021 = int(vuelta) if vuelta in (1, 2) else _infer_2021_vuelta(q_norm)
        top_n = extract_top_n(q, default=5, minimum=1, maximum=20)
        geo = _extract_geo_fragment_2021(q, q_norm)

        mesa_match = re.search(r"\b(\d{1,6})\b", q)
        if mesa_match and "mesa" in q_norm:
            code = validate_mesa_code(mesa_match.group(1))
            mesa = store.get_mesa_2021_from_local(code, vuelta=round_2021)
            if mesa is None:
                return ok_response(
                    {
                        "intent": "mesa_2021",
                        "answer": f"Mesa {code} no encontrada en 2021 vuelta {round_2021}.",
                        "result": {"found": False, "codigo_mesa": code, "vuelta": round_2021},
                        "source": "sqlite_2021",
                    },
                    started_ms=started_ms,
                )
            top = mesa["votos"][:3]
            top_txt = ", ".join(f"{x['candidato'] or x['partido']} {x['votos']:,}v" for x in top)
            return ok_response(
                {
                    "intent": "mesa_2021",
                    "answer": (
                        f"Mesa {mesa['codigo_mesa']} (2021 {'2da' if round_2021 == 2 else '1ra'} vuelta, "
                        f"{mesa['departamento']} / {mesa['provincia']} / {mesa['distrito']}): "
                        f"{mesa['votos_emitidos']:,} emitidos, {mesa['votos_validos']:,} válidos. Top: {top_txt}."
                    ),
                    "result": mesa,
                    "source": "sqlite_2021",
                },
                started_ms=started_ms,
            )

        cand_query = None
        _cand_match = re.search(
            r"\b(?:cu[aá]ntos?\s+votos?\s+(?:sac[oó]|obtuvo|tuvo)|votos?\s+de|votaci[oó]n\s+de)\s+(.+?)(?:\s+en\b.*)?$",
            q,
            flags=re.IGNORECASE,
        )
        if _cand_match:
            cand_query = _cand_match.group(1).strip()
        if cand_query:
            cand = store.get_candidate_votes_2021(vuelta=round_2021, candidate_query=cand_query, geo_query=geo)
            if cand:
                place = f" en {cand['filtro']}" if cand.get("filtro") else ""
                return ok_response(
                    {
                        "intent": "candidate_2021",
                        "answer": (
                            f"{cand['candidato']} ({cand['partido']}) obtuvo {cand['votos']:,} votos "
                            f"en 2021 {'2da' if round_2021 == 2 else '1ra'} vuelta{place}."
                        ),
                        "result": cand,
                        "source": "sqlite_2021",
                    },
                    started_ms=started_ms,
                )

        agg = store.aggregate_votes_2021(vuelta=round_2021, geo_query=geo, top_n=top_n)
        title_geo = f" en {agg['filtro']}" if agg.get("filtro") else " a nivel nacional"
        lines = [
            f"**Top {top_n} 2021 {'2da' if round_2021 == 2 else '1ra'} vuelta{title_geo}** "
            f"({agg['mesas']:,} mesas, {agg['votos_emitidos']:,} votos emitidos)",
            "",
        ]
        for i, r in enumerate(agg["top"], 1):
            lines.append(f"{i}. **{r['candidato'] or r['nombre_partido']}** — {r['total_votos']:,} votos")
        return ok_response(
            {
                "intent": "ranking_2021",
                "answer": "\n".join(lines),
                "result": agg,
                "source": "sqlite_2021",
            },
            started_ms=started_ms,
        )
    except Exception as exc:
        logger.exception("Error en onpe_2021_chat")
        return error_response(str(exc), started_ms=started_ms)


@mcp.tool()
def onpe_chat(query: str, id_eleccion: int = 10, timeout: int = 10) -> dict[str, Any]:
    """Interfaz conversacional única para consultas comunes de ONPE con estrategia cache-first.

    Orden de prioridad de datos:
      1. Cache local SQLite (datos hidratados del MCP) — siempre primero.
      2. API ONPE en vivo — cuando el dato no está en cache.
      3. Compendio cualitativo verificable (knowledge_base.py) — fallback pedagógico sin cifras inventadas.
      4. Fuentes externas — indicado explícitamente cuando aplica.

    timeout: segundos máximos para llamadas a la API ONPE en vivo (default 10s).
    Para consultas que requieren hidratación masiva usa timeout=30 explícito.
    """
    started_ms = now_ms()
    try:
        q = str(query or "").strip()
        q_norm_early = _norm(q)
        query_year = _resolve_query_year(q_norm_early)
        if query_year == 2021:
            res_2021 = onpe_2021_chat(query=q)
            return res_2021
        if not q or len(q) < 3:
            return ok_response(
                {
                    "intent": "unknown",
                    "answer": (
                        "¡Hola! Puedo responder consultas sobre resultados electorales del Perú 2026 y 2021. "
                        "Por ejemplo: *'¿cuántos votos obtuvo López Aliaga en Lima?'* "
                        "o *'top 5 en Arequipa'* o *'senadores para Puno'*."
                    ),
                },
                started_ms=started_ms,
            )

        # ── Guard: saludos y queries muy cortas ─────────────────────────────
        _GREETINGS = {"hola", "hi", "hey", "buenas", "ola", "hello", "saludos", "que tal"}
        _GREETING_PHRASES = {
            "hola como estas", "hola como esta", "hola que tal", "como estas", "como esta usted",
            "buenos dias", "buenas noches", "buenas tardes",
            "hola buenas tardes", "hola buenas noches", "hola buenos dias",
            "hola buen dia", "hola buen tarde", "buen dia", "buenas como estas",
        }
        _PERSONAL_QUERIES = {
            "como te llamas", "cual es tu nombre", "quien eres", "que eres",
            "que puedes hacer", "como te llamo", "tu nombre", "como funciona",
        }
        _q_lower = q.lower().strip("¿?!.,")
        if _q_lower in _GREETINGS or _q_lower in _PERSONAL_QUERIES or _q_lower in _GREETING_PHRASES or len(q) < 4:
            return ok_response(
                {
                    "intent": "unknown",
                    "answer": (
                        "¡Hola! Puedo responder consultas sobre resultados electorales del Perú 2026 y 2021. "
                        "Por ejemplo: *'¿cuántos votos obtuvo López Aliaga en Lima?'* "
                        "o *'top 5 en Arequipa'* o *'senadores para Puno'*."
                    ),
                },
                started_ms=started_ms,
            )

        # ── Guard: dominios claramente no electorales ──────────────────────
        _q_norm_guard = _norm(q)
        _NON_ELECTORAL_TOKENS = frozenset({
            "dolar", "euro", "libra", "yen", "precio", "costo", "coste",
            "gasolina", "petroleo", "gas", "temperatura", "clima",
            "tipo de cambio", "cotizacion", "bitcoin", "criptomoneda",
            "llover", "lluvia", "lluvias", "llueve", "calor", "frio", "viento",
            "trafico", "congestion", "accidente", "noticias", "noticia",
            "moneda", "cambio de moneda", "tipo de cambio",
            "mide", "pesa", "altura", "distancia", "longitud", "peso", "talla",
            "hotel", "hoteles", "restaurante", "turismo", "vuelos", "hospedaje",
            "ingles", "frances", "idioma", "traducir", "traduccion",
            "plato", "comida", "gastronomia", "receta", "ingredientes",
            "mundial", "campeonato", "torneo", "copa", "deporte", "futbol", "olimpiadas",
            "planeta", "planetas", "sistema solar", "estrella", "galaxia", "universo",
            "independencia", "liberacion", "fundacion", "constitucion", "historia",
            "pelicula", "peliculas", "oscar", "cine", "cinema", "actor", "actriz",
            "nominacion", "nominaciones", "serie", "television", "musica", "cancion",
            "album", "artista", "concierto", "espectaculo", "teatro", "obra",
            "vuelo", "vuelos", "aerolinea", "aerolineas", "pasaje", "pasajes",
            "champions", "liga europea", "liga espanola", "formula uno", "nba",
            "real madrid", "barcelona", "chelsea", "arsenal", "manchester",
            # Economía laboral
            "sueldo", "salario", "remuneracion", "salario minimo", "sueldo minimo",
            "pension", "jubilacion", "bonificacion", "gratificacion",
            # Fauna / flora / naturaleza
            "animales", "plantas", "fauna", "flora", "especies", "biodiversidad",
            "mamiferos", "aves", "reptiles", "anfibios", "peces", "insectos",
            "bosque", "selva tropical", "ecosistema",
            # Economía / estadísticas no electorales
            "pib", "gdp", "inflacion", "inflación", "economia", "economía",
            "desempleo", "desocupacion", "pobreza", "recesion", "devaluacion",
            "tasa", "indice", "banco", "bancos", "finanzas", "presupuesto",
            # Cargos públicos no-candidatos
            "presidente del peru", "presidente de la republica",
            "primer ministro", "primer presidente",
            # Historia no-electoral
            "guerra",
            # Demografía y geografía no-electoral
            "habitantes", "poblacion", "pobladores", "censo",
            "terremoto", "sismo", "tsunami", "catastrofe", "desastre",
            # PBI/PNB (sinónimos)
            "pbi", "pnb",
            # Economía y política general
            "ingreso", "ingresos", "sueldo", "renta", "corrupto", "corrupcion",
            "democratico", "democracia",  # en contexto no-electoral
            "presidentes",  # "cuantos presidentes ha tenido peru"
        })
        # "tiempo" alone is ambiguous; only block if paired with weather words
        # "cuanto vale/cuesta" = pricing query → non-electoral
        _has_price_query = bool(
            re.search(r"\bcu[aá]nto\s+(?:vale|cuesta|cuestan?|salen?|cobran?)\b", _q_norm_guard)
            and not any(kw in _q_norm_guard for kw in ("voto", "votos", "eleccion", "candidato", "mesa"))
        )
        # "tiempo" alone is ambiguous (also = "time"); only block if paired with weather words
        _has_weather = bool(
            _NON_ELECTORAL_TOKENS & set(_q_norm_guard.split())
            or ("tiempo" in _q_norm_guard and any(w in _q_norm_guard for w in ("hoy", "manana", "clima", "llov")))
        )
        if (_has_weather or _has_price_query) and not any(
            kw in _q_norm_guard for kw in (
                "voto", "votos", "eleccion", "resultado", "candidato", "mesa",
                "senador", "diputado", "congresista", "partido"
            )
        ):
            return ok_response(
                {
                    "intent": "unknown",
                    "answer": (
                        "Esa consulta no parece estar relacionada con resultados electorales. "
                        "Puedo responder preguntas como: *'¿cuántos votos obtuvo López Aliaga?'* "
                        "o *'top 5 en Arequipa'* o *'senadores para Puno'*."
                    ),
                },
                started_ms=started_ms,
            )

        # Historical/biographical queries → unknown
        # Preguntas geográficas administrativas (no electorales): "cuántos departamentos tiene el peru"
        if re.search(r"\bcu[aá]ntos?\s+(?:departamentos?|provincias?|distritos?|municipios?|regiones?|ciudades?|hospitales?|cl[ií]nicas?|escuelas?|colegios?|universidades?|centros?\s+(?:de\s+salud|comerciales?|educativos?)|postas?|farmacias?|parques?|museos?|iglesias?|cementerios?|habitantes?|personas?|pobladores?)\s+(?:tiene|hay|existen?|son|viven?)\b", _q_norm_guard) and not any(kw in _q_norm_guard for kw in ("voto", "votos", "eleccion", "candidato", "mesa", "resultado")):
            return ok_response(
                {
                    "intent": "unknown",
                    "answer": (
                        "Esa pregunta es sobre geografía administrativa, no sobre resultados electorales. "
                        "Puedo ayudarte con *'¿cuántos votos obtuvo X en Arequipa?'* o *'top 5 en Lima'*."
                    ),
                },
                started_ms=started_ms,
            )
        # Trivial/factual geo questions: "cual es la capital de X" → non-electoral
        if re.search(r"\bcu[aá]l\s+es\s+(?:la|el)?\s*(?:capital|idioma|moneda|bandera|himno|poblaci[oó]n|superficie|area|extension)\s+(?:de[l]?|oficial\s+de)\b", _q_norm_guard) and not any(kw in _q_norm_guard for kw in ("voto", "votos", "eleccion", "candidato", "mesa", "resultado")):
            return ok_response(
                {
                    "intent": "unknown",
                    "answer": (
                        "Esa pregunta es sobre geografía o cultura general, no sobre resultados electorales. "
                        "Puedo ayudarte con votos, candidatos o mesas electorales peruanas 2026."
                    ),
                },
                started_ms=started_ms,
            )

        # Sports-match result guard: "el resultado del partido X vs Y" → non-electoral
        if re.search(r"\b(?:resultado|partido)\b", _q_norm_guard) and re.search(r"\bvs\.?\b", _q_norm_guard) and not any(kw in _q_norm_guard for kw in ("voto", "votos", "eleccion", "candidato", "mesa")):
            return ok_response(
                {
                    "intent": "unknown",
                    "answer": (
                        "Esa consulta parece sobre deportes o competencias, no sobre resultados electorales. "
                        "Puedo responder sobre votos, candidatos y mesas electorales peruanas."
                    ),
                },
                started_ms=started_ms,
            )

        # Scheduling / sports query: "cuando es el proximo partido/juego/encuentro" → non-electoral
        if re.search(r"\b(?:cuando|que\s+dia|a\s+que\s+hora)\b", _q_norm_guard) and re.search(r"\b(?:partido|juego|encuentro|match)\b", _q_norm_guard) and not any(kw in _q_norm_guard for kw in ("voto", "votos", "eleccion", "candidato", "mesa")):
            return ok_response(
                {
                    "intent": "unknown",
                    "answer": (
                        "Esa pregunta parece ser sobre deportes o agenda, no sobre resultados electorales. "
                        "Puedo ayudarte con votos, candidatos y mesas de las elecciones peruanas."
                    ),
                },
                started_ms=started_ms,
            )

        # Preguntas históricas fuertes que contienen keywords electorales pero siguen siendo históricas
        # (el bypass normal de _has_historical bloquea "eleccion"/"candidato" en la query)
        if re.search(
            r"\b(?:primera\s+elecci[oó]n\s+presidencial|primer\s+candidato\s+a\s+la\s+presidencia)\b",
            _q_norm_guard,
        ):
            return ok_response(
                {
                    "intent": "unknown",
                    "answer": (
                        "Esa pregunta es de carácter histórico y está fuera del alcance de los resultados "
                        "electorales peruanos 2026/2021. Puedo responder sobre votos, candidatos y mesas de "
                        "las elecciones actuales."
                    ),
                },
                started_ms=started_ms,
            )

        _has_historical = bool(
            re.search(r"\b(?:antes\s+de\s+ser|antes\s+de\s+convertirse|biografia|historia\s+de|quien\s+fue\s+.+\s+antes|nació|murio|estudio|se\s+fund[oó]|se\s+cre[oó]|fue\s+fundado|fue\s+creado|cuando\s+(?:se\s+)?(?:fund|cre|naci|establec)|primer\s+(?:presidente|mandatario|ministro|alcalde|gobernador|rector|director|secretario|canciller)|pib\b|gdp\b|inflaci[oó]n\b|econom[ií]a\b|desempleo\b|pobreza\b|como\s+se\s+llama\b|cu[aá]l\s+es\s+el\s+nombre\s+de\b|cu[aá]l\s+es\s+la\s+capital\s+de\b|quien\s+(?:es|era|fue)\s+el\s+presidente\b|quien\s+(?:es|era|fue)\s+el\s+(?:primer\s+)?ministro\b|primera\s+elecci[oó]n\s+presidencial|primer\s+candidato\s+a\s+la\s+presidencia|cuantos\s+presidentes\b)\b", _q_norm_guard)
            and not any(kw in _q_norm_guard for kw in ("voto", "votos", "eleccion", "resultado", "candidato", "mesa"))
        )
        # "como funciona / que es / define / explica" + electoral term → definitional (unknown)
        _has_definitional = bool(
            re.search(r"\b(?:como\s+funciona|qu[eé]\s+es|define\s|definicion\s+de|explicar?\b|explicame\b|que\s+significa|como\s+se\s+hace|como\s+funciona(?:\s+el)?|propuesta(?:s)?\s+(?:de|del?|economica|politica|social)|plan\s+de\s+gobierno|programa\s+de\s+gobierno|ideologia\s+de|partido\s+(?:de|del?)|afiliacion\s+(?:de|politica)|que\s+dice\s+la\s+constituci[oó]n|constituci[oó]n\s+(?:sobre|acerca)|hay\s+en\s+el\s+mundo|en\s+el\s+mundo\b)\b", _q_norm_guard)
            and not any(kw in _q_norm_guard for kw in ("voto", "votos", "candidato", "mesa", "resultado"))
        )
        if _has_historical:
            return ok_response(
                {
                    "intent": "unknown",
                    "answer": (
                        "Esa pregunta parece ser biográfica o histórica, fuera del alcance electoral. "
                        "Puedo responder sobre votos, resultados o candidatos en las elecciones peruanas 2026 y 2021."
                    ),
                },
                started_ms=started_ms,
            )
        if _has_definitional:
            return ok_response(
                {
                    "intent": "unknown",
                    "answer": (
                        "Esa pregunta parece ser de definición o concepto, fuera del alcance electoral directo. "
                        "Puedo responder sobre votos, candidatos y resultados de las elecciones peruanas 2026 y 2021."
                    ),
                },
                started_ms=started_ms,
            )

        # Personal/biographical query about candidates → non-electoral
        if re.search(r"\bcu[aá]ntos?\s+(?:hijos?|hermanos?|esposos?|esposas?|marido|mujer|carros?|casas?|dinero|sueldo|deudas?|bienes?|a[ñn]os?\s+(?:tiene|tuvo|cumple)|novio|novia|cuentas?|patrimonio|seguros?|propiedades?)\b", _q_norm_guard):
            return ok_response(
                {
                    "intent": "unknown",
                    "answer": (
                        "Esa pregunta es sobre datos personales o biográficos, no sobre resultados electorales. "
                        "Puedo responder sobre votos, candidatos y resultados de las elecciones peruanas 2026 y 2021."
                    ),
                },
                started_ms=started_ms,
            )
        if re.search(
            r"\bqu[eé]\s+hora\b|\bdime\s+la\s+hora\b|\bcu[aá]l\s+es\s+la\s+hora\b"
            r"|\bqu[eé]\s+hora\s+es\b|\ba\s+qu[eé]\s+hora\b",
            _q_norm_guard,
        ) and not any(kw in _q_norm_guard for kw in ("voto", "votos", "eleccion", "mesa")):
            return ok_response(
                {
                    "intent": "unknown",
                    "answer": (
                        "Esa pregunta no está relacionada con resultados electorales. "
                        "Puedo ayudarte con votos, candidatos o resultados de las elecciones peruanas 2026 y 2021."
                    ),
                },
                started_ms=started_ms,
            )

        # Detectar preguntas de significado/definición/receta/ciencia → unknown
        if re.search(
            r"\bqu[eé]\s+significa\b"
            r"|\bqu[eé]\s+(?:es|son)\s+(?:la|el|los|las)\s+(?:abstenci[oó]n|padr[oó]n|sufragio|escrutinio|ballot)\b"
            r"|\bcomo\s+se\s+dice\b|\bcomo\s+se\s+traduce\b"
            r"|\bcomo\s+se\s+(?:hace|prepara|cocina|elabora)\b"
            r"|\bqu[eé]\s+ingredientes\b|\breceta\s+de\b"
            r"|\bcu[aá]l\s+es\s+la\s+f[oó]rmula\b"
            r"|\bcu[aá]l\s+es\s+la\s+composici[oó]n\b"
            r"|\bcu[aá]l\s+es\s+la\s+estructura\s+(?:de|del|qu[ií]mica)\b",
            _q_norm_guard,
        ):
            return ok_response(
                {
                    "intent": "unknown",
                    "answer": (
                        "Esa parece ser una pregunta de definición o significado, no sobre resultados electorales. "
                        "Puedo responder sobre votos, candidatos o resultados de las elecciones peruanas 2026 y 2021."
                    ),
                },
                started_ms=started_ms,
            )

        # Detectar preguntas de edad / características personales → unknown
        if re.search(r"\bcu[aá]ntos?\s+a[nñ]os?\s+(?:tiene|tienes?|tendr[aá]s?|ha|cumple|cumpli[oó])\b|\bcu[aá]nto\s+gana\b", _q_norm_guard) and not any(kw in _q_norm_guard for kw in ("voto", "votos", "eleccion", "candidato", "mesa")):
            return ok_response(
                {
                    "intent": "unknown",
                    "answer": (
                        "Esa parece ser una pregunta personal/biográfica. "
                        "Solo puedo responder sobre resultados electorales peruanos 2026/2021."
                    ),
                },
                started_ms=started_ms,
            )

        # Detectar años electorales pasados / futuros → unknown
        _year_m = re.search(r"\b(20\d{2})\b", _q_norm_guard)
        if _year_m and _year_m.group(1) != "2026":
            return ok_response(
                {
                    "intent": "unknown",
                    "answer": (
                        f"Solo tengo datos de las elecciones peruanas 2026 y 2021. "
                        f"La consulta menciona el año {_year_m.group(1)}, que no está en mi base de datos."
                    ),
                },
                started_ms=started_ms,
            )

        # Detectar preguntas matemáticas / aritméticas → unknown
        if re.search(r"\bcu[aá]nto\s+es\b|\bcuanto\s+vale\b|\bcuantos\s+son\b", _q_norm_guard) and re.search(r"\d", _q_norm_guard) and not any(
            kw in _q_norm_guard for kw in ("voto", "votos", "eleccion", "candidato", "mesa")
        ):
            return ok_response(
                {"intent": "unknown", "answer": "Esa no es una consulta electoral. Pregúntame sobre votos, candidatos o resultados electorales del Perú 2026/2021."},
                started_ms=started_ms,
            )

        # ── Guard: DB no hidratada ──────────────────────────────────────────
        try:
            _total_mesas = store.total_mesas_local()
        except Exception:
            _total_mesas = 0

        if _total_mesas == 0:
            onpescraper_ready = (settings.output_dir / "mesas_data.txt").exists()
            if onpescraper_ready:
                next_step = (
                    "Llama a **onpe_bootstrap_snapshot()** para cargar los datos de onpescraper "
                    "(fuente más actualizada). Tarda ~30-60 segundos."
                )
            else:
                next_step = (
                    "Llama a **onpe_bootstrap_atu_manera()** para descargar las 92,766 mesas "
                    "desde GitHub (~2-5 min según red). O clona https://github.com/oscarzamora/onpeescraper "
                    "en la carpeta hermana y llama a onpe_bootstrap_snapshot()."
                )
            return ok_response(
                {
                    "intent": "db_not_hydrated",
                    "hydrated": False,
                    "total_mesas_local": 0,
                    "answer": (
                        "⚠️ **La base de datos local está vacía.** "
                        "El MCP necesita hidratación antes de responder consultas electorales.\n\n"
                        f"**Siguiente paso:** {next_step}\n\n"
                        "Mientras tanto puedo responder preguntas cualitativas sobre el proceso electoral "
                        "usando el compendio interno. Para datos numéricos de mesas específicas, "
                        "usa onpe_get_mesa() directamente (consulta live a ONPE)."
                    ),
                    "next_step": next_step,
                },
                started_ms=started_ms,
            )

        mesa_match = re.search(r"\b(\d{1,6})\b", q)
        # Evitar interpretar años (1900-2099) como códigos de mesa cuando no hay palabra "mesa"
        if mesa_match and "mesa" not in _norm(q):
            _num = int(mesa_match.group(1))
            if 1900 <= _num <= 2099:
                mesa_match = None
        # Evitar que "top 3" o "top 5" dispare intent de mesa con código "000003"
        if mesa_match and re.search(
            r"\btop\s+" + re.escape(mesa_match.group(1)) + r"\b", q, re.IGNORECASE
        ):
            mesa_match = None
        # Evitar que cantidades tipo "50000 votos" o "mas de 100000" se traten como mesa
        if mesa_match and "mesa" not in _norm(q):
            _mstart, _mend = mesa_match.start(1), mesa_match.end(1)
            _before = q[max(0, _mstart - 8):_mstart].lower()
            _after = q[_mend:_mend + 7].lower()
            _has_voto_context = "voto" in _norm(q) or "votos" in _norm(q)
            if (
                _after.lstrip().startswith("voto")
                or re.search(r"\bde\s*$", _before)
                or (re.search(r"\bentre\s*$", _before) and _has_voto_context)  # "entre X y Y votos"
                or (re.search(r"\by\s*$", _before) and _has_voto_context)      # "X y N votos" (rango)
            ):
                mesa_match = None
        # Normalizar puntuación especial para mejorar pattern matching
        q = re.sub(r"[¿¡:;?!]", " ", q)
        # Normalizar símbolo % → "porcentaje" (en cualquier posición)
        q = q.replace("%", " porcentaje ")
        # Normalizar typos fonéticos frecuentes en español peruano (b/v, c/s)
        q = re.sub(r"\bbotos?\b", "votos", q, flags=re.IGNORECASE)  # "botos" → "votos"
        q = re.sub(r"\belecsion\b", "eleccion", q, flags=re.IGNORECASE)  # "elecsion" → "eleccion"
        q = re.sub(r"\bme+s+a\b", "mesa", q, flags=re.IGNORECASE)  # "messa/meesa/messaa" → "mesa"
        q = re.sub(r"\b(?:msa)\b", "mesa", q, flags=re.IGNORECASE)  # "msa" → "mesa"
        q = re.sub(r"\bsak[oó]\b", "saco", q, flags=re.IGNORECASE)  # "sako/sakó" → "saco"
        q = re.sub(r"%", " porcentaje ", q)  # "%" → "porcentaje"
        q = re.sub(r"\s{2,}", " ", q).strip()
        # Eliminar muletillas verbales del inicio/fin (normalización lenguaje natural)
        q = _strip_filler(q)
        # Eliminar "pasó a la segunda vuelta" como filler solo cuando HAY contenido después
        # (no eliminar si es el final: "X pasó a la segunda vuelta <más texto>")
        q = re.sub(
            r"(?<=\S)\s+(?:fue|llego|llegó|entro|entró|pasó|paso|llega|pasa)\s+a\s+la\s+(?:primera|segunda)\s+vuelta\b(?=\s+\S)",
            " ", q, flags=re.IGNORECASE
        ).strip()
        q_norm = _norm(q)
        top_n = extract_top_n(q, default=5, minimum=1, maximum=20)
        _has_sv_kw = any(kw in q_norm for kw in ("segunda vuelta", "segunda_vuelta", "2da vuelta"))
        _has_reasignado_kw = any(kw in q_norm for kw in ("reasign", "local reasignado", "reubicad", "reubican", "huelga", "extorsion", "reconstruccion"))
        _has_transfer_kw = any(kw in q_norm for kw in ("transferencia", "a donde fueron los votos", "proyeccion", "como se repartieron"))

        # EARLY EXIT — Reasignados SV: cuando se nombra dpto/distrito como "Trujillo",
        # el flujo cae a geo_domestic antes. Interceptamos primero si la query menciona
        # reasignados/reubicados/huelga/etc. explícitamente.
        if _has_reasignado_kw:
            _sv_dpto_early = None
            _dpt_m_early = re.search(
                r"\b(?:en|de|del?)\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñ]{2,30}?)(?:\s*$|\s+(?:por|motivo|debido|entre))",
                q, re.IGNORECASE,
            )
            if _dpt_m_early:
                _sv_dpto_early = _dpt_m_early.group(1).strip()
            try:
                reasig_early = store.get_sv_reasignados(dpto=_sv_dpto_early)
            except Exception:
                reasig_early = []
            total_mesas_aff = sum(int(r.get("mesas_afectadas", 0)) for r in reasig_early)
            if reasig_early:
                _lines_r = [f"**{len(reasig_early)} locales reasignados** para segunda vuelta 2026 ({total_mesas_aff} mesas afectadas):\n"]
                for r in reasig_early[:10]:
                    _lines_r.append(
                        f"- {r['nombre_local_original']} → **{r['nombre_local_nuevo']}** "
                        f"({r['dpto']}, {r['motivo']})"
                    )
                if len(reasig_early) > 10:
                    _lines_r.append(f"... y {len(reasig_early)-10} más.")
                _answer_r = "\n".join(_lines_r)
            elif _sv_dpto_early:
                _answer_r = (
                    f"No hay registros de locales reasignados en '{_sv_dpto_early}' "
                    "en la base de datos. Filtros válidos por departamento: LA LIBERTAD, "
                    "LIMA, CAJAMARCA (los que efectivamente tuvieron reubicaciones)."
                )
            else:
                _answer_r = "No hay registros de locales reasignados en la base de datos."
            _data_r = {
                "intent": "sv_reasignados",
                "answer": _answer_r,
                "result": {
                    "total": len(reasig_early),
                    "dpto_filtro": _sv_dpto_early,
                    "locales": reasig_early[:20],
                },
                "source": "sqlite_sv",
            }
            store.append_raw_event("onpe_chat_sv_reasignados_early", {"query": q})
            return ok_response(_data_r, started_ms=started_ms)

        # CLAIM VERIFIER (1V): si la query parece una afirmación cuantitativa
        # impugnable ("faltan 900 mil", "1.2% / 100 mil", "millón no pudo votar"),
        # delegamos al verificador para refutar con cifras oficiales.
        _claim_keywords = (
            "falta", "faltan", "faltaron", "desaparec", "sin contar",
            "no se contar", "no se contabiliz", "no pudo votar", "no pudieron votar",
            "impedid", "nos restar", "nos quitar", "perdimos", "nos robar",
            "patrones irregular", "actas irregular", "fraude", "manipul",
        )
        _has_claim_kw = any(kw in q_norm for kw in _claim_keywords)
        if _has_claim_kw and not _has_sv_kw and not _has_reasignado_kw:
            try:
                _cifras = parse_quantitative_claims(q)
                _tiene_cifra = bool(_cifras["absolutos"]) or bool(_cifras["porcentajes"])
                if _tiene_cifra:
                    _cv = onpe_claim_verifier(claim_text=q, id_eleccion=10)
                    if _cv.get("ok"):
                        data_cv = _cv["data"]
                        data_cv["intent"] = "claim_verifier"
                        data_cv["source"] = "sqlite_1v"
                        data_cv["data_tier"] = "tier_1_local_cache"
                        return ok_response(data_cv, started_ms=started_ms)
            except Exception:  # noqa: BLE001 — degrada al flow normal si falla
                logger.exception("claim_verifier fallback en onpe_chat")

        # SV: conteo actual desde cache hidratado (intent 'sv_resultados').
        # Trigger: queries sobre el conteo / quién va ganando / margen / balotaje.
        # Se intercepta ANTES del JEE para que "cuánto va la segunda vuelta" use el cache.
        _sv_count_triggers = (
            "ballotage", "ballottage", "balotaje",
            "resultado final", "resultado oficial", "quien gana", "quien va ganando",
            "ganador 2v", "conteo actual", "conteo sv", "conteo segunda",
            "cuanto va", "que va", "como va",
        )
        _sv_candidates_hint = (
            ("keiko" in q_norm and "sanchez" in q_norm) or
            ("fujimori" in q_norm and "sanchez" in q_norm) or
            ("fuerza popular" in q_norm and "juntos por el peru" in q_norm)
        )
        _candidate_vs_with_sv = _sv_candidates_hint and _has_sv_kw and (
            " vs " in f" {q_norm} " or " versus " in q_norm
        )
        # No disparar si la query tiene contexto de actas observadas / JEE / reasignados
        _is_jee_or_reasignados = (
            "observad" in q_norm or "jee" in q_norm or
            _has_reasignado_kw or _has_transfer_kw
        )
        _trigger_sv_resultados = (
            (_has_sv_kw and any(t in q_norm for t in _sv_count_triggers))
            or any(t in q_norm for t in ("balotaje", "ballotage", "ballottage"))
            or (_sv_candidates_hint and not _candidate_vs_with_sv)
        ) and not _is_jee_or_reasignados
        if _trigger_sv_resultados:
            try:
                sv_data = store.get_sv_conteo_actual()
                oficial = sv_data.get("oficial", {})
                proy = sv_data.get("proyectado_con_crudo", {})
                candidatos = oficial.get("candidatos", [])
                lines_sv = ["**SEGUNDA VUELTA 2026 — cache hidratado**", ""]
                if oficial.get("pct_contabilizadas") is not None:
                    lines_sv.append(
                        f"📊 {oficial['actas_contabilizadas']:,}/{oficial['total_actas']:,} actas "
                        f"({oficial['pct_contabilizadas']:.4f}% certificado)  ·  "
                        f"participación {oficial.get('participacion', 0):.2f}%"
                    )
                lines_sv.append("")
                lines_sv.append("**Cifras OFICIALES (certificadas ONPE):**")
                for c in candidatos:
                    if c.get('partido_id') in ('8', '10'):
                        lines_sv.append(
                            f"  • {c['nombre']}: {c['votos_validos']:,} votos "
                            f"({c['pct_votos_validos']:.4f}%)"
                        )
                if proy and proy.get('keiko'):
                    lines_sv.append("")
                    lines_sv.append("**Proyectado con crudo capturado (C + E):**")
                    lines_sv.append(f"  • Keiko (FP):    {proy['keiko']:,} ({proy['pct_keiko']:.4f}%)")
                    lines_sv.append(f"  • Sánchez (JxP): {proy['sanchez']:,} ({proy['pct_sanchez']:.4f}%)")
                    lines_sv.append(f"  • **Margen K–S: {proy['margen_keiko_sanchez']:+,d} votos**")
                if sv_data.get("cache_hidratado_al"):
                    lines_sv.append("")
                    lines_sv.append(f"_fuente: cache local SQLite, hidratado {sv_data['cache_hidratado_al']}_")
                store.append_raw_event("onpe_chat_sv_resultados", {"query": q})
                return ok_response(
                    {
                        "intent": "sv_resultados",
                        "answer": "\n".join(lines_sv),
                        "result": sv_data,
                        "source": "sqlite_sv_cache",
                        "data_tier": "tier_1_local_cache",
                    },
                    started_ms=started_ms,
                )
            except Exception:
                logger.exception("Error consultando SV cache en onpe_chat")
                # Cae al flujo normal si algo falla

        # SV: actas observadas / envío al JEE / escenario "todas aceptadas"
        _jee_data = _detect_jee_intent(q, q_norm)
        if _jee_data is not None:
            store.append_raw_event("onpe_chat_sv_estado_actas", {"query": q})
            return ok_response(_jee_data, started_ms=started_ms)

        if _has_reasignado_kw:
            _sv_dpto = None
            _dept_m = re.search(r"\b(?:en|de|del?)\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñ]{2,30}?)(?:\s*$|\s+(?:por|motivo|debido))", q, re.IGNORECASE)
            if _dept_m:
                _sv_dpto = _dept_m.group(1).strip()
            reasig = store.get_sv_reasignados(dpto=_sv_dpto)
            total_mesas_afectadas = sum(int(r.get("mesas_afectadas", 0)) for r in reasig)
            if reasig:
                lines_r = [f"**{len(reasig)} locales reasignados** para segunda vuelta 2026 ({total_mesas_afectadas} mesas afectadas):\n"]
                for r in reasig[:10]:
                    lines_r.append(f"- {r['nombre_local_original']} → **{r['nombre_local_nuevo']}** ({r['dpto']}, {r['motivo']})")
                if len(reasig) > 10:
                    lines_r.append(f"... y {len(reasig)-10} más.")
                answer_r = "\n".join(lines_r)
            else:
                answer_r = "No hay registros de locales reasignados en la base de datos. Ejecuta onpe_sv_bootstrap() primero."
            data = {"intent": "sv_reasignados", "answer": answer_r, "result": {"total": len(reasig), "locales": reasig[:20]}, "source": "sqlite_sv"}
            store.append_raw_event("onpe_chat_sv_reasignados", {"query": q})
            return ok_response(data, started_ms=started_ms)

        if mesa_match and (_has_sv_kw or re.search(r"\bcompar[ae]?\b", q_norm)):
            _sv_code_raw = mesa_match.group(1)
            try:
                _sv_code = validate_mesa_code(_sv_code_raw)
                comparacion = store.get_comparacion_mesa(_sv_code)
                if comparacion["primera_vuelta"] or comparacion["segunda_vuelta"]:
                    _p1 = comparacion.get("primera_vuelta") or {}
                    _p2 = comparacion.get("segunda_vuelta") or {}
                    lines_c = [f"**Mesa {_sv_code} — Comparación 1V vs 2V:**\n"]
                    if _p1:
                        ve1 = _p1.get("votos_emitidos", 0)
                        lines_c.append(f"**Primera vuelta:** {ve1:,} votos emitidos")
                        for v in (_p1.get("votos") or [])[:3]:
                            lines_c.append(f"  • {v['nombre']}: {v['votos']:,}")
                    if _p2:
                        ve2 = _p2.get("votos_emitidos", 0)
                        lines_c.append(f"**Segunda vuelta:** {ve2:,} votos emitidos")
                        for v in (_p2.get("votos") or [])[:3]:
                            lines_c.append(f"  • {v['nombre']}: {v['votos']:,}")
                    data_c = {"intent": "sv_comparacion_mesa", "answer": "\n".join(lines_c), "result": comparacion, "source": "sqlite"}
                    store.append_raw_event("onpe_chat_sv_comparacion_mesa", {"query": q, "codigo_mesa": _sv_code})
                    return ok_response(data_c, started_ms=started_ms)
            except ValueError:
                pass

        if _has_transfer_kw or (re.search(r"\bproyecci[oó]n\b", q_norm) and _has_sv_kw):
            _proj_prefix = None
            _geo_m = re.search(r"\b(?:en|para|de)\s+([A-Za-záéíóúñÁÉÍÓÚÑ]{3,})", q, re.IGNORECASE)
            if _geo_m:
                _geo_name = _geo_m.group(1).strip()
                _dept_r = find_peru_department_prefix(_geo_name)
                if _dept_r:
                    _, _proj_prefix = _dept_r

            with store._connect() as _pc:
                _proj_exists = _pc.execute("SELECT COUNT(*) AS c FROM proyeccion_sv_by_ubigeo").fetchone()["c"]
            if _proj_exists == 0:
                store.rebuild_proyeccion_sv()

            proj_rows = store.get_proyeccion_sv(_proj_prefix)
            if proj_rows:
                if not _proj_prefix:
                    total_1v = sum(int(r.get("votos_1v_total", 0)) for r in proj_rows)
                    total_pk = sum(int(r.get("votos_proyectados_keiko", 0)) for r in proj_rows)
                    total_ps = sum(int(r.get("votos_proyectados_sanchez", 0)) for r in proj_rows)
                    total_abs = sum(int(r.get("votos_abstencion_estimada", 0)) for r in proj_rows)
                    answer_t = (
                        f"**Proyección de transferencia de votos (modelo NNLS, ~86K mesas):**\n\n"
                        f"De los {total_1v:,} votos válidos de primera vuelta:\n"
                        f"- **Keiko Fujimori**: ~{total_pk:,} votos proyectados ({total_pk/total_1v*100:.1f}%)\n"
                        f"- **Roberto Sánchez**: ~{total_ps:,} votos proyectados ({total_ps/total_1v*100:.1f}%)\n"
                        f"- **Abstención estimada**: ~{total_abs:,} votos (~{total_abs/total_1v*100:.1f}%)\n\n"
                        f"⚠️ Proyección basada en patrones electorales históricos. "
                        f"Los resultados reales de segunda vuelta son los definitivos."
                    ) if total_1v > 0 else "Sin datos de primera vuelta para proyectar."
                else:
                    answer_t = f"Proyección para el área consultada: {len(proj_rows)} ubigeos procesados."
                data_t = {"intent": "sv_proyeccion_transferencia", "answer": answer_t, "result": {"rows": proj_rows[:50]}, "source": "sqlite"}
                store.append_raw_event("onpe_chat_sv_proyeccion", {"query": q})
                return ok_response(data_t, started_ms=started_ms)

        if _has_sv_kw:
            # J4: Cobertura de actas SV
            if re.search(r"\bcobertura\b", q_norm):
                rows_cob = store.get_sv_cobertura()
                lines_cob = ["**Cobertura de actas — Segunda vuelta 2026:**\n"]
                for r in rows_cob:
                    nm = r.get("nombre_departamento", "")
                    pct = float(r.get("pct_actas_contabilizadas", 0))
                    c = int(r.get("actas_contabilizadas", 0))
                    if nm:
                        lines_cob.append(f"- {nm}: {pct:.1f}% ({c:,} actas)")
                answer_cob = "\n".join(lines_cob)
                data_cob = {"intent": "sv_cobertura", "answer": answer_cob, "result": rows_cob, "source": "sqlite_sv"}
                store.append_raw_event("onpe_chat_sv_cobertura", {"query": q})
                return ok_response(data_cob, started_ms=started_ms)

            _sv_ubigeo = None
            _sv_nombre = None
            _sv_nivel = "nacional"

            # J7: Geo comparison (1V vs 2V) — "compara Lima primera y segunda vuelta"
            _has_compar_geo_kw = bool(
                re.search(r"\bcompar[ae]?\b", q_norm) or ("primera" in q_norm and "segunda" in q_norm)
            )
            if _has_compar_geo_kw:
                _comp_dept_match = find_peru_department_prefix(q)
                if _comp_dept_match:
                    _comp_name, _comp_prefix = _comp_dept_match
                    _comp_ubigeo = _comp_prefix + "0000"
                    comp = store.get_comparacion_geo(_comp_ubigeo)
                    if comp["primera_vuelta"]["mesas"] > 0 or comp["segunda_vuelta"]["mesas"] > 0:
                        v1 = comp["primera_vuelta"]["votos"]
                        v2 = comp["segunda_vuelta"]["votos"]
                        m1 = comp["primera_vuelta"]["mesas"]
                        m2 = comp["segunda_vuelta"]["mesas"]
                        lines_comp = [f"**Comparación 1V vs 2V — {_comp_name.title()}:**\n"]
                        lines_comp.append(f"Primera vuelta: {m1:,} mesas")
                        for v in v1[:4]:
                            lines_comp.append(f"  • {v.get('nombre') or v.get('partido_id','?')}: {int(v.get('total_votos',0)):,}")
                        lines_comp.append(f"\nSegunda vuelta: {m2:,} mesas")
                        for v in v2[:4]:
                            lines_comp.append(f"  • {v.get('nombre') or v.get('partido_id','?')}: {int(v.get('total_votos',0)):,}")
                        answer_comp = "\n".join(lines_comp)
                        data_comp = {"intent": "sv_comparacion_geo", "answer": answer_comp, "result": comp, "source": "sqlite"}
                        store.append_raw_event("onpe_chat_sv_comparacion_geo", {"query": q})
                        return ok_response(data_comp, started_ms=started_ms)

            # Geo resolution: dept → exterior country → Peru district
            _sv_dept_match = find_peru_department_prefix(q)
            if _sv_dept_match:
                _sv_dept_name, _sv_dept_prefix = _sv_dept_match
                _sv_ubigeo = _sv_dept_prefix + "0000"
                _sv_nivel = "departamento"
                _sv_nombre = _sv_dept_name
            else:
                # J8: Exterior country/city (e.g. "Argelia segunda vuelta")
                # Use extract_foreign_geo_candidates to strip stopwords and find country tokens.
                # Guard: skip candidates <4 chars (e.g. "van" → Vancouver false-positive)
                # and candidates that are purely electoral vocabulary.
                _SV_ELECTION_VOCAB = {
                    "segunda", "vuelta", "candidato", "candidatos", "votos", "voto",
                    "resultado", "resultados", "primera", "2da", "eleccion", "elecciones",
                }
                _sv_foreign_hits: list[dict] = []
                for _fld, _fval in extract_foreign_geo_candidates(q):
                    _cand_tokens = [t for t in _fval.split() if t]
                    # Skip if too short to be a country/city name
                    if len(_fval.strip()) < 4:
                        continue
                    # Skip if all tokens are electoral vocabulary
                    if _cand_tokens and all(t in _SV_ELECTION_VOCAB for t in _cand_tokens):
                        continue
                    _hits = store.find_foreign_ubigeos(_fval, _fld)
                    if _hits:
                        _sv_foreign_hits = _hits
                        break
                if _sv_foreign_hits:
                    _sv_foreign_pais = str(_sv_foreign_hits[0].get("pais", "")).strip()
                    if _sv_foreign_pais:
                        _sv_nivel = "pais_exterior"
                        _sv_nombre = _sv_foreign_pais
                else:
                    # J3: Peru district/city (e.g. "San Isidro segunda vuelta")
                    _sv_district_match = store.find_domestic_ubigeos_by_geo_name(q)
                    if _sv_district_match and _sv_district_match[1]:
                        _sv_nombre, _sv_ubigeos_list = _sv_district_match
                        _sv_ubigeo = str(_sv_ubigeos_list[0]).zfill(6)
                        _sv_nivel = "distrito"

            sv_rows = store.query_sv_geo(nivel=_sv_nivel, ubigeo=_sv_ubigeo, nombre=_sv_nombre, top_n=top_n)
            if sv_rows:
                geo_label = _sv_nombre or "nivel nacional"
                lines_sv = [f"**Resultados de segunda vuelta 2026** — {geo_label}:\n"]
                candidatos_sv = [r for r in sv_rows if str(r.get("partido_id", "")) not in ("80", "81", "82")]
                others_sv = [r for r in sv_rows if str(r.get("partido_id", "")) in ("80", "81", "82")]
                for r in candidatos_sv[:top_n]:
                    vv = int(r.get("votos_validos") or r.get("votos") or 0)
                    pct = float(r.get("pct_votos_validos") or 0)
                    nombre = str(r.get("nombre_candidato") or r.get("nombre_agrupacion") or "")
                    lines_sv.append(f"- **{nombre}**: {vv:,} votos válidos ({pct:.2f}%)")
                for r in others_sv[:2]:
                    vv = int(r.get("votos_validos") or r.get("votos") or 0)
                    nombre = str(r.get("nombre_candidato") or r.get("nombre_agrupacion") or "")
                    lines_sv.append(f"  ({nombre}: {vv:,})")
                nac_rows = store.query_sv_nacional()
                if nac_rows:
                    n0 = nac_rows[0]
                    pct_actas = float(n0.get("actas_contabilizadas_pct") or 0)
                    cont = int(n0.get("contabilizadas") or 0)
                    total_a = int(n0.get("total_actas") or 0)
                    lines_sv.append(f"\n📊 Cobertura: {pct_actas:.2f}% ({cont:,}/{total_a:,} actas)")
                answer_sv = "\n".join(lines_sv)
                _sv_intent = (
                    "geo_exterior" if _sv_nivel in ("pais_exterior", "continente")
                    else "geo_domestic" if _sv_nivel in ("departamento", "provincia", "distrito", "ciudad")
                    else "nacional"
                )
                data_sv = {
                    "intent": _sv_intent,
                    "answer": answer_sv,
                    "result": {"nivel": _sv_nivel, "ubigeo": _sv_ubigeo, "resultados": sv_rows},
                    "source": "sqlite_sv",
                }
                store.append_raw_event("onpe_chat_sv_geo", {"query": q, "nivel": _sv_nivel})
                return ok_response(data_sv, started_ms=started_ms)
            sv_total = store.total_mesas_sv_local()
            if sv_total == 0:
                return ok_response(
                    {
                        "intent": "sv_not_bootstrapped",
                        "answer": (
                            "⚠️ No hay datos de segunda vuelta en la base de datos local. "
                            "Ejecuta **onpe_sv_bootstrap()** para cargar los datos."
                        ),
                    },
                    started_ms=started_ms,
                )

        # Intención 0: legislativo (diputados/senadores/escaños/congresistas) más votado por distrito
        if ("diputad" in q_norm or "senador" in q_norm or "congresista" in q_norm
                or re.search(r"\besca[nñ]os?\b", q_norm)
                or re.search(r"\brepresentantes?\b", q_norm)
                or re.search(r"\bparlamentarios?\b", q_norm)
                or re.search(r"\blegisladores?\b", q_norm)
                or re.search(r"\bcurules?\b", q_norm)):
            cargo = "senadores" if ("senador" in q_norm or ("esca" in q_norm and "senador" in q_norm)) else "diputados"
            if "senador" in q_norm:
                cargo = "senadores"
            distrito_expr = q
            match = re.search(r"\b(?:en|para)\s+(.+)$", q, flags=re.IGNORECASE)
            if match:
                distrito_expr = match.group(1).strip()
            if _is_local_only():
                distrito_nombre = distrito_expr.upper()
                if distrito_nombre == "CUZCO":
                    distrito_nombre = "CUSCO"
                return ok_response(
                    {
                        "intent": "legislative_top_candidate",
                        "answer": (
                            "La consulta legislativa live está deshabilitada en modo local-only. "
                            f"Sin datos legislativos locales para '{distrito_nombre}'."
                        ),
                        "result": {
                            "cargo": cargo,
                            "distrito": {"id": None, "nombre": distrito_nombre},
                            "available": False,
                        },
                        "source": "local_only",
                    },
                    started_ms=started_ms,
                )

            district: object
            try:
                district = onpe_api.resolve_district(distrito_expr)
            except Exception:
                district = None
            if district is None:
                data = {
                    "intent": "legislative_top_candidate",
                    "answer": f"No encontré distrito electoral para '{distrito_expr}'.",
                    "result": None,
                    "source": "onpe_live",
                }
                return ok_response(data, started_ms=started_ms)

            endpoint_candidates: list[tuple[str, int]]
            if cargo == "diputados":
                endpoint_candidates = [("eleccion-diputado/participantes-por-candidato", 13)]
            else:
                endpoint_candidates = [
                    ("eleccion-senador-multiple/participantes-por-candidato", 14),
                    ("eleccion-senador/participantes-por-candidato", 14),
                ]

            top_rows: list[dict[str, Any]] = []
            chosen_endpoint: str | None = None
            chosen_election_id: int | None = None
            last_error: Exception | None = None

            for endpoint_path, election_id in endpoint_candidates:
                try:
                    rows = onpe_api.get_candidates_by_district(
                        endpoint_path=endpoint_path,
                        id_eleccion=election_id,
                        id_distrito_electoral=district.id_distrito_electoral,
                        page_size=200,
                    )
                    if rows:
                        top_rows = rows
                        chosen_endpoint = endpoint_path
                        chosen_election_id = election_id
                        break
                except Exception as exc:
                    last_error = exc

            if not top_rows:
                error_msg = str(last_error) if last_error else "sin datos"
                data = {
                    "intent": "legislative_top_candidate",
                    "answer": (
                        f"El endpoint de {cargo} para '{district.nombre}' no está disponible "
                        "en este momento — ONPE puede estar devolviendo HTML en vez de JSON "
                        "(anti-bot o mantenimiento). Intenta más tarde o usa onpe_get_mesa "
                        "para consultas individuales.\n\n"
                        f"Distrito encontrado: **{district.nombre}** "
                        f"(id={district.id_distrito_electoral})"
                    ),
                    "result": {
                        "cargo": cargo,
                        "distrito": {
                            "id": district.id_distrito_electoral,
                            "nombre": district.nombre,
                        },
                        "available": False,
                    },
                    "source": "onpe_live_unavailable",
                    "meta": {"error": error_msg},
                }
                store.append_raw_event(
                    "onpe_chat_legislative_unavailable",
                    {"query": q, "cargo": cargo, "district_id": district.id_distrito_electoral, "error": error_msg},
                )
                return ok_response(data, started_ms=started_ms)

            top = top_rows[0]
            answer = (
                f"El {cargo[:-1]} más votado en {district.nombre} es "
                f"{top['nombre_candidato']} ({top['nombre_agrupacion']}) con "
                f"{top['votos_validos']} votos válidos."
            )
            data = {
                "intent": "legislative_top_candidate",
                "answer": answer,
                "result": {
                    "cargo": cargo,
                    "distrito": {
                        "id": district.id_distrito_electoral,
                        "nombre": district.nombre,
                    },
                    "top_candidate": top,
                    "top_10": top_rows[:10],
                    "meta": {
                        "endpoint": chosen_endpoint,
                        "id_eleccion": chosen_election_id,
                    },
                },
                "source": "onpe_live",
            }
            store.append_raw_event(
                "onpe_chat_legislative_top_candidate",
                {
                    "query": q,
                    "cargo": cargo,
                    "district_id": district.id_distrito_electoral,
                    "district_name": district.nombre,
                    "endpoint": chosen_endpoint,
                    "id_eleccion": chosen_election_id,
                },
            )
            return ok_response(data, started_ms=started_ms)

        # ── Helpers de prefijo de mesa compartidos por los siguientes bloques ──
        _CAND_PATTERNS_SHARED = [
            re.compile(
                r"\b(?:fue|quedo|qued[oó]|estuvo)\s+primero\s+(.+?)(?=\s*$|\s+en\b|\s+con\b|\s+para\b|\s+sobre\b)",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:fue|quedo|qued[oó]|estuvo)\s+(.+?)\s+primero\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bgan[oó]\s+(.+?)(?=\s*$|\s+en\b|\s+con\b|\s+para\b)",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:solo|siempre)\s+(?:gana|sale|qued[oó]|fue|queda)\s+(.+?)(?=\s*$|\s+primero\b|\s+en\b)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?:porque|ya\s+que)\s+(.+?)\s+(?:gana|sale|qued[oó]|fue)\s+primero",
                re.IGNORECASE,
            ),
        ]

        def _extract_candidate_expr(text: str) -> str:
            for _pat in _CAND_PATTERNS_SHARED:
                _m = _pat.search(text)
                if _m:
                    return _m.group(1).strip()
            return ""

        _has_mesa_kw = "mesa" in q_norm
        # Support both "900K" shorthand and plain digit ranges
        _prefix_m = re.search(r"\b(\d{3,6})\b", q) or re.search(r"\b(\d{3,4})\s*[kK]\b", q)
        _has_prefix_num = bool(_prefix_m)

        # ── Intent: verificar existencia de mesas (responder a "mesas fantasma") ──
        _EXISTENCE_DENY_WORDS = {
            "fantasma", "fantasm", "inventad", "no existen", "no hay", "falsa",
            "falso", "dudosa", "ghost", "no son reales", "no son real",
        }
        _DESCRIBE_MESA_WORDS = {
            "que son las", "que hay en", "donde estan", "cuantas hay", "cuantas son",
            "cuantas existen", "son reales", "existen realmente",
            "existen de verdad", "cuantas mesas", "informacion sobre",
            "que lugar", "en que lugar", "que mesas",
        }
        _has_existence_deny = any(w in q_norm for w in _EXISTENCE_DENY_WORDS)
        _has_describe_mesa = any(w in q_norm for w in _DESCRIBE_MESA_WORDS)
        # "existen" / "existen las mesas" / "las mesas XK existen" como standalone
        if not _has_describe_mesa and not _has_existence_deny:
            if re.search(r"\bexist[ei]\w*\b", q_norm):
                _has_describe_mesa = True
        # "top X candidatos en mesas NNN[K]" / "top X en mesas NNN" → tambien describe
        if not _has_describe_mesa and not _has_existence_deny:
            if re.search(r"\btop\s+\d+\b", q_norm) and re.search(r"\bmesas?\b", q_norm) and _has_prefix_num:
                _has_describe_mesa = True

        # Excluir: código exacto de 6 dígitos con keyword "mesa" → es mesa directa, no rango
        _prefix_is_full_code = bool(_prefix_m and len(_prefix_m.group(1)) == 6 and _has_mesa_kw)

        if _has_mesa_kw and _has_prefix_num and (_has_existence_deny or _has_describe_mesa) and not (
            "primero" in q_norm or "gano" in q_norm or "gana" in q_norm
        ) and not _prefix_is_full_code:
            mesa_prefix = _prefix_m.group(1)  # type: ignore[union-attr]
            coverage = _build_coverage_block(q_norm, id_eleccion, timeout, prefix=mesa_prefix)
            description = store.describe_mesa_prefix(mesa_prefix)
            total_mesas = int(description.get("total_mesas") or 0)
            locations = description.get("locations") or []
            # Skip expensive candidate query when no local mesas exist for this prefix
            top_candidates = store.get_top_candidates_for_prefix(mesa_prefix, top_n=5) if total_mesas > 0 else []

            context_notes = get_context_notes(q_norm, mesa_prefix)

            if total_mesas == 0:
                answer = (
                    f"No tengo mesas con prefijo '{mesa_prefix}' en mi cache local. "
                    "Para verificar su existencia usa onpe_get_mesas_batch con ese rango — "
                    "las mesas son reales y figuran en el padrón oficial de ONPE."
                )
            else:
                display_suffix = "K" if len(mesa_prefix) <= 3 and mesa_prefix.isdigit() else ""
                label = f"mesas {mesa_prefix}{display_suffix}"
                ve = coverage["votos_emitidos"]
                vv = coverage["votos_validos"]
                eh = int(description.get("total_electores_habiles") or 0)
                eh_min = description.get("electores_min", 0)
                eh_max = description.get("electores_max", 0)
                eh_avg = description.get("electores_avg", 0.0)
                cov_pct = coverage["coverage_pct"]
                verdict = coverage["verdict"]
                departamentos = description.get("departamentos") or []

                lines = [
                    f"## ✅ Las {label} SÍ existen — datos cache local ONPE\n",
                    "| Indicador | Dato |",
                    "|-----------|------|",
                    f"| Total mesas | **{total_mesas:,}** |",
                    f"| Con votos registrados | **{coverage['mesas_con_votos']:,} ({cov_pct}%)** |",
                    f"| Electores habilitados | {eh:,} |",
                    f"| Electores por mesa (min/avg/max) | {eh_min} / {eh_avg:.1f} / {eh_max} |",
                    f"| Votos emitidos | {ve:,} |",
                    f"| Votos válidos | {vv:,} |",
                    f"| Cobertura | {verdict} |",
                    "",
                ]

                if departamentos:
                    lines.append("### 🗺️ Distribución por departamento\n")
                    lines.append("| Departamento | Mesas | Electores | Votos |")
                    lines.append("|--------------|-------|-----------|-------|")
                    for d in departamentos:
                        lines.append(
                            f"| {d['departamento']} | {d['n_mesas']:,} | {d['total_electores_habiles']:,} | {d['total_votos_emitidos']:,} |"
                        )
                    lines.append("")

                if top_candidates:
                    lines.append("### 🗳️ Top candidatos en este segmento\n")
                    for c in top_candidates:
                        lines.append(f"{c['rank']}. **{c['nombre']}**: {c['votos']:,} votos ({c['n_mesas']:,} mesas)")
                    lines.append("")

                if context_notes:
                    lines.append("### 📚 Contexto\n")
                    lines.append(context_notes[0])

                answer = "\n".join(lines)

            data = {
                "intent": "range_existence_verify",
                "answer": answer,
                "result": {**description, "coverage": coverage, "context_notes": context_notes},
                "source": "sqlite" if total_mesas > 0 else "sqlite_empty",
                "data_tier": data_tier_label("sqlite" if total_mesas > 0 else "sqlite_empty"),
            }
            store.append_raw_event(
                "onpe_chat_range_existence_verify",
                {"query": q, "mesa_prefix": mesa_prefix, "total_mesas": total_mesas},
            )
            return ok_response(data, started_ms=started_ms)

        # ── Intent: verificar claim de fraude / exclusividad ("solo X gana en mesas 900K") ──
        _FRAUD_CLAIM_WORDS = {"fraude", "trampa", "manipulacion", "sospechoso", "sospecha", "irregular"}
        _EXCLUSIVITY_WORDS = {"solo", "siempre", "todos", "todas", "unico", "unica"}

        _has_fraud_claim = any(w in q_norm for w in _FRAUD_CLAIM_WORDS)
        _has_exclusivity = any(w in q_norm for w in _EXCLUSIVITY_WORDS) and (
            "primero" in q_norm or "gano" in q_norm or "gana" in q_norm
        )

        if _has_mesa_kw and _has_prefix_num and (_has_fraud_claim or _has_exclusivity):
            mesa_prefix = _prefix_m.group(1)  # type: ignore[union-attr]
            candidate_expr = _extract_candidate_expr(q)

            coverage = _build_coverage_block(q_norm, id_eleccion, timeout, prefix=mesa_prefix)
            ranking_data = store.all_first_places_by_prefix(mesa_prefix)
            total_mesas = int(ranking_data.get("total_mesas") or 0)
            mesas_con_votos = int(ranking_data.get("mesas_con_votos") or 0)
            ranking = ranking_data.get("ranking") or []

            if total_mesas == 0:
                answer = (
                    f"No tengo mesas con prefijo '{mesa_prefix}' en mi cache. "
                    "Usa onpe_get_mesas_batch para hidratarlas y luego repite la consulta."
                )
                data = {
                    "intent": "range_claim_verify",
                    "answer": answer,
                    "result": {"mesa_prefix": mesa_prefix, "is_partial": True, "ranking": []},
                    "source": "sqlite_empty",
                    "data_tier": "tier_3_knowledge_base",
                }
                store.append_raw_event("onpe_chat_range_claim_verify", {"query": q, "mesa_prefix": mesa_prefix})
                return ok_response(data, started_ms=started_ms)

            top5_str = "; ".join(
                f"{r['nombre_partido']} en {r['mesas_primero']} mesas"
                for r in ranking[:5]
            )

            claimed_mesas = 0
            claimed_rank = None
            if candidate_expr:
                candidate_map = store.load_candidate_map(settings.source_dir / "candidato.txt")
                expr_norm = _norm(candidate_expr)
                for idx, item in enumerate(ranking, start=1):
                    pid = item["partido_id"]
                    cand = candidate_map.get(pid, "")
                    if expr_norm and (expr_norm in _norm(cand) or expr_norm in _norm(item["nombre_partido"])):
                        claimed_mesas = item["mesas_primero"]
                        claimed_rank = idx
                        break

            if len(ranking) <= 1 and claimed_rank == 1 and claimed_mesas == mesas_con_votos and mesas_con_votos > 0:
                answer = (
                    f"En mi cache ({mesas_con_votos} mesas con prefijo '{mesa_prefix}'), "
                    f"'{candidate_expr}' sí quedó primero en todas. "
                    "Esto no implica fraude automáticamente — puede reflejar preferencia regional. "
                    f"Hay {total_mesas} mesas totales en ese prefijo."
                )
                is_refuted = False
            elif len(ranking) > 1:
                answer = (
                    f"No: en las {mesas_con_votos} mesas con prefijo '{mesa_prefix}' en mi cache, "
                    f"el primer lugar varía — {top5_str}."
                )
                if candidate_expr:
                    if claimed_mesas > 0:
                        answer += (
                            f" '{candidate_expr}' quedó primero en {claimed_mesas} de {mesas_con_votos} mesas "
                            f"(posición {claimed_rank} del ranking)."
                        )
                    else:
                        answer += f" '{candidate_expr}' no aparece ganando ninguna mesa en ese rango en mi cache."
                is_refuted = True
            else:
                answer = (
                    f"En mi cache ({mesas_con_votos} mesas con prefijo '{mesa_prefix}'): {top5_str}."
                )
                is_refuted = False

            context_notes = get_context_notes(q_norm, mesa_prefix)
            if context_notes:
                answer += " — " + context_notes[0]

            data = {
                "intent": "range_claim_verify",
                "answer": answer,
                "result": {
                    "mesa_prefix": mesa_prefix,
                    "claimed_candidate": candidate_expr,
                    "claimed_mesas_primero": claimed_mesas,
                    "claimed_rank": claimed_rank,
                    "total_mesas": total_mesas,
                    "mesas_con_votos": mesas_con_votos,
                    "ranking": ranking,
                    "is_refuted": is_refuted,
                    "is_partial": mesas_con_votos == 0,
                    "context_notes": context_notes,
                    "coverage": coverage,
                },
                "source": "sqlite",
                "data_tier": "tier_1_local_cache",
            }
            store.append_raw_event(
                "onpe_chat_range_claim_verify",
                {
                    "query": q,
                    "mesa_prefix": mesa_prefix,
                    "candidate": candidate_expr,
                    "is_refuted": is_refuted,
                },
            )
            return ok_response(data, started_ms=started_ms)

        # Intención especial: razonamiento por prefijo de mesas + candidato que quedó primero
        # Trigger: "mesa" + indicador de rango + indicador de desempeño.
        # gano = ganó normalizado (NFD strip).
        _RANGE_INDICATOR_WORDS = {
            "arranc", "empiez", "prefij", "comienz", "comenz", "inicia", "partir",
            "bloque", "grupo", "serie", "rango", "lote",
        }
        _has_mesa = "mesa" in q_norm
        # También detectar rango numérico explícito "X a Y" (ej: "900100 a 900200") o "entre X y Y" o "del X al Y"
        _numeric_range_m = (
            re.search(r"\b(\d{4,6})\s+al?\s+(?:la\s+|el\s+)?\d{4,6}\b", q_norm)
            or re.search(r"\bentre\s+(?:la\s+)?(?:mes[a]+s?\s+)?(\d{4,6})\s+y\s+\d{4,6}\b", q_norm)
            or re.search(r"\bdel?\s+(\d{4,6})\s+al?\s+\d{4,6}\b", q_norm)
            or re.search(r"\bdesde\s+(?:la\s+)?mes[a]+s?\s+(\d{4,6})\s+hasta\s+\d{4,6}\b", q_norm)
            or re.search(r"\bdesde\s+(?:el\s+|la\s+)?(\d{4,6})\s+(?:hasta|al)\s+(?:el\s+|la\s+)?\d{4,6}\b", q_norm)
            or re.search(r"\b(\d{4,6})\s+hasta\s+\d{4,6}\b", q_norm)
            or re.search(r"\b(\d{4,6})-\d{4,6}\b", q_norm)  # hyphen range: 700001-700010
        )
        # Treat queries with explicit numeric range as if they have "mesa" context
        if not _has_mesa and _numeric_range_m and mesa_match:
            _has_mesa = True
        _has_performance = (
            "primero" in q_norm or "primer " in q_norm or "gano" in q_norm
            or "sacaron mas" in q_norm or "quienes sacaron" in q_norm
            or "quien saco mas" in q_norm or "mas votos" in q_norm
            or "obtuvo mas" in q_norm or "quien mas" in q_norm
            or "jalaron mas" in q_norm or "jalo mas" in q_norm
        )
        # "mesas XXXX" en plural con performance → prefijo, no mesa individual
        _has_plural_mesa_prefix = bool(
            re.search(r"\bmesas\s+\d{3,5}\b", q_norm) and _has_performance
        )
        _has_range = (
            any(w in q_norm for w in _RANGE_INDICATOR_WORDS)
            or bool(_numeric_range_m)
            or _has_plural_mesa_prefix
        )
        # Explicit numeric range with "mesas" plural → range_reasoning even without performance word
        _has_explicit_mesa_range = bool(
            ("mesa" in q_norm or "mesas" in q_norm) and _numeric_range_m
        )
        if _has_mesa and _has_range and (_has_performance or _has_explicit_mesa_range):
            mesa_prefix = extract_mesa_prefix_claim(q)
            if not mesa_prefix:
                data = {
                    "intent": "range_reasoning",
                    "answer": (
                        "Para analizar por rango de mesas necesito el prefijo numérico. "
                        "¿Cuál es? Ejemplo: '900000', '9001' o '900K'."
                    ),
                    "result": None,
                    "source": "clarification_needed",
                }
                return ok_response(data, started_ms=started_ms)

            # Extraer nombre del candidato con patrones en orden de prioridad.
            # 1. "fue/ganó primero NOMBRE"  (ej: "ganó primero López Aliaga")
            # 2. "fue NOMBRE primero"  (ej: "fue López Aliaga primero")
            # 3. "ganó NOMBRE"          (ej: "ganó López Aliaga")
            candidate_expr = ""
            _cand_patterns = [
                re.compile(
                    r"\b(?:fue|quedo|qued[oó]|estuvo|gan[oó])\s+primero\s+(.+?)(?=\s*$|\s+en\b|\s+con\b|\s+para\b|\s+sobre\b)",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\b(?:fue|quedo|qued[oó]|estuvo|gan[oó])\s+(.+?)\s+primero\b",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"\bgan[oó]\s+(.+?)(?=\s*$|\s+en\b|\s+con\b|\s+para\b)",
                    re.IGNORECASE,
                ),
            ]
            for pat in _cand_patterns:
                m = pat.search(q)
                if m:
                    candidate_expr = m.group(1).strip()
                    break

            if not candidate_expr:
                data = {
                    "intent": "range_reasoning",
                    "answer": (
                        f"Encontré el prefijo de mesa '{mesa_prefix}' pero no identifiqué el candidato. "
                        "¿A quién te refieres? Ejemplo: 'fue primero López Aliaga'."
                    ),
                    "result": {"mesa_prefix": mesa_prefix},
                    "source": "clarification_needed",
                }
                return ok_response(data, started_ms=started_ms)

            candidate_map = store.load_candidate_map(settings.source_dir / "candidato.txt")
            aggregates = store.aggregate_votes_by_party()
            expr_norm = _norm(candidate_expr)

            matched_partidos: set[str] = set()
            for item in aggregates:
                partido_id = str(item.get("partido_id") or "")
                if not partido_id:
                    continue
                candidato = candidate_map.get(partido_id, "")
                partido = str(item.get("nombre_partido") or "")
                if expr_norm and (expr_norm in _norm(candidato) or expr_norm in _norm(partido)):
                    matched_partidos.add(partido_id)

            if not matched_partidos:
                data = {
                    "intent": "range_reasoning",
                    "answer": (
                        f"No encontré a '{candidate_expr}' en los candidatos/partidos con votos en SQLite. "
                        "Verifica el nombre o hidrata el cache con onpe_get_mesas_batch primero."
                    ),
                    "result": {"mesa_prefix": mesa_prefix, "candidate": candidate_expr},
                    "source": "sqlite",
                }
                return ok_response(data, started_ms=started_ms)

            analysis = store.candidate_first_places_by_mesa_prefix(
                mesa_prefix=mesa_prefix,
                partido_ids=matched_partidos,
                top_n=top_n,
            )

            hydrated = _hydrate_missing_city_department_by_prefix(mesa_prefix, id_eleccion)
            if hydrated > 0:
                analysis = store.candidate_first_places_by_mesa_prefix(
                    mesa_prefix=mesa_prefix,
                    partido_ids=matched_partidos,
                    top_n=top_n,
                )

            lugares = analysis.get("lugares") or []
            total_mesas_prefijo = int(analysis.get("total_mesas_prefijo") or 0)
            mesas_con_votos = int(analysis.get("mesas_con_votos") or 0)
            mesas_primero = int(analysis.get("mesas_primero") or 0)
            is_partial = total_mesas_prefijo == 0 or mesas_con_votos == 0

            answer = (
                f"Para el prefijo {mesa_prefix}, '{candidate_expr}' quedó primero en {mesas_primero} mesas "
                f"(sobre {mesas_con_votos} con votos, {total_mesas_prefijo} mesas en total)."
            )
            if is_partial:
                answer += (
                    " Resultado parcial: falta hidratar más mesas en SQLite para ese prefijo."
                )

            data = {
                "intent": "range_reasoning",
                "answer": answer,
                "result": {
                    "mesa_prefix": mesa_prefix,
                    "candidate": candidate_expr,
                    "matched_partido_ids": sorted(matched_partidos),
                    "top_n": top_n,
                    "total_mesas_prefijo": total_mesas_prefijo,
                    "mesas_con_votos": mesas_con_votos,
                    "mesas_primero": mesas_primero,
                    "lugares": lugares,
                    "is_partial": is_partial,
                },
                "source": "sqlite",
            }
            store.append_raw_event(
                "onpe_chat_range_reasoning",
                {
                    "query": q,
                    "mesa_prefix": mesa_prefix,
                    "candidate": candidate_expr,
                    "partidos": sorted(matched_partidos),
                    "mesas_primero": mesas_primero,
                    "ubigeo_location_hydrated": hydrated,
                },
            )
            return ok_response(data, started_ms=started_ms)

        # ── Intent: mesa individual ─────────────────────────────────────────
        # Se verifica ANTES que geo cuando la query contiene la palabra "mesa"
        # explícita, para evitar que "qué pasó en la mesa 900100" sea capturado
        # por el detector de geo ("que" → lugar extranjero).
        _mesa_codes_multi = []
        for _m in re.findall(r"\b\d{6}\b", q_norm):
            if _m not in _mesa_codes_multi:
                _mesa_codes_multi.append(_m)
        if len(_mesa_codes_multi) >= 2 and "mesa" in q_norm:
            items: list[dict[str, Any]] = []
            for _raw in _mesa_codes_multi:
                _code = validate_mesa_code(_raw)
                _payload = store.get_cached_mesa(_code, settings.cache_ttl_seconds)
                _source = "sqlite_cache"
                if _payload is None:
                    _payload = store.get_mesa_from_local(_code)
                    _source = "local_db"
                if _payload is None:
                    if _is_local_only():
                        items.append({"codigo_mesa": _code, "ok": False, "source": "local_only"})
                        continue
                    try:
                        _payload = onpe_api.get_mesa(
                            _code,
                            id_eleccion=max(1, int(id_eleccion)),
                            timeout=max(1, int(timeout)),
                        )
                        store.upsert_mesa_bundle(
                            _code,
                            _payload,
                            source="onpe_live",
                            id_eleccion=max(1, int(id_eleccion)),
                        )
                        _source = "onpe_live"
                    except Exception:
                        items.append({"codigo_mesa": _code, "ok": False, "source": "error"})
                        continue

                _mesa_data = _payload.get("mesa_data") or {}
                _votos = _payload.get("votos") or []
                _top = [
                    v
                    for v in _votos
                    if v.get("votos", 0) > 0
                    and "blanco" not in str(v.get("nombre_partido", "")).lower()
                    and "nulo" not in str(v.get("nombre_partido", "")).lower()
                ][:3]
                _top_str = ", ".join(f"{v.get('nombre_partido','?')} {int(v.get('votos',0))}" for v in _top)
                items.append(
                    {
                        "codigo_mesa": _code,
                        "ok": True,
                        "source": _source,
                        "estado_acta": _mesa_data.get("estado_acta", ""),
                        "electores_habiles": int(_mesa_data.get("electores_habiles", 0) or 0),
                        "votos_emitidos": int(_mesa_data.get("votos_emitidos", 0) or 0),
                        "top_str": _top_str,
                        "result": _payload,
                    }
                )

            _lines = []
            for _it in items:
                if _it.get("ok"):
                    _lines.append(
                        f"Mesa {_it['codigo_mesa']}: {_it.get('estado_acta','')}. "
                        f"{_it.get('votos_emitidos',0)} emitidos de {_it.get('electores_habiles',0)}. "
                        f"Top: {_it.get('top_str','N/D')}."
                    )
                else:
                    _lines.append(f"Mesa {_it['codigo_mesa']}: sin datos (error).")
            return ok_response(
                {
                    "intent": "mesa_batch",
                    "answer": "\n".join(_lines),
                    "result": {"total": len(items), "items": items},
                    "source": "local_db" if all(i.get("source") in {"sqlite_cache", "local_db"} for i in items) else "mixed",
                    "data_tier": "tier_1_local_cache",
                },
                started_ms=started_ms,
            )

        if mesa_match and "mesa" in q_norm:
            code = validate_mesa_code(mesa_match.group(1))

            # Tier 1a: API cache fresco (JSON completo, máx cache_ttl_seconds)
            cached = store.get_cached_mesa(code, settings.cache_ttl_seconds)
            if cached is not None:
                mesa_data = cached.get("mesa_data") or {}
                estado = mesa_data.get("estado_acta", "No disponible")
                votos = cached.get("votos") or []
                top3 = [v for v in votos if v.get("votos", 0) > 0
                        and "blanco" not in str(v.get("nombre_partido","")).lower()
                        and "nulo" not in str(v.get("nombre_partido","")).lower()][:3]
                top3_str = ", ".join(f"{v['nombre_partido']} {v['votos']}" for v in top3)
                data = {
                    "intent": "mesa",
                    "answer": f"Mesa {code} ({mesa_data.get('local_votacion','')}, {estado}). Top candidatos: {top3_str}.",
                    "result": cached,
                    "source": "sqlite_cache",
                    "data_tier": "tier_1_local_cache",
                }
                return ok_response(data, started_ms=started_ms)

            # Tier 1b: DB local hidratada (mesas_data + votos) — sin llamada HTTP
            local_bundle = store.get_mesa_from_local(code)
            if local_bundle is not None:
                mesa_data = local_bundle.get("mesa_data") or {}
                estado = mesa_data.get("estado_acta", "No disponible")
                votos = local_bundle.get("votos") or []
                cand_map = store.load_candidate_map(settings.source_dir / "candidato.txt")
                for v in votos:
                    v["candidato"] = cand_map.get(str(v.get("partido_id", "")), "")
                top3 = [v for v in votos if v.get("votos", 0) > 0
                        and "blanco" not in str(v.get("nombre_partido","")).lower()
                        and "nulo" not in str(v.get("nombre_partido","")).lower()][:3]
                top3_str = ", ".join(
                    f"{v.get('candidato') or v['nombre_partido']} {v['votos']}"
                    for v in top3
                )
                loc = mesa_data.get("local_votacion", "")
                dept = mesa_data.get("departamento", "")
                loc_str = f"{loc}, {dept}" if dept else loc
                store.append_raw_event("onpe_chat_mesa", {"query": q, "codigo_mesa": code, "source": "local_db"})
                data = {
                    "intent": "mesa",
                    "answer": f"Mesa {code} ({loc_str}): {estado}. {mesa_data.get('votos_emitidos',0)} votos emitidos de {mesa_data.get('electores_habiles',0)} electores. Top: {top3_str}.",
                    "result": local_bundle,
                    "source": "local_db",
                    "data_tier": "tier_1_local_cache",
                }
                return ok_response(data, started_ms=started_ms)

            # Tier 1c: código redondo (ej. "900000", "150000") → tratar como bloque/prefijo
            # Las mesas 900000–999999 son el bloque 9xxxxx (arrancando con 9, domésticas).
            # Strippear ceros finales: '900000' → '9', '150000' → '15', '912000' → '912'
            if code.endswith("000"):
                _block_prefix = code.rstrip("0") or code[0]
                _block_desc = store.describe_mesa_prefix(_block_prefix)
                _block_total = int(_block_desc.get("total_mesas") or 0)
                if _block_total > 0:
                    coverage = _build_coverage_block(q_norm, id_eleccion, timeout, prefix=_block_prefix)
                    context_notes = get_context_notes(q_norm, _block_prefix)
                    top_candidates = store.get_top_candidates_for_prefix(_block_prefix, top_n=5)
                    display_label = f"mesas {_block_prefix}K" if _block_prefix.isdigit() else f"mesas {code}"
                    ve = coverage["votos_emitidos"]
                    vv = coverage["votos_validos"]
                    pct = coverage["coverage_pct"]
                    verdict = coverage["verdict"]
                    answer_block = (
                        f"## ✅ Las {display_label} SÍ existen — datos cache local ONPE\n\n"
                        f"| Indicador | Dato |\n|-----------|------|\n"
                        f"| Total mesas | **{_block_total:,}** |\n"
                        f"| Con votos registrados | {coverage.get('mesas_con_votos',0):,} |\n"
                        f"| Cobertura | {pct:.1f}% ({verdict}) |\n"
                        f"| Votos emitidos | {ve:,} |\n"
                        f"| Votos válidos | {vv:,} |\n"
                    )
                    if top_candidates:
                        answer_block += "\n**Top candidatos:**\n"
                        total_tc = sum(int(c.get("total_votos", 0)) for c in top_candidates)
                        for i, c in enumerate(top_candidates[:5], 1):
                            pct_c = int(c.get("total_votos", 0)) / total_tc * 100 if total_tc else 0
                            answer_block += f"{i}. {c.get('nombre_partido', c.get('partido_id', '?'))} — {int(c.get('total_votos', 0)):,} ({pct_c:.1f}%)\n"
                    if context_notes:
                        answer_block += f"\n> {context_notes}"
                    data = {
                        "intent": "range_existence_verify",
                        "answer": answer_block,
                        "result": {
                            "prefix": _block_prefix,
                            "description": _block_desc,
                            "coverage": coverage,
                            "top_candidates": top_candidates,
                        },
                        "source": "sqlite",
                        "data_tier": "tier_1_local_cache",
                    }
                    store.append_raw_event("onpe_chat_mesa_block", {"query": q, "prefix": _block_prefix, "total": _block_total})
                    return ok_response(data, started_ms=started_ms)

            # Tier 2: local-only hard stop
            if _is_local_only():
                return ok_response(
                    {
                        "intent": "mesa",
                        "answer": f"Detecté la mesa **{code}** pero no existe en la base local.",
                        "result": None,
                        "source": "local_only",
                        "data_tier": "tier_1_local_cache",
                    },
                    started_ms=started_ms,
                )
            try:
                mesa = onpe_api.get_mesa(code, id_eleccion=max(1, int(id_eleccion)), timeout=max(1, int(timeout)))
                store.upsert_mesa_bundle(code, mesa, source="onpe_live", id_eleccion=max(1, int(id_eleccion)))
                store.append_raw_event("onpe_chat_mesa", {"query": q, "codigo_mesa": code, "found": bool(mesa.get("found"))})
                estado = (mesa.get("mesa_data") or {}).get("estado_acta", "No disponible")
                data = {
                    "intent": "mesa",
                    "answer": f"Mesa {code}: estado {estado}.",
                    "result": mesa,
                    "source": "onpe_live",
                    "data_tier": "tier_2_onpe_api",
                }
                return ok_response(data, started_ms=started_ms)
            except Exception as _mesa_err:
                return ok_response(
                    {
                        "intent": "mesa",
                        "answer": f"Detecté la mesa **{code}** pero no pude consultar la API en este momento ({type(_mesa_err).__name__}). Intenta de nuevo o usa `onpe_get_mesa('{code}')` directamente.",
                        "result": None,
                        "source": "api_error",
                        "data_tier": "tier_2_onpe_api",
                    },
                    started_ms=started_ms,
                )

        # ── Candidato ANTES de geo Y nacional ───────────────────────────────
        # ORDEN CRÍTICO: candidato primero para que apellidos como Castillo,
        # Urresti, Sánchez no se confundan con distritos RENIEC, y para que
        # "cuántos votos sacó Keiko a nivel nacional" no active el bloque nacional.
        _candidate_from_pattern_early: str | None = None
        if "mesa" not in q_norm:
            for _vp in _CANDIDATE_VOTE_PATTERNS:
                _vm = _vp.search(q)
                if _vm:
                    _cfe_cand = _vm.group(1).strip()
                    # Eliminar artículo/honorífico inicial: "el doctor X" → "X", "el ingeniero X" → "X"
                    _cfe_cand = re.sub(
                        r"^(?:el|la|los|las|un|una)\s+(?:doctor[a]?|dr\.?|ing\.?|ingeniero[a]?|licenciado[a]?|lic\.?|profesor[a]?|prof\.?|señor[a]?|don|doña)\s+",
                        "", _cfe_cand, flags=re.IGNORECASE
                    ).strip()
                    # Si después del artículo no hay honorífico, quitar "el/la/los/las" inicial
                    _cfe_cand = re.sub(r"^(?:el|la|los|las)\s+(?=[a-záéíóúñ])", "", _cfe_cand).strip()
                    # Quitar preposición inicial "a/para" (ej: "a Forsyth", "para Lopez Aliaga")
                    _cfe_cand = re.sub(r"^(?:a|para)\s+(?=[A-Za-záéíóúñÁÉÍÓÚÑ])", "", _cfe_cand).strip()
                    # Quitar "en total [el/la]" al inicio si el patrón lo capturó como prefijo
                    _cfe_cand = re.sub(r"^en\s+total\s+(?:el?\s+|la\s+|los\s+|las\s+)?", "", _cfe_cand, flags=re.IGNORECASE).strip()
                    # Quitar trailing " en total" / " a nivel nacional"
                    _cfe_cand = re.sub(r"\s+en\s+total\s*$|\s+a\s+nivel\s+nacional\s*$", "", _cfe_cand, flags=re.IGNORECASE).strip()
                    _cfe_n = _norm(_cfe_cand)
                    _cfe_w = set(_cfe_n.split())
                    if (
                        _cfe_n not in _NON_CANDIDATE_EXPRESSIONS
                        and not _cfe_n.startswith("en ")
                        and not _cfe_n.startswith("a nivel")
                        and not re.match(r"(?:hacia|desde)\s", _cfe_n)
                        and not re.fullmatch(r"\d+", _cfe_n.strip())  # no son candidatos números puros
                        and not re.fullmatch(r"peru", _cfe_n.strip())  # "Peru" no es candidato
                        and not re.match(r"^peru\b", _cfe_n.strip())    # "Peru en X" tampoco
                        and not re.search(r"\bperu\b", _cfe_n.strip())  # "de Peru en X" tampoco
                        and len(_cfe_n.strip()) >= 3
                        and not (_cfe_w & _NON_CANDIDATE_EXPRESSIONS)
                        # Guard: captura que empieza con verbo → no es candidato
                        and not re.match(r"^(?:obtuvo|tuvo|sac[oó]|logr[oó]|consigui[oó]|recibi[oó]|junto|llev[oó]|gan[oó]|sum[oó]|lleg[oó]|alcanz[oó]|fue|quedo|salio|result[oó])\b", _cfe_n)
                    ):
                        _candidate_from_pattern_early = _cfe_cand
                        break
                    # else: match inválido, continuar al siguiente patrón

        # ── Multi-candidato: "Aliaga y Fujimori cuántos votos" ───────────────
        # Detectar cuando la expresión candidato contiene " y " separando dos candidatos.
        _multi_candidates: list[str] = []
        if _candidate_from_pattern_early and re.search(r"\s+(?:y|e)\s+", _candidate_from_pattern_early, re.IGNORECASE):
            _parts = re.split(r"\s+(?:y|e)\s+", _candidate_from_pattern_early, flags=re.IGNORECASE)
            _multi_candidates = [p.strip() for p in _parts if p.strip()]
        elif _candidate_from_pattern_early and re.search(r"\s+(?:versus|vs\.?|con|comparado\s+con|frente\s+a|contra|respecto\s+a|en\s+comparacion\s+con|a\s+diferencia\s+de)\s+", _candidate_from_pattern_early, re.IGNORECASE):
            _mc_m2 = _MULTI_CANDIDATE_PATTERN.search(q)
            if _mc_m2:
                _mc_groups2 = [g.strip() for g in _mc_m2.groups() if g and g.strip()]
                if len(_mc_groups2) >= 2:
                    _multi_candidates = _mc_groups2[:2]
                    _candidate_from_pattern_early = None
            if not _multi_candidates:
                # Fallback: split by versus/vs/comparado con/frente a/contra/respecto a
                _parts2 = re.split(r"\s+(?:versus|vs\.?|comparado\s+con|frente\s+a|contra|respecto\s+a|en\s+comparacion\s+con)\s+", _candidate_from_pattern_early, flags=re.IGNORECASE)
                if len(_parts2) >= 2:
                    _multi_candidates = [p.strip() for p in _parts2 if p.strip()]
                    _candidate_from_pattern_early = None
        elif not _candidate_from_pattern_early:
            _mc_m = _MULTI_CANDIDATE_PATTERN.search(q)
            if _mc_m:
                _mc_groups = [g.strip() for g in _mc_m.groups() if g and g.strip()]
                if len(_mc_groups) >= 2:
                    _multi_candidates = _mc_groups[:2]
        else:
            # _candidate_from_pattern_early está fijo pero puede haber multi-cand
            # en el query original (e.g. "Keiko cuantos votos y Aliaga cuantos votos",
            # "comparar a X con Y")
            _mc_m_fallback = _MULTI_CANDIDATE_PATTERN.search(q)
            if _mc_m_fallback:
                _mc_gfb = [g.strip() for g in _mc_m_fallback.groups() if g and g.strip()]
                if len(_mc_gfb) >= 2:
                    _multi_candidates = _mc_gfb[:2]
                    _candidate_from_pattern_early = None
        # Strip trailing "en PLACE" and leading stop-words from candidate names
        # e.g. "Keiko en Arequipa" → "Keiko", "votos Nieto" → "Nieto"
        _CAND_LEAD_STRIP = re.compile(r"^(?:votos?\s+|dame\s+|los?\s+votos?\s+(?:de\s+)?)", re.IGNORECASE)
        _multi_candidates = [
            _CAND_LEAD_STRIP.sub("", re.sub(r"\s+en\s+\S.*$", "", c, flags=re.IGNORECASE)).strip()
            for c in _multi_candidates
        ]
        # "Keiko vs Sanchez segunda vuelta" no debe entrar por multi_candidate
        # para mantener el flujo histórico de consultas nacionales/geo.
        if (
            _has_sv_kw
            and (" vs " in f" {q_norm} " or " versus " in q_norm)
            and any(n in q_norm for n in ("keiko", "fujimori"))
            and "sanchez" in q_norm
        ):
            _multi_candidates = []

        # Guard: si ambos candidatos capturados son pronombres interrogativos → es consulta nacional
        _INTERROGATIVE_PRONOUNS = {"quien", "que", "cual", "cuales", "quienes"}
        if _multi_candidates and all(_norm(c.split()[0]) in _INTERROGATIVE_PRONOUNS for c in _multi_candidates):
            _multi_candidates = []

        # Guard: si algún candidato capturado es una expresión no-candidato → no es multi_candidate
        if _multi_candidates and any(_norm(c) in _NON_CANDIDATE_EXPRESSIONS for c in _multi_candidates):
            _multi_candidates = []

        # Guard: si ambos "candidatos" son principalmente numéricos → es rango de votos, no multi_candidate
        # e.g. "candidatos entre 10000 y 50000 votos" → nacional
        if _multi_candidates and all(re.match(r"^\d", c.strip()) for c in _multi_candidates):
            _multi_candidates = []

        # Guard: si ambos candidatos capturados son departamentos/lugares geográficos conocidos
        # "cuantos votos hubo en Arequipa y Moquegua" → geo_domestic, no multi_candidate
        if _multi_candidates and len(_multi_candidates) >= 2:
            _KNOWN_DEPTS_MC = {
                "lima", "arequipa", "callao", "cusco", "cuzco", "piura", "la libertad",
                "junin", "puno", "cajamarca", "lambayeque", "loreto", "ica", "ucayali",
                "ancash", "san martin", "amazonas", "tacna", "moquegua", "huancavelica",
                "apurimac", "tumbes", "madre de dios", "pasco", "huanuco", "ayacucho",
            }
            _mc_both_geo = all(
                _norm(c) in _KNOWN_DEPTS_MC or
                any(_norm(c) in _norm(d) or _norm(d) in _norm(c) for d in _KNOWN_DEPTS_MC)
                for c in _multi_candidates
            )
            if _mc_both_geo:
                _multi_candidates = []  # let geo_domestic handle it

        if _multi_candidates:
            _cand_map_mc = store.load_candidate_map(settings.source_dir / "candidato.txt")
            # Detectar scope geográfico para multi-candidato
            _mc_scope_ubigeos: set[str] | None = None
            _mc_scope_label = ""
            _mc_geo_m = re.search(r"\ben\s+([A-Za-záéíóúÁÉÍÓÚñÑ][A-Za-z\sáéíóúÁÉÍÓÚñÑ]+?)(?:\s+(?:cuantos?|votos?|dame|top|resultados?|quien|que|como)\b|$)", q, re.IGNORECASE)
            if _mc_geo_m:
                _mc_potential = _mc_geo_m.group(1).strip()
                if all(_norm(_mc_potential) not in _norm(c) for c in _multi_candidates):
                    _mc_geo_res = store.find_domestic_ubigeos_by_geo_name(_mc_potential)
                    if _mc_geo_res:
                        _, _mc_ubigeo_list = _mc_geo_res
                        _mc_scope_ubigeos = set(_mc_ubigeo_list) if _mc_ubigeo_list else None
                        _mc_scope_label = f" en {_mc_potential.title()}"
            _aggs_mc = store.aggregate_votes_by_party(ubigeos=_mc_scope_ubigeos)
            _mc_results = []
            for _mc_expr in _multi_candidates:
                _mc_expr_norm = _norm(_mc_expr)
                _mc_pat = re.compile(r'\b' + re.escape(_mc_expr_norm) + r'\b', re.IGNORECASE) if _mc_expr_norm else None
                _mc_match = next(
                    (it for it in _aggs_mc if _mc_pat and (
                        _mc_pat.search(_norm(_cand_map_mc.get(str(it["partido_id"]), "")))
                        or _mc_pat.search(_norm(str(it["nombre_partido"]))))),
                    None,
                )
                if _mc_match:
                    _mc_rank = next((i for i, it in enumerate(_aggs_mc, 1) if str(it["partido_id"]) == str(_mc_match["partido_id"])), None)
                    _mc_cname = _cand_map_mc.get(str(_mc_match["partido_id"]), _mc_match["nombre_partido"])
                    _mc_results.append({
                        "candidato": _mc_cname,
                        "partido_id": str(_mc_match["partido_id"]),
                        "total_votos": int(_mc_match["total_votos"]),
                        "rank": _mc_rank,
                        "found": True,
                    })
                else:
                    _mc_results.append({"candidato": _mc_expr, "found": False, "total_votos": 0})
            _mc_ans_parts = []
            for _mcr in _mc_results:
                if _mcr["found"]:
                    _mc_ans_parts.append(
                        f"**{_mcr['candidato']}**: {int(_mcr['total_votos']):,} votos (posición #{_mcr['rank']})"
                    )
                else:
                    _mc_ans_parts.append(f"**{_mcr['candidato']}**: no encontrado en 2026")
            _mc_scope_str = _mc_scope_label or " a nivel nacional"
            _mc_answer = f"Comparación de votos{_mc_scope_str}:\n" + "\n".join(_mc_ans_parts)
            data = {
                "intent": "multi_candidate",
                "answer": _mc_answer,
                "result": {"candidates": _mc_results, "scope": _mc_scope_label or "nacional"},
                "source": "sqlite",
                "data_tier": "tier_1_local_cache",
            }
            store.append_raw_event("onpe_chat_multi_candidate", {"query": q})
            return ok_response(data, started_ms=started_ms)

        # "candidato" en contexto colectivo ("cada candidato", "todos los candidatos" + nacional) → NO candidate early
        _cand_in_collective = (
            re.search(r"\b(?:cada|todos?\s+(?:los|las)?|cualquier)\s+candidatos?\b", q_norm)
            or any(p in q_norm for p in ("a nivel nacional", "nivel nacional", "todo el peru", "todo peru", "en el peru"))
        )
        if _candidate_from_pattern_early or ("candidato" in q_norm and not _cand_in_collective):
            _cand_map_early = store.load_candidate_map(settings.source_dir / "candidato.txt")

            # Detectar scope geográfico en la query: "en Puno", "en Lima", "en Loreto"
            # Se extrae la parte después de "en" que no forma parte del nombre del candidato.
            _candidate_geo_scope: str | None = None
            _scope_ubigeos: set[str] | None = None
            _scope_label = ""
            if _candidate_from_pattern_early:
                _geo_scope_m = re.search(r"\ben\s+(.+?)$", q, re.IGNORECASE)
                if _geo_scope_m:
                    _potential_scope = _geo_scope_m.group(1).strip()
                    # Solo usar si el scope no forma parte del nombre del candidato
                    if _norm(_potential_scope) not in _norm(_candidate_from_pattern_early):
                        _geo_res_scope = store.find_domestic_ubigeos_by_geo_name(_potential_scope)
                        if _geo_res_scope is not None:
                            _candidate_geo_scope = _potential_scope
                            _, _scope_ubigeo_list = _geo_res_scope
                            _scope_ubigeos = set(_scope_ubigeo_list) if _scope_ubigeo_list else None
                            _scope_label = f" en {_candidate_geo_scope.title()}"

            _aggs_early = store.aggregate_votes_by_party(ubigeos=_scope_ubigeos)
            _expr_early = _norm(_candidate_from_pattern_early or q)
            _match_early = None
            _expr_early_pat = re.compile(r'\b' + re.escape(_expr_early) + r'\b', re.IGNORECASE) if _expr_early else None
            for _item in _aggs_early:
                _pid = str(_item["partido_id"])
                _cname = _cand_map_early.get(_pid, "")
                if _expr_early_pat and (
                    _expr_early_pat.search(_norm(_cname)) or _expr_early_pat.search(_norm(str(_item["nombre_partido"])))
                ):
                    _match_early = {**_item, "candidato": _cname}
                    break

            if _match_early is not None:
                _rank_early = next(
                    (i for i, it in enumerate(_aggs_early, 1) if str(it["partido_id"]) == str(_match_early["partido_id"])),
                    None,
                )
                _ans_early = (
                    f"Candidato {_match_early.get('candidato') or 'sin mapeo'} "
                    f"(partido {_match_early['partido_id']}) tiene {int(_match_early['total_votos']):,} votos "
                    f"y posición {_rank_early}{_scope_label} en el consolidado actual."
                )
                data = {
                    "intent": "candidate",
                    "answer": _ans_early,
                    "result": {
                        **_match_early,
                        "rank": _rank_early,
                        "total_partidos": len(_aggs_early),
                        "scope": _candidate_geo_scope,
                    },
                    "source": "sqlite",
                    "data_tier": "tier_1_local_cache",
                }
                store.append_raw_event("onpe_chat_candidate", {"query": q, "partido_id": _match_early["partido_id"]})
                return ok_response(data, started_ms=started_ms)
            elif _candidate_from_pattern_early:
                # El patrón detectó una consulta de candidato pero no hay match.
                # Antes de devolver "no encontré", verificar que la expresión no sea
                # un lugar geográfico (ej: "resultados de Arequipa" → geo, no candidato).
                # Verificación estricta: solo consideramos geo si el nombre
                # completo coincide exactamente con un departamento, provincia o
                # distrito (sin token fallback), para evitar que "Pedro Castillo"
                # coincida con "José Crespo y Castillo" o "Daniel Urresti" con
                # "Daniel Alcides Carrión".
                _expr_norm_geo = _norm(_candidate_from_pattern_early)
                with store._connect() as _geo_chk_conn:
                    _geo_chk_conn.create_function("norm_py", 1, _norm)
                    _geo_chk = _geo_chk_conn.execute(
                        "SELECT 1 FROM ubigeo_reniec "
                        "WHERE norm_py(departamento)=? OR norm_py(provincia)=? OR norm_py(distrito)=? LIMIT 1",
                        (_expr_norm_geo, _expr_norm_geo, _expr_norm_geo),
                    ).fetchone()
                _expr_is_geo = _geo_chk is not None
                # Fallback estático: check _CITY_ALIASES sin necesitar la DB (funciona en CI/vacío)
                if not _expr_is_geo:
                    _expr_is_geo = any(
                        re.search(r"\b" + re.escape(k) + r"\b", _expr_norm_geo)
                        for k in _STATIC_CITY_ALIASES
                    )
                if not _expr_is_geo:
                    # Antes de responder "no encontrado", verificar si el nombre
                    # coincide con un país/ciudad extranjera → fallthrough a geo.
                    # Omitir la búsqueda para nombres muy cortos (≤4 chars): demasiados falsos positivos
                    # ("RLA" → ORLANDO/IRLANDA, "GV" → cualquier ciudad, etc.)
                    _expr_foreign_chk = (
                        store.find_foreign_ubigeos(_candidate_from_pattern_early)
                        if len(_candidate_from_pattern_early.strip()) > 4
                        else []
                    )
                    if _expr_foreign_chk:
                        pass  # cae a bloques geo abajo
                    else:
                        # Fuzzy match contra candidatos conocidos
                        _known_names = sorted({v for v in _cand_map_early.values() if v})
                        _expr_norm_cand = _norm(_candidate_from_pattern_early or "")
                        _fuzzy = difflib.get_close_matches(
                            _expr_norm_cand,
                            [_norm(n) for n in _known_names],
                            n=3, cutoff=0.5,
                        )
                        # Mapear de vuelta a nombres originales
                        _fuzzy_names = []
                        for _fn in _fuzzy:
                            for _kn in _known_names:
                                if _norm(_kn) == _fn:
                                    _fuzzy_names.append(_kn)
                                    break

                        _known = ", ".join(_known_names[:10])
                        # Buscar sugerencia cultural (ej: "castillo" → Sánchez por sombrero)
                        _cultural_hint: str | None = None
                        _expr_for_alias = _norm(_candidate_from_pattern_early or q)
                        for _alias, _target in _CANDIDATE_CULTURAL_ALIASES.items():
                            if _alias in _expr_for_alias:
                                _hint_item = next(
                                    (it for it in _aggs_early if _target in _norm(_cand_map_early.get(str(it["partido_id"]), ""))),
                                    None,
                                )
                                if _hint_item:
                                    _cultural_hint = _cand_map_early.get(str(_hint_item["partido_id"]))
                                break
                        _hint_text = (
                            f"\n💡 ¿Quizás te refieres a **{_cultural_hint}**? "
                            f"Es el candidato de 2026 también conocido por usar sombrero."
                            if _cultural_hint else ""
                        )
                        if _fuzzy_names and not _cultural_hint:
                            _sugerencias = " / ".join(f"**{n}**" for n in _fuzzy_names)
                            _hint_text = f"\n💡 ¿Quisiste decir {_sugerencias}?"
                        # Fallback cualitativo si no hay datos en DB
                        _qualitative_notes: list[str] = []
                        if not _aggs_early:
                            _qualitative_notes = get_fallback_qualitative(_norm(_candidate_from_pattern_early or q))
                        _answer_parts = [
                            f"No encontré al candidato '{_candidate_from_pattern_early}' en los resultados "
                            f"de las elecciones generales 2026.{_hint_text}",
                        ]
                        if _qualitative_notes:
                            _answer_parts.append(
                                " Información contextual: " + " ".join(_qualitative_notes[:2])
                            )
                        elif _known_names:
                            _answer_parts.append(f" Candidatos disponibles en cache: {_known}…")
                        data = {
                            "intent": "candidate",
                            "answer": "".join(_answer_parts),
                            "result": {
                                "query": _candidate_from_pattern_early,
                                "found": False,
                                "cultural_hint": _cultural_hint,
                                "sugerencias": _fuzzy_names,
                            },
                            "source": "sqlite",
                        }
                        return ok_response(data, started_ms=started_ms)
                # Si es geo (doméstico o extranjero), caemos al bloque geo abajo

        # ── Nacional / "todo el Perú" / "a nivel nacional" ──────────────────
        # Va DESPUÉS del candidato para que "cuántos votos sacó Keiko a nivel
        # nacional" se resuelva como candidato, no como consulta nacional.
        _NATIONAL_PHRASES = {
            "a nivel nacional", "todo el peru", "a nivel del peru",
            "nivel nacional", "todo peru", "en el peru", "resultados nacionales",
            "a nivel de peru", "peru entero", "todo el pais",
            "quien gano las elecciones", "quien fue el ganador",
            "presidente electo", "quien es el presidente",
            "ganador de las elecciones", "ganador de la eleccion",
            "top de candidatos",
            "candidatos con mas votos", "candidatos mas votados",
            "mas votados", "los mas votados",
            "podio electoral", "podio", "lideres electorales",
            "ranking nacional", "ranking en peru",
            "resultados generales", "resultados electorales generales",
            "resultados totales", "resultados finales",
            "resultado de la eleccion",  # nota: "resultados de la eleccion" movida a check dinámico
            "ganadores de", "ganadores en la",
            "total de votos", "total votos", "votos por candidato",
            "en total", "en general", "en conjunto",
            "participacion electoral", "participacion",
            "al pais", "en el pais", "todo el pais", "el pais",
            "todos los partidos", "partidos politicos", "cada partido",
            "resumen de votos", "listado de candidatos", "listado completo",
            "resumen de elecciones", "resumen electoral", "reporte electoral",
            "resumen de resultados", "resumen general",
            # votos especiales — movidos a check dinámico con guard geo
            # "votos en blanco", "votos nulos", "votos viciados", "en blanco", "votos blancos", "votos invalidos"
            # referencias temporales a elecciones — movidas a check dinámico
            # "elecciones 2026", "elecciones 2021", "elecciones del 2026", "elecciones del 2021",
            # "resultados 2026", "resultados 2021",
            # frases adicionales
            "elecciones presidenciales", "eleccion presidencial",
            "resumen de la eleccion", "resumen de las elecciones",
            "presidenciales 2026", "presidenciales 2021",
            "participaron en las elecciones", "participacion en las elecciones",
            "ranking completo", "tabla de resultados", "tabla electoral",
            "tabla de candidatos", "lista completa", "todos los candidatos",
            # regiones naturales (sin geo específico)
            "sierra peruana", "selva peruana", "costa peruana",
            "en la sierra", "en la selva", "en la costa",
            # estado del conteo
            "faltan por contar", "falta por contar", "por contabilizar",
            "estado del conteo", "avance del conteo", "actas procesadas",
            # participación
            "acudieron a votar", "fueron a votar", "participaron en la votacion",
            "cuantos votaron", "quienes votaron",
            # temporales electorales
            "cuando fueron las elecciones", "cuando se realizaron", "fecha de las elecciones",
            # escrutinio
            "escrutinios", "escrutinio", "conteo final", "resultado del escrutinio",
            # margen y liderazgo
            "margen de victoria", "margen de diferencia", "distancia entre candidatos",
            "cuantos peruanos votaron en total", "cuantos peruanos votaron a nivel nacional",
            "peruanos que votaron", "peruanos votaron",
            # porcentaje y ultimo
            "porcentaje final", "ultimo porcentaje", "porcentaje definitivo",
            "ultimos resultados", "ultimas noticias electorales", "resultados definitivos",
            "resultados de anoche", "resultados de hoy",
            # blancos y nulos (sin geo)
            "blancos y nulos", "nulos y blancos", "votos invalidos y blancos",
            # balance / balance electoral
            "balance electoral", "balance de votos", "balance de resultados",
            # primer lugar
            "quien obtuvo el primer lugar", "quien quedo en primer lugar",
            "quien ocupa el primer lugar", "primer lugar nacional",
            # mapa y informe
            "mapa electoral", "informe electoral", "informe de resultados",
            "informe de resultados electorales", "reporte final de resultados",
            # conteo en tiempo real
            "quien esta arriba", "quien va arriba", "quien lidera el conteo",
            "arriba en el conteo", "lidera el conteo", "va ganando",
            "quien salio primero", "quien quedo primero", "primer lugar",
            # más frases nacionales
            "quien le gano a quien", "como quedo la votacion", "votacion nacional",
            "como quedo el conteo", "como quedo el resultado", "como van los resultados",
            "como quedaron las elecciones", "quien encabeza", "encabeza la votacion",
            # Estado del conteo por distrito
            "cuantos distritos", "distritos que votaron", "distritos contaron",
            "cuantos centros de votacion", "cuantas mesas contaron",
            "cuantas mesas se procesaron", "mesas procesadas", "mesas contabilizadas",
            # territorio nacional
            "todo el territorio peruano", "el territorio peruano", "territorio nacional",
            "territorio del peru", "en todo el territorio",
            # extranjero / diaspora — quitados: geo_foreign_summary los maneja
            # (no agregar aquí: "en el exterior", "del exterior", "en el extranjero", "del extranjero", etc.)
            # resumen/informe detallado — cuidado con "resultados electorales Bolivia" etc.
            "resumen de los resultados", "resumen de resultados electorales",
            "resultados del proceso electoral",
            # "resultados electorales" es demasiado greedy; se maneja via condicional
            # disponibilidad de resultados
            "hay resultados", "resultados disponibles", "hay datos disponibles",
            "estan disponibles los resultados", "ya hay resultados",
        }
        _is_national = any(p in q_norm for p in _NATIONAL_PHRASES)
        # Override: si frases genéricas de ranking/participación se activan pero hay geo específico
        # → dejar que la ruta geo tome el control
        _NATIONAL_GEO_OVERRIDE_PHRASES = {
            "mas votados", "los mas votados", "votados", "el mas votado",
            # "candidatos con mas votos en X" → geo, no nacional
            "candidatos con mas votos", "candidatos mas votados",
            # "top de candidatos en X" → geo
            "top de candidatos",
            "peruanos votaron", "peruanos que votaron", "quienes votaron", "cuantos votaron",
            "acudieron a votar", "fueron a votar", "participaron en la votacion",
            "quien encabeza", "quien va arriba", "quien lidera el conteo",
            "quien esta arriba", "quien salio primero", "quien quedo primero",
            "va ganando", "lidera", "va arriba",
            "hay resultados", "ya hay resultados", "resultados disponibles",
            # "como quedo el conteo/resultado/votacion en X" → geo
            "como quedo el conteo", "como quedo la votacion", "como quedo el resultado",
            "como van los resultados",
            # "participacion en X" → geo (participación en una región específica)
            "participacion", "participacion electoral",
            "participacion en las elecciones",
            # votos especiales + geo → geo
            "blancos y nulos", "nulos y blancos", "votos invalidos y blancos",
            "votos blancos", "votos nulos", "votos viciados", "votos invalidos",
            # avance/resultados + geo → geo
            "avance del conteo", "avance del escrutinio",
            "escrutinio", "escrutinios", "conteo final", "resultado del escrutinio",
            "resultados finales", "resultados totales", "resultados definitivos",
            "resultados parciales", "resultados oficiales", "resultados actualizados",
        }
        if _is_national and re.search(
            r"\b(?:en|de|para)\s+(?:(?:el|la|los|las)\s+)?(?!(?:el|la|los|las|un|una"
            r"|eleccion|elecciones|electoral|candidato|candidatos|voto|votos|resultado|resultados"
            r"|total|totales|general|generales|primera|segunda|vuelta|mesas?|escrutinio)\b)"
            r"[A-Za-záéíóúñÁÉÍÓÚÑ]{3,}",
            q_norm,
        ):
            # Si la única frase nacional activa es una de tipo genérico/ranking → ceder a geo
            _active_phrases = [p for p in _NATIONAL_PHRASES if p in q_norm]
            if all(p in _NATIONAL_GEO_OVERRIDE_PHRASES for p in _active_phrases):
                _is_national = False
        # Departamentos peruanos conocidos — para detectar geo sin preposición ("elecciones 2026 Arequipa")
        _PERU_DEPTS = {
            "lima", "arequipa", "callao", "cusco", "cuzco", "piura", "la libertad",
            "junin", "puno", "cajamarca", "lambayeque", "loreto", "ica", "ucayali",
            "ancash", "san martin", "amazonas", "tacna", "moquegua", "huancavelica",
            "apurimac", "tumbes", "madre de dios", "pasco", "huanuco", "ayacucho",
        }
        # Solo activar _bare_dept si hay contexto electoral (año/resultados/votos) pero NO "candidato"
        _bare_dept_in_q = (
            any(re.search(r"\b" + re.escape(d) + r"\b", q_norm) for d in _PERU_DEPTS)
            and re.search(r"\b(?:resultados?|elecciones?|votos?|\d{4})\b", q_norm)
            and "candidato" not in q_norm
        )
        # Guard: "en/de" (+ artículo opcional) seguido de un nombre real → hay contexto geo
        # Se excluyen palabras del dominio electoral que nunca son lugares.
        _GEO_IN_Q = re.search(
            r"\b(?:en|de|para)\s+(?:(?:el|la|los|las)\s+)?(?!\d)"
            r"(?!(?:el|la|los|las|un|una|unos|unas"
            r"|este|esta|esto|estos|estas|ese|esa|eso|esos|esas|aquel|aqui|ahi|alla"
            r"|todos?|todas?|cada|alguno?|ninguno?|cualquier|la\s+eleccion|candidatos?"
            r"|votos?|voto|sufragios?|votaci[oó]n|votaciones?|porcentaje|participaci[oó]n|datos?|resultado|resultados|informacion|info"
            r"|blanco|nulos?|viciados?|blancos|invalidos?|total|totales|general|generales"
            r"|norte|sur|este|oeste|centro|oriente|occidente|sierra|selva|costa"
            r"|primera|segunda|tercera|primera|primer|segundo|tercer|tercero|cuarta|quinto"
            r"|vuelta|turno|ronda|siguiente|anterior"
            r"|eleccion|elecciones|elecci[oó]n|electoral|electorales"
            r"|dolar|euro|sol|libra|precio|costo|cambio|tipo)\b)\w{3,}",
            q_norm
        ) or _bare_dept_in_q
        if not _is_national and re.search(r"\b(top\s*\d*|\d+\s+primeros?|primeros?\s+\d+)\b", q_norm) and not _GEO_IN_Q and (
            "nacional" in q_norm or "pais" in q_norm or re.search(r"\bperu\b", q_norm)
            or ("candidatos" in q_norm)
        ):
            _is_national = True
        if not _is_national and re.search(r"\bm[aá]s\s+votos\b", q_norm) and "candidatos" in q_norm and not _GEO_IN_Q:
            _is_national = True
        # "dame el top 5" / "top 3" sin contexto geográfico → nacional
        # (pero no si hay un departamento en la consulta, ej: "top 3 Ica")
        if not _is_national and re.search(r"\btop\s+\d+\b", q_norm) and not _GEO_IN_Q:
            _is_national = True
        # "todos/todas" + (candidatos|resultados|votos|regiones) sin geo específico → nacional
        if not _is_national and ("todos" in q_norm or "todas" in q_norm) and not _GEO_IN_Q:
            if "candidatos" in q_norm or "resultados" in q_norm or "votos" in q_norm or "regiones" in q_norm or "provincias" in q_norm or "pais" in q_norm:
                _is_national = True
        # Check simple: ¿algún departamento peruano conocido en la consulta?
        _dept_name_in_q = any(re.search(r"\b" + re.escape(d) + r"\b", q_norm) for d in _PERU_DEPTS)
        # Si _is_national fue activado por "top N" pero hay un dept en la consulta → ceder a geo
        if _is_national and _dept_name_in_q and not any(p in q_norm for p in _NATIONAL_PHRASES):
            _is_national = False
        # "candidatos/candidato" sin geo → nacional (ej: "cuántos candidatos se presentaron")
        if not _is_national and re.search(r"\bcandidatos?\b", q_norm) and not _GEO_IN_Q and not _dept_name_in_q:
            _is_national = True
        # "resultados de la eleccion/elecciones" sin geo específico → nacional
        if not _is_national and re.search(r"\bresultados?\s+de\s+(?:la[s]?\s+)?elecci[oó]nes?\b", q_norm) and not _GEO_IN_Q:
            _is_national = True
        # "primera vuelta" / "segunda vuelta" sin geo explícita → nacional
        if not _is_national and re.search(r"\b(?:primera|segunda)\s+vuelta\b", q_norm) and not _GEO_IN_Q:
            _is_national = True
        # "entre X y Y votos" → consulta de rango → nacional
        if not _is_national and re.search(r"\bentre\s+\d+\s+y\s+\d+\s+votos?\b", q_norm) and not _GEO_IN_Q:
            _is_national = True
        # "quienes tienen/tienen" + "votos" → nacional
        if not _is_national and re.search(r"\bquienes?\s+(?:tienen|tienen|llevan|acumulan)\b", q_norm) and "votos" in q_norm and not _GEO_IN_Q:
            _is_national = True
        # "resultados de/del/en AÑO" / "elecciones AÑO" → nacional (año de elecciones sin lugar)
        if not _is_national and re.search(r"\b(?:resultados?|elecciones?)\s+(?:de[l]?\s+)?\d{4}\b", q_norm) and not _GEO_IN_Q:
            _is_national = True
        # "votos en blanco/nulos/viciados" sin geo explícito → nacional
        if not _is_national and re.search(r"\bvotos?\s+(?:en\s+)?(?:blanco|nulos?|viciados?|blancos|inv[aá]lidos?)\b", q_norm) and not _GEO_IN_Q:
            _is_national = True
        # "cada/todos los candidato(s)" → consulta colectiva → nacional
        if not _is_national and re.search(r"\b(?:cada|todos?\s+(?:los|las)?)\s+candidatos?\b", q_norm) and not _GEO_IN_Q:
            _is_national = True
        # "distribución de votos" → nacional
        if not _is_national and re.search(r"\bdistribuci[oó]n\s+de\s+votos?\b", q_norm) and not _GEO_IN_Q:
            _is_national = True
        # "porcentaje (final) de votos" sin geo → nacional
        if not _is_national and re.search(r"\bporcentaje\s+(?:\w+\s+)?de\s+votos?\b", q_norm) and not _GEO_IN_Q:
            _is_national = True
        # "quien salió en primer/segundo lugar" → ranking nacional sin geo
        if not _is_national and re.search(r"\b(?:quien|quienes?)\s+(?:sali[oó]|qued[oó]|result[oó])\s+en\s+(?:primer|segundo|tercer|cuarto|quinto)\b", q_norm) and not _GEO_IN_Q:
            _is_national = True
        # "que paso en las elecciones" / "que ocurrio en las elecciones" → nacional (solo si no hay geo específico)
        if not _is_national and re.search(r"\b(?:qu[eé]|como)\s+(?:pas[oó]|ocurri[oó]|result[oó]|fue)\s+en\s+(?:las?\s+)?elecci[oó]nes?\b", q_norm) and not _dept_name_in_q:
            _is_national = True
        # "quienes ganaron/superaron/consiguieron" sin geo → nacional; con "en PLACE" → geo_domestic
        if not _is_national and re.search(r"\bquienes?\s+(?:son\s+(?:los\s+)?)?(?:gan[ao]ron?|lider(?:es)?|superaron|consiguieron|obtuvieron|tuvieron)\b", q_norm):
            if not _GEO_IN_Q:
                _is_national = True
        # "resultados electorales" sin geo específico → nacional
        if not _is_national and re.search(r"\bresultados?\s+electorales?\b", q_norm) and not _GEO_IN_Q:
            _is_national = True
        # "informacion/datos/noticias de elecciones" → nacional
        if not _is_national and re.search(r"\b(?:elecciones?|electoral(?:es)?)\b", q_norm) and not _GEO_IN_Q and not _dept_name_in_q and not re.search(r"\b20(?:21|22|23|24|25)\b", q_norm):
            _is_national = True
        # bare standalone electoral keywords → nacional
        if not _is_national and q_norm.strip() in {"resultados", "resultado", "quien gano", "quien gan", "votos", "voto", "candidatos", "ganador", "ganadora", "ganadores", "eleccion", "primera vuelta", "segunda vuelta", "2026"}:
            _is_national = True
        # "quienes participaron" / "quien quedo N" / "cual fue el resultado" → nacional
        if not _is_national and not _GEO_IN_Q and not _dept_name_in_q:
            if re.search(r"\b(?:participaron|concurrieron|compitieron|se\s+presentaron)\b", q_norm):
                _is_national = True
            elif re.search(r"\bquien(?:es?)?\s+qued[oó](?:\s+en)?\s+(?:segundo|tercero|cuarto|quinto|primer|primero|último|ultimo)\b", q_norm):
                _is_national = True
            elif re.search(r"\bcual\s+(?:fue|es)\s+(?:el\s+)?resultado\b", q_norm):
                _is_national = True
            elif re.search(r"\bquienes?\s+(?:quedaron|terminaron|acabaron)\b", q_norm):
                _is_national = True
        # "quienes quedaron en el top N" — _GEO_IN_Q fires on "en el top" so handle separately
        if not _is_national and re.search(r"\bquienes?\s+(?:quedaron?|terminaron|acabaron|lleg[ao]ron)\b", q_norm) and not _dept_name_in_q:
            _is_national = True
        # "quien gano la presidencia/eleccion/votacion" → nacional
        if not _is_national and re.search(r"\bquien\s+(?:gan[oó]|obtuvo|logr[oó])\s+(?:la\s+)?(?:presidencia|eleccion|elecciones|votacion|votaciones)\b", q_norm) and not _GEO_IN_Q and not _dept_name_in_q:
            _is_national = True
        # "cual es el ranking (actual/general)" → nacional
        if not _is_national and re.search(r"\bcual\s+(?:es|fue)\s+(?:el\s+)?ranking\b", q_norm) and not _GEO_IN_Q:
            _is_national = True
        # "cuantas mesas se han contado/procesado" → nacional
        if not _is_national and re.search(r"\bcu[aá]ntas?\s+mesas?\s+(?:se\s+han?\s+|han?\s+sido\s+)?(?:contado|procesado|contabilizado|acumulado|reportado)\b", q_norm) and not _GEO_IN_Q:
            _is_national = True
        # "quien encabezo/lidera/va adelante la votacion" → nacional
        if not _is_national and re.search(r"\bquien\s+(?:encabez[oó]|encabeza|encabezaba|lidera|lideraba|iba\s+adelante|va\s+adelante|estaba\s+primero)\b", q_norm) and not _GEO_IN_Q:
            _is_national = True
        # "como va el recuento/conteo/avance" → nacional
        if not _is_national and re.search(r"\bcomo\s+va\s+(?:el\s+)?(?:recuento|conteo|avance|escrutinio|proceso)\b", q_norm) and not _GEO_IN_Q:
            _is_national = True
        # "avance de votos/resultados" / "votos acumulados" / "resultados preliminares" → nacional
        if not _is_national and re.search(r"\b(?:avance\s+(?:de\s+)?(?:votos?|resultados?)|votos?\s+acumulados?|resultados?\s+(?:preliminares?|acumulados?|en\s+tiempo\s+real)|recuento\s+(?:de\s+)?votos?)\b", q_norm) and not _GEO_IN_Q:
            _is_national = True
        # "estado (actual/del) conteo/recuento/elecciones" → nacional
        if not _is_national and re.search(r"\bestado\s+(?:actual\s+)?(?:del?\s+)?(?:conteo|recuento|escrutinio|elecciones?|proceso\s+electoral)\b", q_norm):
            _is_national = True
        # "como van los votos/candidatos" → nacional
        if not _is_national and re.search(r"\bcomo\s+van\s+(?:los\s+)?(?:votos?|candidatos?|elecciones?|resultados?|las\s+elecciones?)\b", q_norm) and not _GEO_IN_Q:
            _is_national = True
        # "cuantos viciados/blancos/nulos/invalidos" → nacional
        if not _is_national and re.search(r"\bcu[aá]ntos?\s+(?:votos?\s+)?(?:viciados?|blancos?|nulos?|invalidos?|impugnados?|observados?)\b", q_norm) and not _GEO_IN_Q and not _dept_name_in_q:
            _is_national = True
        # "cuantos electores/ciudadanos/personas/gente votaron" → nacional
        if not _is_national and re.search(r"\bcu[aá]ntos?\s+(?:electores?|ciudadanos?|personas?|peruanos?|gente)\s+(?:votaron?|sufragaron?|ejercieron|participaron|acudieron|fueron\s+a\s+votar|asistieron)\b", q_norm) and not _GEO_IN_Q and not _dept_name_in_q:
            _is_national = True
        # "cuantos votos saco/obtuvo el ganador/lider/presidente" → nacional
        if not _is_national and re.search(r"\b(?:el\s+)?(?:ganador|lider|vencedor|presidente\s+electo)\b", q_norm) and re.search(r"\b(?:votos?|sac[oó]|obtuvo|logr[oó]|consigui[oó]|tuvo|alcanz[oó])\b", q_norm) and not _GEO_IN_Q and not _dept_name_in_q:
            _is_national = True
        # "cuantos votos validos/en total hubo" → nacional
        if not _is_national and re.search(r"\bcu[aá]ntos?\s+votos?\s+(?:totales?|en\s+total|emitidos?|computados?|v[aá]lidos?|hubo|hay|fueron)\b", q_norm) and not _GEO_IN_Q and not _dept_name_in_q:
            _is_national = True
        # "total de mesas escrutadas/procesadas" → nacional (sin chequeo de geo: "de mesas" activa _GEO_IN_Q)
        if not _is_national and re.search(r"\b(?:total\s+de\s+mesas?|mesas?\s+escrutadas?|mesas?\s+procesadas?|porcentaje\s+de\s+mesas?)\b", q_norm):
            _is_national = True
        # "porcentaje de escrutinio/mesas contadas/conteo" → nacional (sin chequeo geo: mesas está en exclusión _GEO_IN_Q)
        if not _is_national and re.search(r"\bporcentaje\s+de\s+(?:escrutinio|mesas?|conteo)\b", q_norm):
            _is_national = True
        # "porcentaje de participacion/votos validos" → nacional solo si no hay geo específico
        if not _is_national and re.search(r"\bporcentaje\s+de\s+(?:participaci[oó]n|votos?\s+(?:v[aá]lidos?|blancos?|nulos?))\b", q_norm) and not _GEO_IN_Q and not _dept_name_in_q:
            _is_national = True
        # "tercer/segundo/cuarto candidato mas votado" → nacional
        if not _is_national and re.search(r"\b(?:tercer|segundo|primer|cuarto|quinto)\s+candidato\s+(?:mas\s+)?(?:votado|en\s+votos)\b", q_norm):
            _is_national = True
        # "el mas votado" / "segundo/tercer mas votado" / "quien resulto mas votado" → nacional (si no hay geo)
        if not _is_national and re.search(r"\b(?:el\s+mas\s+votado|(?:segundo|tercer|cuarto|quinto|primer)\s+mas\s+votado|quien\s+resulto\s+(?:mas\s+)?votado)\b", q_norm) and not _GEO_IN_Q and not _dept_name_in_q:
            _is_national = True
        # "top N en Peru" / "resultados en Peru" (país entero sin dept específico) → nacional
        if not _is_national and re.search(r"\b(?:en|del?)\s+peru\b", q_norm) and not any(re.search(r"\b" + re.escape(d) + r"\b", q_norm) for d in _PERU_DEPTS):
            _is_national = True
        # "resultados de la votacion/votaciones" sin geo → nacional
        if not _is_national and re.search(r"\bresultados?\s+de\s+(?:la[s]?\s+)?votaci[oó]n(?:es)?\b", q_norm) and not _dept_name_in_q:
            _is_national = True
        # "sufragios validos/totales/emitidos" sin geo → nacional
        if not _is_national and re.search(r"\bsufragios?\s+(?:v[aá]lidos?|totales?|emitidos?|v[aá]lidos?|blancos?|nulos?|viciados?|invalidos?|computados?)\b", q_norm) and not _GEO_IN_Q and not _dept_name_in_q:
            _is_national = True
        # Override: si hay un país extranjero conocido en la consulta (sin preposición) → no es nacional
        _FOREIGN_COUNTRY_NAMES = frozenset({
            "bolivia", "argentina", "chile", "colombia", "ecuador", "brasil", "mexico",
            "eeuu", "usa", "canada", "espana", "italia", "alemania", "francia", "japon",
            "china", "reino unido", "australia", "nueva zelanda", "venezuela", "paraguay",
            "uruguay", "panama", "costa rica", "cuba", "haiti", "suiza", "portugal",
            "belgica", "holanda", "suecia", "noruega", "finlandia", "dinamarca", "rusia",
            "ucrania", "india", "corea", "tailandia", "vietnam", "indonesia", "singapur",
        })
        if _is_national and any(re.search(r"\b" + c + r"\b", q_norm) for c in _FOREIGN_COUNTRY_NAMES):
            _is_national = False

        if _is_national:
            _nat_aggs = store.aggregate_votes_by_party()
            _nat_top = _nat_aggs[:top_n]
            _nat_total = sum(int(t.get("total_votos", 0)) for t in _nat_aggs)
            _cmap_nat = store.load_candidate_map(settings.source_dir / "candidato.txt")
            with store._connect() as _nc:
                _nat_row = _nc.execute("SELECT COUNT(*) AS c FROM mesas_data").fetchone()
                _nat_mesas = int(_nat_row["c"] if _nat_row else 0)
            if _nat_top and _nat_total > 0:
                _nat_lines = [f"**Top {min(top_n, len(_nat_top))} a nivel nacional** ({_nat_mesas:,} mesas · {_nat_total:,} votos)\n"]
                for _ni, _nt in enumerate(_nat_top, 1):
                    _pct = int(_nt["total_votos"]) / _nat_total * 100
                    _nname = _cmap_nat.get(str(_nt.get("partido_id", ""))) or _nt["nombre_partido"]
                    _nat_lines.append(f"{_ni}. **{_nname}** — {int(_nt['total_votos']):,} votos ({_pct:.1f}%)")
                _nat_ans = "\n".join(_nat_lines)
            else:
                _nat_ans = "No hay votos consolidados en el cache local todavía."
            data = {
                "intent": "nacional",
                "answer": _nat_ans,
                "result": {"scope": "nacional", "top": _nat_top, "total_votos": _nat_total, "mesas": _nat_mesas},
                "source": "sqlite",
                "data_tier": "tier_1_local_cache",
            }
            store.append_raw_event("onpe_chat_nacional", {"query": q})
            return ok_response(data, started_ms=started_ms)

        # ── Geo doméstica (departamento/provincia/distrito peruano) ─────────
        # Antes de consultar RENIEC, verificamos si algún token del query
        # corresponde exactamente a un país en foreign_catalog. Si sí,
        # saltamos geo_domestic para evitar falsos positivos como
        # "Chile" → "Chilete", "Canadá" → "Encañada".
        _STOPWORDS_GEO = {"top", "en", "de", "los", "las", "que", "fue", "son", "hay"}
        _q_tokens_geo = [t for t in q_norm.split() if len(t) >= 4 and t not in _STOPWORDS_GEO]
        _has_foreign_country = False
        if _q_tokens_geo:
            with store._connect() as _gc:
                # Incluye países Y ciudades para detectar "Buenos Aires", "Miami", etc.
                _fc_geos: set[str] = set()
                for _r in _gc.execute("SELECT DISTINCT pais FROM foreign_catalog WHERE pais != ''").fetchall():
                    _fc_geos.add(_norm(_r["pais"]))
                for _r in _gc.execute("SELECT DISTINCT ciudad FROM foreign_catalog WHERE ciudad != ''").fetchall():
                    _fc_geos.add(_norm(_r["ciudad"]))
            # Agrega prefijos de nombres multi-palabra: "estados unidos de america" → "estados unidos"
            _fc_geos_ext = set(_fc_geos)
            for _fg in _fc_geos:
                _fg_parts = _fg.split()
                for _k in range(2, len(_fg_parts)):
                    _fc_geos_ext.add(" ".join(_fg_parts[:_k]))
            # Coincidencia exacta de token: "chile", "suecia", "miami", etc.
            for _tok in _q_tokens_geo:
                if _tok in _fc_geos_ext:
                    _has_foreign_country = True
                    break
            # Coincidencia por frase multi-token: "estados unidos", "buenos aires"
            # Requiere que la frase NO sea prefijo de un nombre doméstico más largo,
            # ej: "san juan" NO debe coincidir en "san juan de lurigancho".
            if not _has_foreign_country:
                _JOINERS = {"de", "del", "la", "el", "los", "las", "y", "e", "o"}
                for _fp in sorted(_fc_geos_ext, key=len, reverse=True):
                    if " " in _fp and _fp in q_norm:
                        _fp_end = q_norm.find(_fp) + len(_fp)
                        _after_words = [
                            w for w in q_norm[_fp_end:].split()
                            if w.isalpha() and w not in _JOINERS
                        ]
                        if not _after_words:
                            _has_foreign_country = True
                            break

        # Detectar geo ambigua: coincide con doméstico Y extranjero → pedir aclaración.
        # Solo es genuinamente ambigua si el nombre doméstico aparece textualmente en la
        # consulta (no solo via token fallback). Ej: "Buenos Aires" sí aparece, pero
        # "Chilete" no aparece en "top 5 en Chile" → falso positivo, preferir extranjero.
        _domestic_attempt = _resolve_domestic_geo_query(q)
        if _has_foreign_country and _domestic_attempt is not None:
            _dom_name_amb, _ = _domestic_attempt
            _dom_name_in_query = _norm(_dom_name_amb) in q_norm
            if _dom_name_in_query:
                # Verificar que el nombre extranjero que disparó _has_foreign_country
                # sea el MISMO token que el nombre doméstico (o una variante).
                # Si el token extranjero es diferente (ej: "mendoza" dispara extranjero
                # pero "lima" es el doméstico), el nombre en "en PLACE" ya es claro
                # → preferir doméstico y no pedir aclaración.
                _foreign_tok_match = next(
                    (fp for fp in sorted(_fc_geos_ext, key=len, reverse=True) if fp in q_norm),
                    None,
                )
                _dom_norm_match = _norm(_dom_name_amb)
                # Verdadera ambigüedad: el token extranjero y el nombre doméstico se solapan
                _genuine_ambiguity = (
                    _foreign_tok_match is not None
                    and (
                        _foreign_tok_match == _dom_norm_match
                        or _dom_norm_match.startswith(_foreign_tok_match)
                        or _foreign_tok_match.startswith(_dom_norm_match)
                    )
                )
                if _genuine_ambiguity:
                    _foreign_name_amb = _foreign_tok_match.title() if _foreign_tok_match else "exterior"
                    data = {
                        "intent": "ambiguous",
                        "answer": (
                            f"Tu consulta '{q}' puede referirse a dos lugares:\n"
                            f"  • **{_foreign_name_amb}** — peruanos votando en el exterior\n"
                            f"  • **{_dom_name_amb.title()}** — territorio dentro del Perú\n\n"
                            f"¿A cuál te refieres? Puedes especificar, por ejemplo: "
                            f"'resultados de peruanos en {_foreign_name_amb}' o "
                            f"'resultados en {_dom_name_amb.title()}, Perú'."
                        ),
                        "result": {
                            "options": [
                                {"tipo": "extranjero", "nombre": _foreign_name_amb},
                                {"tipo": "domestico", "nombre": _dom_name_amb.title()},
                            ]
                        },
                        "source": "sqlite",
                    }
                    store.append_raw_event("onpe_chat_ambiguous", {"query": q})
                    return ok_response(data, started_ms=started_ms)
                # Token extranjero diferente al doméstico → resolver como doméstico
                _has_foreign_country = False
            # Falso positivo doméstico — preferir extranjero

        domestic_result = None if _has_foreign_country else _domestic_attempt
        if domestic_result is not None:
            dept_name, ubigeos_dept = domestic_result

            cache_key = _geo_query_cache_key(None, dept_name, top_n)
            cached_geo = store.get_geo_query_cache(cache_key, settings.geo_query_cache_ttl_seconds)
            if cached_geo is not None:
                cached_geo["source"] = "sqlite_query_cache"
                cached_geo["answer"] += " (cache de consulta)"
                return ok_response(cached_geo, started_ms=started_ms)

            aggregates = store.aggregate_votes_by_party(ubigeos_dept if ubigeos_dept else None)
            top = aggregates[:top_n]
            mesas_count = store.count_mesas_by_ubigeos(ubigeos_dept) if ubigeos_dept else 0
            total_votes = sum(int(item.get("total_votos", 0)) for item in aggregates)
            is_partial = mesas_count == 0 or total_votes == 0

            # Respuesta rápida: si no hay datos locales, no intentar hidratación (puede demorar minutos)
            if mesas_count == 0 and total_votes == 0:
                _sugg_alt = [
                    "onpe_health() — para ver estado del cache",
                    "onpe_bootstrap_atu_manera() — para cargar las 92,766 mesas (~2 min)",
                    f"onpe_get_mesa <codigo> — para una mesa específica en {dept_name.title()}",
                ]
                data = {
                    "intent": "geo_domestic",
                    "answer": (
                        f"No tengo datos locales para {dept_name.title()} aún. "
                        f"La base de datos no tiene mesas hidratadas para esta región. "
                        f"Opciones rápidas: {' | '.join(_sugg_alt)}"
                    ),
                    "result": {
                        "query": dept_name,
                        "mesas_match": 0,
                        "total_votos": 0,
                        "is_partial": True,
                        "sugerencias": _sugg_alt,
                    },
                    "source": "sqlite",
                    "data_tier": "tier_3_knowledge_base",
                }
                return ok_response(data, started_ms=started_ms)

            coverage = _build_coverage_block(q_norm, id_eleccion, timeout, ubigeos=ubigeos_dept if ubigeos_dept else None)

            _dept_prefix_result = find_peru_department_prefix(q)
            dept_prefix = _dept_prefix_result[1] if _dept_prefix_result else ""

            # Enriquecer con nombres de candidatos
            cand_map_geo = store.load_candidate_map(settings.source_dir / "candidato.txt")
            valid_top = [
                t for t in top
                if "blanco" not in t.get("nombre_partido","").lower()
                and "nulo" not in t.get("nombre_partido","").lower()
                and "impugnad" not in t.get("nombre_partido","").lower()
            ]
            for t in valid_top:
                t["candidato"] = cand_map_geo.get(str(t.get("partido_id","")), "")

            if valid_top and not is_partial:
                total_validos = sum(int(t.get("total_votos",0)) for t in valid_top)
                lines = [f"**Top {min(top_n, len(valid_top))} en {dept_name.title()}** "
                         f"({mesas_count:,} mesas · {total_votes:,} votos emitidos)\n"]
                for i, t in enumerate(valid_top[:top_n], 1):
                    pct = int(t["total_votos"])/total_validos*100 if total_validos else 0
                    nombre = t.get("candidato") or t["nombre_partido"]
                    lines.append(f"{i}. **{nombre}** — {int(t['total_votos']):,} votos ({pct:.1f}%)")
                answer = "\n".join(lines)
            else:
                answer = (
                    f"Para '{dept_name.title()}' encontré {mesas_count} mesas en el consolidado local. "
                    f"Votos acumulados: {total_votes}."
                )
                if is_partial:
                    answer += (
                        " Resultado parcial: sin votos locales suficientes para este ámbito. "
                        "Usa onpe_get_mesa o onpe_get_mesas_batch para hidratar el cache."
                    )
            data = {
                "intent": "geo_domestic",
                "answer": answer,
                "result": {
                    "query": dept_name,
                    "dept_prefix": dept_prefix,
                    "ubigeos_match": len(ubigeos_dept),
                    "mesas_match": mesas_count,
                    "total_votos": total_votes,
                    "top_n": top_n,
                    "top_partidos": top,
                    "is_partial": is_partial,
                    "coverage": coverage,
                },
                "source": "sqlite",
                "data_tier": data_tier_label("sqlite"),
            }
            store.upsert_geo_query_cache(cache_key, data)
            store.append_raw_event(
                "onpe_chat_geo_domestic",
                {"query": q, "dept_name": dept_name, "dept_prefix": dept_prefix, "mesas": mesas_count},
            )
            return ok_response(data, started_ms=started_ms)

        # ── Geo extranjera (solo si no es doméstica) ────────────────────────
        # Intent "extranjero" genérico: "quién va ganando en extranjero", "resultados en exterior"
        _GENERIC_FOREIGN_WORDS = {"extranjero", "exterior", "mundo", "internacional", "overseas"}
        if any(w in q_norm for w in _GENERIC_FOREIGN_WORDS):
            # Obtener todos los ubigeos del catálogo extranjero
            with store._connect() as _fc_conn:
                _fc_rows = _fc_conn.execute("SELECT DISTINCT ubigeo FROM foreign_catalog").fetchall()
            foreign_ubigeos = {str(r["ubigeo"]) for r in _fc_rows}
            all_foreign = store.aggregate_votes_by_party(ubigeos=foreign_ubigeos if foreign_ubigeos else None)
            top_f = all_foreign[:top_n]
            cand_map_f = store.load_candidate_map(settings.source_dir / "candidato.txt")
            total_f = sum(int(t.get("total_votos", 0)) for t in all_foreign)
            mesas_f = store.count_mesas_by_ubigeos(foreign_ubigeos) if foreign_ubigeos else 0
            if top_f and total_f > 0:
                lines_f = [f"**Top {min(top_n, len(top_f))} en el exterior** ({mesas_f:,} mesas · {total_f:,} votos)\n"]
                for i, t in enumerate(top_f[:top_n], 1):
                    pct = int(t["total_votos"]) / total_f * 100
                    nombre = cand_map_f.get(str(t.get("partido_id", ""))) or t["nombre_partido"]
                    lines_f.append(f"{i}. **{nombre}** — {int(t['total_votos']):,} votos ({pct:.1f}%)")
                answer_f = "\n".join(lines_f)
            else:
                answer_f = (
                    "No hay votos del exterior en el consolidado local todavía. "
                    "Usa onpe_sync_foreign_catalog() para cargar el catálogo de países y ciudades."
                )
            data = {
                "intent": "geo_foreign_summary",
                "answer": answer_f,
                "result": {"top": top_f, "total_votos": total_f, "mesas": mesas_f},
                "source": "sqlite",
            }
            store.append_raw_event("onpe_chat_geo_foreign_summary", {"query": q})
            return ok_response(data, started_ms=started_ms)

        global _foreign_catalog_synced
        geo_resolution = _resolve_foreign_geo_query(q)
        sync_performed = False
        # Auto-sync: solo si la sesión aún no sincronizó y la query tiene candidatos geo.
        # Sincronizar solo UNA vez por proceso para no pagar 700ms en cada query.
        if (
            geo_resolution is None
            and settings.auto_sync_foreign_catalog_on_demand
            and not _is_local_only()
            and not _foreign_catalog_synced
            and extract_foreign_geo_candidates(q)
        ):
            try:
                election_id, rows = onpe_api.build_foreign_catalog(None)
                upserted = store.upsert_foreign_catalog(rows)
                sync_performed = upserted > 0
                _foreign_catalog_synced = True
                store.append_raw_event(
                    "onpe_chat_geo_catalog_autosync",
                    {
                        "query": q,
                        "id_eleccion": election_id,
                        "rows": len(rows),
                        "upserted": upserted,
                    },
                )
                geo_resolution = _resolve_foreign_geo_query(q)
            except Exception:
                logger.exception("Falló auto-sync de catálogo extranjero en onpe_chat")
        elif geo_resolution is None and _foreign_catalog_synced:
            # Ya sincronizamos en esta sesión — intentar de nuevo sin sync
            geo_resolution = _resolve_foreign_geo_query(q)

        if geo_resolution is not None:
            geo_field, geo_expr, catalog = geo_resolution
            ubigeos = {row["ubigeo"] for row in catalog}

            cache_key = _geo_query_cache_key(geo_field, geo_expr, top_n)
            cached_geo = store.get_geo_query_cache(cache_key, settings.geo_query_cache_ttl_seconds)
            if cached_geo is not None:
                cached_geo["source"] = "sqlite_query_cache"
                cached_geo["answer"] += " (cache de consulta)"
                return ok_response(cached_geo, started_ms=started_ms)

            aggregates = store.aggregate_votes_by_party(ubigeos)
            top = aggregates[:top_n]
            mesas_count = store.count_mesas_by_ubigeos(ubigeos)
            total_votes = sum(int(item.get("total_votos", 0)) for item in aggregates)
            is_partial = mesas_count == 0 or total_votes == 0
            source = "sqlite"
            coverage = _build_coverage_block(q_norm, id_eleccion, timeout, ubigeos=ubigeos)

            answer = (
                f"Para '{geo_expr}' encontré {len(ubigeos)} ubicaciones y {mesas_count} mesas en el consolidado local. "
                f"Votos acumulados: {total_votes}."
            )
            if is_partial:
                answer += (
                    " Resultado parcial: no hay votos locales suficientes todavía para este ámbito. "
                    "Consulta mesas ONPE (onpe_get_mesa/onpe_get_mesas_batch) para hidratar cache y acelerar siguientes consultas."
                )
            data = {
                "intent": "geo",
                "answer": answer,
                "result": {
                    "query": geo_expr,
                    "field": geo_field or "any",
                    "ubigeos_match": len(ubigeos),
                    "mesas_match": mesas_count,
                    "total_votos": total_votes,
                    "top_n": top_n,
                    "top_partidos": top,
                    "is_partial": is_partial,
                    "coverage": coverage,
                },
                "source": source,
                "data_tier": data_tier_label(source),
            }
            store.upsert_geo_query_cache(cache_key, data)
            store.append_raw_event("onpe_chat_geo", {"query": q, "ubigeos": len(ubigeos), "mesas": mesas_count})
            return ok_response(data, started_ms=started_ms)

        # ── Stage SV-1: Mesa de segunda vuelta ────────────────────────────
        _SV_KEYWORDS = {"segunda vuelta", "segunda_vuelta", "2da vuelta", "2da_vuelta"}
        _has_sv_kw = any(kw in q_norm for kw in ("segunda vuelta", "segunda_vuelta", "2da vuelta"))
        _has_reasignado_kw = any(kw in q_norm for kw in ("reasign", "local reasignado", "reubicad", "reubican", "huelga", "extorsion", "reconstruccion"))

        # SV: actas observadas / envío al JEE / escenario "todas aceptadas"
        _jee_data = _detect_jee_intent(q, q_norm)
        if _jee_data is not None:
            store.append_raw_event("onpe_chat_sv_estado_actas", {"query": q})
            return ok_response(_jee_data, started_ms=started_ms)

        # SV: reasignados
        if _has_reasignado_kw:
            _sv_dpto = None
            _dept_m = re.search(r"\b(?:en|de|del?)\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñ]{2,30}?)(?:\s*$|\s+(?:por|motivo|debido))", q, re.IGNORECASE)
            if _dept_m:
                _sv_dpto = _dept_m.group(1).strip()
            reasig = store.get_sv_reasignados(dpto=_sv_dpto)
            total_mesas_afectadas = sum(int(r.get("mesas_afectadas", 0)) for r in reasig)
            if reasig:
                lines_r = [f"**{len(reasig)} locales reasignados** para segunda vuelta 2026 ({total_mesas_afectadas} mesas afectadas):\n"]
                for r in reasig[:10]:
                    lines_r.append(f"- {r['nombre_local_original']} → **{r['nombre_local_nuevo']}** ({r['dpto']}, {r['motivo']})")
                if len(reasig) > 10:
                    lines_r.append(f"... y {len(reasig)-10} más.")
                answer_r = "\n".join(lines_r)
            else:
                answer_r = "No hay registros de locales reasignados en la base de datos. Ejecuta onpe_sv_bootstrap() primero."
            data = {"intent": "sv_reasignados", "answer": answer_r, "result": {"total": len(reasig), "locales": reasig[:20]}, "source": "sqlite_sv"}
            store.append_raw_event("onpe_chat_sv_reasignados", {"query": q})
            return ok_response(data, started_ms=started_ms)

        # SV: compare mesa
        if mesa_match and (_has_sv_kw or re.search(r"\bcompar[ae]?\b", q_norm)):
            _sv_code_raw = mesa_match.group(1)
            try:
                _sv_code = validate_mesa_code(_sv_code_raw)
                comparacion = store.get_comparacion_mesa(_sv_code)
                if comparacion["primera_vuelta"] or comparacion["segunda_vuelta"]:
                    _p1 = comparacion.get("primera_vuelta") or {}
                    _p2 = comparacion.get("segunda_vuelta") or {}
                    lines_c = [f"**Mesa {_sv_code} — Comparación 1V vs 2V:**\n"]
                    if _p1:
                        ve1 = _p1.get("votos_emitidos", 0)
                        lines_c.append(f"**Primera vuelta:** {ve1:,} votos emitidos")
                        for v in (_p1.get("votos") or [])[:3]:
                            lines_c.append(f"  • {v['nombre']}: {v['votos']:,}")
                    if _p2:
                        ve2 = _p2.get("votos_emitidos", 0)
                        lines_c.append(f"**Segunda vuelta:** {ve2:,} votos emitidos")
                        for v in (_p2.get("votos") or [])[:3]:
                            lines_c.append(f"  • {v['nombre']}: {v['votos']:,}")
                    data_c = {"intent": "sv_comparacion_mesa", "answer": "\n".join(lines_c), "result": comparacion, "source": "sqlite"}
                    store.append_raw_event("onpe_chat_sv_comparacion_mesa", {"query": q, "codigo_mesa": _sv_code})
                    return ok_response(data_c, started_ms=started_ms)
            except ValueError:
                pass

        # SV: transfer/proyeccion
        _TRANSFER_KW = {"transferencia", "transference", "a donde fueron", "votos de ", "proyeccion", "proyección"}
        _has_transfer_kw = any(kw in q_norm for kw in ("transferencia", "a donde fueron los votos", "proyeccion", "como se repartieron"))
        if _has_transfer_kw or (re.search(r"\bproyecci[oó]n\b", q_norm) and _has_sv_kw):
            _proj_prefix = None
            _geo_m = re.search(r"\b(?:en|para|de)\s+([A-Za-záéíóúñÁÉÍÓÚÑ]{3,})", q, re.IGNORECASE)
            if _geo_m:
                _geo_name = _geo_m.group(1).strip()
                _dept_r = find_peru_department_prefix(_geo_name)
                if _dept_r:
                    _, _proj_prefix = _dept_r

            with store._connect() as _pc:
                _proj_exists = _pc.execute("SELECT COUNT(*) AS c FROM proyeccion_sv_by_ubigeo").fetchone()["c"]
            if _proj_exists == 0:
                store.rebuild_proyeccion_sv()

            proj_rows = store.get_proyeccion_sv(_proj_prefix)
            if proj_rows:
                if not _proj_prefix and proj_rows:
                    total_1v = sum(int(r.get("votos_1v_total", 0)) for r in proj_rows)
                    total_pk = sum(int(r.get("votos_proyectados_keiko", 0)) for r in proj_rows)
                    total_ps = sum(int(r.get("votos_proyectados_sanchez", 0)) for r in proj_rows)
                    total_abs = sum(int(r.get("votos_abstencion_estimada", 0)) for r in proj_rows)
                    answer_t = (
                        f"**Proyección de transferencia de votos (modelo NNLS, ~86K mesas):**\n\n"
                        f"De los {total_1v:,} votos válidos de primera vuelta:\n"
                        f"- **Keiko Fujimori**: ~{total_pk:,} votos proyectados ({total_pk/total_1v*100:.1f}%)\n"
                        f"- **Roberto Sánchez**: ~{total_ps:,} votos proyectados ({total_ps/total_1v*100:.1f}%)\n"
                        f"- **Abstención estimada**: ~{total_abs:,} votos (~{total_abs/total_1v*100:.1f}%)\n\n"
                        f"⚠️ Proyección basada en patrones electorales históricos. "
                        f"Los resultados reales de segunda vuelta son los definitivos."
                    ) if total_1v > 0 else "Sin datos de primera vuelta para proyectar."
                else:
                    answer_t = f"Proyección para el área consultada: {len(proj_rows)} ubigeos procesados."
                data_t = {"intent": "sv_proyeccion_transferencia", "answer": answer_t, "result": {"rows": proj_rows[:50]}, "source": "sqlite"}
                store.append_raw_event("onpe_chat_sv_proyeccion", {"query": q})
                return ok_response(data_t, started_ms=started_ms)

        # SV: resultados segunda vuelta (geo)
        if _has_sv_kw:
            # J4: Cobertura de actas SV
            if re.search(r"\bcobertura\b", q_norm):
                rows_cob = store.get_sv_cobertura()
                lines_cob = ["**Cobertura de actas — Segunda vuelta 2026:**\n"]
                for r in rows_cob:
                    nm = r.get("nombre_departamento", "")
                    pct = float(r.get("pct_actas_contabilizadas", 0))
                    c = int(r.get("actas_contabilizadas", 0))
                    if nm:
                        lines_cob.append(f"- {nm}: {pct:.1f}% ({c:,} actas)")
                answer_cob = "\n".join(lines_cob)
                data_cob = {"intent": "sv_cobertura", "answer": answer_cob, "result": rows_cob, "source": "sqlite_sv"}
                store.append_raw_event("onpe_chat_sv_cobertura", {"query": q})
                return ok_response(data_cob, started_ms=started_ms)

            _sv_ubigeo = None
            _sv_nombre = None
            _sv_nivel = "nacional"

            # J7: Geo comparison (1V vs 2V) — "compara Lima primera y segunda vuelta"
            _has_compar_geo_kw = bool(
                re.search(r"\bcompar[ae]?\b", q_norm) or ("primera" in q_norm and "segunda" in q_norm)
            )
            if _has_compar_geo_kw:
                _comp_dept_match = find_peru_department_prefix(q)
                if _comp_dept_match:
                    _comp_name, _comp_prefix = _comp_dept_match
                    _comp_ubigeo = _comp_prefix + "0000"
                    comp = store.get_comparacion_geo(_comp_ubigeo)
                    if comp["primera_vuelta"]["mesas"] > 0 or comp["segunda_vuelta"]["mesas"] > 0:
                        v1 = comp["primera_vuelta"]["votos"]
                        v2 = comp["segunda_vuelta"]["votos"]
                        m1 = comp["primera_vuelta"]["mesas"]
                        m2 = comp["segunda_vuelta"]["mesas"]
                        lines_comp = [f"**Comparación 1V vs 2V — {_comp_name.title()}:**\n"]
                        lines_comp.append(f"Primera vuelta: {m1:,} mesas")
                        for v in v1[:4]:
                            lines_comp.append(f"  • {v.get('nombre') or v.get('partido_id','?')}: {int(v.get('total_votos',0)):,}")
                        lines_comp.append(f"\nSegunda vuelta: {m2:,} mesas")
                        for v in v2[:4]:
                            lines_comp.append(f"  • {v.get('nombre') or v.get('partido_id','?')}: {int(v.get('total_votos',0)):,}")
                        answer_comp = "\n".join(lines_comp)
                        data_comp = {"intent": "sv_comparacion_geo", "answer": answer_comp, "result": comp, "source": "sqlite"}
                        store.append_raw_event("onpe_chat_sv_comparacion_geo", {"query": q})
                        return ok_response(data_comp, started_ms=started_ms)

            # Geo resolution: dept → exterior country → Peru district
            _sv_dept_match = find_peru_department_prefix(q)
            if _sv_dept_match:
                _sv_dept_name, _sv_dept_prefix = _sv_dept_match
                _sv_ubigeo = _sv_dept_prefix + "0000"
                _sv_nivel = "departamento"
                _sv_nombre = _sv_dept_name
            else:
                # J8: Exterior country/city (e.g. "Argelia segunda vuelta")
                # Guard: skip candidates <4 chars and purely electoral vocabulary.
                _SV_ELECTION_VOCAB2 = {
                    "segunda", "vuelta", "candidato", "candidatos", "votos", "voto",
                    "resultado", "resultados", "primera", "2da", "eleccion", "elecciones",
                }
                _sv_foreign_hits2: list[dict] = []
                for _fld2, _fval2 in extract_foreign_geo_candidates(q):
                    _cand_tokens2 = [t for t in _fval2.split() if t]
                    if len(_fval2.strip()) < 4:
                        continue
                    if _cand_tokens2 and all(t in _SV_ELECTION_VOCAB2 for t in _cand_tokens2):
                        continue
                    _hits2 = store.find_foreign_ubigeos(_fval2, _fld2)
                    if _hits2:
                        _sv_foreign_hits2 = _hits2
                        break
                if _sv_foreign_hits2:
                    _sv_foreign_pais2 = str(_sv_foreign_hits2[0].get("pais", "")).strip()
                    if _sv_foreign_pais2:
                        _sv_nivel = "pais_exterior"
                        _sv_nombre = _sv_foreign_pais2
                else:
                    # J3: Peru district/city (e.g. "San Isidro segunda vuelta")
                    _sv_district_match = store.find_domestic_ubigeos_by_geo_name(q)
                    if _sv_district_match and _sv_district_match[1]:
                        _sv_nombre, _sv_ubigeos_list = _sv_district_match
                        _sv_ubigeo = str(_sv_ubigeos_list[0]).zfill(6)
                        _sv_nivel = "distrito"

            sv_rows = store.query_sv_geo(nivel=_sv_nivel, ubigeo=_sv_ubigeo, nombre=_sv_nombre, top_n=top_n)

            if sv_rows:
                geo_label = _sv_nombre or "nivel nacional"
                lines_sv = [f"**Resultados de segunda vuelta 2026** — {geo_label}:\n"]
                candidatos_sv = [r for r in sv_rows if str(r.get("partido_id", "")) not in ("80", "81", "82")]
                others_sv = [r for r in sv_rows if str(r.get("partido_id", "")) in ("80", "81", "82")]
                for r in candidatos_sv[:top_n]:
                    vv = int(r.get("votos_validos") or r.get("votos") or 0)
                    pct = float(r.get("pct_votos_validos") or 0)
                    nombre = str(r.get("nombre_candidato") or r.get("nombre_agrupacion") or "")
                    lines_sv.append(f"- **{nombre}**: {vv:,} votos válidos ({pct:.2f}%)")
                for r in others_sv[:2]:
                    vv = int(r.get("votos_validos") or r.get("votos") or 0)
                    nombre = str(r.get("nombre_candidato") or r.get("nombre_agrupacion") or "")
                    lines_sv.append(f"  ({nombre}: {vv:,})")
                nac_rows = store.query_sv_nacional()
                if nac_rows:
                    n0 = nac_rows[0]
                    pct_actas = float(n0.get("actas_contabilizadas_pct") or 0)
                    cont = int(n0.get("contabilizadas") or 0)
                    total_a = int(n0.get("total_actas") or 0)
                    lines_sv.append(f"\n📊 Cobertura: {pct_actas:.2f}% ({cont:,}/{total_a:,} actas)")
                answer_sv = "\n".join(lines_sv)
                _sv_intent = (
                    "geo_exterior" if _sv_nivel in ("pais_exterior", "continente")
                    else "geo_domestic" if _sv_nivel in ("departamento", "provincia", "distrito", "ciudad")
                    else "nacional"
                )
                data_sv = {
                    "intent": _sv_intent,
                    "answer": answer_sv,
                    "result": {"nivel": _sv_nivel, "ubigeo": _sv_ubigeo, "resultados": sv_rows},
                    "source": "sqlite_sv",
                }
                store.append_raw_event("onpe_chat_sv_geo", {"query": q, "nivel": _sv_nivel})
                return ok_response(data_sv, started_ms=started_ms)
            else:
                sv_total = store.total_mesas_sv_local()
                if sv_total == 0:
                    return ok_response(
                        {
                            "intent": "sv_not_bootstrapped",
                            "answer": (
                                "⚠️ No hay datos de segunda vuelta en la base de datos local. "
                                "Ejecuta **onpe_sv_bootstrap()** para cargar los datos."
                            ),
                        },
                        started_ms=started_ms,
                    )

        # Intención 1: candidato específico
        # Detecta tanto "candidato X" como "cuántos votos tuvo/sacó X", "votos de X", etc.
        # Los patrones están compilados a nivel de módulo (_CANDIDATE_VOTE_PATTERNS).
        _candidate_from_pattern: str | None = None
        if not re.search(r'\bcandidato\b', q_norm) and "mesa" not in q_norm:
            for _vp in _CANDIDATE_VOTE_PATTERNS:
                _vm = _vp.search(q)
                if _vm:
                    _late_cand = _vm.group(1).strip()
                    # Strip artículo+honorífico inicial
                    _late_cand = re.sub(
                        r"^(?:el|la|los|las|un|una)\s+(?:doctor[a]?|dr\.?|ing\.?|ingeniero[a]?|licenciado[a]?|lic\.?|profesor[a]?|prof\.?|señor[a]?|don|doña)\s+",
                        "", _late_cand, flags=re.IGNORECASE
                    ).strip()
                    _late_cand = re.sub(r"^(?:el|la)\s+(?=[A-ZÁÉÍÓÚÑ])", "", _late_cand).strip()
                    # Quitar preposición inicial "a/para"
                    _late_cand = re.sub(r"^(?:a|para)\s+(?=[A-Za-záéíóúñÁÉÍÓÚÑ])", "", _late_cand).strip()
                    _late_n = _norm(_late_cand)
                    _late_w = set(_late_n.split())
                    if (
                        _late_n not in _NON_CANDIDATE_EXPRESSIONS
                        and not _late_n.startswith("en ")
                        and not _late_n.startswith("a nivel")
                        and not re.match(r"(?:hacia|desde)\s", _late_n)
                        and not re.fullmatch(r"\d+", _late_n.strip())  # no son candidatos números puros
                        and len(_late_n.strip()) >= 3
                        and not (_late_w & _NON_CANDIDATE_EXPRESSIONS)
                        # Guard: captura que empieza con verbo → no es candidato
                        and not re.match(r"^(?:obtuvo|tuvo|sac[oó]|logr[oó]|consigui[oó]|recibi[oó]|junto|llev[oó]|gan[oó]|sum[oó]|lleg[oó]|alcanz[oó]|fue|quedo|salio|result[oó])\b", _late_n)
                    ):
                        _candidate_from_pattern = _late_cand
                        break

        if bool(re.search(r'\bcandidato\b', q_norm)) or _candidate_from_pattern:
            # Priorizar el nombre extraído por patrón sobre la query completa
            candidate_expr = _candidate_from_pattern or q
            if re.search(r'\bcandidato\b', q_norm):
                match = re.search(r"candidato\s+(.+)$", q, flags=re.IGNORECASE)
                if match:
                    candidate_expr = match.group(1).strip()

            aggregates = store.aggregate_votes_by_party()
            if not aggregates:
                data = {
                    "intent": "candidate",
                    "answer": "Aún no tengo votos consolidados en SQLite. Consulta mesas primero (onpe_get_mesa o onpe_get_mesas_batch).",
                    "result": None,
                    "source": "sqlite",
                    "data_tier": "tier_3_knowledge_base",
                }
                return ok_response(data, started_ms=started_ms)

            candidate_map = store.load_candidate_map(settings.source_dir / "candidato.txt")
            expr_norm = _norm(candidate_expr)

            chosen: dict[str, Any] | None = None
            _late_pat = re.compile(r'\b' + re.escape(expr_norm) + r'\b', re.IGNORECASE) if expr_norm else None
            for item in aggregates:
                pid = str(item["partido_id"])
                cand = candidate_map.get(pid, "")
                if expr_norm.isdigit() and pid == expr_norm:
                    chosen = {**item, "candidato": cand}
                    break
                if _late_pat and (_late_pat.search(_norm(cand)) or _late_pat.search(_norm(str(item["nombre_partido"])))):
                    chosen = {**item, "candidato": cand}
                    break

            if chosen is None:
                # Fuzzy match + qualitative fallback
                _late_known_names = sorted({v for v in candidate_map.values() if v})
                _late_expr_norm = _norm(candidate_expr or "")
                _late_fuzzy = difflib.get_close_matches(
                    _late_expr_norm,
                    [_norm(n) for n in _late_known_names],
                    n=3, cutoff=0.5,
                )
                _late_fuzzy_names = []
                for _lfn in _late_fuzzy:
                    for _lkn in _late_known_names:
                        if _norm(_lkn) == _lfn:
                            _late_fuzzy_names.append(_lkn)
                            break
                _late_qualitative = get_fallback_qualitative(_late_expr_norm) if not aggregates else []
                _late_hint = ""
                if _late_fuzzy_names:
                    _late_hint = " ¿Quisiste decir " + " / ".join(f"**{n}**" for n in _late_fuzzy_names) + "?"
                elif _late_known_names:
                    _late_hint = " Candidatos en cache: " + ", ".join(_late_known_names[:8]) + "…"
                _late_ctx = (" Contexto: " + " ".join(_late_qualitative[:2])) if _late_qualitative else ""
                data = {
                    "intent": "candidate",
                    "answer": (
                        f"No encontré coincidencia para '{candidate_expr}' en los resultados "
                        f"de las elecciones generales 2026.{_late_hint}{_late_ctx}"
                    ),
                    "result": {"query": candidate_expr, "sugerencias": _late_fuzzy_names},
                    "source": "sqlite",
                }
                return ok_response(data, started_ms=started_ms)

            rank = next(
                (
                    idx
                    for idx, item in enumerate(aggregates, start=1)
                    if str(item["partido_id"]) == str(chosen["partido_id"])
                ),
                None,
            )
            answer = (
                f"Candidato {chosen.get('candidato') or 'sin mapeo'} "
                f"(partido {chosen['partido_id']}) tiene {chosen['total_votos']} votos "
                f"y posición {rank} en el consolidado actual."
            )
            data = {
                "intent": "candidate",
                "answer": answer,
                "result": {**chosen, "rank": rank, "total_partidos": len(aggregates)},
                "source": "sqlite",
                "data_tier": "tier_1_local_cache",
            }
            store.append_raw_event("onpe_chat_candidate", {"query": q, "partido_id": chosen["partido_id"]})
            return ok_response(data, started_ms=started_ms)

        _MESA_CONTEXT_WORDS = {"mesa", "acta", "local", "votacion", "sufragio", "urna", "codigo", "dame", "ver", "consulta", "busca", "info", "informacion", "detalle", "datos"}
        mesa_codes_detected = []
        for m in re.findall(r"\b\d{6}\b", q_norm):
            if m not in mesa_codes_detected:
                mesa_codes_detected.append(m)

        if len(mesa_codes_detected) >= 2 and any(w in q_norm for w in _MESA_CONTEXT_WORDS):
            items: list[dict[str, Any]] = []
            for raw_code in mesa_codes_detected:
                code = validate_mesa_code(raw_code)
                payload = None
                source = "not_found"

                cached = store.get_cached_mesa(code, settings.cache_ttl_seconds)
                if cached is not None:
                    payload = cached
                    source = "sqlite_cache"
                else:
                    local_bundle = store.get_mesa_from_local(code)
                    if local_bundle is not None:
                        payload = local_bundle
                        source = "local_db"
                    else:
                        if _is_local_only():
                            payload = None
                            source = "local_only"
                        else:
                            try:
                                mesa = onpe_api.get_mesa(
                                    code,
                                    id_eleccion=max(1, int(id_eleccion)),
                                    timeout=max(1, int(timeout)),
                                )
                                store.upsert_mesa_bundle(
                                    code,
                                    mesa,
                                    source="onpe_live",
                                    id_eleccion=max(1, int(id_eleccion)),
                                )
                                payload = mesa
                                source = "onpe_live"
                            except Exception:
                                payload = None
                                source = "error"

                if payload:
                    mesa_data = payload.get("mesa_data") or {}
                    votos = payload.get("votos") or []
                    top3 = [
                        v for v in votos
                        if v.get("votos", 0) > 0
                        and "blanco" not in str(v.get("nombre_partido", "")).lower()
                        and "nulo" not in str(v.get("nombre_partido", "")).lower()
                    ][:3]
                    top3_str = ", ".join(
                        f"{v.get('nombre_partido', '?')} {int(v.get('votos', 0))}"
                        for v in top3
                    )
                    items.append(
                        {
                            "codigo_mesa": code,
                            "ok": True,
                            "source": source,
                            "estado_acta": mesa_data.get("estado_acta", ""),
                            "electores_habiles": int(mesa_data.get("electores_habiles", 0) or 0),
                            "votos_emitidos": int(mesa_data.get("votos_emitidos", 0) or 0),
                            "top": top3,
                            "top_str": top3_str,
                            "result": payload,
                        }
                    )
                else:
                    items.append(
                        {
                            "codigo_mesa": code,
                            "ok": False,
                            "source": source,
                            "error": "No se pudo obtener información en este momento.",
                        }
                    )

            lines = []
            for it in items:
                if it["ok"]:
                    lines.append(
                        f"Mesa {it['codigo_mesa']}: {it.get('estado_acta','')}. "
                        f"{it.get('votos_emitidos',0)} emitidos de {it.get('electores_habiles',0)}. "
                        f"Top: {it.get('top_str','N/D')}."
                    )
                else:
                    lines.append(f"Mesa {it['codigo_mesa']}: sin datos ({it.get('source')}).")

            data = {
                "intent": "mesa_batch",
                "answer": "\n".join(lines),
                "result": {"total": len(items), "items": items},
                "source": "local_db" if all(i.get("source") in {"sqlite_cache", "local_db"} for i in items) else "mixed",
                "data_tier": "tier_1_local_cache",
            }
            store.append_raw_event("onpe_chat_mesa_batch", {"query": q, "codes": mesa_codes_detected})
            return ok_response(data, started_ms=started_ms)

        if mesa_match and (any(w in q_norm for w in _MESA_CONTEXT_WORDS) or len(q_norm.split()) <= 2):
            # Fallback: número detectado sin keyword "mesa" explícita (e.g. "dame el 900100")
            # Requiere alguna palabra de contexto O query muy corta (solo el número)
            code = validate_mesa_code(mesa_match.group(1))

            # Tier 1a: API cache fresco
            cached = store.get_cached_mesa(code, settings.cache_ttl_seconds)
            if cached is not None:
                mesa_data = cached.get("mesa_data") or {}
                estado = mesa_data.get("estado_acta", "No disponible")
                votos = cached.get("votos") or []
                top3 = [v for v in votos if v.get("votos", 0) > 0
                        and "blanco" not in str(v.get("nombre_partido","")).lower()
                        and "nulo" not in str(v.get("nombre_partido","")).lower()][:3]
                top3_str = ", ".join(f"{v['nombre_partido']} {v['votos']}" for v in top3)
                data = {
                    "intent": "mesa",
                    "answer": f"Mesa {code} ({mesa_data.get('local_votacion','')}, {estado}). Top candidatos: {top3_str}.",
                    "result": cached,
                    "source": "sqlite_cache",
                    "data_tier": "tier_1_local_cache",
                }
                return ok_response(data, started_ms=started_ms)

            # Tier 1b: DB local hidratada (mesas_data + votos) — sin llamada HTTP
            local_bundle = store.get_mesa_from_local(code)
            if local_bundle is not None:
                mesa_data = local_bundle.get("mesa_data") or {}
                estado = mesa_data.get("estado_acta", "No disponible")
                votos = local_bundle.get("votos") or []
                # Cargar nombres de candidatos
                cand_map = store.load_candidate_map(settings.source_dir / "candidato.txt")
                for v in votos:
                    v["candidato"] = cand_map.get(str(v.get("partido_id", "")), "")
                top3 = [v for v in votos if v.get("votos", 0) > 0
                        and "blanco" not in str(v.get("nombre_partido","")).lower()
                        and "nulo" not in str(v.get("nombre_partido","")).lower()][:3]
                top3_str = ", ".join(
                    f"{v.get('candidato') or v['nombre_partido']} {v['votos']}"
                    for v in top3
                )
                loc = mesa_data.get("local_votacion", "")
                dept = mesa_data.get("departamento", "")
                loc_str = f"{loc}, {dept}" if dept else loc
                store.append_raw_event("onpe_chat_mesa", {"query": q, "codigo_mesa": code, "source": "local_db"})
                data = {
                    "intent": "mesa",
                    "answer": f"Mesa {code} ({loc_str}): {estado}. {mesa_data.get('votos_emitidos',0)} votos emitidos de {mesa_data.get('electores_habiles',0)} electores. Top candidatos: {top3_str}.",
                    "result": local_bundle,
                    "source": "local_db",
                    "data_tier": "tier_1_local_cache",
                }
                return ok_response(data, started_ms=started_ms)

            # Tier 1c: código redondo → bloque/prefijo (igual que el bloque principal)
            # '900000' → prefix '9' (bloque 900000–999999), '150000' → '15', etc.
            if code.endswith("000"):
                _block_prefix2 = code.rstrip("0") or code[0]
                _block_desc2 = store.describe_mesa_prefix(_block_prefix2)
                _block_total2 = int(_block_desc2.get("total_mesas") or 0)
                if _block_total2 > 0:
                    coverage2 = _build_coverage_block(q_norm, id_eleccion, timeout, prefix=_block_prefix2)
                    context_notes2 = get_context_notes(q_norm, _block_prefix2)
                    top_cands2 = store.get_top_candidates_for_prefix(_block_prefix2, top_n=5)
                    display_label2 = f"mesas {_block_prefix2}K" if _block_prefix2.isdigit() else f"mesas {code}"
                    ve2 = coverage2["votos_emitidos"]
                    pct2 = coverage2["coverage_pct"]
                    verdict2 = coverage2["verdict"]
                    ans2 = (
                        f"## ✅ Las {display_label2} SÍ existen — datos cache local ONPE\n\n"
                        f"| Indicador | Dato |\n|-----------|------|\n"
                        f"| Total mesas | **{_block_total2:,}** |\n"
                        f"| Cobertura | {pct2:.1f}% ({verdict2}) |\n"
                        f"| Votos emitidos | {ve2:,} |\n"
                    )
                    if top_cands2:
                        ans2 += "\n**Top candidatos:**\n"
                        _tc2 = sum(int(c.get("total_votos", 0)) for c in top_cands2)
                        for i2, c2 in enumerate(top_cands2[:5], 1):
                            pct_c2 = int(c2.get("total_votos", 0)) / _tc2 * 100 if _tc2 else 0
                            ans2 += f"{i2}. {c2.get('nombre_partido', '?')} — {int(c2.get('total_votos', 0)):,} ({pct_c2:.1f}%)\n"
                    if context_notes2:
                        ans2 += f"\n> {context_notes2}"
                    data = {
                        "intent": "range_existence_verify",
                        "answer": ans2,
                        "result": {"prefix": _block_prefix2, "description": _block_desc2, "coverage": coverage2},
                        "source": "sqlite",
                        "data_tier": "tier_1_local_cache",
                    }
                    store.append_raw_event("onpe_chat_mesa_block", {"query": q, "prefix": _block_prefix2})
                    return ok_response(data, started_ms=started_ms)

            # Tier 2 deshabilitado en local-only
            if _is_local_only():
                return ok_response(
                    {
                        "intent": "mesa",
                        "answer": f"Mesa {code}: no existe en la base local.",
                        "source": "local_only",
                    },
                    started_ms=started_ms,
                )
            try:
                mesa = onpe_api.get_mesa(code, id_eleccion=max(1, int(id_eleccion)), timeout=max(1, int(timeout)))
                store.upsert_mesa_bundle(code, mesa, source="onpe_live", id_eleccion=max(1, int(id_eleccion)))
                store.append_raw_event("onpe_chat_mesa", {"query": q, "codigo_mesa": code, "found": bool(mesa.get("found"))})
                estado = (mesa.get("mesa_data") or {}).get("estado_acta", "No disponible")
                data = {
                    "intent": "mesa",
                    "answer": f"Mesa {code}: estado {estado}.",
                    "result": mesa,
                    "source": "onpe_live",
                    "data_tier": "tier_2_onpe_api",
                }
                return ok_response(data, started_ms=started_ms)
            except Exception:
                return ok_response(
                    {
                        "intent": "mesa",
                        "answer": f"Mesa {code}: no se pudo obtener información en este momento. Intenta de nuevo más tarde.",
                        "source": "error",
                    },
                    started_ms=started_ms,
                )

        qual_notes = get_fallback_qualitative(q_norm)
        fallback_answer = (
            f"No identifiqué la intención para '{q}'. "
            "Prueba: una mesa ('mesa 012345'), un departamento ('top 3 en Loreto'), "
            "un lugar extranjero ('resultados en Santiago'), "
            "legislativo ('senadores en Lima' o 'diputados para Arequipa'), "
            "o candidato ('candidato Fujimori')."
        )
        if qual_notes and qual_notes[0] != fallback_answer:
            fallback_answer += " — " + qual_notes[0]
        fallback = {
            "intent": "unknown",
            "answer": fallback_answer,
            "result": {"qualitative_notes": qual_notes} if qual_notes else None,
            "source": "knowledge_base",
            "data_tier": "tier_3_knowledge_base",
        }
        return ok_response(fallback, started_ms=started_ms)
    except ValueError as exc:
        return error_response(str(exc), started_ms=started_ms, code="VALIDATION_ERROR")
    except GatewayError as exc:
        return error_response(str(exc), started_ms=started_ms, code="GATEWAY_ERROR")
    except OnpeApiError as exc:
        return error_response(str(exc), started_ms=started_ms, code="ONPE_API_ERROR")
    except Exception as exc:  # pragma: no cover
        logger.exception("Error inesperado en onpe_chat")
        return error_response(str(exc), started_ms=started_ms)


def main() -> None:
    logger.info("Iniciando servidor onpe-mcp")
    mcp.run()


if __name__ == "__main__":
    main()
