# ONPE API Contract (mesa)

## Objetivo

Definir un contrato estable para la integración MCP con el endpoint de ONPE usado por el scraper:

- Endpoint: `GET /presentacion-backend/actas/buscar/mesa`
- Parámetro obligatorio: `codigoMesa`

Este contrato está alineado a la implementación observada en:

- `onpescraper/src/onpe_scraper/scraper.py`

## Request contract

### URL base

- `https://resultadoelectoral.onpe.gob.pe/presentacion-backend`

### Path

- `/actas/buscar/mesa`

### Query params

- `codigoMesa` (string numérico, recomendado 6 dígitos con zero-padding)

### Headers recomendados

- `Accept: application/json, text/plain, */*`
- `X-Requested-With: XMLHttpRequest`
- `Referer: https://resultadoelectoral.onpe.gob.pe/`
- `User-Agent: navegador moderno`

### Notas operativas

- El backend puede devolver HTML si no se emula correctamente cliente navegador.
- En scraper se usa `curl_cffi` con `impersonate=chrome124`.

## Response contract (mínimo esperado)

Tipo raíz: objeto JSON.

Campos mínimos:

- `data`: arreglo de actas (`array<object>`)

Cada acta debería contener, al menos para extracción completa:

- `idEleccion` (number)
- `descripcionEstadoActa` (string)
- `codigoMesa` (string)
- `idUbigeo` (string)
- `nombreLocalVotacion` (string)
- `totalElectoresHabiles` (number|string)
- `totalVotosEmitidos` (number|string)
- `totalVotosValidos` (number|string)
- `detalle` (array<object>)

Cada item de `detalle` usado por el parser:

- `adCodigo` (string)
- `adVotos` (number|string)
- `adAgrupacionPolitica` (string)
- `adDescripcion` (string)

## Reglas de selección de acta

Orden aplicado por el scraper:

1. Buscar acta con `idEleccion == configured_id_eleccion`.
2. Si existe y `descripcionEstadoActa == "Contabilizada"`, usarla.
3. Si no, buscar cualquier acta `Contabilizada`.
4. Si no hay contabilizada, usar la seleccionada por `idEleccion`.
5. Como último fallback, usar la primera acta disponible.

## Reglas de mapeo de campos

### mesa_data

- `codigo_mesa <- codigoMesa`
- `ubigeo <- idUbigeo`
- `local_votacion <- nombreLocalVotacion`
- `electores_habiles <- totalElectoresHabiles`
- `votos_emitidos <- totalVotosEmitidos`
- `votos_validos <- totalVotosValidos`
- `estado_acta <- descripcionEstadoActa`
- `blancos <- detalle[adCodigo=="80"].adVotos`
- `nulos <- detalle[adCodigo=="81"].adVotos`
- `impugnados <- detalle[adCodigo=="82"].adVotos`

### agrupaciones

- `partido_id <- detalle[].adAgrupacionPolitica`
- `nombre <- detalle[].adDescripcion`

### votos

- `codigo_mesa <- codigoMesa(normalizado)`
- `partido_id <- detalle[].adAgrupacionPolitica`
- `votos <- detalle[].adVotos`

## Validación recomendada en MCP

Validar en este orden:

1. HTTP status `2xx`.
2. Content-Type o parseo JSON válido.
3. Estructura raíz `object` con `data` como `array`.
4. Para cada acta candidata, tolerar faltantes con defaults seguros.
5. Registrar payload crudo hash y timestamp para trazabilidad.

## Esquemas JSON asociados

- `schemas/onpe.actas.buscar.mesa.response.schema.json`
- `schemas/onpe.acta.min.schema.json`

## Consideraciones de compatibilidad

- ONPE puede alterar estructura o nombres de campos sin aviso.
- Mantener validación tolerante a faltantes y tipos mixtos (`number|string`).
- Versionar contrato local (`schema_version`) en persistencia del MCP.
