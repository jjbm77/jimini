## ADDED Requirements

### Requirement: Detección de comandos `/hoy`, `/semana`, `/mes` en el webhook

El webhook SHALL detectar los comandos `/hoy`, `/semana`, y `/mes` (con o sin argumento numérico) además de los comandos ya implementados (`/tareas`, `/recurrencia`, `/recurrencias`, `/vacaciones`, `/finde`). Los tres comandos SHALL ser respondidos directamente sin insertar en el buffer.

#### Scenario: Comando /hoy
- **WHEN** el webhook recibe `/hoy`
- **THEN** consulta tareas con `fecha_vence = CURRENT_DATE` (zona del usuario)
- **AND** responde al usuario con la lista formateada
- **AND** no inserta nada en el buffer

#### Scenario: Comando /semana
- **WHEN** el webhook recibe `/semana`
- **THEN** consulta tareas con `fecha_vence` entre `CURRENT_DATE` y `CURRENT_DATE + 7`, más vencidas
- **AND** responde al usuario con la lista agrupada por día
- **AND** no inserta nada en el buffer

#### Scenario: Comando /mes
- **WHEN** el webhook recibe `/mes` o `/mes N`
- **THEN** calcula el grid del mes correspondiente
- **AND** responde al usuario con el calendario ASCII
- **AND** no inserta nada en el buffer