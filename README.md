# Jimini

Personal management system with AI and Telegram — ingesta durable, transcripción de audio, motor de recurrencias, y hostigamiento (Pepe Grillo alerts).

## Setup

```bash
pip install -e .
cp .env.example .env  # fill in your keys
uvicorn jimini.main:app
```

## Testing

```bash
pip install -e ".[dev]"
pytest -v
```

Tests run automatically on every push via GitHub Actions (see `.github/workflows/ci.yml`).

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | — | Groq API key for audio transcription |
| `SUPABASE_URL` | — | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | — | Supabase service role key |
| `SUPABASE_BUCKET_AUDIO` | `audio-ingesta` | Storage bucket for voice notes |
| `OPENROUTER_API_KEY` | — | OpenRouter API key for task structuring |
| `TELEGRAM_BOT_TOKEN` | — | Telegram Bot API token |
| `WEBHOOK_SECRET_TOKEN` | `""` | Secret token for webhook verification |
| `TRANSCRIPCION_IDIOMA_DEFAULT` | `es` | Default language for audio transcription |
| `GROQ_MODEL` | `whisper-large-v3-turbo` | Groq transcription model |
| `MAX_AUDIO_FILE_SIZE_MB` | `25` | Max audio file size (Groq free tier limit) |
| `SIGNED_URL_TTL_HOURS` | `24` | Signed URL lifetime |
| `WORKER_POLL_INTERVAL_SECONDS` | `5` | Worker idle poll interval |

## Database migrations

Run in order:

1. `migrations/001_buffer_schema.sql` — Creates `buffer_ingesta_contingencia` with multi-media, lease, and message tracking columns.
2. `migrations/002_reclaim_function.sql` — Creates buffer lease protocol functions and schedules the stale lock reclaim via `pg_cron`.
3. `migrations/003_seed_config.sql` — Seeds configuration defaults.
4. `migrations/004_plantillas_recurrencia.sql` — Creates `plantillas_recurrencia` table, adds `valor_texto` to `configuracion_sistema`, adds `tipo_mensaje` to buffer.
5. `migrations/005_evaluar_recurrencias.sql` — Creates `evaluar_plantillas_recurrencia()` function and schedules daily pg_cron job.
6. `migrations/006_hostigamiento.sql` — Adds `descartado` estado to tareas, `chat_id` column, hostigamiento level functions, and vacation mode config seeds.

### pg_cron jobs

| Name | Schedule | Description |
|---|---|---|
| `reclaim-stale-locks` | `* * * * *` (every minute) | Reclaims buffer messages stuck in `procesando` for >5 min |
| `evaluar-recurrencias` | `1 5 * * *` (05:01 UTC = 00:01 Lima) | Evaluates recurrence templates and generates tasks |

### Database functions

- `claim_next_buffer_message()` — Atomically locks and returns the oldest pending buffer row (`FOR UPDATE SKIP LOCKED`).
- `mark_buffer_completed(p_id)` — Marks a message as successfully processed.
- `mark_buffer_failed(p_id, p_current_intentos)` — Marks a message as failed with exponential backoff (`10s × 2^n`), advancing to `error_permanente` after 3 attempts.
- `reclaim_stale_locks_buffer()` — Reclaims stale `procesando` rows.
- `evaluar_plantillas_recurrencia()` — Evaluates active recurrence templates against today's date (in configured timezone) and generates tasks. Idempotent via `ultima_generacion` guard + `ON CONFLICT DO NOTHING`.

## Recurrencias

### Comandos de Telegram

| Comando | Descripción |
|---|---|
| `/recurrencia <descripción>` | Crea una plantilla de recurrencia. La IA estructura la descripción. Ej: `/recurrencia Pagar luz el día 5 de cada mes, personal` |
| `/recurrencias` | Lista las recurrencias activas |

Tras crear una recurrencia, el bot envía una confirmación con botón [Deshacer] por si la IA malinterpretó la descripción.

### Convención `dia_del_mes = 0`

Si `dia_del_mes = 0`, la recurrencia se evalúa el **último día del mes** (28/29 en febrero, 30 en meses cortos, 31 en meses largos). Esto cubre pagos de "fin de mes" sin quebrar en febrero.

### Skip missed

Si el job de evaluación no corre un día (servidor caído, Supabase indisponible), las recurrencias de ese día **no se generan**. No hay mecanismo de catch-up. Trade-off aceptado para uso personal con servidor always-on: si notas que faltó una recurrencia, créala manualmente.

### Zona horaria

La evaluación opera en la zona horaria configurada en `configuracion_sistema` (clave `zona_horaria_default`, default `America/Lima`). El job de pg_cron dispara a las 05:01 UTC (00:01 Lima).

## Architecture

```
Telegram → Webhook → buffer_ingesta_contingencia (DB) → Async Worker → OpenRouter → tareas/plantillas

Audio path:
Telegram voice note → Webhook (download .ogg + upload Storage) → buffer → Worker
  → Groq STT (transcription cached) → OpenRouter (task/recurrence structuring)

Recurrence path:
Telegram /recurrencia → buffer (tipo_mensaje='recurrencia') → Worker
  → OpenRouter (plantilla structuring) → plantillas_recurrencia
  → Confirmation + [Deshacer] button

Daily evaluation:
pg_cron (05:01 UTC) → evaluar_plantillas_recurrencia()
  → SELECT plantillas WHERE activa AND coincide(fecha_hoy)
  → INSERT INTO tareas (origen='recurrencia')
```

## Hostigamiento (Pepe Grillo alerts)

El worker de hostigamiento evalúa tareas pendientes con fecha de vencimiento cada 60s y envía alertas por Telegram.

### Niveles

| Nivel | Trigger | Frecuencia | Botones |
|---|---|---|---|
| 0 (aviso) | -1 día | Una vez | [Completar] |
| 1 (hoy) | vence hoy | Cada 4h (09,13,17,21) | [Snooze 2h] [Mañana] [Completar] |
| 2 (vencida corto) | +1 a +2 días | Cada 3h | [Snooze 2h] [Mañana] [Completar] |
| 3 (vencida medio) | +3 a +6 días | Cada 4h | [Completar] [Descartar] |
| 4 (vencida largo) | +7 días | Diario 09:00 | [Completar] [Descartar] |

Horario activo 09-21 en zona del usuario. Fuera de ese rango no se envían alertas.

### Comandos

| Comando | Descripción |
|---|---|
| `/tareas` | Lista tareas pendientes agrupadas (vencidas, hoy, próximas, inbox) |
| `/hoy` | Muestra solo las tareas que vencen hoy |
| `/semana` | Muestra tareas de los próximos 7 días agrupadas por día + vencidas |
| `/mes [N]` | Vista calendario ASCII del mes actual (o mes N, 1-12) |
| `/vacaciones <fecha>` | Silencia alertas laborales hasta la fecha especificada |
| `/finde` | Silencia alertas laborales hasta el lunes 08:30 |

### Emojis en comandos de vista

| Emoji | Significado |
|---|---|
| 🔵 | Tarea laboral |
| 🟠 | Tarea personal |
| 🟡 | Tarea generada por recurrencia |
| ⚡ | Tarea vencida (más allá de su fecha límite) |
| 🔄 | Tarea de origen recurrencia activa |

### Modo descanso

En modo vacaciones/finde, las alertas del ámbito `laboral` se silencian completamente.
Las del ámbito `personal` solo se silencian para niveles 0-1 (aviso y vence-hoy); las
vencidas (nivel 2+) siguen activas.

### Estado descartado

El estado `descartado` en `tareas.estado` significa que la tarea ya no aplica pero
no se completó (distinto de `completado`). Las tareas descartadas no son hostigadas.

