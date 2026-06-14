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

## Esquema mínimo a crear

La idea es usar el mismo modelo lógico en todos los motores, aunque cambie la sintaxis exacta de tipos, índices o materialización.

### Tablas base

```sql
-- Dimensiones
dim_election(
  election_key      INT / BIGINT / IDENTITY / SEQUENCE,
  election_year     SMALLINT,
  round_number      TINYINT,
  election_name     VARCHAR(...),
  is_active         BOOLEAN
)

dim_geo(
  geo_key           INT / BIGINT / IDENTITY / SEQUENCE,
  ubigeo            VARCHAR(6) UNIQUE,
  geo_level         VARCHAR(...),   -- nacional, departamento, provincia, distrito, exterior, continente, país, ciudad
  parent_ubigeo      VARCHAR(6) NULL,
  name              VARCHAR(...)
)

dim_party(
  party_key         INT / BIGINT / IDENTITY / SEQUENCE,
  election_key      INT,
  party_id          VARCHAR(...),
  party_name        VARCHAR(...),
  candidate_name    VARCHAR(...),
  UNIQUE (election_key, party_id)
)

-- Hechos
fact_mesa(
  mesa_key          BIGINT / VARCHAR(...),
  election_key      INT,
  ubigeo            VARCHAR(6),
  local_code        VARCHAR(...),
  mesa_code         VARCHAR(...),
  electores_habiles INT,
  votos_emitidos    INT,
  votos_validos     INT,
  votos_blancos     INT,
  votos_nulos       INT,
  votos_impugnados  INT,
  status_code       VARCHAR(...),
  status_label      VARCHAR(...),
  updated_at        TIMESTAMP
)

fact_vote(
  mesa_key          BIGINT / VARCHAR(...),
  election_key      INT,
  party_key         INT,
  votes             INT,
  pct_validos       DECIMAL(...),
  pct_emitidos      DECIMAL(...),
  PRIMARY KEY (mesa_key, election_key, party_key)
)

-- Serving / agregados
agg_geo_summary(
  election_key      INT,
  geo_key           INT,
  party_key         INT,
  votes             BIGINT,
  pct_validos       DECIMAL(...),
  total_validos     BIGINT,
  total_mesas       BIGINT,
  mesas_contabilizadas BIGINT,
  updated_at        TIMESTAMP,
  PRIMARY KEY (election_key, geo_key, party_key)
)

-- Operación
sync_meta(
  meta_key          VARCHAR(...) PRIMARY KEY,
  meta_value        VARCHAR(...),
  updated_at        TIMESTAMP
)

raw_events(
  event_id          BIGINT / IDENTITY / SEQUENCE,
  tool_name         VARCHAR(...),
  payload_json      JSON / NVARCHAR(MAX),
  created_at        TIMESTAMP
)
```

### Tablas temporales / staging
- `stg_mesas`
- `stg_votes`
- `stg_parties`
- `stg_geo`
- `stg_summary`

Estas tablas pueden borrarse o truncarse en cada carga. Sirven para validar antes de promover al core.

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
