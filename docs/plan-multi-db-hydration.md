# Plan: hidratación multi-DB para `onpe-mcp`

## Objetivo
Mantener SQLite como opción local por defecto, pero permitir que la misma base de datos lógica pueda hidratarse en:
- MySQL
- SQL Server / Azure SQL
- Snowflake
- Microsoft Fabric Warehouse

El contrato MCP no cambia: solo cambia el backend de persistencia.

## Principios de diseño
1. **Mismo modelo lógico, distintos motores.**
2. **Lectura separada de ingesta.**
3. **Carga idempotente.**
4. **Validación de paridad antes de exponer resultados.**
5. **Fallback explícito, nunca silencioso.**

## Arquitectura propuesta

### Capas
- **Extract**: archivos fuente oficiales.
- **Staging**: tablas temporales o landing.
- **Core**: hechos y dimensiones normalizadas.
- **Serving**: vistas/denorm para consultas MCP.

## Modelo de datos real (extraído de `storage.py`)

A continuación se listan **todas las tablas** con sus columnas reales, cardinalidades de referencia y claves. Esto es lo que se debe replicar en el motor destino. La sintaxis DDL aquí es SQLite-compatible; ver sección "Adaptaciones por motor" para diferencias.

---

### 🗳️ Primera vuelta 2026 (1V)

**`mesas_data`** — 92,766 filas · 1 fila por mesa

| Columna | Tipo | PK | Descripción |
|---|---|---|---|
| `codigo_mesa` | TEXT | ✅ | Código de 6 dígitos, zero-padded (ej. `900100`) |
| `ubigeo` | TEXT | | Ubigeo ONPE 6 dígitos (ej. `150101`) |
| `local_votacion` | TEXT | | Nombre del local de votación |
| `electores_habiles` | INTEGER | | Padrón electoral de la mesa |
| `votos_emitidos` | INTEGER | | Total votos emitidos |
| `votos_validos` | INTEGER | | Total votos válidos |
| `blancos` | INTEGER | | Votos en blanco |
| `nulos` | INTEGER | | Votos nulos |
| `impugnados` | INTEGER | | Votos impugnados |
| `estado_acta` | TEXT | | Estado: `C`=Contabilizada, `E`=En proceso, `P`=Pendiente |
| `fetched_at` | TEXT | | ISO-8601 UTC del último upsert |

Índices: `idx_mesas_ubigeo (ubigeo)`, `idx_mesas_estado (estado_acta)`

---

**`votos`** — ~3.8M filas · 1 fila por (mesa × partido)

| Columna | Tipo | PK | Descripción |
|---|---|---|---|
| `codigo_mesa` | TEXT | ✅ | FK → `mesas_data.codigo_mesa` |
| `partido_id` | TEXT | ✅ | ID del partido (ej. `"1"`, `"38"`) |
| `votos` | INTEGER | | Votos obtenidos |
| `fetched_at` | TEXT | | ISO-8601 UTC |

Índice: `idx_votos_partido (partido_id)`

---

**`agrupaciones`** — 38+ filas · catálogo de partidos 1V

| Columna | Tipo | PK | Descripción |
|---|---|---|---|
| `partido_id` | TEXT | ✅ | ID numérico asignado por ONPE |
| `nombre` | TEXT | | Nombre oficial del partido |
| `candidato` | TEXT | | Nombre del candidato presidencial (hidratado desde `candidato.txt`) |
| `fetched_at` | TEXT | | ISO-8601 UTC |

---

**`votos_by_ubigeo_partido`** — agregado incremental por ubigeo

| Columna | Tipo | PK | Descripción |
|---|---|---|---|
| `ubigeo` | TEXT | ✅ | Ubigeo 6 dígitos |
| `partido_id` | TEXT | ✅ | ID del partido |
| `total_votos` | INTEGER | | Suma de votos en ese ubigeo |
| `fetched_at` | TEXT | | ISO-8601 UTC |

Índice: `idx_votos_ubigeo_partido (ubigeo, partido_id)`

---

**`mesa_prefix_totals`** — totales por prefijo numérico (para queries de segmento)

| Columna | Tipo | PK | Descripción |
|---|---|---|---|
| `prefix` | TEXT | ✅ | Prefijo (ej. `"900"`, `"087"`) |
| `n_mesas` | INTEGER | | Total mesas en el bloque |
| `mesas_con_votos` | INTEGER | | Mesas con al menos 1 voto registrado |
| `votos_emitidos` | INTEGER | | Suma votos emitidos del bloque |
| `votos_validos` | INTEGER | | Suma votos válidos del bloque |
| `rebuilt_at` | TEXT | | ISO-8601 UTC del último rebuild |

---

**`mesa_prefix_party_summary`** — top partidos por prefijo

| Columna | Tipo | PK | Descripción |
|---|---|---|---|
| `prefix` | TEXT | ✅ | Prefijo del bloque |
| `partido_id` | TEXT | ✅ | ID del partido |
| `total_votos` | INTEGER | | Votos totales del partido en el bloque |
| `n_mesas` | INTEGER | | Mesas donde ese partido tiene votos |

Índice: `idx_prefix_party (prefix, total_votos DESC)`

---

**`mesa_winner`** — ganador por mesa (cache de resultado)

| Columna | Tipo | PK | Descripción |
|---|---|---|---|
| `codigo_mesa` | TEXT | ✅ | FK → `mesas_data.codigo_mesa` |
| `partido_id` | TEXT | | Partido ganador |
| `max_votos` | INTEGER | | Votos del ganador |

---

### 🏛️ Catálogo geográfico (compartido 1V y 2V)

**`ubigeo_reniec`** — 1,838 filas · ubigeos domésticos RENIEC

| Columna | Tipo | PK |
|---|---|---|
| `ubigeo` | TEXT | ✅ |
| `distrito` | TEXT | |
| `provincia` | TEXT | |
| `departamento` | TEXT | |
| `distrito_norm` | TEXT | | Acento-normalizado para búsqueda |
| `provincia_norm` | TEXT | |
| `departamento_norm` | TEXT | |
| `fetched_at` | TEXT | |

Índices: `departamento_norm`, `provincia_norm`, `distrito_norm`

---

**`foreign_catalog`** — ubigeos extranjeros

| Columna | Tipo | PK |
|---|---|---|
| `ubigeo` | TEXT | ✅ |
| `continente` | TEXT | |
| `pais` | TEXT | |
| `ciudad` | TEXT | |
| `fetched_at` | TEXT | |

---

**`ubigeo_location_cache`** — resolución rápida ubigeo→geo

| Columna | Tipo | PK |
|---|---|---|
| `ubigeo` | TEXT | ✅ |
| `ambito` | TEXT | |
| `departamento` | TEXT | |
| `ciudad` | TEXT | |
| `pais` | TEXT | |
| `fetched_at` | TEXT | |

---

### 🥈 Segunda vuelta 2026 (2V)

**`mesas_sv`** — 92,766 filas · 1 fila por mesa

| Columna | Tipo | PK | Descripción |
|---|---|---|---|
| `codigo_mesa` | TEXT | ✅ | Código de 6 dígitos |
| `id_ubigeo` | TEXT | | Ubigeo 6 dígitos (universo SV, puede diferir de RENIEC) |
| `nombre_local` | TEXT | | Nombre del local |
| `id_ambito` | INTEGER | | `1`=Perú doméstico, `2`=Exterior |
| `electores_habiles` | INTEGER | | Padrón SV |
| `votos_emitidos` | INTEGER | | |
| `votos_validos` | INTEGER | | |
| `total_asistentes` | INTEGER | | |
| `codigo_estado_acta` | TEXT | | `C`/`E`/`P` |
| `fetched_at` | TEXT | | |

Índices: `idx_mesas_sv_ubigeo (id_ubigeo)`, `idx_mesas_sv_estado (codigo_estado_acta)`

---

**`votos_sv`** — ~463,600 filas · 1 fila por (mesa × partido)

| Columna | Tipo | PK | Descripción |
|---|---|---|---|
| `codigo_mesa` | TEXT | ✅ | FK → `mesas_sv.codigo_mesa` |
| `partido_id` | TEXT | ✅ | `"8"`=Keiko, `"10"`=Sánchez, `"80"`=Blanco, `"81"`=Nulo, `"82"`=Impugnado |
| `votos` | INTEGER | | |
| `fetched_at` | TEXT | | |

---

**`agrupaciones_sv`** — 5 filas · catálogo 2V

| Columna | Tipo | PK |
|---|---|---|
| `partido_id` | TEXT | ✅ |
| `nombre` | TEXT | |
| `fetched_at` | TEXT | |

---

**`ubicaciones_sv`** — 2,102 filas · catálogo geográfico SV

| Columna | Tipo | PK | Descripción |
|---|---|---|---|
| `ubigeo` | TEXT | ✅ | |
| `ambito` | TEXT | | `"peru"` / `"exterior"` |
| `departamento` | TEXT | | |
| `provincia` | TEXT | | |
| `distrito` | TEXT | | |
| `continente` | TEXT | | Solo exterior |
| `pais` | TEXT | | Solo exterior |
| `ciudad` | TEXT | | Solo exterior |
| `fetched_at` | TEXT | | |

---

**`sv_resumen_nacional`** — 4 filas · totales oficiales ONPE (snapshot)

| Columna | Tipo | PK | Descripción |
|---|---|---|---|
| `partido_id` | TEXT | ✅ | |
| `nombre_candidato` | TEXT | | Nombre completo oficial ONPE |
| `nombre_agrupacion` | TEXT | | |
| `votos_validos` | INTEGER | | |
| `pct_votos_validos` | REAL | | |
| `pct_votos_emitidos` | REAL | | |
| `actas_contabilizadas_pct` | REAL | | |
| `contabilizadas` | INTEGER | | Actas Contabilizadas |
| `total_actas` | INTEGER | | Total actas del proceso |
| `participacion_ciudadana` | REAL | | |
| `fecha_actualizacion` | TEXT | | ISO-8601 UTC del snapshot ONPE |
| `fuente` | TEXT | | `"scraper"` / `"api"` |
| `loaded_at` | TEXT | | ISO-8601 UTC del último refresh |

---

**`sv_resumen_departamentos`** — 150 filas · resultados por departamento (25 dptos × 4 candidatos + continentes exterior)

| Columna | Tipo | PK |
|---|---|---|
| `ubigeo` | TEXT | ✅ |
| `partido_id` | TEXT | ✅ |
| `nombre_candidato` | TEXT | |
| `nombre_agrupacion` | TEXT | |
| `votos_validos` | INTEGER | |
| `pct_votos_validos` | REAL | |
| `pct_votos_emitidos` | REAL | |
| `total_votos_validos_geo` | INTEGER | Total válidos del geo |
| `total_votos_emitidos_geo` | INTEGER | |
| `fuente` | TEXT | |
| `loaded_at` | TEXT | |

---

**`sv_resumen_provincias`** — ~1,345 filas · por provincia peruana y por país exterior

| Columna | Tipo | PK | Descripción |
|---|---|---|---|
| `ubigeo` | TEXT | ✅ | Ubigeo de provincia o país exterior (ej. `920100`=Argentina) |
| `partido_id` | TEXT | ✅ | |
| `nombre_candidato` | TEXT | | |
| `nombre_agrupacion` | TEXT | | |
| `nombre_geo` | TEXT | | Nombre de la provincia o país |
| `votos_validos` | INTEGER | | |
| `pct_votos_validos` | REAL | | |
| `pct_votos_emitidos` | REAL | | |
| `total_votos_validos_geo` | INTEGER | | |
| `total_votos_emitidos_geo` | INTEGER | | |
| `fuente` | TEXT | | |
| `loaded_at` | TEXT | | |

---

**`sv_resumen_cobertura`** — 30 filas · cobertura de actas por departamento + continente

| Columna | Tipo | PK |
|---|---|---|
| `ubigeo` | TEXT | ✅ |
| `nombre_departamento` | TEXT | |
| `actas_contabilizadas` | INTEGER | |
| `pct_actas_contabilizadas` | REAL | |
| `fuente` | TEXT | |
| `loaded_at` | TEXT | |

---

**`sv_agg_distrito`** — agregados por distrito (CTAS, calculados localmente)

| Columna | Tipo | PK |
|---|---|---|
| `ubigeo` | TEXT | ✅ |
| `partido_id` | TEXT | ✅ |
| `nombre_candidato` | TEXT | |
| `votos` | INTEGER | |
| `total_mesas` | INTEGER | |
| `mesas_contabilizadas` | INTEGER | |
| `rebuilt_at` | TEXT | |

---

**`sv_agg_ciudad`** — agregados por ciudad (CTAS, calculados localmente)

| Columna | Tipo | PK |
|---|---|---|
| `ubigeo` | TEXT | ✅ |
| `ciudad` | TEXT | ✅ |
| `partido_id` | TEXT | ✅ |
| `nombre_candidato` | TEXT | |
| `votos` | INTEGER | |
| `total_mesas` | INTEGER | |
| `mesas_contabilizadas` | INTEGER | |
| `rebuilt_at` | TEXT | |

---

**`proyeccion_sv_by_ubigeo`** — proyección de transferencia de votos 1V→2V por ubigeo

| Columna | Tipo | PK |
|---|---|---|
| `ubigeo` | TEXT | ✅ |
| `votos_1v_total` | INTEGER | |
| `votos_proyectados_keiko` | INTEGER | |
| `votos_proyectados_sanchez` | INTEGER | |
| `votos_proyectados_bn` | INTEGER | Blanco/nulo esperado |
| `votos_abstencion_estimada` | INTEGER | |
| `rebuilt_at` | TEXT | |

---

**`voto_transfer_map`** — pesos NNLS partido 1V → candidatos 2V (estático, derivado de datos reales)

| Columna | Tipo | PK | Descripción |
|---|---|---|---|
| `partido_nombre_norm` | TEXT | ✅ | Nombre del partido normalizado (sin tildes, minúsculas) |
| `peso_keiko` | REAL | | Fracción → Keiko (calibrado NNLS con 86K mesas) |
| `peso_sanchez` | REAL | | Fracción → Sánchez |
| `peso_bn` | REAL | | Fracción → blanco/nulo |
| `fuente` | TEXT | | `"nnls_calibrado"` / `"editorial"` |
| `loaded_at` | TEXT | | |

---

**`locales_reasignados_sv`** — 44 filas · locales reubicados entre vueltas

| Columna | Tipo | PK |
|---|---|---|
| `nro` | INTEGER | ✅ |
| `odpe` | TEXT | |
| `dpto` | TEXT | |
| `provincia` | TEXT | |
| `distrito` | TEXT | |
| `ccpp` | TEXT | |
| `nombre_local_original` | TEXT | |
| `nombre_local_nuevo` | TEXT | |
| `motivo` | TEXT | |
| `mesas_afectadas` | INTEGER | |
| `estado_parseo` | TEXT | |

---

**`sv_sync_meta`** — control de sincronización

| Columna | Tipo | PK | Descripción |
|---|---|---|---|
| `key` | TEXT | ✅ | Ej. `"party_map_2021_fingerprint"` |
| `value` | TEXT | | |
| `updated_at` | TEXT | | |

---

### 📅 Dataset histórico 2021 (1V y 2V)

**`mesas_2021`** — 172,976 filas (86,488 × 2 vueltas) · 1 fila por (vuelta, mesa)

| Columna | Tipo | PK | Descripción |
|---|---|---|---|
| `vuelta` | INTEGER | ✅ | `1` = primera vuelta, `2` = segunda vuelta |
| `codigo_mesa` | TEXT | ✅ | Código de 6 dígitos |
| `ubigeo` | TEXT | | Ubigeo 6 dígitos |
| `departamento` | TEXT | | |
| `provincia` | TEXT | | |
| `distrito` | TEXT | | |
| `tipo_eleccion` | TEXT | | |
| `descrip_estado_acta` | TEXT | | |
| `tipo_observacion` | TEXT | | |
| `n_cvas` | INTEGER | | Nro. candidaturas |
| `n_elec_habil` | INTEGER | | Electores hábiles |
| `votos_vb` | INTEGER | | Votos en blanco |
| `votos_vn` | INTEGER | | Votos nulos |
| `votos_vi` | INTEGER | | Votos impugnados |
| `votos_emitidos` | INTEGER | | |
| `votos_validos` | INTEGER | | |
| `fetched_at` | TEXT | | |

Índices: `(vuelta, departamento, provincia, distrito)`, `(vuelta, ubigeo)`

---

**`votos_2021`** — ~1.7M filas · 1 fila por (vuelta, mesa, partido)

| Columna | Tipo | PK |
|---|---|---|
| `vuelta` | INTEGER | ✅ |
| `codigo_mesa` | TEXT | ✅ |
| `partido_id` | TEXT | ✅ |
| `votos` | INTEGER | |
| `fetched_at` | TEXT | |

---

**`partidos_2021`** — 20 filas (18 en 1V + 2 en 2V)

| Columna | Tipo | PK | Descripción |
|---|---|---|---|
| `vuelta` | INTEGER | ✅ | `1` / `2` |
| `partido_id` | TEXT | ✅ | Ej. `"PC"`, `"K"`, `"RL"` |
| `nombre_partido` | TEXT | | |
| `candidato` | TEXT | | Nombre completo del candidato presidencial |
| `fetched_at` | TEXT | | |

Partidos 1V 2021: 18 candidatos.  
Partidos 2V 2021: `PC`=Pedro Castillo, `K`=Keiko Fujimori.

---

### 🧰 Tablas operativas (cache y auditoría)

**`mesa_cache`** — cache de bundles completos de mesa (respuesta ONPE cruda)

| Columna | Tipo | PK |
|---|---|---|
| `codigo_mesa` | TEXT | ✅ |
| `payload_json` | TEXT | JSON completo |
| `fetched_at` | TEXT | |
| `source` | TEXT | `"local_db"` / `"api_live"` |
| `id_eleccion` | INTEGER | |
| `payload_hash` | TEXT | SHA-256 para detección de cambios |
| `schema_version` | INTEGER | |

---

**`geo_query_cache`** — cache de resultados de queries geográficos

| Columna | Tipo | PK |
|---|---|---|
| `query_key` | TEXT | ✅ |
| `payload_json` | TEXT | |
| `fetched_at` | TEXT | |

---

### Tablas temporales / staging (crear y truncar en cada carga)

| Tabla staging | Fuente real |
|---|---|
| `stg_mesas_1v` | `mesas_data` |
| `stg_votos_1v` | `votos` |
| `stg_partidos_1v` | `agrupaciones` |
| `stg_mesas_2v` | `mesas_sv` |
| `stg_votos_2v` | `votos_sv` |
| `stg_partidos_2v` | `agrupaciones_sv` |
| `stg_ubicaciones_2v` | `ubicaciones_sv` |
| `stg_resumen_nac` | `sv_resumen_nacional` |
| `stg_resumen_dptos` | `sv_resumen_departamentos` |
| `stg_resumen_provs` | `sv_resumen_provincias` |
| `stg_cobertura` | `sv_resumen_cobertura` |
| `stg_mesas_2021` | `mesas_2021` |
| `stg_votos_2021` | `votos_2021` |
| `stg_partidos_2021` | `partidos_2021` |
| `stg_geo` | `ubigeo_reniec` + `foreign_catalog` |

---

## Adaptaciones por motor

| Aspecto | SQLite | MySQL | SQL Server | Snowflake | Fabric Warehouse |
|---|---|---|---|---|---|
| `TEXT` | TEXT | VARCHAR(512) / TEXT | NVARCHAR(512) / NVARCHAR(MAX) | VARCHAR | VARCHAR |
| `INTEGER` | INTEGER | INT / BIGINT | INT / BIGINT | NUMBER | INT |
| `REAL` | REAL | DOUBLE | FLOAT / DECIMAL(18,6) | FLOAT | FLOAT |
| Timestamps | TEXT (ISO-8601) | DATETIME | DATETIME2 | TIMESTAMP_NTZ | DATETIME2 |
| JSON | TEXT | JSON | NVARCHAR(MAX) | VARIANT | NVARCHAR(MAX) |
| Upsert | `INSERT OR REPLACE` / `ON CONFLICT DO UPDATE` | `INSERT ... ON DUPLICATE KEY UPDATE` | `MERGE` | `MERGE` | `MERGE` |
| Bulk load | `executemany` batch | `LOAD DATA INFILE` | `BULK INSERT` / `bcp` | `COPY INTO` | `COPY INTO` / Pipeline |
| Auto-increment | — | `AUTO_INCREMENT` | `IDENTITY(1,1)` | `AUTOINCREMENT` | `IDENTITY` |

### Interfaces
- `IDataStore`
  - `health()`
  - `bootstrap_*()`
  - `query_*()`
  - `upsert_*()`
  - `close()`

Implementaciones:
- `SQLiteStore`
- `MySQLStore`
- `SqlServerStore`
- `SnowflakeStore`
- `FabricWarehouseStore`

## Flujo de hidratación

1. Descargar o leer la fuente oficial.
2. Normalizar a staging.
3. Cargar catálogos.
4. Cargar cabeceras de mesa.
5. Cargar votos.
6. Construir agregados.
7. Ejecutar validaciones.
8. Publicar solo si la paridad coincide.

## Estrategia por motor

### SQLite
- Default local.
- Útil para desarrollo, pruebas y despliegue offline.
- Transacciones batch e índices locales.

### MySQL
- Adecuado para despliegues medianos.
- Usar pool, TLS y usuario read-only para consultas MCP.
- Cargas masivas con `LOAD DATA` o batches transaccionales.

### SQL Server / Azure SQL
- Útil en entornos corporativos con AD / Azure AD.
- Cargas con `BULK INSERT` o `bcp`.
- Activar `READ_COMMITTED_SNAPSHOT` si el patrón es muy concurrente.

### Snowflake
- Ideal como warehouse analítico.
- Ingesta vía `COPY INTO` desde stage.
- Consultas MCP contra vistas/materialized views de serving.

### Fabric Warehouse
- Opción enterprise para ecosistema Microsoft.
- Ingesta por pipelines o notebooks.
- Serving con tablas optimizadas para lectura.

## Best practices corporativas

### Seguridad
- Secret manager obligatorio.
- TLS en tránsito.
- Usuario de lectura separado del usuario de carga.
- Principio de mínimo privilegio.
- Rotación de credenciales.

### Conectividad
- Pool de conexiones.
- Timeout de conexión y de query.
- Retries solo para fallas transitorias.
- Red privada / endpoint privado cuando aplique.

### Gobierno
- Esquema versionado.
- Auditoría de cargas.
- Checksums y conteos de control.
- Monitoreo de latencia y drift de datos.

## Configuración MCP sugerida

Variables:
- `ONPE_DB_PROVIDER=sqlite|mysql|sqlserver|snowflake|fabric`
- `ONPE_DB_DSN=...`
- `ONPE_DB_HOST=...`
- `ONPE_DB_PORT=...`
- `ONPE_DB_NAME=...`
- `ONPE_DB_USER=...`
- `ONPE_DB_PASSWORD=...`
- `ONPE_DB_SCHEMA=...`
- `ONPE_DB_SSL=true|false`
- `ONPE_DB_POOL_MIN=1`
- `ONPE_DB_POOL_MAX=10`
- `ONPE_DB_READ_ONLY=true|false`
- `ONPE_DB_TIMEOUT_SECONDS=30`
- `ONPE_DB_STATEMENT_TIMEOUT_SECONDS=60`

Reglas:
- SQLite sigue siendo el default.
- Si `ONPE_DB_PROVIDER` apunta a otro motor, el server usa ese backend sin cambiar tools.
- Si la conexión falla, responder con error explícito.

## Validaciones mínimas
- Totales nacionales por vuelta.
- Totales por departamento/provincia/distrito.
- Totales por mesa.
- Comparación contra SQLite de referencia.
- Igualdad de agregaciones críticas por `partido_id`.

## Fase de implementación
1. Separar la capa de storage en una interfaz.
2. Extraer la lógica común de hidratación.
3. Implementar adaptadores por motor.
4. Parametrizar el arranque con `ONPE_DB_PROVIDER`.
5. Agregar pruebas de paridad.
6. Documentar despliegue corporativo.

## Resultado esperado
- SQLite queda como modo local.
- MySQL / SQL Server / Snowflake / Fabric Warehouse quedan habilitados para corporativo.
- La experiencia MCP no cambia.
- Los números siguen reconciliando entre motores.
