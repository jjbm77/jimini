## ADDED Requirements

### Requirement: Tests para signed_url_is_expired

El sistema SHALL tener tests unitarios para `signed_url_is_expired()` cubriendo los 4 casos: URL sin parámetro expires, URL expirada, URL vigente, y error de parsing.

#### Scenario: signed_url_is_expired con URL sin expires
- **WHEN** se ejecuta `signed_url_is_expired("https://example.com/file.ogg")`
- **THEN** retorna `False` (no está expirada)

#### Scenario: signed_url_is_expired con URL expirada
- **WHEN** se ejecuta `signed_url_is_expired("https://example.com/file.ogg?expires=1000000000")` (timestamp en el pasado)
- **THEN** retorna `True` (está expirada)

#### Scenario: signed_url_is_expired con URL vigente
- **WHEN** se ejecuta `signed_url_is_expired("https://example.com/file.ogg?expires=9999999999")` (timestamp en el futuro)
- **THEN** retorna `False`

#### Scenario: signed_url_is_expired con formato inválido
- **WHEN** se ejecuta `signed_url_is_expired("https://example.com/file.ogg?expires=notanumber")`
- **THEN** retorna `False` (error de parsing silentemente capturado)

### Requirement: Tests para _build_keyboard

El sistema SHALL tener tests unitarios para `_build_keyboard()` cubriendo los 6 casos: nivel 0 a 4 más default. Cada test SHALL verificar la estructura exacta de la lista de botones inline.

#### Scenario: _build_keyboard nivel 0
- **WHEN** se llama `_build_keyboard("t-123", 0)`
- **THEN** retorna una lista con un solo botón: `[{"text": "✅ Completar", "callback_data": "completar:t-123"}]`

#### Scenario: _build_keyboard nivel 1
- **WHEN** se llama `_build_keyboard("t-123", 1)`
- **THEN** retorna dos filas: `[⏳ 2h, 📅 Mañana]` + `[✅ Completar]`

#### Scenario: _build_keyboard nivel 3
- **WHEN** se llama `_build_keyboard("t-123", 3)`
- **THEN** retorna dos filas: `[✅ Completar]` + `[🗑️ Descartar]`

#### Scenario: _build_keyboard nivel default
- **WHEN** se llama `_build_keyboard("t-123", 99)` (nivel no mapeado)
- **THEN** retorna un solo botón: `[✅ Completar]`

### Requirement: Tests para _month_grid

El sistema SHALL tener tests unitarios para `_month_grid()` cubriendo: mes de 31 días, mes de 28 días (febrero no bisiesto), y mes con tareas en alguna celda (verificar emojis en la celda correcta).

#### Scenario: _month_grid mes de 31 días
- **WHEN** se llama `_month_grid(2026, 1, {})` (enero 2026, sin tareas)
- **THEN** el grid contiene 31 celdas con números
- **AND** el grid comienza con el día correcto de la semana (enero 2026 empieza jueves)

#### Scenario: _month_grid mes con tareas
- **WHEN** se llama `_month_grid(2026, 7, {"2026-07-05": [{"ambito": "laboral", "id": "t1"}]})`
- **THEN** la celda del día 5 contiene emoji 🔵

### Requirement: Tests para _get_text_for_ia

El sistema SHALL tener tests unitarios para `_get_text_for_ia()` cubriendo: entrada de texto (pasa directo), entrada de voz con transcripción cacheada, entrada de voz sin transcripción (invoca Groq), renovación de signed URL expirada, y detección automática de /recurrencia en transcripción de voz.

#### Scenario: _get_text_for_ia con texto
- **WHEN** se llama con un BufferMessage de tipo texto
- **THEN** retorna `mensaje_raw` sin modificaciones

#### Scenario: _get_text_for_ia con voz cacheada
- **WHEN** se llama con un BufferMessage de tipo voz y `transcripcion` no nulo
- **THEN** retorna `transcripcion` sin invocar Groq

#### Scenario: _get_text_for_ia con voz sin cache
- **WHEN** se llama con BufferMessage tipo voz y `transcripcion` nulo
- **THEN** invoca `TranscriptionProvider.transcribe()`, guarda resultado en DB, lo retorna

#### Scenario: _get_text_for_ia detecta /recurrencia en voz
- **WHEN** la transcripción comienza con "/recurrencia"
- **THEN** ajusta `tipo_mensaje` a "recurrencia" en el buffer
- **AND** retorna el texto después del comando

### Requirement: Tests para worker_loop_hostigamiento

El sistema SHALL tener tests unitarios para el loop de hostigamiento cubriendo: tarea que sube de nivel (nivel 1→2), tarea que se repite en el mismo nivel, tarea bloqueada por modo vacaciones, y tarea sin chat_id (silenciada).

#### Scenario: Subida de nivel dispara alerta
- **WHEN** una tarea con `nivel_hostigamiento=1` y nivel calculado=2 es evaluada
- **THEN** el worker envía alerta de nivel 2
- **AND** actualiza `nivel_hostigamiento=2` y `proxima_alerta_bloqueada_hasta`

#### Scenario: Tarea bloqueada por modo vacaciones
- **WHEN** el modo vacaciones está activo y la tarea es laboral
- **THEN** el worker no envía alerta (skip silencioso)

#### Scenario: Tarea sin chat_id
- **WHEN** una tarea sin `chat_id` es evaluada
- **THEN** el worker omite la tarea sin enviar alerta