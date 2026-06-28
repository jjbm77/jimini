## ADDED Requirements

### Requirement: Ingesta durable persistente

El sistema SHALL persistir cada mensaje entrante de Telegram en la tabla física `buffer_ingesta_contingencia` con `estado_procesamiento='pendiente'` y `procesado=false` antes de retornar HTTP 200 al webhook. Queda prohibido el uso de colas puras en memoria RAM (asyncio.Queue sin persistencia) como mecanismo primario de ingesta.

#### Scenario: Mensaje de texto llega al webhook
- **WHEN** un update de Telegram con `message.text` llega al webhook
- **THEN** el sistema ejecuta `INSERT INTO buffer_ingesta_contingencia (chat_id, telegram_message_id=<message_id>, tipo_media='texto', mensaje_raw=<texto>, estado_procesamiento='pendiente', procesado=false)` de forma síncrona
- **AND** retorna HTTP 200 al remitente únicamente después de confirmar el commit en la base de datos

#### Scenario: Caída del proceso FastAPI después del ACK
- **WHEN** el proceso FastAPI se reinicia/cae después de haber retornado 200 OK para un mensaje
- **AND** el mensaje está persistido en `buffer_ingesta_contingencia` con `estado_procesamiento='pendiente'`
- **THEN** al levantar un nuevo worker, el mensaje será reclamado y procesado desde la base de datos sin pérdida

### Requirement: Claim atómico de mensajes para procesamiento

El sistema SHALL usar `SELECT ... FOR UPDATE SKIP LOCKED` (o equivalente atómico) para que los workers reclamen mensajes del buffer sin contención entre ellos. El claim SHALL ser una transición atómica de `estado_procesamiento` de `pendiente` a `procesando` con registro de `tomado_en=NOW()`.

#### Scenario: Worker reclama un mensaje pendiente
- **WHEN** un worker consulta el buffer buscando mensajes para procesar
- **THEN** el sistema selecciona la fila más antigua con `estado_procesamiento='pendiente'` AND (`proximo_intento_en IS NULL` OR `proximo_intento_en <= NOW()`)
- **AND** actualiza atómicamente `estado_procesamiento='procesando'`, `tomado_en=NOW()`
- **AND** retorna los datos de la fila al worker vía `RETURNING *`

#### Scenario: Múltiples workers compiten por el mismo mensaje
- **WHEN** dos workers consultan el buffer concurrentemente
- **THEN** `SKIP LOCKED` garantiza que solo uno obtenga y reclame cada fila
- **AND** el otro worker no se bloquea ni obtiene filas duplicadas

#### Scenario: No hay mensajes para procesar
- **WHEN** un worker consulta el buffer y no hay filas `pendiente` con backoff expirado
- **THEN** el sistema retorna cero filas
- **AND** el worker espera un intervalo corto (polling) antes de reconsultar

### Requirement: Backoff exponencial en fallos de procesamiento

El sistema SHALL aplicar backoff exponencial a los mensajes que fallen en procesamiento. La fórmula SHALL ser `proximo_intento_en = NOW() + INTERVAL '10 seconds' * POWER(2, intentos_fallidos)`. Tras cada fallo, `intentos_fallidos` se incrementa en 1 y `estado_procesamiento` vuelve a `pendiente` con `tomado_en=NULL`.

#### Scenario: Primer fallo de procesamiento
- **WHEN** el procesamiento de un mensaje falla y `intentos_fallidos=0`
- **THEN** el sistema actualiza `intentos_fallidos=1`, `estado_procesamiento='pendiente'`, `tomado_en=NULL`, `proximo_intento_en=NOW() + INTERVAL '10 seconds'`

#### Scenario: Segundo fallo de procesamiento
- **WHEN** el procesamiento falla y `intentos_fallidos=1`
- **THEN** el sistema actualiza `intentos_fallidos=2`, `estado_procesamiento='pendiente'`, `proximo_intento_en=NOW() + INTERVAL '20 seconds'`

#### Scenario: Mensaje en backoff no es reclamado antes de tiempo
- **WHEN** un worker consulta el buffer y un mensaje tiene `proximo_intento_en > NOW()`
- **THEN** el sistema no selecciona ese mensaje para procesamiento
- **AND** el worker solo lo reclamará cuando `proximo_intento_en <= NOW()`

### Requirement: Dead Letter Queue al tercer intento fallido

El sistema SHALL mover un mensaje a `estado_procesamiento='error_permanente'` cuando `intentos_fallidos` alcance 3. En ese momento, el mensaje sale de la cola activa (no es reclamado por workers) y el sistema SHALL enviar una notificación proactiva al usuario vía Telegram indicando que el mensaje requiere revisión manual.

#### Scenario: Tercer fallo consecutivo
- **WHEN** el procesamiento de un mensaje falla y `intentos_fallidos=2` (pasando a 3)
- **THEN** el sistema actualiza `intentos_fallidos=3`, `estado_procesamiento='error_permanente'`, `tomado_en=NULL`
- **AND** el mensaje no será reclamado por workers en consultas posteriores
- **AND** el sistema envía una notificación proactiva al `chat_id` del mensaje vía Telegram Bot

#### Scenario: Mensaje en error_permanente es ignorado por workers
- **WHEN** un worker consulta el buffer buscando mensajes para procesar
- **THEN** la consulta filtra `estado_procesamiento='pendiente'` exclusivamente
- **AND** los mensajes en `error_permanente` nunca son seleccionados

### Requirement: Reclaim de stale locks vía pg_cron

El sistema SHALL ejecutar un job pg_cron cada minuto que reclame filas en `estado_procesamiento='procesando'` con `tomado_en < NOW() - INTERVAL '5 minutes'`. El reclaim SHALL devolver la fila a `estado_procesamiento='pendiente'`, incrementar `intentos_fallidos` en 1, asignar `proximo_intento_en=NOW() + INTERVAL '30 seconds'`, y limpiar `tomado_en=NULL`.

#### Scenario: Worker muere con mensaje en procesando
- **WHEN** un worker toma un mensaje (`estado_procesamiento='procesando'`, `tomado_en=T0`) y el proceso muere antes de completar
- **AND** transcurren más de 5 minutos desde `T0`
- **THEN** el job pg_cron detecta la fila stale
- **AND** actualiza `estado_procesamiento='pendiente'`, `intentos_fallidos=intentos_fallidos+1`, `proximo_intento_en=NOW() + INTERVAL '30 seconds'`, `tomado_en=NULL`
- **AND** el mensaje será reclamado por un worker cuando el backoff expire

#### Scenario: Worker sigue procesando dentro del umbral
- **WHEN** un worker tiene un mensaje en `procesando` con `tomado_en` dentro de los últimos 5 minutos
- **THEN** el job pg_cron no toca la fila
- **AND** el worker puede completar el procesamiento normalmente

#### Scenario: Reclaim empuja el mensaje a DLQ
- **WHEN** un mensaje stale tiene `intentos_fallidos=2` antes del reclaim
- **THEN** tras el reclaim `intentos_fallidos=3`
- **AND** el sistema lo transiciona directamente a `estado_procesamiento='error_permanente'` (sin pasar por `pendiente`)
- **AND** envía notificación proactiva al usuario vía Telegram

### Requirement: Schema evolucionado del buffer con multi-media

El sistema SHALL mantener el esquema de `buffer_ingesta_contingencia` con columnas para soporte multi-media, control de lease, y referencia al mensaje original de Telegram: `tipo_media`, `mensaje_raw` (nullable), `file_id` (nullable), `storage_path` (nullable), `signed_url` (nullable), `transcripcion` (nullable), `telegram_message_id` (nullable), `tomado_en`, `proximo_intento_en`, además de las columnas V4 (`chat_id`, `intentos_fallidos`, `estado_procesamiento`, `procesado`, `creado_en`).

#### Scenario: Mensaje de texto
- **WHEN** se inserta un mensaje de texto en el buffer
- **THEN** `tipo_media='texto'`, `mensaje_raw=<texto>`, `telegram_message_id=<id del mensaje de Telegram>`, y las columnas `file_id`, `storage_path`, `signed_url`, `transcripcion` son NULL

#### Scenario: Mensaje de voz
- **WHEN** se inserta un mensaje de voz en el buffer
- **THEN** `tipo_media='voz'`, `mensaje_raw=NULL` (hasta que se transcriba), `file_id=<file_id de Telegram>`, `storage_path=<path en Supabase Storage>`, `signed_url=<URL firmada>`, `telegram_message_id=<id del mensaje de Telegram>`, `transcripcion=NULL`

#### Scenario: Validación de consistencia tipo_media vs columnas
- **WHEN** `tipo_media='texto'`
- **THEN** el sistema garantiza vía CHECK constraint que `mensaje_raw IS NOT NULL` AND `file_id IS NULL` AND `storage_path IS NULL`
- **WHEN** `tipo_media='voz'`
- **THEN** el sistema garantiza vía CHECK constraint que `file_id IS NOT NULL` AND `storage_path IS NOT NULL`

#### Scenario: telegram_message_id siempre presente
- **WHEN** se inserta cualquier mensaje (texto o voz) proveniente de Telegram en el buffer
- **THEN** `telegram_message_id` SHALL ser no nulo (todas las inserts desde el webhook llevan el `message.message_id` del update de Telegram)
