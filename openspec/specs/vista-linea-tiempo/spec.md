## Purpose

Definir los requisitos para la vista de línea de tiempo de tareas en formato calendario vía comandos de Telegram: `/hoy` (día actual), `/semana` (próximos 7 días), y `/mes [N]` (vista mensual compacta con grid ASCII). Esta capability reemplaza la necesidad de sincronización con Google Calendar externo, manteniendo toda la interacción dentro de Pepe Grillo.

## Requirements

### Requirement: Comando `/hoy` para ver tareas del día actual

El webhook SHALL detectar el comando `/hoy` (sin argumento) y responder con una lista de tareas pendientes con `fecha_vence` igual a la fecha actual en zona del usuario. La respuesta SHALL ser compacta y usar emojis por ámbito.

#### Scenario: /hoy con tareas hoy
- **WHEN** el usuario envía `/hoy`
- **AND** hay tareas con `estado='pendiente'` y `fecha_vence = CURRENT_DATE` (zona del usuario)
- **THEN** el sistema responde con las tareas listadas, una por línea, con emoji de ámbito

#### Scenario: /hoy sin tareas hoy
- **WHEN** el usuario envía `/hoy`
- **AND** no hay tareas con `fecha_vence = CURRENT_DATE`
- **THEN** el sistema responde "🎉 No tienes tareas para hoy."

#### Scenario: /hoy no va al buffer
- **WHEN** el usuario envía `/hoy`
- **THEN** el webhook responde directamente sin insertar en buffer ni invocar IA

### Requirement: Comando `/semana` para ver tareas de los próximos 7 días

El webhook SHALL detectar el comando `/semana` (sin argumento) y responder con tareas pendientes agrupadas por día para los próximos 7 días. Las tareas vencidas se muestran en un encabezado separado. Los días sin tareas se omiten.

#### Scenario: /semana con tareas
- **WHEN** el usuario envía `/semana`
- **AND** hay tareas pendientes con `fecha_vence` en los próximos 7 días
- **THEN** la respuesta incluye un encabezado `🔴 Vencidas:` (si hay tareas vencidas)
- **AND** cada día se muestra como `📅 Lun 7` seguido de sus tareas
- **AND** los días sin tareas se omiten

#### Scenario: /semana sin tareas
- **WHEN** el usuario envía `/semana`
- **AND** no hay tareas en los próximos 7 días ni vencidas
- **THEN** el sistema responde "🎉 No tienes tareas para esta semana."

### Requirement: Comando `/mes [n]` para vista mensual compacta

El webhook SHALL detectar el comando `/mes` (sin argumento) y responder con una vista calendario del mes actual en grid ASCII con emojis indicadores por día. El argumento opcional `n` (1-12) selecciona el mes del año actual.

#### Scenario: /mes del mes actual
- **WHEN** el usuario envía `/mes`
- **THEN** el sistema muestra el grid del mes en formato semanas (Lu a Do)
- **AND** cada celda muestra el día + indicadores emoji de tareas
- **AND** incluye leyenda al final

#### Scenario: /mes con argumento específico
- **WHEN** el usuario envía `/mes 8`
- **THEN** el sistema muestra la vista de agosto del año actual

#### Scenario: /mes con argumento inválido
- **WHEN** el usuario envía `/mes 13`
- **THEN** el sistema responde "Mes inválido. Usa un número entre 1 y 12."

### Requirement: Consistencia de emojis entre comandos

Los emojis usados en los comandos de vista de línea de tiempo SHALL ser consistentes entre sí y con `/tareas`: `🔵` laboral, `🟠` personal, `🟡` recurrencia, `⚡` vencida.

#### Scenario: Misma tarea, mismo emoji
- **WHEN** una misma tarea aparece en `/hoy`, `/semana`, y `/mes`
- **THEN** el emoji de ámbito es el mismo en los tres comandos
