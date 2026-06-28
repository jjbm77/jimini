## Purpose

Definir los requisitos para el motor de tareas recurrentes del sistema Jimini. Cubre la tabla de plantillas de recurrencia con modelado ad-hoc de criterios temporales, la evaluación diaria vía pg_cron con zona horaria configurable, la generación idempotente de tareas, la creación de plantillas por comando `/recurrencia` (vía IA), la confirmación con botón [Deshacer], el listado de plantillas activas, y la configuración de zona horaria.

## Requirements

### Requirement: Tabla de plantillas de recurrencia

El sistema SHALL mantener una tabla `plantillas_recurrencia` con columnas para modelado ad-hoc de criterios temporales (`tipo_recurrencia`, `intervalo`, `dia_del_mes`, `mes_del_anio`, `dia_de_semana`), offset de vencimiento (`dias_para_vencer`), ciclo de vida (`activa`, `fecha_inicio`, `fecha_fin`, `ultima_generacion`), y metadatos de tarea (`titulo`, `ambito`, `proyecto`, `prioridad`, `origen`).

#### Scenario: Plantilla mensual simple
- **WHEN** se inserta una plantilla con `tipo_recurrencia='mensual'`, `intervalo=1`, `dia_del_mes=5`, `dias_para_vencer=0`
- **THEN** el sistema la acepta y almacena
- **AND** la plantilla generará una tarea el día 5 de cada mes con `fecha_vence` = mismo día

#### Scenario: Plantilla trimestral con intervalo
- **WHEN** se inserta una plantilla con `tipo_recurrencia='mensual'`, `intervalo=3`, `dia_del_mes=15`, `dias_para_vencer=7`
- **THEN** el sistema la acepta y almacena
- **AND** la plantilla generará una tarea el día 15 de cada tercer mes (contado desde `fecha_inicio`) con `fecha_vence` = día 15 + 7 días

#### Scenario: Plantilla de fin de mes
- **WHEN** se inserta una plantilla con `tipo_recurrencia='mensual'`, `dia_del_mes=0`
- **THEN** el sistema la acepta y almacena
- **AND** la plantilla generará una tarea el último día de cada mes (28/29 en febrero, 30 en meses cortos, 31 en meses largos)

#### Scenario: Plantilla semanal
- **WHEN** se inserta una plantilla con `tipo_recurrencia='semanal'`, `dia_de_semana=1` (lunes), `dias_para_vencer=0`
- **THEN** el sistema la acepta y almacena
- **AND** la plantilla generará una tarea cada lunes con `fecha_vence` = mismo lunes

#### Scenario: Plantilla anual
- **WHEN** se inserta una plantilla con `tipo_recurrencia='anual'`, `dia_del_mes=15`, `mes_del_anio=3`
- **THEN** el sistema la acepta y almacena
- **AND** la plantilla generará una tarea el 15 de marzo de cada año

#### Scenario: Validación de consistencia según tipo_recurrencia
- **WHEN** se intenta insertar una plantilla con `tipo_recurrencia='semanal'` y `dia_de_semana IS NULL`
- **THEN** el sistema la rechaza vía CHECK constraint
- **WHEN** se intenta insertar una plantilla con `tipo_recurrencia='mensual'` y `dia_del_mes IS NULL`
- **THEN** el sistema la rechaza vía CHECK constraint
- **WHEN** se intenta insertar una plantilla con `tipo_recurrencia='anual'` y (`dia_del_mes IS NULL` OR `mes_del_anio IS NULL`)
- **THEN** el sistema la rechaza vía CHECK constraint

### Requirement: Evaluación diaria idempotente con zona horaria configurable

El sistema SHALL ejecutar un job pg_cron diariamente a las 05:01 UTC que invoque la función `evaluar_plantillas_recurrencia()`. La función SHALL leer la zona horaria de `configuracion_sistema` (clave `zona_horaria_default`, default `America/Lima`), calcular `fecha_hoy` en esa zona, evaluar las plantillas activas contra `fecha_hoy`, y generar tareas para las que coincidan. La función SHALL ser idempotente: si se ejecuta múltiples veces el mismo día, no generará duplicados.

#### Scenario: Evaluación normal diaria
- **WHEN** el job pg_cron dispara a las 05:01 UTC (00:01 Lima)
- **AND** la zona horaria configurada es `America/Lima`
- **THEN** la función calcula `fecha_hoy` = fecha actual en Lima
- **AND** evalúa todas las plantillas con `activa=true`, `fecha_inicio <= fecha_hoy`, y (`fecha_fin IS NULL` OR `fecha_fin >= fecha_hoy`)
- **AND** para cada plantilla que coincide con `fecha_hoy`, inserta una tarea en `tareas` con `estado='pendiente'` y `fecha_vence = fecha_hoy + dias_para_vencer`
- **AND** actualiza `ultima_generacion = fecha_hoy` en la plantilla

#### Scenario: Idempotencia — job corre dos veces el mismo día
- **WHEN** la función se ejecuta dos veces en el mismo `fecha_hoy`
- **AND** la primera ejecución ya seteó `ultima_generacion = fecha_hoy` en una plantilla
- **THEN** la segunda ejecución no selecciona esa plantilla (filtro `ultima_generacion IS DISTINCT FROM fecha_hoy`)
- **AND** no se generan tareas duplicadas

#### Scenario: Skip missed — servidor estuvo caído un día
- **WHEN** el job no ejecutó el día X por caída del servidor
- **AND** el servidor levanta el día X+1
- **THEN** la función del día X+1 solo evalúa `fecha_hoy = X+1`
- **AND** las recurrencias que coincidían con el día X no se generan (no hay catch-up)

#### Scenario: Plantilla inactiva no genera
- **WHEN** una plantilla tiene `activa=false`
- **AND** la función evalúa el día correspondiente a sus criterios temporales
- **THEN** la función no la selecciona (filtro `activa=true`)
- **AND** no se genera tarea

#### Scenario: Plantilla fuera de rango de fechas
- **WHEN** una plantilla tiene `fecha_fin` anterior a `fecha_hoy`
- **THEN** la función no la selecciona
- **AND** no se genera tarea

### Requirement: Evaluación de criterios temporales con intervalo

La función `evaluar_plantillas_recurrencia()` SHALL evaluar los criterios temporales de cada plantilla según su `tipo_recurrencia` y `intervalo`. Para `intervalo > 1`, la función SHALL verificar que el número de períodos transcurridos desde `fecha_inicio` sea múltiplo de `intervalo`.

#### Scenario: Mensual con intervalo=1
- **WHEN** una plantilla mensual con `intervalo=1`, `dia_del_mes=5` se evalúa en `fecha_hoy` con día 5
- **THEN** la función verifica que `EXTRACT(DAY FROM fecha_hoy) = 5`
- **AND** como `intervalo=1`, no aplica filtro de multiplo
- **AND** genera la tarea

#### Scenario: Mensual con intervalo=3 (trimestral)
- **WHEN** una plantilla mensual con `intervalo=3`, `dia_del_mes=15`, `fecha_inicio='2026-01-15'` se evalúa en `fecha_hoy='2026-04-15'`
- **THEN** la función verifica que `EXTRACT(DAY FROM fecha_hoy) = 15`
- **AND** calcula `meses_transcurridos = (2026-2026)*12 + (4-1) = 3`
- **AND** verifica `3 % 3 = 0` → coincide
- **AND** genera la tarea

#### Scenario: Mensual con intervalo=3 no coincide en mes intermedio
- **WHEN** la misma plantilla se evalúa en `fecha_hoy='2026-02-15'`
- **THEN** `meses_transcurridos = 1`, `1 % 3 != 0` → no coincide
- **AND** no genera la tarea

#### Scenario: Fin de mes (dia_del_mes=0)
- **WHEN** una plantilla con `dia_del_mes=0` se evalúa en `fecha_hoy='2026-02-28'` (último día de febrero 2026)
- **THEN** la función verifica que `fecha_hoy` es el último día del mes
- **AND** genera la tarea

#### Scenario: Semanal con intervalo=2 (quincenal)
- **WHEN** una plantilla semanal con `intervalo=2`, `dia_de_semana=1`, `fecha_inicio='2026-01-05'` (lunes) se evalúa en `fecha_hoy='2026-01-19'` (lunes)
- **THEN** la función calcula `semanas_transcurridas = 2`
- **AND** verifica `2 % 2 = 0` → coincide
- **AND** genera la tarea

### Requirement: Generación de tarea desde plantilla

Cuando una plantilla coincide con `fecha_hoy`, la función SHALL insertar una nueva fila en `tareas` con: `id` único derivado del ID de la plantilla y la fecha, `titulo` y metadatos copiados de la plantilla, `origen='recurrencia'`, `fecha_vence = fecha_hoy + dias_para_vencer`, `estado='pendiente'`. La inserción y el update de `ultima_generacion` SHALL ocurrir en la misma transacción.

#### Scenario: Tarea generada con vencimiento mismo día
- **WHEN** una plantilla con `dias_para_vencer=0` coincide con `fecha_hoy`
- **THEN** la tarea generada tiene `fecha_vence = fecha_hoy`

#### Scenario: Tarea generada con vencimiento post-fechado
- **WHEN** una plantilla con `dias_para_vencer=7` coincide con `fecha_hoy`
- **THEN** la tarea generada tiene `fecha_vence = fecha_hoy + 7 días`

#### Scenario: ID único de tarea generada
- **WHEN** la plantilla con `id=42` coincide con `fecha_hoy='2026-07-05'`
- **THEN** la tarea generada tiene `id = 'rec-42-2026-07-05'`
- **AND** si la función se ejecuta de nuevo el mismo día, el ID ya existe y la idempotencia previene el duplicado

#### Scenario: Transacción atómica
- **WHEN** la función inserta la tarea y actualiza `ultima_generacion`
- **AND** ocurre un error después del INSERT pero antes del UPDATE
- **THEN** la transacción se revierte (ROLLBACK)
- **AND** ni la tarea ni el update de `ultima_generacion` persisten

### Requirement: Creación de plantillas vía comando `/recurrencia`

El webhook SHALL detectar mensajes de Telegram que comiencen con `/recurrencia` y setear `tipo_mensaje='recurrencia'` en el INSERT al buffer. El texto después del comando SHALL ser el input para la estructuración por IA. El worker SHALL usar un system prompt distinto para `tipo_mensaje='recurrencia'` que extraiga los campos de la plantilla e inserte en `plantillas_recurrencia` (no en `tareas`).

#### Scenario: Usuario crea recurrencia mensual
- **WHEN** el usuario envía `/recurrencia Pagar luz el día 5 de cada mes, personal`
- **THEN** el webhook inserta en el buffer con `tipo_mensaje='recurrencia'`, `mensaje_raw='Pagar luz el día 5 de cada mes, personal'`
- **AND** el worker estructura con el system prompt de plantilla
- **AND** inserta en `plantillas_recurrencia` con `titulo='Pagar luz'`, `tipo_recurrencia='mensual'`, `dia_del_mes=5`, `ambito='personal'`
- **AND** responde al usuario con confirmación + botón [Deshacer]

#### Scenario: Usuario crea recurrencia de fin de mes
- **WHEN** el usuario envía `/recurrencia Pagar alquiler a fin de cada mes`
- **THEN** la IA estructura `dia_del_mes=0` (convención fin de mes)
- **AND** inserta la plantilla
- **AND** la confirmación muestra "Día: último día del mes"

#### Scenario: Usuario crea recurrencia semanal
- **WHEN** el usuario envía `/recurrencia Revisión de proyecto cada lunes, laboral, prioridad alta`
- **THEN** la IA estructura `tipo_recurrencia='semanal'`, `dia_de_semana=1`, `ambito='laboral'`, `prioridad='alta'`
- **AND** inserta la plantilla
- **AND** la confirmación muestra "Cada lunes"

#### Scenario: Mensaje de voz con comando recurrencia
- **WHEN** el usuario envía un voice note que transcribe como "/recurrencia pagar luz día 5 cada mes"
- **THEN** el webhook detecta `/recurrencia` en la transcripción
- **AND** setea `tipo_mensaje='recurrencia'` en el buffer
- **AND** el worker estructura como plantilla (no como tarea)

### Requirement: Confirmación de creación con botón [Deshacer]

Tras insertar una plantilla, el worker SHALL enviar un mensaje de confirmación al `chat_id` del usuario vía Telegram con el detalle de la plantilla creada y un botón inline [Deshacer]. Si el usuario presiona el botón, el sistema SHALL eliminar la plantilla y confirmar la eliminación.

#### Scenario: Confirmación exitosa
- **WHEN** el worker inserta una plantilla exitosamente
- **THEN** envía un mensaje al `chat_id` con: título, tipo de recurrencia, día, ámbito, prioridad, días para vencer
- **AND** adjunta un botón inline [Deshacer] con callback_data que incluya el ID de la plantilla

#### Scenario: Usuario presiona [Deshacer]
- **WHEN** el usuario presiona el botón [Deshacer]
- **THEN** el callback handler elimina la plantilla con `DELETE FROM plantillas_recurrencia WHERE id = <id>`
- **AND** responde al callback con "✅ Recurrencia eliminada"
- **AND** edita el mensaje original para indicar que fue deshecha

#### Scenario: Botón [Deshacer] presionado después de que la plantilla ya generó tareas
- **WHEN** el usuario presiona [Deshacer] después de que la plantilla ya generó una o más tareas
- **THEN** el sistema elimina la plantilla (no generará más tareas)
- **AND** NO elimina las tareas ya generadas (permanecen como pendientes o completadas)
- **AND** la confirmación indica "Recurrencia eliminada. Las tareas ya generadas permanecen."

### Requirement: Comando `/recurrencias` para listar plantillas activas

El webhook SHALL detectar el comando `/recurrencias` (sin argumento) y responder con una lista de las plantillas activas. La lista SHALL incluir: título, tipo de recurrencia, día, y próximo vencimiento calculado.

#### Scenario: Listar recurrencias activas
- **WHEN** el usuario envía `/recurrencias`
- **THEN** el webhook consulta `SELECT * FROM plantillas_recurrencia WHERE activa=true ORDER BY id`
- **AND** responde con una lista formateada, una por línea:
  `📌 #<id> "Pagar luz" — Mensual, día 5 — Personal — Vence en 0 días`
- **AND** si no hay plantillas activas, responde "No tienes recurrencias activas."

#### Scenario: Comando no va al buffer
- **WHEN** el usuario envía `/recurrencias`
- **THEN** el webhook responde directamente sin insertar en el buffer
- **AND** no invoca la IA

### Requirement: Configuración de zona horaria

El sistema SHALL leer la zona horaria de `configuracion_sistema` (clave `zona_horaria_default`). El valor por defecto SHALL ser `America/Lima`. La función `evaluar_plantillas_recurrencia()` SHALL usar esta zona para calcular `fecha_hoy`.

#### Scenario: Zona horaria configurada
- **WHEN** `configuracion_sistema` tiene `clave='zona_horaria_default'`, `valor_texto='America/Lima'`
- **AND** la función se ejecuta a las 05:01 UTC del 5 de julio
- **THEN** `fecha_hoy` = 5 de julio (00:01 Lima = 05:01 UTC)

#### Scenario: Zona horaria no configurada (default)
- **WHEN** `configuracion_sistema` no tiene la clave `zona_horaria_default`
- **THEN** la función usa el default `America/Lima`
- **AND** el comportamiento es idéntico al escenario anterior

#### Scenario: Zona horaria cambiada
- **WHEN** el valor de `zona_horaria_default` se cambia a `Europe/Madrid`
- **THEN** la función evalúa contra la fecha en Madrid
- **AND** las recurrencias se generan según el calendario percibido en Madrid
