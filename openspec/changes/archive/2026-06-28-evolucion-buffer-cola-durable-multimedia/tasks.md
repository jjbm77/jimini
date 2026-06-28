## 1. Migración de base de datos y schema del buffer

- [x] 1.1 Crear migración SQL con `CREATE TABLE buffer_ingesta_contingencia` usando el esquema evolucionado (columnas V4 + `tipo_media`, `file_id`, `storage_path`, `signed_url`, `transcripcion`, `telegram_message_id`, `tomado_en`, `proximo_intento_en`)
- [x] 1.2 Añadir CHECK constraints: `tipo_media IN ('texto', 'voz')`, `estado_procesamiento IN ('pendiente', 'procesando', 'completado', 'error_permanente')`, consistencia `tipo_media` vs columnas (`texto` implica `mensaje_raw NOT NULL` AND media columns NULL; `voz` implica `file_id NOT NULL` AND `storage_path NOT NULL`), y `telegram_message_id IS NOT NULL` (todo mensaje desde el webhook lleva el message_id de Telegram)
- [x] 1.3 Añadir índices: `CREATE INDEX idx_buffer_estado_procesamiento ON buffer_ingesta_contingencia (estado_procesamiento) WHERE estado_procesamiento = 'pendiente'` y `CREATE INDEX idx_buffer_tomado_en ON buffer_ingesta_contingencia (tomado_en) WHERE estado_procesamiento = 'procesando'`
- [x] 1.4 Crear bucket de Supabase Storage `audio-ingesta` (privado, sin acceso público)
  *Operación en Supabase Dashboard: Crea un bucket privado llamado `audio-ingesta` en Supabase Storage.*
- [x] 1.5 Configurar política RLS del bucket para acceso solo vía service role key
  *Operación en Supabase Dashboard: SQL → Policies → `CREATE POLICY "Service role only" ON storage.objects FOR ALL USING (auth.role() = 'service_role')`*
- [x] 1.6 Seed de `configuracion_sistema`: insertar clave `transcripcion_idioma_default` con valor `'es'`
  *Implementado en `migrations/003_seed_config.sql`. La tabla V3 no tiene columna `valor_texto`; la configuración de idioma se resuelve desde env var `TRANSCRIPCION_IDIOMA_DEFAULT` (default `'es'`) con fallback a DB vía `get_idioma_config()` RPC para futura extensibilidad.*

## 2. Funciones SQL y job pg_cron para reclaim de stale locks

- [x] 2.1 Crear función SQL `reclaim_stale_locks_buffer()` que reclame filas en `procesando` con `tomado_en < NOW() - INTERVAL '5 minutes'`: actualiza a `pendiente` (o `error_permanente` si llega a 3 intentos), `intentos_fallidos++`, `proximo_intento_en=NOW() + INTERVAL '30 seconds'`, `tomado_en=NULL`
  *Incluye `claim_next_buffer_message()`, `mark_buffer_completed()`, `mark_buffer_failed()`, `get_idioma_config()` — todas en `migrations/002_reclaim_function.sql`.*
- [x] 2.2 Programar job pg_cron: `SELECT cron.schedule('reclaim-stale-locks', '* * * * *', 'SELECT reclaim_stale_locks_buffer()')`
- [x] 2.3 Verificar que el job pg_cron ejecuta sin errores y reclama filas stale correctamente (test manual con INSERT de fila stale)
  *Manual: INSERT fila con estado='procesando', tomado_en=NOW()-INTERVAL '6 min', esperar ~60s, verificar que el cron la reclama.*

## 3. Adaptador TranscriptionProvider

- [x] 3.1 Definir interfaz `TranscriptionProvider` (método `transcribe(audio_url: str, language: str) -> str` con excepciones tipadas `RateLimitError`, `TranscriptionError`)
- [x] 3.2 Implementar `GroqTranscriptionProvider` usando `groq` SDK con endpoint `/openai/v1/audio/transcriptions`, modelo `whisper-large-v3-turbo`, parámetro `url` (no base64)
- [x] 3.3 Manejar errores HTTP: 429 → `RateLimitError`, 5xx/timeout → `TranscriptionError`, propagar sin retry interno
- [x] 3.4 Añadir `groq` SDK a dependencias del proyecto (`pyproject.toml` o `requirements.txt`)
- [x] 3.5 Configurar `GROQ_API_KEY` en variables de entorno y factory del provider según configuración

## 4. Webhook FastAPI extendido para multi-media

- [x] 4.1 Modificar handler del webhook `/api/v1/tg/webhook` para distinguir `message.text` vs `message.voice`
- [x] 4.2 Rama `texto`: INSERT síncrono en buffer con `tipo_media='texto'`, `mensaje_raw=text`, `telegram_message_id=<message_id>`, return 200
- [x] 4.3 Rama `voz`: validar `file_size` <= 25MB; si excede, enviar mensaje Telegram explicativo y retornar 200 (no insertar en buffer)
- [x] 4.4 Rama `voz` (tamaño ok): llamar a Telegram `getFile`, descargar `.ogg` con hasta 2 reintentos internos; si falla, retornar 500
- [x] 4.5 Rama `voz` (descarga ok): subir `.ogg` a Supabase Storage `audio-ingesta/<uuid>.ogg`; si falla, retornar 500
- [x] 4.6 Rama `voz` (subida ok): generar signed URL con TTL 24h, INSERT en buffer con `tipo_media='voz'`, `file_id`, `storage_path`, `signed_url`, `telegram_message_id=<message_id>`, return 200

## 5. Worker de procesamiento con protocolo de lease

- [x] 5.1 Implementar función `claim_next_message()` con RPC a `claim_next_buffer_message()` (FOR UPDATE SKIP LOCKED)
- [x] 5.2 Implementar función `mark_completed(message_id)` con RPC a `mark_buffer_completed()`
- [x] 5.3 Implementar función `mark_failed(message_id)` con RPC a `mark_buffer_failed()`: backoff exponencial 10s*2^intentos, DLQ al 3er fallo
- [x] 5.4 Implementar loop principal del worker: claim → procesar → mark_completed/mark_failed → sleep corto si no hay mensajes → repetir
- [x] 5.5 Lógica de procesamiento para `tipo_media='texto'`: pasar `mensaje_raw` directo a OpenRouter para estructuración de tarea
- [x] 5.6 Lógica de procesamiento para `tipo_media='voz'`: si `transcripcion IS NULL`, leer `transcripcion_idioma_default` de `configuracion_sistema` (default `'es'`), verificar y renovar `signed_url` si expiró, invocar `TranscriptionProvider.transcribe(signed_url, language)`, guardar en `transcripcion`; luego pasar `transcripcion` a OpenRouter
- [x] 5.7 Lógica de reintento optimizada: si `transcripcion IS NOT NULL`, saltar transcripción y pasar directo a OpenRouter

## 6. Notificación de DLQ con cadena de fallback para audio

- [x] 6.1 Implementar función `notify_dlq_telegram(message)` que envíe mensaje proactivo al `chat_id` del mensaje en `error_permanente`
- [x] 6.2 Si `tipo_media='texto'`: incluir `mensaje_raw` en la notificación
- [x] 6.3 Si `tipo_media='voz'` AND `transcripcion IS NOT NULL`: incluir el texto transcrito en la notificación
- [x] 6.4 Si `tipo_media='voz'` AND `transcripcion IS NULL`: implementar cadena ordenada de fallback:
  - [x] 6.4.1 Intentar `forwardMessage(from_chat_id=chat_id, message_id=telegram_message_id)`; si succeede, enviar notificación textual indicando fallo de transcripción + el voice note reenviado
  - [x] 6.4.2 Si `forwardMessage` falla, intentar `sendVoice(voice=file_id)`; si succeede, enviar notificación textual + el voice note como nota nueva
  - [x] 6.4.3 Si ambos fallan, enviar notificación textual indicando que el audio no pudo transcribirse ni reenviarse, indicar al usuario contactar al administrador, y registrar `storage_path` en logs
- [x] 6.5 Manejar fallo en el envío de la notificación DLQ (log, no bloquear el flujo principal)

## 7. Renovación de signed URL en el worker

- [x] 7.1 Implementar función `signed_url_is_expired()` que parsea el expiry de la URL (parámetro `?expires=`) y compara con `NOW()`
- [x] 7.2 Implementar función `regenerate_signed_url()` que genere una nueva signed URL desde Supabase Storage con TTL 24h
- [x] 7.3 Integrar en el worker: antes de invocar `TranscriptionProvider.transcribe`, verificar expiración y regenerar si corresponde, actualizando la columna `signed_url` del buffer

## 8. Pruebas y verificación

- [x] 8.1 Test unitario del protocolo de lease: claim atómico con dos workers concurrentes no retorna la misma fila
- [x] 8.2 Test unitario del backoff: tras 3 fallos, el mensaje transiciona a `error_permanente` y dispara notificación
- [x] 8.3 Test del job pg_cron de reclaim: fila con `tomado_en` > 5 min es reclamada correctamente
- [x] 8.4 Test del webhook con mensaje de voz: end-to-end, audio llega a Supabase Storage y fila queda en buffer con `tipo_media='voz'`
- [x] 8.5 Test del worker con mensaje de voz: transcripción vía Groq (mock o real), `transcripcion` se cachea, OpenRouter estructura la tarea
- [x] 8.6 Test de reintento con cache: simular fallo de OpenRouter después de transcripción exitosa, verificar que el reintento salta la transcripción
- [x] 8.7 Test de renovación de signed URL: simular URL expirada, verificar regeneración antes de transcribir
- [x] 8.8 Test de notificación DLQ para audio: verificar formato del mensaje para los escenarios con/sin transcripción
- [x] 8.9 Test de cadena de fallback en DLQ para audio: simular `forwardMessage` exitoso, simular `forwardMessage` fallido + `sendVoice` exitoso, simular ambos fallidos (verificar mensaje terminal y log de `storage_path`)
- [x] 8.10 Test de idioma configurable: verificar que el worker lee `transcripcion_idioma_default` de `configuracion_sistema` y lo pasa al `TranscriptionProvider` (casos: `'es'`, `'en'`, `NULL` auto-detección)
- [x] 8.11 Test de persistencia de `telegram_message_id`: verificar que todo mensaje insertado desde el webhook lleva `telegram_message_id` no nulo

## 9. Documentación y configuración

- [x] 9.1 Documentar variables de entorno nuevas: `GROQ_API_KEY`, `SUPABASE_BUCKET_AUDIO`, `SIGNED_URL_TTL_HOURS` (default 24)
- [x] 9.2 Documentar el job pg_cron de reclaim y la función SQL en el README o docs del proyecto
- [x] 9.3 Actualizar la documentación inicial (Documentación Inicial/) con una nota indicando que la línea base de specs ahora vive en OpenSpec, y que V4 es superseded por los specs de `ingesta-durable` y `transcripcion-audio` para los temas cubiertos por esta change
