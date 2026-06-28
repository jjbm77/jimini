## ADDED Requirements

### Requirement: Estado `descartado` en el schema de tareas

El sistema SHALL soportar el estado `descartado` en `tareas.estado` además de `pendiente` y `completado`. El CHECK constraint de la columna `estado` SHALL incluir `descartado` como valor válido.

#### Scenario: Tarea puede tener estado descartado
- **WHEN** se ejecuta `UPDATE tareas SET estado='descartado' WHERE id=X`
- **THEN** la operación es aceptada por el CHECK constraint
- **AND** la tarea permanece en la tabla con `estado='descartado'`

#### Scenario: Tareas descartadas no aparecen en queries de pendientes
- **WHEN** se consulta `SELECT * FROM tareas WHERE estado='pendiente'`
- **THEN** las tareas con `estado='descartado'` no aparecen en los resultados

### Requirement: Detección de comandos `/vacaciones`, `/finde`, `/tareas` en el webhook

El webhook SHALL detectar los comandos `/vacaciones`, `/finde`, y `/tareas` además de los comandos ya implementados (`/recurrencia`, `/recurrencias`). Los comandos `/vacaciones` y `/finde` SHALL ser respondidos directamente sin insertar en el buffer. El comando `/tareas` SHALL ser respondido directamente sin insertar en el buffer.

#### Scenario: Comando /vacaciones con fecha
- **WHEN** el webhook recibe `/vacaciones 15/07/2026`
- **THEN** activa el modo vacaciones en `configuracion_sistema`
- **AND** responde al usuario con confirmación
- **AND** no inserta nada en el buffer

#### Scenario: Comando /finde
- **WHEN** el webhook recibe `/finde`
- **THEN** activa el modo finde en `configuracion_sistema`
- **AND** responde al usuario con confirmación
- **AND** no inserta nada en el buffer

#### Scenario: Comando /tareas
- **WHEN** el webhook recibe `/tareas`
- **THEN** consulta tareas pendientes y responde con la lista formateada
- **AND** no inserta nada en el buffer

### Requirement: Callbacks de hostigamiento (snooze, completar, descartar)

El webhook SHALL procesar `callback_query` updates con prefijos `snooze_2h:`, `snooze_manana:`, `completar:`, y `descartar:` además del ya existente `recurrencia_deshacer:`. Cada callback SHALL ejecutar el UPDATE correspondiente en `tareas` y responder al callback con confirmación.

#### Scenario: Callback snooze_2h
- **WHEN** el webhook recibe `callback_query.data = "snooze_2h:tarea-123"`
- **THEN** ejecuta `UPDATE tareas SET proxima_alerta_bloqueada_hasta = NOW() + INTERVAL '2 hours' WHERE id='tarea-123'`
- **AND** responde al callback con "⏳ Pospuesto 2 horas"

#### Scenario: Callback snooze_manana
- **WHEN** el webhook recibe `callback_query.data = "snooze_manana:tarea-123"`
- **THEN** ejecuta `UPDATE tareas SET proxima_alerta_bloqueada_hasta = TOMORROW 09:00 WHERE id='tarea-123'`
- **AND** responde al callback con "📅 Pospuesto para mañana"

#### Scenario: Callback completar
- **WHEN** el webhook recibe `callback_query.data = "completar:tarea-123"`
- **THEN** ejecuta `UPDATE tareas SET estado='completado' WHERE id='tarea-123'`
- **AND** responde al callback con "✅ Completada"

#### Scenario: Callback descartar
- **WHEN** el webhook recibe `callback_query.data = "descartar:tarea-123"`
- **THEN** ejecuta `UPDATE tareas SET estado='descartado' WHERE id='tarea-123'`
- **AND** responde al callback con "🗑️ Descartada"

#### Scenario: Callback con tarea inexistente
- **WHEN** el webhook recibe un callback con un ID de tarea que no existe
- **THEN** responde al callback con "Esta tarea ya no existe."