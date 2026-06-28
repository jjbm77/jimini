## ADDED Requirements

### Requirement: Dimensiones ortogonales tipo_media y tipo_mensaje en el buffer

El buffer `buffer_ingesta_contingencia` SHALL mantener dos dimensiones ortogonales: `tipo_media` (formato del input: `texto` | `voz`) y `tipo_mensaje` (intención semántica: `tarea` | `recurrencia`). El webhook SHALL setear `tipo_mensaje` al detectar comandos antes del INSERT. El worker SHALL bifurcar el procesamiento según `tipo_mensaje`.

#### Scenario: Mensaje de texto para tarea
- **WHEN** el webhook recibe un update con `message.text` que no comienza con un comando conocido
- **THEN** inserta en el buffer con `tipo_media='texto'`, `tipo_mensaje='tarea'`

#### Scenario: Mensaje de texto para recurrencia
- **WHEN** el webhook recibe un update con `message.text` que comienza con `/recurrencia`
- **THEN** inserta en el buffer con `tipo_media='texto'`, `tipo_mensaje='recurrencia'`
- **AND** `mensaje_raw` contiene el texto después del comando

#### Scenario: Mensaje de voz para tarea
- **WHEN** el webhook recibe un update con `message.voice` y la transcripción no comienza con `/recurrencia`
- **THEN** inserta en el buffer con `tipo_media='voz'`, `tipo_mensaje='tarea'`

#### Scenario: Mensaje de voz para recurrencia
- **WHEN** el webhook recibe un update con `message.voice` y la transcripción comienza con `/recurrencia`
- **THEN** inserta en el buffer con `tipo_media='voz'`, `tipo_mensaje='recurrencia`

#### Scenario: Bifurcación del worker por tipo_mensaje
- **WHEN** el worker reclama un mensaje con `tipo_mensaje='tarea'`
- **THEN** usa el system prompt de estructuración de tarea e inserta en `tareas`
- **WHEN** el worker reclama un mensaje con `tipo_mensaje='recurrencia'`
- **THEN** usa el system prompt de estructuración de plantilla e inserta en `plantillas_recurrencia`

### Requirement: Detección de comandos en el webhook

El webhook SHALL detectar comandos de Telegram (mensajes que comienzan con `/`) antes de insertar en el buffer. Los comandos conocidos (`/recurrencia`, `/recurrencias`) SHALL ser manejados específicamente. Los comandos `/recurrencias` (listar) SHALL ser respondidos directamente sin pasar por el buffer. Los comandos `/recurrencia <texto>` (crear) SHALL ir al buffer con `tipo_mensaje='recurrencia'`.

#### Scenario: Comando /recurrencia con argumento
- **WHEN** el webhook recibe `/recurrencia Pagar luz día 5 cada mes`
- **THEN** extrae el texto después de `/recurrencia `
- **AND** inserta en el buffer con `tipo_mensaje='recurrencia'`, `mensaje_raw='Pagar luz día 5 cada mes'`
- **AND** retorna 200 OK

#### Scenario: Comando /recurrencias (listar)
- **WHEN** el webhook recibe `/recurrencias` (sin argumento o con argumento vacío)
- **THEN** consulta la base de datos directamente
- **AND** responde al usuario con la lista de plantillas activas
- **AND** no inserta nada en el buffer
- **AND** retorna 200 OK

#### Scenario: Comando /recurrencia sin argumento
- **WHEN** el webhook recibe `/recurrencia` (sin texto después)
- **THEN** responde al usuario indicando el uso: "Describe la recurrencia: `/recurrencia <descripción>`"
- **AND** no inserta nada en el buffer
- **AND** retorna 200 OK

#### Scenario: Mensaje sin comando
- **WHEN** el webhook recibe un texto que no comienza con `/`
- **THEN** inserta en el buffer con `tipo_mensaje='tarea'`
- **AND** retorna 200 OK
