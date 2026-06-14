# Plan: Extensión de `onpe-mcp` para Segunda Vuelta 2026

> **Estado:** Plan listo para ejecución futura — sin cambios al código.  
> **Scraper de referencia:** https://github.com/oscarzamora/onpe-scraper-2026-2  
> **Fecha del análisis:** 2026-06-08  
> **Última revisión:** 2026-06-11 — validado contra datos reales del scraper (98.25% contabilizado); incorpora carpeta `resumen/`, modelo híbrido de agregaciones, corrección del modelo exterior AMERICA/ambito, routing `onpe_chat` por etapas, y 9xxxxx mesas documentadas.

---

## Contexto de uso

El scraper **sigue actualizándose en tiempo real** durante el escrutinio. El flujo es:

```
git pull (onpe-scraper-2026-2)  →  onpe_sv_refresh()  →  datos frescos en el MCP
```

Cuando el escrutinio esté al 100%, el MCP queda como herramienta de **análisis post-elección**: cómo se desempeñó la segunda vuelta, dónde ganó cada candidato, y cómo se compara con la primera vuelta mesa a mesa, ciudad a ciudad.

---

## Objetivos

1. **Segunda vuelta independiente** — datos, tablas y tools propias que no interfieren con primera vuelta.
2. **Refresco on-demand** — una sola tool (`onpe_sv_refresh`) para actualizar desde el repo del scraper sin pasos manuales.
3. **Comparaciones entre vueltas** — misma mesa, misma ciudad, mismo departamento: variación de participación, cambio de candidato ganador, diferencia de votos válidos.
4. **Mapa de transferencia de votos** — proyectar cuántos votos de primera vuelta "esperaban" ir a Keiko o Sánchez según la tendencia de cada agrupación, y contrastar esa proyección con los resultados reales de segunda vuelta.
5. **Análisis de locales reasignados** — 44 locales de votación fueron reubicados entre primera y segunda vuelta (~570 mesas). Medir si la participación cayó en esas mesas vs el resto, y exponer los motivos de cada reasignación.

---

## Contexto y análisis

### Lo que produce el scraper `onpe-scraper-2026-2`

Genera los mismos formatos de archivo que `onpescraper` (primera vuelta), **más una carpeta `resumen/` con agregados pre-computados**:

| Archivo | Descripción |
|---|---|
| `output/mesas_data.txt` | Una fila por mesa. Columnas: `codigo_mesa`, `id_eleccion`, `id_ubigeo`, `nombre_local_votacion`, `codigo_local_votacion`, `id_ambito_geografico`, `electores_habiles`, `votos_emitidos`, `votos_validos`, `total_asistentes`, `participacion_ciudadana`, `codigo_estado_acta`, `descripcion_estado_acta` |
| `output/votos.txt` | Una fila por mesa × partido. Columnas: `codigo_mesa`, `id_eleccion`, `partido_id`, `votos`, `pct_votos_validos`, `pct_votos_emitidos` |
| `output/agrupaciones.txt` | Catálogo de partidos (solo 2 + blancos/nulos/impugnados). `partido_id`, `codigo_op`, `nombre` |
| `output/ubicaciones.txt` | Jerarquía geográfica: `ubigeo`, `ambito`, `departamento`, `provincia`, `distrito`, `continente`, `pais`, `ciudad` |
| `output/locales.txt` | Locales con coordenadas: `codigo_local_votacion`, `nombre_local_votacion`, `ubigeo`, `lat`, `lon` |
| `resumen/resumen_nacional.txt` | **Pre-computado.** Totales nacionales por candidato: `id_eleccion`, `partido_id`, `nombre_candidato`, `nombre_agrupacion_politica`, `votos_validos`, `pct_votos_validos`, `pct_votos_emitidos`, `actas_contabilizadas_pct`, `contabilizadas`, `total_actas`, `participacion_ciudadana`, `fecha_actualizacion`, `fuente` |
| `resumen/resumen_departamentos.txt` | **Pre-computado.** Totales por departamento (ubigeo 010000–250000). Schema idéntico a resumen_nacional + `ubigeo`. |
| `resumen/resumen_provincias.txt` | **Pre-computado.** Totales por provincia peruana **y por país exterior** (ubigeos 910100=ARGELIA, 920100=ARGENTINA, etc.). 1,346 filas. |
| `resumen/resumen_cobertura_departamentos.txt` | **Pre-computado.** Cobertura de actas: `id_eleccion`, `ubigeo`, `nombre_departamento`, `actas_contabilizadas`, `pct_actas_contabilizadas`, `fuente`. Incluye 25 departamentos + 5 continentes (910000=AFRICA/6, 920000=AMERICAS/1490, 930000=ASIA/105, 940000=EUROPA/782, 950000=OCEANIA/20). |

### Hechos clave de la data real (validado 2026-06-11)

| Métrica | Valor |
|---|---|
| Total mesas | 92,766 |
| Mesas contabilizadas | 91,146 (98.25%) |
| Mesas pendientes | 9 |
| Mesas 9xxxxx (código especial) | **4,703** — mesas peruanas válidas con código numérico ≥ 900000 |
| Mesas exterior (ambito=2) | 2,543 |
| `id_eleccion` | 10 |
| `partido_id` Keiko | 8 (FUERZA POPULAR) |
| `partido_id` Sánchez | 10 (JUNTOS POR EL PERÚ) |
| Resultado nacional | Keiko 9,035,493 (50.003%) · Sánchez 9,034,466 (49.997%) |

### Mesas 9xxxxx — clarificación

Las mesas con código ≥ 900000 son **mesas peruanas válidas** (`id_ambito_geografico=1`, ubigeo normal). No son mesas especiales de exterior ni de categoría distinta. El prefijo numérico **no determina geografía** — solo `id_ubigeo` / `ubigeo` lo hace. Los usuarios preguntarán "¿qué son las mesas 900000?" — responder que son mesas regulares de Peru con código asignado en el bloque alto del rango numérico.

### Geografía exterior — ubigeos y jerarquía

```
Prefijo ubigeo  Continente       Ciudades  Mesas aprox.
91xxxx          ÁFRICA               6          35
92xxxx          AMÉRICAS            95       1,490
93xxxx          ASIA                35         105
94xxxx          EUROPA              67         782
95xxxx          OCEANÍA              7          20
```

Ubigeos en `ubicaciones.txt`: nivel **ciudad** (ej: `910101=ARGEL`).  
Ubigeos en `resumen_provincias.txt`: nivel **país** (ej: `910100=ARGELIA` — no está en `ubicaciones.txt`).  
Ubigeos en `resumen_cobertura_departamentos.txt`: nivel **continente** (`910000`, `920000`, …).  

> **Regla crítica:** nunca mezclar `ambito=peru` con exterior en los totales de "votos en el exterior". Usar siempre `id_ambito_geografico` o la columna `ambito` de `ubicaciones_sv` como discriminador. El continente `AMÉRICAS` incluye **peruanos en el exterior en América** (≠ votos de Perú doméstico).

### Candidatos de segunda vuelta

| `partido_id` SV | `nombre` |
|---|---|
| `8` | FUERZA POPULAR (Keiko Fujimori) |
| `10` | JUNTOS POR EL PERÚ (Roberto Sánchez) |
| `80` | VOTOS EN BLANCO |
| `81` | VOTOS NULOS |
| `82` | VOTOS IMPUGNADOS |

> Los partido_id SV son asignados por ONPE en el proceso de segunda vuelta. Confirmar con el endpoint `/proceso/proceso-electoral-activo` de la URL SV antes de hardcodear.

### API viva de segunda vuelta

- **Base URL:** `https://resultadosegundavuelta.onpe.gob.pe/presentacion-backend`
- **Endpoint acta:** `/actas/buscar/mesa?codigoMesa={codigo}&idEleccion={id}`
- **Proceso activo:** `/proceso/proceso-electoral-activo`
- **Ubigeos:** `/ubigeos/dep-prov-distritos?idEleccion={id}`
- **Mismo mecanismo:** `curl_cffi` con `impersonate="chrome124"` (obligatorio)
- **Mismo envelope:** `{"success": true, "data": [...]}`
- **Misma lógica `_pick_mesa_acta`** (prioridad `Contabilizada` + `idEleccion`)

### Problema de colisión de PKs

Los `codigo_mesa` son los **mismos** en ambas vueltas (locales físicos). La tabla `mesas_data` usa `codigo_mesa` como PK única. Cargar SV en las mismas tablas sobrescribiría la primera vuelta.

**Decisión de diseño: tablas separadas** (`mesas_sv`, `votos_sv`, etc.) — cero cambios al esquema actual, cero riesgo de regresión. Las comparaciones se hacen con JOINs explícitos por `codigo_mesa` o `ubigeo`.

---

## Arquitectura de la extensión

```
onpe-mcp/
├── src/onpe_mcp/
│   ├── config.py           ← +2 campos: sv_scraper_root, sv_output_dir
│   ├── knowledge_base.py   ← +mapa de transferencia de votos (dict estático)
│   ├── storage.py          ← +6 tablas SV + 6 métodos nuevos
│   ├── onpe_api.py         ← +1 constante BASE_URL_SV
│   ├── server.py           ← +6 tools nuevas + extensión onpe_chat
│   └── (resto sin cambios)
└── .env.example            ← +2 variables de entorno SV
```

---

## Fase 1 — Configuración (`config.py`)

### Variables de entorno nuevas

| Variable | Default | Descripción |
|---|---|---|
| `ONPE_SV_SCRAPER_ROOT` | `../onpe-scraper-2026-2` | Raíz del repo del scraper SV |
| `ONPE_SV_OUTPUT_DIR` | `$ONPE_SV_SCRAPER_ROOT/output` | Directorio con los `.txt` del scraper SV |
| `ONPE_SV_RESUMEN_DIR` | `$ONPE_SV_SCRAPER_ROOT/resumen` | **Nuevo.** Directorio con los `resumen_*.txt` pre-computados |

### Cambios en `Settings`

```python
@dataclass(frozen=True)
class Settings:
    # ... campos existentes (sin cambios) ...
    sv_scraper_root: Path   # nuevo
    sv_output_dir: Path     # nuevo
    sv_resumen_dir: Path    # nuevo
```

### Inicialización en `from_env()`

```python
sv_scraper_root = Path(
    os.getenv(
        "ONPE_SV_SCRAPER_ROOT",
        str((workspace_default / ".." / "onpe-scraper-2026-2").resolve()),
    )
).resolve()
sv_output_dir = Path(
    os.getenv("ONPE_SV_OUTPUT_DIR", str((sv_scraper_root / "output").resolve()))
).resolve()
sv_resumen_dir = Path(
    os.getenv("ONPE_SV_RESUMEN_DIR", str((sv_scraper_root / "resumen").resolve()))
).resolve()
```

Agregar `sv_scraper_root=sv_scraper_root, sv_output_dir=sv_output_dir, sv_resumen_dir=sv_resumen_dir` al `return Settings(...)`.

---

## Fase 2 — Mapa de transferencia de votos (`knowledge_base.py`)

### El twist: el plan editorial estaba equivocado

El plan original asignaba `peso_keiko ∈ {0.0, 0.6, 1.0}` basándose en alineamiento ideológico. Al comparar con los datos reales de 86,124 mesas ya contabilizadas (modelo NNLS calibrado en `onpe.ozamora.com/proyeccion.php`) se encontraron tres problemas fundamentales:

1. **~9.2% de abstención inter-vuelta** — votantes que no aparecen en 2V. El plan asumía 0%.
2. **8+ partidos completamente invertidos** — Podemos Perú (catalogado "pro-Keiko") va 94% Sánchez; Partido Cívico Obras, Somos Perú, Partido Democrático Federal, Partido Demócrata Verde, Progresemos, Salvemos al Perú, Perú Acción — todos van mayoritariamente a Sánchez a pesar de estar catalogados como Keiko.
3. **Anti-fujimorismo infraestimado** — APP/Acuña (plan: 100% Keiko) en realidad 44.7% Keiko / 45.9% Sánchez. Fuerza y Libertad (plan: Keiko) va 63.9% Sánchez.

**Estructura corregida — 3 pesos + abstención implícita:**
- `peso_keiko` + `peso_sanchez` + `peso_bn` (blanco/nulo) ≤ 1.0
- `peso_abs` implícito = `1.0 - (peso_keiko + peso_sanchez + peso_bn)`
- `fuente`: `"nnls_calibrado"` = datos reales de 86K mesas | `"editorial"` = solo estimación ideológica

Los pesos NNLS son los usados para proyección. Los partidos sin datos calibrados usan pesos editoriales conservadores.

```python
# ──────────────────────────────────────────────────────────────────────────────
# Mapa de transferencia de votos: 1ª vuelta → 2ª vuelta
#
# Estructura por entrada:
#   peso_keiko  : fracción del electorado → Keiko (NNLS calibrado o editorial)
#   peso_sanchez: fracción del electorado → Sánchez
#   peso_bn     : fracción → voto en blanco/nulo en 2V
#   peso_abs    : IMPLÍCITO = 1.0 - (keiko + sanchez + bn)  ← abstención inter-vuelta
#
# Fuentes:
#   "nnls_calibrado" = calibrado con datos reales de 86K mesas 2V (onpe.ozamora.com/proyeccion.php)
#   "editorial"      = estimación ideológica/histórica (no calibrado con datos 2V)
#
# IMPORTANTE: para la proyección al 100%, usar solo los pesos aquí —
# NO el campo `sv` que era el alineamiento binario del plan original.
# ──────────────────────────────────────────────────────────────────────────────
TRANSFER_MAP: dict[str, dict] = {
    # ── NNLS calibrado ────────────────────────────────────────────────────────
    "renovacion popular":                  {"peso_keiko": 0.991, "peso_sanchez": 0.000, "peso_bn": 0.009, "fuente": "nnls_calibrado", "candidato_1v": "López Aliaga",          "sv_plan": "keiko",    "nota": "✅ confirma plan"},
    "ahora nacion":                        {"peso_keiko": 0.000, "peso_sanchez": 0.966, "peso_bn": 0.034, "fuente": "nnls_calibrado", "candidato_1v": "Alfonso López Chau",    "sv_plan": "keiko",    "nota": "🔴 plan decía Keiko — datos: 97% Sánchez"},
    "alianza electoral venceremos":        {"peso_keiko": 0.000, "peso_sanchez": 0.977, "peso_bn": 0.023, "fuente": "nnls_calibrado", "candidato_1v": "Ronald Atencio",        "sv_plan": "sanchez",  "nota": "✅ confirma plan"},
    "peru moderno":                        {"peso_keiko": 0.000, "peso_sanchez": 1.000, "peso_bn": 0.000, "fuente": "nnls_calibrado", "candidato_1v": "Carlos Jaico",          "sv_plan": "keiko",    "nota": "🔴 plan decía Keiko — datos: 100% Sánchez"},
    "fe en el peru":                       {"peso_keiko": 0.000, "peso_sanchez": 0.884, "peso_bn": 0.116, "fuente": "nnls_calibrado", "candidato_1v": "Álvaro Paz de la Barra","sv_plan": "keiko",    "nota": "🔴 plan decía Keiko — datos: 88% Sánchez"},
    "avanza pais":                         {"peso_keiko": 0.720, "peso_sanchez": 0.187, "peso_bn": 0.092, "fuente": "nnls_calibrado", "candidato_1v": "José Williams",         "sv_plan": "keiko",    "nota": "⚠️ fuga material — plan 100% Keiko, datos 72%"},
    "fuerza popular":                      {"peso_keiko": 0.956, "peso_sanchez": 0.000, "peso_bn": 0.044, "fuente": "nnls_calibrado", "candidato_1v": "Keiko Fujimori",        "sv_plan": "keiko",    "nota": "✅ confirma plan"},
    "fuerza y libertad":                   {"peso_keiko": 0.322, "peso_sanchez": 0.639, "peso_bn": 0.024, "fuente": "nnls_calibrado", "candidato_1v": "Giannina Molinelli",    "sv_plan": "keiko",    "nota": "🔴 invertido — plan Keiko, datos 64% Sánchez"},
    "juntos por el peru":                  {"peso_keiko": 0.000, "peso_sanchez": 0.974, "peso_bn": 0.026, "fuente": "nnls_calibrado", "candidato_1v": "Roberto Sánchez",       "sv_plan": "sanchez",  "nota": "✅ confirma plan"},
    "libertad popular":                    {"peso_keiko": 0.425, "peso_sanchez": 0.352, "peso_bn": 0.176, "fuente": "nnls_calibrado", "candidato_1v": "Rafael Belaunde",       "sv_plan": "keiko",    "nota": "⚠️ dividido real — plan Keiko, datos 42.5%/35.2%"},
    "partido aprista peruano":             {"peso_keiko": 0.856, "peso_sanchez": 0.040, "peso_bn": 0.104, "fuente": "nnls_calibrado", "candidato_1v": "Pitter Valderrama",     "sv_plan": "dividido", "nota": "⚠️ más Keiko — plan 60%, datos 85.6%"},
    "partido civico obras":                {"peso_keiko": 0.000, "peso_sanchez": 1.000, "peso_bn": 0.000, "fuente": "nnls_calibrado", "candidato_1v": "Ricardo Belmont",       "sv_plan": "keiko",    "nota": "🔴 invertido — plan Keiko, datos 100% Sánchez"},
    "partido de los trabajadores del estado": {"peso_keiko": 0.000, "peso_sanchez": 0.961, "peso_bn": 0.039, "fuente": "nnls_calibrado", "candidato_1v": "Napoleón Becerra",   "sv_plan": "sanchez",  "nota": "✅ confirma plan"},
    "partido del buen gobierno":           {"peso_keiko": 0.560, "peso_sanchez": 0.339, "peso_bn": 0.101, "fuente": "nnls_calibrado", "candidato_1v": "Jorge Nieto",           "sv_plan": "sanchez",  "nota": "⚠️ dividido — plan Sánchez, datos 56% Keiko"},
    "partido democrata unido":             {"peso_keiko": 0.000, "peso_sanchez": 1.000, "peso_bn": 0.000, "fuente": "nnls_calibrado", "candidato_1v": "Charlie Carrasco",      "sv_plan": "keiko",    "nota": "🔴 invertido — plan Keiko, datos 100% Sánchez"},
    "partido democrata verde":             {"peso_keiko": 0.000, "peso_sanchez": 0.903, "peso_bn": 0.097, "fuente": "nnls_calibrado", "candidato_1v": "Alex Gonzales",         "sv_plan": "keiko",    "nota": "🔴 invertido — plan Keiko, datos 90% Sánchez"},
    "partido democratico federal":         {"peso_keiko": 0.000, "peso_sanchez": 0.853, "peso_bn": 0.147, "fuente": "nnls_calibrado", "candidato_1v": "Armando Masse",         "sv_plan": "keiko",    "nota": "🔴 invertido — plan Keiko, datos 85% Sánchez"},
    "somos peru":                          {"peso_keiko": 0.374, "peso_sanchez": 0.626, "peso_bn": 0.000, "fuente": "nnls_calibrado", "candidato_1v": "George Forsyth",        "sv_plan": "dividido", "nota": "🔴 invertido — plan 60% Keiko, datos 63% Sánchez"},
    "frente de la esperanza":              {"peso_keiko": 0.000, "peso_sanchez": 0.987, "peso_bn": 0.013, "fuente": "nnls_calibrado", "candidato_1v": "Fernando Olivera",      "sv_plan": "sanchez",  "nota": "✅ confirma plan"},
    "partido morado":                      {"peso_keiko": 0.000, "peso_sanchez": 0.771, "peso_bn": 0.149, "fuente": "nnls_calibrado", "candidato_1v": "Mesías Guevara",        "sv_plan": "sanchez",  "nota": "✅ confirma (Σ=0.921, abstención 7.9%)"},
    "pais para todos":                     {"peso_keiko": 0.822, "peso_sanchez": 0.106, "peso_bn": 0.050, "fuente": "nnls_calibrado", "candidato_1v": "Carlos Álvarez",        "sv_plan": "keiko",    "nota": "✅ confirma (Σ=0.977)"},
    "partido patriotico":                  {"peso_keiko": 0.000, "peso_sanchez": 0.905, "peso_bn": 0.095, "fuente": "nnls_calibrado", "candidato_1v": "Herbert Caller",        "sv_plan": "keiko",    "nota": "🔴 invertido — plan Keiko, datos 90% Sánchez"},
    "cooperacion popular":                 {"peso_keiko": 0.000, "peso_sanchez": 1.000, "peso_bn": 0.000, "fuente": "nnls_calibrado", "candidato_1v": "Yonhy Lescano",         "sv_plan": "sanchez",  "nota": "✅ confirma plan"},
    "integridad democratica":              {"peso_keiko": 0.905, "peso_sanchez": 0.000, "peso_bn": 0.095, "fuente": "nnls_calibrado", "candidato_1v": "Wolfgang Grozo",        "sv_plan": "keiko",    "nota": "✅ confirma plan"},
    "peru libre":                          {"peso_keiko": 0.000, "peso_sanchez": 1.000, "peso_bn": 0.000, "fuente": "nnls_calibrado", "candidato_1v": "Vladimir Cerrón",       "sv_plan": "sanchez",  "nota": "✅ confirma plan"},
    "peru accion":                         {"peso_keiko": 0.000, "peso_sanchez": 0.918, "peso_bn": 0.074, "fuente": "nnls_calibrado", "candidato_1v": "Francisco Diez-Canseco","sv_plan": "keiko",    "nota": "🔴 invertido — plan Keiko, datos 92% Sánchez"},
    "sicreo":                              {"peso_keiko": 0.632, "peso_sanchez": 0.254, "peso_bn": 0.114, "fuente": "nnls_calibrado", "candidato_1v": "Carlos Espi",           "sv_plan": "keiko",    "nota": "✅ confirma plan"},
    "podemos peru":                        {"peso_keiko": 0.000, "peso_sanchez": 0.942, "peso_bn": 0.058, "fuente": "nnls_calibrado", "candidato_1v": "José Luna",             "sv_plan": "keiko",    "nota": "🔴 invertido — plan Keiko, datos 94% Sánchez"},
    "primero la gente":                    {"peso_keiko": 0.330, "peso_sanchez": 0.412, "peso_bn": 0.130, "fuente": "nnls_calibrado", "candidato_1v": "Marisol Pérez Tello",   "sv_plan": "sanchez",  "nota": "⚠️ leve Sánchez (Σ=0.873, abstención 12.7%)"},
    "progresemos":                         {"peso_keiko": 0.000, "peso_sanchez": 0.964, "peso_bn": 0.036, "fuente": "nnls_calibrado", "candidato_1v": "Paul Jaimes",           "sv_plan": "keiko",    "nota": "🔴 invertido — plan Keiko, datos 96% Sánchez"},
    "salvemos al peru":                    {"peso_keiko": 0.000, "peso_sanchez": 0.817, "peso_bn": 0.183, "fuente": "nnls_calibrado", "candidato_1v": "Antonio Ortiz",         "sv_plan": "keiko",    "nota": "🔴 invertido — plan Keiko, datos 82% Sánchez"},
    "un camino diferente":                 {"peso_keiko": 0.592, "peso_sanchez": 0.307, "peso_bn": 0.067, "fuente": "nnls_calibrado", "candidato_1v": "Rosario Fernández",     "sv_plan": "keiko",    "nota": "✅ confirma (Σ=0.966)"},
    "unidad nacional":                     {"peso_keiko": 0.886, "peso_sanchez": 0.000, "peso_bn": 0.114, "fuente": "nnls_calibrado", "candidato_1v": "Roberto Chiabra",       "sv_plan": "keiko",    "nota": "✅ confirma plan"},
    "alianza para el progreso":            {"peso_keiko": 0.447, "peso_sanchez": 0.459, "peso_bn": 0.094, "fuente": "nnls_calibrado", "candidato_1v": "César Acuña",           "sv_plan": "keiko",    "nota": "⚠️ plan 100% Keiko — datos casi 50/50 (anti-fujimorismo infraestimado)"},
    # Votos especiales (calibrados)
    "_blancos_1v":                         {"peso_keiko": 0.326, "peso_sanchez": 0.317, "peso_bn": 0.147, "fuente": "nnls_calibrado", "candidato_1v": "(blanco 1V)",           "sv_plan": None,       "nota": "Σ=0.790, abstención 21%"},
    "_nulos_1v":                           {"peso_keiko": 0.360, "peso_sanchez": 0.292, "peso_bn": 0.131, "fuente": "nnls_calibrado", "candidato_1v": "(nulo 1V)",             "sv_plan": None,       "nota": "Σ=0.783, abstención 22%"},
    "_abstencion_1v":                      {"peso_keiko": 0.000, "peso_sanchez": 0.000, "peso_bn": 0.000, "fuente": "nnls_calibrado", "candidato_1v": "(abstención 1V)",       "sv_plan": None,       "nota": "No se movilizan en 2V"},
    # ── Editorial (sin datos 2V calibrados) ───────────────────────────────────
    "frente popular agricola fia del peru":{"peso_keiko": 0.10,  "peso_sanchez": 0.800, "peso_bn": 0.010, "fuente": "editorial",       "candidato_1v": "(sin candidato)",       "sv_plan": "sanchez",  "nota": "históricamente rural-agrarista — sin datos NNLS"},
    "partido ciudadanos por el peru":      {"peso_keiko": 0.50,  "peso_sanchez": 0.400, "peso_bn": 0.010, "fuente": "editorial",       "candidato_1v": "(sin candidato)",       "sv_plan": "dividido", "nota": "sin datos NNLS — estimación conservadora"},
    "peru primero":                        {"peso_keiko": 0.50,  "peso_sanchez": 0.400, "peso_bn": 0.010, "fuente": "editorial",       "candidato_1v": "Mario Vizcarra",        "sv_plan": "keiko",    "nota": "sin datos NNLS — estimación conservadora"},
    "prin":                                {"peso_keiko": 0.50,  "peso_sanchez": 0.400, "peso_bn": 0.010, "fuente": "editorial",       "candidato_1v": "Walter Chirinos",       "sv_plan": "keiko",    "nota": "sin datos NNLS — estimación conservadora"},
}
```

> **Nota sobre pesos editoriales:** Los 4 partidos sin datos NNLS usan pesos 50/40/1 (neutral), NO el 100% original del plan. Esto es deliberadamente conservador: los datos reales demuestran que ningún partido transfiere al 100%.  
> **⚠️ Bug fix #non-blocking-2 — fallback asimétrico:** El fallback 50/40/1 en `rebuild_proyeccion_sv` para partidos no en mapa tiene un +10pp sesgo hacia Keiko. En producción, emitir un `logger.warning(f"Sin mapa para partido: {nombre}")` para detectar cualquier partido 1V no mapeado. Si hay muchos unmapped, abortar y pedir al implementador que los agregue.  
> **Helper de auditoría:** Agregar `_audit_transfer_coverage(conn) -> list[str]` en `DataStore` que ejecute `SELECT DISTINCT a.nombre FROM agrupaciones a WHERE a.partido_id NOT IN ('80','81','82')` y compare contra TRANSFER_MAP — debe retornar lista vacía si cobertura es 100%.

**Lookup helper** (también en `knowledge_base.py`):

```python
import unicodedata

def _norm_kb(text: str) -> str:
    base = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in base if not unicodedata.combining(ch)).casefold().strip()

def get_transfer(nombre_partido: str) -> dict | None:
    """Retorna el entry de TRANSFER_MAP para un partido de 1ª vuelta, o None.
    
    El dict contiene: peso_keiko, peso_sanchez, peso_bn, fuente, nota.
    peso_abs = 1.0 - (peso_keiko + peso_sanchez + peso_bn)  ← abstención implícita.
    Si fuente == 'nnls_calibrado', los pesos son datos reales de 86K mesas.
    """
    return TRANSFER_MAP.get(_norm_kb(nombre_partido))
```

---

## Fase 3 — Esquema de base de datos (`storage.py`)

### Tablas nuevas (en `_init_schema`)

**Arquitectura de tablas:** 3 grupos con responsabilidades distintas.

```sql
-- ═══════════════════════════════════════════════════════════════════════════
-- GRUPO A: Datos crudos de segunda vuelta (fuente: output/)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS mesas_sv (
    codigo_mesa             TEXT PRIMARY KEY,
    ubigeo                  TEXT,
    local_votacion          TEXT,
    codigo_local_votacion   TEXT,
    id_ambito_geografico    INTEGER,   -- 1=peru, 2=exterior
    electores_habiles       INTEGER,
    votos_emitidos          INTEGER,
    votos_validos           INTEGER,
    total_asistentes        INTEGER,
    participacion_ciudadana REAL,
    estado_acta             TEXT,      -- 'C'=contabilizada, 'P'=pendiente
    fetched_at              TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mesas_sv_ubigeo  ON mesas_sv (ubigeo);
CREATE INDEX IF NOT EXISTS idx_mesas_sv_estado  ON mesas_sv (estado_acta);
CREATE INDEX IF NOT EXISTS idx_mesas_sv_local   ON mesas_sv (codigo_local_votacion);
CREATE INDEX IF NOT EXISTS idx_mesas_sv_ambito  ON mesas_sv (id_ambito_geografico);

CREATE TABLE IF NOT EXISTS votos_sv (
    codigo_mesa TEXT NOT NULL,
    partido_id  TEXT NOT NULL,
    votos       INTEGER,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (codigo_mesa, partido_id)
);
CREATE INDEX IF NOT EXISTS idx_votos_sv_partido ON votos_sv (partido_id);

CREATE TABLE IF NOT EXISTS agrupaciones_sv (
    partido_id TEXT PRIMARY KEY,
    nombre     TEXT,
    fetched_at TEXT NOT NULL
);

-- Geo catálogo (fuente: output/ubicaciones.txt — 2,103 ubigeos)
CREATE TABLE IF NOT EXISTS ubicaciones_sv (
    ubigeo       TEXT PRIMARY KEY,
    ambito       TEXT NOT NULL,   -- 'peru' | 'exterior'
    departamento TEXT,
    provincia    TEXT,
    distrito     TEXT,
    continente   TEXT,            -- solo exterior (ÁFRICA, AMÉRICAS, ASIA, EUROPA, OCEANÍA)
    pais         TEXT,            -- solo exterior
    ciudad       TEXT,            -- solo exterior
    loaded_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ub_sv_ambito  ON ubicaciones_sv (ambito);
CREATE INDEX IF NOT EXISTS idx_ub_sv_dpto    ON ubicaciones_sv (departamento);
CREATE INDEX IF NOT EXISTS idx_ub_sv_prov    ON ubicaciones_sv (provincia);
CREATE INDEX IF NOT EXISTS idx_ub_sv_dist    ON ubicaciones_sv (distrito);
CREATE INDEX IF NOT EXISTS idx_ub_sv_pais    ON ubicaciones_sv (pais);
CREATE INDEX IF NOT EXISTS idx_ub_sv_cont    ON ubicaciones_sv (continente);

-- Locales de votación (fuente: output/locales.txt)
CREATE TABLE IF NOT EXISTS locales_sv (
    codigo_local_votacion TEXT NOT NULL,
    ubigeo               TEXT NOT NULL,
    nombre_local         TEXT,
    lat                  REAL,
    lon                  REAL,
    loaded_at            TEXT NOT NULL,
    PRIMARY KEY (codigo_local_votacion, ubigeo)
);
CREATE INDEX IF NOT EXISTS idx_locales_sv_ubigeo ON locales_sv (ubigeo);

-- ═══════════════════════════════════════════════════════════════════════════
-- GRUPO B: Agregados pre-computados por el scraper (fuente: resumen/)
-- Cargados directamente — NO calculados por el MCP. Más autoritativos.
-- ═══════════════════════════════════════════════════════════════════════════

-- Nacional (fuente: resumen/resumen_nacional.txt — ~4 filas, una por candidato+blancos+nulos)
CREATE TABLE IF NOT EXISTS sv_resumen_nacional (
    partido_id                TEXT NOT NULL,
    nombre_candidato          TEXT,
    nombre_agrupacion         TEXT,
    votos_validos             INTEGER,
    pct_votos_validos         REAL,
    pct_votos_emitidos        REAL,
    actas_contabilizadas_pct  REAL,
    contabilizadas            INTEGER,
    total_actas               INTEGER,
    participacion_ciudadana   REAL,
    fecha_actualizacion       TEXT,
    fuente                    TEXT,     -- 'onpe_api' | 'local_agregado'
    loaded_at                 TEXT NOT NULL,
    PRIMARY KEY (partido_id)
);

-- Por departamento (25 filas Peru) + agregados continente (5 filas 910000-950000)
-- Fuente: resumen/resumen_departamentos.txt
CREATE TABLE IF NOT EXISTS sv_resumen_departamentos (
    ubigeo                   TEXT NOT NULL,
    partido_id               TEXT NOT NULL,
    nombre_candidato         TEXT,
    nombre_agrupacion        TEXT,
    votos_validos            INTEGER,
    pct_votos_validos        REAL,
    pct_votos_emitidos       REAL,
    total_votos_validos_geo  INTEGER,
    total_votos_emitidos_geo INTEGER,
    fuente                   TEXT,
    loaded_at                TEXT NOT NULL,
    PRIMARY KEY (ubigeo, partido_id)
);
CREATE INDEX IF NOT EXISTS idx_sv_rdept_ubigeo ON sv_resumen_departamentos (ubigeo);

-- Por provincia (Peru) + por país exterior (910100=ARGELIA, 920100=ARGENTINA, etc.)
-- Fuente: resumen/resumen_provincias.txt — 1,346 filas
-- nombre_geo: nombre textual del país exterior (ej: "ARGENTINA") para lookup por nombre
CREATE TABLE IF NOT EXISTS sv_resumen_provincias (
    ubigeo                   TEXT NOT NULL,
    partido_id               TEXT NOT NULL,
    nombre_geo               TEXT,            -- nombre departamento (Peru) o nombre país (exterior)
    nombre_candidato         TEXT,
    nombre_agrupacion        TEXT,
    votos_validos            INTEGER,
    pct_votos_validos        REAL,
    pct_votos_emitidos       REAL,
    total_votos_validos_geo  INTEGER,
    total_votos_emitidos_geo INTEGER,
    fuente                   TEXT,
    loaded_at                TEXT NOT NULL,
    PRIMARY KEY (ubigeo, partido_id)
);
CREATE INDEX IF NOT EXISTS idx_sv_rprov_ubigeo    ON sv_resumen_provincias (ubigeo);
CREATE INDEX IF NOT EXISTS idx_sv_rprov_nombre_geo ON sv_resumen_provincias (nombre_geo);

-- Cobertura de actas por departamento + continentes
-- Fuente: resumen/resumen_cobertura_departamentos.txt — 31 filas
CREATE TABLE IF NOT EXISTS sv_resumen_cobertura (
    ubigeo                   TEXT PRIMARY KEY,
    nombre_geo               TEXT,
    actas_contabilizadas     INTEGER,
    pct_actas_contabilizadas REAL,
    fuente                   TEXT,
    loaded_at                TEXT NOT NULL
);

-- ═══════════════════════════════════════════════════════════════════════════
-- GRUPO C: Agregados CTAS — niveles NO cubiertos por resumen/
-- (solo distrito Peru y ciudad exterior)
-- ═══════════════════════════════════════════════════════════════════════════

-- Distrito (Peru) — PK: (distrito, provincia, departamento)
CREATE TABLE IF NOT EXISTS sv_agg_distrito (
    distrito             TEXT NOT NULL,
    provincia            TEXT NOT NULL,
    departamento         TEXT NOT NULL,
    total_mesas          INTEGER DEFAULT 0,
    mesas_contabilizadas INTEGER DEFAULT 0,
    electores_habiles    INTEGER DEFAULT 0,
    votos_emitidos       INTEGER DEFAULT 0,
    votos_validos        INTEGER DEFAULT 0,
    votos_keiko          INTEGER DEFAULT 0,
    votos_sanchez        INTEGER DEFAULT 0,
    votos_blancos        INTEGER DEFAULT 0,
    votos_nulos          INTEGER DEFAULT 0,
    votos_impugnados     INTEGER DEFAULT 0,
    rebuilt_at           TEXT NOT NULL,
    PRIMARY KEY (distrito, provincia, departamento)
);

-- Ciudad exterior — PK: (ciudad, pais)
-- Nota: pais aquí es el nombre textual (ej: "ARGENTINA"), continente es el nombre textual.
-- No confundir con ubigeo-nivel-país de resumen_provincias.
CREATE TABLE IF NOT EXISTS sv_agg_ciudad (
    ciudad               TEXT NOT NULL,
    pais                 TEXT NOT NULL,
    continente           TEXT NOT NULL,
    ambito               TEXT NOT NULL DEFAULT 'exterior',
    total_mesas          INTEGER DEFAULT 0,
    mesas_contabilizadas INTEGER DEFAULT 0,
    electores_habiles    INTEGER DEFAULT 0,
    votos_emitidos       INTEGER DEFAULT 0,
    votos_validos        INTEGER DEFAULT 0,
    votos_keiko          INTEGER DEFAULT 0,
    votos_sanchez        INTEGER DEFAULT 0,
    votos_blancos        INTEGER DEFAULT 0,
    votos_nulos          INTEGER DEFAULT 0,
    votos_impugnados     INTEGER DEFAULT 0,
    rebuilt_at           TEXT NOT NULL,
    PRIMARY KEY (ciudad, pais)
);
CREATE INDEX IF NOT EXISTS idx_sv_agg_ciudad_pais ON sv_agg_ciudad (pais);

-- ═══════════════════════════════════════════════════════════════════════════
-- GRUPO D: Proyección y transferencia de votos
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS votos_sv_by_ubigeo_partido (
    ubigeo      TEXT NOT NULL,
    partido_id  TEXT NOT NULL,
    total_votos INTEGER NOT NULL,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (ubigeo, partido_id)
);

CREATE TABLE IF NOT EXISTS voto_transfer_map (
    nombre_partido_norm TEXT PRIMARY KEY,
    nombre_partido      TEXT NOT NULL,
    candidato_1v        TEXT,
    sv_plan             TEXT,                -- alineamiento editorial original ('keiko'/'sanchez'/'dividido'/NULL)
    peso_keiko          REAL NOT NULL,       -- fracción → Keiko (NNLS o editorial)
    peso_sanchez        REAL NOT NULL,       -- fracción → Sánchez
    peso_bn             REAL NOT NULL,       -- fracción → blanco/nulo en 2V
    -- peso_abs IMPLÍCITO: 1.0 - (peso_keiko + peso_sanchez + peso_bn) = abstención inter-vuelta
    fuente              TEXT NOT NULL,       -- 'nnls_calibrado' | 'editorial'
    nota                TEXT,               -- descripción de sorpresas o confirmaciones
    seeded_at           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proyeccion_sv_by_ubigeo (
    ubigeo                    TEXT PRIMARY KEY,
    votos_proyectados_keiko   INTEGER NOT NULL DEFAULT 0,
    votos_proyectados_sanchez INTEGER NOT NULL DEFAULT 0,
    votos_proyectados_bn      INTEGER NOT NULL DEFAULT 0,  -- blanco/nulo proyectado (abstención separada)
    votos_reales_keiko        INTEGER,
    votos_reales_sanchez      INTEGER,
    delta_keiko               INTEGER,
    delta_sanchez             INTEGER,
    rebuilt_at                TEXT NOT NULL
);

-- ═══════════════════════════════════════════════════════════════════════════
-- GRUPO E: Locales reasignados
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS locales_reasignados_sv (
    nro                    INTEGER PRIMARY KEY,
    odpe                   TEXT,
    departamento           TEXT,
    provincia              TEXT,
    distrito               TEXT,
    ccpp                   TEXT,
    nombre_local_original  TEXT NOT NULL,
    nombre_local_nuevo     TEXT,
    motivo                 TEXT,
    mesas_a_reasignar      INTEGER,
    estado_parseo          TEXT,
    loaded_at              TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reasignados_dpto   ON locales_reasignados_sv (departamento);
CREATE INDEX IF NOT EXISTS idx_reasignados_dist   ON locales_reasignados_sv (distrito);
CREATE INDEX IF NOT EXISTS idx_reasignados_motivo ON locales_reasignados_sv (motivo);
```

### 10 métodos nuevos en `DataStore`

#### 1. `bootstrap_segunda_vuelta(output_dir, force=False)` → `dict`

Lee `mesas_data.txt`, `votos.txt`, `agrupaciones.txt` del scraper SV, los carga en `mesas_sv`/`votos_sv`/`agrupaciones_sv`. También carga `ubicaciones.txt` → `ubicaciones_sv` y `locales.txt` → `locales_sv`. Al finalizar:
- Backfill de `votos_sv_by_ubigeo_partido`
- Llama `bootstrap_resumen_sv(resumen_dir)` (carga los 4 archivos de resumen/)
- Llama `bootstrap_locales_reasignados(output_dir)` (carga el catálogo de reasignados)
- Llama `seed_transfer_map()` (idempotente — solo inserta si vacío)
- Llama `rebuild_sv_ctas_levels()` (solo distrito y ciudad, < 1s)
- Llama `rebuild_proyeccion_sv()` si hay datos de primera vuelta en `votos_by_ubigeo_partido`
- Guarda evento en `events.jsonl`

Column mapping `mesas_data.txt` SV → `mesas_sv`:

| Columna .txt | Columna DB | Tipo |
|---|---|---|
| `codigo_mesa` | `codigo_mesa` | TEXT PK |
| `id_ubigeo` | `ubigeo` | TEXT |
| `nombre_local_votacion` | `local_votacion` | TEXT |
| `codigo_local_votacion` | `codigo_local_votacion` | TEXT |
| `id_ambito_geografico` | `id_ambito_geografico` | INTEGER |
| `electores_habiles` | `electores_habiles` | INTEGER |
| `votos_emitidos` | `votos_emitidos` | INTEGER |
| `votos_validos` | `votos_validos` | INTEGER |
| `total_asistentes` | `total_asistentes` | INTEGER |
| `participacion_ciudadana` | `participacion_ciudadana` | REAL |
| `codigo_estado_acta` | `estado_acta` | TEXT |

> `blancos`/`nulos`/`impugnados` vienen de `votos.txt` con `partido_id` 80/81/82 — no están en `mesas_data.txt` SV.

> **Invariante 9xxxxx:** el campo `id_ambito_geografico` (1=peru, 2=exterior) es el único discriminador correcto. El prefijo del `codigo_mesa` NO determina geografía. Las 4,703 mesas con código ≥ 900000 son mesas peruanas normales.

#### 2. `bootstrap_resumen_sv(resumen_dir)` → `dict` (filas cargadas por tabla)

Carga los 4 archivos de `resumen/`. Usa `DELETE + INSERT` (no UPSERT): los resúmenes son escrituras completas cada vez, son pequeños (~KB) y representan el estado oficial ONPE.

**⚠️ Bug fix #non-blocking-3 — transaccional:** Todo el DELETE+INSERT debe estar dentro de una sola transacción. Un crash entre DELETE y INSERT dejaría las tablas vacías. Usar `BEGIN EXCLUSIVE` o el context manager de la conexión.

```python
def bootstrap_resumen_sv(self, resumen_dir: Path) -> dict[str, int]:
    """
    Carga los pre-computados del scraper SV en las tablas sv_resumen_*.
    Fuentes: resumen_nacional.txt, resumen_departamentos.txt,
             resumen_provincias.txt, resumen_cobertura_departamentos.txt
    DELETE + INSERT completo en UNA transacción (archivos pequeños, siempre autoritativos).
    
    resumen_provincias.txt: poblar nombre_geo con el nombre del departamento (Peru)
    o nombre del país (exterior) para lookup por nombre en query_sv_geo("pais_exterior").
    """
    with self._connect() as conn:
        conn.execute("BEGIN EXCLUSIVE")
        # DELETE todas las tablas resumen primero, luego INSERT
        conn.execute("DELETE FROM sv_resumen_nacional")
        conn.execute("DELETE FROM sv_resumen_departamentos")
        conn.execute("DELETE FROM sv_resumen_provincias")
        conn.execute("DELETE FROM sv_resumen_cobertura")
        # ... INSERT desde cada archivo ...
        conn.execute("COMMIT")
    ...
```

**Manejo de `fuente`:** preservar el campo `fuente` (`onpe_api` vs `local_agregado`) de cada fila en la DB. Exponerlo en las respuestas cuando sea relevante (indica si el número viene directamente de la API oficial o fue calculado localmente).

**Manejo de `fecha_actualizacion`:** preservar en DB. Sirve para responder "¿cuándo fue la última actualización?" sin requerir re-scrapeo.

**Ubigeos de `resumen_provincias.txt` para exterior:** usan el patrón `9XX100` (2 dígitos continente + 2 dígitos país + `00`). Estos **no están en `ubicaciones_sv`** (que tiene nivel ciudad, `9XX1XX`). La tabla `sv_resumen_provincias` se puede consultar directamente por ubigeo — no necesita JOIN con `ubicaciones_sv`.

#### 3. `get_mesa_sv_from_local(codigo_mesa)` → `dict | None`

Análogo a `get_mesa_from_local` pero sobre `mesas_sv + votos_sv + agrupaciones_sv`.

#### 4. `get_sv_resumen_nacional()` → `dict`

Lee desde `sv_resumen_nacional` (cargada de `resumen/resumen_nacional.txt`). O(1). Incluye `fuente` y `fecha_actualizacion` del scraper.

```python
{
    "total_actas": N,
    "contabilizadas": N,
    "pct_contabilizado": float,       # actas_contabilizadas_pct del archivo
    "participacion_ciudadana": float,
    "fecha_actualizacion": "2026-06-12T01:05:19Z",
    "fuente": "onpe_api",
    "candidatos": [
        {"partido_id": "8",  "nombre": "FUERZA POPULAR",     "votos": N, "pct_validos": float, "pct_emitidos": float},
        {"partido_id": "10", "nombre": "JUNTOS POR EL PERÚ", "votos": N, "pct_validos": float, "pct_emitidos": float},
    ],
    "blancos": N,
    "nulos": N,
    "impugnados": N,
}
```

#### 4. `get_comparacion_mesa(codigo_mesa)` → `dict`

JOIN directo entre `mesas_data`+`votos` (1V) y `mesas_sv`+`votos_sv` (2V) por `codigo_mesa`:

```python
{
    "codigo_mesa": "123456",
    "local_votacion": "IE SAN MARTIN",
    "ubigeo": "150101",
    "primera_vuelta": {
        "electores_habiles": N,
        "votos_emitidos": N,
        "votos_validos": N,
        "participacion_pct": float,
        "estado_acta": "C",
        "votos": [{"partido_id": "X", "nombre": "...", "votos": N}, ...]
    },
    "segunda_vuelta": {
        "electores_habiles": N,
        "votos_emitidos": N,
        "votos_validos": N,
        "participacion_pct": float,
        "estado_acta": "C",
        "votos": [
            {"partido_id": "8",  "nombre": "FUERZA POPULAR",     "votos": N, "pct": float},
            {"partido_id": "10", "nombre": "JUNTOS POR EL PERÚ", "votos": N, "pct": float},
        ]
    },
    "delta": {
        "votos_emitidos": N,       # 2V - 1V
        "participacion_pct": float,
        "ganador_1v": "...",        # partido con más votos en 1V
        "ganador_2v": "keiko|sanchez|empate",
        "cambio_ganador": bool,
    }
}
```

Retorna `{"found_1v": False}` / `{"found_2v": False}` si falta una de las dos vueltas para esa mesa.

#### 5. `query_sv_geo(nivel, **kwargs)` → `list[dict]`

Punto de entrada unificado para drill-down geográfico. Rutas a las tablas correctas según `nivel`:

| `nivel` | Tabla fuente | Lookup |
|---|---|---|
| `"nacional"` | `sv_resumen_nacional` | Pivota los 2 candidatos en 1 fila |
| `"continente"` | `sv_resumen_cobertura` WHERE ubigeo LIKE '9_0000' | 5 filas (910000-950000) |
| `"pais_exterior"` | `sv_resumen_provincias` WHERE ubigeo LIKE '9_%' AND ubigeo NOT LIKE '9_0000' | filtra por `nombre_geo` (texto país, indexado) |
| `"departamento"` | `sv_resumen_departamentos` WHERE ubigeo LIKE '0%' OR ubigeo LIKE '1%' OR ubigeo LIKE '2%' | filtra por nombre dept |
| `"provincia"` | `sv_resumen_provincias` WHERE ubigeo LIKE '0%' OR ubigeo LIKE '1%' OR ubigeo LIKE '2%' | filtra por nombre prov |
| `"distrito"` | `sv_agg_distrito` | PK lookup (distrito, provincia, departamento) |
| `"ciudad"` | `sv_agg_ciudad` | filtra por ciudad, pais |

**Nota crítica sobre exterior:** para "peruanos en el exterior" usar `ambito='exterior'` de `mesas_sv` o filtrar por prefijo ubigeo ≥ `910000`. **NO** usar exclusión de continente `AMÉRICAS` — eso elimina la diáspora latinoamericana.

```python
def query_sv_geo(
    self,
    nivel: str,
    *,
    continente: str | None = None,   # "EUROPA", "ASIA", etc.
    pais: str | None = None,         # "ARGENTINA", "ESPAÑA"
    departamento: str | None = None,
    provincia: str | None = None,
    distrito: str | None = None,
    ciudad: str | None = None,
    ambito: str | None = None,       # "peru" | "exterior" — para filtrar nacionamente
) -> list[dict]:
    """
    Retorna lista de filas de la tabla apropiada.
    Cada fila incluye pct_keiko, pct_sanchez, fuente (onpe_api|local_agregado), fecha_actualizacion.
    """
```

#### 6. `get_comparacion_geo(ubigeo)` → `dict`

Compara totales de 1V y 2V para un ubigeo (departamento, provincia, distrito o exterior).

**⚠️ Bug fix #9 — fuente de 1V debe ser explícita:**  
No existe tabla `sv_resumen_*` para 1V. La fuente de 1V depende del nivel:
- **Departamento/provincia (ubigeo peruano):** agregar desde `votos_by_ubigeo_partido` (JOIN `agrupaciones`) filtrado por `ubigeo = ?`. Para participación, usar `mesas_data` (suma `votos_emitidos`, `electores_habiles` WHERE `ubigeo = ?`).
- **Nacional:** agregar `votos_by_ubigeo_partido` sin filtro (o usar totales de `mesas_data`).
- **Exterior (ubigeo prefijo 91-95):** los ubigeos 1V de exterior mapean al mismo esquema.

La fuente de 2V usa `sv_resumen_departamentos` / `sv_resumen_provincias` / `sv_agg_distrito` según nivel (igual que `query_sv_geo`).

```python
{
    "ubigeo": "150000",
    "geo_label": "LIMA (departamento)",
    "primera_vuelta": {
        "total_votos_validos": N,
        "total_votos_emitidos": N,
        "electores_habiles": N,
        "participacion_pct": float,
        "top_partidos": [{"nombre": "...", "votos": N, "pct": float}, ...]  # top 5
    },
    "segunda_vuelta": {
        "total_votos_validos": N,
        "total_votos_emitidos": N,
        "keiko_votos": N, "keiko_pct": float,
        "sanchez_votos": N, "sanchez_pct": float,
        "blancos": N, "nulos": N,
        "fuente": "nnls_calibrado | local_agregado",
    },
    "delta": {
        "votos_emitidos": N,        # 2V - 1V
        "participacion_pct": float,
    },
    "proyeccion": {  # desde proyeccion_sv_by_ubigeo si disponible
        "keiko_proyectado": N,
        "sanchez_proyectado": N,
        "delta_keiko": N,      # real - proyectado
        "delta_sanchez": N,
    }
}
```

> ⚠️ `votos_by_ubigeo_partido` usa ubigeos a nivel ciudad (6 dígitos). Para agregar a nivel departamento (4 dígitos) o nacional, hacer `WHERE ubigeo LIKE '15%'` (Lima) — el prefijo del ubigeo identifica el departamento. Verificar que el padding sea consistente (6 dígitos sin cortar).

#### 7. `seed_transfer_map()` → `int` (filas insertadas)

Lee `TRANSFER_MAP` de `knowledge_base.py` y hace `INSERT OR IGNORE` en `voto_transfer_map`. Idempotente. Siembra los 3 pesos NNLS + fuente.

```python
def seed_transfer_map(self) -> int:
    from .knowledge_base import TRANSFER_MAP, _norm_kb
    now = self.now_iso()
    count = 0
    with self._connect() as conn:
        for nombre_norm, entry in TRANSFER_MAP.items():
            conn.execute(
                """INSERT OR IGNORE INTO voto_transfer_map
                   (nombre_partido_norm, nombre_partido, candidato_1v,
                    sv_plan, peso_keiko, peso_sanchez, peso_bn,
                    fuente, nota, seeded_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (nombre_norm, nombre_norm.title(),
                 entry.get("candidato_1v", ""),
                 entry.get("sv_plan"),
                 entry["peso_keiko"], entry["peso_sanchez"], entry["peso_bn"],
                 entry.get("fuente", "editorial"),
                 entry.get("nota", ""), now),
            )
            count += 1
    return count
```

#### 8. `rebuild_proyeccion_sv()` → `int` (ubigeos recalculados)

Recalcula `proyeccion_sv_by_ubigeo` usando:
- `votos_by_ubigeo_partido` (totales 1V por ubigeo × partido)
- `agrupaciones` (nombres de partidos 1V)
- `TRANSFER_MAP` (pesos calibrados NNLS: `peso_keiko`, `peso_sanchez`, `peso_bn`)

**Implementación en Python** (no SQL puro — la normalización de tildes es incompleta en SQLite):

```python
def rebuild_proyeccion_sv(self) -> int:
    from .knowledge_base import _norm_kb, TRANSFER_MAP

    rows = conn.execute(
        "SELECT vbup.ubigeo, a.nombre, SUM(vbup.total_votos) AS total "
        "FROM votos_by_ubigeo_partido vbup "
        "LEFT JOIN agrupaciones a ON a.partido_id = vbup.partido_id "
        "WHERE vbup.partido_id NOT IN ('80','81','82') "  # excluir blancos/nulos/impugnados de 1V
        "GROUP BY vbup.ubigeo, a.nombre"
    ).fetchall()

    # ⚠️ Bug fix #6 — _blancos_1v/_nulos_1v/_abstencion_1v NO son accesibles aquí:
    # partido_id 80/81/82 están excluidos del query. Si en el futuro se quiere proyectar
    # el comportamiento de los votantes blancos/nulos de 1V, se necesita un segundo query
    # SELECT ubigeo, SUM(votos) FROM votos WHERE partido_id IN ('80','81') GROUP BY ubigeo
    # y aplicar _blancos_1v / _nulos_1v por separado. Pendiente para v2.

    # ⚠️ Bug fix #8 — acumular en float, convertir a int UNA SOLA VEZ por ubigeo al final.
    # int() por fila causa pérdida sistemática de votos (floor * 92K mesas * 38 partidos).
    ubigeo_proj: dict[str, dict] = {}
    for row in rows:
        ubigeo = row["ubigeo"]
        transfer = TRANSFER_MAP.get(_norm_kb(str(row["nombre"] or "")))
        if transfer:
            pk = transfer["peso_keiko"]
            ps = transfer["peso_sanchez"]
            pb = transfer["peso_bn"]
            # peso_abs (abstención) = 1.0 - pk - ps - pb  ← se "pierde" entre vueltas
        else:
            # Partido no en mapa → default conservador 50/40/1; loguear como warning
            pk, ps, pb = 0.50, 0.40, 0.01
        votos = int(row["total"] or 0)
        if ubigeo not in ubigeo_proj:
            ubigeo_proj[ubigeo] = {"keiko": 0.0, "sanchez": 0.0, "bn": 0.0}  # float accumulators
        ubigeo_proj[ubigeo]["keiko"]   += votos * pk   # NO int() aquí
        ubigeo_proj[ubigeo]["sanchez"] += votos * ps
        ubigeo_proj[ubigeo]["bn"]      += votos * pb

    # JOIN con reales SV por ubigeo
    reales = {r["ubigeo"]: r for r in conn.execute(
        "SELECT ubigeo, "
        "MAX(CASE WHEN partido_id='8' THEN total_votos END) AS keiko_real, "
        "MAX(CASE WHEN partido_id='10' THEN total_votos END) AS sanchez_real "
        "FROM votos_sv_by_ubigeo_partido GROUP BY ubigeo"
    ).fetchall()}

    # ⚠️ Bug fix #7 + #8 — incluir votos_proyectados_bn en INSERT; round() al final
    insert_rows = []
    for ubigeo, proj in ubigeo_proj.items():
        r = reales.get(ubigeo, {})
        keiko_real   = r.get("keiko_real")
        sanchez_real = r.get("sanchez_real")
        pk_int = round(proj["keiko"])    # round una vez por ubigeo
        ps_int = round(proj["sanchez"])
        pb_int = round(proj["bn"])
        insert_rows.append((
            ubigeo, pk_int, ps_int, pb_int,
            keiko_real, sanchez_real,
            (keiko_real   - pk_int) if keiko_real   is not None else None,
            (sanchez_real - ps_int) if sanchez_real is not None else None,
        ))

    conn.execute("DELETE FROM proyeccion_sv_by_ubigeo")
    conn.executemany(
        "INSERT INTO proyeccion_sv_by_ubigeo "
        "(ubigeo, votos_proyectados_keiko, votos_proyectados_sanchez, votos_proyectados_bn, "
        " votos_reales_keiko, votos_reales_sanchez, delta_keiko, delta_sanchez, rebuilt_at) "
        "VALUES (?,?,?,?,?,?,?,?,datetime('now'))",
        insert_rows,
    )
    return len(insert_rows)
```

> **Abstención implícita:** `peso_abs = 1 - pk - ps - pb`. Por ejemplo Renovación Popular pierde 0.9%, APP pierde 9.4%, Partido Morado pierde 7.9% (Σ=0.921).  
> **Cobertura de mapping:** llamar `_audit_transfer_coverage()` al bootstrap que verifique que todos los `partido_id` de `agrupaciones` (excepto 80/81/82) tienen match en TRANSFER_MAP, logging warning por cada faltante.  
> **_blancos_1v/_nulos_1v/_abstencion_1v:** Las 3 entradas especiales del TRANSFER_MAP no son alcanzables desde este query (partido_id 80/81/82 están excluidos). Son dead code en esta versión; documentarlas como "pendiente v2: proyección de votantes blancos/nulos 1V".

#### 9. `bootstrap_locales_reasignados(output_dir)` → `int` (filas insertadas)

Lee `output/locales_reasignados_segunda_vuelta_2026.txt` del scraper SV e inserta en `locales_reasignados_sv`.

Column mapping:

| Columna .txt | Columna DB | Notas |
|---|---|---|
| `nro` | `nro` | PK |
| `odpe` | `odpe` | Oficina descentralizada ONPE |
| `dpto` | `departamento` | |
| `provincia` | `provincia` | |
| `distrito` | `distrito` | |
| `ccpp` | `ccpp` | Centro poblado (puede estar vacío) |
| `nombre_local_votacion` | `nombre_local_original` | Local usado en 1V |
| `nombre_local_votacion_nuevo` | `nombre_local_nuevo` | Local asignado en 2V (vacío si `INCOMPLETO_OCR`) |
| `motivo` | `motivo` | Razón oficial |
| `mesas_a_reasignar` | `mesas_a_reasignar` | Número de mesas afectadas |
| `estado_parseo` | `estado_parseo` | `OK` / `INCOMPLETO_OCR` / `OCR_REVISAR` |

Motivos presentes en los datos:

| Motivo | Cantidad | Mesas aprox. |
|---|---|---|
| NEGADO POR DISCONFORMIDAD DE PROPIETARIOS | 15 | ~155 |
| RECONSTRUCCION | 10 | ~120 |
| NO CUENTA CON CERCO PERIMETRICO | 7 | ~107 |
| INFRAESTRUCTURA DETERIORADA | 7 | ~70 |
| LOCAL TOMADO POR ALUMNOS EN HUELGA | 2 | **108** (Ucayali 56 + Lurigancho 52) |
| PARA INSTALACION DE MS PROVENIENTES DE OTRO LV | 2 | ~25 |
| EXTORSION | 1 | 6 |
| SE TRASLADO A OTRO DISTRITO | 1 | 9 |
| TOLDOS EN CAMPO ABIERTO CON BAJA TEMPERATURA | 1 | 15 |

> ⚠️ 2 filas con `INCOMPLETO_OCR` (Miraflores, filas 22-23) y 1 con `OCR_REVISAR` (Lurigancho, fila 43) — `nombre_local_nuevo` puede estar vacío. Cargarlo igual con el flag de estado.

#### 10. `get_analisis_reasignados(distrito=None)` → `dict`

Analiza el impacto de participación en mesas de locales reasignados vs no reasignados:

```python
{
    "total_locales_reasignados": 44,
    "total_mesas_afectadas_estimadas": 570,
    "por_motivo": {
        "NEGADO POR DISCONFORMIDAD DE PROPIETARIOS": {"locales": 15, "mesas": N},
        "LOCAL TOMADO POR ALUMNOS EN HUELGA": {"locales": 2, "mesas": 108},
        # ...
    },
    "impacto_participacion": [
        {
            "nro": 42,
            "distrito": "CALLERIA",
            "departamento": "UCAYALI",
            "local_original": "UNIVERSIDAD NACIONAL DE UCAYALI",
            "local_nuevo": "INSTITUTO DE EDUCACION SUPERIOR TECNOLOGICO PUBLICO SUIZA",
            "motivo": "LOCAL TOMADO POR ALUMNOS EN HUELGA",
            "mesas_afectadas": 56,
            # Solo disponible si mesas_sv tiene datos para ese local
            "participacion_1v_pct": float | None,
            "participacion_2v_pct": float | None,
            "delta_participacion_pct": float | None,  # 2V - 1V
        },
        # ...
    ],
    "resumen": {
        "mesas_con_datos_ambas_vueltas": N,
        "promedio_delta_participacion_reasignados": float,  # si negativo: cayó
        "promedio_delta_participacion_no_reasignados": float,
        "diferencia_vs_no_reasignados": float,  # clave: ¿cayó MÁS en reasignados?
    }
}
```

**Lógica de JOIN** (es fuzzy — nombres de local entre tablas no son idénticos):

1. Para cada `locales_reasignados_sv`, buscar mesas en `mesas_data` (1V) con `local_votacion` que coincida con `nombre_local_original` usando `_norm()` + mismo `distrito` (vía `ubigeo_reniec`).
2. Para 2V: buscar en `mesas_sv` con `local_votacion` ≈ `nombre_local_nuevo` + mismo `distrito`.
3. Promediar `participacion_ciudadana` del scraper SV (disponible en `mesas_sv`) para 2V. Para 1V, calcular `votos_emitidos / electores_habiles * 100`.
4. Si el match fuzzy no encuentra nada, marcar como `participacion_Xv_pct: null` — no fabricar datos.

---

## Fase 3b — Plan de eficiencia: modelo híbrido de agregaciones

### Contexto

El sitio https://onpe.ozamora.com/detalle.php implementa drill-down completo hasta mesa. El scraper **ya pre-computa** los niveles nacional, departamento/continente, provincia/país-exterior y cobertura en `resumen/`. El MCP debe aprovecharlos como primera fuente (son más autoritativos: `fuente=onpe_api` donde aplica).

**Solo hay que calcular por CTAS los niveles que el scraper NO provee:** distrito y ciudad-exterior.

### Tabla de responsabilidades por nivel geográfico

| Nivel | Fuente | Tabla DB | Trigger de update |
|---|---|---|---|
| Nacional | `resumen/resumen_nacional.txt` | `sv_resumen_nacional` | DELETE + INSERT en cada refresh |
| Continente (exterior) | `resumen/resumen_cobertura_departamentos.txt` (9x0000) | `sv_resumen_cobertura` | DELETE + INSERT |
| País exterior | `resumen/resumen_provincias.txt` (9XX100) | `sv_resumen_provincias` | DELETE + INSERT |
| Departamento (Perú) | `resumen/resumen_departamentos.txt` | `sv_resumen_departamentos` | DELETE + INSERT |
| Provincia (Perú) | `resumen/resumen_provincias.txt` | `sv_resumen_provincias` | DELETE + INSERT |
| **Distrito (Perú)** | **Calculado** de `mesas_sv × votos_sv × ubicaciones_sv` | `sv_agg_distrito` | **CTAS swap** |
| **Ciudad exterior** | **Calculado** de `mesas_sv × votos_sv × ubicaciones_sv` | `sv_agg_ciudad` | **CTAS swap** |

> `sv_resumen_provincias` sirve para **ambos**: provincias peruanas (ubigeo 0x-2x) y países exteriores (ubigeo 9x).  
> La tabla `sv_resumen_departamentos` también contiene aggregados de continente (ubigeo 9x0000) si el scraper los incluye.

### Jerarquía real de ubigeos en el scraper

```
Nivel       Formato ubigeo   Ejemplo         En ubicaciones.txt?
────────────────────────────────────────────────────────────────
Nacional    (no tiene ubigeo; actas_pct en resumen_nacional)
Continente  9X0000           910000=AFRICA   NO — solo en cobertura
País ext.   9XX100           910100=ARGELIA  NO — solo en provincias
Ciudad ext. 9XX1YY           910101=ARGEL    SÍ
Dpto Peru   XX0000           150000=LIMA     NO — solo en departamentos
Prov Peru   XX0Y00           150100=LIMA     NO — solo en provincias
Dist Peru   ubigeo completo  150101          SÍ (en ubicaciones.txt)
```

### Estrategia de `rebuild_sv_ctas_levels()` → solo distrito y ciudad

Usa una sola temp table `_sv_base` (un scan de mesas × votos × ubicaciones) luego 2 CTASes.

```sql
-- Un solo scan de las tablas grandes
DROP TABLE IF EXISTS _sv_base;
CREATE TEMP TABLE _sv_base AS
SELECT
    m.codigo_mesa,
    m.electores_habiles,
    m.votos_emitidos,
    m.votos_validos,
    CASE m.estado_acta WHEN 'C' THEN 1 ELSE 0 END AS contabilizada,
    m.id_ambito_geografico,
    u.ambito,
    u.departamento,
    u.provincia,
    u.distrito,
    u.continente,
    u.pais,
    u.ciudad,
    SUM(CASE WHEN v.partido_id = :pk  THEN v.votos ELSE 0 END) AS vk,
    SUM(CASE WHEN v.partido_id = :ps  THEN v.votos ELSE 0 END) AS vs,
    SUM(CASE WHEN v.partido_id = '80' THEN v.votos ELSE 0 END) AS vb,
    SUM(CASE WHEN v.partido_id = '81' THEN v.votos ELSE 0 END) AS vn,
    SUM(CASE WHEN v.partido_id = '82' THEN v.votos ELSE 0 END) AS vi
FROM mesas_sv m
JOIN  ubicaciones_sv u ON u.ubigeo      = m.ubigeo
LEFT JOIN votos_sv v   ON v.codigo_mesa = m.codigo_mesa
GROUP BY m.codigo_mesa;

CREATE INDEX _sv_base_ambito ON _sv_base (ambito);
CREATE INDEX _sv_base_dist   ON _sv_base (departamento, provincia, distrito);

-- CTAS 1: Distrito (Peru solamente)
CREATE TABLE sv_agg_distrito_new AS
SELECT
    distrito, provincia, departamento,
    COUNT(*)               AS total_mesas,
    SUM(contabilizada)     AS mesas_contabilizadas,
    SUM(electores_habiles) AS electores_habiles,
    SUM(votos_emitidos)    AS votos_emitidos,
    SUM(votos_validos)     AS votos_validos,
    SUM(vk) AS votos_keiko,    SUM(vs) AS votos_sanchez,
    SUM(vb) AS votos_blancos,  SUM(vn) AS votos_nulos,  SUM(vi) AS votos_impugnados,
    :now AS rebuilt_at
FROM _sv_base
WHERE ambito = 'peru'
GROUP BY departamento, provincia, distrito;

-- CTAS 2: Ciudad exterior
-- Nota: 'continente' y 'pais' vienen de ubicaciones_sv (nivel ciudad)
-- NO confundir con los ubigeos país/continente de resumen_provincias/cobertura
CREATE TABLE sv_agg_ciudad_new AS
SELECT
    ciudad, pais, continente,
    'exterior' AS ambito,
    COUNT(*)               AS total_mesas,
    SUM(contabilizada)     AS mesas_contabilizadas,
    SUM(electores_habiles) AS electores_habiles,
    SUM(votos_emitidos)    AS votos_emitidos,
    SUM(votos_validos)     AS votos_validos,
    SUM(vk) AS votos_keiko,    SUM(vs) AS votos_sanchez,
    SUM(vb) AS votos_blancos,  SUM(vn) AS votos_nulos,  SUM(vi) AS votos_impugnados,
    :now AS rebuilt_at
FROM _sv_base
WHERE ambito = 'exterior'
GROUP BY continente, pais, ciudad;

-- Swap atómico (dentro de transacción)
BEGIN;
DROP TABLE IF EXISTS sv_agg_distrito; ALTER TABLE sv_agg_distrito_new RENAME TO sv_agg_distrito;
DROP TABLE IF EXISTS sv_agg_ciudad;   ALTER TABLE sv_agg_ciudad_new   RENAME TO sv_agg_ciudad;
COMMIT;

DROP TABLE IF EXISTS _sv_base;
```

### Estrategia completa de update en `onpe_sv_refresh()`

```
git commit cambió?
├── NO  → O(1) — retorna "ya_actualizado" sin tocar DB
└── SÍ  → UPSERT incremental sobre mesas_sv + votos_sv (INSERT OR REPLACE)
          ↓
          1. bootstrap_resumen_sv(resumen_dir)      — DELETE + INSERT, archivos ~KB, ms
          2. Si changed_mesas > 0:
             a. bootstrap_sv_incremental() → stats
             b. rebuild_sv_ctas_levels()   — _sv_base → 2 CTASes → swap atómico (~0.5s)
             c. rebuild_proyeccion_sv()    — solo si hay datos 1V
          3. Retornar stats + sv_resumen_nacional (O(1))
```

**Resumen de tiempos estimados por operación:**
| Operación | Filas procesadas | Tiempo estimado |
|---|---|---|
| `bootstrap_resumen_sv()` | ~1,400 filas (4 archivos txt pequeños) | < 50ms |
| `bootstrap_sv_incremental()` UPSERT | ~92K mesas + ~460K votos | ~1.5s |
| `rebuild_sv_ctas_levels()` | ~92K mesas en _sv_base | ~0.5s |
| `rebuild_proyeccion_sv()` | ~2K ubigeos | ~200ms |
| **Total refresh real** | | **~2.3s** |
| Guard "ya actualizado" | 0 | **< 10ms** |

### `SV_PARTIDO_KEIKO` y `SV_PARTIDO_SANCHEZ` — constantes configurables (CONFIRMADAS)

```python
SV_PARTIDO_KEIKO   = "8"   # FUERZA POPULAR — CONFIRMADO con agrupaciones.txt real
SV_PARTIDO_SANCHEZ = "10"  # JUNTOS POR EL PERÚ — CONFIRMADO
```

### Método de consulta `query_sv_geo(nivel, **kwargs)` → `list[dict]`

El routing a la tabla correcta (definido también en el método 5 de DataStore arriba):

```python
# "¿cómo va Lima?"
store.query_sv_geo("departamento", departamento="LIMA")
# → sv_resumen_departamentos WHERE ubigeo=150000  (PK lookup O(1))

# "¿cómo van los peruanos en el exterior?"
store.query_sv_geo("continente", ambito="exterior")
# → sv_resumen_cobertura WHERE ubigeo LIKE '9_0000' (5 filas)
# ⚠️ NO usar continent != AMÉRICAS — eso es incorrecto

# "¿cómo va Argentina?"
store.query_sv_geo("pais_exterior", pais="ARGENTINA")
# → sv_resumen_provincias WHERE ubigeo = ubigeo_de_argentina (9XX100)

# "¿cómo va Miraflores?"
store.query_sv_geo("distrito", distrito="MIRAFLORES")
# → sv_agg_distrito WHERE distrito='MIRAFLORES' (puede haber varios - necesita prov/dept para desambiguar)

# "¿cómo va Buenos Aires?"
store.query_sv_geo("ciudad", ciudad="BUENOS AIRES")
# → sv_agg_ciudad WHERE ciudad='BUENOS AIRES'
```

### Comparación 1V vs 2V por nivel geográfico

- **2V side**: desde `sv_resumen_*` (dept, prov, país) o `sv_agg_*` (distrito, ciudad)
- **1V side**: desde `votos_by_ubigeo_partido` (JOIN con `ubicaciones_sv` para nombres)
- **Para departamento/provincia**: ubigeo de `sv_resumen_departamentos` puede usarse como JOIN key con 1V (mismo esquema ubigeo)

### Impacto en herramientas existentes (actualizado)

| Tool / intent | Antes | Después |
|---|---|---|
| `onpe_sv_resumen()` | Full scan `mesas_sv` + `votos_sv` | `sv_resumen_nacional` → O(1) |
| `onpe_chat("Keiko en Lima")` | JOIN 90K + 460K rows | `sv_resumen_departamentos` ubigeo=150000 |
| `onpe_chat("exterior")` | JOIN + GROUP | `sv_resumen_cobertura` WHERE 9x0000 — 5 filas |
| `onpe_chat("Argentina")` | JOIN + WHERE pais | `sv_resumen_provincias` PK lookup |
| `onpe_chat("Miraflores")` | JOIN + GROUP distrito | `sv_agg_distrito` PK lookup |
| `onpe_chat("Buenos Aires")` | JOIN + GROUP ciudad | `sv_agg_ciudad` PK lookup |
| `onpe_comparar_geo("Lima")` | doble scan 1V+2V | `sv_resumen_departamentos` + `votos_by_ubigeo` |

```python
def onpe_sv_refresh():
    commit_antes = git_rev_parse("HEAD")
    git_pull()
    commit_despues = git_rev_parse("HEAD")

    if commit_antes == commit_despues:
        return ok_response({"status": "ya_actualizado"})  # O(1), cero trabajo

    stats = store.bootstrap_sv_incremental(output_dir)   # UPSERT + captura delta

    if stats["mesas_nuevas"] > 0 or stats["mesas_contabilizadas_nuevas"] > 0:
        changed = stats["mesas_nuevas"] + stats["mesas_contabilizadas_nuevas"]
        is_first = stats["total_mesas"] == changed

        if is_first or changed >= FULL_REBUILD_THRESHOLD:
            store.rebuild_sv_aggregates_full()            # CTAS + swap atómico
        else:
            store.rebuild_sv_aggregates_delta(stats["changed_mesas_detail"])  # UPDATE += diff

        if has_1v_data():
            store.rebuild_proyeccion_sv_partial(stats["affected_ubigeos"])

    return ok_response({"commit_antes": ..., "commit_despues": ..., **stats,
                        "resumen": store.get_sv_resumen_nacional()})  # O(1)
```

---

## Fase 4 — Cliente API segunda vuelta (`onpe_api.py`)

```python
BASE_URL_SV = "https://resultadosegundavuelta.onpe.gob.pe/presentacion-backend"
```

En `server.py`:

```python
onpe_api_sv = OnpeApiClient(base_url=BASE_URL_SV)
```

`OnpeApiClient` reutiliza sin cambios — acepta `base_url` en el constructor.

> ⚠️ Confirmar el `idEleccionPrincipal` real con:
> ```bash
> python -c "from curl_cffi import requests as r; import json; print(json.dumps(r.get('https://resultadosegundavuelta.onpe.gob.pe/presentacion-backend/proceso/proceso-electoral-activo', impersonate='chrome124').json(), indent=2))"
> ```

---

## Fase 5 — Herramientas MCP (`server.py`)

### Tool 1: `onpe_sv_bootstrap`

```python
@mcp.tool()
def onpe_sv_bootstrap(force: bool = False) -> dict[str, Any]:
    """Importa snapshot del scraper onpe-scraper-2026-2 hacia SQLite.

    Carga mesas_sv, votos_sv, agrupaciones_sv. Siembra voto_transfer_map
    y recalcula proyeccion_sv_by_ubigeo si ya hay datos de 1ª vuelta.
    Pasa force=true para reimportar aunque ya haya datos.
    """
```

Pasos:
1. Verificar `settings.sv_output_dir / "mesas_data.txt"` — si no existe, error claro.
2. `store.bootstrap_segunda_vuelta(settings.sv_output_dir, force=force)`
3. `store.seed_transfer_map()` (idempotente)
4. Si `store.total_mesas_local() > 0`: `store.rebuild_proyeccion_sv()`
5. `ok_response(stats)`

### Tool 2: `onpe_sv_get_mesa`

```python
@mcp.tool()
def onpe_sv_get_mesa(
    codigo_mesa: str,
    force_live: bool = False,
    timeout: int = 30,
) -> dict[str, Any]:
    """Consulta una mesa de segunda vuelta (local → API viva).

    Prioridad: tablas locales mesas_sv/votos_sv → API resultadosegundavuelta.onpe.gob.pe
    """
```

### Tool 3: `onpe_sv_resumen`

```python
@mcp.tool()
def onpe_sv_resumen() -> dict[str, Any]:
    """Resumen nacional de segunda vuelta: % contabilizado, votos por candidato."""
```

Lógica: `store.get_sv_resumen_nacional()` → lee desde `sv_agg_nacional` (O(1)).

### Tool 4 (nuevo): `onpe_sv_refresh`

```python
@mcp.tool()
def onpe_sv_refresh() -> dict[str, Any]:
    """Actualiza datos de segunda vuelta desde el repo del scraper (git pull + reimport).

    Flujo completo en un solo llamado:
      1. git pull en sv_scraper_root (si es un repo git válido)
      2. bootstrap_segunda_vuelta(force=True) — reimporta todo
      3. rebuild_proyeccion_sv() — recalcula proyección vs real
      4. Retorna stats: mesas nuevas, mesas_contabilizadas, pct_contabilizado

    Llamar cada vez que el scraper publique nuevos datos.
    No requiere pasos manuales.
    """
```

Lógica:
1. Verificar que `settings.sv_scraper_root` sea un directorio git (`settings.sv_scraper_root / ".git"` existe).
2. Si es git:
   - Capturar commit actual: `commit_antes = git_rev_parse("HEAD")`
   - `subprocess.run(["git", "-C", str(sv_root), "pull", "--ff-only"], ...)` — capturar stdout.
   - Capturar commit nuevo: `commit_despues = git_rev_parse("HEAD")`
   - **⚠️ Bug fix #1 — guard doble:** Si `commit_antes == commit_despues` Y `mesas_sv` ya tiene datos → retornar `status: "ya_actualizado"`. Si el commit no cambió PERO `mesas_sv` está vacío (primer run, DB borrado), continuar con el bootstrap igualmente.
3. `stats = store.bootstrap_sv_incremental(settings.sv_output_dir)` — UPSERT incremental mesas_sv + votos_sv.
4. **⚠️ Bug fix #2 — siempre recargar lookup tables:** Independientemente del delta, recargar `agrupaciones_sv`, `ubicaciones_sv`, `locales_sv` — son necesarios para CTAS y geocoding. Son pequeños (~KB) y un reload completo es seguro.
   - `store.bootstrap_ubicaciones_sv(settings.sv_output_dir)`
   - (agrupaciones y locales también si cambiaron, o siempre)
5. `store.bootstrap_resumen_sv(settings.sv_resumen_dir)` — siempre recargar (DELETE+INSERT, archivos autoritativos).
6. **⚠️ Bug fix #3 — votos_sv_by_ubigeo_partido:** Siempre re-backfill (DELETE + re-aggregate de votos_sv JOIN mesas_sv) antes de CTAS y proyección.
7. **⚠️ Bug fix #4 — siempre full CTAS rebuild:** Eliminar la lógica de "small delta patch vs full rebuild". Siempre llamar `store.rebuild_sv_ctas_levels()` cuando hubo cualquier cambio (incluye correcciones en mesas ya-C). El patch parcial requeriría deltas antes/después que el plan no captura.
   - Detectar "hubo cambios" como: `mesas_nuevas > 0 OR mesas_contabilizadas_nuevas > 0 OR any_row_replaced` (cualquier INSERT OR REPLACE que no sea no-op).
8. Si hay datos de 1V: `store.rebuild_proyeccion_sv()`.
9. Retornar:

```python
{
    "git_pull": "Already up to date." | "N files changed",
    "commit_antes": str,
    "commit_despues": str,
    "mesas_nuevas": N,                        # mesas que no existían antes
    "mesas_contabilizadas_nuevas": N,         # P→C o E→C en este ciclo
    "total_contabilizadas": N,
    "total_mesas": N,
    "aggregates_rebuilt": bool,
    "resumen": {
        "pct_contabilizado": float,
        "keiko_pct": float,
        "sanchez_pct": float,
    }
}
```

> Si `sv_scraper_root` no es un repo git (o el pull falla), loguear warning y continuar con UPSERT de los archivos locales — no abortar.

### Estrategia de delta: UPSERT incremental (no DELETE + INSERT)

**Problema con `force=True` / DELETE + reimport:** descarta información sobre qué cambió y es innecesariamente destructivo. Los archivos del scraper solo **crecen** (nunca borran mesas); `estado_acta` cambia `P` → `C` una sola vez por mesa.

**Solución: `INSERT OR REPLACE` (UPSERT nativo de SQLite)**

```python
def bootstrap_sv_incremental(self, output_dir: Path) -> dict[str, int]:
    """
    UPSERT incremental sobre mesas_sv y votos_sv.
    No hace DELETE. El PK codigo_mesa maneja duplicados:
      - Mesa nueva → INSERT
      - Mesa existente con estado_acta actualizado → REPLACE (overwrite in place)
      - Mesa idéntica → REPLACE (no-op efectivo)
    Retorna stats de delta para decisión de rebuild.
    
    ⚠️ Bug fix #5: capturar `rows_replaced` (total_changes - before) para detectar
    correcciones en mesas ya-C (cambio de votos sin cambio de estado_acta).
    """
    # Snapshot ANTES
    antes_c      = _count("SELECT COUNT(*) FROM mesas_sv WHERE estado_acta='C'")
    antes_total  = _count("SELECT COUNT(*) FROM mesas_sv")
    antes_changes = conn.total_changes  # cursor.execute().rowcount no sirve para REPLACE

    # UPSERT — parsear archivos y ejecutar INSERT OR REPLACE INTO mesas_sv / votos_sv
    _upsert_from_file(output_dir / "mesas_data.txt", "mesas_sv")
    _upsert_from_file(output_dir / "votos.txt",      "votos_sv")

    # Snapshot DESPUÉS
    despues_c      = _count("SELECT COUNT(*) FROM mesas_sv WHERE estado_acta='C'")
    despues_total  = _count("SELECT COUNT(*) FROM mesas_sv")
    despues_changes = conn.total_changes

    rows_affected = despues_changes - antes_changes  # includes true no-ops too; > 0 = algo cambió

    return {
        "mesas_nuevas":                  despues_total - antes_total,
        "mesas_contabilizadas_nuevas":   despues_c - antes_c,
        "total_contabilizadas":          despues_c,
        "total_mesas":                   despues_total,
        "rows_affected":                 rows_affected,   # >0 ⟹ rebuild needed
    }
```

> **Nota sobre detección de cambios:** `mesas_nuevas == 0 AND mesas_contabilizadas_nuevas == 0` no significa "sin cambios". Un acta ya-C puede corregir votos sin cambiar su `estado_acta`. Usar `rows_affected > 0` como trigger de rebuild. SQLite `total_changes` se incrementa en 1 por cada fila afectada por INSERT OR REPLACE.

`bootstrap_segunda_vuelta(force=False)` sigue existiendo para el **primer bootstrap** (cuando las tablas están vacías): llama a `bootstrap_sv_incremental` internamente — el resultado es el mismo porque UPSERT sobre tabla vacía = INSERT masivo. El parámetro `force=True` queda deprecado en favor de borrar manualmente y re-bootstrapear si se necesita un reset real.

### Tool 5 (renumerada): `onpe_comparar_mesa`

```python
@mcp.tool()
def onpe_comparar_mesa(codigo_mesa: str) -> dict[str, Any]:
    """Compara los resultados de 1ª y 2ª vuelta para la misma mesa de votación.

    Retorna: datos de participación, votos por partido en 1V, votos Keiko/Sánchez en 2V,
    delta de participación y si cambió el ganador entre vueltas.
    Requiere datos hidratados de ambas vueltas (onpe_bootstrap_snapshot + onpe_sv_bootstrap).
    """
```

Lógica: `store.get_comparacion_mesa(validate_mesa_code(codigo_mesa))`

### Tool 5: `onpe_comparar_geo`

```python
@mcp.tool()
def onpe_comparar_geo(
    ubicacion: str,
    nivel: str = "auto",
) -> dict[str, Any]:
    """Compara 1ª y 2ª vuelta para una ciudad, provincia o departamento.

    ubicacion: nombre libre (p.ej. "Lima", "Arequipa", "Puno", "San Juan de Lurigancho")
    nivel: "distrito" | "provincia" | "departamento" | "auto" (infiere por nombre)

    Retorna: votos totales 1V top-5, votos Keiko/Sánchez en 2V,
    proyección esperada desde mapa de transferencia y delta real vs proyectado.
    """
```

Lógica:
1. Resolver `ubicacion` → `ubigeo` usando `ubigeo_reniec` / `ubigeo_onpe_api` (mismo mecanismo que `onpe_chat`).
2. `store.get_comparacion_geo(ubigeo)`

### Tool 6: `onpe_proyeccion_sv`

```python
@mcp.tool()
def onpe_proyeccion_sv(
    ubicacion: str = "",
) -> dict[str, Any]:
    """Proyecta votos esperados de segunda vuelta a partir de resultados de 1ª vuelta
    y el mapa de transferencia de votos por alineamiento político.

    Si ubicacion es vacío, retorna proyección nacional.
    Si ubicacion tiene valor, filtra por esa geo (ciudad, provincia, departamento).

    ADVERTENCIA: Esta proyección es indicativa basada en tendencias históricas/ideológicas,
    no en encuestas. Los resultados reales pueden diferir significativamente.
    """
```

### Tool 7 (nueva): `onpe_analisis_reasignados`

```python
@mcp.tool()
def onpe_analisis_reasignados(
    distrito: str = "",
    motivo: str = "",
) -> dict[str, Any]:
    """Analiza el impacto en participación de los 44 locales de votación reasignados
    para la segunda vuelta 2026 (~570 mesas).

    Para cada local reasignado, compara la participación en 1ª vuelta (local original)
    vs 2ª vuelta (local nuevo), detectando si hubo caída de participación atribuible
    a la desinformación sobre el cambio de local.

    Parámetros opcionales:
      distrito: filtrar por nombre de distrito (ej: "Lince", "Miraflores", "Callería")
      motivo:   filtrar por motivo (ej: "HUELGA", "PROPIETARIOS", "RECONSTRUCCION")

    Requiere: onpe_sv_bootstrap previo (datos de ambas vueltas).
    """
```

Lógica: `store.get_analisis_reasignados(distrito=distrito or None, motivo=motivo or None)`

### Tool 8 (nueva): `onpe_sv_detalle`

```python
@mcp.tool()
def onpe_sv_detalle(
    nivel: str = "nacional",
    continente: str = "",
    pais: str = "",
    departamento: str = "",
    provincia: str = "",
    distrito: str = "",
    ciudad: str = "",
) -> dict[str, Any]:
    """Resultados de segunda vuelta por nivel geográfico, usando tablas pre-computadas.

    nivel: "nacional" | "continente" | "pais" | "departamento" | "provincia" | "distrito" | "ciudad"

    Ejemplos de uso:
      onpe_sv_detalle()                                → resumen nacional (1 fila)
      onpe_sv_detalle(nivel="continente")              → todas las regiones (AMÉRI CA, EUROPA…)
      onpe_sv_detalle(nivel="pais", continente="EUROPA") → países de Europa
      onpe_sv_detalle(nivel="departamento")            → los 25 departamentos peruanos
      onpe_sv_detalle(nivel="provincia", departamento="LIMA")  → provincias de Lima
      onpe_sv_detalle(nivel="distrito", provincia="LIMA", departamento="LIMA") → distritos de Lima
      onpe_sv_detalle(nivel="ciudad", pais="CHILE")    → ciudades con voto en Chile

    Cada fila incluye: total_mesas, mesas_contabilizadas, pct_contabilizado,
    votos_keiko, votos_sanchez, pct_keiko, pct_sanchez, votos_blancos, votos_nulos.

    Latencia: O(1) — todas las queries son lookups por PK sobre tablas pre-computadas.
    Reconstruir con onpe_sv_refresh() o onpe_sv_bootstrap() para datos actualizados.
    """
```

Lógica: `store.query_sv_geo(nivel, continente=continente or None, pais=pais or None, departamento=departamento or None, provincia=provincia or None, distrito=distrito or None, ciudad=ciudad or None)`

### Extensión de `onpe_chat` — routing por etapas

> **Principio crítico (del rubber duck):** El `onpe_chat` existente en `server.py` tiene routing muy ordenado y con alta especificidad. **No** añadir keyword buckets planos — causarían falsos positivos. Insertar la lógica SV **después** de las etapas existentes (detección de mesa, candidato 1V, geo 1V) y solo si el contexto SV es inequívoco.

#### Orden de las etapas (conservar el existente, agregar al final)

```
Etapa 1: ¿Es una mesa específica? (regex \d{4,6}) → onpe_get_mesa / onpe_sv_get_mesa
Etapa 2: ¿Es candidato específico 1V? → respuesta 1V
Etapa 3: ¿Es query nacional/regional 1V? → votos_by_ubigeo 1V
── NUEVAS ETAPAS (solo se alcanzan si las anteriores no matchearon) ──
Etapa 4: ¿Es query de reasignados?
    Señal alta-especificidad: "reasignado", "reubicado", "local nuevo", "cambio de local",
    "huelga estudiantil", "propietario nego", "extorsión local"
    → get_analisis_reasignados()
Etapa 5: ¿Es comparación entre vueltas?
    Señal alta-especificidad: "primera vs segunda", "vs primera vuelta", "comparar vueltas",
    "diferencia entre vueltas", "cambio entre 1v y 2v"
    → get_comparacion_mesa() / get_comparacion_geo()
Etapa 6: ¿Es transferencia de votos?
    Señal alta-especificidad: "a donde fueron los votos de [PARTIDO]",
    "votos de [PARTIDO] fueron a", "transferencia de votos", "mapa de transferencia"
    → TRANSFER_MAP lookup + votos 1V del partido
Etapa 7: ¿Es proyección?
    Señal alta-especificidad: "proyección de segunda vuelta", "proyectado para Keiko",
    "esperado según primera vuelta"
    → proyeccion_sv_by_ubigeo
Etapa 8: ¿Es query de segunda vuelta con ubicación?
    Señal: (segunda vuelta | 2da vuelta | ballotage | keiko | sanchez) + nombre geo
    Cuidado: "keiko" y "sanchez" solos deben ir a 1V si hay datos 1V con esos candidatos
    → query_sv_geo() con nivel inferido del nombre geo
Etapa 9: ¿Es query general de segunda vuelta?
    "quién va ganando la segunda vuelta", "resultado segunda vuelta", "marcador"
    → get_sv_resumen_nacional()
Etapa 10: ¿Es query sobre mesas 9xxxxx?
    "mesas 900000", "qué son las mesas 9", "mesa especial", "código 9"
    → Knowledge base: "Son mesas peruanas regulares con código ≥ 900000, no tienen nada especial"
```

#### Frases de alta especificidad para cada intent nuevo

```python
# Solo estas frases disparan los intents nuevos — no keywords sueltos
_SV_REASIGNADOS_PHRASES = frozenset({
    "local reasignado", "local reubicado", "cambio de local", "local nuevo de votacion",
    "local tomado por", "huelga estudiantil", "propietario nego",
    "locales reasignados segunda vuelta",
})

_SV_COMPARE_PHRASES = frozenset({
    "primera vs segunda", "primera versus segunda", "comparar vueltas",
    "diferencia entre vueltas", "1v vs 2v", "cambio entre vueltas",
    "como compara primera", "comparacion de vueltas",
})

_SV_TRANSFER_PHRASES = frozenset({
    "a donde fueron los votos de", "donde fueron los votos de",
    "transferencia de votos", "mapa de transferencia", "votos de aliaga",
    "votos de acuna", "votos de fujimori primera", "votos de peru libre",
})

_SV_PROJECTION_PHRASES = frozenset({
    "proyeccion segunda vuelta", "proyectado keiko", "proyectado sanchez",
    "esperado segun primera vuelta", "cuanto se esperaba",
})

_SV_MESA_9_PHRASES = frozenset({
    "mesas 900000", "que son las mesas 9", "mesa especial 9", "codigo 9",
    "mesa 9", "mesas con codigo 9",
})
```

Queries nuevas que debe responder:

| Query ejemplo | Etapa | Datos usados |
|---|---|---|
| "¿quién va ganando la segunda vuelta?" | 9 | `sv_resumen_nacional` O(1) |
| "¿cuánto va Keiko en Lima?" | 8 | `sv_resumen_departamentos` ubigeo=150000 |
| "segunda vuelta en Arequipa" | 8 | `sv_resumen_departamentos` ubigeo=040000 |
| "resultado en Miraflores" | 8 | `sv_agg_distrito` PK=(Miraflores,...) — puede ser ambiguo, pedir provincia |
| "¿cómo van los peruanos en el exterior?" | 8 | `sv_resumen_cobertura` WHERE 9x0000, `ambito=exterior` |
| "¿cómo van en Europa?" | 8 | `sv_resumen_cobertura` WHERE ubigeo=940000 |
| "¿cómo va Argentina?" | 8 | `sv_resumen_provincias` WHERE ubigeo=92XX00 (Argentina) |
| "¿cómo va Buenos Aires?" | 8 | `sv_agg_ciudad` WHERE ciudad='BUENOS AIRES' |
| "¿cuántas mesas contabilizadas?" | 9 | `sv_resumen_nacional.contabilizadas` |
| "compara la mesa 123456" | 5 | `get_comparacion_mesa()` |
| "primera vs segunda en Lima" | 5 | `get_comparacion_geo(ubigeo=150000)` |
| "¿a dónde fueron los votos de Aliaga?" | 6 | `TRANSFER_MAP` + votos 1V de RENOVACIÓN POPULAR |
| "proyección de Keiko en Puno" | 7 | `proyeccion_sv_by_ubigeo` WHERE ubigeo=PUNO |
| "¿bajó la participación en locales reasignados?" | 4 | `get_analisis_reasignados()` |
| "¿por qué fue reasignado el local en Miraflores?" | 4 | `locales_reasignados_sv WHERE distrito='MIRAFLORES'` |
| "¿cuántas mesas por huelga?" | 4 | `locales_reasignados_sv WHERE motivo LIKE '%HUELGA%'` |
| "¿qué son las mesas 900000?" | 10 | KB: mesas peruanas regulares con código ≥ 900000 |

**Regla defensiva:** si el intent SV/comparación/proyección/reasignados aplica pero las tablas están vacías, responder con instrucción explícita: "Ejecuta `onpe_sv_bootstrap()` primero".

---

## Fase 6 — `.env.example`

```dotenv
# ── Segunda vuelta 2026 ────────────────────────────────────────────────────────
# Ruta al repo scraper de segunda vuelta (sibling directory por defecto)
# ONPE_SV_SCRAPER_ROOT=../onpe-scraper-2026-2

# Directorio con los .txt del scraper SV (por defecto: $ONPE_SV_SCRAPER_ROOT/output)
# ONPE_SV_OUTPUT_DIR=../onpe-scraper-2026-2/output

# Directorio con los resumen_*.txt pre-computados (por defecto: $ONPE_SV_SCRAPER_ROOT/resumen)
# ONPE_SV_RESUMEN_DIR=../onpe-scraper-2026-2/resumen
```

---

## Orden de implementación recomendado

```
1. knowledge_base.py  — Agregar TRANSFER_MAP + get_transfer() + _norm_kb()    (20 min)
2. config.py          — Agregar sv_scraper_root + sv_output_dir + sv_resumen_dir (8 min)
3. storage.py
   a. _init_schema: grupos A-E (21 tablas nuevas + nombre_geo en resumen_provincias) (35 min)
   b. bootstrap_segunda_vuelta() — orquestador principal                       (20 min)
   c. bootstrap_resumen_sv() — transaccional, poblar nombre_geo en provincias  (30 min)
   d. bootstrap_ubicaciones_sv() + bootstrap_locales_sv()                      (20 min)
   e. bootstrap_locales_reasignados()                                          (20 min)
   f. bootstrap_sv_incremental() — UPSERT + rows_affected counter              (25 min)
   g. rebuild_sv_ctas_levels() — _sv_base → 2 CTASes (distrito+ciudad)        (30 min)
   h. get_mesa_sv_from_local()                                                 (15 min)
   i. get_sv_resumen_nacional() — desde sv_resumen_nacional                    (5 min)
   j. query_sv_geo() — routing híbrido resumen/+CTAS, pais_exterior usa nombre_geo (25 min)
   k. seed_transfer_map()                                                      (15 min)
   l. _audit_transfer_coverage() — verifica 100% match, lista unmapped         (10 min)
   m. rebuild_proyeccion_sv() — float accum + round(), votos_proyectados_bn    (35 min)
   n. get_comparacion_mesa()                                                   (20 min)
   o. get_comparacion_geo() — 1V desde votos_by_ubigeo_partido+mesas_data     (25 min)
   p. get_analisis_reasignados()                                               (30 min)
4. onpe_api.py        — Agregar BASE_URL_SV                                    (2 min)
5. server.py
   a. onpe_sv_bootstrap (incluye _audit_transfer_coverage call)                (15 min)
   b. onpe_sv_get_mesa                                                         (15 min)
   c. onpe_sv_resumen                                                          (10 min)
   d. onpe_sv_refresh (guard doble: hash+DB, reload lookup tables, rows_affected, full CTAS) (35 min)
   e. onpe_sv_detalle (drill-down geo O(1) — routing híbrido)                 (15 min)
   f. onpe_comparar_mesa                                                       (15 min)
   g. onpe_comparar_geo                                                        (20 min)
   h. onpe_proyeccion_sv                                                       (20 min)
   i. onpe_analisis_reasignados                                                (20 min)
   j. onpe_chat — routing por etapas (4-10) sin keyword buckets planos        (60 min)
6. .env.example                                                                (5 min)
7. tests/test_storage_sv.py + tests/test_server_sv.py                          (90 min)
```

**Tiempo estimado total: ~8.5 horas** (+1h por fixes del rubber duck)

---

## Criterios para comenzar la implementación

1. ✅ **El scraper tiene datos contabilizados** — Confirmado: 91,146/92,766 (98.25%) al 2026-06-11.
2. ✅ **Confirmar `idEleccionPrincipal` SV** — `id_eleccion=10` confirmado en todos los archivos del scraper.
3. ✅ **Confirmar `partido_id` de Keiko y Sánchez en SV** — `8=FUERZA POPULAR`, `10=JUNTOS POR EL PERÚ`. Confirmado con `agrupaciones.txt` real.
4. **Primera vuelta hidratada** — Para comparaciones y proyecciones, la DB debe tener datos de 1V cargados (`onpe_bootstrap_snapshot` ejecutado).

---

## Notas de implementación críticas

### Reload de segunda vuelta (datos incompletos)

Los datos de segunda vuelta **no están completos al momento de implementar** (98.2% al 2026-06-11). El flujo de actualización incremental es:

1. **`onpe_sv_refresh`** — hace `git pull` en el repo del scraper y ejecuta UPSERT incremental
   - Guard de hash: si el commit no cambió → devuelve `"ya_actualizado"` sin work
   - Si cambió → `bootstrap_sv_incremental()` (UPSERT mesas/votos) + `bootstrap_resumen_sv()` (reload completo de `resumen/`) + `rebuild_sv_ctas_levels()` (solo distrito+ciudad)
   
2. **Rebuilds post-refresh obligatorios:**
   - `votos_sv_by_ubigeo_partido` — re-backfill completo tras UPSERT
   - `sv_resumen_*` — DELETE+INSERT (archivos cambian con cada scraper run)
   - `sv_agg_distrito` y `sv_agg_ciudad` — CTAS atómico (swap)
   - `proyeccion_sv_by_ubigeo` — re-run solo si hay datos 1V en DB

3. **Cuándo el usuario dirá "alimenta":** ejecutar `onpe_sv_refresh` tool. Cuando el scraper llegue al 100%, la próxima llamada a `onpe_sv_refresh` importará las ~1,660 mesas restantes y todos los resúmenes se actualizarán automáticamente.

### Backfill `votos_sv_by_ubigeo_partido`

```sql
INSERT OR REPLACE INTO votos_sv_by_ubigeo_partido (ubigeo, partido_id, total_votos, fetched_at)
SELECT m.ubigeo, v.partido_id, SUM(v.votos), datetime('now')
FROM votos_sv v
INNER JOIN mesas_sv m ON m.codigo_mesa = v.codigo_mesa
WHERE COALESCE(m.ubigeo,'') <> ''
GROUP BY m.ubigeo, v.partido_id;
```

### Proyección con 3 pesos NNLS

El modelo corregido usa `peso_keiko + peso_sanchez + peso_bn ≤ 1.0`. La diferencia clave con el plan original:

| Partido | Plan original | Datos reales (NNLS) |
|---|---|---|
| APP (Acuña) | 100% Keiko | 44.7% Keiko / 45.9% Sánchez |
| Podemos Perú | pro-Keiko | 94.2% Sánchez |
| Somos Perú | 60% Keiko | 62.6% Sánchez |
| Fuerza y Libertad | Keiko | 63.9% Sánchez |
| Partido Cívico Obras | Keiko | 100% Sánchez |
| Avanza País | 100% Keiko | 72.0% Keiko + 9.2% abstención |
| *Abstención media* | 0% | **~9.2%** por partido |

La proyección implementada usa los pesos calibrados de `TRANSFER_MAP` (ver Fase 2). El código completo de `rebuild_proyeccion_sv()` está en la sección del método #8.

### Sin cambios a tablas existentes

Las tablas `mesas_data`, `votos`, `agrupaciones`, `mesa_cache`, `votos_by_ubigeo_partido`, etc. **no se modifican**. Todas las tools de primera vuelta (`onpe_get_mesa`, `onpe_bootstrap_snapshot`, etc.) **no se tocan**.

### `onpe_chat` — regla de contexto

Cuando la query menciona comparación o transferencia, el chat debe incluir en su respuesta el disclaimer:

> *"La proyección usa pesos calibrados con datos reales de 86K mesas (modelo NNLS). El plan editorial original estaba equivocado en 8+ partidos (Podemos Perú, Somos Perú, Fuerza y Libertad, Partido Cívico Obras, etc.). Es indicativa — no es una encuesta."*

---

## Flujo de uso post-implementación

### Durante el escrutinio (scraper actualizándose)

```bash
# Setup inicial — solo una vez
git clone https://github.com/oscarzamora/onpe-scraper-2026-2 ../onpe-scraper-2026-2
onpe_bootstrap_snapshot()   # cargar 1ª vuelta (prerrequisito para comparaciones)
onpe_sv_bootstrap()         # primer carga de 2ª vuelta

# Cada vez que quieras datos frescos — UN SOLO LLAMADO
onpe_sv_refresh()
→ "git pull: 2 files changed — mesas importadas: 4,210 — 43% contabilizado — Keiko 51.2%"
```

### Consultas durante el conteo

```
onpe_sv_resumen()                          # ¿cómo va el marcador?
onpe_sv_get_mesa("300010")                 # mesa específica
onpe_chat("¿quién va ganando?")
onpe_chat("¿cuánto va Keiko en Puno?")
onpe_chat("¿cuántas mesas faltan?")
```

### Análisis post-elección (escrutinio al 100%)

```
# Comparaciones mesa a mesa
onpe_comparar_mesa("300010")
→ 1V: participación 78%, ganó Aliaga · 2V: Keiko 55%, delta -4pp participación

# Comparaciones por ciudad/región
onpe_comparar_geo("Arequipa")
onpe_comparar_geo("San Juan de Lurigancho")
onpe_chat("¿en qué regiones cambió el ganador entre vueltas?")
onpe_chat("¿dónde bajó más la participación?")

# Análisis de transferencia de votos
onpe_chat("¿a dónde fueron los votos de López Aliaga?")
onpe_chat("¿a dónde fueron los votos de Perú Libre?")
onpe_proyeccion_sv("Ayacucho")
onpe_chat("¿qué tan bien le fue a Sánchez vs lo proyectado en Lima?")
onpe_chat("¿en qué regiones superó Keiko la proyección?")

# Análisis de locales reasignados
onpe_analisis_reasignados()                         # panorama nacional
onpe_analisis_reasignados(distrito="Lince")         # solo Lince (5 locales reasignados)
onpe_analisis_reasignados(motivo="HUELGA")          # los 2 por huelga estudiantil (108 mesas)
onpe_chat("¿bajó la participación en locales reasignados?")
onpe_chat("¿por qué fue reasignado el local en Miraflores?")
onpe_chat("¿hubo menos votos en mesas reasignadas vs las normales?")
onpe_chat("¿qué pasó con la universidad de Ucayali?")  # 56 mesas por huelga
```

---

## Tests a escribir

| Test | Archivo | Qué verifica |
|---|---|---|
| `test_bootstrap_sv_inserts_mesas` | `tests/test_storage_sv.py` | Fixture `mesas_data.txt` SV → `mesas_sv` con columnas correctas incluido `id_ambito_geografico` |
| `test_bootstrap_sv_inserts_votos` | `tests/test_storage_sv.py` | Fixture `votos.txt` → `votos_sv` |
| `test_bootstrap_sv_skip_if_exists` | `tests/test_storage_sv.py` | `force=False` salta si ya hay datos |
| `test_bootstrap_sv_backfills_ubigeo` | `tests/test_storage_sv.py` | `votos_sv_by_ubigeo_partido` correctamente agregado |
| `test_mesa_9xxxxx_is_peru` | `tests/test_storage_sv.py` | Mesa código 900001 tiene `id_ambito_geografico=1` y ubigeo peruano — no es exterior |
| `test_mesa_prefix_doesnt_determine_ambito` | `tests/test_storage_sv.py` | Prefijo de mesa ≠ geografía; solo `id_ambito_geografico` determina exterior |
| `test_bootstrap_resumen_sv_nacional` | `tests/test_storage_sv.py` | `resumen_nacional.txt` → `sv_resumen_nacional` con fuente y fecha_actualizacion |
| `test_bootstrap_resumen_sv_departamentos` | `tests/test_storage_sv.py` | `resumen_departamentos.txt` → `sv_resumen_departamentos` con ubigeos correctos |
| `test_bootstrap_resumen_sv_provincias_exterior` | `tests/test_storage_sv.py` | `resumen_provincias.txt` incluye filas exterior (ubigeo 9XX100) |
| `test_bootstrap_resumen_sv_cobertura` | `tests/test_storage_sv.py` | `resumen_cobertura_departamentos.txt` → `sv_resumen_cobertura` con 5 filas continente (9x0000) |
| `test_seed_transfer_map_idempotent` | `tests/test_storage_sv.py` | Doble seed no duplica filas |
| `test_rebuild_proyeccion_sv` | `tests/test_storage_sv.py` | Proyección correcta dado fixture 1V + transfer weights |
| `test_get_sv_resumen_from_resumen_table` | `tests/test_storage_sv.py` | `get_sv_resumen_nacional()` lee `sv_resumen_nacional`, incluye `fuente` y `fecha_actualizacion` |
| `test_get_sv_resumen_empty` | `tests/test_storage_sv.py` | Retorna estructura vacía si `sv_resumen_nacional` vacía |
| `test_query_sv_geo_nacional` | `tests/test_storage_sv.py` | `query_sv_geo("nacional")` → lee `sv_resumen_nacional` |
| `test_query_sv_geo_departamento_ubigeo` | `tests/test_storage_sv.py` | `query_sv_geo("departamento", departamento="LIMA")` → lookup por ubigeo 150000 |
| `test_query_sv_geo_exterior_ambito_filter` | `tests/test_storage_sv.py` | "peruanos exterior" usa `ambito=exterior`, NO exclusión de continente AMÉRICAS |
| `test_query_sv_geo_pais_exterior` | `tests/test_storage_sv.py` | `query_sv_geo("pais_exterior", pais="ARGENTINA")` → lookup `sv_resumen_provincias` por ubigeo 9XX00 |
| `test_rebuild_sv_ctas_distrito` | `tests/test_storage_sv.py` | `sv_agg_distrito` PK=(dist, prov, dept) sin colisiones, solo mesas Peru (ambito=peru) |
| `test_rebuild_sv_ctas_ciudad` | `tests/test_storage_sv.py` | `sv_agg_ciudad` solo incluye mesas exterior (ambito=exterior) |
| `test_get_comparacion_mesa_both_vueltas` | `tests/test_storage_sv.py` | Retorna delta participación y ganador ambas vueltas |
| `test_get_comparacion_mesa_missing_sv` | `tests/test_storage_sv.py` | `found_2v: False` si mesa no está en `mesas_sv` |
| `test_get_comparacion_geo` | `tests/test_storage_sv.py` | Usa `sv_resumen_departamentos` para 2V side |
| `test_bootstrap_sv_incremental_upsert` | `tests/test_storage_sv.py` | Segunda llamada con nuevas mesas → solo inserta las nuevas, no duplica |
| `test_bootstrap_sv_incremental_estado_update` | `tests/test_storage_sv.py` | Mesa P→C → REPLACE, mesas_contabilizadas_nuevas=1 |
| `test_refresh_guard_skips_on_same_hash_with_data` | `tests/test_server_sv.py` | same commit + mesas_sv populated → "ya_actualizado" |
| `test_refresh_bootstraps_on_same_hash_if_empty_db` | `tests/test_server_sv.py` | same commit + mesas_sv vacío → bootstrap runs anyway |
| `test_refresh_reloads_ubicaciones_agrupaciones` | `tests/test_server_sv.py` | refresh siempre recarga ubicaciones_sv + agrupaciones_sv |
| `test_refresh_rebuilds_votos_sv_by_ubigeo` | `tests/test_server_sv.py` | refresh re-backfill votos_sv_by_ubigeo_partido antes de CTAS |
| `test_refresh_triggers_rebuild_on_vote_correction` | `tests/test_server_sv.py` | mesa ya-C con votos cambiados → rows_affected > 0 → rebuild |
| `test_bootstrap_incremental_returns_rows_affected` | `tests/test_storage_sv.py` | UPSERT sin cambios → rows_affected = N_total, stat existe |
| `test_bootstrap_resumen_sv_transactional` | `tests/test_storage_sv.py` | crash medio DELETE+INSERT → tablas no vacías (rollback) |
| `test_rebuild_proyeccion_float_round_not_floor` | `tests/test_storage_sv.py` | proyección agrega 10 partidos × ubigeo → total correcto (no floor) |
| `test_rebuild_proyeccion_includes_bn_column` | `tests/test_storage_sv.py` | votos_proyectados_bn no es NULL en resultado |
| `test_comparacion_geo_1v_from_votos_by_ubigeo` | `tests/test_storage_sv.py` | 1V side lee votos_by_ubigeo_partido + mesas_data (no tabla inexistente) |
| `test_query_sv_geo_pais_exterior_by_nombre_geo` | `tests/test_storage_sv.py` | `query_sv_geo("pais_exterior", pais="ARGENTINA")` usa nombre_geo index |
| `test_audit_transfer_coverage_empty` | `tests/test_storage_sv.py` | todos los partidos 1V mapeados → lista vacía |
| `test_audit_transfer_coverage_missing` | `tests/test_storage_sv.py` | partido sin mapa → aparece en lista de unmapped |
| `test_onpe_sv_refresh_reloads_resumen` | `tests/test_server_sv.py` | Refresh recarga `sv_resumen_*` + recalcula CTAS distrito/ciudad |
| `test_onpe_sv_refresh_no_git` | `tests/test_server_sv.py` | Sin repo git → UPSERT local + reload resumen sin abortar |
| `test_onpe_sv_bootstrap_tool` | `tests/test_server_sv.py` | Tool `ok=True`, stats presentes |
| `test_onpe_sv_get_mesa_from_local` | `tests/test_server_sv.py` | Usa local si hidratado |
| `test_onpe_comparar_mesa_tool` | `tests/test_server_sv.py` | Retorna delta entre vueltas |
| `test_onpe_comparar_geo_tool` | `tests/test_server_sv.py` | Resuelve nombre geo → ubigeo → comparación |
| `test_onpe_sv_detalle_nacional` | `tests/test_server_sv.py` | `onpe_sv_detalle()` retorna `sv_resumen_nacional` O(1) |
| `test_onpe_sv_detalle_exterior` | `tests/test_server_sv.py` | `onpe_sv_detalle(nivel="continente", ambito="exterior")` excluye PERÚ doméstico |
| `test_onpe_chat_sv_staged_routing` | `tests/test_server_sv.py` | "segunda vuelta Lima" → etapa 8 (no steal 1V) |
| `test_onpe_chat_compare_highspec_phrase` | `tests/test_server_sv.py` | "primera vs segunda en Lima" → etapa 5, no etapa 3 |
| `test_onpe_chat_transfer_highspec_phrase` | `tests/test_server_sv.py` | "a donde fueron los votos de aliaga" → etapa 6 |
| `test_onpe_chat_mesa_9xxxxx_kb` | `tests/test_server_sv.py` | "qué son las mesas 900000" → etapa 10, KB respuesta |
| `test_bootstrap_locales_reasignados_inserts` | `tests/test_storage_sv.py` | Fixture .txt → 44 filas en `locales_reasignados_sv` |
| `test_bootstrap_locales_reasignados_ocr_incomplete` | `tests/test_storage_sv.py` | Filas con `INCOMPLETO_OCR` se cargan con `nombre_local_nuevo=NULL` |
| `test_get_analisis_reasignados_empty` | `tests/test_storage_sv.py` | Retorna estructura vacía si no hay datos |
| `test_get_analisis_reasignados_delta` | `tests/test_storage_sv.py` | Calcula delta participación para local con datos en ambas vueltas |
| `test_onpe_analisis_reasignados_tool` | `tests/test_server_sv.py` | Tool retorna `ok=True` con `impacto_participacion` |
| `test_onpe_chat_reasignados_highspec` | `tests/test_server_sv.py` | "local reasignado segunda vuelta" → etapa 4, no falso positivo en 1V |

---

## Mapa de transferencia de referencia (calibrado NNLS)

Fuente: modelo NNLS entrenado con 86,124 mesas reales de 2V (onpe.ozamora.com/proyeccion.php, 2026-06-11).  
`peso_abs = 1 - peso_keiko - peso_sanchez - peso_bn` (abstención implícita entre vueltas).  
🔴 = invertido respecto al plan original | ⚠️ = diferencia material | ✅ = confirma plan | 📝 = editorial (sin datos 2V)

| Agrupación / Candidato 1V | → Keiko | → Sánchez | → BN | Abs | Nota |
|---|---|---|---|---|---|
| ALIANZA PARA EL PROGRESO — César Acuña | 44.7% | 45.9% | 9.4% | 0% | ⚠️ plan 100% Keiko |
| AHORA NACIÓN — Alfonso López Chau | 0% | 96.6% | 3.4% | 0% | 🔴 plan decía Keiko |
| ALIANZA ELECTORAL VENCEREMOS — Ronald Atencio | 0% | 97.7% | 2.3% | 0% | ✅ |
| PERÚ MODERNO — Carlos Jaico | 0% | 100% | 0% | 0% | 🔴 plan decía Keiko |
| FE EN EL PERÚ — Álvaro Paz de la Barra | 0% | 88.4% | 11.6% | 0% | 🔴 plan decía Keiko |
| FRENTE POPULAR AGRÍCOLA FIA DEL PERÚ | 10% | 80% | 1% | 9% | 📝 editorial |
| AVANZA PAÍS — José Williams | 72.0% | 18.7% | 9.2% | 0% | ⚠️ plan 100% Keiko |
| FUERZA POPULAR — Keiko Fujimori | 95.6% | 0% | 4.4% | 0% | ✅ |
| FUERZA Y LIBERTAD — Giannina Molinelli | 32.2% | 63.9% | 2.4% | 1.5% | 🔴 plan Keiko |
| JUNTOS POR EL PERÚ — Roberto Sánchez | 0% | 97.4% | 2.6% | 0% | ✅ |
| LIBERTAD POPULAR — Rafael Belaunde | 42.5% | 35.2% | 17.6% | 4.7% | ⚠️ plan Keiko, datos dividido |
| PARTIDO APRISTA — Pitter Valderrama | 85.6% | 4.0% | 10.4% | 0% | ⚠️ plan 60% Keiko, datos 86% |
| PARTIDO CIUDADANOS POR EL PERÚ | 50% | 40% | 1% | 9% | 📝 editorial |
| PARTIDO CÍVICO OBRAS — Ricardo Belmont | 0% | 100% | 0% | 0% | 🔴 plan Keiko |
| PTE — Napoleón Becerra | 0% | 96.1% | 3.9% | 0% | ✅ |
| PARTIDO DEL BUEN GOBIERNO — Jorge Nieto | 56.0% | 33.9% | 10.1% | 0% | ⚠️ plan Sánchez, datos 56% Keiko |
| PARTIDO DEMÓCRATA UNIDO — Charlie Carrasco | 0% | 100% | 0% | 0% | 🔴 plan Keiko |
| PARTIDO DEMÓCRATA VERDE — Alex Gonzales | 0% | 90.3% | 9.7% | 0% | 🔴 plan Keiko |
| PARTIDO DEMOCRÁTICO FEDERAL — Armando Masse | 0% | 85.3% | 14.7% | 0% | 🔴 plan Keiko |
| SOMOS PERÚ — George Forsyth | 37.4% | 62.6% | 0% | 0% | 🔴 plan 60% Keiko |
| FRENTE DE LA ESPERANZA — Fernando Olivera | 0% | 98.7% | 1.3% | 0% | ✅ |
| PARTIDO MORADO — Mesías Guevara | 0% | 77.1% | 14.9% | 7.9% | ✅ (con abstención) |
| PAÍS PARA TODOS — Carlos Álvarez | 82.2% | 10.6% | 5.0% | 2.3% | ✅ |
| PARTIDO PATRIÓTICO — Herbert Caller | 0% | 90.5% | 9.5% | 0% | 🔴 plan Keiko |
| COOPERACIÓN POPULAR — Yonhy Lescano | 0% | 100% | 0% | 0% | ✅ |
| INTEGRIDAD DEMOCRÁTICA — Wolfgang Grozo | 90.5% | 0% | 9.5% | 0% | ✅ |
| PERÚ LIBRE — Vladimir Cerrón | 0% | 100% | 0% | 0% | ✅ |
| PERÚ ACCIÓN — Francisco Diez-Canseco | 0% | 91.8% | 7.4% | 0.8% | 🔴 plan Keiko |
| PERÚ PRIMERO — Mario Vizcarra | 50% | 40% | 1% | 9% | 📝 editorial |
| PRIN — Walter Chirinos | 50% | 40% | 1% | 9% | 📝 editorial |
| SICREO — Carlos Espi | 63.2% | 25.4% | 11.4% | 0% | ✅ |
| PODEMOS PERÚ — José Luna | 0% | 94.2% | 5.8% | 0% | 🔴 plan Keiko (anti-establishment) |
| PRIMERO LA GENTE — Marisol Pérez Tello | 33.0% | 41.2% | 13.0% | 12.7% | ⚠️ alta abstención |
| PROGRESEMOS — Paul Jaimes | 0% | 96.4% | 3.6% | 0% | 🔴 plan Keiko |
| RENOVACIÓN POPULAR — López Aliaga | 99.1% | 0% | 0.9% | 0% | ✅ |
| SALVEMOS AL PERÚ — Antonio Ortiz | 0% | 81.7% | 18.3% | 0% | 🔴 plan Keiko |
| UN CAMINO DIFERENTE — Rosario Fernández | 59.2% | 30.7% | 6.7% | 3.4% | ✅ |
| UNIDAD NACIONAL — Roberto Chiabra | 88.6% | 0% | 11.4% | 0% | ✅ |
| *BLANCOS 1V* | 32.6% | 31.7% | 14.7% | 21.0% | calibrado |
| *NULOS 1V* | 36.0% | 29.2% | 13.1% | 22.0% | calibrado |
| *ABSTENCIÓN 1V* | 0% | 0% | 0% | 100% | no se movilizan |

**Resumen de sorpresas:** 12 partidos completamente invertidos (🔴) y 6 con diferencia material (⚠️) respecto al plan editorial original. La abstención inter-vuelta media es ~9.2%, no 0%.

---

*Documento generado el 2026-06-07. Última revisión: 2026-06-11.*  
*`partido_id=8` (Keiko FP), `partido_id=10` (Sánchez JPP) confirmados en datos reales del scraper.*  
*Pesos NNLS calibrados con 86,124 mesas (onpe.ozamora.com/proyeccion.php, corte 2026-06-11). Datos aún incompletos (~1,660 mesas pendientes) — re-calibrar cuando llegue al 100%.*
