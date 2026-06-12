# ONPE MCP — Elecciones Generales Perú 2026 (1ª y 2ª vuelta)

[![Tests](https://img.shields.io/badge/tests-581%20passing-brightgreen)]() [![Python](https://img.shields.io/badge/python-3.11+-blue)]() [![MCP](https://img.shields.io/badge/protocol-MCP-purple)]() [![Coverage 2V](https://img.shields.io/badge/2V%20cobertura-98.25%25-success)]()

Servidor **[Model Context Protocol](https://modelcontextprotocol.io/)** de grado empresarial que expone las **92,766 mesas presidenciales** y los **resultados oficiales ONPE** de las elecciones generales del Perú 2026 (1ª y 2ª vuelta) a cualquier asistente de IA compatible con MCP (Claude, GPT, Gemini, etc.).

## ¿Qué es esto? (para quienes no son técnicos)

Imagina que puedes **preguntarle a un asistente de IA** cosas como:

> *"¿Cuántos votos sacó Keiko Fujimori en Puno?"*
> *"¿Quién ganó la segunda vuelta en Lima?"*
> *"¿Qué pasó en la mesa 900100 — comparado con la primera vuelta?"*
> *"¿Cómo fluyeron los votos del Partido Cívico Obras hacia los finalistas en 2V?"*
> *"¿Hubo fraude en las mesas 900K? — es verdad?"*

…y recibir una respuesta inmediata con datos reales de la ONPE, **sin buscar en PDFs, sin abrir el portal web, sin saber de tecnología**.

**ONPE MCP es el puente** entre un asistente de IA y los datos oficiales de las elecciones presidenciales del Perú 2026. Tiene las 92,766 mesas de sufragio (ambas vueltas), resultados pre-computados por departamento, provincia, distrito, ciudad y país exterior, modelo de transferencia de votos calibrado por NNLS sobre 86,124 mesas, y responde en **menos de un segundo**.

### ¿Para qué sirve?

| Quiero saber... | Ejemplo de pregunta |
|---|---|
| Resultados de una mesa específica (1V o 2V) | *"dame los resultados de la mesa 900574"* |
| Comparar 1V vs 2V en una mesa | *"compara primera y segunda vuelta de la mesa 000900"* |
| Quién ganó la 2V en mi región | *"resultados segunda vuelta en Lima — top candidatos"* |
| Quién ganó la 1V en mi región | *"top 5 en Puno — quiénes fueron los más votados"* |
| Proyección de transferencia 1V→2V | *"cómo se proyectan los votos en mesas 900K"* |
| Cobertura del escrutinio 2V | *"cuál es la cobertura por departamento en segunda vuelta"* |
| Locales reubicados entre vueltas | *"qué locales se reasignaron en Trujillo"* |
| Votos de un candidato | *"cuántos votos sacó Rafael López Aliaga a nivel nacional"* |
| Resultados peruanos en el exterior | *"quién ganó entre los peruanos en Suecia"* |
| Legislativo | *"quién fue el diputado más votado en Lima"* |
| Contexto electoral y verificación | *"¿qué es el STAE?, ¿puede manipular votos?"* |
| Análisis profundo 900K | Ver [`docs/analisis-mesas-900k.md`](docs/analisis-mesas-900k.md) |

### ¿Cómo funciona por dentro? (sin tecnicismos)

1. **Tú preguntas** en lenguaje natural — no necesitas saber códigos ni formatos especiales.
2. **El asistente entiende** qué quieres (una mesa, una región, un candidato…).
3. **Primero busca en la base de datos local** — respuesta en milisegundos, sin internet.
4. **Si no lo tiene guardado**, consulta directamente la ONPE — un poco más lento pero siempre actualizado.
5. **Si la pregunta es sobre el proceso electoral** (fraude, STAE, segunda vuelta…), responde con un compendio de 535 hechos verificados.

> La base de datos local se descarga automáticamente la primera vez que arrancas el servidor (~2 minutos). Después de eso, todo es instantáneo.

---

Estrategia **cache-first** de 3 tiers: **SQLite local** (`<100 ms`) → **API ONPE live** (`~1-8 s`) → **compendio cualitativo verificable** de 535 hechos sobre el proceso electoral. Soporte completo para 1V, 2V y comparaciones entre vueltas.

---

## ⚡ Instalación desde cero

```bash
# 1. Clonar e instalar
git clone https://github.com/oscarzamora/onpe-mcp
cd onpe-mcp
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

# 2. Clonar los scrapers (ambas vueltas) — ÚNICA fuente oficial para bootstrap
git clone https://github.com/oscarzamora/onpescraper ../onpescraper
git clone https://github.com/oscarzamora/onpe-scraper-2026-2 ../onpe-scraper-2026-2

# 3. Arrancar el servidor MCP
onpe-mcp
```

> **Importante:** la base de datos (`data/onpe.db`, ~250 MB) y los archivos `raw/` **NO se distribuyen** en el repositorio. Se generan localmente en el primer arranque a partir de los scrapers oficiales. Esto garantiza que cada deploy tenga datos auditables y trazables al origen.

### Verificación post-instalación

```bash
pytest                                  # corre la suite (581 tests, ~25s)
onpe-mcp                                # arranca servidor MCP (modo stdio)
```

---

## 🗄️ Hidratación de la base de datos (bootstrap completo)

**Política del proyecto:** todo bootstrap se hace **desde los scrapers oficiales**. La base SQLite es 100% derivable de los archivos planos que generan los repos `onpescraper` (1V) y `onpe-scraper-2026-2` (2V). Esto garantiza trazabilidad, reproducibilidad y posibilidad de auditoría.

### Pipeline de bootstrap (orden de ejecución)

```
┌─ Scraper 1V ──┐    ┌─ Bootstrap MCP ──────────────────┐    ┌─ SQLite local ─┐
│  onpescraper  │ →  │ onpe_bootstrap_snapshot()        │ →  │  92,766 mesas  │
│   output/*.txt│    │  · mesas_data, votos, agrupaciones│   │  3.8M votos    │
└───────────────┘    └──────────────────────────────────┘    └────────────────┘

┌─ Scraper 2V ───────────┐  ┌─ Bootstrap MCP ──────────┐   ┌─ SQLite local ─┐
│ onpe-scraper-2026-2    │→ │ onpe_sv_bootstrap()      │→  │  92,766 mesas  │
│  output/*.txt          │  │  · mesas_sv, votos_sv,   │   │  4 partidos    │
│  resumen/*.txt         │  │    ubicaciones_sv,       │   │  + agregados   │
│                        │  │    locales_reasignados,  │   │  geográficos   │
│                        │  │    sv_resumen_*          │   │  pre-computados│
└────────────────────────┘  └──────────────────────────┘   └────────────────┘
```

### Cold start automático

Al arrancar con base vacía, `onpe-mcp` ejecuta:

```
INFO  Bootstrap 1V desde ../onpescraper/output/ ............. (~30-60 s)
INFO  Bootstrap 2V desde ../onpe-scraper-2026-2/output/ ..... (~10-20 s)
INFO  Bootstrap 2V resumen desde ../onpe-scraper-2026-2/resumen/ (~5 s)
INFO  Pre-computando agregados geográficos (distrito/ciudad)  (~5 s)
INFO  Sembrando mapa de transferencia NNLS .................. (~1 s)
INFO  Hidratación completada en 51.2 s — 92,766 mesas 1V + 92,766 mesas 2V.
```

### Hidratación manual (desde el agente MCP)

```python
# === Primera vuelta ===
onpe_bootstrap_snapshot()             # carga 1V desde ../onpescraper/output/
onpe_bootstrap_atu_manera()           # FALLBACK: descarga CSV público si no hay scraper local

# === Segunda vuelta ===
onpe_sv_bootstrap()                   # carga 2V desde ../onpe-scraper-2026-2/
onpe_sv_refresh()                     # re-importa 2V (UPSERT) — usar tras `git pull` del scraper

# === Catálogos auxiliares ===
onpe_sync_foreign_catalog()           # países y ciudades del exterior (live API ONPE)
onpe_sync_domestic_catalog()          # ubigeos domésticos
```

### Verificar estado de la DB

```python
onpe_health()                         # estado 1V + 2V, cobertura, próximo paso sugerido
onpe_sv_cobertura()                   # % actas contabilizadas por departamento (2V)
```

**DB hidratada y lista (ambas vueltas):**
```json
{
  "status": "ok",
  "hydrated": true,
  "total_mesas_local": 92766,
  "total_votos_local": 3801438,
  "sv_total_mesas": 92766,
  "sv_coverage_pct": 98.25,
  "coverage_pct": 99.9,
  "next_step": null
}
```

### Refrescar 2V tras nuevo escrutinio

La segunda vuelta sigue contabilizándose en tiempo real. Para sincronizar:

```bash
cd ../onpe-scraper-2026-2 && git pull   # nuevos datos del scraper
```
```python
onpe_sv_refresh()                       # UPSERT idempotente en SQLite
```

---

## 🏗️ Arquitectura de datos

```
onpe-mcp/
├── data/
│   ├── onpe.db          ← SQLite: mesas, votos, cache, índices pre-computados
│   ├── raw/events.jsonl ← log append-only de cada tool call
│   └── reports/         ← resúmenes markdown diarios
├── src/onpe_mcp/
│   ├── server.py        ← tools MCP + NLU/intent routing
│   ├── storage.py       ← DataStore: todas las queries SQLite
│   ├── onpe_api.py      ← cliente HTTP directo a ONPE
│   ├── gateway.py       ← bridge a onpescraper (import dinámico)
│   ├── knowledge_base.py← 535 hechos verificados sobre el proceso
│   └── config.py        ← Settings desde variables de entorno
```

### Prioridad de datos en `onpe_chat`

| Tier | Fuente | Latencia |
|------|--------|----------|
| **1a** | `mesa_cache` SQLite (JSON API cacheado, TTL 15 min) | ~1 ms |
| **1b** | `mesas_data` + `votos` SQLite (snapshot hidratado) | ~5 ms |
| **2** | API ONPE live (`resultadoelectoral.onpe.gob.pe`) | ~1-8 s |
| **3** | Compendio cualitativo (535 hechos verificados) | ~0 ms |

---

## 🛠️ Tools MCP

### Núcleo (lenguaje natural y mesa individual)

| Tool | Descripción |
|------|-------------|
| `onpe_chat` | **Interfaz principal** — lenguaje natural, cache-first, intención automática, soporte 1V + 2V + legislativo |
| `onpe_get_mesa` | Consulta una mesa de 1V por código (cache → live API) |
| `onpe_get_mesas_batch` | Hasta 200 mesas en paralelo (siempre live) |
| `onpe_health` | Estado del servidor, DB y cobertura de hidratación |

### Bootstrap y sincronización

| Tool | Descripción |
|------|-------------|
| `onpe_bootstrap_snapshot` | Carga 1V desde `../onpescraper/output/` → SQLite |
| `onpe_bootstrap_atu_manera` | Fallback: descarga CSV público de 1V → SQLite (~2-5 min) |
| `onpe_sv_bootstrap` | Carga 2V desde `../onpe-scraper-2026-2/` (mesas + resumen + reasignados) |
| `onpe_sv_refresh` | UPSERT idempotente de 2V tras `git pull` del scraper |
| `onpe_sync_foreign_catalog` | Sincroniza catálogo país/ciudad para mesas del exterior |
| `onpe_sync_domestic_catalog` | Sincroniza catálogo de ubigeos peruanos |

### Segunda vuelta — consultas y análisis

| Tool | Descripción |
|------|-------------|
| `onpe_sv_get_mesa` | Cabecera, votos y ubicación de mesa en 2V |
| `onpe_sv_resultados_geo` | Resultados 2V por nacional/departamento/provincia/distrito/ciudad/continente/país |
| `onpe_sv_cobertura` | % actas contabilizadas por departamento en 2V |
| `onpe_sv_reasignados` | Locales reubicados entre 1V y 2V (44 locales, ~570 mesas) |
| `onpe_sv_estado_actas` | Estado de actas 2V (contabilizadas, observadas, pendientes) |
| `onpe_sv_comparacion_mesa` | Compara 1V vs 2V para la misma mesa |
| `onpe_sv_comparacion_geo` | Compara 1V vs 2V por prefijo de ubigeo |
| `onpe_sv_proyeccion_transferencia` | Proyección NNLS de cómo se transfirió cada voto 1V → finalistas en 2V. Acepta `ubigeo_prefix` o `mesa_prefix` (soporta shorthand `"900K"`) |

---

## 💬 Ejemplos conversacionales

### 🗳️ Mesa específica

```
"dame los resultados de la mesa 900100"
```
```
Mesa 900100 (IEI 326, Amazonas): Contabilizada.
210 votos emitidos de 248 electores hábiles.
Top: Rafael López Aliaga Cazorla 68v, Keiko Fujimori 55v, Roberto Sánchez 24v.
```

```
"cuántos electores hábiles tuvo la mesa 004521 y quién ganó ahí"
"qué estado tiene el acta de la mesa 000001"
```

### 📊 Resultados por candidato (nivel nacional)

```
"cuántos votos sacó Keiko Fujimori a nivel nacional"
```
```
Candidato Keiko Sofía Fujimori Higuchi (partido 1) tiene 5,432,109 votos
y posición 1 en el consolidado actual.
```

```
"cuántos votos obtuvo Rafael López Aliaga en primera vuelta"
"cuántos votos sacó Roberto Sánchez Palomino"
"quién fue el tercer candidato más votado a nivel nacional"
"qué porcentaje alcanzó Fuerza Popular en 2026"
```

### 🗺️ Resultados por región peruana

```
"top 5 en Puno — quiénes fueron los más votados"
```
```
Top 5 en Puno (4,520 mesas · 946,628 votos emitidos)

1. Keiko Sofía Fujimori Higuchi  — 197,801 votos (20.9%)
2. Roberto Sánchez Palomino      — 178,042 votos (18.8%)
3. Ricardo Belmont Cassinelli    —  98,530 votos (10.4%)
4. Carlos Álvarez Requena        —  73,914 votos  (7.8%)
5. Rafael López Aliaga Cazorla   —  59,703 votos  (6.3%)
```

```
"top 3 en Loreto"
"quién ganó en Cusco en primera vuelta"
"cuántos votos sacó López Aliaga en Arequipa"
"quién fue primero en Ayacucho"
"cuántas mesas tiene Ancash y quién ganó"
"top 3 en Amazonas"
```

### 🌎 Exterior

```
"top 3 de candidatos en Suecia"
"resultados en Estocolmo — quién ganó"
"cuántos votos sacó Keiko Fujimori en Chile"
"quién fue el más votado entre los peruanos en España"
"top 5 candidatos en Argentina"
"cuántos votos hubo en las mesas de Estados Unidos"
```

### 🏛️ Legislativo (live API)

```
"quién fue el diputado más votado en Lima"
"top 10 senadores más votados para Cusco"
"quién ganó los senadores en Arequipa"
"cuántos votos sacó el primer diputado en Piura"
```

### 🔍 Segmentos de mesas

```
"cuántas mesas arrancan en 900 y dónde están"
"top 3 candidatos en las mesas 900K"
"de las mesas que arrancan en 900000, en qué lugares ganó primero López Aliaga"
"cuántos electores hábiles tienen las mesas con prefijo 087"
"cuántas mesas hay en el bloque 150 y qué candidato ganó ahí"
```

### 🥇🥈 Segunda vuelta y comparación entre vueltas

```
"quién ganó la segunda vuelta a nivel nacional"
"resultados segunda vuelta en Lima — top candidatos"
"cuál es la cobertura de actas en segunda vuelta"
"cuántos votos sacó Keiko en segunda vuelta en Cusco"
"compara primera y segunda vuelta de la mesa 000900"
"cómo cambió el voto en Puno entre primera y segunda vuelta"
"qué locales se reasignaron en Trujillo entre vueltas"
"cómo se proyectan los votos del Partido Cívico Obras hacia los finalistas"
"cómo fluyeron los votos en las mesas 900K"
"qué pasó con el voto blanco entre primera y segunda vuelta"
```

### ❓ Contexto y proceso electoral

```
"las mesas 900K son fantasma — es verdad?"
"por qué algunas mesas tienen solo 50 votantes"
"hubo fraude en las elecciones 2026"
"qué es el STAE y puede manipular votos"
"por qué hubo mesas que votaron el lunes 13 de abril"
"cuándo es la segunda vuelta"
"quién pasó a segunda vuelta"
"por qué el sur del Perú vota diferente al norte"
```

---

## 📚 Análisis e investigación

Análisis profundos publicados en este repositorio (datos oficiales + metodología documentada):

| Documento | Descripción |
|-----------|-------------|
| [`docs/analisis-mesas-900k.md`](docs/analisis-mesas-900k.md) | **Análisis completo de las 4,703 mesas 900K**: geografía, comparación 1V vs 2V, mapeo NNLS de transferencia partido → finalistas, foco Lima 900K, queries reproducibles. |
| [`docs/plan-segunda-vuelta.md`](docs/plan-segunda-vuelta.md) | Plan técnico de la extensión 2V: schema, tools, modelo de transferencia, validación contra datos reales. |
| [`docs/qa-plan-segunda-vuelta.md`](docs/qa-plan-segunda-vuelta.md) | Plan de QA enterprise: 30+ escenarios, criterios de aceptación, casos edge. |
| [`docs/onpe-api-contract.md`](docs/onpe-api-contract.md) | Especificación técnica del contrato API ONPE consumido por el MCP. |

---

## ⚙️ Configuración

Copia `.env.example` a `.env` para ajustar valores:

### Variables generales

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ONPE_DATA_DIR` | `./data` | Directorio de la base SQLite y eventos |
| `ONPE_LOG_LEVEL` | `INFO` | Nivel de logging |
| `ONPE_MAX_BATCH_SIZE` | `200` | Límite de lote en `onpe_get_mesas_batch` |
| `ONPE_CACHE_TTL_SECONDS` | `900` | TTL del cache individual de mesa (segundos) |
| `ONPE_GEO_QUERY_CACHE_TTL_SECONDS` | `300` | TTL del cache de queries geográficas (segundos) |

### Primera vuelta (scraper `onpescraper`)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ONPE_SCRAPER_ROOT` | `../onpescraper` | Ruta al repo `onpescraper` (1V) |
| `ONPE_SCRAPER_REPO_URL` | `https://github.com/oscarzamora/onpeescraper` | URL a clonar si no existe |
| `ONPE_SOURCE_DIR` | `$ONPE_SCRAPER_ROOT/source_data` | Datos crudos del scraper |
| `ONPE_OUTPUT_DIR` | `$ONPE_SCRAPER_ROOT/output` | Datos procesados del scraper |
| `ONPE_BOOTSTRAP_ON_STARTUP` | `true` | Refresca desde scraper al arrancar |
| `ONPE_BOOTSTRAP_INCLUDE_VOTES` | `true` | Incluye votos en el snapshot |
| `ONPE_ATU_MANERA_BOOTSTRAP` | `false` | Fuerza descarga CSV ATuManera al inicio |
| `ONPE_ATU_MANERA_CSV_PATH` | _(opcional)_ | Ruta local al CSV ATuManera (evita descarga) |

### Segunda vuelta (scraper `onpe-scraper-2026-2`)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ONPE_SV_SCRAPER_ROOT` | `../onpe-scraper-2026-2` | Ruta al repo del scraper de 2V |
| `ONPE_SV_OUTPUT_DIR` | `$ONPE_SV_SCRAPER_ROOT/output` | Mesas, votos, ubicaciones, reasignados |
| `ONPE_SV_RESUMEN_DIR` | `$ONPE_SV_SCRAPER_ROOT/resumen` | Agregados pre-computados nacional/depto/provincia |

### Auto-hidratación y catálogos

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ONPE_AUTO_HYDRATE_ON_DEMAND` | `true` | Consulta API ONPE para mesas faltantes con baja cobertura |
| `ONPE_AUTO_HYDRATE_MAX_MESAS` | `20` | Máximo de mesas a hidratar bajo demanda por consulta |
| `ONPE_AUTO_SYNC_FOREIGN_CATALOG_ON_DEMAND` | `true` | Sincroniza catálogo extranjero si no hay datos |

---

## 🏛️ Garantías enterprise

- **Trazabilidad completa**: cada tool call se registra en `data/raw/events.jsonl` (append-only).
- **Tests automatizados**: 581 tests, suite ejecutable en ~25 s. CI-ready.
- **Aislamiento de origen**: cada tabla en SQLite tiene timestamp `fetched_at` y origen (`source`, `fuente`).
- **Operaciones idempotentes**: todos los `bootstrap_*` y `refresh` usan UPSERT — re-ejecutar es seguro.
- **Sin datos en el repo**: `data/`, `*.db`, `*.db-wal`, `*.db-shm` están en `.gitignore`. Todo se regenera desde scrapers oficiales.
- **Manejo de errores tipado**: `VALIDATION_ERROR`, `GATEWAY_ERROR`, `API_ERROR` con `error_response()` consistente.
- **Cache-first explícito**: cada respuesta indica el tier de origen (`tier_1_local_cache`, `tier_2_live_api`, `tier_3_knowledge_base`).
- **Verificación factual**: el compendio cualitativo (535 hechos) NO inventa cifras; cuando no hay datos cuantitativos derivables, responde con contexto institucional verificable o redirige a fuente oficial (JNE/RENIEC/ONPE).
- **Soporte multi-modelo**: cualquier cliente MCP-compatible (Claude Desktop, Cline, Continue, Cody, agentes custom).

---

## 📋 Requisitos

- Python 3.11+
- Git (para clonar los scrapers)
- ~500 MB de espacio en disco para `data/` (SQLite + raw events + reports)
- Acceso a internet en el primer arranque (clonar scrapers / descargar ATuManera CSV)

---

## 🧪 Desarrollo y testing

```bash
pip install -e ".[dev]"                 # instala con extras dev (pytest, ruff, etc.)
pytest                                  # corre 581 tests
pytest tests/test_storage.py -v         # solo storage
pytest -k "proyeccion_sv_by_mesa_prefix"  # solo tests de mapeo 1V→2V por prefijo
onpe-mcp                                # arranca servidor MCP (stdio)
```

---

## 📐 Contratos y schemas

- Especificación técnica API ONPE: [`docs/onpe-api-contract.md`](docs/onpe-api-contract.md)
- JSON schema response: [`schemas/onpe.actas.buscar.mesa.response.schema.json`](schemas/onpe.actas.buscar.mesa.response.schema.json)
- JSON schema acta mínima: [`schemas/onpe.acta.min.schema.json`](schemas/onpe.acta.min.schema.json)

---

## 📄 Licencia y atribución

Datos oficiales de la **Oficina Nacional de Procesos Electorales (ONPE), Perú** — disponibles públicamente en <https://resultadoelectoral.onpe.gob.pe>. Este proyecto es una herramienta de consulta y análisis, sin afiliación oficial con ONPE.
