## Purpose

Definir los requisitos para los modos de descanso del sistema Jimini: el comando `/vacaciones` para silenciar alertas laborales hasta una fecha de retorno, el comando `/finde` para silenciar hasta el lunes 08:30, la auto-limpieza de modos al expirar, y el comando `/tareas` para listar el backlog activo.

## Requirements

### Requirement: Comando `/vacaciones` para silenciar hostigamiento laboral

El webhook SHALL detectar el comando `/vacaciones <fecha>` y activar el modo vacaciones, que silencia todas las alertas de ámbito `laboral` hasta la fecha de retorno especificada. Las alertas de ámbito `personal` de nivel 2+ (vencidas) continúan activas.

#### Scenario: Activar modo vacaciones con fecha de retorno
- **WHEN** el usuario envía `/vacaciones 15/07/2026`
- **THEN** el sistema inserta/actualiza en `configuracion_sistema` la clave `modo_vacaciones` con `valor_booleano=true` y `fecha_liberacion='2026-07-15'`
- **AND** responde al usuario: "🏖️ Modo vacaciones activado hasta el 15/07/2026. Las alertas laborales están silenciadas."
- **AND** retorna 200 OK (no inserta en buffer)

#### Scenario: Modo vacaciones silencia ámbito laboral
- **WHEN** el modo vacaciones está activo AND `NOW() < fecha_liberacion`
- **AND** el worker evalúa una tarea con `ambito='laboral'`
- **THEN** el worker no envía la alerta (silenciada)
- **AND** la tarea permanece `pendiente` (no se altera su estado)

#### Scenario: Modo vacaciones mantiene alertas personales vencidas
- **WHEN** el modo vacaciones está activo
- **AND** el worker evalúa una tarea con `ambito='personal'` y nivel 2+ (vencida)
- **THEN** el worker envía la alerta normalmente (no silenciada)

#### Scenario: Modo vacaciones silencia alertas personales no vencidas
- **WHEN** el modo vacaciones está activo
- **AND** el worker evalúa una tarea con `ambito='personal'` y nivel 0-1 (aviso o vence hoy)
- **THEN** el worker no envía la alerta (silenciada)

### Requirement: Auto-limpieza de modo vacaciones al expirar

El worker de hostigamiento SHALL verificar en cada iteración si `fecha_liberacion` del modo vacaciones es menor o igual a `NOW()`. Si expiró, SHALL desactivar el modo automáticamente seteando `valor_booleano=false` y `fecha_liberacion=NULL`.

#### Scenario: Modo vacaciones expira automáticamente
- **WHEN** `NOW() >= fecha_liberacion` del modo vacaciones
- **THEN** el worker ejecuta `UPDATE configuracion_sistema SET valor_booleano=false, fecha_liberacion=NULL WHERE clave='modo_vacaciones'`
- **AND** las alertas laborales se reanudan inmediatamente

#### Scenario: Usuario consulta estado de vacaciones
- **WHEN** el usuario envía `/vacaciones` (sin fecha)
- **AND** el modo vacaciones está activo
- **THEN** el sistema responde: "🏖️ Modo vacaciones activo hasta el {fecha_liberacion}."
- **AND** si no está activo, responde: "No estás en modo vacaciones."

### Requirement: Comando `/finde` para silenciar hostigamiento laboral en fin de semana

El webhook SHALL detectar el comando `/finde` y activar el modo fin de semana, que silencia todas las alertas de ámbito `laboral` hasta el lunes a las 08:30 AM en zona del usuario. El comportamiento para alertas personales es idéntico al modo vacaciones (niveles 2+ siguen activos).

#### Scenario: Activar modo finde
- **WHEN** el usuario envía `/finde`
- **THEN** el sistema calcula `fecha_liberacion` = próximo lunes a las 08:30 en zona del usuario
- **AND** inserta/actualiza en `configuracion_sistema` la clave `modo_finde` con `valor_booleano=true` y `fecha_liberacion` calculada
- **AND** responde: "🗓️ Modo fin de semana activado. Las alertas laborales se reanudarán el lunes a las 08:30."
- **AND** retorna 200 OK (no inserta en buffer)

#### Scenario: Modo finde silencia ámbito laboral
- **WHEN** el modo finde está activo AND `NOW() < fecha_liberacion`
- **AND** el worker evalúa una tarea con `ambito='laboral'`
- **THEN** el worker no envía la alerta

#### Scenario: Auto-limpieza de modo finde al expirar
- **WHEN** `NOW() >= fecha_liberacion` del modo finde (lunes 08:30)
- **THEN** el worker desactiva el modo automáticamente
- **AND** las alertas laborales se reanudan

### Requirement: Comando `/tareas` para listar tareas pendientes

El webhook SHALL detectar el comando `/tareas` (sin argumento) y responder con una lista de tareas pendientes agrupadas por estado de vencimiento. El comando no inserta nada en el buffer ni invoca la IA.

#### Scenario: Listar tareas pendientes agrupadas
- **WHEN** el usuario envía `/tareas`
- **THEN** el webhook consulta `SELECT * FROM tareas WHERE estado='pendiente' ORDER BY fecha_vence`
- **AND** responde con las tareas agrupadas:
  `🔴 Vencidas:` seguido de las tareas con `fecha_vence < CURRENT_DATE`
  `⚠️ Hoy:` seguido de las tareas con `fecha_vence = CURRENT_DATE`
  `📅 Próximas:` seguido de las tareas con `fecha_vence > CURRENT_DATE` (con fecha)
  `📥 Inbox:` seguido de las tareas con `fecha_vence IS NULL`
- **AND** si no hay tareas en un grupo, ese grupo se omite
- **AND** si no hay tareas pendientes, responde "No tienes tareas pendientes. 🎉"

#### Scenario: /tareas no muestra tareas descartadas ni completadas
- **WHEN** el usuario envía `/tareas`
- **THEN** la consulta filtra `estado='pendiente'` exclusivamente
- **AND** las tareas con `estado='descartado'` o `estado='completado'` no aparecen

#### Scenario: /tareas no va al buffer
- **WHEN** el usuario envía `/tareas`
- **THEN** el webhook responde directamente
- **AND** no inserta nada en el buffer
- **AND** no invoca la IA
