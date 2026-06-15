# Matriz de pruebas MCP (README + permutaciones multi-input)

Este documento centraliza la batería de pruebas MCP para validar que las preguntas del README y sus permutaciones funcionen contra el servidor.

## Objetivo

1. Validar cobertura funcional de preguntas del README.
2. Validar rutas 2026 sobre base local denorm.
3. Validar escenarios multi-input (múltiples mesas, geos y países).

## Suites de prueba

| Suite | Propósito |
|---|---|
| `tests/test_mcp_smoke_queries.py` | Smoke real de preguntas representativas 2026/2021. |
| `tests/test_enterprise_qa.py` | Cobertura amplia (tool contracts, geo, 2V, comparaciones, performance). |
| `tests/test_readme_mcp_permutations.py` | Matriz README 2026 + permutaciones multi-input. |

## Casos README (2026)

Se validan consultas como:

1. Mesa específica (`mesa 900100`).
2. Candidato nacional (Keiko 2026).
3. Resultados SV por departamento (Lima).
4. Ranking 1V por departamento (Puno).
5. Cobertura SV.
6. Reasignados.
7. Proyección/transferencia en prefijos de mesa (900K).
8. Exterior (ej. Suecia).

## Permutaciones multi-input (MCP)

### 1. Múltiples mesas

- Tool: `onpe_get_mesas_batch`
- Ejemplo: `["900100", "900101", "900102"]`
- Validación: total solicitado, items y shape por item.

### 2. Múltiples geografías (departamentos)

- Tool: `onpe_resultados_geo`
- Inputs: `LIMA`, `AREQUIPA`, `CUSCO`
- Validación: respuesta `ok`, lista de resultados por cada geo.

### 3. Múltiples países (exterior)

- Tool: `onpe_sv_resultados_geo`
- Nivel: `pais_exterior`
- Inputs: `ARGENTINA`, `CHILE`, `ESPAÑA`
- Validación: respuesta `ok`, lista de resultados por país.

### 4. Predicados analíticos (denorm)

- Tool: `onpe_filter_mesas`
- Ejemplo: `election_year=2026, vuelta=2, partido="8", votos_op="eq", votos_value=0`
- Validación:
  - `ok=true`
  - contrato enumerable completo: `rows,total,returned,offset,limit,has_more`
  - `query_echo` y `sql_explain` presentes
  - `data_tier = tier_1_denorm`

### 5. Query estructurado (fase inicial)

- Tool: `onpe_query`
- Ejemplo mínimo:
  - `dataset=mesa`, `select=[codigo_mesa,partido_id,votos]`
  - `where=[{field:partido_id,op:eq,value:8},{field:votos,op:eq,value:0}]`
- Validación:
  - devuelve filas correctas y paginación explícita
  - rechaza features fuera de fase (`group_by`, `having`, `compare`) con `VALIDATION_ERROR`
  - no acepta columnas fuera de whitelist

## Ejecución

```bash
python -m pytest tests/test_mcp_smoke_queries.py -q --tb=short
python -m pytest tests/test_enterprise_qa.py -q --tb=short
python -m pytest tests/test_readme_mcp_permutations.py -q --tb=short
python -m pytest tests/test_analytics_engine.py -q --tb=short
```

## Criterios de aceptación

1. Todas las suites MCP en verde.
2. Sin rutas de error para las preguntas README 2026.
3. Multi-input resuelto por herramientas MCP (batch/geo/pais) con shape consistente.
4. Predicados analíticos responden desde denorm con contrato paginado auditable.
