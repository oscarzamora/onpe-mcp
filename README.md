# ONPE MCP

Servidor MCP para exponer herramientas de consulta y actualización de resultados ONPE reutilizando el proyecto `onpescraper`.

## Arquitectura de datos (best practice)

- SQLite como fuente canónica para consultas rápidas y reuso de datos.
- JSONL append-only para trazabilidad de eventos y auditoría.
- Markdown para resumen diario legible por humanos.

Estructura generada en `data/`:

- `data/onpe.db` (SQLite)
- `data/raw/events.jsonl` (histórico de eventos)
- `data/reports/daily-summary.md` (resumen operativo)

Modo API-first:

- No necesitas archivos de arranque para comenzar.
- El MCP puede iniciar vacío y construir su data con consultas ONPE en vivo.
- Para geografía de extranjero (pais/ciudad), usa `onpe_sync_foreign_catalog`.

## Características

- Consulta de mesa individual con normalización y validación.
- Consulta por lotes con límites de seguridad.
- Health check de rutas y dependencias.
- Persistencia local cache-first para evitar consultas repetidas a ONPE.
- Tool conversacional de alto nivel para preguntas comunes.

## Requisitos

- Python 3.11+
- Proyecto `onpescraper` disponible localmente.

## Configuración

Variables de entorno soportadas:

- `ONPE_SCRAPER_ROOT`: ruta absoluta al proyecto `onpescraper`.
- `ONPE_SOURCE_DIR`: ruta de `source_data` (opcional; por defecto `<ONPE_SCRAPER_ROOT>/source_data`).
- `ONPE_OUTPUT_DIR`: ruta de `output` (opcional; por defecto `<ONPE_SCRAPER_ROOT>/output`).
- `ONPE_LOG_LEVEL`: nivel de logging (`INFO`, `DEBUG`, etc.).
- `ONPE_MAX_BATCH_SIZE`: tamaño máximo permitido en consultas por lote (default: 200).
- `ONPE_DATA_DIR`: directorio de persistencia local (default: `./data`).
- `ONPE_CACHE_TTL_SECONDS`: TTL de cache para mesa individual (default: 900).
- `ONPE_GEO_QUERY_CACHE_TTL_SECONDS`: TTL de cache para resultados de consultas geográficas en SQLite (default: 300).
- `ONPE_AUTO_SYNC_FOREIGN_CATALOG_ON_DEMAND`: auto-sincroniza catálogo extranjero desde ONPE cuando una consulta geo no encuentra catálogo local (default: `true`).
- `ONPE_BOOTSTRAP_ON_STARTUP`: importa snapshot local de `onpescraper/output` al iniciar (default: `true`).
- `ONPE_BOOTSTRAP_INCLUDE_VOTES`: cuando `ONPE_BOOTSTRAP_ON_STARTUP=true`, incluye votos del snapshot (default: `true`).
- `ONPE_ATU_MANERA_BOOTSTRAP`: ejecuta bootstrap de ATuManera al iniciar si está en `true` (default: `false`).

Si no defines `ONPE_SCRAPER_ROOT`, el servidor intentará resolver `../onpescraper` desde este repo.

## Instalación

```bash
pip install -e .
```

## Ejecución

```bash
onpe-mcp
```

## Tools MCP expuestas

- `onpe_get_mesa`
- `onpe_get_mesas_batch`
- `onpe_health`
- `onpe_chat`
- `onpe_sync_foreign_catalog`
- `onpe_bootstrap_snapshot`

## Ejemplos conversacionales

Usa la tool `onpe_chat` con texto natural:

- `mesa 001234`
- `candidato Keiko Fujimori`
- `candidato 8`
- `pais Chile`
- `ciudad Santiago`
- `dame quien fue el diputado mas votado en lima`
- `senador más votado en arequipa`

Notas:

- Las consultas por país/ciudad usan catálogo en SQLite poblado desde ONPE con `onpe_sync_foreign_catalog`.
- En cold start, si no hay catálogo extranjero local y `ONPE_AUTO_SYNC_FOREIGN_CATALOG_ON_DEMAND=true`, `onpe_chat` intentará sincronizarlo automáticamente desde ONPE (sin precargar votos).
- En cold start, si tras el bootstrap local la base de mesas queda vacía, el servidor intenta una hidratación inicial automática desde ATuManera (aunque `ONPE_ATU_MANERA_BOOTSTRAP=false`).
- Las consultas por candidato funcionan con votos/agrupaciones en SQLite y usan `source_data/candidato.txt` solo como enriquecimiento opcional.
- Las consultas geo repetidas reutilizan cache corto de query (`ONPE_GEO_QUERY_CACHE_TTL_SECONDS`) para reducir latencia.
- Estrategia híbrida recomendada: bootstrap opcional con `onpe_bootstrap_snapshot` para acelerar, y fallback live API para datos faltantes o cuando se fuerza consulta en vivo (`onpe_get_mesa(..., force_live=true)`).
- Consultas legislativas de "más votado" (diputados/senadores) se resuelven por endpoint live especializado de ONPE por distrito electoral.

## Contrato ONPE

- Especificación técnica: `docs/onpe-api-contract.md`
- JSON schema response: `schemas/onpe.actas.buscar.mesa.response.schema.json`
- JSON schema acta mínima: `schemas/onpe.acta.min.schema.json`
