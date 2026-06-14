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
