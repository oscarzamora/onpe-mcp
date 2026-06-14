# Plan QA — `onpe-mcp` Segunda Vuelta 2026

> **Audiencia:** Agente QA externo.
> **Alcance:** Validar que toda consulta de segunda vuelta 2026 sea respondida exclusivamente con tools MCP (`onpe-mcp`), sin recurrir a SQL directo, lectura de `.txt` del scraper, ni a fuentes externas.
> **Origen:** Preguntas reales formuladas en una sesión de chat el 2026-06-11, ampliadas con permutaciones por nivel geográfico y tipo de consulta.
> **Snapshot referencia:** 98.25% mesas contabilizadas, Keiko 50.003% / Sánchez 49.997% (datos al 2026-06-11 22:01 Lima).

---

## 1. Tools MCP disponibles para segunda vuelta

| Tool | Propósito |
|---|---|
| `onpe_health` | Salud del servidor, hidratación de SQLite, paths críticos |
| `onpe_sv_bootstrap(force=false)` | Carga inicial desde scraper local |
| `onpe_sv_refresh()` | UPSERT incremental desde scraper |
| `onpe_sv_get_mesa(codigo_mesa)` | Cabecera, votos y ubicación de mesa SV |
| `onpe_sv_resultados_geo(nivel, ubigeo?, nombre?, top_n=10)` | Resultados por nivel geográfico |
| `onpe_sv_cobertura()` | Cobertura de actas por departamento + continente |
| `onpe_sv_comparacion_geo(ubigeo_prefix)` | PV vs SV por prefijo de ubigeo |
| `onpe_sv_reasignados(dpto?, motivo?)` | Locales reasignados entre PV y SV |
| `onpe_chat(query)` | Interfaz conversacional cache-first |

---

## 2. Reglas críticas de validación

Para **cada** pregunta del plan, el QA debe verificar:

1. **La respuesta debe provenir de una tool MCP**, no de SQL ad-hoc ni de archivos `.txt`.
2. El payload debe seguir el shape estándar:
   ```json
   { "ok": true,  "data": {...}, "errors": [], "meta": {"duration_ms": N} }
   { "ok": false, "data": null,  "errors": [{"code": "...", "message": "..."}], "meta": {...} }
   ```
3. `meta.source` (cuando exista) debe indicar la fuente: `sqlite_sv`, `local_db_sv`, `scraper`, etc.
4. Las cifras devueltas deben **cuadrar entre tools** (cross-check):
   - Suma de votos por distrito ≈ total nacional (± mesas pendientes).
   - Suma de mesas C+E+P por departamento = total de departamento.
5. **No se permite inventar candidatos, partidos ni cifras**. Si el dato no está disponible, debe devolverse error explícito.
6. Cualquier pregunta que **no** pueda resolverse 100% vía MCP debe registrarse como **GAP** (ver §11).

---

## 3. Categoría A — Estado y disponibilidad del MCP

| ID | Pregunta natural | Tool esperado | Parámetros | Criterio de aceptación |
|---|---|---|---|---|
| A1 | ¿Ya está trabajando el MCP de segunda vuelta? | `onpe_health` | — | `ok=true`, `data.status="ok"`, `data.hydrated=true`, mesas_sv > 0 |
| A2 | ¿El MCP ya está listo? | `tool discovery` + `onpe_health` | — | Las 7 tools SV deben aparecer en `tools/list`; `onpe_health` retorna `hydrated=true` |
| A3 | ¿Cuántas mesas tiene cargadas el MCP de segunda vuelta? | `onpe_sv_bootstrap(force=false)` | — | `data.mesas_sv = 92766` con `skipped=true` si ya estaba cargado |
| A4 | Refresca los datos de segunda vuelta. | `onpe_sv_refresh` | — | `ok=true`, retorna conteos por tabla (`mesas_sv`, `votos_sv`, `ubicaciones_sv`, `ctas`) |
| A5 | ¿Qué tools de segunda vuelta están disponibles? | `tool discovery` | — | Lista debe incluir las 7 tools `onpe_sv_*` |

---

## 4. Categoría B — Resultados nacionales

| ID | Pregunta natural | Tool esperado | Parámetros | Criterio de aceptación |
|---|---|---|---|---|
| B1 | ¿Cómo van las votaciones de segunda vuelta? | `onpe_sv_resultados_geo` | `nivel="nacional"` | Top 4 (Keiko, Sánchez, Nulos, Blancos). Suma % válidos = 100. |
| B2 | ¿Quién va ganando la segunda vuelta? | `onpe_chat` o `onpe_sv_resultados_geo` | `query="resultados nacional segunda vuelta"` | Debe responder con el candidato puntero y el margen actual. |
| B3 | ¿Cuál es el margen entre Keiko y Sánchez? | `onpe_sv_resultados_geo` | `nivel="nacional"` | Diferencia = `votos[Keiko] − votos[Sánchez]`; valor consistente con snapshot. |
| B4 | ¿Cuántos votos nulos y blancos hay a nivel nacional? | `onpe_sv_resultados_geo` | `nivel="nacional"` | Devuelve `partido_id=81` (NULOS) y `partido_id=80` (BLANCOS). |
| B5 | ¿Qué porcentaje de actas se ha contabilizado? | `onpe_sv_cobertura` | — | Sumar `actas_contabilizadas` / `total_actas` ≈ 98.25%. |

---

## 5. Categoría C — Resultados por nivel geográfico (permutaciones)

### C.1 Por departamento

| ID | Pregunta natural | Tool | Parámetros | Criterio |
|---|---|---|---|---|
| C1.1 | ¿Cómo va la segunda vuelta en Lima? | `onpe_sv_resultados_geo` | `nivel="departamento", ubigeo="140000"` | Devuelve resultados Lima con totales > 0 |
| C1.2 | Resultados en Arequipa | `onpe_sv_resultados_geo` | `nivel="departamento", nombre="arequipa"` | Match por nombre, suma de mesas consistente |
| C1.3 | ¿Cómo está Cusco? | `onpe_sv_resultados_geo` | `nivel="departamento", nombre="cusco"` | Match insensible a tildes |
| C1.4 | Top 5 departamentos donde va ganando Keiko | `onpe_sv_resultados_geo` | `nivel="departamento", top_n=50` (filtrar cliente) | Ordenamiento por % Keiko |
| C1.5 | Top 5 departamentos donde va ganando Sánchez | `onpe_sv_resultados_geo` | mismo + filtro | Ordenamiento por % Sánchez |
| C1.6 | ¿Cuál es el departamento con mayor participación? | `onpe_sv_cobertura` | — | Ordenar por `pct_actas_contabilizadas` |

### C.2 Por provincia

| ID | Pregunta | Tool | Parámetros | Criterio |
|---|---|---|---|---|
| C2.1 | ¿Cómo va la provincia de Lima? | `onpe_sv_resultados_geo` | `nivel="provincia", ubigeo="150100"` | Devuelve provincia Lima |
| C2.2 | Resultados en Trujillo (provincia) | `onpe_sv_resultados_geo` | `nivel="provincia", nombre="trujillo"` | Match parcial |
| C2.3 | ¿Cómo va la provincia constitucional del Callao? | `onpe_sv_resultados_geo` | `nivel="provincia", ubigeo="240100"` | Datos válidos para Callao |

### C.3 Por distrito

| ID | Pregunta | Tool | Parámetros | Criterio |
|---|---|---|---|---|
| C3.1 | ¿Cómo fue Miraflores? | `onpe_sv_resultados_geo` | `nivel="distrito", nombre="miraflores"` | Devuelve Miraflores Lima |
| C3.2 | ¿Cómo fue San Isidro? | `onpe_sv_resultados_geo` | `nivel="distrito", ubigeo="140124"` | Top: Keiko ≈ 84%, Sánchez ≈ 16% |
| C3.3 | Resultados en La Molina | `onpe_sv_resultados_geo` | `nivel="distrito", ubigeo="140110"` | Top: Keiko ≈ 75%, Sánchez ≈ 25% |
| C3.4 | ¿Cómo fue VES? | `onpe_sv_resultados_geo` | `nivel="distrito", nombre="villa el salvador"` | Resultados consistentes |
| C3.5 | ¿Cómo fue SJL? | `onpe_sv_resultados_geo` | `nivel="distrito", nombre="san juan de lurigancho"` | Datos válidos |
| C3.6 | Top 10 distritos más fujimoristas a nivel nacional | `onpe_sv_resultados_geo` | `nivel="distrito", top_n=50`, filtro cliente | Ordenar por % Keiko, descartar mesas < N |
| C3.7 | Top 10 distritos más sanchecistas | `onpe_sv_resultados_geo` | mismo + filtro | Ordenar por % Sánchez |

### C.4 Por ciudad / continente / país exterior

| ID | Pregunta | Tool | Parámetros | Criterio |
|---|---|---|---|---|
| C4.1 | ¿Cómo votó el exterior? | `onpe_sv_resultados_geo` | `nivel="continente"` | 5 filas (África, Américas, Asia, Europa, Oceanía) |
| C4.2 | Resultados en Argentina (exterior) | `onpe_sv_resultados_geo` | `nivel="pais_exterior", nombre="argentina"` | Datos válidos para país 920100 |
| C4.3 | ¿Cómo votó la comunidad peruana en EE.UU.? | `onpe_sv_resultados_geo` | `nivel="pais_exterior", nombre="estados unidos"` | Datos válidos |
| C4.4 | ¿Cómo votó Madrid? | `onpe_sv_resultados_geo` | `nivel="ciudad", nombre="madrid"` | Match parcial + ámbito europeo |
| C4.5 | ¿Cómo votó Tokio? | `onpe_sv_resultados_geo` | `nivel="ciudad", nombre="tokio"` | Match parcial |

---

## 6. Categoría D — Cobertura y actas pendientes

| ID | Pregunta | Tool | Parámetros | Criterio |
|---|---|---|---|---|
| D1 | ¿Qué porcentaje de actas se ha contabilizado a nivel nacional? | `onpe_sv_cobertura` | — | Calcular sobre filas devueltas, cuadrar con `onpe_health` |
| D2 | ¿Cuál es el departamento con menos cobertura? | `onpe_sv_cobertura` | — | Ordenar ascendente; al snapshot, Lima 96.90% |
| D3 | ¿Cuáles departamentos tienen >99% de cobertura? | `onpe_sv_cobertura` | — | Filtrar `pct_actas_contabilizadas > 99` |
| D4 | ¿Cuántas mesas faltan por contabilizar? | `onpe_sv_cobertura` + `onpe_health` | — | `total_mesas - mesas_contabilizadas` |
| D5 | ¿Cómo va la cobertura del voto en el exterior? | `onpe_sv_cobertura` | — | Filtrar ubigeos 91xxxx–95xxxx |

---

## 7. Categoría E — Comparación primera vs segunda vuelta (transferencia)

| ID | Pregunta | Tool | Parámetros | Criterio |
|---|---|---|---|---|
| E1 | ¿Cómo fue la transferencia de votos en La Molina entre primera y segunda vuelta? | `onpe_sv_comparacion_geo` | `ubigeo_prefix="140110"` | Devuelve bloques `primera_vuelta` y `segunda_vuelta` con totales por partido |
| E2 | Compara San Isidro PV vs SV | `onpe_sv_comparacion_geo` | `ubigeo_prefix="140124"` | Mismo shape, totales > 0 en ambos bloques |
| E3 | ¿Cómo cambió el voto en Lima entre primera y segunda vuelta? | `onpe_sv_comparacion_geo` | `ubigeo_prefix="14"` o `"140000"` | Acepta prefijo corto (≥2 chars) o ubigeo completo |
| E4 | Variación de participación en Arequipa entre vueltas | `onpe_sv_comparacion_geo` | `ubigeo_prefix="04"` | Comparar mesas y suma de votos válidos |
| E5 | Transferencia de votos en VES | `onpe_sv_comparacion_geo` | `ubigeo_prefix=<ubigeo VES>` | Bloques PV/SV completos |
| E6 | ¿Cuántos votos de López Aliaga fueron a Keiko en Lima? | `onpe_sv_comparacion_geo` + inferencia | `ubigeo_prefix="140000"` | **Caveat:** la tool no devuelve transferencia directa, sólo bases por partido. El agente debe **declarar la limitación**, no inventar el split. |
| E7 | ¿Dónde subió más Keiko respecto a primera vuelta? | iteración sobre `onpe_sv_comparacion_geo` | varios ubigeos | Solo si el agente itera responsablemente; sino, declarar gap |

---

## 8. Categoría F — Mesas para envío al JEE (gap principal)

> ⚠️ **GAP CONOCIDO:** Hoy no existe una tool MCP dedicada a estado de actas (`C`/`E`/`P`). Cualquier pregunta de esta categoría debe **forzar un error o reportar el gap**, no responder vía SQL directo.

| ID | Pregunta | Tool esperado (futuro) | Estado actual | Resultado QA esperado |
|---|---|---|---|---|
| F1 | ¿Cuántas mesas de segunda vuelta están enviadas al JEE? | `onpe_sv_estado_actas` (no existe) | **GAP** | El agente debe responder "no disponible vía MCP", no calcular con SQL |
| F2 | Si todas las mesas observadas se aceptaran, ¿cómo quedaría el resultado? | `onpe_sv_estado_actas(escenario_jee=True)` (no existe) | **GAP** | Mismo |
| F3 | ¿Cuántas mesas observadas hay en Lima? | `onpe_sv_estado_actas(nivel="departamento", ubigeo="140000")` (no existe) | **GAP** | Mismo |
| F4 | ¿Cuántos votos pre-contados tienen las mesas observadas? | `onpe_sv_estado_actas` (no existe) | **GAP** | Mismo |
| F5 | ¿Qué pasa si el JEE anula las mesas E? | (análisis derivado, no atómico) | **GAP** | Debe declarar limitación |

**Acción requerida tras QA:** documentar como ticket "Implementar `onpe_sv_estado_actas` con soporte `nivel`, `ubigeo`, `escenario_jee`" y extender `onpe_chat` con intent `mesas_jee`.

---

## 9. Categoría G — Locales reasignados

| ID | Pregunta | Tool | Parámetros | Criterio |
|---|---|---|---|---|
| G1 | ¿Cuántos locales fueron reasignados entre primera y segunda vuelta? | `onpe_sv_reasignados` | — | Retorna 44 registros (o el total vigente) |
| G2 | ¿Qué locales reasignados hay en Piura? | `onpe_sv_reasignados` | `dpto="piura"` | Filtra por departamento; insensible a tildes |
| G3 | ¿Qué locales fueron reasignados por extorsión? | `onpe_sv_reasignados` | `motivo="extorsion"` | Match parcial en campo motivo |
| G4 | ¿Cuáles fueron reasignados por reconstrucción? | `onpe_sv_reasignados` | `motivo="reconstruccion"` | Match parcial |
| G5 | ¿En qué departamentos hubo más locales reasignados? | `onpe_sv_reasignados` | — | Agregar por departamento del lado cliente |
| G6 | ¿La Molina tuvo locales reasignados? | `onpe_sv_reasignados` | `dpto="lima"` (filtro fino cliente) | Confirma o niega con datos de la tool |

---

## 10. Categoría H — Mesa individual

| ID | Pregunta | Tool | Parámetros | Criterio |
|---|---|---|---|---|
| H1 | Dame los resultados de la mesa 000001 en segunda vuelta | `onpe_sv_get_mesa` | `codigo_mesa="000001"` | Cabecera + votos + ubicación |
| H2 | Mesa 1 (sin ceros a la izquierda) | `onpe_sv_get_mesa` | `codigo_mesa="1"` | Debe normalizar a `"000001"` y devolver lo mismo que H1 |
| H3 | Mesa 999999 (probable no existe) | `onpe_sv_get_mesa` | `codigo_mesa="999999"` | `ok=false`, `code="NOT_FOUND"` |
| H4 | Mesa con código inválido | `onpe_sv_get_mesa` | `codigo_mesa="ABC"` | `ok=false`, `code="VALIDATION_ERROR"` |
| H5 | Mesa de exterior (ej: alguna de Madrid) | `onpe_sv_get_mesa` | `codigo_mesa=<código real>` | `id_ambito=2` (exterior) |
| H6 | Mesa con código ≥ 900000 (mesas peruanas alto rango) | `onpe_sv_get_mesa` | `codigo_mesa="900001"` | Debe responder normal; el `id_ambito=1` |

---

## 11. Categoría I — Casos edge y errores esperados

| ID | Pregunta / acción | Tool | Resultado esperado |
|---|---|---|---|
| I1 | `onpe_sv_resultados_geo(nivel="invalido")` | — | `ok=false` con mensaje informativo, sin caer |
| I2 | `onpe_sv_resultados_geo(nivel="departamento", ubigeo="999999")` | — | Resultado vacío con `ok=true` o `code="NOT_FOUND"`, nunca crash |
| I3 | `onpe_sv_comparacion_geo(ubigeo_prefix="")` | — | Error de validación, no consulta vacía |
| I4 | `onpe_sv_comparacion_geo(ubigeo_prefix="ZZ")` | — | Mesas=0, votos=[] en ambos bloques; ok=true |
| I5 | `onpe_sv_resultados_geo(nivel="distrito", nombre="x")` | — | Resultado vacío, no error |
| I6 | `onpe_sv_get_mesa(codigo_mesa="")` | — | `ok=false`, `code="VALIDATION_ERROR"` |
| I7 | `onpe_sv_bootstrap(force=true)` 2 veces seguidas | — | Idempotente, ambos exitosos |
| I8 | Llamar tool SV antes de `onpe_sv_bootstrap` en BD vacía | — | Mensaje claro pidiendo ejecutar bootstrap primero |

---

## 12. Categoría J — Lenguaje natural (`onpe_chat`)

> Validar que `onpe_chat` rutee correctamente a las tools SV. Donde el ruteo no exista, **registrar gap**, no fabricar respuesta.

| ID | Query natural | Intent esperado | Tool subyacente | Criterio |
|---|---|---|---|---|
| J1 | "¿Cómo va Keiko vs Sánchez?" | `nacional_sv` | `onpe_sv_resultados_geo(nivel="nacional")` | Respuesta debe mencionar % válidos de ambos |
| J2 | "Resultados segunda vuelta en Lima" | `geo_sv_departamento` | `onpe_sv_resultados_geo(nivel="departamento", nombre="lima")` | Sin caer en respuesta de primera vuelta |
| J3 | "Quién ganó en San Isidro segunda vuelta" | `geo_sv_distrito` | `onpe_sv_resultados_geo(nivel="distrito", nombre="san isidro")` | Detecta distrito correcto entre 3 homónimos (Lima vs Huancavelica vs Amazonas) — debe pedir desambiguación o priorizar Lima |
| J4 | "Cobertura segunda vuelta" | `cobertura_sv` | `onpe_sv_cobertura` | Resumen agregado |
| J5 | "Locales reasignados por extorsión" | `reasignados_sv` | `onpe_sv_reasignados(motivo="extorsion")` | Filtro aplicado |
| J6 | "Mesas observadas para JEE" | **GAP** | — | Debe declarar gap, no responder con SQL |
| J7 | "Compara Lima primera y segunda vuelta" | `comparacion_sv` | `onpe_sv_comparacion_geo(ubigeo_prefix="140000")` | Devuelve los dos bloques |
| J8 | "Resultados en Argelia" | `geo_sv_pais_exterior` | `onpe_sv_resultados_geo(nivel="pais_exterior", nombre="argelia")` | Match exterior (ubigeo 910100) |

---

## 13. Cross-checks de consistencia

Estas validaciones deben hacerse al final de la suite:

| ID | Check | Tools involucradas | Tolerancia |
|---|---|---|---|
| X1 | Suma de votos Keiko por departamento ≈ total nacional Keiko | `onpe_sv_resultados_geo(nivel="departamento")` vs `nivel="nacional"` | Δ ≤ votos en mesas pendientes |
| X2 | Suma de votos Sánchez por departamento ≈ total nacional Sánchez | mismo | mismo |
| X3 | Mesas reportadas por `onpe_health.total_mesas_local` = mesas en `onpe_sv_resultados_geo` agregadas | — | exacto |
| X4 | `onpe_sv_comparacion_geo` PV mesas ≈ SV mesas para mismo distrito | — | igualdad (mismo padrón) |
| X5 | `onpe_sv_cobertura` total contabilizadas concuerda con cifra del snapshot del scraper | — | exacto en última refrescada |
| X6 | `onpe_sv_get_mesa` para una mesa C en Lima da votos compatibles con suma por distrito | — | mesa ⊂ distrito |

---

## 14. Reporte sugerido por el agente QA

Por cada pregunta el QA debe devolver:

```yaml
id: B1
pregunta: "¿Cómo van las votaciones de segunda vuelta?"
tool_invocada: onpe_sv_resultados_geo
parametros: { nivel: "nacional" }
ok: true
fuente_declarada: sqlite_sv
respuesta_correcta: true   # cifras cuadran con snapshot
respeta_shape: true
respuesta_proviene_de_mcp: true
gap_detectado: false
notas: "Top 4 devuelto correctamente."
```

Y un **resumen ejecutivo** al final:

- Total preguntas
- % respondidas correctamente vía MCP
- Lista de gaps detectados (tools faltantes / intents faltantes en `onpe_chat`)
- Lista de inconsistencias entre tools (si X1-X6 fallan)
- Recomendaciones priorizadas

---

## 15. Apéndice — Ubigeos útiles

| Ámbito | Ubigeo |
|---|---|
| Lima dpto | `140000` |
| Lima provincia | `150100` (legacy) / `140100` |
| Callao dpto | `240000` |
| La Molina | `140110` |
| San Isidro | `140124` |
| Miraflores | `140122` (validar contra `ubicaciones_sv`) |
| Surco | `140131` (validar) |
| VES | `140143` (validar) |
| SJL | `140126` (validar) |
| Continente África | `910000` |
| Continente Américas | `920000` |
| Continente Europa | `940000` |
| Argentina (país exterior) | `920100` |
| Argelia (país exterior) | `910100` |

> El QA debe **resolver el ubigeo real** consultando `onpe_sv_resultados_geo(nombre=...)` antes de fijar pruebas con ubigeo. Los valores arriba son referenciales según el plan original.
