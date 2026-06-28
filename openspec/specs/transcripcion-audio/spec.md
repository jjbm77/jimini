## Purpose

Definir los requisitos para la ingesta y procesamiento de mensajes de voz de Telegram: descarga síncrona del `.ogg` en el webhook, almacenamiento durable en Supabase Storage, transcripción asíncrona vía proveedor cloud gratuito (Groq STT) con cache de resultado, e integración con el flujo de estructuración por IA. Incluye la notificación de Dead Letter Queue con cadena de fallback para reenvío del audio al usuario.

## Requirements

### Requirement: Ingesta síncrona de mensajes de voz en webhook

El webhook SHALL detectar updates de Telegram con `message.voice`, descargar el archivo `.ogg` vía `getFile` + HTTP GET, subirlo a Supabase Storage (bucket privado `audio-ingesta`), generar una signed URL con TTL ≥ 24h, y persistir la referencia en `buffer_ingesta_contingencia` con `tipo_media='voz'` — todo antes de retornar HTTP 200.

#### Scenario: Mensaje de voz llega al webhook
- **WHEN** un update de Telegram con `message.voice` llega al webhook
- **THEN** el sistema llama a Telegram `getFile` con `file_id`
- **AND** descarga el archivo `.ogg` desde la URL efímera retornada
- **AND** sube el archivo a Supabase Storage en `audio-ingesta/<uuid>.ogg`
- **AND** genera una signed URL con TTL de 24h
- **AND** inserta en `buffer_ingesta_contingencia` con `tipo_media='voz'`, `file_id=<id>`, `storage_path=<path>`, `signed_url=<url>`, `telegram_message_id=<message_id>`, `mensaje_raw=NULL`, `estado_procesamiento='pendiente'`
- **AND** retorna HTTP 200 únicamente después de confirmar el commit

#### Scenario: Audio excede el límite de tamaño del proveedor de transcripción
- **WHEN** el webhook recibe un voice note con `file_size` > 25MB (límite free tier de Groq)
- **THEN** el sistema retorna HTTP 200 con un mensaje al usuario vía Telegram explicando que el audio excede el límite
- **AND** no inserta el mensaje en el buffer (rechazo explícito, no DLQ)

#### Scenario: Falla la descarga desde Telegram
- **WHEN** la llamada a `getFile` o la descarga del `.ogg` falla (red, 5xx, file_id inválido)
- **THEN** el sistema reintenta la descarga hasta 2 veces dentro del mismo request
- **AND** si todas las tentativas fallan, retorna HTTP 500 a Telegram (para que Telegram reintenta el update)
- **AND** no inserta nada en el buffer (no hay audio que persistir)

#### Scenario: Falla la subida a Supabase Storage
- **WHEN** la descarga del `.ogg` succeeds pero la subida a Supabase Storage falla
- **THEN** el sistema retorna HTTP 500 a Telegram
- **AND** no inserta nada en el buffer (no hay storage_path confiable)

### Requirement: Transcripción asíncrona con cache de resultado y idioma configurable

El worker SHALL transcribir el audio de los mensajes con `tipo_media='voz'` usando un `TranscriptionProvider`. El resultado SHALL guardarse en la columna `transcripcion` del buffer. Si una fila es reclamada para reintento y `transcripcion IS NOT NULL`, el worker SHALL saltar la transcripción y pasar directamente a la estructuración por IA. El parámetro `language` SHALL leerse de `configuracion_sistema` (clave `transcripcion_idioma_default`), con valor por defecto `'es'`.

#### Scenario: Primera transcripción de un mensaje de voz
- **WHEN** un worker reclama una fila con `tipo_media='voz'` AND `transcripcion IS NULL`
- **THEN** el worker lee `transcripcion_idioma_default` de `configuracion_sistema` (default `'es'` si la clave no existe)
- **AND** invoca `TranscriptionProvider.transcribe(signed_url, language)` con el valor leído
- **AND** guarda el texto retornado en `transcripcion`
- **AND** procede a la estructuración por IA con ese texto

#### Scenario: Reintento después de fallo en la IA
- **WHEN** un worker reclama una fila con `tipo_media='voz'` AND `transcripcion IS NOT NULL` AND `estado_procesamiento='pendiente'` (reintento)
- **THEN** el worker salta la invocación a `TranscriptionProvider`
- **AND** usa el texto de `transcripcion` directamente para la estructuración por IA

#### Scenario: Transcripción falla
- **WHEN** `TranscriptionProvider.transcribe` lanza una excepción (429, 5xx, timeout)
- **THEN** el worker aplica el protocolo de backoff del buffer (incrementa `intentos_fallidos`, vuelve a `pendiente`, asigna `proximo_intento_en`)
- **AND** `transcripcion` permanece NULL
- **AND** el próximo reintento volverá a intentar la transcripción

#### Scenario: Idioma configurado a auto-detección
- **WHEN** `configuracion_sistema.transcripcion_idioma_default` es `NULL`
- **THEN** el worker invoca `TranscriptionProvider.transcribe(signed_url, language=NULL)`
- **AND** el proveedor usa auto-detección de idioma nativa de Whisper

### Requirement: Adaptador TranscriptionProvider para aislar el proveedor de ASR

El sistema SHALL definir un adaptador `TranscriptionProvider` con una interfaz estable (`transcribe(audio_url, language) -> text`) que oculte el proveedor concreto. El proveedor inicial SHALL ser Groq STT (`whisper-large-v3-turbo`). El adaptador SHALL permitir añadir proveedores alternativos (faster-whisper local, OpenAI Whisper) sin modificar el pipeline del worker.

#### Scenario: Transcripción exitosa vía Groq
- **WHEN** el worker invoca `TranscriptionProvider.transcribe(signed_url, 'es')`
- **AND** el proveedor configurado es Groq
- **THEN** el adaptador llama al endpoint `https://api.groq.com/openai/v1/audio/transcriptions` con `url=signed_url`, `model='whisper-large-v3-turbo'`, `language='es'`
- **AND** retorna el texto transcrito al worker

#### Scenario: Groq retorna rate limit (429)
- **WHEN** el adaptador recibe HTTP 429 de Groq
- **THEN** propaga la excepción al worker (que aplica backoff del buffer)
- **AND** no realiza retry interno (el protocolo de lease del buffer maneja los reintentos)

#### Scenario: Cambio de proveedor sin modificar el worker
- **WHEN** se configura un nuevo proveedor (ej: faster-whisper local) implementando la misma interfaz `TranscriptionProvider`
- **THEN** el worker no requiere modificaciones
- **AND** el pipeline de transcripción + estructuración por IA permanece idéntico

### Requirement: Renovación de signed URL expirada antes de transcribir

El worker SHALL verificar si `signed_url` de una fila ha expirado antes de pasarla al `TranscriptionProvider`. Si expiró, SHALL regenerar la signed URL desde `storage_path` y actualizar la fila antes de invocar la transcripción.

#### Scenario: Signed URL vigente
- **WHEN** el worker reclama una fila con `tipo_media='voz'` AND `transcripcion IS NULL`
- **AND** la `signed_url` tiene TTL vigente (no expirada)
- **THEN** el worker pasa la `signed_url` directamente al `TranscriptionProvider`

#### Scenario: Signed URL expirada
- **WHEN** el worker reclama una fila con `tipo_media='voz'` AND `transcripcion IS NULL`
- **AND** la `signed_url` ha expirado
- **THEN** el worker regenera una nueva signed URL desde `storage_path` con TTL de 24h
- **AND** actualiza la columna `signed_url` en la fila
- **AND** pasa la nueva URL al `TranscriptionProvider`

### Requirement: Notificación de DLQ con cadena de fallback para audio

Cuando un mensaje con `tipo_media='voz'` alcanza `estado_procesamiento='error_permanente'`, la notificación proactiva al usuario SHALL incluir una referencia reproducible al audio original. Si `transcripcion IS NOT NULL`, la notificación SHALL incluir el texto transcrito para contexto. Si `transcripcion IS NULL`, la notificación SHALL seguir una cadena ordenada de fallback para reenviar el audio al usuario: (1) `forwardMessage(from_chat_id, message_id)` usando `telegram_message_id` y `chat_id` del buffer, (2) `sendVoice(voice=file_id)` usando el `file_id` persistido, (3) mensaje informativo indicando que el audio no pudo reenviarse y debe contactar al administrador. La notificación SHALL ser informativa (sin botones accionables en v1).

#### Scenario: DLQ con transcripción exitosa (falló la IA después)
- **WHEN** un mensaje `tipo_media='voz'` cae en `error_permanente` AND `transcripcion IS NOT NULL`
- **THEN** la notificación a Telegram incluye el texto transcrito
- **AND** indica que el procesamiento por IA falló repetidamente
- **AND** permite al usuario revisar y reingresar la tarea manualmente

#### Scenario: DLQ sin transcripción — forwardMessage exitoso
- **WHEN** un mensaje `tipo_media='voz'` cae en `error_permanente` AND `transcripcion IS NULL`
- **AND** el intento de `forwardMessage(from_chat_id=chat_id, message_id=telegram_message_id)` succeede
- **THEN** la notificación a Telegram incluye un texto indicando que el audio no pudo transcribirse tras 3 intentos
- **AND** el voice note original es reenviado al chat del usuario vía `forwardMessage` (con atribución "Reenviado")
- **AND** el usuario puede escuchar el audio y reingresar la tarea manualmente por texto

#### Scenario: DLQ sin transcripción — forwardMessage falla, sendVoice exitoso
- **WHEN** un mensaje `tipo_media='voz'` cae en `error_permanente` AND `transcripcion IS NULL`
- **AND** `forwardMessage` falla (ej: el usuario borró el mensaje original)
- **AND** el intento de `sendVoice(voice=file_id)` succeede
- **THEN** la notificación a Telegram incluye un texto indicando que el audio no pudo transcribirse tras 3 intentos
- **AND** el audio es reenviado como voice note nuevo vía `sendVoice` (sin atribución de reenvío)
- **AND** el usuario puede escuchar el audio y reingresar la tarea manualmente por texto

#### Scenario: DLQ sin transcripción — ambos reenvíos fallan
- **WHEN** un mensaje `tipo_media='voz'` cae en `error_permanente` AND `transcripcion IS NULL`
- **AND** tanto `forwardMessage` como `sendVoice` fallan
- **THEN** la notificación a Telegram indica explícitamente que el audio no pudo transcribirse ni reenviarse
- **AND** indica al usuario que contacte al administrador para acceder al audio almacenado
- **AND** registra el `storage_path` en los logs para recuperación manual administrativa
