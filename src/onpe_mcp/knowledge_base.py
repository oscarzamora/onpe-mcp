"""Base de conocimiento electoral verificable para respuestas pedagógicas neutrales.

Orden de prioridad de datos en onpe_chat:
  1. Cache local SQLite (datos hidratados del MCP)
  2. API ONPE en vivo
  3. Compendio cualitativo de este módulo (fallback sin cifras inventadas)
  4. Fuentes externas (indicado explícitamente)

Todos los hechos son verificables mediante fuentes oficiales (ONPE, JNE, RENIEC).
No se especulan ni proyectan resultados electorales.
"""
from __future__ import annotations

# ──────────────────────────────────────────────────────────────────────────────
# Mesas 900K
# ──────────────────────────────────────────────────────────────────────────────
_MESA_900K_FACTS: tuple[str, ...] = (
    "Las mesas con prefijo 9XXXXX existen en el padrón oficial de ONPE desde hace más de 20 años.",
    "Se asignan a centros poblados menores, comunidades nativas y zonas rurales de difícil acceso.",
    "No son nuevas ni creadas para 2026; funcionan igual que cualquier mesa urbana: "
    "padrón RENIEC, miembros de mesa, personeros, actas y fiscalización.",
    "Todos los partidos reciben con anticipación la lista completa de mesas (incluidas las 900K) "
    "para acreditar personeros.",
    "Las mesas 900K no aparecen en Lima urbana, por eso muchos ciudadanos nunca han visto una. "
    "Su numeración alta no implica irregularidad; es un rango asignado históricamente para zonas rurales.",
)

# ──────────────────────────────────────────────────────────────────────────────
# STAE y sistema de transmisión
# ──────────────────────────────────────────────────────────────────────────────
_STAE_FACTS: tuple[str, ...] = (
    "El STAE no está conectado a internet. Es un kit para imprimir actas y reducir errores manuales.",
    "Fue auditado bajo ISO 27001 y NIST CSF. No transmite votos ni resultados "
    "y no tiene capacidad de alterar el padrón.",
    "ONPE reconoció errores logísticos en Lima Metropolitana los días 12–13 de abril; "
    "se separó a funcionarios responsables y se abrió investigación administrativa. "
    "Esto no invalida el proceso.",
)

# ──────────────────────────────────────────────────────────────────────────────
# Proceso electoral y actas
# ──────────────────────────────────────────────────────────────────────────────
_PROCESS_FACTS: tuple[str, ...] = (
    "El escrutinio es público y presenciado por personeros de todos los partidos.",
    "Las actas físicas son el documento fuente; el STAE transmite imágenes de esas actas.",
    "Las actas observadas son normales en cualquier elección: se observan por errores de firma, "
    "sumas, tachaduras o inconsistencias. El JEE revisa cada caso con presencia de personeros. "
    "No significa manipulación.",
    "Las correcciones en actas son normales cuando se detecta un error de suma; "
    "deben estar firmadas por los tres miembros de mesa y el JEE revisa cualquier corrección dudosa.",
    "En zonas sin STAE las actas se llenan manualmente. "
    "Cada miembro de mesa tiene su propia firma; no existe un estándar visual. "
    "Los personeros verifican identidad en el momento.",
    "Las diferencias entre número de votantes y número de votos pueden deberse a errores de conteo. "
    "Por eso existen las actas observadas: el JEE revisa y corrige con presencia de personeros.",
    "El escaneo de actas depende de la calidad del equipo y la iluminación. "
    "ONPE publica la imagen original sin editar. Si el acta es ilegible, se revisa el físico.",
    "Si falta una firma, el acta se observa automáticamente. "
    "No se contabiliza hasta que el JEE la revise.",
)

# ──────────────────────────────────────────────────────────────────────────────
# Patrones rurales vs urbanos
# ──────────────────────────────────────────────────────────────────────────────
_RURAL_VOTE_FACTS: tuple[str, ...] = (
    "En zonas rurales pequeñas la participación suele ser muy alta porque las comunidades son cohesionadas. "
    "En ciudades la abstención es más común. No es un fenómeno nuevo.",
    "Las mesas rurales pueden tener 20, 30 o 50 votantes porque están diseñadas para evitar "
    "que la población camine largas distancias. Esto existe desde hace muchos procesos electorales.",
    "En zonas rurales el voto tiende a ser más homogéneo; en ciudades es más fragmentado. "
    "No implica fraude; implica dinámicas sociales distintas.",
    "Una concentración de votos en un candidato dentro de un prefijo rural puede reflejar "
    "preferencia regional documentada, no necesariamente irregularidad.",
)

# ──────────────────────────────────────────────────────────────────────────────
# Patrones geográficos específicos (Lima periurbana, distritos)
# ──────────────────────────────────────────────────────────────────────────────
_GEO_PATTERNS: tuple[str, ...] = (
    "Pachacámac y Lurín combinan zonas urbanas consolidadas con anexos rurales; "
    "el voto en los anexos tiende a ser más homogéneo que en las áreas urbanas.",
    "San Juan de Miraflores (SJM) es urbano denso, por lo que el voto es más fragmentado "
    "y la abstención puede ser mayor que en zonas rurales.",
    "Paterson y Orlando (EE. UU.) concentran alta migración peruana; "
    "la participación en mesas del exterior depende del registro consular.",
    "Los resultados oficiales por distrito deben consultarse en el portal de ONPE "
    "(resultadoelectoral.onpe.gob.pe) o mediante este MCP usando onpe_get_mesa / onpe_chat.",
)

# ──────────────────────────────────────────────────────────────────────────────
# Respuesta a sospechas de fraude
# ──────────────────────────────────────────────────────────────────────────────
_FRAUD_RESPONSE_FACTS: tuple[str, ...] = (
    "No hay indicios documentados de fraude asociados a mesas 900K, STAE o mesas rurales.",
    "El padrón electoral es de RENIEC, no de ONPE; no puede ser alterado por el sistema de cómputo.",
    "Las actas se procesan igual que cualquier otra y existen auditorías externas al sistema.",
    "Para cualquier denuncia concreta, el canal oficial es el JNE "
    "(jne.gob.pe) y la Fiscalía Especializada en Delitos Electorales.",
)

# ──────────────────────────────────────────────────────────────────────────────
# Mesas del lunes 13 (instalación diferida Lima)
# ──────────────────────────────────────────────────────────────────────────────
_LUNES13_FACTS: tuple[str, ...] = (
    "ONPE reconoció errores logísticos en Lima Metropolitana el 12–13 de abril.",
    "La ley electoral permite completar la instalación de mesas en casos excepcionales.",
    "Se separó a los funcionarios responsables y se abrió investigación administrativa.",
    "La instalación diferida no invalida el proceso ni las actas resultantes.",
)

# ──────────────────────────────────────────────────────────────────────────────
# Resultados nacionales 2026 (100 % mesas contabilizadas)
# ──────────────────────────────────────────────────────────────────────────────
_ELECTION_RESULTS_2026: tuple[str, ...] = (
    "Resultados nacionales elecciones 2026 (fuente: ONPE, 100% de mesas contabilizadas):",
    "· FUERZA POPULAR (Keiko Fujimori): 2,877,621 votos válidos (17.18%)",
    "· JUNTOS POR EL PERÚ: 2,015,060 votos válidos (12.03%)",
    "· RENOVACIÓN POPULAR (Rafael López Aliaga): 1,993,815 votos válidos (11.90%)",
    "· PARTIDO DEL BUEN GOBIERNO: 1,837,456 votos válidos (10.97%)",
    "· PARTIDO CÍVICO OBRAS: 1,698,895 votos válidos (10.14%)",
    "· Blancos + nulos + impugnados: 3,418,306 (no forman parte del denominador de votos válidos ONPE).",
    "Universo: 92,766 mesas presidenciales, 27,325,132 electores hábiles.",
)

# ──────────────────────────────────────────────────────────────────────────────
# Índice de temas → grupos de hechos (para get_fallback_qualitative)
# ──────────────────────────────────────────────────────────────────────────────
_TOPIC_MAP: list[tuple[frozenset[str], tuple[str, ...]]] = [
    (
        frozenset({
            "900", "900k", "mesas rurales", "fantasma", "fantasm", "inventad",
            "no existen", "ghost", "rural", "nativa", "comunidad", "centro poblado",
        }),
        _MESA_900K_FACTS + _RURAL_VOTE_FACTS,
    ),
    (
        frozenset({"stae", "transmision", "sistema", "kit", "impresion"}),
        _STAE_FACTS,
    ),
    (
        frozenset({
            "acta", "observada", "correccion", "firma", "escaneo", "imagen", "legible",
            "tachadur", "inconsistencia", "suma",
        }),
        _PROCESS_FACTS,
    ),
    (
        frozenset({"lunes", "13 de abril", "instalacion", "diferid"}),
        _LUNES13_FACTS,
    ),
    (
        frozenset({
            "fraude", "trampa", "manipul", "irregular", "sospech",
            "solo gana", "siempre gana", "solo sale",
        }),
        _FRAUD_RESPONSE_FACTS + _PROCESS_FACTS,
    ),
    (
        frozenset({"pachacamac", "lurin", "sjm", "san juan de miraflores", "paterson", "orlando"}),
        _GEO_PATTERNS,
    ),
    (
        frozenset({
            "resultado", "votos nacionales", "porcentaje", "quien gano",
            "quien gana", "cuanto saco", "total nacional",
        }),
        _ELECTION_RESULTS_2026,
    ),
    (
        frozenset({"rural", "campo", "amazonia", "comunidad", "participacion", "ausentismo", "abstencion"}),
        _RURAL_VOTE_FACTS,
    ),
]


# ──────────────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────────────

def get_context_notes(q_norm: str, mesa_prefix: str | None = None) -> list[str]:
    """Retorna hechos contextuales verificables relevantes para la consulta (Tier 3).

    Nunca especula resultados electorales. Tono pedagógico y técnico.
    """
    notes: list[str] = []

    is_900k = (
        (mesa_prefix is not None and mesa_prefix.startswith("9"))
        or any(w in q_norm for w in {
            "fantasma", "fantasm", "inventad", "no existen", "no hay", "falsa",
            "falso", "dudosa", "ghost", "rural", "nativa", "amazonia", "comunidad",
            "centro poblado", "remota",
        })
    )
    if is_900k:
        notes.extend(_MESA_900K_FACTS)

    if any(w in q_norm for w in {
        "stae", "transmision", "transmitid", "sistema", "acta", "imagen",
        "fraude", "trampa", "manipul", "irregular",
    }):
        notes.extend(_STAE_FACTS)

    if any(w in q_norm for w in {
        "fraude", "trampa", "manipul", "irregular", "solo gana", "siempre gana",
        "solo sale", "siempre sale", "sospech",
    }):
        notes.extend(_PROCESS_FACTS)
        notes.extend(_FRAUD_RESPONSE_FACTS)

    if any(w in q_norm for w in {"lunes", "13 de abril", "instalacion diferid"}):
        notes.extend(_LUNES13_FACTS)

    if any(w in q_norm for w in {
        "pachacamac", "lurin", "sjm", "san juan de miraflores", "paterson", "orlando",
    }):
        notes.extend(_GEO_PATTERNS)

    if any(w in q_norm for w in {"rural", "amazonia", "comunidad", "participacion alta", "abstencion baja"}):
        notes.extend(_RURAL_VOTE_FACTS)

    if any(w in q_norm for w in {
        "resultado", "votos nacionales", "cuantos votos", "porcentaje", "total nacional",
        "quien gano", "quien gana", "cuanto saco", "puntaje nacional",
    }) and not mesa_prefix:
        notes.extend(_ELECTION_RESULTS_2026)

    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for note in notes:
        if note not in seen:
            seen.add(note)
            unique.append(note)
    return unique


def get_fallback_qualitative(q_norm: str) -> list[str]:
    """Devuelve el compendio cualitativo completo para la consulta (Tier 3 fallback).

    Usado cuando no hay datos en cache ni en la API ONPE.
    Retorna todos los hechos verificables relevantes para el tema de la consulta.
    Si no hay match de tema, retorna una nota genérica.
    """
    matched: list[str] = []
    for keywords, facts in _TOPIC_MAP:
        if any(kw in q_norm for kw in keywords):
            matched.extend(facts)

    # Deduplicate
    seen: set[str] = set()
    unique: list[str] = []
    for fact in matched:
        if fact not in seen:
            seen.add(fact)
            unique.append(fact)

    if not unique:
        unique = [
            "No tengo datos suficientes en cache local ni en la API ONPE para responder esta consulta. "
            "Para datos oficiales usa: resultadoelectoral.onpe.gob.pe o consulta mesas específicas "
            "con onpe_get_mesa / onpe_get_mesas_batch.",
        ]
    return unique


def data_tier_label(source: str) -> str:
    """Retorna el tier de datos según la fuente del resultado."""
    _tier1 = {"sqlite", "sqlite_cache", "sqlite_query_cache"}
    _tier2 = {"onpe_live", "onpe_api"}
    _tier3 = {"sqlite_empty", "nlu_fallback", "clarification_needed", "knowledge_base"}
    if source in _tier1 or source.startswith("sqlite"):
        return "tier_1_local_cache"
    if source in _tier2 or source.startswith("onpe"):
        return "tier_2_onpe_api"
    if source in _tier3 or source.startswith("clarification"):
        return "tier_3_knowledge_base"
    return "tier_4_external"
