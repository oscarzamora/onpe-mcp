# ONPE MCP — Elecciones Presidenciales Perú 2026 + 2021 (histórico)

[![Tests](https://img.shields.io/badge/tests-410%2B%20passing-brightgreen)]() [![Python](https://img.shields.io/badge/python-3.11+-blue)]() [![MCP](https://img.shields.io/badge/protocol-MCP-purple)]() [![Data 2021](https://img.shields.io/badge/2021%20data-complete-blue)]()

Servidor **[Model Context Protocol](https://modelcontextprotocol.io/)** de grado empresarial que expone:
- **2026**: Las **92,766 mesas presidenciales** de 1ª y 2ª vuelta con resultados oficiales ONPE
- **2021**: Dataset completo histórico de **86,488 mesas** (1ª y 2ª vuelta)

Compatible con cualquier asistente de IA con soporte MCP (Claude, GPT, Gemini, etc.). Responde en **menos de un segundo** con datos locales de SQLite.

## ¿Qué es esto? (para quienes no son técnicos)

Imagina que puedes **preguntarle a un asistente de IA** cosas como:

> "¿Cuántos votos sacó Keiko Fujimori en Puno en 2026?"
> "¿Quién ganó la segunda vuelta en Lima en 2026?"
> "Compara los votos de Pedro Castillo en 2021 2V vs Keiko en 2026 1V"
> "¿Qué pasó en la mesa 900100 en 2026 — comparado con 2021?"
> "¿Cómo fluyeron los votos del Partido Cívico Obras hacia los finalistas en 2026 2V?"

…y recibir una respuesta inmediata con **datos reales de ONPE sin necesidad de buscar PDFs, abrir portales o tener conocimientos técnicos**.

**ONPE MCP es el puente** entre un asistente de IA y los datos electorales oficiales. Tiene ambas vueltas 2026 (92,766 mesas), dataset histórico 2021 (86,488 mesas), modelo de transferencia de votos calibrado por NNLS, y responde en **menos de un segundo**.

### ¿Para qué sirve?

**Todos los ejemplos de consulta usan MCP**: el asistente elige automáticamente el tool necesario (`onpe_chat` para 2026 y `onpe_2021_chat` para histórico 2021).

| Quiero saber... | Ejemplo con MCP |
|---|---|
| Resultados 2026 de una mesa específica (1V o 2V) | "dame los resultados de la mesa 900574 en 2026" |
| Comparar 2026 1V vs 2V en una mesa | "compara primera y segunda vuelta de la mesa 000900 en 2026" |
| Comparativa 2021 vs 2026 | "compara Pedro Castillo 2021 2V vs Keiko 2026 1V" |
| Resultados 2021 (histórico) | "quién ganó en Lima en 2021 segunda vuelta", "top 5 en Puno 2021" |
| Quién ganó la 2V 2026 en mi región | "resultados segunda vuelta en Lima 2026 — top candidatos" |
| Quién ganó la 1V en mi región | "top 5 en Puno 2026 — quiénes fueron los más votados" |
| Proyección de transferencia 1V→2V | "cómo se proyectan los votos en mesas 900K" |
| Cobertura del escrutinio 2V | "cuál es la cobertura por departamento en segunda vuelta 2026" |
| Locales reubicados entre vueltas | "qué locales se reasignaron en Trujillo" |
| Votos de un candidato | "cuántos votos sacó Rafael López Aliaga a nivel nacional en 2026" |
| Resultados peruanos en el exterior | "quién ganó entre los peruanos en Suecia en 2026" |
| Contexto electoral y verificación | "¿qué es el STAE?, ¿puede manipular votos?" |
| Análisis profundo 900K | Ver [`docs/analisis-mesas-900k.md`](docs/analisis-mesas-900k.md) |

### ¿Cómo funciona por dentro? (sin tecnicismos)

1. **Tú preguntas** en lenguaje natural — no necesitas saber códigos ni formatos especiales.
2. **El asistente entiende** qué quieres (una mesa, una región, un candidato…).
3. **Primero busca en la base de datos local** — respuesta en milisegundos, sin internet.
4. **Si no lo tiene guardado**, responde que falta en la base local para mantener modo local-only.
5. **Si la pregunta es sobre el proceso electoral** (fraude, STAE, segunda vuelta…), responde con un compendio de 535 hechos verificados.

> La base de datos local se descarga automáticamente la primera vez que arrancas el servidor (~2 minutos). Después de eso, todo es instantáneo.

---

Estrategia **cache-first** local: **SQLite denorm local** (`<100 ms`) → **compendio cualitativo verificable** de 535 hechos sobre el proceso electoral. Soporte completo para 1V, 2V y comparaciones entre vueltas.

---

## ⚡ Instalación desde cero

```bash
# 1. Clonar e instalar
git clone https://github.com/oscarzamora/onpe-mcp
cd onpe-mcp
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

# 2. Clonar los datos: scrapers 2026 + dataset histórico 2021
git clone https://github.com/oscarzamora/onpescraper ../onpescraper
git clone https://github.com/oscarzamora/onpe-scraper-2026-2 ../onpe-scraper-2026-2
git clone https://github.com/oscarzamora/peruvoto2021 ../peruvoto2021

# 3. Arrancar el servidor MCP
onpe-mcp
```

> **Importante:** la base de datos (`data/onpe_denorm.db`) y los archivos `raw/` **NO se distribuyen** en el repositorio. Se generan localmente en el primer arranque a partir de los scrapers oficiales y dataset 2021. Esto garantiza que cada deploy tenga datos auditables, trazables y verificables.

### Verificación post-instalación

```bash
pytest                                  # corre la suite (410+ tests, ~30s)
onpe-mcp                                # arranca servidor MCP (modo stdio)
```

Ejemplos rápidos de consulta tras arranque:
```python
onpe_health()                           # estado 2026 + 2021, cobertura
onpe_get_mesa("900100")                 # mesa 2026
# "top 5 en Lima 2021"                  # query histórico 2021
# "Keiko vs Sanchez 2V"                 # 2026 segunda vuelta
```

---

## 🗄️ Hidratación de la base de datos (bootstrap completo)

**Política del proyecto:** todo bootstrap se hace **desde fuentes oficiales auditables**:
- 2026: Scrapers oficiales (`onpescraper`, `onpe-scraper-2026-2`)
- 2021: Dataset CSV histórico del repo `peruvoto2021`

La base SQLite es 100% derivable de archivos planos, garantizando trazabilidad, reproducibilidad y auditoría.

> Si necesitas llevar esta hidratación a otra plataforma (MySQL, SQL Server, Snowflake o Fabric Warehouse), revisa el plan dedicado: [docs/plan-multi-db-hydration.md](docs/plan-multi-db-hydration.md).

### Pipeline de bootstrap (orden de ejecución)

```
┌─ Scraper 1V 2026 ┐   ┌─ Bootstrap MCP ──────────────────┐    ┌─ SQLite local ─┐
│  onpescraper     │→  │ onpe_bootstrap_snapshot()        │→   │  92,766 mesas  │
│  output/*.txt    │   │  · mesas_data, votos, grupos     │    │  3.8M votos    │
└──────────────────┘   └──────────────────────────────────┘    └────────────────┘

┌─ Dataset 2021 ──────┐  ┌─ Bootstrap MCP ──────────┐   ┌─ SQLite local ───┐
│ peruvoto2021/data   │→ │ onpe_2021_bootstrap()    │→  │  86,488 mesas    │
│  *.csv (1V+2V)      │  │  · mesas_2021, votos_2021│   │  1.7M votos      │
└─────────────────────┘  │  · 20 partidos (ambas V) │   │  partidos_2021   │
                         └──────────────────────────┘   └──────────────────┘

┌─ Scraper 2V 2026 ──────┐  ┌─ Bootstrap MCP ──────────┐   ┌─ SQLite local ─┐
│ onpe-scraper-2026-2    │→ │ onpe_sv_bootstrap()      │→  │  92,766 mesas  │
│  output/*.txt          │  │  · mesas_sv, votos_sv,   │   │  + agregados   │
│  resumen/*.txt         │  │    reasignados, resumen  │   │  geográficos   │
└────────────────────────┘  └──────────────────────────┘   └────────────────┘
```

### Cold start automático

Al arrancar con base vacía, `onpe-mcp` ejecuta:

```
INFO  Bootstrap 1V 2026 desde ../onpescraper/output/ ........ (~30-60 s)
INFO  Bootstrap 2021 desde ../peruvoto2021/data/*.csv ....... (~10-15 s)
INFO  Bootstrap 2V 2026 desde ../onpe-scraper-2026-2/ ....... (~10-20 s)
INFO  Bootstrap resumen 2V desde resumen/ ................... (~5 s)
INFO  Pre-computando agregados geográficos .................. (~5 s)
INFO  Sembrando mapa de transferencia NNLS .................. (~1 s)
INFO  Hidratación completada en ~65s — 2026: 92,766+92,766 mesas · 2021: 86,488 mesas
```

### Hidratación manual (desde el agente MCP)

```python
# === Primera vuelta 2026 ===
onpe_bootstrap_snapshot()             # carga 1V desde ../onpescraper/output/
onpe_bootstrap_atu_manera()           # FALLBACK: descarga CSV público si no hay scraper

# === Dataset histórico 2021 (1V + 2V) ===
onpe_2021_bootstrap()                 # carga CSV oficiales desde ../peruvoto2021/data/

# === Segunda vuelta 2026 ===
onpe_sv_bootstrap()                   # carga 2V desde ../onpe-scraper-2026-2/
onpe_sv_refresh()                     # re-importa 2V (UPSERT) — usar tras `git pull`

# === Catálogos auxiliares ===
onpe_sync_foreign_catalog()           # deshabilitado en local-only (usa datos ya cargados)
onpe_sync_domestic_catalog()          # deshabilitado en local-only (usa datos ya cargados)
```

### Verificar estado de la DB

```python
onpe_health()                         # estado 2026 (1V+2V) + 2021, cobertura
onpe_sv_cobertura()                   # % actas contabilizadas por departamento (2V 2026)
```

**DB hidratada completamente (2026 + 2021):**
```json
{
  "status": "ok",
  "hydrated": true,
  "total_mesas_local": 92766,
  "total_votos_local": 3801438,
  "total_mesas_2021_v1": 86488,
  "total_mesas_2021_v2": 86488,
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

### Flujo recomendado en frío (pull + hydrate + denorm + tests)

Para dejar el entorno reproducible y con la suite completa en verde, usa esta secuencia end-to-end:

```bash
# 1) Pull de repos
git pull --ff-only
git -C ../onpescraper pull --ff-only
git -C ../onpe-scraper-2026-2 pull --ff-only
git -C ../peruvoto2021 pull --ff-only

# 2) Hidratación runtime (1V + 2021 + 2V)
python -c "import json; from onpe_mcp.server import onpe_bootstrap_snapshot,onpe_2021_bootstrap,onpe_sv_bootstrap; print(json.dumps(onpe_bootstrap_snapshot(force=True), ensure_ascii=False)); print(json.dumps(onpe_2021_bootstrap(force=True), ensure_ascii=False)); print(json.dumps(onpe_sv_bootstrap(force=True), ensure_ascii=False))"

# 3) Snapshot seguro para build_denorm
python -c "import sqlite3; s=sqlite3.connect('data/onpe_denorm.db'); d=sqlite3.connect('data/source_snapshot.db'); s.backup(d); d.close(); s.close(); print('SNAPSHOT_OK')"

# 4) Materializar denorm BI
python scripts/build_denorm.py --src data/source_snapshot.db --dest data/onpe_denorm.db

# 5) Rehidratar runtime (obligatorio: build_denorm recrea la DB)
python -c "import json; from onpe_mcp.server import onpe_bootstrap_snapshot,onpe_2021_bootstrap,onpe_sv_bootstrap; print(json.dumps(onpe_bootstrap_snapshot(force=True), ensure_ascii=False)); print(json.dumps(onpe_2021_bootstrap(force=True), ensure_ascii=False)); print(json.dumps(onpe_sv_bootstrap(force=True), ensure_ascii=False))"

# 6) Tests
python -m pytest tests -q --tb=short
```

> Nota: si `../onpe-scraper-2026-2` tiene cambios locales, resuélvelos antes de `git pull` para evitar bloqueos.

---

## 🏗️ Arquitectura de datos

```
onpe-mcp/
├── data/
│   ├── onpe_denorm.db   ← SQLite denorm: facts/dims + tablas runtime MCP
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
| **0** | `onpe_denorm.db` — facts/dims y tablas runtime MCP | **<1 ms** |
| **1** | Cache de query en SQLite local (`mesa_cache`, `query_cache`) | ~1-5 ms |
| **2** | Compendio cualitativo (535 hechos verificados) | ~0 ms |

### Modelo Analítico BI (`onpe_denorm.db`)

Pre-materializa **todas las permutaciones** `election_year × vuelta × geo × partido` para las 4 elecciones disponibles. Incluye votos del exterior como ciudadano de primera clase.

**Tablas fact (8 tablas, ~8 M filas totales):**

| Tabla | Grain | Filas |
|-------|-------|------:|
| `fact_votos_mesa` | election × vuelta × mesa × partido | ~6.5 M |
| `fact_votos_ubigeo` | election × vuelta × distrito × partido | ~150 K |
| `fact_votos_provincia` | election × vuelta × provincia × partido | ~14 K |
| `fact_votos_departamento` | election × vuelta × departamento × partido | ~1.9 K |
| `fact_votos_pais` | election × vuelta × país × partido | ~5 K |
| `fact_votos_nacional` | election × vuelta × partido | 72 |
| `dim_eleccion` | proceso electoral | 4 |
| `dim_partido` | partido × elección | 72 |

**Benchmark histórico vs baseline legacy (26 queries, mediana de 5 ejecuciones):**

> **99.6% reducción de tiempo — speedup mediano 1,116×**

| Categoría | Baseline legacy | Denorm | Speedup |
|-----------|-----:|-------:|--------:|
| Nacionales / departamento / provincia | 250–10,000 ms | <1 ms | >999× |
| Mesa range (1–500 mesas) | 388 ms | 36 ms | 10.7× |
| País exterior | 200–230 ms | 2–3 ms | 87–120× |
| Mesa exacta | ~0.1 ms | ~0.1 ms | ~1× |

**Construir / validar el modelo:**
```bash
python scripts/build_denorm.py                # reconstruye (~108 s, ~1.9 GB)
python scripts/build_denorm.py --validate-only # solo valida (7/7 checks)
python scripts/benchmark_denorm.py            # corre 26 queries baseline legacy vs Denorm
```

> El MCP opera sobre `data/onpe_denorm.db` como única base de datos runtime.
> Tras rehidratación, todas las rutas 2026 responden desde denorm/local.

---

## 🛠️ Tools MCP

### Núcleo (lenguaje natural y mesa individual)

| Tool | Descripción |
|------|-------------|
| `onpe_chat` | **Interfaz principal** — lenguaje natural, cache-first, intención automática. Soporta **2026 (1V+2V) + 2021 (histórico)** en modo local-only. Routea automáticamente por año. |
| `onpe_query` | Motor analítico estructurado (fase inicial): `select + where + order_by + paginación` sobre facts denorm. |
| `onpe_filter_mesas` | Atajo para búsqueda inversa por predicado de votos (ej. mesas con 0 votos de un partido). |
| `onpe_get_mesa` | Consulta mesa 2026 1V por código desde cache/local DB |
| `onpe_get_mesas_batch` | Hasta 200 mesas 2026 1V en paralelo desde cache/local DB |
| `onpe_health` | Estado del servidor, DB 2026/2021 y cobertura de hidratación |

### Analítica controlada (`db_*`)

| Tool | Descripción |
|------|-------------|
| `db_query` | Puerta analítica read-only con request estructurado, presets y metadatos de trazabilidad (`query_id`, `snapshot_id`, `request_hash`). |
| `db_search` | Descubre entidades canónicas (geo/partido/candidato) para alimentar `db_query` sin depender de SQL ad hoc. |
| `db_batch_execute` | Ejecuta lote de consultas `db_query` con límites y `stop_on_error` para orquestación controlada. |

### Bootstrap y sincronización

| Tool | Descripción |
|------|-------------|
| `onpe_bootstrap_snapshot` | Carga 2026 1V desde `../onpescraper/output/` → SQLite |
| `onpe_bootstrap_atu_manera` | Fallback: descarga CSV público de 2026 1V → SQLite (~2-5 min) |
| `onpe_2021_bootstrap` | Carga 2021 (1V+2V) desde `../peruvoto2021/data/*.csv` — ambas vueltas en tablas separadas |
| `onpe_sv_bootstrap` | Carga 2026 2V desde `../onpe-scraper-2026-2/` (mesas + resumen + reasignados) |
| `onpe_sv_refresh` | UPSERT idempotente de 2026 2V tras `git pull` del scraper |
| `onpe_sync_foreign_catalog` | Deshabilitado en local-only (solo disponible fuera de modo estricto) |
| `onpe_sync_domestic_catalog` | Deshabilitado en local-only (solo disponible fuera de modo estricto) |

### Chat especializado para 2021 (histórico)

| Tool | Descripción |
|------|-------------|
| `onpe_2021_chat` | **Interfaz NL para 2021** — soporta preguntas sobre 1V, 2V, comparativas 2021, mesas, candidatos (Pedro Castillo, Keiko, Fujimori, etc.), análisis geográfico. Lee de tablas `mesas_2021`, `votos_2021`, `partidos_2021`. |

### Raw data 2021 (para análisis estadístico arbitrario)

> Diseñados para que cualquier asistente IA o herramienta externa (pandas, R, Power BI) pueda consumir datos crudos y construir sus propios análisis (HHI, NNLS, bootstrap, correlaciones, etc.) sin depender de agregaciones pre-computadas. Soportan filtros geográficos (dpto/prov/distrito/ubigeo_prefix/mesa_prefix), paginación (`limit` + `offset`), y devuelven `has_more` para iterar.

| Tool | Descripción |
|------|-------------|
| `onpe_2021_export_mesas` | Cabecera por mesa: geo + electores + votos emitidos/válidos/blancos/nulos. |
| `onpe_2021_export_votos` | 1 fila por (mesa × partido) con votos + geo enriquecido. Filtro `partido_ids`. |
| `onpe_2021_export_partidos` | Catálogo completo de partidos y candidatos (1V y/o 2V). |
| `onpe_2021_summary` | Resumen agregado nacional por vuelta (totales + por partido + %). |

### Raw data 2026 1V — paridad con 2021

| Tool | Descripción |
|------|-------------|
| `onpe_export_mesas` | Cabecera por mesa 2026 1V (geo + electores + emit/válidos/blancos/nulos + estado_acta). Filtros: dpto/prov/distrito/ubigeo_prefix/mesa_prefix/estado_acta. |
| `onpe_export_votos` | 1 fila por (mesa × partido) 2026 1V con geo enriquecido. Filtro `partido_ids`. |
| `onpe_export_partidos` | Catálogo 2026 1V (38 partidos + blanco/nulo/impugnado con `is_candidate` y `candidato` cuando existe en `source_data/candidato.txt`). |
| `onpe_summary` | Resumen agregado nacional 2026 1V (totales + por partido + %). |
| `onpe_resultados_geo` | Top N candidatos por nivel geo (nacional/dpto/prov/distrito). Análogo a `onpe_sv_resultados_geo`. |
| `onpe_cobertura` | Cobertura 2026 1V por departamento. Análogo a `onpe_sv_cobertura`. |

### Raw data 2026 2V — paridad con 1V

| Tool | Descripción |
|------|-------------|
| `onpe_sv_export_mesas` | Cabecera por mesa 2V con geo + estado (C/E/P). Filtro `codigo_estado_acta`. |
| `onpe_sv_export_votos` | 1 fila por (mesa × partido) 2V con geo enriquecido (incluye continente/país). |
| `onpe_sv_export_partidos` | Catálogo 2V (2 partidos finalistas + blanco/nulo/impugnado). |
| `onpe_sv_summary` | Resumen agregado nacional 2V (solo actas Contabilizadas). |

### Catálogos, listados y analítica genérica

| Tool | Descripción |
|------|-------------|
| `onpe_list_departamentos` | Lista los 25 dptos peruanos + #provincias y #distritos. |
| `onpe_list_partidos` | Lista todos los partidos para una vuelta 2026 (1 = 38, 2 = 2). |
| `onpe_list_foreign_geo` | Continentes/países/ciudades con voto extranjero. |
| `onpe_top_candidato_geo` | Top N geos (distrito/prov/dpto) donde un candidato es más fuerte. Vuelta 1 o 2. |
| `onpe_stats_participacion` | Distribución estadística de participación por mesa (media, σ, p10/p25/p50/p75/p90). |
| `onpe_audit_votos_consistency` | Detecta mesas donde Σ votos partido ≠ votos_validos en cabecera. |
| `onpe_audit_coverage` | Matriz de cobertura por dpto: "huecos" (mesas sin votos hidratados). |

### Segunda vuelta 2026 — consultas y análisis

| Tool | Descripción |
|------|-------------|
| `onpe_sv_get_mesa` | Cabecera, votos y ubicación de mesa en 2V 2026 |
| `onpe_sv_resultados_geo` | Resultados 2V 2026 por nacional/departamento/provincia/distrito/ciudad/continente/país |
| `onpe_sv_cobertura` | % actas contabilizadas por departamento en 2V 2026 |
| `onpe_sv_reasignados` | Locales reubicados entre 1V y 2V 2026 (44 locales, ~570 mesas) |
| `onpe_sv_estado_actas` | Estado de actas 2V 2026 (contabilizadas, observadas, pendientes) |
| `onpe_sv_comparacion_mesa` | Compara 1V vs 2V 2026 para la misma mesa |
| `onpe_sv_comparacion_geo` | Compara 1V vs 2V 2026 por prefijo de ubigeo |
| `onpe_sv_proyeccion_transferencia` | Proyección NNLS de cómo se transfirió cada voto 1V → finalistas 2V 2026. Acepta `ubigeo_prefix` o `mesa_prefix` (ej: `"900K"`) |

---

## 💬 Ejemplos conversacionales

### 🗳️ Mesa específica (2026)

```
"dame los resultados de la mesa 900100 en 2026"
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

#### 2026

```
"cuántos votos sacó Keiko Fujimori a nivel nacional en 2026"
```
```
Candidato Keiko Sofía Fujimori Higuchi (partido 1) tiene 5,432,109 votos
y posición 1 en el consolidado 2026.
```

```
"cuántos votos obtuvo Rafael López Aliaga en primera vuelta 2026"
"cuántos votos sacó Roberto Sánchez Palomino"
"quién fue el tercer candidato más votado a nivel nacional"
"qué porcentaje alcanzó Fuerza Popular en 2026"
```

#### 2021 (histórico)

```
"cuántos votos sacó Pedro Castillo en 2021 segunda vuelta"
"quién ganó en Peru 2021 - primera vuelta"
"qué porcentaje obtuvo Fujimori en 2021 2V"
```

### 🗺️ Resultados por región peruana

#### 2026 1V

```
"top 5 en Puno — quiénes fueron los más votados en 2026"
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
"top 3 en Loreto 2026"
"quién ganó en Cusco en primera vuelta 2026"
"cuántos votos sacó López Aliaga en Arequipa 2026"
"quién fue primero en Ayacucho"
"cuántas mesas tiene Ancash y quién ganó"
"top 3 en Amazonas"
```

#### 2021 (histórico)

```
"quién ganó en Lima 2021 primera vuelta - top 5"
"top 3 en Puno 2021 segunda vuelta"
"cuántos votos sacó Fujimori en Arequipa 2021"
"quién fue el más votado en Cusco 2021 segunda vuelta"
```

### 🌎 Exterior (2026)

```
"top 3 de candidatos en Suecia 2026"
"resultados en Estocolmo 2026 — quién ganó"
"cuántos votos sacó Keiko Fujimori en Chile 2026"
"quién fue el más votado entre los peruanos en España"
"top 5 candidatos en Argentina 2026"
"cuántos votos hubo en las mesas de Estados Unidos"
```

### 🔍 Segmentos de mesas (2026)

```
"cuántas mesas arrancan en 900 y dónde están en 2026"
"top 3 candidatos en las mesas 900K"
"de las mesas que arrancan en 900000, en qué lugares ganó primero López Aliaga"
"cuántos electores hábiles tienen las mesas con prefijo 087"
"cuántas mesas hay en el bloque 150 y qué candidato ganó ahí"
```

### 🥇🥈 Segunda vuelta y comparación entre vueltas (2026 y 2021)

#### 2026

```
"quién ganó la segunda vuelta a nivel nacional en 2026"
"resultados segunda vuelta en Lima 2026 — top candidatos"
"cuál es la cobertura de actas en segunda vuelta 2026"
"cuántos votos sacó Keiko en segunda vuelta en Cusco"
"compara primera y segunda vuelta de la mesa 000900"
"cómo cambió el voto en Puno entre primera y segunda vuelta 2026"
"qué locales se reasignaron en Trujillo entre vueltas"
"cómo se proyectan los votos del Partido Cívico Obras hacia los finalistas"
"cómo fluyeron los votos en las mesas 900K"
"qué pasó con el voto blanco entre primera y segunda vuelta"
```

#### Comparativa 2021 vs 2026

```
"compara los resultados de Keiko en 2021 primera vuelta vs 2026 primera vuelta"
"cuántos votos sacó Pedro Castillo 2021 segunda vuelta - comparado con alguien en 2026"
"diferencias en Puno entre 2021 y 2026"
"cómo cambió la concentración de votos en Lima entre 2021 y 2026"
```

### ❓ Contexto y proceso electoral

```
"las mesas 900K son fantasma — es verdad?"
"por qué algunas mesas tienen solo 50 votantes"
"hubo fraude en las elecciones 2026"
"qué es el STAE y puede manipular votos"
"por qué hubo mesas que votaron el lunes 13 de abril"
"cuándo fue la segunda vuelta 2026"
"quién pasó a segunda vuelta 2026"
"por qué el sur del Perú vota diferente al norte"
"por qué Fujimori hizo mejor en 2026 que en 2021 en algunas regiones"
"cuál fue el candidato que más mejoró su votación entre 2021 y 2026"
```

---

## 📚 Análisis e investigación

Análisis profundos publicados en este repositorio (datos oficiales + metodología documentada):

| Documento | Descripción |
|-----------|-------------|
| [`docs/analisis-mesas-900k.md`](docs/analisis-mesas-900k.md) | **Análisis completo de las 4,703 mesas 900K**: geografía, comparación 1V vs 2V, mapeo NNLS de transferencia partido → finalistas, foco Lima 900K, queries reproducibles. |
| [`docs/plan-segunda-vuelta.md`](docs/plan-segunda-vuelta.md) | Plan técnico de la extensión 2V: schema, tools, modelo de transferencia, validación contra datos reales. |
| [`docs/onpe-2021-integration-plan.md`](docs/onpe-2021-integration-plan.md) | **Plan de integración 2021**: alcance por niveles (nacional/geo/mesa), preguntas NL posibles, actualización MCP, banco de queries históricas. |
| [`docs/qa-plan-segunda-vuelta.md`](docs/qa-plan-segunda-vuelta.md) | Plan de QA enterprise: 30+ escenarios, criterios de aceptación, casos edge. |
| [`docs/onpe-api-contract.md`](docs/onpe-api-contract.md) | Especificación técnica del contrato API ONPE consumido por el MCP. |
| [`docs/mcp-test-matrix.md`](docs/mcp-test-matrix.md) | Matriz de pruebas MCP del README + permutaciones multi-input (mesas/geos/países). |

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

### Primera vuelta 2026 (scraper `onpescraper`)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ONPE_SCRAPER_ROOT` | `../onpescraper` | Ruta al repo `onpescraper` (1V 2026) |
| `ONPE_SCRAPER_REPO_URL` | `https://github.com/oscarzamora/onpescraper` | URL a clonar si no existe |
| `ONPE_SOURCE_DIR` | `$ONPE_SCRAPER_ROOT/source_data` | Datos crudos del scraper 1V |
| `ONPE_OUTPUT_DIR` | `$ONPE_SCRAPER_ROOT/output` | Datos procesados del scraper 1V |
| `ONPE_BOOTSTRAP_ON_STARTUP` | `true` | Refresca desde scraper al arrancar |
| `ONPE_BOOTSTRAP_INCLUDE_VOTES` | `true` | Incluye votos en el snapshot |
| `ONPE_ATU_MANERA_BOOTSTRAP` | `false` | Fuerza descarga CSV ATuManera al inicio |
| `ONPE_ATU_MANERA_CSV_PATH` | _(opcional)_ | Ruta local al CSV ATuManera (evita descarga) |

### Segunda vuelta 2026 (scraper `onpe-scraper-2026-2`)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ONPE_SV_SCRAPER_ROOT` | `../onpe-scraper-2026-2` | Ruta al repo del scraper de 2V 2026 |
| `ONPE_SV_OUTPUT_DIR` | `$ONPE_SV_SCRAPER_ROOT/output` | Mesas, votos, ubicaciones, reasignados 2V 2026 |
| `ONPE_SV_RESUMEN_DIR` | `$ONPE_SV_SCRAPER_ROOT/resumen` | Agregados pre-computados nacional/depto/provincia 2V 2026 |

### Dataset histórico 2021 (`peruvoto2021`)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ONPE_VOTO2021_ROOT` | `../peruvoto2021` | Ruta al repo con CSV oficiales 2021 (1V+2V) |

### Auto-hidratación y catálogos

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ONPE_AUTO_HYDRATE_ON_DEMAND` | `false` | Hidrata mesas faltantes bajo demanda (requiere desactivar local-only) |
| `ONPE_AUTO_HYDRATE_MAX_MESAS` | `20` | Máximo de mesas a hidratar bajo demanda por consulta |
| `ONPE_AUTO_SYNC_FOREIGN_CATALOG_ON_DEMAND` | `false` | Sincroniza catálogo extranjero bajo demanda (requiere desactivar local-only) |
| `ONPE_LOCAL_ONLY` | `true` | Modo estricto local-only: deshabilita lecturas live de ONPE y sync live |

---

## 🏛️ Garantías enterprise

- **Cobertura temporal completa**: 2026 (1V+2V) + 2021 (1V+2V histórico) — comparativas de ciclos electorales.
- **Trazabilidad completa**: cada tool call se registra en `data/raw/events.jsonl` (append-only).
- **Tests automatizados**: 410+ tests, suite ejecutable en ~30 s. CI-ready (matriz Python 3.11/3.12).
- **Aislamiento de origen**: cada tabla en SQLite tiene timestamp `fetched_at` y origen (`source`, `fuente`).
- **Operaciones idempotentes**: todos los `bootstrap_*` y `refresh` usan UPSERT — re-ejecutar es seguro.
- **Sin datos en el repo**: `data/`, `*.db`, `*.db-wal`, `*.db-shm` están en `.gitignore`. Todo se regenera desde scrapers oficiales + dataset 2021.
- **Manejo de errores tipado**: `VALIDATION_ERROR`, `GATEWAY_ERROR`, `API_ERROR` con `error_response()` consistente.
- **Cache-first explícito**: cada respuesta indica el tier de origen (`tier_1_local_cache`, `tier_3_knowledge_base`).
- **Verificación factual**: el compendio cualitativo (535 hechos) NO inventa cifras; cuando no hay datos cuantitativos derivables, responde con contexto institucional verificable o redirige a fuente oficial.
- **Soporte multi-año**: router automático en `onpe_chat` detecta año (2021/2026) y delega a handler correspondiente.
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
pytest                                  # corre 410+ tests (2026 + 2021)
pytest tests/test_storage_2021.py -v   # solo tests de storage 2021
pytest tests/test_nl_100_year_cases.py -v  # tests de año/routing automático
pytest tests/test_onpe_chat.py -v      # tests de routeo principal
pytest -k "proyeccion_sv"              # solo tests de mapeo transferencia 2026
onpe-mcp                                # arranca servidor MCP (stdio)
```

---

## 📐 Contratos y schemas

- Especificación técnica API ONPE: [`docs/onpe-api-contract.md`](docs/onpe-api-contract.md)
- JSON schema response: [`schemas/onpe.actas.buscar.mesa.response.schema.json`](schemas/onpe.actas.buscar.mesa.response.schema.json)
- JSON schema acta mínima: [`schemas/onpe.acta.min.schema.json`](schemas/onpe.acta.min.schema.json)

---

## 📄 Licencia y atribución

- **2026**: Datos oficiales de la **Oficina Nacional de Procesos Electorales (ONPE), Perú** — disponibles en <https://resultadoelectoral.onpe.gob.pe>
- **2021**: Dataset histórico del repo [`peruvoto2021`](https://github.com/oscarzamora/peruvoto2021) — datos oficiales ONPE.

Este proyecto es una herramienta de consulta y análisis, sin afiliación oficial con ONPE ni JNE.
