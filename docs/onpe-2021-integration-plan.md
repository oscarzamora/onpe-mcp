# Plan completo: integración de elecciones 2021 al MCP

## 1) Alcance funcional (todos los niveles de `peruvoto2021`)

Fuente: `https://github.com/oscarzamora/peruvoto2021` (CSV oficiales ONPE 2021).

Niveles cubiertos:

1. Nacional (1ra y 2da vuelta).
2. Departamento.
3. Provincia.
4. Distrito.
5. Mesa de votación.
6. Exterior (por país/ciudad cuando corresponda en la estructura UBIGEO 2021).

## 2) Modelo de datos MCP (SQLite)

Nuevas tablas:

- `mesas_2021`: cabecera por mesa/vuelta (geo, estado, electores, blancos/nulos/impugnados).
- `votos_2021`: votos por partido en cada mesa/vuelta.
- `partidos_2021`: diccionario partido/candidato por vuelta.

Bootstrap:

- `onpe_2021_bootstrap(force=False)` carga ambos CSV desde `ONPE_VOTO2021_ROOT`.

Chat:

- `onpe_2021_chat(query, vuelta=None)` responde consultas NL de 2021.
- `onpe_chat(...)` enruta a 2021 cuando detecta año `2021` en la consulta.

## 3) Banco de preguntas posibles (NL) para 2021

### Nacional

1. ¿Quién ganó la primera vuelta 2021?
2. ¿Quién ganó la segunda vuelta 2021?
3. Top 5 candidatos 2021 primera vuelta.
4. Top 2 2021 segunda vuelta.
5. ¿Cuántas mesas se contabilizaron en 2021?
6. ¿Cuántos votos emitidos hubo en 2021?
7. ¿Cuántos votos válidos hubo en 2021?
8. ¿Cuántos votos nulos hubo en 2021?
9. ¿Cuántos votos en blanco hubo en 2021?
10. ¿Cuántos votos impugnados hubo en 2021?

### Candidato/partido

1. ¿Cuántos votos obtuvo Pedro Castillo en 2021?
2. ¿Cuántos votos obtuvo Keiko Fujimori en 2021?
3. ¿Cuántos votos obtuvo Rafael López Aliaga en primera vuelta 2021?
4. ¿Cuántos votos sacó Perú Libre en 2021 segunda vuelta?
5. ¿Cuántos votos tuvo Fuerza Popular en 2021 segunda vuelta?
6. Votación de Acción Popular en 2021.
7. Votación de Renovación Popular en 2021.
8. ¿Qué puesto ocupó [candidato] en 2021?
9. ¿Cuál fue el total nacional de [partido] en 2021?
10. ¿Cómo le fue a [candidato] en 2021?

### Geográfico (departamento/provincia/distrito)

1. Top 5 en Lima 2021.
2. Top 5 en Cusco 2021.
3. Top 5 en Arequipa 2021.
4. Votos de Castillo en Puno 2021.
5. Votos de Keiko en La Libertad 2021.
6. Top 3 en provincia de Lima 2021.
7. Top 3 en distrito de Miraflores 2021.
8. ¿Quién ganó en [departamento] en 2021?
9. ¿Quién ganó en [provincia] en 2021?
10. ¿Quién ganó en [distrito] en 2021?

### Mesa

1. Resultado de la mesa 000001 en 2021.
2. Estado del acta de la mesa 000001 en 2021.
3. Electores hábiles de la mesa 000001 en 2021.
4. Votos válidos de la mesa 000001 en 2021.
5. Blancos/nulos/impugnados de la mesa 000001 en 2021.
6. Top de candidatos en mesa 000001 (2021).
7. Comparar mesa 000001 entre 1ra y 2da vuelta 2021.

### Comparativas 2021 vs 2026 (routing)

1. Compara top nacional 2021 vs 2026.
2. Compara votos de Keiko en 2021 y 2026.
3. Compara votos de López Aliaga 2021 vs 2026.
4. ¿Qué cambió entre 2021 y 2026 en Lima?
5. ¿Quién lideró 2021 y quién lidera 2026?

## 4) Plan de update MCP

1. Agregar bootstrap 2021.
2. Agregar chat 2021.
3. Agregar ruteo por año en `onpe_chat`.
4. Mantener comportamiento actual de 2026 sin regresión.
5. Cubrir con tests unitarios y NL.

## 5) Testing

- Test de storage 2021 (hidratación y consultas).
- 100 casos NL de detección de año/ruteo (2021/2026).
- Test de ruteo de `onpe_chat` hacia handler 2021.

## 6) Documentación

- README actualizado con herramientas 2021.
- `.env.example` actualizado con `ONPE_VOTO2021_ROOT`.
- Este documento como referencia de alcance/preguntas.

## 7) Mapeo de columnas y auto-rehydration (jun-2026)

### Diccionario `VOTOS_Pn → partido_id / candidato`

El orden de las columnas `VOTOS_Pn` en los CSV oficiales PCM **NO es alfabético** por nombre de partido; corresponde al orden de aparición en la **cédula electoral** (sorteo JNE). El mapeo definitivo, verificado por sum-matching contra los totales oficiales ONPE (86,488 mesas, total válidos 14,400,630), vive en `_PARTY_MAP_2021_1V` en [src/onpe_mcp/storage.py](../src/onpe_mcp/storage.py).

Referencia externa: [peruvoto2021/docs/CSV_PARTIDOS_CANDIDATOS.md](https://github.com/oscarzamora/peruvoto2021/blob/master/docs/CSV_PARTIDOS_CANDIDATOS.md).

| Columna | partido_id | Candidato |
|---|---|---|
| P1 | PNP | Ollanta Humala Tasso |
| P5 | VN  | George Forsyth Sommer |
| P6 | AP  | Yonhy Lescano Ancieta |
| P7 | AP2 | Hernando de Soto |
| P11 | K  | Keiko Fujimori Higuchi |
| P13 | RL | Rafael López Aliaga |
| P16 | PC | Pedro Castillo Terrones |
| P18 | APP | César Acuña Peralta |

(Tabla completa de los 18 partidos en el doc externo y en el código.)

### Auto-detección de cache obsoleto

`bootstrap_elecciones_2021()` calcula un **fingerprint SHA-256** sobre `_PARTY_MAP_2021_1V` + `_PARTY_MAP_2021_2V` y lo persiste en `sv_sync_meta(key='party_map_2021_fingerprint')` tras cada hidratación exitosa. En arranques posteriores:

1. Si el fingerprint del código **coincide** con el almacenado → skip (cache válido).
2. Si **no coincide** (ej. el usuario hizo pull de un fix al mapeo) → fuerza re-hidratación automática, sin necesidad de `force=True` ni borrado manual de la DB.

Esto evita el bug histórico en que la guarda `if c1 > 0 and c2 > 0: return skipped` dejaba datos incorrectos en silencio tras un cambio de mapeo.

Tests:
- `tests/test_storage_2021.py::test_bootstrap_2021_and_queries` — datos básicos.
- `tests/test_storage_2021.py::test_bootstrap_2021_auto_rehydrates_on_party_map_change` — verifica el fingerprint.

Script de validación manual: `scripts/_verify_2021_1v.py` (imprime top-18 desde SQLite para verificar contra ONPE/Wikipedia).
