# ONPE MCP

Servidor [MCP](https://modelcontextprotocol.io/) para consultas electorales sobre **Perú 2026 — primera vuelta presidencial**. Expone las 92,766 mesas de sufragio con estrategia **cache-first**: SQLite local → API ONPE live → compendio cualitativo verificable.

> **Velocidad**: todas las consultas sobre datos locales resuelven en **<100 ms**. Las consultas que requieren la API ONPE en vivo dependen de la red (~1-8 s).

---

## ⚡ Instalación desde cero

```bash
# 1. Clonar e instalar
git clone https://github.com/oscarzamora/onpe-mcp
cd onpe-mcp
pip install -e .

# 2. (Opcional pero recomendado) clonar la fuente de datos más actualizada
git clone https://github.com/oscarzamora/onpeescraper ../onpescraper

# 3. Arrancar el servidor MCP
onpe-mcp
```

**La base de datos (`data/onpe.db`) no se distribuye en el repositorio** — se genera localmente en el primer arranque.

---

## 🗄️ Hidratación de la base de datos

Al arrancar con la base vacía, el servidor inicia **hidratación automática**:

```
WARNING  DB vacía al arrancar — hidratación MANDATORIA.
         Descargando ATuManera CSV (~92,766 mesas, 1-3 min según red).
INFO     Hidratación cold-start completada: 92766 mesas cargadas.
```

### Rutas de hidratación (en orden de prioridad)

| # | Fuente | Cuándo se usa | Tiempo aprox. |
|---|--------|---------------|---------------|
| 1 | **onpescraper local** (`../onpescraper/output/`) | Si el repo hermano está clonado | 30-60 s |
| 2 | **ATuManera CSV** (descarga pública desde GitHub) | Fallback automático | 1-3 min |
| 3 | **Modo degradado** (solo API ONPE live) | Si ambas fallan | inmediato |

### Verificar estado de la DB

```
onpe_health()
```

**DB vacía (arranque en frío):**
```json
{
  "status": "not_hydrated",
  "hydrated": false,
  "total_mesas_local": 0,
  "next_step": "Llama a onpe_bootstrap_atu_manera() para descargar las 92,766 mesas."
}
```

**DB hidratada y lista:**
```json
{
  "status": "ok",
  "hydrated": true,
  "total_mesas_local": 92766,
  "total_votos_local": 3801438,
  "coverage_pct": 99.9,
  "next_step": null
}
```

### Hidratación manual desde el agente

Si la hidratación automática no se completó, llamar directamente:

```
# Fuente más actualizada — requiere repo onpescraper en ../onpescraper
onpe_bootstrap_snapshot()

# Descarga el CSV público desde GitHub (~100 MB)
onpe_bootstrap_atu_manera()
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

| Tool | Descripción |
|------|-------------|
| `onpe_chat` | **Interfaz principal** — lenguaje natural, cache-first, intención automática |
| `onpe_get_mesa` | Consulta una mesa por código (cache → live API) |
| `onpe_get_mesas_batch` | Hasta 200 mesas en paralelo (siempre live) |
| `onpe_health` | Estado del servidor, DB y cobertura de hidratación |
| `onpe_bootstrap_snapshot` | Carga snapshot de onpescraper → SQLite |
| `onpe_bootstrap_atu_manera` | Descarga CSV público → SQLite (~2-5 min) |
| `onpe_sync_foreign_catalog` | Sincroniza catálogo de países/ciudades para el exterior |

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

## ⚙️ Configuración

Copia `.env.example` a `.env` para ajustar valores:

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ONPE_SCRAPER_ROOT` | `../onpescraper` | Ruta al repo onpescraper |
| `ONPE_SCRAPER_REPO_URL` | `https://github.com/oscarzamora/onpeescraper` | URL a clonar si no existe |
| `ONPE_DATA_DIR` | `./data` | Directorio de la base SQLite y eventos |
| `ONPE_BOOTSTRAP_ON_STARTUP` | `true` | Refresca desde onpescraper al arrancar (si ya hay datos) |
| `ONPE_BOOTSTRAP_INCLUDE_VOTES` | `true` | Incluye votos en el snapshot |
| `ONPE_ATU_MANERA_BOOTSTRAP` | `false` | Fuerza descarga ATuManera al inicio |
| `ONPE_MAX_BATCH_SIZE` | `200` | Límite de lote en `onpe_get_mesas_batch` |
| `ONPE_CACHE_TTL_SECONDS` | `900` | TTL del cache individual de mesa (segundos) |
| `ONPE_AUTO_SYNC_FOREIGN_CATALOG_ON_DEMAND` | `true` | Sincroniza catálogo extranjero si no hay datos |

## Requisitos

- Python 3.11+
- Git (para clonar onpescraper — opcional si usas `onpe_bootstrap_atu_manera`)

---

## 📐 Contrato ONPE

- Especificación técnica: `docs/onpe-api-contract.md`
- JSON schema response: `schemas/onpe.actas.buscar.mesa.response.schema.json`
- JSON schema acta mínima: `schemas/onpe.acta.min.schema.json`

