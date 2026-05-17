# pyright: reportMissingImports=false

from __future__ import annotations

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
    validate_mesa_code,
)


settings = Settings.from_env()
configure_logging(settings.log_level)
logger = logging.getLogger("onpe_mcp")

gateway = OnpeScraperGateway(settings)
store = DataStore(settings.data_dir)
onpe_api = OnpeApiClient()

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

# Patrones para detectar consultas de votos por candidato sin keyword "candidato".
# Compilados una vez a nivel de módulo para evitar overhead por llamada.
_CANDIDATE_VOTE_PATTERNS = [
    # "cuántos votos sacó/tuvo/obtuvo/logró/consiguió/recibió/juntó X"
    # incluye plural "sacaron/tuvieron/obtuvieron" para multi-candidato
    # acepta "en total", "fue que" intercalados: "cuántos votos fue que obtuvo X"
    # acepta typos b/v frecuentes en español peruano: tubo/obtubo/obtubieron
    re.compile(
        r"\bcu[aá]ntos?\s+votos?\s+(?:en\s+total\s+|fue\s+que\s+|se\s+)?(?:tuvo|tuvieron|tubo|tubieron|sac[oó]|sacaron|tiene|tienen|obtuvo|obtuvieron|obtubo|obtubieron|gan[oó]|ganaron|logr[oó]|lograron|consigui[oó]|consiguieron|recibi[oó]|recibieron|junt[oó]|juntaron|lleva|llevan|lleba|lleban|llev[oó]|llevaron|acumula|acumulan|sum[oó]|sumaron)\s+(.+?)(?:\s+(?:en|a\s+nivel|para)\b.*)?$",
        re.IGNORECASE,
    ),
    # "cuánto sacó/obtuvo X" / "que porcentaje obtuvo X" — también plural "cuántos"
    # acepta palabras intermedias: "cuanto porcentaje saco X", "cuantos puntos tuvo X"
    re.compile(
        r"\b(?:cu[aá]ntos?\s+(?:\w+\s+)?|qu[eé]\s+(?:porcentaje|puntaje|puntos?|lugar|posici[oó]n)\s+)(?:sac[oó]|obtuvo|logr[oó]|llev[oó]|anot[oó]|junt[oó]|consigui[oó]|recibi[oó]|tiene|tuvo)\s+(.+?)(?:\s+(?:en|a\s+nivel|total|en\s+total)\b.*)?$",
        re.IGNORECASE,
    ),
    # "votos de X" / "votos totales de X" / "número de votos de X"
    re.compile(
        r"\bvotos?\s+(?:totales?\s+)?(?:de|que\s+(?:sac[oó]|tuvo|obtuvo|logr[oó]))\s+(.+?)(?:\s+(?:en|a\s+nivel|total|nacional)\b.*)?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bn[uú]mero\s+de\s+votos?\s+de\s+(.+?)(?:\s+(?:en|a\s+nivel|total|nacional)\b.*)?$",
        re.IGNORECASE,
    ),
    # "votos en la elección de X" → candidato X
    re.compile(
        r"\bvotos?\s+en\s+(?:la\s+)?elecci[oó]n\s+de\s+(.+?)(?:\s+(?:en|a\s+nivel|total|nacional)\b.*)?$",
        re.IGNORECASE,
    ),
    # "qué resultados/votos/porcentaje tuvo/obtuvo/sacó X"
    re.compile(
        r"\bqu[eé]\s+(?:result(?:ados?|[oó])|votos?|porcentaje|puntuaci[oó]n|puntaje|lugar|posici[oó]n)\s+(?:tuvo|obtuvo|sac[oó]|logr[oó]|consigui[oó]|recibi[oó])\s+(.+?)$",
        re.IGNORECASE,
    ),
    # "resultados de X" / "resultados nacionales de X" / "puntaje de X" / "resultados del X"
    re.compile(
        r"\b(?:result(?:ados?|[oó])(?:\s+\w+)?\s+(?:de|del)|puntaje\s+(?:de|del))\s+(.+?)(?:\s+(?:en|a\s+nivel|total|nacional)\b.*)?$",
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
    # "X cuántos votos" (order reversed) — also "X cuántos lleva/tiene/acumula"
    # The (?:\s+...)? at the end is optional to also match bare "X cuántos" (no verb/votos)
    re.compile(
        r"^(.+?)\s+cu[aá]ntos?(?:\s+(?:votos?\s+)?(?:sac[oó]|tuvo|tiene|obtuvo|lleva|acumula|sum[oó]|consigui[oó])?)?$",
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
    # "NAME resultados" — reversed order (resultados after name)
    re.compile(
        r"^([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,35})\s+resultados?$",
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
    "nivel", "nacional",  # "a nivel nacional" capturado por Pattern 13 "candidato a nivel"
})

# Patrón para detectar consultas multi-candidato: "X y Y" o "X e Y"
_MULTI_CANDIDATE_PATTERN = re.compile(
    r"\bvotos?\s+(?:de\s+)?(.+?)\s+(?:y|e)\s+(.+?)(?:\s+(?:en|a\s+nivel|total)\b.*)?$"
    r"|\b(.+?)\s+y\s+(.+?)\s+cu[aá]ntos?\s+votos?"
    r"|\bcomparar?\s+(?:a\s+)?(?:votos?\s+(?:de\s+)?)?(.+?)\s+(?:y|con|versus|vs\.?)\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\b([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,40}?)\s+y\s+([A-Za-záéíóúñÁÉÍÓÚÑ][A-Za-z\sáéíóúñÁÉÍÓÚÑ]{1,40}?)\s+en\b"
    r"|\b(.+?)\s+versus\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\b(.+?)\s+vs\.?\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\bdiferencia\s+(?:de\s+votos?\s+)?entre\s+(.+?)\s+y\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\b(.+?)\s+frente\s+a\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\b(.+?)\s+contra\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\b(.+?)\s+o\s+(.+?)\s+(?:quien|cu[aá]l|cu[aá]ntos?)\s+(?:sac[oó]|tuvo|obtuvo|tiene|tiene\s+m[aá]s|gan[oó]|logr[oó])"
    r"|\bquien\s+(?:sac[oó]|tuvo|obtuvo|tiene)\s+m[aá]s\s+(.+?)\s+o\s+(.+?)(?:\?|$)"
    r"|\b(.+?)\s+cu[aá]ntos?\s+votos?\s+(?:y|e)\s+(.+?)\s+cu[aá]ntos?\s+votos?"
    r"|\b(?:si\s+)?(.+?)\s+(?:le\s+)?gan[oó]\s+(?:a|contra)\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\btanto\s+(.+?)\s+como\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\b(.+?)\s+(?:tuvo|sac[oó]|obtuvo)\s+m[aá]s\s+votos?\s+que\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$"
    r"|\b(.+?)\s+m[aá]s\s+que\s+(.+?)(?:\s+(?:en|a\s+nivel)\b.*)?$",
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
    r"|(?:quiero|quisiera|necesito|podrias?\s+decirme|podrías?\s+decirme)\s+(?:saber\s+|ver\s+)?"
    r"|(?:oye|oiga|escucha)[,\s]+"
    r"|(?:ponme|dame|muestrame|muéstrame|dime)[,\s]+"
    r"|(?:por\s+favor[,\s]+)?"
    r"|(?:sabes?\s+(?:cuantos?|cu[aá]ntos?|como|cómo)\s+)?"
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
    """Elimina muletillas verbales de inicio/fin para normalizar lenguaje natural."""
    t = _FILLER_START.sub("", text.strip())
    t = _FILLER_END.sub("", t).strip()
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
    """Resuelve una geo doméstica peruana. Primero tabla ubigeo_reniec, luego prefijos por departamento."""
    reniec_result = store.find_domestic_ubigeos_by_geo_name(q)
    if reniec_result is not None:
        geo_name, ubigeos = reniec_result
        return geo_name, set(ubigeos)
    dept_result = find_peru_department_prefix(q)
    if dept_result is not None:
        dept_name, dept_prefix = dept_result
        ubigeos = set(store.find_ubigeos_by_prefix(dept_prefix))
        return dept_name, ubigeos
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
    hydrated = 0
    for code in mesa_codes:
        try:
            data = onpe_api.get_mesa(code, id_eleccion=id_eleccion, timeout=timeout)
            store.upsert_mesa_bundle(code, data, source="auto_hydrate", id_eleccion=id_eleccion)
            hydrated += 1
        except Exception:
            logger.debug("auto_hydrate: falló mesa %s", code)
    return hydrated


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

        cached = None if force_live else store.get_cached_mesa(code, settings.cache_ttl_seconds)
        if cached is not None:
            logger.info("tool=onpe_get_mesa codigo_mesa=%s source=cache", code)
            return ok_response(cached, started_ms=started_ms, meta={"source": "sqlite_cache"})

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
        try:
            total_mesas = store.total_mesas_local()
            with store._connect() as _c:
                total_votos = int((_c.execute("SELECT COUNT(*) AS c FROM votos").fetchone() or {"c": 0})["c"])
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
def onpe_chat(query: str, id_eleccion: int = 10, timeout: int = 30) -> dict[str, Any]:
    """Interfaz conversacional única para consultas comunes de ONPE con estrategia cache-first.

    Orden de prioridad de datos:
      1. Cache local SQLite (datos hidratados del MCP) — siempre primero.
      2. API ONPE en vivo — cuando el dato no está en cache.
      3. Compendio cualitativo verificable (knowledge_base.py) — fallback pedagógico sin cifras inventadas.
      4. Fuentes externas — indicado explícitamente cuando aplica.
    """
    started_ms = now_ms()
    try:
        q = str(query or "").strip()
        if not q:
            raise ValueError("query no puede estar vacía")

        # ── Guard: saludos y queries muy cortas ─────────────────────────────
        _GREETINGS = {"hola", "hi", "hey", "buenas", "ola", "hello", "saludos", "que tal"}
        if q.lower().strip("¿?!.,") in _GREETINGS or len(q) < 4:
            return ok_response(
                {
                    "intent": "unknown",
                    "answer": (
                        "¡Hola! Puedo responder consultas sobre los resultados electorales del Perú 2026. "
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
        })
        # "tiempo" alone is ambiguous (also = "time"); only block if paired with weather words
        _has_weather = bool(
            _NON_ELECTORAL_TOKENS & set(_q_norm_guard.split())
            or ("tiempo" in _q_norm_guard and any(w in _q_norm_guard for w in ("hoy", "manana", "clima", "llov")))
        )
        if _has_weather and not any(
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
            if (
                _after.lstrip().startswith("voto")
                or re.search(r"\bde\s*$", _before)
                or re.search(r"\bentre\s*$", _before)  # "entre X y Y votos"
                or re.search(r"\by\s*$", _before)      # "X y N votos" (rango)
            ):
                mesa_match = None
        # Normalizar puntuación especial para mejorar pattern matching
        q = re.sub(r"[¿¡:;?!]", " ", q)
        # Normalizar símbolo % → "porcentaje" (en cualquier posición)
        q = q.replace("%", " porcentaje ")
        # Normalizar typos fonéticos frecuentes en español peruano (b/v, c/s)
        q = re.sub(r"\bbotos?\b", "votos", q, flags=re.IGNORECASE)  # "botos" → "votos"
        q = re.sub(r"\belecsion\b", "eleccion", q, flags=re.IGNORECASE)  # "elecsion" → "eleccion"
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

        # Intención 0: legislativo (diputados/senadores/escaños/congresistas) más votado por distrito
        if "diputad" in q_norm or "senador" in q_norm or re.search(r"\besca[nñ]os?\b", q_norm) or "congresista" in q_norm:
            cargo = "senadores" if ("senador" in q_norm or ("esca" in q_norm and "senador" in q_norm)) else "diputados"
            if "senador" in q_norm:
                cargo = "senadores"
            distrito_expr = q
            match = re.search(r"\b(?:en|para)\s+(.+)$", q, flags=re.IGNORECASE)
            if match:
                distrito_expr = match.group(1).strip()

            district = onpe_api.resolve_district(distrito_expr)
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
        }
        _has_mesa = "mesa" in q_norm
        # También detectar rango numérico explícito "X a Y" (ej: "900100 a 900200")
        _numeric_range_m = re.search(r"\b(\d{4,6})\s+a\s+\d{4,6}\b", q_norm)
        _has_range = any(w in q_norm for w in _RANGE_INDICATOR_WORDS) or bool(_numeric_range_m)
        _has_performance = "primero" in q_norm or "primer " in q_norm or "gano" in q_norm
        if _has_mesa and _has_range and _has_performance:
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
            # 1. "fue/quedó primero NOMBRE"  (ej: "fue primero López Aliaga")
            # 2. "fue/quedó NOMBRE primero"  (ej: "fue López Aliaga primero")
            # 3. "ganó/gano NOMBRE"          (ej: "ganó López Aliaga")
            candidate_expr = ""
            _cand_patterns = [
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

            # Tier 2: Live API — wrapped para siempre devolver intent="mesa"
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
                    _cfe_n = _norm(_cfe_cand)
                    _cfe_w = set(_cfe_n.split())
                    if (
                        _cfe_n not in _NON_CANDIDATE_EXPRESSIONS
                        and not _cfe_n.startswith("en ")
                        and not _cfe_n.startswith("a nivel")
                        and not re.match(r"(?:hacia|desde)\s", _cfe_n)
                        and not re.fullmatch(r"\d+", _cfe_n.strip())  # no son candidatos números puros
                        and len(_cfe_n.strip()) >= 3
                        and not (_cfe_w & _NON_CANDIDATE_EXPRESSIONS)
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
        elif _candidate_from_pattern_early and re.search(r"\s+(?:versus|vs\.?|con|comparado\s+con|frente\s+a|contra)\s+", _candidate_from_pattern_early, re.IGNORECASE):
            _mc_m2 = _MULTI_CANDIDATE_PATTERN.search(q)
            if _mc_m2:
                _mc_groups2 = [g.strip() for g in _mc_m2.groups() if g and g.strip()]
                if len(_mc_groups2) >= 2:
                    _multi_candidates = _mc_groups2[:2]
                    _candidate_from_pattern_early = None
            if not _multi_candidates:
                # Fallback: split by versus/vs/comparado con/frente a/contra
                _parts2 = re.split(r"\s+(?:versus|vs\.?|comparado\s+con|frente\s+a|contra)\s+", _candidate_from_pattern_early, flags=re.IGNORECASE)
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
                if not _expr_is_geo:
                    # Antes de responder "no encontrado", verificar si el nombre
                    # coincide con un país/ciudad extranjera → fallthrough a geo.
                    _expr_foreign_chk = store.find_foreign_ubigeos(_candidate_from_pattern_early)
                    if _expr_foreign_chk:
                        pass  # cae a bloques geo abajo
                    else:
                        _known = ", ".join(sorted({v for v in _cand_map_early.values() if v})[:10])
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
                        data = {
                            "intent": "candidate",
                            "answer": (
                                f"No encontré al candidato '{_candidate_from_pattern_early}' en los resultados "
                                f"de las elecciones generales 2026.{_hint_text} "
                                f"Algunos candidatos disponibles: {_known}…"
                            ),
                            "result": {
                                "query": _candidate_from_pattern_early,
                                "found": False,
                                "cultural_hint": _cultural_hint,
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
            "top candidatos", "top de candidatos",
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
            # votos especiales — movidos a check dinámico con guard geo
            # "votos en blanco", "votos nulos", "votos viciados", "en blanco", "votos blancos", "votos invalidos"
            # referencias temporales a elecciones — movidas a check dinámico
            # "elecciones 2026", "elecciones 2021", "elecciones del 2026", "elecciones del 2021",
            # "resultados 2026", "resultados 2021",
            # frases adicionales
            "elecciones presidenciales", "presidenciales 2026", "presidenciales 2021",
            "participaron en las elecciones", "participacion en las elecciones",
            "ranking completo", "tabla de resultados", "tabla electoral",
            "tabla de candidatos", "lista completa", "todos los candidatos",
            # regiones naturales (sin geo específico)
            "sierra peruana", "selva peruana", "costa peruana",
            "en la sierra", "en la selva", "en la costa",
        }
        _is_national = any(p in q_norm for p in _NATIONAL_PHRASES)
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
            r"\b(?:en|de)\s+(?:(?:el|la|los|las)\s+)?(?!\d)"
            r"(?!(?:el|la|los|las|un|una|unos|unas"
            r"|todos?|todas?|cada|alguno?|ninguno?|cualquier|la\s+eleccion|candidatos?"
            r"|votos?|voto|porcentaje|datos?|resultado|resultados|informacion|info"
            r"|blanco|nulos?|viciados?|blancos|invalidos?|total|totales|general|generales"
            r"|primera|segunda|tercera|primera|primer|segundo|tercer|tercero|cuarta|quinto"
            r"|vuelta|turno|ronda|siguiente|anterior"
            r"|eleccion|elecciones|elecci[oó]n|electoral|electorales"
            r"|dolar|euro|sol|libra|precio|costo|cambio|tipo)\b)\w{3,}",
            q_norm
        ) or _bare_dept_in_q
        if not _is_national and re.search(r"\b(top\s*\d*|\d+\s+primeros?|primeros?\s+\d+)\b", q_norm) and (
            "nacional" in q_norm or "pais" in q_norm or "peru" in q_norm
            or ("candidatos" in q_norm and not _GEO_IN_Q)
        ):
            _is_national = True
        if not _is_national and re.search(r"\bm[aá]s\s+votos\b", q_norm) and "candidatos" in q_norm and not _GEO_IN_Q:
            _is_national = True
        # "dame el top 5" / "top 3" sin contexto geográfico → nacional
        if not _is_national and re.search(r"\btop\s+\d+\b", q_norm) and not _GEO_IN_Q:
            _is_national = True
        # "todos/todas" + (candidatos|resultados|votos|regiones) sin geo específico → nacional
        if not _is_national and ("todos" in q_norm or "todas" in q_norm) and not _GEO_IN_Q:
            if "candidatos" in q_norm or "resultados" in q_norm or "votos" in q_norm or "regiones" in q_norm or "provincias" in q_norm or "pais" in q_norm:
                _is_national = True
        # "candidatos/candidato" sin geo → nacional (ej: "cuántos candidatos se presentaron")
        if not _is_national and re.search(r"\bcandidatos?\b", q_norm) and not _GEO_IN_Q:
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
        # "quien salió en primer/segundo lugar" → ranking nacional sin geo
        if not _is_national and re.search(r"\b(?:quien|quienes?)\s+(?:sali[oó]|qued[oó]|result[oó])\s+en\s+(?:primer|segundo|tercer|cuarto|quinto)\b", q_norm) and not _GEO_IN_Q:
            _is_national = True
        # "quienes ganaron/superaron/consiguieron" sin geo → nacional; con "en PLACE" → geo_domestic
        if not _is_national and re.search(r"\bquienes?\s+(?:son\s+(?:los\s+)?)?(?:gan[ao]ron?|lider(?:es)?|superaron|consiguieron|obtuvieron|tuvieron)\b", q_norm):
            if not _GEO_IN_Q:
                _is_national = True

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
                _foreign_name_amb = next(
                    (fp.title() for fp in sorted(_fc_geos_ext, key=len, reverse=True) if fp in q_norm),
                    "exterior",
                )
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
                data = {
                    "intent": "candidate",
                    "answer": f"No encontré coincidencia para candidato '{candidate_expr}'.",
                    "result": {"query": candidate_expr},
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

        if mesa_match:
            # Fallback: número detectado sin keyword "mesa" explícita (e.g. "dame el 900100")
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

            # Tier 2: Live API (mesa no está en DB local)
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
