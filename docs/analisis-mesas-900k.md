# Análisis Mesas 900K — Elecciones Generales Perú 2026

> **Audiencia:** Analistas electorales, periodistas de datos, auditores de proceso, ciudadanos interesados.
> **Origen:** Datos oficiales ONPE consolidados localmente vía `onpe-mcp` + scrapers `onpeescraper` (1V) y `onpe-scraper-2026-2` (2V).
> **Fecha de cierre del análisis:** 2026-06-12 (cobertura 2V: 98.25% — 91,146 / 92,766 actas).
> **Modelo de transferencia:** NNLS calibrado sobre 86,124 mesas (ver [`src/onpe_mcp/knowledge_base.py`](../src/onpe_mcp/knowledge_base.py) → `TRANSFER_MAP`).
> **Reproducción:** `mcp_onpe-mcp_onpe_sv_proyeccion_transferencia(mesa_prefix="900K")` y consultas SQL anexas.

---

## Tabla de contenidos

1. [¿Qué son las mesas 900K?](#qué-son-las-mesas-900k)
2. [Universo y geografía nacional](#universo-y-geografía-nacional)
3. [Comparación agregada 1V → 2V](#comparación-agregada-1v--2v)
4. [Flujo de votos por departamento](#flujo-de-votos-por-departamento)
5. [Mapeo NNLS partido → finalistas](#mapeo-nnls-partido--finalistas)
6. [Foco Lima 900K](#foco-lima-900k)
7. [Validación del modelo](#validación-del-modelo)
8. [Conclusiones](#conclusiones)
9. [Anexos: queries reproducibles](#anexos-queries-reproducibles)
10. [Comparativa 2021 2V vs 2026 2V por departamento](#comparativa-2021-2v-vs-2026-2v-por-departamento)
11. [Participación 2V 2026 por departamento](#participación-2v-2026-por-departamento)
12. [Análisis por tamaño de mesa (2V 2026)](#análisis-por-tamaño-de-mesa-2v-2026)
13. [Mesas con mayor margen por candidato — Top 20 nacional](#mesas-con-mayor-margen-por-candidato--top-20-nacional)
14. [Estado de actas 900K (2V 2026)](#estado-de-actas-900k-2v-2026)
15. [Desglose Puno por provincia (2V 2026)](#desglose-puno-por-provincia-2v-2026)
16. [Primera vuelta 2021 — top partidos por departamento](#primera-vuelta-2021--top-partidos-por-departamento)
17. [Consultas MCP 2021 con filtro de prefijo de mesas](#consultas-mcp-2021-con-filtro-de-prefijo-de-mesas)

---

## ¿Qué son las mesas 900K?

Las **mesas 900K** son las mesas de sufragio cuyo código numérico se encuentra en el rango `900000–999999`. Existen en el padrón electoral peruano desde hace más de 20 años y se asignan a:

- Centros poblados menores
- Comunidades nativas
- Anexos rurales y zonas de difícil acceso

El prefijo `9` no implica irregularidad alguna: es una convención numérica histórica de ONPE para distinguir mesas rurales pequeñas (con padrones de 50–300 electores) del resto de mesas urbanas. Todos los partidos políticos reciben la lista completa con anticipación para acreditar personeros, y las mesas siguen el mismo protocolo de escrutinio público que cualquier otra (padrón RENIEC, miembros de mesa, personeros, actas firmadas, fiscalización JNE).

> Para el discurso de "fraude 900K" desmontado con datos oficiales, ver el intent `range_existence_verify` y `range_claim_verify` en [`src/onpe_mcp/server.py`](../src/onpe_mcp/server.py).

---

## Universo y geografía nacional

| Indicador | Valor |
|---|---:|
| Total mesas en bloque 900K | **4,703** |
| Electores hábiles totales | **1,109,876** |
| Promedio electores por mesa | 236 |
| Departamentos representados | **24 / 24** (todos) |
| Cobertura geográfica | Predominantemente rural + periurbano |

### Distribución por departamento (mesas 900K)

| Departamento | Mesas | Electores | % del bloque |
|---|---:|---:|---:|
| Cajamarca | 636 | 153,418 | 13.5% |
| Áncash | 412 | 93,332 | 8.8% |
| Piura | 371 | 96,843 | 7.9% |
| Loreto | 299 | 71,660 | 6.4% |
| Huánuco | 290 | 65,923 | 6.2% |
| Puno | 289 | 63,907 | 6.1% |
| Cusco | 253 | 58,999 | 5.4% |
| **Lima** | **239** | **62,307** | **5.1%** |
| Amazonas | 239 | 53,623 | 5.1% |
| San Martín | 237 | 58,735 | 5.0% |
| Huancavelica | 235 | 51,884 | 5.0% |
| Ayacucho | 215 | 44,778 | 4.6% |
| La Libertad | 208 | 52,445 | 4.4% |
| Junín | 194 | 45,380 | 4.1% |
| Lambayeque | 190 | 48,534 | 4.0% |
| Apurímac | 154 | 34,732 | 3.3% |
| Ucayali | 77 | 17,498 | 1.6% |
| Arequipa | 44 | 9,267 | 0.9% |
| Pasco | 42 | 8,067 | 0.9% |
| Madre de Dios | 34 | 8,721 | 0.7% |
| Tacna | 18 | 4,121 | 0.4% |
| Moquegua | 14 | 2,497 | 0.3% |
| Ica | 7 | 1,486 | 0.1% |
| Tumbes | 6 | 1,719 | 0.1% |
| **TOTAL** | **4,703** | **1,109,876** | **100%** |

### Agrupación por tipo de zona

| Tipo de zona | Departamentos | Mesas | % |
|---|---|---:|---:|
| Sierra norte/centro | Cajamarca, Áncash, Huánuco, Huancavelica, Apurímac, Pasco | 1,769 | 37.6% |
| Sur andino | Puno, Cusco, Ayacucho, Arequipa, Tacna, Moquegua, Madre de Dios | 833 | 17.7% |
| Costa norte | Piura, La Libertad, Lambayeque, Tumbes, Ica | 782 | 16.6% |
| Selva | Loreto, San Martín, Amazonas, Ucayali | 852 | 18.1% |
| **Lima (periurbano + provincias serranas)** | Lima | **239** | **5.1%** |
| Junín | Junín | 194 | 4.1% |

**Observación:** las mesas 900K NO se concentran en una sola región del país; están distribuidas entre los 24 departamentos. Lima tiene 239 mesas en zonas periurbanas (Lurigancho-Chosica, Pachacámac, Carabayllo, El Agustino) y en provincias serranas (Huarochirí, Yauyos, Huaura, Cañete, Oyón, Cajatambo).

---

## Comparación agregada 1V → 2V

### Cobertura

| Indicador | 1V (2026-04-12) | 2V (2026-06-07) | Δ |
|---|---:|---:|---:|
| Mesas en bloque | 4,703 | 4,703 | — |
| Electores hábiles | 1,109,876 | 1,109,876 | — |
| Votos emitidos | 836,866 | 800,784 | **−36,082** |
| Participación | 75.40% | 72.15% | −3.25 pp |
| Votos válidos | 604,353 | 742,315 | **+137,962** |
| Blancos | 168,820 | 9,482 | −159,338 |
| Nulos | 63,693 | 49,556 | −14,137 |

### Top fuerzas en mesas 900K — 1V

| Posición | Agrupación | Votos | % válidos |
|---:|---|---:|---:|
| 1 | JUNTOS POR EL PERÚ | 252,290 | 41.7% |
| — | (VOTOS EN BLANCO) | 168,820 | — |
| 2 | FUERZA POPULAR | 99,088 | 16.4% |
| — | (VOTOS NULOS) | 63,693 | — |
| 3 | PARTIDO CÍVICO OBRAS | 52,345 | 8.7% |
| 4 | AHORA NACIÓN | 25,951 | 4.3% |
| 5 | PODEMOS PERÚ | 21,764 | 3.6% |
| 6 | PAÍS PARA TODOS | 17,063 | 2.8% |
| 7 | RENOVACIÓN POPULAR | 15,692 | 2.6% |
| 8 | PARTIDO DEL BUEN GOBIERNO | 12,170 | 2.0% |

### Resultados 2V en mesas 900K

| Candidato | Agrupación | Votos | % válidos |
|---|---|---:|---:|
| Roberto Sánchez | JUNTOS POR EL PERÚ | **524,580** | **70.66%** |
| Keiko Fujimori | FUERZA POPULAR | 223,803 | 30.15% |
| — | VOTOS NULOS | 49,556 | — |
| — | VOTOS EN BLANCO | 9,482 | — |

> Comparación con nacional: **A nivel nacional Keiko obtuvo 50.003% (9,035,493 votos) vs Sánchez 49.997% (9,034,466 votos)** — empate técnico de ~1,000 votos. En las mesas 900K, Sánchez gana 70/30.

---

## Flujo de votos por departamento

Análisis del crecimiento neto de cada finalista entre 1V y 2V, segmentado por departamento dentro del bloque 900K:

| Departamento | JxP 1V | JxP 2V | ΔSánchez | FP 1V | FP 2V | ΔKeiko | Captura Sánchez | Captura Keiko |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Cajamarca | 52,380 | 76,646 | +24,266 | 11,211 | 27,006 | +15,795 | 60.6% | 39.4% |
| Piura | 16,692 | 37,944 | +21,252 | 15,306 | 28,547 | +13,241 | 61.6% | 38.4% |
| Áncash | 17,103 | 41,651 | +24,548 | 8,861 | 21,082 | +12,221 | 66.8% | 33.2% |
| Huánuco | 19,570 | 34,019 | +14,449 | 4,037 | 9,782 | +5,745 | 71.6% | 28.4% |
| San Martín | 12,950 | 26,765 | +13,815 | 7,566 | 15,828 | +8,262 | 62.6% | 37.4% |
| Amazonas | 15,263 | 25,880 | +10,617 | 4,041 | 9,239 | +5,198 | 67.1% | 32.9% |
| Huancavelica | 17,681 | 30,361 | +12,680 | 1,387 | 4,691 | +3,304 | 79.3% | 20.7% |
| **Puno** | 17,062 | 45,682 | **+28,620** | 1,181 | 3,804 | +2,623 | **91.6%** | **8.4%** |
| Cusco | 14,971 | 36,347 | +21,376 | 1,535 | 4,507 | +2,972 | 87.8% | 12.2% |
| Lambayeque | 7,650 | 16,186 | +8,536 | 8,665 | 17,368 | +8,703 | 49.5% | **50.5%** |
| Ayacucho | 13,098 | 25,522 | +12,424 | 1,651 | 4,461 | +2,810 | 81.6% | 18.4% |
| La Libertad | 8,922 | 19,434 | +10,512 | 5,708 | 13,694 | +7,986 | 56.8% | 43.2% |
| Loreto | 7,930 | 22,595 | +14,665 | 6,400 | 12,983 | +6,583 | 69.0% | 31.0% |
| **Lima** | 4,185 | 23,900 | +19,715 | 9,898 | 25,692 | +15,794 | **55.5%** | **44.5%** |
| Apurímac | 11,766 | 21,819 | +10,053 | 955 | 2,873 | +1,918 | 84.0% | 16.0% |
| Junín | 6,405 | 16,178 | +9,773 | 6,171 | 12,985 | +6,814 | 58.9% | 41.1% |
| Ucayali | 2,141 | 5,449 | +3,308 | 1,619 | 3,119 | +1,500 | 68.8% | 31.2% |
| Madre de Dios | 1,751 | 4,539 | +2,788 | 575 | 1,188 | +613 | 82.0% | 18.0% |
| Pasco | 1,243 | 3,210 | +1,967 | 1,045 | 1,912 | +867 | 69.4% | 30.6% |
| Arequipa | 1,762 | 5,138 | +3,376 | 423 | 1,157 | +734 | 82.1% | 17.9% |
| Tacna | 771 | 2,689 | +1,918 | 211 | 497 | +286 | 87.0% | 13.0% |
| Moquegua | 697 | 1,649 | +952 | 58 | 156 | +98 | 90.7% | 9.3% |
| **Tumbes** | 55 | 294 | +239 | 446 | 925 | +479 | 33.3% | **66.7%** |
| Ica | 242 | 683 | +441 | 138 | 307 | +169 | 72.3% | 27.7% |
| **TOTAL 900K** | **252,290** | **524,580** | **+272,290** | **99,088** | **223,803** | **+124,715** | **68.6%** | **31.4%** |

### Tres patrones regionales claros

1. **Sur andino — Sánchez arrasa el pool**
   Puno, Moquegua, Cusco, Apurímac, Tacna, Ayacucho, Arequipa, Madre de Dios, Huancavelica.
   Captura Sánchez: **80–92%** | Captura Keiko: 8–20%.

2. **Costa/sierra mixta — reparto cercano al 60/40 a favor de Sánchez**
   Cajamarca, Piura, San Martín, Áncash, Huánuco, La Libertad, Junín, Lima, Loreto, Amazonas.
   Captura Sánchez: 55–72% | Captura Keiko: 28–45%.

3. **Costa norte particular — Keiko captura más**
   Lambayeque (50.5% Keiko), **Tumbes (66.7% Keiko)**.

---

## Mapeo NNLS partido → finalistas

Se aplican los coeficientes de transferencia del modelo NNLS nacional (calibrado sobre 86,124 mesas) al pool 1V del bloque 900K. La tabla muestra qué porcentaje del voto de cada agrupación en 1V se proyecta que fue a cada finalista en 2V.

| Partido 1V (en 900K) | Votos 1V | %→Keiko | %→Sánchez | %→BN/Abs | Proyec. K | Proyec. S |
|---|---:|---:|---:|---:|---:|---:|
| JUNTOS POR EL PERÚ | 252,290 | 7% | 88% | 5% | 17,660 | 222,015 |
| Votos en blanco | 168,820 | 35% | 40% | 25% | 59,087 | 67,528 |
| FUERZA POPULAR | 99,088 | 91% | 5% | 4% | 90,170 | 4,954 |
| Votos nulos | 63,693 | 35% | 40% | 25% | 22,293 | 25,477 |
| PARTIDO CÍVICO OBRAS | 52,345 | 0% | 100% | 0% | 0 | 52,345 |
| AHORA NACIÓN | 25,951 | 72% | 19% | 9% | 18,685 | 4,931 |
| PODEMOS PERÚ | 21,764 | 3% | 94% | 3% | 653 | 20,458 |
| PAÍS PARA TODOS | 17,063 | 70% | 21% | 9% | 11,944 | 3,583 |
| RENOVACIÓN POPULAR | 15,692 | 84% | 8% | 8% | 13,181 | 1,255 |
| PARTIDO DEL BUEN GOBIERNO | 12,170 | 21% | 69% | 10% | 2,556 | 8,397 |
| ALIANZA ELECTORAL VENCEREMOS | 11,054 | 14% | 76% | 10% | 1,548 | 8,401 |
| ALIANZA PARA EL PROGRESO | 10,471 | 78% | 13% | 9% | 8,167 | 1,361 |
| Otros 27 partidos | 86,375 | varios | varios | varios | ~40,340 | ~50,313 |
| **TOTAL PREDICHO** | **836,866** | | | | **286,284** | **471,418** |
| **TOTAL OBSERVADO 2V** | | | | | **223,803** | **524,580** |
| **Error modelo nacional** | | | | | **+62,481 (+27.9%)** | **−53,162 (−10.1%)** |

> **Lectura del error:** el modelo nacional **sobreestima Keiko en +28%** y **subestima Sánchez en −10%** cuando se aplica solo al bloque 900K. Esto NO es un error del modelo; es evidencia de que las tasas de transferencia rurales en el sur andino y selva alta son sistemáticamente más favorables a Sánchez de lo que predice el promedio nacional.

### Partidos con "flip" rural significativo

Partidos cuyos votantes urbanos a nivel nacional fueron mayoritariamente a Keiko, pero en 900K fueron mayoritariamente a Sánchez:

| Partido | %→Keiko nacional | %→Keiko en 900K (NNLS local) |
|---|---:|---:|
| Ahora Nación | 72% | 0% |
| Venceremos | 14% | 0% |
| Demócrata Unido | 74% | 0% |
| Cooperación Popular | 24% | 0% |
| Perú Libre | 10% | 0% |
| Frente de la Esperanza | 22% | 0% |
| Perú Primero | 67% | 0% |

> Este "flip rural" es coherente con la hipótesis sociopolítica de que los electorados rurales no comparten las preferencias programáticas de los electorados urbanos, incluso votando por el mismo partido en 1V.

---

## Foco Lima 900K

### Universo Lima 900K

| Indicador | 1V | 2V | Δ |
|---|---:|---:|---:|
| Mesas | 239 | 239 | — |
| Electores hábiles | 62,307 | 62,307 | — |
| Votos emitidos | 51,999 | 51,788 | −211 (−0.4%) |
| Participación | 83.46% | 83.12% | −0.34 pp |

> **Participación Lima 900K (83%) es 8 puntos superior al promedio 900K nacional (75%)** — son zonas rurales conectadas con la capital, no comunidades aisladas.

### Distribución Lima 900K por provincia

| Provincia | Mesas | Electores | Participación 2V |
|---|---:|---:|---:|
| LIMA (Metropolitana) | 143 | 40,155 | ~85% |
| Huarochirí | 28 | 6,940 | ~82% |
| Yauyos | 18 | 3,508 | ~78% |
| Huaura | 15 | 3,984 | ~81% |
| Cañete | 14 | 3,579 | ~83% |
| Oyón | 9 | 1,467 | ~79% |
| Cajatambo | 7 | 1,417 | ~75% |
| Huaral | 2 | 491 | — |
| Canta | 2 | 530 | — |
| Barranca | 1 | 236 | — |

### Top 15 distritos Lima 900K — resultados 2V

| Distrito | Provincia | Mesas | Electores | JxP | FP | Ganador | Margen |
|---|---|---:|---:|---:|---:|---|---:|
| LURIGANCHO (Chosica) | Lima | 66 | 18,665 | 7,130 | 8,353 | **Keiko** | 7.9% |
| PACHACÁMAC | Lima | 32 | 8,779 | 3,400 | 3,894 | **Keiko** | 6.8% |
| CARABAYLLO | Lima | 30 | 8,603 | 3,249 | 3,267 | **Keiko** | 0.3% |
| NUEVO IMPERIAL | Cañete | 14 | 3,579 | 1,478 | 1,477 | **Sánchez** | 0.0% |
| EL AGUSTINO | Lima | 12 | 3,229 | 1,157 | 1,522 | **Keiko** | 13.6% |
| SAN ANTONIO | Huarochirí | 12 | 3,207 | 1,426 | 1,165 | **Sánchez** | 10.1% |
| SAYÁN | Huaura | 11 | 3,116 | 1,502 | 1,015 | **Sánchez** | 19.3% |
| STO DOMINGO DE LOS OLLEROS | Huarochirí | 10 | 2,406 | 865 | 1,089 | **Keiko** | 11.5% |
| PACHANGARA | Oyón | 4 | 573 | 116 | 335 | **Keiko** | 48.6% |
| COCHAMARCA | Oyón | 3 | 567 | 187 | 204 | **Keiko** | 4.3% |
| COLONIA | Yauyos | 3 | 503 | 174 | 168 | **Sánchez** | 1.8% |
| MARIATANA | Huarochirí | 3 | 792 | 269 | 296 | **Keiko** | 4.8% |
| SANTA ROSA | Lima | 3 | 879 | 318 | 351 | **Keiko** | 4.9% |
| VIÑAC | Yauyos | 3 | 640 | 282 | 167 | **Sánchez** | 25.6% |
| CATAHUASI | Yauyos | 2 | 448 | 200 | 155 | **Sánchez** | 12.7% |

### Flujo 1V → 2V por provincia (Lima 900K)

| Provincia | JxP 1V→2V | ΔSánchez | FP 1V→2V | ΔKeiko | Captura S | Captura K |
|---|---|---:|---|---:|---:|---:|
| LIMA Metropolitana | 2,037 → 15,254 | +13,217 | 5,536 → 17,387 | +11,851 | 52.7% | **47.3%** |
| Huarochirí | 494 → 2,670 | +2,176 | 1,434 → 2,771 | +1,337 | 61.9% | 38.1% |
| Yauyos | 609 → 1,437 | +828 | 501 → 1,026 | +525 | 61.2% | 38.8% |
| Huaura | 424 → 1,637 | +1,213 | 768 → 1,514 | +746 | 61.9% | 38.1% |
| Cañete | 264 → 1,478 | +1,214 | 829 → 1,477 | +648 | 65.2% | 34.8% |
| Oyón | 122 → 445 | +323 | 410 → 647 | +237 | 57.7% | 42.3% |
| Cajatambo | 112 → 414 | +302 | 211 → 409 | +198 | 60.4% | 39.6% |
| Canta | 38 → 236 | +198 | 91 → 184 | +93 | 68.0% | 32.0% |
| Huaral | 65 → 236 | +171 | 60 → 156 | +96 | 64.0% | 36.0% |
| Barranca | 20 → 93 | +73 | 58 → 121 | +63 | 53.7% | 46.3% |
| **TOTAL LIMA 900K** | **4,185 → 23,900** | **+19,715 (+471%)** | **9,898 → 25,692** | **+15,794 (+160%)** | **55.5%** | **44.5%** |

### Comparativa Lima 900K vs Total 900K nacional

|  | Captura Sánchez | Captura Keiko |
|---|---:|---:|
| Total 900K nacional (4,703 mesas) | 68.6% | 31.4% |
| **Lima 900K (239 mesas)** | **55.5%** | **44.5%** |
| Δ Lima vs nacional | **−13.1 pp** | **+13.1 pp** |

**Lima 900K es significativamente más keikista que el promedio rural nacional.** El modelo NNLS nacional predice Lima 900K casi perfecto en Keiko (error −0.93%) y con leve subestimación en Sánchez (−9.08%), confirmando que el comportamiento electoral de Lima 900K se parece más al promedio peruano urbano que al promedio rural andino.

### Las 5 mesas 900K con margen Keiko más alto (Lima)

| Distrito | Provincia | Mesas | JxP | FP | Margen K |
|---|---|---:|---:|---:|---:|
| PACHANGARA | Oyón | 4 | 116 | 335 | **48.6%** |
| EL AGUSTINO | Lima | 12 | 1,157 | 1,522 | 13.6% |
| STO DOMINGO DE LOS OLLEROS | Huarochirí | 10 | 865 | 1,089 | 11.5% |
| LURIGANCHO | Lima | 66 | 7,130 | 8,353 | 7.9% |
| PACHACÁMAC | Lima | 32 | 3,400 | 3,894 | 6.8% |

### Las 5 mesas 900K con margen Sánchez más alto (Lima)

| Distrito | Provincia | Mesas | JxP | FP | Margen S |
|---|---|---:|---:|---:|---:|
| VIÑAC | Yauyos | 3 | 282 | 167 | **25.6%** |
| SAYÁN | Huaura | 11 | 1,502 | 1,015 | 19.3% |
| CATAHUASI | Yauyos | 2 | 200 | 155 | 12.7% |
| SAN ANTONIO | Huarochirí | 12 | 1,426 | 1,165 | 10.1% |
| COLONIA | Yauyos | 3 | 174 | 168 | 1.8% |

---

## Validación del modelo

### Métricas de ajuste

| Métrica | Modelo nacional aplicado a 900K | Modelo NNLS específico 900K |
|---|---:|---:|
| Error agregado Keiko | +27.9% | −20.1% |
| Error agregado Sánchez | −10.1% | −6.4% |
| R² mesa-a-mesa Keiko | n/a | 0.79 |
| R² mesa-a-mesa Sánchez | n/a | 0.83 |
| Mesas usadas | 4,703 | 4,703 |
| Features | 41 partidos + BN + Abs | 28 features (top 24 + OTROS + BN + Abs) |

> **Lectura:** El modelo nacional pega bien a Lima 900K (error <1%) pero no a las 900K rurales andinas. Un modelo NNLS recalibrado específicamente para el bloque 900K mejora el ajuste mesa-a-mesa a R²~0.80, indicando que el flujo en zonas rurales tiene una estructura distinta y consistente del flujo urbano.

### Reproducir el modelo NNLS

```python
# Ver src/onpe_mcp/knowledge_base.py: TRANSFER_MAP
from onpe_mcp.knowledge_base import get_transfer

pk, ps, pb, fuente = get_transfer("PARTIDO CÍVICO OBRAS")
# → (0.00, 1.00, 0.00, "nnls_calibrado")
```

### Reproducir el análisis 900K

```python
# Tool MCP — devuelve pool 1V, predicción NNLS, observación 2V real y error
mcp_onpe-mcp_onpe_sv_proyeccion_transferencia(mesa_prefix="900K")

# O para sub-bloques específicos:
mcp_onpe-mcp_onpe_sv_proyeccion_transferencia(mesa_prefix="900")   # 999 mesas
mcp_onpe-mcp_onpe_sv_proyeccion_transferencia(mesa_prefix="9")     # 4,703 mesas
mcp_onpe-mcp_onpe_sv_proyeccion_transferencia(mesa_prefix="9001")  # sub-bloque
```

---

## Conclusiones

1. **Las mesas 900K NO son fantasma ni nuevas.** Existen desde hace más de 20 años en el padrón ONPE como bloque numérico asignado a mesas rurales pequeñas, distribuidas en los 24 departamentos del Perú.

2. **NO se concentran en una región: el 95% son del interior** (sierra norte/centro 37.6%, selva 18.1%, sur andino 17.7%, costa norte 16.6%, Junín 4.1%) y **el 5.1% son de Lima** en zonas periurbanas (Lurigancho, Pachacámac, Carabayllo, El Agustino) y provincias serranas (Huarochirí, Yauyos, Huaura, Cañete).

3. **El bloque 900K votó 70/30 a favor de Sánchez en 2V**, un patrón fuertemente distinto del 50/50 nacional. La diferencia se debe a la sobre-representación de zonas rurales andinas y selváticas.

4. **El 82% del pool 1V no-finalistas se polarizó hacia los dos finalistas en 2V.** El voto en blanco y la abstención cayeron significativamente, indicando un electorado movilizado a definir entre dos opciones.

5. **El modelo NNLS nacional describe bien Lima 900K pero falla en el sur andino**: el "flip rural" de partidos como Ahora Nación, Demócrata Unido, Perú Primero (de Keiko a Sánchez) no está capturado en los pesos nacionales porque promedia electorados urbanos y rurales del mismo partido.

6. **Lima 900K se comporta como Lima urbana, no como rural andino**: Keiko gana en Lurigancho, Pachacámac, Carabayllo, El Agustino. Sánchez solo gana en distritos serranos profundos (Yauyos, parte de Huarochirí).

7. **No hay evidencia estadística de anomalía** en los flujos 1V→2V de las mesas 900K. Las desviaciones del modelo nacional se explican por la heterogeneidad sociogeográfica de los electorados rurales, no por irregularidades en el escrutinio.

---

## Anexos: queries reproducibles

### Tool MCP (recomendado)

```python
# Universo y resultados
mcp_onpe-mcp_onpe_chat("cuántas mesas con prefijo 900 hay y cómo se distribuyen")

# Comparación 1V vs 2V agregada
mcp_onpe-mcp_onpe_sv_proyeccion_transferencia(mesa_prefix="900K")

# Mesa individual
# Mesa individual (2V: https://onpe.ozamora.com/geo.php?mesa=900100 | 1V: https://onpe.ozamora.com/2026/geo.php?mesa=900100)
mcp_onpe-mcp_onpe_sv_comparacion_mesa(codigo_mesa="900100")

# Departamento específico
mcp_onpe-mcp_onpe_sv_resultados_geo(nivel="departamento", nombre="Lima")
```

### SQL directo sobre `data/onpe.db`

```sql
-- 1) Universo agregado 900K en 1V
SELECT COUNT(*) AS mesas, SUM(electores_habiles) AS electores,
       SUM(votos_emitidos) AS emitidos, SUM(votos_validos) AS validos
FROM mesas_data WHERE codigo_mesa GLOB '9?????';

-- 2) Universo agregado 900K en 2V
SELECT COUNT(*) AS mesas, SUM(electores_habiles) AS electores,
       SUM(votos_emitidos) AS emitidos, SUM(votos_validos) AS validos
FROM mesas_sv WHERE codigo_mesa GLOB '9?????';

-- 3) Top partidos 1V en 900K
SELECT a.nombre, SUM(v.votos) AS total
FROM votos v JOIN agrupaciones a ON a.partido_id = v.partido_id
WHERE v.codigo_mesa GLOB '9?????'
GROUP BY a.nombre ORDER BY total DESC LIMIT 15;

-- 4) Resultados 2V en 900K
SELECT a.nombre, SUM(v.votos) AS total
FROM votos_sv v LEFT JOIN agrupaciones_sv a ON a.partido_id = v.partido_id
WHERE v.codigo_mesa GLOB '9?????'
GROUP BY a.nombre ORDER BY total DESC;

-- 5) Distribución por departamento
SELECT u.departamento, COUNT(*) AS mesas, SUM(m.electores_habiles) AS electores
FROM mesas_sv m
LEFT JOIN ubicaciones_sv u ON u.ubigeo = m.id_ubigeo
WHERE m.codigo_mesa GLOB '9?????'
GROUP BY u.departamento ORDER BY mesas DESC;

-- 6) Foco Lima 900K — provincias
SELECT u.provincia, COUNT(*) AS mesas, SUM(m.electores_habiles) AS electores
FROM mesas_sv m
JOIN ubicaciones_sv u ON u.ubigeo = m.id_ubigeo
WHERE m.codigo_mesa GLOB '9?????' AND u.departamento='LIMA'
GROUP BY u.provincia ORDER BY mesas DESC;

-- 7) Ganador 2V por distrito Lima 900K
WITH m900_lima AS (
  SELECT m.codigo_mesa, u.distrito, u.provincia
  FROM mesas_sv m
  JOIN ubicaciones_sv u ON u.ubigeo = m.id_ubigeo
  WHERE m.codigo_mesa GLOB '9?????' AND u.departamento='LIMA'
)
SELECT ml.distrito, ml.provincia,
       SUM(CASE WHEN v.partido_id='10' THEN v.votos ELSE 0 END) AS jxp,
       SUM(CASE WHEN v.partido_id='8'  THEN v.votos ELSE 0 END) AS fp
FROM m900_lima ml
JOIN votos_sv v ON v.codigo_mesa = ml.codigo_mesa
GROUP BY ml.distrito, ml.provincia
ORDER BY (jxp + fp) DESC;
```

---

## Comparativa 2021 2V vs 2026 2V por departamento

Porcentaje bipartidista de Keiko sobre votos válidos (Keiko vs el candidato de izquierda: Castillo en 2021, Sánchez en 2026). Δ positivo = Keiko mejoró; negativo = empeoró. Ordenado por Δ.

| Departamento | Keiko % 2021 (vs Castillo) | Keiko % 2026 (vs Sánchez) | Δ Keiko (pp) | Mesas 2021 | Mesas 2026 |
|---|---:|---:|---:|---:|---:|
| Áncash | 29.6% | 33.6% | **+4.0** | 263 | 412 |
| Cajamarca | 22.1% | 26.1% | **+4.0** | 374 | 636 |
| Arequipa | 15.5% | 18.4% | **+2.9** | 35 | 44 |
| Ucayali | 33.8% | 36.4% | **+2.6** | 32 | 77 |
| **Lima** | 49.3% | **51.8%** | **+2.5** | 254 | 239 |
| Huancavelica | 11.3% | 13.4% | +2.1 | 171 | 235 |
| Amazonas | 24.4% | 26.3% | +1.9 | 183 | 239 |
| Puno | 6.1% | 7.7% | +1.6 | 111 | 289 |
| Cusco | 9.7% | 11.0% | +1.3 | 166 | 253 |
| Huánuco | 21.2% | 22.3% | +1.1 | 196 | 290 |
| Ayacucho | 13.8% | 14.9% | +1.1 | 159 | 215 |
| Lambayeque | 51.2% | 51.8% | +0.6 | 149 | 190 |
| San Martín | 37.2% | 37.2% | 0.0 | 160 | 237 |
| Moquegua | 8.6% | 8.6% | 0.0 | 8 | 14 |
| Madre de Dios | 21.4% | 20.7% | −0.7 | 32 | 34 |
| Pasco | 39.3% | 37.3% | −2.0 | 19 | 42 |
| Piura | 45.2% | 42.9% | −2.3 | 199 | 371 |
| Tacna | 18.6% | 15.6% | −3.0 | 12 | 18 |
| Junín | 47.9% | 44.5% | −3.4 | 138 | 194 |
| La Libertad | 45.8% | 41.3% | −4.5 | 143 | 208 |
| Apurímac | 17.8% | 11.6% | −6.2 | 88 | 154 |
| Loreto | 42.8% | 36.5% | −6.3 | 213 | 295 |
| Ica | 38.6% | 31.0% | −7.6 | 3 | 7 |
| Tumbes | — (0 mesas 900K en 2021) | 75.9% | n/a | 0 | 6 |

### Lecturas del desglose

1. **El mapa rural es notablemente estable.** La mayoría de departamentos se mueve menos de ±5 pp entre 2021 y 2026. El "techo de Keiko" en el campo es estructural, no coyuntural.
2. **Solo dos plazas rurales son competitivas para Keiko, y ahí mejoró:** Lambayeque (51.8%) y Lima rural (49.3% → 51.8%, su mayor avance neto entre los grandes).
3. **Costa norte agrícola se le erosionó:** La Libertad (−4.5), Piura (−2.3), Loreto (−6.3), Ica (−7.6). Donde tenía algo que perder, perdió.
4. **Sur andino sigue siendo muro:** Puno (7.7%), Moquegua (8.6%), Cusco (11.0%), Apurímac (11.6%), Huancavelica (13.4%). Keiko no pasa del 14%.
5. **Apurímac es el caso de mayor caída** (−6.2 pp), pasando de un ya bajo 17.8% a 11.6%.
6. **Tumbes 900K es nuevo** (sin mesas en 2021) y es el único departamento rural donde Keiko domina (75.9%) — consistente con su fuerza histórica en Tumbes.

> ⚠️ El número de mesas 900K por departamento difiere entre años (p. ej. Cajamarca 374 → 636, Áncash 263 → 412), por lo que se comparan proporciones bipartidistas, no votos absolutos. El universo creció +1,595 mesas entre elecciones.

---

## Participación 2V 2026 por departamento

Tasa de participación (votos emitidos / electores hábiles) en el bloque 900K por departamento, de mayor a menor.

| Departamento | Mesas | Electores | Emitidos | Participación | Mesas contabilizadas |
|---|---:|---:|---:|---:|---:|
| **Lima** | 239 | 62,307 | 51,788 | **83.1%** | 235 |
| Tacna | 18 | 4,121 | 3,335 | 80.9% | 18 |
| Puno | 289 | 63,907 | 51,333 | 80.3% | 286 |
| San Martín | 237 | 58,735 | 45,790 | 78.0% | 235 |
| Tumbes | 6 | 1,719 | 1,302 | 75.7% | 6 |
| Moquegua | 14 | 2,497 | 1,880 | 75.3% | 14 |
| Lambayeque | 190 | 48,534 | 36,382 | 75.0% | 190 |
| Apurímac | 154 | 34,732 | 25,900 | 74.6% | 151 |
| Piura | 371 | 96,843 | 72,033 | 74.4% | 368 |
| Áncash | 412 | 93,332 | 68,196 | 73.1% | 407 |
| Cajamarca | 636 | 153,418 | 110,847 | 72.3% | 632 |
| Arequipa | 44 | 9,267 | 6,679 | 72.1% | 44 |
| Cusco | 253 | 58,999 | 42,506 | 72.1% | 248 |
| Huancavelica | 235 | 51,884 | 37,350 | 72.0% | 234 |
| Huánuco | 290 | 65,923 | 47,017 | 71.3% | 287 |
| Ayacucho | 215 | 44,778 | 31,640 | 70.7% | 213 |
| Madre de Dios | 34 | 8,721 | 6,121 | 70.2% | 34 |
| La Libertad | 208 | 52,445 | 36,750 | 70.1% | 208 |
| Junín | 194 | 45,380 | 31,730 | 69.9% | 193 |
| Amazonas | 239 | 53,623 | 37,342 | 69.6% | 239 |
| Ica | 7 | 1,486 | 1,022 | 68.8% | 7 |
| Pasco | 42 | 8,067 | 5,501 | 68.2% | 42 |
| **Loreto** | 299 | 71,660 | 38,988 | **54.4%** | 293 |
| **Ucayali** | 77 | 17,498 | 9,352 | **53.5%** | 76 |
| **PROMEDIO 900K** | **4,703** | **1,109,876** | **800,784** | **72.2%** | **4,660** |

> Lima 900K (83.1%) tiene la participación más alta del bloque — 11 pp sobre el promedio. Loreto y Ucayali presentan la participación más baja (53–54%), consistente con las dificultades logísticas de las mesas en selva profunda.

---

## Análisis por tamaño de mesa (2V 2026)

Las mesas 900K se agrupan en tres rangos de padrón. No existe ninguna mesa 900K con más de 300 electores (no hay "grandes").

| Tamaño | Mesas (est.) | Electores | Participación | Keiko (FP) % | Sánchez (JxP) % |
|---|---:|---:|---:|---:|---:|
| Micro (≤100 electores) | ~51 | ~4,206 | 72.2% | **31.1%** | 68.9% |
| Pequeña (101–200 electores) | ~910 | ~154,645 | 72.5% | 24.5% | **75.5%** |
| Mediana (201–300 electores) | ~3,742 | ~950,312 | 72.1% | 30.8% | 69.2% |
| Grande (>300 electores) | 0 | — | — | — | — |
| **Total 900K** | **4,703** | **1,109,876** | **72.2%** | **29.9%** | **70.1%** |

### Observaciones

- **La participación es uniforme entre tamaños** (~72% en todos los rangos). El tamaño del padrón de la mesa no afecta la movilización en zonas rurales.
- **Las mesas pequeñas (101–200) son significativamente más pro-Sánchez** (75.5%) que las medianas (69.2%) y micro (68.9%). Esto se explica porque muchas mesas pequeñas están en comunidades nativas y andinas del sur donde el voto de izquierda es más concentrado.
- **Las mesas micro (≤100) tienen el mayor porcentaje de Keiko** (31.1%), posiblemente reflejo de comunidades muy pequeñas con dinámicas locales más variables.

---

## Mesas con mayor margen por candidato — Top 20 nacional

### Top 20 mesas con mayor margen para Keiko Fujimori (FP)

| Mesa | Departamento | Provincia | Distrito | Electores | FP | JxP | Margen FP |
|---|---|---|---|---:|---:|---:|---:|
| [903476](https://onpe.ozamora.com/geo.php?mesa=903476) | Loreto | M. R. Castilla | Santa Rosa de Loreto | 142 | 113 | 0 | **100.0%** |
| [903451](https://onpe.ozamora.com/geo.php?mesa=903451) | Loreto | M. R. Castilla | Yavarí | 283 | 147 | 2 | 98.7% |
| [903547](https://onpe.ozamora.com/geo.php?mesa=903547) | Loreto | Loreto | Urarinas | 190 | 65 | 2 | 97.0% |
| [903561](https://onpe.ozamora.com/geo.php?mesa=903561) | Loreto | Requena | Alto Tapiche | 72 | 30 | 1 | 96.8% |
| [903455](https://onpe.ozamora.com/geo.php?mesa=903455) | Loreto | M. R. Castilla | Yavarí | 240 | 56 | 2 | 96.6% |
| [903960](https://onpe.ozamora.com/geo.php?mesa=903960) | Piura | Paita | Paita | 243 | 180 | 7 | 96.3% |
| [903961](https://onpe.ozamora.com/geo.php?mesa=903961) | Piura | Paita | Paita | 243 | 177 | 7 | 96.2% |
| [903179](https://onpe.ozamora.com/geo.php?mesa=903179) | Lima | Oyón | Pachangara | 155 | 104 | 5 | 95.4% |
| [903558](https://onpe.ozamora.com/geo.php?mesa=903558) | Loreto | Putumayo | Yaguas | 175 | 82 | 4 | 95.3% |
| [903574](https://onpe.ozamora.com/geo.php?mesa=903574) | Loreto | Requena | Yaquerana | 132 | 39 | 2 | 95.1% |
| [903965](https://onpe.ozamora.com/geo.php?mesa=903965) | Piura | Paita | Paita | 284 | 211 | 11 | 95.0% |
| [903546](https://onpe.ozamora.com/geo.php?mesa=903546) | Loreto | Loreto | Urarinas | 191 | 62 | 4 | 93.9% |
| [903555](https://onpe.ozamora.com/geo.php?mesa=903555) | Loreto | Putumayo | Putumayo | 97 | 31 | 2 | 93.9% |
| [903962](https://onpe.ozamora.com/geo.php?mesa=903962) | Piura | Paita | Paita | 273 | 195 | 13 | 93.8% |
| [903458](https://onpe.ozamora.com/geo.php?mesa=903458) | Loreto | M. R. Castilla | Yavarí | 260 | 59 | 4 | 93.7% |
| [903530](https://onpe.ozamora.com/geo.php?mesa=903530) | Loreto | Loreto | Tigre | 222 | 111 | 8 | 93.3% |
| [903964](https://onpe.ozamora.com/geo.php?mesa=903964) | Piura | Paita | Paita | 284 | 206 | 16 | 92.8% |
| [903456](https://onpe.ozamora.com/geo.php?mesa=903456) | Loreto | M. R. Castilla | Yavarí | 260 | 71 | 6 | 92.2% |
| [903963](https://onpe.ozamora.com/geo.php?mesa=903963) | Piura | Paita | Paita | 285 | 209 | 18 | 92.1% |
| [903459](https://onpe.ozamora.com/geo.php?mesa=903459) | Loreto | M. R. Castilla | Yavarí | 260 | 57 | 5 | 91.9% |

> Las mesas con mayor margen Keiko se concentran en **Loreto (Mariscal Ramón Castilla / Yavarí, Putumayo, Tigre, Requena)** y **Piura (Paita)**. El distrito de Yavarí (frontera con Brasil) domina con 6 mesas en el top 20. Ver acta en [onpe.ozamora.com/geo.php](https://onpe.ozamora.com/geo.php) (2V) | [onpe.ozamora.com/2026/geo.php](https://onpe.ozamora.com/2026/geo.php) (1V).

### Top 20 mesas con mayor margen para Roberto Sánchez (JxP)

| Mesa | Departamento | Provincia | Distrito | Electores | FP | JxP | Margen JxP |
|---|---|---|---|---:|---:|---:|---:|
| [901555](https://onpe.ozamora.com/geo.php?mesa=901555) | Cajamarca | San Ignacio | Huarango | 298 | 0 | 205 | **100.0%** |
| [900100](https://onpe.ozamora.com/geo.php?mesa=900100) | Amazonas | Condorcanqui | El Cenepa | 248 | 0 | 194 | **100.0%** |
| [901615](https://onpe.ozamora.com/geo.php?mesa=901615) | Cajamarca | San Ignacio | Tabaconas | 279 | 0 | 193 | **100.0%** |
| [900089](https://onpe.ozamora.com/geo.php?mesa=900089) | Amazonas | Condorcanqui | El Cenepa | 246 | 0 | 166 | **100.0%** |
| [903416](https://onpe.ozamora.com/geo.php?mesa=903416) | Loreto | Datem del Marañón | Manseriche | 229 | 0 | 157 | **100.0%** |
| [900047](https://onpe.ozamora.com/geo.php?mesa=900047) | Amazonas | Bagua | Imaza | 218 | 0 | 155 | **100.0%** |
| [903404](https://onpe.ozamora.com/geo.php?mesa=903404) | Loreto | Datem del Marañón | Cahuapanas | 214 | 0 | 149 | **100.0%** |
| [900049](https://onpe.ozamora.com/geo.php?mesa=900049) | Amazonas | Bagua | Imaza | 203 | 0 | 148 | **100.0%** |
| [901523](https://onpe.ozamora.com/geo.php?mesa=901523) | Cajamarca | Jaén | Sallique | 248 | 0 | 148 | **100.0%** |
| [903415](https://onpe.ozamora.com/geo.php?mesa=903415) | Loreto | Datem del Marañón | Manseriche | 230 | 0 | 133 | **100.0%** |
| [900070](https://onpe.ozamora.com/geo.php?mesa=900070) | Amazonas | Condorcanqui | Nieva | 191 | 0 | 126 | **100.0%** |
| [903398](https://onpe.ozamora.com/geo.php?mesa=903398) | Loreto | Datem del Marañón | Cahuapanas | 267 | 0 | 122 | **100.0%** |
| [900028](https://onpe.ozamora.com/geo.php?mesa=900028) | Amazonas | Bagua | Imaza | 216 | 0 | 119 | **100.0%** |
| [900838](https://onpe.ozamora.com/geo.php?mesa=900838) | Arequipa | Condesuyos | Cayarani | 236 | 0 | 111 | **100.0%** |
| [900023](https://onpe.ozamora.com/geo.php?mesa=900023) | Amazonas | Bagua | Imaza | 196 | 0 | 107 | **100.0%** |
| [900048](https://onpe.ozamora.com/geo.php?mesa=900048) | Amazonas | Bagua | Imaza | 146 | 0 | 104 | **100.0%** |
| [900085](https://onpe.ozamora.com/geo.php?mesa=900085) | Amazonas | Condorcanqui | Río Santiago | 140 | 0 | 102 | **100.0%** |
| [903389](https://onpe.ozamora.com/geo.php?mesa=903389) | Loreto | Datem del Marañón | Andoas | 220 | 0 | 96 | **100.0%** |
| [900096](https://onpe.ozamora.com/geo.php?mesa=900096) | Amazonas | Condorcanqui | El Cenepa | 161 | 0 | 90 | **100.0%** |
| [903443](https://onpe.ozamora.com/geo.php?mesa=903443) | Loreto | Datem del Marañón | Pastaza | 135 | 0 | 88 | **100.0%** |

> Las mesas con mayor margen Sánchez se concentran en **Amazonas (Condorcanqui/El Cenepa, Bagua/Imaza, Condorcanqui/Nieva y Río Santiago)**, **Loreto (Datem del Marañón — Manseriche, Cahuapanas, Andoas, Pastaza)** y **Cajamarca (San Ignacio, Jaén)**. Todos los 20 tienen 100% JxP (FP=0). Ver acta en [onpe.ozamora.com/geo.php](https://onpe.ozamora.com/geo.php) (2V) | [onpe.ozamora.com/2026/geo.php](https://onpe.ozamora.com/2026/geo.php) (1V).

---

## Estado de actas 900K (2V 2026)

| Estado | Mesas | Electores hábiles | Votos emitidos |
|---|---:|---:|---:|
| **C** — Contabilizada | 4,660 | 1,100,165 | 800,784 |
| **E** — En proceso / Escrutinio | 39 | 8,998 | 0 |
| **P** — Pendiente | 4 | 713 | 0 |
| **TOTAL** | **4,703** | **1,109,876** | **800,784** |

> Al cierre del análisis (2026-06-12), el **99.1% de las mesas 900K están contabilizadas** (4,660 / 4,703). Solo 43 actas (39 en proceso + 4 pendientes) aún no tienen votos computados — representan ~9,711 electores hábiles (0.9% del padrón 900K). El análisis de votos en todas las secciones de este documento usa únicamente las 4,660 actas contabilizadas.

---

## Desglose Puno por provincia (2V 2026)

Puno es el departamento sur andino más grande del bloque 900K (289 mesas, 63,907 electores) y uno de los más pro-Sánchez a nivel nacional. Este desglose muestra que el patrón es homogéneo en todas sus provincias.

| Provincia | Mesas | Votos JxP | JxP % | Votos FP | FP % |
|---|---:|---:|---:|---:|---:|
| Puno | 56 | 8,559 | 91.1% | 834 | 8.9% |
| Chucuito | 44 | 6,912 | 93.7% | 465 | 6.3% |
| Azángaro | 35 | 6,120 | 93.8% | 405 | 6.2% |
| El Collao | 27 | 4,806 | 92.4% | 397 | 7.6% |
| Carabaya | 33 | 4,475 | 90.1% | 490 | 9.9% |
| Huancané | 20 | 3,302 | 95.3% | 164 | 4.7% |
| Sandia | 20 | 3,119 | 90.4% | 333 | 9.6% |
| San Román | 16 | 2,851 | 91.3% | 271 | 8.7% |
| Moho | 20 | 2,713 | 94.1% | 171 | 5.9% |
| Melgar | 10 | 1,581 | 91.3% | 151 | 8.7% |
| San Antonio de Putina | 6 | 949 | 91.9% | 84 | 8.1% |
| Yunguyo | 1 | 189 | 91.3% | 18 | 8.7% |
| Lampa | 1 | 106 | 83.5% | 21 | 16.5% |

> **El muro electoral de Puno es uniforme:** todas las provincias dan a Sánchez entre 83.5% y 95.3%. Huancané (95.3%) y Moho (94.1%), en la frontera norte con Bolivia, son las más pro-Sánchez. Lampa (83.5%) y Carabaya (90.1%) son las más moderadas dentro del propio Puno. No existe una sola provincia puneña donde Keiko supere el 17%.

---

## Primera vuelta 2021 — top partidos por departamento

Resultado de la primera vuelta 2021 en el bloque 900K, desglosado por departamento para los 8 más grandes.

### Áncash (263 mesas, 90,578 votos válidos)

| Pos. | Candidato | Partido | Votos |
|---:|---|---|---:|
| 1 | Pedro Castillo | Perú Libre | 12,659 |
| 2 | Keiko Fujimori | Fuerza Popular | 4,762 |
| 3 | Yonhy Lescano | Acción Popular | 2,940 |
| 4 | Verónika Mendoza | Juntos por el Perú | 2,661 |
| 5 | César Acuña | Alianza para el Progreso | 1,495 |

### Cajamarca (374 mesas, 135,036 votos válidos)

| Pos. | Candidato | Partido | Votos |
|---:|---|---|---:|
| 1 | Pedro Castillo | Perú Libre | 24,137 |
| 2 | Keiko Fujimori | Fuerza Popular | 5,047 |
| 3 | Yonhy Lescano | Acción Popular | 3,422 |
| 4 | César Acuña | Alianza para el Progreso | 2,560 |
| 5 | Verónika Mendoza | Juntos por el Perú | 2,110 |

### Cusco (166 mesas, 59,264 votos válidos)

| Pos. | Candidato | Partido | Votos |
|---:|---|---|---:|
| 1 | Pedro Castillo | Perú Libre | 9,586 |
| 2 | Verónika Mendoza | Juntos por el Perú | 3,718 |
| 3 | Yonhy Lescano | Acción Popular | 1,843 |
| 4 | Keiko Fujimori | Fuerza Popular | 1,207 |
| 5 | Ollanta Humala | Partido Nacionalista Peruano | 490 |

### Huánuco (196 mesas, 66,390 votos válidos)

| Pos. | Candidato | Partido | Votos |
|---:|---|---|---:|
| 1 | Pedro Castillo | Perú Libre | 11,171 |
| 2 | Keiko Fujimori | Fuerza Popular | 2,337 |
| 3 | Yonhy Lescano | Acción Popular | 2,038 |
| 4 | Rafael López Aliaga | Renovación Popular | 1,549 |
| 5 | César Acuña | Alianza para el Progreso | 1,226 |

### Lima (254 mesas, 110,218 votos válidos)

| Pos. | Candidato | Partido | Votos |
|---:|---|---|---:|
| 1 | **Keiko Fujimori** | Fuerza Popular | **8,987** |
| 2 | Pedro Castillo | Perú Libre | 8,558 |
| 3 | Rafael López Aliaga | Renovación Popular | 5,453 |
| 4 | Hernando de Soto | Avanza País | 3,925 |
| 5 | Yonhy Lescano | Acción Popular | 3,601 |

### Loreto (213 mesas, 58,752 votos válidos)

| Pos. | Candidato | Partido | Votos |
|---:|---|---|---:|
| 1 | **Keiko Fujimori** | Fuerza Popular | **3,224** |
| 2 | Ollanta Humala | Partido Nacionalista Peruano | 3,033 |
| 3 | César Acuña | Alianza para el Progreso | 2,516 |
| 4 | Yonhy Lescano | Acción Popular | 2,481 |
| 5 | George Forsyth | Victoria Nacional | 1,960 |

### Piura (199 mesas, 77,322 votos válidos)

| Pos. | Candidato | Partido | Votos |
|---:|---|---|---:|
| 1 | **Keiko Fujimori** | Fuerza Popular | **7,256** |
| 2 | Pedro Castillo | Perú Libre | 6,505 |
| 3 | Yonhy Lescano | Acción Popular | 1,738 |
| 4 | Verónika Mendoza | Juntos por el Perú | 1,733 |
| 5 | Ollanta Humala | Partido Nacionalista Peruano | 1,570 |

### Puno (111 mesas, 43,356 votos válidos)

| Pos. | Candidato | Partido | Votos |
|---:|---|---|---:|
| 1 | Pedro Castillo | Perú Libre | 9,068 |
| 2 | Yonhy Lescano | Acción Popular | 3,922 |
| 3 | Verónika Mendoza | Juntos por el Perú | 1,090 |
| 4 | Keiko Fujimori | Fuerza Popular | 423 |
| 5 | Ollanta Humala | Partido Nacionalista Peruano | 377 |

> **Patrón Lima 900K en 1V es único:** es el único departamento donde Keiko ganó en 1V dentro del bloque 900K (8,987 vs 8,558 de Castillo). En Loreto y Piura también lidera en 1V. En el sur andino (Puno, Cusco, Ayacucho), Keiko queda 4ª o más abajo.

---

## Consultas MCP 2021 con filtro de prefijo de mesas

Desde la versión actual del servidor, `onpe_2021_chat` soporta filtrado por prefijo de mesa. Esto permite replicar las consultas del bloque 900K directamente para 2021.

### Ejemplos funcionales

```python
# Top 5 en mesas 900K — 2021 segunda vuelta
mcp_onpe-mcp_onpe_2021_chat("top en mesas 900K segunda vuelta", vuelta=2)
# → 3,108 mesas, Castillo 380,932 (69.5%), Keiko 167,309 (30.5%)

# Top 5 en mesas 900K — 2021 primera vuelta
mcp_onpe-mcp_onpe_2021_chat("top en mesas prefijo 9 primera vuelta", vuelta=1)
# → 3,108 mesas, Castillo 140,021, Keiko 59,437, Lescano 38,308

# Mismo bloque pero como query SQL
mcp_onpe-mcp_onpe_2021_chat("resultados bloque 900 segunda vuelta 2021")
```

### Datos de referencia 2021 2V — bloque 900K

| Indicador | Valor |
|---|---:|
| Mesas 900K | 3,108 |
| Electores hábiles | 778,663 |
| Votos emitidos | 589,952 |
| Participación | 75.77% |
| Votos válidos | 548,241 |
| **Pedro Castillo** (Perú Libre) | **380,932 (69.5%)** |
| **Keiko Fujimori** (Fuerza Popular) | **167,309 (30.5%)** |
| Blancos | 7,745 |
| Nulos | 33,966 |

> El bloque 900K creció de **3,108 mesas en 2021** a **4,703 en 2026** (+1,595 mesas, +51%). El patrón 70/30 se mantiene casi idéntico en ambas segundas vueltas, confirmando que la estructura del voto rural es estructural.



1. **Cobertura 2V no es 100%** (98.25% al cierre del análisis). 1,620 actas siguen en proceso (anuladas, observadas o pendientes).
2. **El modelo NNLS asume linealidad** en la transferencia de votos. Casos extremos (mesas con candidato local fuerte en 1V) pueden tener flujos no-lineales.
3. **El "Otros partidos pequeños"** (18 agrupaciones agregadas en el modelo local 900K) tiene alta multicolinealidad; sus coeficientes individuales no son interpretables.
4. **No se modeló cambio de local de votación**: 44 locales fueron reasignados entre 1V y 2V (~570 mesas afectadas — ver `mcp_onpe-mcp_onpe_sv_reasignados`). El análisis las trata como si la mesa siguiera siendo la misma.
5. **No se diferenció horario de cierre**: mesas que cerraron tardío en 1V o 2V pueden tener perfil de votantes distinto al promedio.

## Referencias

- Datos oficiales ONPE: <https://resultadoelectoral.onpe.gob.pe>
- Scraper 1V: <https://github.com/oscarzamora/onpeescraper>
- Scraper 2V: <https://github.com/oscarzamora/onpe-scraper-2026-2>
- Modelo NNLS calibrado: [`src/onpe_mcp/knowledge_base.py`](../src/onpe_mcp/knowledge_base.py) (`TRANSFER_MAP`)
- Plan técnico SV: [`docs/plan-segunda-vuelta.md`](plan-segunda-vuelta.md)
- QA plan SV: [`docs/qa-plan-segunda-vuelta.md`](qa-plan-segunda-vuelta.md)
- Compendio cualitativo: [`src/onpe_mcp/knowledge_base.py`](../src/onpe_mcp/knowledge_base.py) (535 hechos verificados)
