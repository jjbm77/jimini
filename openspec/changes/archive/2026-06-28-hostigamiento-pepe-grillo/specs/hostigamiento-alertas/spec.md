## ADDED Requirements

### Requirement: Worker de hostigamiento con evaluación continua

El sistema SHALL ejecutar un worker asíncrono (`worker_loop_hostigamiento`) en el mismo proceso FastAPI, concurrente con el worker del buffer vía `asyncio.gather`. El worker SHALL evaluar cada 60 segundos las tareas con `estado='pendiente'` y `fecha_vence IS NOT NULL`, calcular su nivel de hostigamiento, y enviar alertas por Telegram cuando corresponda según el nivel y la frecuencia de repetición.

#### Scenario: Worker evalúa tareas pendientes
- **WHEN** el worker de hostigamiento ejecuta una iteración
- **THEN** consulta la base de datos por tareas con `estado='pendiente'` AND `fecha_vence IS NOT NULL`
- **AND** para cada tarea, calcula el nivel de hostigamiento según `fecha_vence` y `NOW()`
- **AND** si el nivel subió respecto a `nivel_hostigamiento` actual, envía una alerta con el nuevo nivel
- **AND** si el nivel no subió pero toca repetir (frecuencia expirada), envía una alerta del mismo nivel

#### Scenario: Tarea sin fecha_vence no es hostigada
- **WHEN** una tarea tiene `fecha_vence IS NULL`
- **THEN** el worker no la selecciona para evaluación
- **AND** no se envía ninguna alerta para esa tarea

#### Scenario: Tarea con proxima_alerta_bloqueada_hasta en el futuro
- **WHEN** una tarea tiene `proxima_alerta_bloqueada_hasta > NOW()`
- **THEN** el worker no la selecciona para evaluación
- **AND** la tarea será reevaluada cuando `proxima_alerta_bloqueada_hasta <= NOW()`

#### Scenario: Proceso FastAPI se reinicia
- **WHEN** el proceso FastAPI se reinicia después de una caída
- **THEN** el worker de hostigamiento reanuda la evaluación
- **AND** las tareas que debieron ser alertadas durante la caída se evalúan en la próxima iteración (las que cambiaron de nivel se alertan con el nuevo nivel)

### Requirement: Cálculo de nivel de hostigamiento por días de vencimiento

El sistema SHALL calcular el nivel de hostigamiento de una tarea según los días transcurridos entre `NOW()` y `fecha_vence`. La función SQL `calcular_nivel_hostigamiento(p_fecha_vence, p_now)` SHALL retornar un entero 0-4 según la siguiente tabla: nivel 0 si `fecha_vence` es 1 día en el futuro (aviso preventivo), nivel 1 si es el día del vencimiento, nivel 2 si está vencida 1-2 días, nivel 3 si está vencida 3-6 días, nivel 4 si está vencida 7+ días.

#### Scenario: Nivel 0 — aviso preventivo (día anterior)
- **WHEN** `fecha_vence = CURRENT_DATE + 1` (mañana)
- **THEN** `calcular_nivel_hostigamiento` retorna 0

#### Scenario: Nivel 1 — vence hoy
- **WHEN** `fecha_vence = CURRENT_DATE` (hoy)
- **THEN** `calcular_nivel_hostigamiento` retorna 1

#### Scenario: Nivel 2 — vencida 1-2 días
- **WHEN** `fecha_vence = CURRENT_DATE - 1` (ayer)
- **AND** `fecha_vence = CURRENT_DATE - 2` (anteayer)
- **THEN** `calcular_nivel_hostigamiento` retorna 2

#### Scenario: Nivel 3 — vencida 3-6 días
- **WHEN** `fecha_vence` está entre `CURRENT_DATE - 3` y `CURRENT_DATE - 6`
- **THEN** `calcular_nivel_hostigamiento` retorna 3

#### Scenario: Nivel 4 — vencida 7+ días
- **WHEN** `fecha_vence <= CURRENT_DATE - 7`
- **THEN** `calcular_nivel_hostigamiento` retorna 4

#### Scenario: Tarea no vencida y no es día anterior
- **WHEN** `fecha_vence > CURRENT_DATE + 1` (más de 1 día en el futuro)
- **THEN** `calcular_nivel_hostigamiento` retorna -1 (no alertar)

### Requirement: Frecuencia de repetición por nivel

El sistema SHALL repetir las alertas dentro de cada nivel según una frecuencia definida: nivel 0 una sola vez (no se repite), nivel 1 cada 4 horas, nivel 2 cada 3 horas, nivel 3 cada 4 horas, nivel 4 diario a las 09:00. La frecuencia se implementa seteando `proxima_alerta_bloqueada_hasta = NOW() + frecuencia_nivel(nivel)` tras enviar cada alerta.

#### Scenario: Nivel 1 — repetición cada 4 horas
- **WHEN** el worker envía una alerta de nivel 1 a las 09:00
- **THEN** setea `proxima_alerta_bloqueada_hasta = 13:00` (09:00 + 4h)
- **AND** la próxima alerta de nivel 1 se enviará a las 13:00 (si el nivel no ha subido)

#### Scenario: Nivel 2 — repetición cada 3 horas
- **WHEN** el worker envía una alerta de nivel 2 a las 09:00
- **THEN** setea `proxima_alerta_bloqueada_hasta = 12:00` (09:00 + 3h)
- **AND** la próxima repetición será a las 12:00

#### Scenario: Nivel 4 — repetición diaria a las 09:00
- **WHEN** el worker envía una alerta de nivel 4 a las 09:00 del día X
- **THEN** setea `proxima_alerta_bloqueada_hasta = día X+1 09:00`
- **AND** la próxima alerta será a las 09:00 del día siguiente

#### Scenario: Nivel 0 — no se repite
- **WHEN** el worker envía una alerta de nivel 0 (aviso preventivo)
- **THEN** setea `proxima_alerta_bloqueada_hasta` al día del vencimiento a las 09:00
- **AND** no se envían más alertas de nivel 0 (al día siguiente el nivel sube a 1 automáticamente)

### Requirement: Horario activo 09:00-21:00 en zona horaria del usuario

El worker de hostigamiento SHALL enviar alertas únicamente entre las 09:00 y las 21:00 en la zona horaria configurada (`configuracion_sistema.zona_horaria_default`, default `America/Lima`). Fuera de ese rango, el worker no envía alertas pero el cálculo de nivel sí avanza.

#### Scenario: Dentro del horario activo
- **WHEN** la hora actual en zona del usuario es entre 09:00 y 21:00
- **AND** una tarea requiere alerta
- **THEN** el worker envía la alerta inmediatamente

#### Scenario: Fuera del horario activo
- **WHEN** la hora actual en zona del usuario es 22:00
- **AND** una tarea requiere alerta
- **THEN** el worker no envía la alerta
- **AND** la evalúa nuevamente en la próxima iteración (a las 09:00 se enviará con el nivel correspondiente)

#### Scenario: Tarea que vence a las 22:00
- **WHEN** una tarea vence a las 22:00 y el horario activo termina a las 21:00
- **THEN** no se envía alerta el día del vencimiento (nivel 1 no se dispara)
- **AND** al día siguiente a las 09:00, el nivel ya es 2 (vencida 1 día) y se envía alerta de nivel 2

### Requirement: Botones de snooze (RF07) en niveles 1 y 2

Las alertas de nivel 1 y 2 SHALL incluir botones inline `[⏳ Posponer 2 horas]` y `[📅 Mañana]`. Al presionar un botón de snooze, el sistema SHALL setear `proxima_alerta_bloqueada_hasta` al momento correspondiente sin alterar `fecha_vence`. Snooze detiene temporalmente la escalada de hostigamiento.

#### Scenario: Usuario pospone 2 horas
- **WHEN** el usuario presiona `[⏳ Posponer 2 horas]` en una alerta de nivel 1 o 2
- **THEN** el sistema ejecuta `UPDATE tareas SET proxima_alerta_bloqueada_hasta = NOW() + INTERVAL '2 hours'` WHERE id = <tarea>
- **AND** `fecha_vence` permanece sin cambios
- **AND** `nivel_hostigamiento` permanece sin cambios
- **AND** el worker no volverá a alertar esa tarea hasta que expire el snooze

#### Scenario: Usuario pospuesta para mañana
- **WHEN** el usuario presiona `[📅 Mañana]` en una alerta de nivel 1 o 2
- **THEN** el sistema ejecuta `UPDATE tareas SET proxima_alerta_bloqueada_hasta = TOMORROW 09:00` en zona del usuario WHERE id = <tarea>
- **AND** `fecha_vence` permanece sin cambios
- **AND** el worker no volverá a alertar hasta mañana a las 09:00

#### Scenario: Snooze expira y el nivel subió
- **WHEN** el snooze expira (`proxima_alerta_bloqueada_hasta <= NOW()`)
- **AND** el nivel calculado es mayor que `nivel_hostigamiento` actual
- **THEN** el worker envía alerta con el nuevo nivel (la escalada continúa donde se quedó)

#### Scenario: Snooze no disponible en niveles 3-4
- **WHEN** el worker envía una alerta de nivel 3 o 4
- **THEN** la alerta NO incluye botones de snooze
- **AND** solo incluye botones de resolución ([Completar], [Descartar])

### Requirement: Botones de resolución — Completar y Descartar

Todas las alertas SHALL incluir un botón `[✅ Completar]`. Las alertas de niveles 3 y 4 SHALL además incluir un botón `[🗑️ Descartar]`. Al presionar [Completar], el sistema SHALL setear `estado='completado'`. Al presionar [Descartar], el sistema SHALL setear `estado='descartado'` (un nuevo estado distinto de `pendiente` y `completado`).

#### Scenario: Usuario completa tarea desde alerta
- **WHEN** el usuario presiona `[✅ Completar]` en cualquier nivel
- **THEN** el sistema ejecuta `UPDATE tareas SET estado='completado'` WHERE id = <tarea>
- **AND** la tarea sale del pool de hostigamiento (no será evaluada nuevamente)

#### Scenario: Usuario descarta tarea desde alerta nivel 3
- **WHEN** el usuario presiona `[🗑️ Descartar]` en una alerta de nivel 3 o 4
- **THEN** el sistema ejecuta `UPDATE tareas SET estado='descartado'` WHERE id = <tarea>
- **AND** la tarea sale del pool de hostigamiento
- **AND** `fecha_vence` permanece sin cambios (preserva el registro de cuándo vencía)

#### Scenario: Botón [Descartar] no aparece en niveles 0-2
- **WHEN** el worker envía una alerta de nivel 0, 1 o 2
- **THEN** la alerta NO incluye botón [Descartar]
- **AND** solo incluye [Completar] (niveles 0) o [Completar] + [Snooze] (niveles 1-2)

### Requirement: Estado `descartado` en tareas

El sistema SHALL soportar el estado `descartado` en `tareas.estado`, distinto de `pendiente` (activa) y `completado` (se hizo). `descartado` significa "se reconoce que la tarea ya no aplica pero no se completó". El worker de hostigamiento SHALL excluir tareas con `estado='descartado'` de la evaluación.

#### Scenario: Tarea descartada no es hostigada
- **WHEN** una tarea tiene `estado='descartado'`
- **THEN** el worker no la selecciona para evaluación
- **AND** no se envían alertas para esa tarea

#### Scenario: Tarea descartada preserva fecha_vence
- **WHEN** una tarea es descartada
- **THEN** `fecha_vence` permanece con su valor original
- **AND** el registro histórico preserva cuándo debía vencerse

### Requirement: Mensajes de alerta formateados por nivel

Cada nivel de hostigamiento SHALL tener un mensaje de alerta distinto con tono y emojis acorde a la urgencia. El mensaje SHALL incluir el título de la tarea y, cuando aplique, los días de vencimiento.

#### Scenario: Mensaje nivel 0 (aviso preventivo)
- **WHEN** el worker envía una alerta de nivel 0
- **THEN** el mensaje es: `📅 Recuerda: '{titulo}' vence mañana.`

#### Scenario: Mensaje nivel 1 (vence hoy)
- **WHEN** el worker envía una alerta de nivel 1
- **THEN** el mensaje es: `⚠️ '{titulo}' vence HOY. ¿Lo resolvemos?`

#### Scenario: Mensaje nivel 2 (vencida corto)
- **WHEN** el worker envía una alerta de nivel 2
- **THEN** el mensaje incluye los días de vencimiento: `🔴 '{titulo}' está vencida (N días). Hay que resolverlo.`

#### Scenario: Mensaje nivel 4 (vencida largo)
- **WHEN** el worker envía una alerta de nivel 4
- **THEN** el mensaje fuerza al usuario a actuar: `📈 '{titulo}' lleva una semana+ vencida. Necesito que la completes o descartes.`