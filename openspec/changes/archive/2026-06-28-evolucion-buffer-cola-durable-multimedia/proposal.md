## Why

El Fail-Safe Buffer de V4 (RF01, RF02) deja tres huecos críticos sin definir: (1) no especifica quién/cuándo devuelve un mensaje del estado `procesando` a `pendiente` tras un fallo transitorio, (2) no trata el stale lock cuando un worker muere con una fila en `procesando`, y (3) el esquema actual asume solo `mensaje_raw TEXT`, impidiendo procesar mensajes de voz de Telegram — una feature prioritaria para Pepe Grillo. Estos huecos rompen la promesa de durabilidad de RF01 en escenarios reales (redeploys, caídas de OpenRouter, reinicios) y excluyen un canal de ingesta natural para un asistente conversacional.

## What Changes

- **Evolution of `buffer_ingesta_contingencia` schema** con columnas de lease (`tomado_en`, `proximo_intento_en`), multi-media (`tipo_media`, `file_id`, `storage_path`, `signed_url`, `transcripcion`) — **BREAKING** frente al esquema V4 publicado.
- **Protocolo de lease sobre el buffer** basado en `FOR UPDATE SKIP LOCKED` para claim atómico, backoff exponencial (10s/20s/40s) en fallos, y umbral de 3 intentos para transición a `error_permanente` (cumple RF02 literal).
- **Reclaim de stale locks vía pg_cron** (cada minuto): filas en `procesando` con `tomado_en` > 5 minutos vuelven a `pendiente` con `intentos_fallidos++` y backoff. Reusa el pg_cron ya introducido en V4 para recurrencias.
- **Pipeline de transcripción de voz** con proveedor cloud gratuito (Groq STT, `whisper-large-v3-turbo`): el webhook descarga el `.ogg` de Telegram, lo sube a Supabase Storage, persiste referencia + signed URL en el buffer, y retorna 200 OK. El worker transcribe vía URL passthrough (sin descargar el audio al proceso FastAPI) y cachea el resultado en `transcripcion` para no retranscribir en reintentos posteriores.
- **Adaptador `TranscriptionProvider`** para aislar el proveedor de ASR y permitir fallback a faster-whisper local si el free tier de Groq cambia.
- **Extensión de la notificación de DLQ (RF02) para audio**: cuando un mensaje de voz cae en `error_permanente` sin transcripción, la notificación a Telegram incluye una referencia reproducible al audio original (no solo texto, que no existe).

## Capabilities

### New Capabilities
- `ingesta-durable`: Buffer persistente con protocolo de lease, backoff exponencial, reclaim de stale locks vía pg_cron y DLQ con notificación proactiva. Cubre RF01, RF02 y los huecos de reintento/stale-lock del diseño V4.
- `transcripcion-audio`: Pipeline de ingesta y procesamiento de mensajes de voz de Telegram: descarga síncrona en webhook, almacenamiento en Supabase Storage, transcripción asíncrona vía proveedor cloud gratuito con cache de resultado, e integración con el flujo existente de estructuración por IA.

### Modified Capabilities
<!-- No existen specs previas en openspec/specs/ — todas las capabilities son nuevas. -->

## Impact

- **Base de datos (Supabase/PostgreSQL)**: migración del esquema `buffer_ingesta_contingencia` (breaking). Reusa `pg_cron` ya presente en V4 para el job de reclaim de stale locks (nueva función SQL además de `evaluar_plantillas_recurrencia`).
- **Supabase Storage**: nuevo bucket privado para audios `.ogg` (no existía en V3/V4). Generación de signed URLs con TTL.
- **Backend FastAPI**: webhook extendido para distinguir `tipo_media`; nuevo worker de transcripción que reusa el protocolo de lease del buffer; nuevo adaptador `TranscriptionProvider`.
- **Dependencias Python**: `groq` SDK (nuevo). No reemplaza `openrouter` — coexisten.
- **Servicios externos**: nuevo proveedor Groq (free tier rate-limited). Sin costo para tráfico personal. Volatilidad del free tier mitigada por el adaptador.
- **Telegram Bot**: notificación de DLQ extendida para incluir referencia reproducible al audio cuando aplica.
- **Documentación inicial**: V4 no menciona audio ni el protocolo de lease. Esta change establece la línea base de specs para ambos; futuras revisiones de los documentos iniciales deberían reflejar estos contratos.
