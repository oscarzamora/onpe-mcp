# Plan: Motor Analítico de Consultas tipo-SQL para `onpe-mcp`

> **Objetivo:** Dotar al MCP de la capacidad de responder consultas analíticas arbitrarias sobre votos —
> sumas, restas, agregados, rangos, similitudes, comparaciones entre candidatos / ciudades / años —
> **sin** que un agente tenga que bajar a SQL crudo ni arriesgar alucinaciones.
>
> **Origen:** brechas detectadas en sesión de trabajo (jun-2026) al intentar responder
> *"dame todas las mesas con 0 votos de Fuerza Popular en 2V"*, que ninguna tool ni intent del MCP
> podía resolver.
>
> **Audiencia:** mantenedores del MCP, futuros agentes que consuman las tools.
> **Estado:** implementación incremental en curso (**Fase 0 parcial implementada**).

---

## Tabla de contenidos

1. [Diagnóstico: qué falta hoy](#1-diagnóstico-qué-falta-hoy)
2. [Principios de diseño (mejores prácticas)](#2-principios-de-diseño-mejores-prácticas)
3. [Arquitectura propuesta](#3-arquitectura-propuesta)
4. [Capacidades del motor analítico](#4-capacidades-del-motor-analítico)
5. [Catálogo de nuevas tools](#5-catálogo-de-nuevas-tools)
6. [Contrato de respuesta y señalización de gaps](#6-contrato-de-respuesta-y-señalización-de-gaps)
7. [Seguridad: SQL controlado, no SQL arbitrario](#7-seguridad-sql-controlado-no-sql-arbitrario)
8. [Permutaciones de consulta soportadas (matriz)](#8-permutaciones-de-consulta-soportadas-matriz)
9. [Plan de implementación por fases](#9-plan-de-implementación-por-fases)
10. [Estrategia de pruebas](#10-estrategia-de-pruebas)
11. [Bugs y deuda técnica a resolver en paralelo](#11-bugs-y-deuda-técnica-a-resolver-en-paralelo)
12. [Riesgos y mitigaciones](#12-riesgos-y-mitigaciones)

---

## 1. Diagnóstico: qué falta hoy

Lo observado en esta sesión, ordenado por impacto:

| # | Brecha | Síntoma concreto | Clase |
|---|---|---|---|
| G1 | **Sin filtro por cantidad de votos** | No se puede pedir "mesas con `votos == 0`" / "`< 5`" / "`BETWEEN`". `onpe_sv_export_votos` solo filtra por geo/partido/estado. | Filtro de predicado |
| G2 | **Sin búsqueda inversa (mesas que cumplen condición)** | Las tools *agregan* (suman/rankean) pero no *enumeran mesas que satisfacen un predicado de voto*. | Modelo de consulta |
| G3 | **Sin aritmética entre series** | No hay "votos A − votos B", "A + B + C", "% de A sobre (A+B)", "margen A vs B por mesa". | Operaciones derivadas |
| G4 | **Sin comparación cross-entidad genérica** | Comparar candidato vs candidato, ciudad vs ciudad, año vs año fuera de tools puntuales (`*_cross_year`, `*_comparacion_mesa`). | Comparación |
| G5 | **Sin similitud / distancia** | No se puede "ciudades con perfil de voto similar a X", "mesas atípicas (outliers)", correlaciones. | Analítica avanzada |
| G6 | **`onpe_chat` no señaliza incapacidad** | Devuelve `ok:True` + `intent:"unknown"` → un agente puede confundir "no puedo" con "no hay datos" o **alucinar**. | Contrato/seguridad |
| G7 | **Datos parciales silenciosos** | Filtrar 92k filas con `limit=5000` puede entregar resultados incompletos si el consumidor ignora `has_more`. | Contrato |
| G8 | **Bug real** | `onpe_claim_verifier` y `onpe_margen_pase` fallan con `KeyError: 'electores_habiles'`. | Bug |

> **Insight central:** el problema no es *"falta una tool"* sino *"falta una clase de capacidad"* (analítica
> por predicado + aritmética + comparación) **y** *"falta honestidad estructurada"* cuando el MCP no puede
> responder.

---

## 2. Principios de diseño (mejores prácticas)

Estos principios gobiernan todo el plan:

1. **Capability gaps explícitos, no silenciosos.** Una respuesta "exitosa" que no responde la pregunta es
   peor que un error honesto. Toda respuesta debe permitir al agente distinguir, de forma estructurada,
   entre *respondí* / *fallé* / *no puedo responder esto*.
2. **Paginación siempre explícita.** `total`, `returned`, `offset`, `has_more` obligatorios en cualquier
   salida enumerable. Nunca entregar un subconjunto como si fuera el universo.
3. **SQL controlado, no SQL arbitrario.** El agente compone consultas mediante un **DSL/JSON estructurado y
   validado**, no enviando strings SQL crudos (evita inyección y consultas catastróficas).
4. **Determinismo y reproducibilidad.** Cache-first sobre `onpe_denorm.db`. La misma consulta da el mismo
   resultado entre llamadas.
5. **Descriptions como contrato.** Cada tool declara qué **sí** y qué **no** hace, y a qué tool delegar si
   la pregunta cae fuera.
6. **Composición sobre proliferación.** Un motor parametrizable cubre una *clase* de preguntas; evita crear
   una tool nueva por cada pregunta futura.
7. **Cero cifras inventadas.** Si no hay datos suficientes, se dice; nunca se rellena con estimaciones no
   etiquetadas como tales.
8. **Reutilizar el star schema existente.** `fact_votos_mesa` (grano mesa×partido, con `mesa_num`
   generado), `fact_votos_ubigeo/provincia/departamento/nacional`, `dim_partido`, `dim_geo` ya están
   denormalizados → son el sustrato ideal; no reconstruir.

---

## 3. Arquitectura propuesta

```
┌─────────────────────────────────────────────────────────────────────┐
│ Capa 1 — Tools MCP (interfaz pública, @mcp.tool)                     │
│   onpe_query · onpe_compare · onpe_filter_mesas · onpe_similarity    │
│   (+ onpe_chat enruta a estas cuando detecta intención analítica)    │
└───────────────┬─────────────────────────────────────────────────────┘
                │  (request validado como JSON/DSL, NO SQL crudo)
┌───────────────▼─────────────────────────────────────────────────────┐
│ Capa 2 — AnalyticsEngine (nuevo módulo: analytics.py)                │
│   • QuerySpec  (dataclass validada: select/where/group/having/order) │
│   • SQLCompiler (QuerySpec → SQL parametrizado seguro)               │
│   • Operadores derivados (suma/resta/ratio/margen/similitud)         │
│   • Guardarraíles (límites de filas, timeouts, whitelist de columnas)│
└───────────────┬─────────────────────────────────────────────────────┘
                │  (SQL parametrizado + binds)
┌───────────────▼─────────────────────────────────────────────────────┐
│ Capa 3 — DataStore (storage.py, ya existe)                          │
│   _connect_denorm() → onpe_denorm.db (star schema read-only)        │
└─────────────────────────────────────────────────────────────────────┘
```

**Módulo nuevo:** `src/onpe_mcp/analytics.py`. Aísla la lógica de compilación y validación del DSL, de modo
que `server.py` solo exponga tools delgadas que delegan al engine (igual que hoy delega en `store`).

---

## 4. Capacidades del motor analítico

El `AnalyticsEngine` debe soportar, sobre cualquier nivel de grano (mesa / ubigeo / provincia / departamento
/ nacional) y cualquier `(election_year, vuelta)`:

### 4.1 Selección y filtrado por predicado (cubre G1, G2)
- Filtros por dimensión: año, vuelta, partido(s)/candidato(s), departamento/provincia/distrito/ubigeo,
  país/ciudad (extranjero), estado de acta, rango de `mesa_num`/prefijo de mesa.
- **Filtros por métrica de voto:** operadores `eq, ne, lt, lte, gt, gte, between, in` sobre `votos`,
  `votos_validos`, `electores_habiles`, `participacion`, `pct_validos`.
  → resuelve *"mesas con 0 votos de FP"* como `where votos eq 0 and partido = FP`.

### 4.2 Agregaciones (cubre G3 parcialmente)
- `sum, count, avg, min, max, count_distinct` sobre métricas.
- `group_by` por cualquier dimensión o lista de dimensiones.
- `having` (filtro post-agregación): *"departamentos donde Σ FP < 1000"*.

### 4.3 Aritmética entre series / operaciones derivadas (cubre G3, G4)
Expresiones calculadas a nivel de fila o de grupo, entre dos o más partidos/candidatos:
- **Resta / margen:** `votos(A) − votos(B)` → margen por mesa/distrito.
- **Suma de bloques:** `votos(A) + votos(B) + votos(C)` (ej. coaliciones, "izquierda total").
- **Ratio / cuota:** `votos(A) / (votos(A)+votos(B))` → % bipartidista.
- **Delta cross-year / cross-vuelta:** `votos_2026 − votos_2021` para la misma entidad geográfica.
- **Swing:** variación porcentual de un candidato entre dos elecciones.

### 4.4 Rangos y umbrales (cubre G1)
- `BETWEEN` sobre votos, %, participación, tamaño de padrón.
- Buckets/binning: *"mesas agrupadas por rango de participación (0-50, 50-70, 70-100)"*.

### 4.5 Similitud y detección de atípicos (cubre G5)
- **Perfil de voto** por entidad = vector de % por candidato.
- **Similitud:** distancia coseno / euclidiana entre perfiles → *"ciudades similares a Puno"*,
  *"mesas con perfil más parecido a la mesa X"*.
- **Outliers:** z-score sobre una métrica dentro de un grupo → *"mesas atípicas en Lima"*.
- **Correlación:** Pearson entre dos series (ej. participación vs % de un candidato).

### 4.6 Ordenamiento y top-N
- `order_by` multi-columna (incl. columnas derivadas), `asc/desc`, `limit/offset`.

---

## 5. Catálogo de nuevas tools

Cuatro tools nuevas, todas delgadas sobre `AnalyticsEngine`. Diseño deliberadamente **pequeño y
componible** (principio 6).

### 5.1 `onpe_query` — motor de consulta estructurada (núcleo)
Acepta un `QuerySpec` validado (JSON), no SQL. Cubre selección, filtro por predicado, agregación,
`group_by`, `having`, `order_by`, paginación.

> **Implementado en esta iteración:** selección + `where` + `order_by` + paginación.
> `group_by`, `having` y `compare` devuelven validación explícita de feature no soportada.

```jsonc
// "mesas 2V-2026 con 0 votos de Fuerza Popular y escrutinio real"
{
  "dataset": "mesa",            // mesa | ubigeo | provincia | departamento | nacional
  "election_year": 2026, "vuelta": 2,
  "select": ["codigo_mesa", "departamento", "provincia", "distrito",
             "votos", "votos_validos"],
  "where": [
    {"field": "partido_id", "op": "eq", "value": "8"},
    {"field": "votos", "op": "eq", "value": 0},
    {"field": "votos_validos", "op": "gt", "value": 0}
  ],
  "order_by": [{"field": "votos_validos", "dir": "desc"}],
  "limit": 500
}
```

### 5.2 `onpe_compare` — comparación / aritmética entre entidades
Comparar N candidatos, N geografías o N (año,vuelta) y derivar suma/resta/ratio/margen.

```jsonc
// "margen Sánchez − Keiko por departamento en 2V-2026"
{
  "dataset": "departamento",
  "election_year": 2026, "vuelta": 2,
  "compare": {
    "dimension": "candidato",
    "left":  {"partido_id": "10"},   // Sánchez
    "right": {"partido_id": "8"},    // Keiko
    "metric": "votos",
    "operation": "diff"              // diff | sum | ratio | margin_pct
  },
  "order_by": [{"field": "value", "dir": "desc"}]
}
```

### 5.3 `onpe_filter_mesas` — atajo de búsqueda inversa (azúcar sobre `onpe_query`)
API amigable para el caso más común (G1/G2) sin construir el spec completo. Pensada para que `onpe_chat`
la invoque fácilmente.

```
onpe_filter_mesas(election_year=2026, vuelta=2, partido="fuerza popular",
                  votos_op="eq", votos_value=0, solo_escrutadas=True)
```

> **Implementado en esta iteración:** sí (incluye resolución por nombre/`partido_id`,
> filtro por prefijo de mesa y paginación explícita).

### 5.4 `onpe_similarity` — similitud / outliers / correlación
```
onpe_similarity(mode="similar_geo", target="Puno", level="departamento",
                election_year=2026, vuelta=2, top_n=5)
onpe_similarity(mode="outliers", level="mesa", departamento="Lima", metric="pct_sanchez")
onpe_similarity(mode="correlation", x="participacion", y="pct_keiko", level="provincia")
```

> `onpe_chat` se extiende para detectar intención analítica (palabras como "diferencia", "suma", "margen",
> "parecidas", "atípicas", "con 0", "más de N votos") y enrutar a la tool correcta — o, si no puede, emitir
> la señal de gap (§6).

---

## 6. Contrato de respuesta y señalización de gaps

### 6.1 Forma estándar (se mantiene `ok_response`/`error_response`)
Toda salida enumerable incluye **paginación explícita** (principio 2):

```jsonc
{
  "ok": true,
  "data": {
    "rows": [ ... ],
    "total": 41, "returned": 41, "offset": 0, "limit": 500, "has_more": false,
    "query_echo": { ...QuerySpec normalizado... },   // reproducibilidad
    "sql_explain": "SELECT ... WHERE ...",            // transparencia (solo lectura)
    "data_tier": "tier_1_denorm"
  },
  "errors": [],
  "meta": { "duration_ms": 12, "source": "sqlite_denorm" }
}
```

### 6.2 Señal de "capability gap" (cubre G6 — clave anti-alucinación)
Cuando `onpe_chat` (o una tool) **no puede** responder, NO devuelve un `ok:True` ambiguo. Devuelve una
estructura que el agente puede leer programáticamente:

```jsonc
{
  "ok": true,
  "data": {
    "answerable": false,
    "intent": "capability_gap",
    "reason_code": "no_tool_for_request",
    "human_reason": "No existe una operación para 'similitud de mesas' en este momento.",
    "suggested_tool": "onpe_similarity",
    "suggested_args_hint": { "mode": "similar_geo", "target": "..." },
    "did_you_mean": ["onpe_query", "onpe_compare"]
  }
}
```

Regla para agentes (documentar en la `description` y en `copilot-instructions.md`):
> Si `answerable == false`, **no inventes la respuesta**. Usa `suggested_tool` o informa al usuario que la
> consulta no está soportada.

---

## 7. Seguridad: SQL controlado, no SQL arbitrario

Mejor práctica crítica (OWASP A03 — Injection):

- **NO** exponer una tool que reciba SQL crudo del agente/usuario. El riesgo de inyección y de consultas
  catastróficas (cross joins, full scans, escrituras) es inaceptable.
- El agente compone un **`QuerySpec` (JSON)**; el `SQLCompiler` lo traduce a SQL **parametrizado** con
  *binds*, validando contra:
  - **Whitelist de columnas y tablas** (derivada de los `CREATE TABLE` del star schema).
  - **Whitelist de operadores** (`eq, ne, lt, lte, gt, gte, between, in`) y de funciones de agregación.
  - **Conexión read-only** (`mode=ro` en el URI SQLite) → imposibilita `INSERT/UPDATE/DELETE/ATTACH`.
- **Guardarraíles de recursos:**
  - `LIMIT` máximo forzado (p. ej. 50 000 filas) y `limit` por defecto conservador.
  - `sqlite3` `set_progress_handler` / timeout para abortar consultas largas.
  - Rechazo de `group_by` sin límite sobre el grano mesa (6.5 M filas) sin filtro previo.
- **Auditoría:** cada consulta se registra en `data/raw/events.jsonl` con el `QuerySpec` y el SQL compilado
  (ya existe `append_raw_event`).

---

## 8. Permutaciones de consulta soportadas (matriz)

Ejemplos que el motor debe poder responder tras la implementación (todas vistas o implícitas en esta
sesión):

| Pregunta en lenguaje natural | Tool | Operación |
|---|---|---|
| Mesas con 0 votos de Fuerza Popular (2V) | `onpe_filter_mesas` | `where votos eq 0` |
| Mesas donde Sánchez sacó 100% de válidos | `onpe_query` | `having votos = votos_validos` |
| Mesas donde el margen K−S es < 5 votos | `onpe_compare` | `diff` + `where between -5 5` |
| Departamentos donde Σ Keiko bajó vs 2021 | `onpe_compare` | `delta cross-year` |
| % bipartidista de Keiko por provincia | `onpe_compare` | `ratio A/(A+B)` |
| Suma "izquierda total" (A+B+C) por distrito | `onpe_query` | `sum` multi-partido |
| Ciudades del exterior similares a Puno | `onpe_similarity` | distancia de perfil |
| Mesas atípicas (outliers) en Lima | `onpe_similarity` | z-score |
| Correlación participación vs % Keiko | `onpe_similarity` | Pearson |
| Mesas con padrón entre 50 y 100 electores | `onpe_query` | `between` |
| Top 20 mesas por margen a favor de Sánchez | `onpe_compare` | `diff` + `order desc` |
| Mesas 900K con participación < 50% | `onpe_filter_mesas` | predicado + prefijo |

---

## 9. Plan de implementación por fases

Incremental, cada fase entrega valor y es testeable de forma aislada.

### Fase 0 — Cimientos y arreglos rápidos (1 PR)
- [x] Crear `src/onpe_mcp/analytics.py` con `QuerySpec`, compilación SQL segura (solo `select` + `where`
      + `order_by` + paginación) y whitelist de columnas.
- [x] Conexión read-only al denorm DB (`file:...onpe_denorm.db?mode=ro`).
- [x] Tool `onpe_filter_mesas` (azúcar) → desbloquea la consulta original "0 votos FP".
- [x] Arreglar bug de shape en `get_totales_nacionales_1v` que causaba `KeyError` downstream en
      `onpe_claim_verifier` / `onpe_margen_pase`.

### Fase 1 — Motor de consulta estructurada
- [ ] Tool `onpe_query` completa: `group_by`, agregaciones, `having`, `order_by`, multi-dataset.
- [ ] `query_echo` + `sql_explain` + paginación explícita en la respuesta.
- [ ] Guardarraíles de recursos (límites, timeout, rechazo de full-scan sin filtro).

### Fase 2 — Comparación y aritmética
- [ ] Tool `onpe_compare`: `diff`, `sum`, `ratio`, `margin_pct`, deltas cross-year/cross-vuelta.
- [ ] Reusar `fact_votos_*` por nivel para mantener performance.

### Fase 3 — Similitud y atípicos
- [ ] Tool `onpe_similarity`: `similar_geo`, `outliers`, `correlation`.
- [ ] Cálculo en Python sobre vectores ya agregados (no en SQL) para mantener el compiler simple.

### Fase 4 — Integración conversacional y señal de gap
- [ ] Extender `onpe_chat`: detección de intención analítica → enrutamiento a las tools nuevas.
- [ ] Reemplazar el `intent:"unknown"` genérico por la **señal `capability_gap`** estructurada (§6.2).
- [ ] Documentar la regla anti-alucinación en `description`s y `.github/copilot-instructions.md`.

### Fase 5 — Documentación y endurecimiento
- [ ] README: sección "Consultas analíticas" con ejemplos de los 4 tools.
- [ ] `docs/mcp-test-matrix.md`: añadir las permutaciones de §8.
- [ ] Memoria de repo: registrar el DSL y los gotchas.

---

## 10. Estrategia de pruebas

- **Unit (compiler):** `QuerySpec` → SQL esperado (parametrizado); casos de whitelist rechazada,
  operadores inválidos, columnas no permitidas.
- **Seguridad:** intentos de inyección (`value: "0; DROP TABLE"`), escritura bloqueada por `mode=ro`,
  límites de filas/timeout respetados.
- **Correctitud de datos:** cada permutación de §8 comparada contra una query SQL de referencia
  (golden) calculada directamente sobre `onpe_denorm.db` → garantiza que el engine y SQL crudo coinciden.
- **Regresión del caso semilla:** test explícito *"0 votos FP 2V = 88 mesas (41 con escrutinio real)"*
  comparado contra snapshot actual (sin hardcodear cifras fijas que cambian por rehidratación).
- **Contrato:** toda salida enumerable expone `total/returned/offset/has_more`; `capability_gap` se
  dispara cuando corresponde (`answerable:false`).
- **Convención del repo:** sin red externa (monkeypatch HTTP), `pytest -q`, fixtures sobre DB de prueba.

---

## 11. Bugs y deuda técnica a resolver en paralelo

| Item | Acción | Prioridad |
|---|---|---|
| `KeyError: 'electores_habiles'` en `claim_verifier` / `margen_pase` | Localizar el acceso a clave faltante; usar `.get()` o coerción tolerante. Añadir test de regresión. | Alta (Fase 0) |
| `onpe_chat` devuelve `intent:"unknown"` ambiguo | Sustituir por señal `capability_gap` estructurada. | Alta (Fase 4) |
| `limit=5000` puede ocultar parcialidad | Asegurar `has_more`/`total` en TODAS las tools de export y que `onpe_chat` los propague. | Media |
| Drift de snapshot entre rehidrataciones | Evitar asserts con cifras absolutas fijas; validar consistencia relativa y shape de respuesta. | Media |

---

## 12. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| **Inyección SQL / consultas destructivas** | DSL validado + binds + conexión `mode=ro` + whitelist. Nunca SQL crudo del agente. |
| **Full scans sobre 6.5 M filas (mesa)** | Forzar filtro o `LIMIT`; preferir `fact_votos_ubigeo/...` cuando el grano lo permita; índices sobre `mesa_num`, `partido_id`, `cod_departamento`. |
| **Explosión de complejidad del DSL** | Mantener 4 tools pequeñas y componibles; no perseguir paridad total con SQL. Documentar qué NO soporta. |
| **Agente alucina ante un gap** | Señal `answerable:false` + regla explícita en instrucciones + `did_you_mean`. |
| **Cifras derivadas mal interpretadas** | `query_echo` + `sql_explain` para que el resultado sea auditable; etiquetar siempre proyecciones/estimaciones. |
| **Divergencia engine vs SQL** | Tests golden contra SQL de referencia en cada permutación. |

---

### Resumen ejecutivo

Hoy el MCP *agrega* bien pero no *filtra por predicado*, no *hace aritmética entre series*, no *mide
similitud*, y —lo más peligroso— **no avisa con claridad cuando no puede responder**. Este plan introduce un
`AnalyticsEngine` con un DSL JSON seguro y cuatro tools componibles (`onpe_query`, `onpe_compare`,
`onpe_filter_mesas`, `onpe_similarity`) sobre el star schema ya existente, más una **señal estructurada de
capability gap** que elimina el riesgo de alucinación. Se implementa en fases, empezando por desbloquear el
caso semilla ("0 votos FP") y arreglar el bug de `claim_verifier`.
