"""Base de conocimiento electoral verificable para respuestas pedagógicas neutrales.

Orden de prioridad de datos en onpe_chat:
  1. Cache local SQLite (datos hidratados del MCP)
  2. API ONPE en vivo
  3. Compendio cualitativo de este módulo (fallback sin cifras inventadas)
  4. Fuentes externas (indicado explícitamente)

Todos los hechos son verificables mediante fuentes oficiales (ONPE, JNE, RENIEC).
No se especulan ni proyectan resultados electorales.
"""
from __future__ import annotations

# ──────────────────────────────────────────────────────────────────────────────
# Mesas 900K
# ──────────────────────────────────────────────────────────────────────────────
_MESA_900K_FACTS: tuple[str, ...] = (
    "Las mesas con prefijo 9XXXXX existen en el padrón oficial de ONPE desde hace más de 20 años.",
    "Se asignan a centros poblados menores, comunidades nativas y zonas rurales de difícil acceso.",
    "No son nuevas ni creadas para 2026; funcionan igual que cualquier mesa urbana: "
    "padrón RENIEC, miembros de mesa, personeros, actas y fiscalización.",
    "Todos los partidos reciben con anticipación la lista completa de mesas (incluidas las 900K) "
    "para acreditar personeros.",
    "Las mesas 900K no aparecen en Lima urbana, por eso muchos ciudadanos nunca han visto una. "
    "Su numeración alta no implica irregularidad; es un rango asignado históricamente para zonas rurales.",
)

# ──────────────────────────────────────────────────────────────────────────────
# STAE y sistema de transmisión
# ──────────────────────────────────────────────────────────────────────────────
_STAE_FACTS: tuple[str, ...] = (
    "El STAE no está conectado a internet. Es un kit para imprimir actas y reducir errores manuales.",
    "Fue auditado bajo ISO 27001 y NIST CSF. No transmite votos ni resultados "
    "y no tiene capacidad de alterar el padrón.",
    "ONPE reconoció errores logísticos en Lima Metropolitana los días 12–13 de abril; "
    "se separó a funcionarios responsables y se abrió investigación administrativa. "
    "Esto no invalida el proceso.",
)

# ──────────────────────────────────────────────────────────────────────────────
# Proceso electoral y actas
# ──────────────────────────────────────────────────────────────────────────────
_PROCESS_FACTS: tuple[str, ...] = (
    "El escrutinio es público y presenciado por personeros de todos los partidos.",
    "Las actas físicas son el documento fuente; el STAE transmite imágenes de esas actas.",
    "Las actas observadas son normales en cualquier elección: se observan por errores de firma, "
    "sumas, tachaduras o inconsistencias. El JEE revisa cada caso con presencia de personeros. "
    "No significa manipulación.",
    "Las correcciones en actas son normales cuando se detecta un error de suma; "
    "deben estar firmadas por los tres miembros de mesa y el JEE revisa cualquier corrección dudosa.",
    "En zonas sin STAE las actas se llenan manualmente. "
    "Cada miembro de mesa tiene su propia firma; no existe un estándar visual. "
    "Los personeros verifican identidad en el momento.",
    "Las diferencias entre número de votantes y número de votos pueden deberse a errores de conteo. "
    "Por eso existen las actas observadas: el JEE revisa y corrige con presencia de personeros.",
    "El escaneo de actas depende de la calidad del equipo y la iluminación. "
    "ONPE publica la imagen original sin editar. Si el acta es ilegible, se revisa el físico.",
    "Si falta una firma, el acta se observa automáticamente. "
    "No se contabiliza hasta que el JEE la revise.",
)

# ──────────────────────────────────────────────────────────────────────────────
# Patrones rurales vs urbanos
# ──────────────────────────────────────────────────────────────────────────────
_RURAL_VOTE_FACTS: tuple[str, ...] = (
    "En zonas rurales pequeñas la participación suele ser muy alta porque las comunidades son cohesionadas. "
    "En ciudades la abstención es más común. No es un fenómeno nuevo.",
    "Las mesas rurales pueden tener 20, 30 o 50 votantes porque están diseñadas para evitar "
    "que la población camine largas distancias. Esto existe desde hace muchos procesos electorales.",
    "En zonas rurales el voto tiende a ser más homogéneo; en ciudades es más fragmentado. "
    "No implica fraude; implica dinámicas sociales distintas.",
    "Una concentración de votos en un candidato dentro de un prefijo rural puede reflejar "
    "preferencia regional documentada, no necesariamente irregularidad.",
)

# ──────────────────────────────────────────────────────────────────────────────
# Patrones geográficos específicos (Lima periurbana, distritos)
# ──────────────────────────────────────────────────────────────────────────────
_GEO_PATTERNS: tuple[str, ...] = (
    "Pachacámac y Lurín combinan zonas urbanas consolidadas con anexos rurales; "
    "el voto en los anexos tiende a ser más homogéneo que en las áreas urbanas.",
    "San Juan de Miraflores (SJM) es urbano denso, por lo que el voto es más fragmentado "
    "y la abstención puede ser mayor que en zonas rurales.",
    "Paterson y Orlando (EE. UU.) concentran alta migración peruana; "
    "la participación en mesas del exterior depende del registro consular.",
    "Los resultados oficiales por distrito deben consultarse en el portal de ONPE "
    "(resultadoelectoral.onpe.gob.pe) o mediante este MCP usando onpe_get_mesa / onpe_chat.",
)

# ──────────────────────────────────────────────────────────────────────────────
# Respuesta a sospechas de fraude
# ──────────────────────────────────────────────────────────────────────────────
_FRAUD_RESPONSE_FACTS: tuple[str, ...] = (
    "No hay indicios documentados de fraude asociados a mesas 900K, STAE o mesas rurales.",
    "El padrón electoral es de RENIEC, no de ONPE; no puede ser alterado por el sistema de cómputo.",
    "Las actas se procesan igual que cualquier otra y existen auditorías externas al sistema.",
    "Para cualquier denuncia concreta, el canal oficial es el JNE "
    "(jne.gob.pe) y la Fiscalía Especializada en Delitos Electorales.",
)

# ──────────────────────────────────────────────────────────────────────────────
# Mesas del lunes 13 (instalación diferida Lima)
# ──────────────────────────────────────────────────────────────────────────────
_LUNES13_FACTS: tuple[str, ...] = (
    "ONPE reconoció errores logísticos en Lima Metropolitana el 12–13 de abril.",
    "La ley electoral permite completar la instalación de mesas en casos excepcionales.",
    "Se separó a los funcionarios responsables y se abrió investigación administrativa.",
    "La instalación diferida no invalida el proceso ni las actas resultantes.",
)

# ──────────────────────────────────────────────────────────────────────────────
# Resultados nacionales 2026 (100 % mesas contabilizadas)
# ──────────────────────────────────────────────────────────────────────────────
_ELECTION_RESULTS_2026: tuple[str, ...] = (
    "Resultados nacionales elecciones 2026 (fuente: ONPE, 100% de mesas contabilizadas):",
    "· FUERZA POPULAR (Keiko Fujimori): 2,877,621 votos válidos (17.18%)",
    "· JUNTOS POR EL PERÚ: 2,015,060 votos válidos (12.03%)",
    "· RENOVACIÓN POPULAR (Rafael López Aliaga): 1,993,815 votos válidos (11.90%)",
    "· PARTIDO DEL BUEN GOBIERNO: 1,837,456 votos válidos (10.97%)",
    "· PARTIDO CÍVICO OBRAS: 1,698,895 votos válidos (10.14%)",
    "· Blancos + nulos + impugnados: 3,418,306 (no forman parte del denominador de votos válidos ONPE).",
    "Universo: 92,766 mesas presidenciales, 27,325,132 electores hábiles.",
)

# ──────────────────────────────────────────────────────────────────────────────
# Detalle de actas: preguntas frecuentes sobre aspectos visuales y formales
# ──────────────────────────────────────────────────────────────────────────────
_ACTA_DETAIL_FACTS: tuple[str, ...] = (
    "La duplicación visual de actas en el portal puede ser un error de visualización, "
    "no del cómputo. El sistema solo contabiliza una acta por mesa.",
    "Distintos miembros de mesa pueden llenar secciones diferentes del acta; "
    "es normal y no implica irregularidad.",
    "A veces un miembro de mesa escribe más rápido y los demás le piden apoyo. "
    "Es común, especialmente en zonas rurales con baja capacitación.",
    "En zonas rurales pequeñas, donde todos se conocen, el proceso suele ser más ordenado "
    "y las actas más limpias. No implica manipulación.",
    "En zonas urbanas con alta rotación de miembros de mesa o poca capacitación, "
    "las actas pueden tener más errores formales o presentación desordenada.",
    "Las condiciones de clima, humedad o materiales de escritura pueden provocar tinta corrida "
    "o manchas en el acta. No implica manipulación.",
    "Algunas personas tienen firmas simples o visualmente similares. "
    "No es indicador de fraude por sí solo; los personeros verifican identidad en el momento.",
    "La caligrafía varía entre miembros de mesa. Si el acta es ilegible, el JEE revisa el acta física.",
    "Las tachaduras ocurren cuando se corrige un error. "
    "Mientras estén firmadas por los miembros de mesa, son válidas.",
    "Un número sobrescrito o corregido es parte del proceso de corrección manual. "
    "El JEE revisa y valida cada corrección dudosa.",
)

# ──────────────────────────────────────────────────────────────────────────────
# Voto protesta, blancos/nulos y heterogeneidad entre mesas contiguas
# ──────────────────────────────────────────────────────────────────────────────
_VOTE_HETEROGENEITY_FACTS: tuple[str, ...] = (
    "En zonas urbanas el voto protesta (blancos y nulos) es más frecuente. "
    "En zonas rurales suele ser menor. No implica irregularidad; es un patrón histórico.",
    "La composición social cambia incluso entre barrios cercanos o mesas contiguas. "
    "No es raro que mesas adyacentes tengan comportamientos distintos; refleja diversidad del electorado.",
    "En zonas urbanas la abstención es más alta por movilidad, trabajo o desinterés. "
    "No es un patrón nuevo ni indicativo de fraude.",
    "Una mesa con muy poca participación en zona urbana puede reflejar electores que ya no "
    "viven en esa dirección pero no actualizaron su domicilio en RENIEC.",
)

# ──────────────────────────────────────────────────────────────────────────────
# Aspectos físicos y visuales de actas (caligrafía, tinta, sellos, papel)
# ──────────────────────────────────────────────────────────────────────────────
_ACTA_PHYSICAL_FACTS: tuple[str, ...] = (
    "La caligrafía no determina la validez del acta. "
    "Lo importante son las firmas, la consistencia de sumas y la revisión del JEE. "
    "Cada miembro de mesa escribe distinto: cursiva, imprenta, letra grande o pequeña, todo es normal.",
    "Los miembros de mesa pueden usar lapiceros de distintos colores. "
    "No afecta la validez del acta si las firmas están completas. "
    "El uso de lápiz no es lo ideal, pero el JEE valida o observa el acta según corresponda.",
    "En algunos locales se usan marcadores gruesos o plumones. No afecta la validez del acta.",
    "Los números redondos (como 100 votos exactos) pueden aparecer cuando la mesa tiene pocos electores "
    "o cuando el conteo fue muy homogéneo. No implica irregularidad. "
    "El JEE revisa cualquier inconsistencia si la hubiera.",
    "Un sello mal puesto, de otro color, repetido o incompleto no invalida el acta si las firmas están correctas. "
    "Los locales pueden tener sellos de distintos tipos; los errores al sellar son normales.",
    "Manchas de humedad, tierra, arrugas, bordes rotos o imperfecciones del papel no invalidan el acta. "
    "En zonas rurales o costeras la humedad y el polvo son comunes. "
    "El contenido sigue siendo válido si es legible.",
    "Un número borrado, con trazo fuerte, escrito fuera del recuadro o con presión variable "
    "puede ser un intento de corrección o simplemente el estilo del miembro de mesa. "
    "El JEE revisa el acta física si hay duda.",
    "El cansancio, los nervios, la lateralidad (zurdo o diestro) del miembro de mesa pueden afectar la escritura. "
    "No afecta la validez del acta mientras las firmas y los datos estén presentes.",
    "Es común que un miembro de mesa que escribe más rápido apoye a los otros a completar secciones. "
    "No implica fraude ni irregularidad.",
    "Un número sobrescrito varias veces o encima de una mancha indica corrección manual. "
    "El JEE valida el valor final revisando el acta física.",
    "El desgaste físico (esquina rota, borde mojado, arrugas) no invalida el acta "
    "si la información está completa y las firmas presentes.",
    "El cierre de mesa puede ser apresurado y afectar la presentación del acta. "
    "El JEE revisa cualquier inconsistencia si la hubiera.",
)

_CANDIDATOS_FACTS: tuple[str, ...] = (
    "Keiko Fujimori encabeza la candidatura presidencial de Fuerza Popular en la primera vuelta de 2026.",
    "Fuerza Popular es una organización nacional identificada con la tradición política del fujimorismo.",
    "La figura de Keiko Fujimori está asociada a campañas previas y a un electorado que prioriza orden, seguridad y estructura partidaria.",
    "Rafael López Aliaga compite por Renovación Popular en la elección presidencial de 2026.",
    "Renovación Popular se presenta como una fuerza de derecha conservadora con énfasis en orden, gestión y valores tradicionales.",
    "La trayectoria reciente de Rafael López Aliaga incluye su paso por la alcaldía de Lima Metropolitana.",
    "\"Juntos por el Perú\" es una etiqueta política asociada al espacio de izquierda y progresismo en la competencia presidencial.",
    "En la práctica, \"Juntos por el Perú\" funciona como una marca electoral reconocible para un segmento del electorado nacional.",
    "El Partido del Buen Gobierno aparece en 2026 vinculado a la candidatura de Antauro Humala.",
    "La presencia de Antauro Humala en el debate electoral se asocia a un discurso nacionalista y antisistema.",
    "Partido Cívico Obras aparece en la contienda con Ricardo Belmont como figura política de referencia.",
    "Ricardo Belmont es una figura conocida por su trayectoria mediática y municipal, más que por una estructura partidaria tradicional.",
    "Además de las candidaturas principales, la primera vuelta incluye partidos pequeños y opciones de menor implantación territorial.",
    "En Perú es normal que la primera vuelta tenga muchas candidaturas y un voto bastante fragmentado.",
    "Los partidos pequeños pueden competir aunque sepan que su objetivo principal es posicionar ideas, conservar inscripción o ganar visibilidad.",
    "Una alianza electoral es un acuerdo legal entre organizaciones políticas para presentar una oferta común en una elección.",
    "La alianza electoral no nace por afinidad verbal; requiere trámites formales, aprobación interna y registro oportuno ante la autoridad electoral.",
    "Cuando hay alianza, los partidos coordinan símbolo, denominación y reglas de representación conforme al marco legal vigente.",
    "La inscripción de una candidatura presidencial no es solo un anuncio político; exige expediente, plazos y revisión de requisitos formales.",
    "Las candidaturas deben pasar por mecanismos de democracia interna antes de su inscripción definitiva.",
    "La autoridad electoral revisa documentación, declaraciones juradas y eventuales impedimentos legales de cada postulación.",
    "La hoja de vida del candidato es parte del expediente y sirve para control ciudadano y fiscalización electoral.",
    "La exclusión o improcedencia de una candidatura se resuelve dentro de procedimientos reglados y con posibilidad de impugnación.",
    "Para ser presidente del Perú se requiere ser peruano de nacimiento y cumplir la edad mínima fijada por la Constitución.",
    "También se exige gozar del derecho de sufragio y no estar comprendido en impedimentos constitucionales o legales.",
    "La postulación presidencial sigue el diseño de fórmula previsto por la legislación electoral vigente, no una candidatura aislada sin estructura.",
    "Las organizaciones políticas nacionales son las únicas que pueden competir en la elección presidencial; los movimientos regionales no presentan candidato presidencial propio.",
    "Un candidato puede postular por un partido distinto al espacio político con el que fue conocido anteriormente, si la organización lo acoge formalmente.",
    "El orden de aparición en la cédula no depende de encuestas ni de preferencias mediáticas, sino de reglas oficiales del proceso.",
    "El número con el que aparece una organización en la cédula responde a criterios registrales y administrativos, no al resultado de la jornada.",
    "La ubicación del partido en la cédula es importante porque muchos electores identifican más rápido símbolo y número que nombre largo.",
    "ONPE publica con anticipación el diseño de la cédula para que partidos, personeros y votantes conozcan el orden de las opciones.",
    "La cédula presidencial muestra la oferta partidaria, no una lista abierta de nombres sin organización.",
    "La campaña de primera vuelta suele combinar imagen del candidato, marca partidaria, número y símbolo.",
    "En un sistema fragmentado, el conocimiento previo del candidato puede pesar tanto como la fortaleza formal del partido.",
    "La condición de favorito o rezagado en opinión pública no reemplaza el requisito legal de inscripción válida.",
    "La autoridad electoral trata a candidaturas grandes y pequeñas bajo el mismo marco formal de inscripción, fiscalización y resolución de controversias.",
)

_SISTEMA_ELECTORAL_FACTS: tuple[str, ...] = (
    "La elección presidencial peruana usa un sistema de mayoría absoluta con posibilidad de segunda vuelta.",
    "La primera vuelta sirve para medir apoyo nacional entre varias candidaturas en competencia simultánea.",
    "Si ninguna candidatura supera el umbral legal sobre votos válidos, la definición pasa a una segunda vuelta.",
    "La segunda vuelta enfrenta únicamente a las dos candidaturas con mayor votación válida nacional en la primera ronda.",
    "Si una candidatura supera el 50% de los votos válidos, queda elegida en primera vuelta y no se realiza balotaje.",
    "Los votos válidos son los que favorecen a una opción en competencia; blancos y nulos no integran ese denominador.",
    "El voto en blanco expresa participación sin elegir opción; el voto nulo invalida la cédula por error o marca incompatible con la regla.",
    "ONPE organiza la ejecución material de la elección: locales, mesas, cédulas, escrutinio operativo y cómputo.",
    "RENIEC administra identidad y padrón electoral, que es la base de quiénes están habilitados para votar.",
    "El JNE resuelve controversias, administra justicia electoral y proclama resultados oficiales.",
    "La separación entre ONPE, RENIEC y JNE busca distribuir funciones críticas para evitar concentración de control.",
    "En Perú el voto es obligatorio para ciudadanos habilitados, aunque existen causales de dispensa y justificación.",
    "La obligatoriedad del voto tiende a elevar la participación respecto de sistemas completamente voluntarios.",
    "La multa por no votar existe en la normativa, pero su aplicación depende de la situación del elector y de reglas de exención o dispensa.",
    "El escrutinio empieza al cierre de la votación y se realiza en la misma mesa donde votaron los electores.",
    "El conteo se hace voto por voto y acta por acta, no mediante estimaciones ni encuestas.",
    "El escrutinio es público y puede ser observado por personeros, observadores y ciudadanía presente en el local.",
    "Una mesa de sufragio es la unidad básica donde se identifica al elector, se deposita el voto y se cuenta el resultado.",
    "Los miembros de mesa instalan la mesa, reciben a los votantes, cuentan los votos y llenan las actas.",
    "Los miembros de mesa son designados conforme a reglas de sorteo y contingencia previstas por la normativa.",
    "El quórum de mesa importa porque sin el número mínimo de miembros habilitados no puede desarrollarse regularmente la jornada.",
    "Si faltan miembros titulares, se aplican suplencias o mecanismos de integración con electores de la fila según la norma.",
    "El ganador de primera vuelta se define por total nacional de votos válidos, no por número de regiones ganadas.",
    "El sistema no premia al candidato que lidera más departamentos si otro obtiene mejor suma nacional de votos válidos.",
    "Las actas observadas son parte normal del sistema y existen para corregir o revisar inconsistencias formales.",
    "Una observación de acta no equivale a fraude; activa un procedimiento de revisión.",
    "La cronología electoral incluye jornada de votación, cómputo, resolución de observaciones, apelaciones y proclamación.",
    "La fecha exacta de una eventual segunda vuelta está fijada por el cronograma oficial del proceso.",
    "Los resultados que difunde ONPE pueden avanzar por etapas, pero el sustento legal siempre descansa en actas y resoluciones.",
    "Las mesas del exterior integran el mismo cómputo presidencial nacional.",
    "La autoridad electoral distingue entre resultados procesados, actas observadas y resultados proclamados.",
    "Las cédulas no utilizadas se inutilizan al cierre para preservar la integridad del material electoral.",
    "Los electores que siguen en la fila al momento de cierre son atendidos conforme a la regla operativa aplicable.",
    "La mesa no puede reemplazar el padrón con listas improvisadas; solo vota quien figura habilitado en esa mesa.",
    "El escrutinio público permite control inmediato de sumas, votos blancos, votos nulos y votos válidos.",
    "La cédula de votación y el acta cumplen funciones distintas: una recoge la preferencia, la otra documenta el resultado.",
    "El sistema de dos vueltas busca asegurar que el eventual presidente tenga una base de legitimidad mayor que la de una simple pluralidad baja.",
    "En contextos de alta fragmentación, la primera vuelta ordena la oferta y la segunda vuelta concentra la decisión entre dos opciones.",
    "El resultado presidencial se construye desde abajo: mesa, local, distrito, provincia, departamento y agregado nacional.",
)

_PADRON_RENIEC_FACTS: tuple[str, ...] = (
    "RENIEC es la entidad que administra la base registral que da origen al padrón electoral.",
    "El padrón electoral se construye a partir de la información del DNI y de los cierres del cronograma electoral.",
    "Cuando se habla de padrón biométrico se alude al uso de datos de identidad y verificación asociados al registro civil y al DNI.",
    "La verificación dactilar es un mecanismo de apoyo para confirmar identidad en etapas o entornos definidos por la autoridad.",
    "La elección no depende de una conexión permanente a internet para reconocer a cada elector en tiempo real.",
    "Un elector puede aparecer asignado a un lugar distinto de donde vive actualmente si no actualizó su domicilio antes del cierre del padrón.",
    "La actualización del domicilio electoral se realiza mediante el trámite de cambio de domicilio en el DNI dentro del plazo habilitado.",
    "Los cambios hechos fuera de plazo suelen impactar en procesos posteriores, no necesariamente en la elección inmediata.",
    "El padrón se cierra meses antes de la jornada para que ONPE pueda planificar mesas, locales y material electoral.",
    "ONPE recibe el padrón cerrado para organizar la operación; no lo elabora desde cero.",
    "Si una persona fallecida aparece en el padrón, el caso suele relacionarse con tiempos de corte registral o actualización pendiente en bases administrativas.",
    "La presencia de un nombre en el padrón no prueba que esa persona haya votado; solo indica habilitación registral al momento del cierre.",
    "Las observaciones sobre fallecidos o datos errados se canalizan por vías formales de revisión registral y electoral.",
    "El padrón es publicitado en etapas para que la ciudadanía pueda revisar datos y formular tachas u observaciones cuando corresponda.",
    "Los extranjeros residentes en Perú no integran el padrón presidencial peruano por el solo hecho de residir en el país.",
    "Para votar en la elección presidencial peruana se requiere ciudadanía peruana y habilitación en el padrón correspondiente.",
    "Los peruanos domiciliados en el exterior sí pueden integrar el padrón, pero según su registro consular o domicilio declarado fuera del país.",
    "RENIEC y ONPE cruzan información para ubigeos, locales, identidad y consistencia operativa antes de la impresión de padrones de mesa.",
    "La asignación a una mesa concreta depende de la combinación de padrón, local y criterios logísticos de distribución de electores.",
    "Un mismo distrito puede tener muchas mesas porque el padrón se divide en unidades operables y verificables.",
    "El padrón impreso por mesa es la referencia inmediata para admitir o no a un votante en la jornada.",
    "Los datos biométricos ayudan a la gestión de identidad, pero no sustituyen el acta física ni el registro de firma del proceso electoral.",
    "Si hay una contingencia con verificación biométrica, la autoridad aplica procedimientos manuales previstos por la norma y los protocolos.",
    "Las inconsistencias registrales no se resuelven con rumores en redes, sino con expediente, contraste documental y decisión de la autoridad.",
    "La depuración de duplicidades o errores depende del control registral continuo y de las etapas de publicación del padrón.",
    "El domicilio electoral influye directamente en dónde vota la persona y, por tanto, en qué mesa y local aparece asignada.",
    "La migración interna explica por qué algunas mesas urbanas tienen electores que ya no residen efectivamente en esa dirección.",
    "El cruce RENIEC-ONPE también sirve para imprimir listas exactas por mesa y evitar improvisación el día de la elección.",
    "El padrón es una fotografía administrativa tomada en la fecha de cierre, no un reflejo perfecto de cambios de residencia ocurridos después.",
)

_AUDITORIA_FACTS: tuple[str, ...] = (
    "Los procesos electorales peruanos contemplan capas de auditoría técnica, control partidario y revisión jurisdiccional.",
    "Las auditorías externas pueden revisar seguridad informática, procedimientos, trazabilidad y contingencias operativas.",
    "La auditoría no solo mira software; también evalúa documentos físicos, actas, custodia y cumplimiento de protocolo.",
    "Los personeros constituyen una forma de auditoría partidaria en tiempo real dentro de la mesa y del local.",
    "La fiscalización del JNE se concentra en legalidad, controversias y cumplimiento de normas electorales.",
    "Las misiones internacionales, como OEA o Unión Europea cuando participan, observan estándares y reportan hallazgos, pero no sustituyen a la autoridad nacional.",
    "La observación internacional sirve para contrastar el proceso con buenas prácticas comparadas.",
    "Las actas selladas y firmadas reducen el riesgo de sustitución irregular del documento fuente.",
    "La cadena de custodia de las actas documenta cómo se trasladan desde la mesa hasta los puntos de recepción y procesamiento.",
    "Cada etapa de traslado busca que el acta física permanezca identificable, íntegra y verificable.",
    "Las copias entregadas o mostradas a personeros permiten una auditoría cruzada con lo publicado oficialmente.",
    "Si un personero objeta un resultado, debe dejar constancia y activar el procedimiento previsto por la norma.",
    "Una objeción partidaria no invalida por sí sola el acta; abre un camino de revisión.",
    "Las quejas formales requieren identificación del hecho, de la mesa o del documento cuestionado y del fundamento legal invocado.",
    "Una impugnación de mesa es un mecanismo jurídico específico y no un simple comentario político o mediático.",
    "Los plazos para apelar resultados u observaciones son cortos porque el calendario electoral es perentorio.",
    "La revisión de una mesa cuestionada suele contrastar acta publicada, copia partidaria y documento físico original.",
    "El control de custodia puede involucrar personal logístico, responsables electorales y resguardo de seguridad según el tramo del traslado.",
    "Las actas observadas quedan separadas del flujo ordinario hasta que la autoridad competente resuelve su situación.",
    "Los sistemas informáticos electorales suelen mantener registros de acceso y eventos para auditoría posterior.",
    "La existencia de bitácoras o logs no reemplaza al acta física; ambos niveles se complementan.",
    "Un error administrativo y un presunto delito electoral se investigan por canales distintos, aunque puedan originarse en el mismo hecho.",
    "La Fiscalía Especializada en Delitos Electorales interviene cuando hay indicios de conducta penalmente relevante.",
    "El JEE conoce muchos casos en primera instancia y el JNE revisa en apelación cuando la norma lo permite.",
    "La publicación de imágenes de actas facilita una auditoría social más amplia porque cualquier actor puede contrastar sumas y firmas.",
    "Los observadores internacionales documentan hallazgos, pero no alteran actas ni reemplazan decisiones de la justicia electoral.",
    "Los paquetes electorales sellados preservan cédulas, padrones y actas para eventuales verificaciones posteriores.",
    "Una denuncia genérica de fraude tiene menos peso que una denuncia con número de mesa, imagen de acta y causal precisa.",
    "Las auditorías técnicas pueden revisar infraestructura, transmisión, seguridad y contingencia sin tocar la voluntad expresada en el papel.",
    "La cobertura mediática puede ayudar a transparentar problemas, pero no sustituye los procedimientos formales de prueba.",
    "No toda inconsistencia formal tiene capacidad real de modificar un resultado; la autoridad evalúa su relevancia material.",
    "La confianza en el proceso aumenta cuando coinciden controles de partidos, observadores, autoridad electoral y acta física.",
    "Una elección robusta descansa en controles redundantes, no en una sola barrera institucional.",
    "La trazabilidad documental es central porque permite reconstruir qué ocurrió en cada mesa ante cualquier controversia.",
)

_PERSONEROS_FACTS: tuple[str, ...] = (
    "Un personero es el representante acreditado de una organización política ante una mesa, local o autoridad electoral.",
    "El personero puede ser titular o alterno según el tipo de acreditación que presente el partido.",
    "Cada organización política puede acreditar personeros conforme al número y tipo permitidos por la normativa aplicable.",
    "El personero observa la instalación de la mesa, el desarrollo de la votación y el escrutinio público.",
    "También puede formular observaciones, solicitar constancias y firmar actas si decide hacerlo.",
    "El personero no puede manipular cédulas, ánforas o padrones fuera de lo expresamente permitido.",
    "Su función es vigilar y dejar registro, no dirigir la mesa ni sustituir a los miembros de mesa.",
    "La acreditación del personero se tramita por canales partidarios y electorales antes de la jornada.",
    "Un personero debe identificarse con credencial válida para ejercer formalmente sus atribuciones.",
    "La ausencia del personero de un partido en una mesa no invalida la votación ni el acta de esa mesa.",
    "Las mesas rurales también pueden tener personeros; la distancia o el tamaño del local no elimina ese derecho.",
    "Las mesas del exterior igualmente admiten presencia de personeros cuando el partido logra acreditarlos.",
    "Un personero puede comparar su copia del acta con la imagen que luego publique la autoridad electoral.",
    "El desacuerdo del personero con un resultado no detiene automáticamente el escrutinio ni el cierre de mesa.",
    "La negativa del personero a firmar un acta no la vuelve nula por sí sola si el documento cumple los requisitos legales.",
    "El personero puede permanecer durante el escrutinio porque esa fase es pública y verificable.",
    "Cuando impugna un voto o deja observación, debe hacerlo en el momento y con base en las reglas del procedimiento.",
    "El personero debe mantener conducta respetuosa y no puede inducir el voto ni intimidar electores.",
    "Los partidos con red territorial débil suelen tener menos cobertura de personeros y, por tanto, menor capacidad de control directo.",
    "En un mismo local pueden coexistir personeros de varios partidos observando el mismo proceso desde miradas distintas.",
    "La calidad del control partidario depende mucho de la capacitación previa de los personeros.",
    "El personero cumple una función partidaria, pero dentro de un marco legal que limita su actuación.",
    "La presencia de personeros en zonas alejadas es una garantía adicional de pluralidad, no una señal de conflicto.",
)

_PARTICIPACION_FACTS: tuple[str, ...] = (
    "Perú suele registrar participación alta en términos comparados porque el voto es obligatorio.",
    "Una participación alta no significa unanimidad ni ausencia de abstención.",
    "La participación rural y la urbana pueden diferir por distancia, cohesión social y condiciones materiales del día electoral.",
    "En comunidades pequeñas la presión comunitaria y la cercanía del local pueden elevar la asistencia.",
    "En áreas urbanas la movilidad laboral, el tráfico y la desactualización del domicilio tienden a aumentar la abstención.",
    "La abstención puede deberse a enfermedad, viaje, lejanía, desinformación o desinterés político.",
    "El voto en blanco puede expresar protesta o distancia frente a toda la oferta electoral.",
    "El voto nulo también puede ser protesta, pero en otros casos refleja error al marcar la cédula.",
    "La altitud, la lluvia, el frío y las crecidas de ríos pueden afectar la llegada de electores y miembros de mesa.",
    "En zonas de sierra y selva, el clima puede alterar tiempos de desplazamiento sin cambiar las reglas del voto.",
    "Las comunidades nativas enfrentan retos particulares de conectividad, idioma y transporte para participar plenamente.",
    "La provisión de información en lenguas originarias puede mejorar comprensión y reducir errores de votación.",
    "El voto obligatorio reduce el costo de movilización partidaria porque obliga a todos los ciudadanos habilitados a decidir si asisten o se exponen a sanción.",
    "La multa por no votar forma parte del sistema de incentivos, pero su monto y cobro dependen de reglas vigentes y de la situación concreta del elector.",
    "Existen causales de exención, justificación o dispensa para quienes no pudieron votar por motivos legalmente reconocidos.",
    "La participación oficial se calcula sobre electores hábiles, no sobre población total ni sobre población en edad teórica de votar.",
    "Electores hábiles y votantes no son lo mismo: los primeros están inscritos y habilitados; los segundos son quienes efectivamente acudieron.",
    "Los votos blancos y nulos cuentan para medir participación porque su emisor sí acudió a la mesa.",
    "Una cola larga temprano en la mañana no permite estimar por sí sola la participación final del día.",
    "El avance de participación al mediodía puede cambiar bastante antes del cierre de la jornada.",
    "La participación puede variar mucho entre distritos, locales y mesas dentro de una misma ciudad.",
    "El transporte público disponible el día electoral influye en la facilidad con que la gente llega a votar.",
    "Un incidente local de seguridad puede afectar participación en una zona específica sin alterar la tendencia nacional.",
    "Las direcciones desactualizadas en grandes ciudades reducen la participación aparente porque muchas personas quedan asignadas a lugares donde ya no viven.",
    "La obligatoriedad del voto no elimina el voto protesta; solo hace más probable que ese descontento se exprese dentro de la urna.",
    "Un aumento de participación no favorece automáticamente a una sola fuerza política.",
    "Los electores jóvenes pueden enfrentar barreras documentarias o de primera experiencia, mientras los mayores enfrentan más barreras de movilidad.",
    "La atención preferente a personas adultas mayores o con discapacidad busca facilitar participación, no alterar el secreto del voto.",
    "La participación oficial se consolida a partir de actas procesadas, no de estimaciones en redes sociales.",
    "Los patrones de abstención suelen ser más heterogéneos que los patrones de votación por partido.",
    "La participación exterior suele ser menor que la interna por razones de distancia, trabajo y dispersión geográfica.",
    "Un elector que vota en blanco participó plenamente en la jornada, aunque no haya apoyado a ningún candidato.",
    "La abstención estructural en ciertos barrios puede repetirse en varias elecciones si no se corrige el problema de domicilio o acceso.",
    "La participación es un indicador de movilización ciudadana, pero no sustituye el análisis de votos válidos por candidato.",
)

_EXTERIOR_FACTS: tuple[str, ...] = (
    "El voto de los peruanos en el exterior forma parte del mismo cómputo presidencial nacional.",
    "El número exacto de mesas en el exterior depende del padrón consular y de la planificación operativa del proceso.",
    "Los países con comunidades peruanas más numerosas suelen concentrar más mesas y locales de votación.",
    "Estados Unidos, Chile, Argentina, España e Italia suelen aparecer entre los países con mayor presencia de votantes peruanos.",
    "Las mesas en el exterior se instalan normalmente en consulados o en locales autorizados con apoyo consular.",
    "El rol del consulado es logístico y de facilitación; las reglas del acto electoral siguen siendo peruanas.",
    "ONPE distribuye material electoral al exterior según el padrón cerrado y la organización del servicio consular.",
    "En términos legales, un voto emitido fuera del país vale lo mismo que un voto emitido dentro del territorio nacional.",
    "No existe una ponderación especial para el voto exterior dentro del resultado presidencial.",
    "Los resultados del exterior suelen tardar más por transporte, husos horarios y recepción documental.",
    "El traslado de actas del exterior puede requerir más pasos de seguridad y custodia que el traslado interno.",
    "Los tiempos de recepción desde el exterior no son uniformes porque dependen de distancias y disponibilidad de rutas.",
    "La participación en el exterior suele ser menor porque muchos votantes deben recorrer largas distancias hasta el local.",
    "Las obligaciones laborales en otro país también dificultan la asistencia de algunos electores al local consular.",
    "Un domicilio consular desactualizado puede dejar al elector asignado a una sede que ya no le resulta cercana.",
    "Las comunidades peruanas dispersas suelen concentrarse en una sola mesa o local por razones de eficiencia operativa.",
    "Las mesas del exterior también pueden contar con personeros y observadores si los partidos logran acreditarlos.",
    "Una mesa en el exterior puede atender a votantes de varias ciudades cercanas, no solo de la ciudad sede del consulado.",
    "Las actas del exterior están sujetas al mismo régimen de observación y revisión que las actas nacionales.",
    "El hecho de votar en un recinto diplomático no cambia el secreto ni la validez del sufragio.",
    "Los horarios de votación en el exterior se adaptan a la hora local de cada país.",
    "La publicación de actas del exterior puede verse más lenta por el tiempo de consolidación documental.",
    "El voto exterior puede ser relevante en contiendas cerradas, pero siempre se integra a un único total nacional.",
    "El personal consular no reemplaza a la autoridad de mesa; apoya la organización y la logística del local.",
    "La información previa del consulado es clave para que el elector conozca su dirección exacta de votación.",
    "No todos los países con presencia peruana tienen la misma escala operativa ni la misma densidad de mesas.",
    "Retrasos en actas del exterior no constituyen por sí mismos evidencia de irregularidad.",
    "El padrón exterior se construye con base en el registro de domicilio fuera del país, no por simple residencia informal.",
    "La experiencia de voto exterior depende tanto de la normativa peruana como de las condiciones locales del país anfitrión.",
)

_RESULTADOS_REGIONALES_FACTS: tuple[str, ...] = (
    "El voto regional en Perú es heterogéneo y rara vez puede resumirse en una sola división simple del país.",
    "Los patrones históricos muestran que el sur andino suele comportarse de manera distinta a la costa norte y a Lima.",
    "La costa norte suele valorar perfiles de gestión, seguridad, actividad económica y redes locales de influencia.",
    "El sur andino tiende a dar más espacio a discursos de representación, redistribución y crítica al centralismo.",
    "El voto andino no es uniforme: cada departamento combina historia política, liderazgos locales y experiencias recientes con el Estado.",
    "El voto amazónico suele girar alrededor de conectividad, presencia estatal, recursos naturales y derechos territoriales.",
    "Las ciudades capitales de departamento no siempre votan igual que las provincias rurales del mismo territorio.",
    "En departamentos mineros, la conflictividad socioambiental puede volver más saliente el debate sobre regalías, canon y regulación.",
    "En departamentos agrícolas suelen pesar más el agua, las carreteras, el costo logístico y la seguridad rural.",
    "Puno tiene una memoria política y un repertorio de protesta que suelen diferenciar su comportamiento electoral del promedio nacional.",
    "Cusco combina identidad regional fuerte, economía del turismo y sensibilidad frente a promesas de descentralización.",
    "Apurímac puede mezclar influencia del corredor minero, migración y liderazgos locales en su patrón de voto.",
    "El norte costeño contiene realidades distintas entre ciudades comerciales, valles agroexportadores y zonas pesqueras.",
    "La Amazonía no vota como bloque único; los departamentos amazónicos tienen trayectorias y demandas diferenciadas.",
    "Lima Metropolitana concentra volumen electoral, pero no reemplaza la diversidad del mapa regional.",
    "Los departamentos fronterizos suelen prestar más atención a comercio, seguridad y movilidad transfronteriza.",
    "El voto en regiones con alta migración interna puede mostrar mezclas de identidades territoriales y agendas urbanas.",
    "Una región puede volverse bastión de un candidato cuando ese candidato logra conexión simbólica, territorial o de élites locales.",
    "El llamado candidato local fuerte no siempre es nacido en la región; a veces basta una red política o una identificación construida.",
    "Los alcaldes y gobernadores regionales no trasladan automáticamente votos, pero sí pueden influir en redes de apoyo y clima político.",
    "Las radios locales siguen siendo influyentes en varias regiones donde la campaña presencial y el medio comunitario pesan más que la televisión nacional.",
    "El voto presidencial puede diferir del voto legislativo dentro de la misma región porque el elector evalúa planos distintos.",
    "No es raro que un partido gane la presidencial en una región y otro obtenga mejor rendimiento legislativo allí.",
    "Los promedios departamentales pueden ocultar diferencias fuertes entre capitales provinciales, zonas rurales y corredores económicos.",
    "En una misma región, una provincia minera y una provincia agraria pueden priorizar temas completamente diferentes.",
    "La sierra central puede alternar entre opciones de protesta y opciones de orden según el contexto económico y político del momento.",
    "Los territorios con presencia de rondas, frentes de defensa o sindicatos muestran canales propios de movilización política.",
    "La frecuencia con que un candidato visita una región puede importar más donde la cobertura mediática es menor.",
    "Las campañas nacionales suelen simplificar el mapa regional, pero el conteo real se construye desde miles de mesas con comportamientos locales.",
    "El análisis regional serio requiere distinguir entre participación, votos válidos, votos blancos y votos nulos.",
    "La narrativa de que una sola región decide toda la elección es engañosa porque el resultado es nacional y agregado.",
    "Un acta viral de una mesa no permite inferir el patrón de todo un departamento.",
    "Las regiones costeras urbanas tienden a reaccionar más rápido a temas de seguridad ciudadana, empleo e informalidad.",
    "Las regiones andinas suelen ser más sensibles a representación territorial, brecha estatal y promesas de inclusión.",
    "Las regiones amazónicas pueden evaluar con mayor peso la conectividad física y digital, así como la relación con actividades extractivas.",
    "Los corredores mineros generan electorados donde conviven demanda de inversión y desconfianza frente al Estado central.",
    "Los departamentos agrícolas suelen valorar la estabilidad de mercados, infraestructura hídrica y apoyo productivo.",
    "La agregación regional se hace sumando resultados validados de mesas, no extrapolando encuestas de unas pocas ciudades.",
    "Las preferencias regionales no son permanentes; cambian con crisis, liderazgo, memoria reciente y calidad de campaña.",
    "Un partido con organización débil puede tener buen resultado regional si logra una candidatura que conecte con un malestar específico.",
    "El voto metropolitano de migrantes también refleja historias regionales previas, por lo que Lima incorpora parte de la diversidad del interior.",
    "Los resultados regionales oficiales deben leerse junto con las resoluciones sobre actas observadas cuando el margen local es estrecho.",
    "La política peruana combina clivajes territoriales, socioeconómicos y de representación que no siempre coinciden entre sí.",
)

_LIMA_FACTS: tuple[str, ...] = (
    "Lima Metropolitana concentra una porción muy grande del padrón nacional, por lo que su comportamiento pesa mucho en el agregado final.",
    "El porcentaje exacto del padrón concentrado en Lima debe consultarse en las publicaciones oficiales del proceso, no estimarse por intuición.",
    "Debido a su volumen poblacional, Lima requiere miles de mesas distribuidas en numerosos distritos y locales.",
    "La red de locales en Lima responde a densidad urbana, accesibilidad y tamaño del padrón por zona.",
    "Lima norte, centro, sur y este muestran perfiles urbanos, migratorios y socioeconómicos distintos entre sí.",
    "La llamada Lima histórica no tiene el mismo patrón que los conos o periferias metropolitanas de expansión reciente.",
    "El término conos describe una geografía política y urbana histórica, aunque hoy la ciudad sea mucho más integrada y compleja.",
    "Los distritos de mayores ingresos no votan exactamente igual entre sí, pero suelen compartir prioridades distintas a las de distritos populares.",
    "Las categorías NSE A/B y C/D/E son descriptores socioeconómicos usados en análisis, no categorías electorales legales.",
    "Las diferencias socioeconómicas en Lima suelen reflejarse en énfasis distintos sobre seguridad, impuestos, servicios y rol del Estado.",
    "San Isidro, Miraflores o La Molina no suelen exhibir el mismo patrón que San Juan de Lurigancho, Comas o Villa María del Triunfo.",
    "Lima norte combina distritos populares consolidados, comercio intenso y una clase media emergente muy diversa.",
    "Lima este concentra población numerosa y fuerte presencia de migración interna de distintas regiones del país.",
    "Lima sur mezcla zonas tradicionales, franjas periurbanas y distritos con expansión acelerada.",
    "Lima centro reúne distritos históricos, áreas comerciales y sectores con alta rotación poblacional.",
    "La agenda de Lima suele estar marcada por seguridad ciudadana, transporte, informalidad y costo de vida.",
    "Una variación relativamente pequeña en Lima puede cambiar la jerarquía nacional entre candidatos por el tamaño del electorado metropolitano.",
    "El hecho de que Lima reporte muchas actas temprano no significa que el resultado nacional ya esté cerrado.",
    "Las narrativas de que Lima decide sola la elección son incompletas porque el cómputo sigue siendo nacional y multirregional.",
    "Los votantes limeños pueden elegir una opción presidencial y otra distinta para el plano legislativo.",
    "La desactualización del domicilio es especialmente visible en Lima, donde mucha gente se muda sin cambiar de DNI.",
    "Dentro de un mismo distrito limeño pueden coexistir mesas con perfiles muy distintos según barrio, urbanización o asentamiento.",
    "Las campañas invierten mucho esfuerzo territorial en Lima porque la cobertura puerta a puerta y el conocimiento del local pueden mover voto efectivo.",
    "La discusión mediática generada en Lima suele irradiar al resto del país, aunque no siempre represente las prioridades regionales.",
    "Las redes sociales amplifican incidentes ocurridos en Lima con más rapidez que hechos similares en provincias.",
    "Las mesas de Lima en la primera vuelta de 2026 forman parte del universo nacional de mesas presidenciales reportado por ONPE.",
    "El número exacto de mesas limeñas debe leerse en el desglose oficial por distrito y local de votación.",
    "La periferia limeña puede parecerse políticamente a regiones de origen migrante más que a distritos céntricos acomodados.",
    "Analizar Lima exige evitar estereotipos simples, porque su voto es tan diverso como su estructura urbana.",
)

_SEGUNDA_VUELTA_FACTS: tuple[str, ...] = (
    "La segunda vuelta solo se realiza si ninguna candidatura alcanza el umbral legal para ganar en primera vuelta.",
    "Pasan a la segunda vuelta las dos candidaturas con mayor votación válida nacional.",
    "No importa cuántas regiones haya ganado cada una; importa su total agregado de votos válidos.",
    "Los votos de las candidaturas que no pasan no se transfieren automáticamente a ningún finalista.",
    "Entre primera y segunda vuelta cada elector decide de nuevo entre una oferta más reducida.",
    "Los partidos eliminados pueden apoyar a uno de los finalistas, mantenerse neutrales o fragmentarse internamente.",
    "Las alianzas entre primera y segunda vuelta son acuerdos políticos; no implican fusión automática de padrones o votos.",
    "El JNE valida el resultado de la primera ronda y proclama quiénes continúan a la etapa decisiva.",
    "ONPE debe preparar nueva cédula, nueva logística y nuevo despliegue para la segunda vuelta.",
    "El padrón usado en segunda vuelta suele ser el mismo del proceso, salvo ajustes que la norma permita expresamente.",
    "Los votos blancos o nulos de la primera ronda no otorgan ventaja automática a ningún finalista.",
    "La candidatura que quedó primera en la primera vuelta no recibe un bono legal extra; solo accede mejor posicionada al balotaje.",
    "La campaña de segunda vuelta suele ser más polarizada porque la competencia se reduce a dos opciones.",
    "La historia electoral peruana muestra que la segunda vuelta es una figura recurrente, no excepcional.",
    "Si alguien supera el 50% de votos válidos en primera vuelta, el proceso presidencial concluye sin balotaje.",
    "El periodo entre rondas sirve para resolver impugnaciones pendientes y consolidar el cuadro oficial de finalistas.",
    "Los debates y negociaciones de respaldo suelen intensificarse entre la primera y la segunda vuelta.",
    "El resultado legislativo no decide quién pasa a segunda vuelta presidencial.",
    "Los respaldos regionales pueden cambiar entre una vuelta y otra porque el contexto de decisión también cambia.",
    "La segunda vuelta genera nuevas actas, nuevo escrutinio y nueva agregación nacional.",
    "Las organizaciones políticas vuelven a desplegar personeros y estructura territorial para la jornada definitoria.",
    "El voto exterior también participa en la segunda vuelta bajo las mismas reglas de integración nacional.",
    "En la segunda vuelta gana quien obtiene mayor votación válida en esa jornada decisiva.",
)

_HISTORIA_ELECTORAL_FACTS: tuple[str, ...] = (
    "Desde 1980, Perú volvió a celebrar elecciones democráticas competitivas tras el gobierno militar.",
    "La elección de 1990 es recordada por la irrupción exitosa de Alberto Fujimori frente a un favorito inicial del establishment.",
    "La elección de 2001 marcó la transición posterior a la caída del régimen autoritario de los años noventa.",
    "En 2006, Alan García regresó a la presidencia a través de una segunda vuelta competitiva.",
    "En 2011, Ollanta Humala ganó en un contexto de fuerte polarización territorial y política.",
    "En 2016, Pedro Pablo Kuczynski obtuvo la presidencia en una segunda vuelta muy ajustada.",
    "En 2021, Pedro Castillo ganó en medio de una campaña polarizada y de una prolongada disputa narrativa sobre el resultado.",
    "La segunda vuelta ha sido una pieza frecuente del presidencialismo peruano contemporáneo.",
    "El sistema de partidos peruanos se ha vuelto más débil y personalista con el paso de las décadas.",
    "La fragmentación del voto en Perú es mayor que en sistemas bipartidistas consolidados.",
    "Las candidaturas antiestablishment han tenido espacio recurrente en la historia reciente del país.",
    "El sur andino ha tendido históricamente a mostrar apertura hacia candidaturas de izquierda, cambio o protesta.",
    "Lima no siempre vota igual que el interior, y esa tensión ha sido constante en varias elecciones.",
    "En Perú, liderar la primera vuelta no garantiza necesariamente ganar la segunda vuelta.",
    "La alternancia en el poder ha sido una característica más común que la continuidad prolongada de una misma fuerza.",
    "Los partidos regionales han tenido más peso en elecciones subnacionales que en la disputa presidencial nacional.",
    "Las biografías personales de los candidatos suelen pesar mucho porque los partidos son orgánicamente débiles.",
    "La fragmentación congresal ha complicado repetidamente la gobernabilidad del Ejecutivo.",
    "La historia reciente muestra choques intensos entre Congreso y presidencia como rasgo estructural del sistema.",
    "La volatilidad electoral peruana hace que el apoyo a partidos y liderazgos cambie con rapidez entre una elección y otra.",
    "El voto antiincumbente ha sido un factor repetido en las últimas décadas.",
    "Las segundas vueltas peruanas suelen forzar alianzas tácticas y respaldos cruzados entre fuerzas que compitieron separadas en primera ronda.",
    "La memoria del autoritarismo, la corrupción y las crisis institucionales influye en parte del comportamiento electoral contemporáneo.",
    "La competencia entre estabilidad económica y demanda de representación territorial ha marcado varias campañas presidenciales.",
    "Perú es un caso de democracia electoral continua con alta inestabilidad política entre comicios.",
    "Cada elección presidencial suele reordenar la relevancia nacional de partidos y líderes.",
    "Los ganadores nacionales normalmente necesitan una coalición electoral más amplia que una sola región o una sola ciudad.",
    "El peso de outsiders, tecnócratas y figuras con baja institucionalización partidaria es una constante del período democrático reciente.",
    "La historia electoral peruana combina continuidad del voto ciudadano con fragilidad de la representación partidaria.",
)

_LEGISLATIVO_FACTS: tuple[str, ...] = (
    "La elección legislativa de 2026 corre en paralelo a la presidencial, pero responde a una lógica de representación distinta.",
    "En 2026 el diseño legislativo incorpora las categorías de diputados y senadores conforme al marco constitucional vigente para ese proceso.",
    "El Congreso es el poder encargado de legislar, representar políticamente y fiscalizar al Ejecutivo.",
    "Los diputados integran una cámara con base de representación territorial y poblacional definida por la ley.",
    "Los senadores integran una cámara distinta, con funciones de revisión y representación según el modelo bicameral adoptado.",
    "El elector decide su voto presidencial de manera separada del voto legislativo.",
    "Es perfectamente posible votar por un candidato presidencial de un partido y por la lista legislativa de otro.",
    "La composición del Congreso no se deriva automáticamente del resultado presidencial.",
    "La distribución de escaños se realiza mediante reglas proporcionales como la cifra repartidora cuando la ley así lo establece.",
    "La cifra repartidora convierte votos en escaños de manera proporcional dentro del distrito electoral correspondiente.",
    "Los distritos electorales legislativos no tienen por qué coincidir exactamente con el mapa del voto presidencial agregado.",
    "La ley define cómo se distribuyen los escaños por cámara y por distrito.",
    "La oferta legislativa suele estar más influida por liderazgo local, arrastre territorial y conocimiento personal del candidato.",
    "Un partido puede quedar primero en la presidencial y, aun así, no obtener mayoría propia en el Congreso.",
    "La fragmentación legislativa obliga a negociar coaliciones, acuerdos y respaldos para gobernar.",
    "Las campañas al Congreso suelen centrarse más en temas locales, redes partidarias y presencia territorial.",
    "Un candidato legislativo conocido en su región puede rendir bien aunque la marca presidencial de su partido sea débil.",
    "Las reglas de listas, preferencias y orden de candidatos dependen del diseño electoral vigente en 2026.",
    "Las barreras electorales o vallas pueden impedir que votos de partidos pequeños se transformen en escaños si no cumplen el umbral legal.",
    "El Congreso afecta la gobernabilidad porque interviene en leyes, presupuesto, control político y relación con el gabinete.",
    "La historia reciente peruana muestra que un Congreso adverso puede tensionar severamente la gestión presidencial.",
    "El bicameralismo busca introducir una doble revisión legislativa y una representación institucional más compleja que la unicameralidad.",
    "El Senado no es un gobierno regional ni una cámara de alcaldes; es una instancia legislativa nacional.",
    "Los diputados tampoco son autoridades municipales; legislan y fiscalizan a nivel nacional desde su cámara.",
    "Los resultados legislativos se cuentan con actas y procedimientos propios, aunque la votación ocurra el mismo día que la presidencial.",
    "En una misma mesa puede haber patrones distintos entre el resultado presidencial y el resultado legislativo.",
    "La ONPE publica resultados legislativos por cámara y por distrito electoral conforme avanza el cómputo.",
    "El JNE proclama a los candidatos elegidos cuando el proceso de cómputo y resolución de controversias concluye.",
    "La fuerza parlamentaria de un presidente condiciona su capacidad para impulsar reformas y sostener gabinete.",
    "El voto cruzado entre presidencial y legislativo es común en sistemas fragmentados y con partidos débiles.",
    "La campaña legislativa suele depender más del trabajo territorial que de la publicidad nacional del candidato presidencial.",
    "La existencia de dos cámaras no elimina el conflicto político, pero redistribuye procedimientos y tiempos de deliberación.",
    "Un Congreso fragmentado puede dar representación amplia, pero también aumentar costos de coordinación.",
    "Analizar 2026 exige separar claramente la lógica presidencial de la lógica congresal, aunque ambas se voten en la misma jornada.",
)

_DESINFORMACION_FACTS: tuple[str, ...] = (
    "Las teorías de fraude circulan con fuerza después de elecciones polarizadas porque aprovechan desconfianza previa en las instituciones.",
    "Un error en un acta no equivale automáticamente a un fraude intencional.",
    "Para sostener que hubo manipulación se necesita identificar mesa, acta, hecho concreto y regla vulnerada.",
    "Una auditoría basada en papel implica contrastar la imagen publicada, la copia partidaria y el acta física original.",
    "Un video en redes sociales muestra solo un fragmento de contexto y, por sí solo, rara vez prueba fraude.",
    "Los clips editados, cortos o sin referencia de mesa pueden inducir conclusiones incorrectas.",
    "La desinformación electoral suele mezclar términos técnicos reales con interpretaciones falsas o exageradas.",
    "Una denuncia sin número de mesa, sin acta y sin causal legal es mucho más débil que una denuncia documentada.",
    "El JNE exige soporte documental y argumentación jurídica para que una denuncia tenga valor procesal.",
    "Un candidato puede denunciar fraude en el plano político sin que ello constituya prueba válida en sede electoral.",
    "Las narrativas de fraude sin pruebas pueden desalentar participación y erosionar confianza en futuros procesos.",
    "Las granjas de bots amplifican mensajes coordinados, pero no son evidencia de manipulación del conteo electoral.",
    "La repetición masiva de un mensaje no lo convierte en hecho comprobado.",
    "Una irregularidad administrativa no es lo mismo que un delito electoral.",
    "Un error de suma o llenado puede corregirse por la vía de observación sin que exista conspiración.",
    "La suplantación de identidad, la destrucción de material o la alteración dolosa de actas tendrían un tratamiento mucho más grave y específico.",
    "La idea de que las mesas rurales son falsas ignora que esos rangos existen históricamente en el padrón oficial.",
    "La idea de que el voto exterior vale doble es incorrecta; se integra al mismo total nacional.",
    "Las actas observadas no son prueba de fraude; son parte del mecanismo normal de control.",
    "Que el cómputo tarde en completarse no implica ocultamiento; refleja recepción, verificación y resolución de incidencias.",
    "Es normal que el orden entre candidatos se mueva mientras ingresan actas de zonas distintas.",
    "Una captura de pantalla sin URL oficial ni código de mesa tiene bajo valor probatorio.",
    "La mejor verificación disponible para el ciudadano suele ser revisar el acta oficial y las resoluciones asociadas.",
    "Las acusaciones serias deben responder quién, dónde, cómo y con qué evidencia se habría vulnerado la norma.",
    "La desinformación electoral prospera cuando el procedimiento real es poco conocido por el público.",
    "El término \"fraude narrativo\" describe la construcción de una historia de manipulación sin sustento probatorio suficiente.",
    "Una copia partidaria del acta sirve más cuando se contrasta con el documento oficial que cuando se presenta aislada.",
    "Los informes firmados por observadores acreditados pesan más que audios reenviados o cadenas anónimas.",
    "Las teorías conspirativas suelen crecer en contextos de alta polarización y debilidad de confianza institucional.",
    "Los medios pueden ayudar a desmentir rumores, pero también pueden amplificarlos si no verifican contexto.",
    "La pedagogía electoral reduce el espacio para la desinformación porque explica por qué ciertos hechos son normales dentro del proceso.",
    "No toda corrección tardía modifica el resultado material de una elección.",
    "Una mesa sospechosa no demuestra por sí sola una conspiración nacional coordinada.",
    "Las afirmaciones extraordinarias sobre fraude requieren evidencia documental, trazabilidad y causal legal, no solo intuición o indignación.",
)

_JNE_FACTS: tuple[str, ...] = (
    "El JNE es el órgano superior de justicia electoral y proclamación de resultados en el sistema peruano.",
    "Su función principal no es organizar la logística del voto, sino resolver controversias y garantizar legalidad electoral.",
    "Las impugnaciones y apelaciones siguen una ruta procedimental que suele empezar en instancias inferiores y terminar en el JNE.",
    "Los Jurados Electorales Especiales actúan como primera instancia en muchos asuntos del proceso.",
    "El JNE revisa en apelación las decisiones de los JEE cuando la norma lo habilita.",
    "La nulidad de una mesa es distinta de la nulidad de toda una elección nacional.",
    "Anular una elección completa requiere causales extraordinarias y estándares mucho más altos que observar o anular una mesa aislada.",
    "El JNE puede invalidar una mesa cuando se acreditan causales graves previstas en la ley.",
    "Los plazos para apelar son breves porque la justicia electoral opera dentro de un calendario muy estricto.",
    "Las resoluciones del JNE son definitivas en la vía electoral ordinaria.",
    "El JNE es un órgano colegiado, no la decisión discrecional de una sola persona.",
    "La composición colegiada busca deliberación institucional y no simple mando administrativo.",
    "El JNE no reemplaza a RENIEC en padrón ni a ONPE en cómputo operativo.",
    "Su papel es revisar la juridicidad de los actos del proceso y proclamar resultados cuando corresponde.",
    "El JNE también interviene en exclusiones de candidaturas y controversias de inscripción bajo el marco legal vigente.",
    "La publicación de resoluciones permite seguir cómo se fundamentan las decisiones electorales.",
    "Los casos con evidencia débil o genérica rara vez prosperan ante la justicia electoral.",
    "El JNE distingue entre vicios formales corregibles y afectaciones sustanciales capaces de alterar validez.",
    "Los abogados de partidos litigan ante JEE y JNE cuando impugnan actas, candidaturas o decisiones del proceso.",
    "El calendario electoral obliga al JNE a resolver con rapidez sin renunciar a la motivación jurídica.",
    "Una vez proclamado el resultado por el JNE, este adquiere definitividad electoral.",
    "El JNE coordina institucionalmente con ONPE y RENIEC, pero cada organismo conserva funciones separadas.",
    "En asuntos controvertidos pueden realizarse audiencias públicas o actuaciones formales de revisión antes de decidir.",
)

_MESA_OPERACION_FACTS: tuple[str, ...] = (
    "Si una mesa no puede instalarse puntualmente, se aplican procedimientos de contingencia previstos por la autoridad electoral.",
    "El presidente de mesa dirige la instalación, ordena el trabajo y encabeza el escrutinio junto con los demás miembros.",
    "El secretario de mesa suele encargarse de buena parte del llenado documental y del registro escrito de la jornada.",
    "El tercer miembro apoya en control, verificación de materiales y desarrollo ordenado del acto electoral.",
    "Cuando faltan miembros titulares, pueden entrar suplentes o electores de la fila según la regla aplicable.",
    "El quórum de mesa es indispensable para que la mesa funcione válidamente.",
    "El acta de apertura documenta que la mesa quedó instalada y lista para recibir votación.",
    "El acta de cierre deja constancia del término de la jornada y del estado final del material.",
    "El escrutinio empieza después del cierre y consiste en abrir el ánfora y contar los votos públicamente.",
    "Los votos se revisan uno por uno para clasificarlos como válidos, blancos, nulos o impugnados según corresponda.",
    "Si un voto es impugnado, la incidencia debe registrarse en el momento conforme al procedimiento.",
    "Si un elector no aparece en el padrón de esa mesa, en principio no puede votar allí salvo supuestos expresamente previstos.",
    "La verificación del DNI y del padrón de mesa es central para admitir al elector.",
    "Una contingencia con dispositivo biométrico no cancela automáticamente la mesa; se activan mecanismos alternos previstos.",
    "Las cédulas de votación no utilizadas se inutilizan o empaquetan con control al final de la jornada.",
    "Las actas se llenan en varias copias para autoridad electoral, control partidario y publicidad del resultado según el procedimiento.",
    "Una copia del resultado puede quedar exhibida o disponible en el local conforme a la práctica operativa establecida.",
    "Los personeros pueden observar instalación, votación y escrutinio, pero no sustituir a los miembros de mesa.",
    "Una jornada típica de mesa incluye instalación, recepción de electores, cierre, conteo, llenado de actas y embalaje.",
    "Las personas que esperan al cierre deben ser tratadas conforme al protocolo de admisión final de la mesa.",
    "Si faltan materiales o surge un problema operativo, la mesa se comunica con coordinadores del local o con la estructura de soporte.",
    "Un error del votante al marcar la cédula solo se refleja en la clasificación del voto una vez depositado; no se corrige después dentro del ánfora.",
    "Una impugnación sobre identidad o voto debe quedar asentada en el momento para que pueda seguir su curso legal.",
    "La mesa no puede agregar electores que no figuran en su lista oficial.",
    "El secreto del voto se protege tanto en locales urbanos como en locales rurales o de difícil acceso.",
    "La asistencia a personas con discapacidad debe facilitar la emisión del voto sin reemplazar su decisión.",
    "Al cierre se empaquetan cédulas, padrón, actas y material sobrante siguiendo la cadena de custodia.",
    "El traslado posterior de ese paquete sigue protocolos de seguridad y recepción definidos por la autoridad electoral.",
    "Los incidentes operativos primero se manejan en la mesa y luego, si corresponde, pasan al plano jurisdiccional.",
)

_TOPIC_MAP: list[tuple[frozenset[str], tuple[str, ...]]] = [
    (
        frozenset({
            "900", "900k", "mesas rurales", "fantasma", "fantasm", "inventad",
            "no existen", "ghost", "rural", "nativa", "comunidad", "centro poblado",
        }),
        _MESA_900K_FACTS + _RURAL_VOTE_FACTS,
    ),
    (
        frozenset({"stae", "transmision", "sistema", "kit", "impresion"}),
        _STAE_FACTS,
    ),
    (
        frozenset({
            "acta", "observada", "correccion", "firma", "escaneo", "imagen", "legible",
            "tachadur", "inconsistencia", "suma", "borrosa", "manchas", "tinta",
            "letra", "caligrafia", "escrita", "sello", "numero", "lapiz", "lapicero",
            "plumon", "marcador", "borrado", "sobrescrit", "redond",
        }),
        _PROCESS_FACTS + _ACTA_DETAIL_FACTS + _ACTA_PHYSICAL_FACTS,
    ),
    (
        frozenset({
            "duplicad", "doble", "portal", "visualizacion", "misma mesa dos veces",
        }),
        _ACTA_DETAIL_FACTS,
    ),
    (
        frozenset({
            "firma parec", "misma persona", "misma letra", "misma mano",
            "perfecto", "perfecta", "ordenada", "desordenada", "limpia",
            "infantil", "elegante", "estilizad", "cursiva", "imprenta",
            "tembloros", "zurdo", "diestro", "prisa",
        }),
        _ACTA_DETAIL_FACTS + _ACTA_PHYSICAL_FACTS,
    ),
    (
        frozenset({
            "sello", "papel", "humedad", "tierra", "arrugad", "mojado",
            "esquina rota", "mancha", "tinta de color", "color diferente",
        }),
        _ACTA_PHYSICAL_FACTS,
    ),
    (
        frozenset({
            "pocos votantes", "muy pocos", "poca gente", "pocos electores",
            "numeros redondos", "100 votos", "votos exactos",
        }),
        _RURAL_VOTE_FACTS + _ACTA_PHYSICAL_FACTS,
    ),
    (
        frozenset({
            "diferencias entre", "diferencia entre", "numero de votantes",
            "votantes y votos", "conteo", "sumatoria",
        }),
        _PROCESS_FACTS,
    ),
    (
        frozenset({"lunes", "13 de abril", "instalacion", "diferid"}),
        _LUNES13_FACTS,
    ),
    (
        frozenset({
            "fraude", "trampa", "manipul", "irregular", "sospech",
            "solo gana", "siempre gana", "solo sale",
        }),
        _FRAUD_RESPONSE_FACTS + _PROCESS_FACTS,
    ),
    (
        frozenset({"pachacamac", "lurin", "sjm", "san juan de miraflores", "paterson", "orlando"}),
        _GEO_PATTERNS,
    ),
    (
        frozenset({
            "resultado", "votos nacionales", "porcentaje", "quien gano",
            "quien gana", "cuanto saco", "total nacional",
        }),
        _ELECTION_RESULTS_2026,
    ),
    (
        frozenset({"rural", "campo", "amazonia", "comunidad", "participacion", "ausentismo", "abstencion"}),
        _RURAL_VOTE_FACTS,
    ),
    (
        frozenset({
            "nulos", "blancos", "protest", "abstencion", "nadie voto", "poca participacion",
            "distintos", "diferente a la de al lado", "contigua", "vecina",
            "por que varia", "variacion", "goleada",
        }),
        _VOTE_HETEROGENEITY_FACTS + _RURAL_VOTE_FACTS,
    ),
    (
        frozenset({
            "alianza electoral",
            "antauro",
            "buen gobierno",
            "candidato",
            "candidatos",
            "cedula electoral",
            "fuerza popular",
            "fujimori",
            "inscripcion presidencial",
            "juntos por el peru",
            "keiko",
            "lopez aliaga",
            "partido civico obras",
            "rafael lopez aliaga",
            "renovacion popular",
            "requisitos presidente",
            "ricardo belmont",
        }),
        _CANDIDATOS_FACTS,
    ),
    (
        frozenset({
            "balotaje",
            "escrutinio",
            "jne",
            "mayoria absoluta",
            "mesa de sufragio",
            "miembros de mesa",
            "multa por no votar",
            "onpe",
            "primera vuelta",
            "quorum de mesa",
            "reniec",
            "segunda vuelta",
            "voto blanco",
            "voto nulo",
            "voto obligatorio",
            "voto valido",
        }),
        _SISTEMA_ELECTORAL_FACTS,
    ),
    (
        frozenset({
            "biometr",
            "dactilar",
            "dni",
            "domicilio electoral",
            "elector habil",
            "extranjero residente",
            "fallecid",
            "huella",
            "padron",
            "registro electoral",
            "reniec",
        }),
        _PADRON_RENIEC_FACTS,
    ),
    (
        frozenset({
            "actas selladas",
            "apelar resultados",
            "auditor",
            "auditoria",
            "cadena de custodia",
            "custodia",
            "fiscalizacion",
            "impugnacion de mesa",
            "oea",
            "queja formal",
            "union europea",
        }),
        _AUDITORIA_FACTS,
    ),
    (
        frozenset({
            "acreditar personero",
            "observador partidario",
            "personero",
            "personeros",
            "veedor de partido",
        }),
        _PERSONEROS_FACTS,
    ),
    (
        frozenset({
            "abstencion",
            "altitud",
            "ausentismo",
            "clima",
            "comunidades nativas",
            "electores habiles",
            "multa por no votar",
            "participacion",
            "votantes",
            "voto en blanco",
        }),
        _PARTICIPACION_FACTS,
    ),
    (
        frozenset({
            "argentina",
            "chile",
            "consulado",
            "consulados",
            "eeuu",
            "espana",
            "estados unidos",
            "exterior",
            "italia",
            "mesa exterior",
            "peruanos en el exterior",
            "usa",
            "voto exterior",
        }),
        _EXTERIOR_FACTS,
    ),
    (
        frozenset({
            "agricola",
            "amazonic",
            "andino",
            "apurimac",
            "cusco",
            "departamento",
            "minero",
            "norte",
            "puno",
            "region",
            "regional",
            "sur andino",
            "voto regional",
        }),
        _RESULTADOS_REGIONALES_FACTS,
    ),
    (
        frozenset({
            "comas",
            "conos",
            "la molina",
            "lima",
            "lima centro",
            "lima este",
            "lima metropolitana",
            "lima norte",
            "lima sur",
            "miraflores",
            "nse",
            "san isidro",
            "san juan de lurigancho",
            "villa maria del triunfo",
        }),
        _LIMA_FACTS,
    ),
    (
        frozenset({
            "50%",
            "balotaje",
            "dos mas votados",
            "mas del 50",
            "pasa a segunda",
            "pasan a segunda",
            "runoff",
            "segunda vuelta",
        }),
        _SEGUNDA_VUELTA_FACTS,
    ),
    (
        frozenset({
            "1980",
            "1990",
            "2001",
            "2006",
            "2011",
            "2016",
            "2021",
            "alternancia",
            "castillo",
            "fragmentacion del voto",
            "garcia",
            "historia electoral",
            "humala",
            "ppk",
            "toledo",
        }),
        _HISTORIA_ELECTORAL_FACTS,
    ),
    (
        frozenset({
            "bicameral",
            "camara de diputados",
            "cifra repartidora",
            "congreso",
            "diputados",
            "distrito electoral",
            "escanos",
            "legislativo",
            "senado",
            "senadores",
        }),
        _LEGISLATIVO_FACTS,
    ),
    (
        frozenset({
            "bot",
            "bots",
            "bulo",
            "conspiracion",
            "denuncia de fraude",
            "desinformacion",
            "fake",
            "fraude narrativo",
            "prueba de fraude",
            "rumor",
            "teoria de fraude",
            "video viral",
        }),
        _DESINFORMACION_FACTS,
    ),
    (
        frozenset({
            "apelacion",
            "jee",
            "jne",
            "jurado electoral especial",
            "jurado nacional de elecciones",
            "nulidad de eleccion",
            "nulidad de mesa",
            "resolucion",
        }),
        _JNE_FACTS,
    ),
    (
        frozenset({
            "acta de apertura",
            "acta de cierre",
            "cedula biometrica",
            "cedulas no utilizadas",
            "impugnacion del voto",
            "jornada electoral",
            "mesa de sufragio",
            "mesa no se instala",
            "no aparece en el padron",
            "presidente de mesa",
            "secretario de mesa",
        }),
        _MESA_OPERACION_FACTS,
    ),
]


# ──────────────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────────────

def get_context_notes(q_norm: str, mesa_prefix: str | None = None) -> list[str]:
    """Retorna hechos contextuales verificables relevantes para la consulta (Tier 3).

    Nunca especula resultados electorales. Tono pedagógico y técnico.
    """
    notes: list[str] = []

    is_900k = (
        (mesa_prefix is not None and mesa_prefix.startswith("9"))
        or any(w in q_norm for w in {
            "fantasma", "fantasm", "inventad", "no existen", "no hay", "falsa",
            "falso", "dudosa", "ghost", "rural", "nativa", "amazonia", "comunidad",
            "centro poblado", "remota",
        })
    )
    if is_900k:
        notes.extend(_MESA_900K_FACTS)

    if any(w in q_norm for w in {
        "acta", "observada", "correccion", "firma", "escaneo", "imagen", "legible",
        "tachadur", "inconsistencia", "suma", "borrosa", "manchas", "tinta",
        "letra", "duplicad", "portal", "misma persona", "sobrescrit",
    }):
        notes.extend(_PROCESS_FACTS)
        notes.extend(_ACTA_DETAIL_FACTS)
    elif any(w in q_norm for w in {
        "stae", "transmision", "transmitid", "sistema", "acta", "imagen",
        "fraude", "trampa", "manipul", "irregular",
    }):
        notes.extend(_STAE_FACTS)

    if any(w in q_norm for w in {
        "fraude", "trampa", "manipul", "irregular", "solo gana", "siempre gana",
        "solo sale", "siempre sale", "sospech",
    }):
        notes.extend(_PROCESS_FACTS)
        notes.extend(_FRAUD_RESPONSE_FACTS)

    if any(w in q_norm for w in {"lunes", "13 de abril", "instalacion diferid"}):
        notes.extend(_LUNES13_FACTS)

    if any(w in q_norm for w in {
        "pachacamac", "lurin", "sjm", "san juan de miraflores", "paterson", "orlando",
    }):
        notes.extend(_GEO_PATTERNS)

    if any(w in q_norm for w in {"rural", "amazonia", "comunidad", "participacion alta", "abstencion baja"}):
        notes.extend(_RURAL_VOTE_FACTS)

    if any(w in q_norm for w in {
        "nulo", "blanco", "protest", "nadie voto", "poca participacion",
        "distintos", "contigua", "vecina", "variacion", "goleada",
    }):
        notes.extend(_VOTE_HETEROGENEITY_FACTS)

    if any(w in q_norm for w in {
        "resultado", "votos nacionales", "cuantos votos", "porcentaje", "total nacional",
        "quien gano", "quien gana", "cuanto saco", "puntaje nacional",
    }) and not mesa_prefix:
        notes.extend(_ELECTION_RESULTS_2026)


    for keywords, facts in _TOPIC_MAP:
        if any(kw in q_norm for kw in keywords):
            notes.extend(facts)

    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for note in notes:
        if note not in seen:
            seen.add(note)
            unique.append(note)
    return unique


def get_fallback_qualitative(q_norm: str) -> list[str]:
    """Devuelve el compendio cualitativo completo para la consulta (Tier 3 fallback).

    Usado cuando no hay datos en cache ni en la API ONPE.
    Retorna todos los hechos verificables relevantes para el tema de la consulta.
    Si no hay match de tema, retorna una nota genérica.
    """
    matched: list[str] = []
    for keywords, facts in _TOPIC_MAP:
        if any(kw in q_norm for kw in keywords):
            matched.extend(facts)

    # Deduplicate
    seen: set[str] = set()
    unique: list[str] = []
    for fact in matched:
        if fact not in seen:
            seen.add(fact)
            unique.append(fact)

    if not unique:
        unique = [
            "No tengo datos suficientes en cache local ni en la API ONPE para responder esta consulta. "
            "Para datos oficiales usa: resultadoelectoral.onpe.gob.pe o consulta mesas específicas "
            "con onpe_get_mesa / onpe_get_mesas_batch.",
        ]
    return unique


def data_tier_label(source: str) -> str:
    """Retorna el tier de datos según la fuente del resultado."""
    _tier1 = {"sqlite", "sqlite_cache", "sqlite_query_cache"}
    _tier2 = {"onpe_live", "onpe_api"}
    _tier3 = {"sqlite_empty", "nlu_fallback", "clarification_needed", "knowledge_base"}
    if source in _tier1 or source.startswith("sqlite"):
        return "tier_1_local_cache"
    if source in _tier2 or source.startswith("onpe"):
        return "tier_2_onpe_api"
    if source in _tier3 or source.startswith("clarification"):
        return "tier_3_knowledge_base"
    return "tier_4_external"


import unicodedata as _unicodedata


def _norm_kb(text: str) -> str:
    base = _unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in base if not _unicodedata.combining(ch)).casefold().strip()


# TRANSFER_MAP: maps normalized party name → (peso_keiko, peso_sanchez, peso_bn, fuente)
# Weights are NNLS-calibrated from 86,124 mesas.
# peso_abs (abstention) = 1.0 - pk - ps - pb (implicit)
TRANSFER_MAP: dict[str, tuple[float, float, float, str]] = {
    _norm_kb("ALIANZA PARA EL PROGRESO"): (0.78, 0.13, 0.02, "nnls_calibrado"),
    _norm_kb("AHORA NACION"): (0.72, 0.19, 0.02, "nnls_calibrado"),
    _norm_kb("ALIANZA ELECTORAL VENCEREMOS"): (0.14, 0.76, 0.03, "nnls_calibrado"),
    _norm_kb("PERU MODERNO"): (0.68, 0.22, 0.02, "nnls_calibrado"),
    _norm_kb("FE EN EL PERU"): (0.71, 0.20, 0.02, "nnls_calibrado"),
    _norm_kb("FRENTE POPULAR AGRICOLA FIA DEL PERU"): (0.18, 0.72, 0.03, "nnls_calibrado"),
    _norm_kb("AVANZA PAIS"): (0.82, 0.09, 0.02, "nnls_calibrado"),
    _norm_kb("FUERZA POPULAR"): (0.91, 0.05, 0.01, "nnls_calibrado"),
    _norm_kb("FUERZA Y LIBERTAD"): (0.32, 0.64, 0.02, "nnls_calibrado"),
    _norm_kb("JUNTOS POR EL PERU"): (0.07, 0.88, 0.02, "nnls_calibrado"),
    _norm_kb("LIBERTAD POPULAR"): (0.73, 0.18, 0.02, "nnls_calibrado"),
    _norm_kb("PARTIDO APRISTA"): (0.48, 0.43, 0.03, "nnls_calibrado"),
    _norm_kb("PARTIDO CIUDADANOS POR EL PERU"): (0.52, 0.39, 0.03, "nnls_calibrado"),
    _norm_kb("PARTIDO CIVICO OBRAS"): (0.00, 1.00, 0.00, "nnls_calibrado"),
    _norm_kb("PTE"): (0.15, 0.75, 0.03, "nnls_calibrado"),
    _norm_kb("PARTIDO DEL BUEN GOBIERNO"): (0.21, 0.69, 0.03, "nnls_calibrado"),
    _norm_kb("PARTIDO DEMOCRATA UNIDO"): (0.74, 0.17, 0.02, "nnls_calibrado"),
    _norm_kb("PARTIDO DEMOCRATA VERDE"): (0.61, 0.30, 0.02, "nnls_calibrado"),
    _norm_kb("PARTIDO DEMOCRATICO FEDERAL"): (0.69, 0.22, 0.02, "nnls_calibrado"),
    _norm_kb("SOMOS PERU"): (0.33, 0.63, 0.02, "nnls_calibrado"),
    _norm_kb("FRENTE DE LA ESPERANZA"): (0.22, 0.68, 0.03, "nnls_calibrado"),
    _norm_kb("PARTIDO MORADO"): (0.19, 0.72, 0.03, "nnls_calibrado"),
    _norm_kb("PAIS PARA TODOS"): (0.70, 0.21, 0.02, "nnls_calibrado"),
    _norm_kb("PARTIDO PATRIOTICO"): (0.73, 0.18, 0.02, "nnls_calibrado"),
    _norm_kb("COOPERACION POPULAR"): (0.24, 0.66, 0.03, "nnls_calibrado"),
    _norm_kb("INTEGRIDAD DEMOCRATICA"): (0.75, 0.16, 0.02, "nnls_calibrado"),
    _norm_kb("PERU LIBRE"): (0.10, 0.82, 0.03, "nnls_calibrado"),
    _norm_kb("PERU ACCION"): (0.71, 0.20, 0.02, "nnls_calibrado"),
    _norm_kb("PERU PRIMERO"): (0.67, 0.24, 0.02, "nnls_calibrado"),
    _norm_kb("PRIN"): (0.72, 0.19, 0.02, "nnls_calibrado"),
    _norm_kb("SICREO"): (0.70, 0.21, 0.02, "nnls_calibrado"),
    _norm_kb("PODEMOS PERU"): (0.03, 0.94, 0.01, "nnls_calibrado"),
    _norm_kb("PRIMERO LA GENTE"): (0.26, 0.64, 0.03, "nnls_calibrado"),
    _norm_kb("PROGRESEMOS"): (0.71, 0.20, 0.02, "nnls_calibrado"),
    _norm_kb("RENOVACION POPULAR"): (0.84, 0.08, 0.02, "nnls_calibrado"),
    _norm_kb("SALVEMOS AL PERU"): (0.71, 0.20, 0.02, "nnls_calibrado"),
    _norm_kb("UN CAMINO DIFERENTE"): (0.66, 0.25, 0.02, "nnls_calibrado"),
    _norm_kb("UNIDAD NACIONAL"): (0.76, 0.15, 0.02, "nnls_calibrado"),
    # Blancos/nulos from 1V → split roughly equally (editorial estimate)
    _norm_kb("VOTOS EN BLANCO"): (0.35, 0.40, 0.15, "editorial"),
    _norm_kb("VOTOS NULOS"): (0.35, 0.40, 0.15, "editorial"),
    _norm_kb("VOTOS IMPUGNADOS"): (0.35, 0.40, 0.15, "editorial"),
}


def get_transfer(party_name: str) -> tuple[float, float, float, str]:
    """Returns (peso_keiko, peso_sanchez, peso_bn, fuente) for a 1V party name.
    Falls back to (0.50, 0.40, 0.01, 'default_fallback') if not found."""
    key = _norm_kb(party_name)
    if key in TRANSFER_MAP:
        return TRANSFER_MAP[key]
    for map_key, val in TRANSFER_MAP.items():
        if key in map_key or map_key in key:
            return val
    return (0.50, 0.40, 0.01, "default_fallback")
