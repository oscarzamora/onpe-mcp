# Plan consolidado: toolset analítico controlado (`db_query`)

## Estado consolidado (implementado)

Se extendió el toolset MCP con tres tools orientadas a consumo analítico controlado:

1. `db_query(query_spec, preset?)`
2. `db_search(query, field, election_year, vuelta, limit)`
3. `db_batch_execute(requests, stop_on_error)`

Objetivo práctico: que agentes/consumidores usen una puerta analítica MCP read-only, en lugar de depender de SQL ad hoc o tablas físicas.

---

## Contrato vigente

### `db_query`

- Ejecuta consultas estructuradas (no SQL string libre).
- Reutiliza validaciones de dataset/columnas/operadores.
- Soporta `preset` versionado (actualmente:
  - `900k_segunda_vuelta_resumen`
  - `audit_estado_E_vs_C`).
- Devuelve metadatos de trazabilidad por ejecución:
  - `query_id`
  - `schema_version`
  - `snapshot_id`
  - `normalized_request_hash`
  - `rowcount`
  - `audit_logged`

### `db_search`

- Descubre entidades canónicas para alimentar `db_query`.
- Tipos soportados: `departamento`, `provincia`, `distrito`, `pais`, `ciudad`, `partido`, `candidato`.
- Modo `field="any"` para búsqueda amplia.

### `db_batch_execute`

- Ejecuta batches de requests `db_query` en modo read-only.
- Límite de seguridad: máximo 50 requests por llamada.
- Soporta `stop_on_error` para control operacional.

---

## Seguridad y gobernanza aplicada

1. **Read-only**: sin rutas de escritura en estas tools.
2. **Esquema público controlado**: columnas permitidas por dataset en `analytics.py`.
3. **Preset registrado**: catálogo interno versionable.
4. **Auditoría por evento**: cada ejecución se registra con `append_raw_event`.

---

## Reproducibilidad

La misma request canónica sobre el mismo snapshot local produce el mismo resultado.

`db_query` ya expone:

- hash canónico (`normalized_request_hash`)
- identificador de snapshot (`snapshot_id`)
- versión de contrato (`schema_version`)

Esto permite replay y comparación entre ejecuciones.

---

## Relación con tools existentes

- `onpe_query` y `onpe_filter_mesas` se mantienen por compatibilidad.
- `db_query` es la puerta recomendada para nuevos flujos analíticos.
- `db_search` se usa para resolver entidades antes de consultar.
- `db_batch_execute` queda para orquestación controlada de múltiples consultas.

---

## Cobertura de pruebas añadida

Se agregó cobertura en `tests/test_analytics_engine.py` para:

1. uso de preset registrado en `db_query`,
2. búsqueda de entidades vía `db_search`.

Además se preserva la cobertura preexistente de validación/paginación/filtros.

---

## Pendientes (siguiente iteración)

1. ampliar catálogo de presets comparativos 2021/2026 y 1V/2V;
2. exponer catálogo de datasets/presets como tool dedicada (`db_catalog`);
3. agregar tests de contrato para campos de `query_meta`;
4. añadir snapshot tests reproducibles para presets críticos.

---

## Nota operativa sobre artefactos locales

Se mantiene la política actual: snapshots SQLite y caches locales fuera de Git.
La base local sigue siendo un artefacto regenerable y no parte del contrato público MCP.
