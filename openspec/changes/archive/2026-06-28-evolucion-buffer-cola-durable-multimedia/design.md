## Context

El sistema Jimini ("Pepe Grillo") está en fase de diseño previo a implementación. Los documentos iniciales V3 (funcional) y V4 (hardening de resiliencia) establecen la línea base. V4 introduce el Fail-Safe Buffer (`buffer_ingesta_contingencia`) y la Dead Letter Queue para fallos de IA, pero deja sin definir el protocolo de reintento, el manejo de stale locks, y no contempla mensajes de voz de Telegram — un canal de ingesta natural para un asistente conversacional.

Restricciones heredadas de la arquitectura existente:
- **Capas gratuitas**: Supabase free, OpenRouter free, Google Calendar API. Cualquier nuevo servicio debe encajar en este patrón (cloud gratuito rate-limited para uso personal).
- **pg_cron** ya está presente en V4 para recurrencias (00:01 AM). Reusar para nuevos jobs programados antes que introducir un nuevo scheduler.
- **PostgreSQL como fuente de verdad y desacoplador**: nada depende de que el proceso FastAPI esté vivo excepto el procesamiento en tiempo real. El buffer es una cola durable implementada sobre una tabla.
- **Framework Simplicidad + Efectividad** (V3 §3): preferir soluciones simples sobre complejas cuando el costo marginal es bajo.

Stakeholders: usuario único (Jaime), uso personal, tráfico bajo. No hay SLA comercial. La simplicidad operacional pesa más que el throughput.

## Goals / Non-Goals

**Goals:**
- Cerrar los huecos de reintento (Hueco 3) y stale lock (Hueco 4) del diseño V4 con un protocolo de lease coherente que reusa primitivas Postgres existentes.
- Habilitar la ingesta y procesamiento de mensajes de voz de Telegram respetando el espíritu de RF01 V4 ("persistir el mensaje crudo antes del 200 OK").
- Mantener RF02 (DLQ al 3er intento) sin añadir complejidad de contadores por fase, usando cache de transcripción como amortiguador.
- Reusar pg_cron (ya en V4) para el reclaim de stale locks en vez de introducir un nuevo mecanismo de scheduling.
- Aislar el proveedor de ASR (Groq) detrás de un adaptador para permitir fallback sin tocar el pipeline.

**Non-Goals:**
- **No** implementar DLQ simétrico para el worker de Google Calendar (mismo patrón aplica pero es scope separado; la tabla `tareas.sincronizado_calendar` no se modifica en esta change).
- **No** diseñar la tabla `plantillas_recurrencia` que falta en V4 (RF05 la supone pero no la define — es otra change).
- **No** resolver el sistema de hostigamiento/niveles de alerta (la parte más "Jiminy" del diseño, pendiente de exploración propia).
- **No** soportar otros tipos de media (imágenes, video) más allá de voz. El esquema se diseña extensible (`tipo_media`) pero solo se especifica e implementa `texto` y `voz`.
- **No** implementar transcripción local (faster-whisper) en esta change. El adaptador se diseña para permitirlo, pero el proveedor implementado es Groq.
- **No** añadir métricas/alertas de tamaño de cola (backpressure). El tráfico personal no las justifica ahora.

## Decisions

### D1: Buffer como cola durable con lease protocol (vs. cola externa tipo Redis/RabbitMQ)

**Decisión**: Implementar el protocolo de lease sobre la tabla `buffer_ingesta_contingencia` existente usando `SELECT ... FOR UPDATE SKIP LOCKED` (claim atómico), `UPDATE ... WHERE ... RETURNING` (transiciones de estado atómicas), y un job pg_cron para reclaim de stale locks.

**Alternativas consideradas**:
- *Redis / RabbitMQ*: introduciría infraestructura externa nueva, violando el principio de "capas gratuitas, sin ops". Supabase free no incluye Redis gestionado.
- *asyncio.Queue + checkpoint en DB*: V4 lo prohíbe explícitamente (RF01) por pérdida ante reinicios.
- *LISTEN/NOTIFY de Postgres*: útil para despertar workers pero no resuelve el claim atómico ni el stale lock. Se podría usar como complemento, pero el polling cada N segundos es suficiente para tráfico personal y más simple.

**Razón**: Postgres ya tiene todas las primitivas. Reusar pg_cron (ya en V4) para reclaim mantiene coherencia arquitectónica. No añade dependencias. El patrón "transactional outbox" está bien establecido para este caso de uso.

### D2: Backoff exponencial 10s / 20s / 40s (vs. progresión V4 10s/30s/60s)

**Decisión**: Backoff `INTERVAL '10 seconds' * POWER(2, intentos_fallidos)` → 10s, 20s, 40s para los tres intentos antes del DLQ.

**Alternativas consideradas**:
- *Progresión 10s/30s/60s del worker de Google Calendar (V4 §2)*: consistencia visual con V4, pero es una progresión ad-hoc no exponencial.
- *Backoff con jitter*: estándar en sistemas distribuidos para evitar thundering herd, pero con un solo worker y tráfico personal no hay contención que mitigar.

**Razón**: Exponencial puro es más simple de razonar y calcular en SQL. La diferencia entre 40s y 60s en el tercer intento es irrelevante para uso personal. Si en el futuro se quiere alinear con la progresión de Google Calendar worker, es un cambio de una línea.

### D3: Stale lock de 5 minutos (vs. configurable por tipo_media desde el inicio)

**Decisión**: Umbral fijo de 5 minutos para el reclaim de stale locks. Documentado como decision aplazable: si se añade faster-whisper local en el futuro (audios largos), se hace configurable por `tipo_media`.

**Razón**: YAGNI para tráfico personal con Groq (transcripción <30s típicamente). 5 min es holgado para no reclamar filas que siguen procesándose. Configurabilidad prematura añade complejidad sin beneficio inmediato.

### D4: Reclaim cuenta como intento fallido (vs. contador separado)

**Decisión**: El reclaim de stale lock incrementa `intentos_fallidos` (cuenta hacia el umbral de 3 de RF02), con backoff de 30s fijo (no exponencial) para el primer reclaim.

**Alternativas consideradas**:
- *No contar*: un mensaje zombie podría sobrevivir indefinidamente sin llegar a DLQ, haciendo RF02 inalcanzable para fallos de infraestructura.
- *Contador separado `intentos_stale` con umbral 5*: más justo (separa fallos de IA de fallos de infra), pero añade columna y complejidad. Injusticia solo aparece si hay 3+ reinicios en ventana corta — poco probable en tráfico personal.

**Razón**: Contar como fallo es más conservador y cumple RF02 literalmente. El backoff fijo de 30s (no exponencial) evita penalizar excesivamente un mensaje que fue víctima de un redeploy. Si la operación revela falsos positivos en DLQ por redeploys frecuentes, se introduce `intentos_stale` separado en una change futura.

### D5: Opción C híbrida para audio (descarga síncrona en webhook + storage persistente)

**Decisión**: El webhook descarga el `.ogg` de Telegram y lo sube a Supabase Storage **antes** del 200 OK. Persiste `storage_path` + `signed_url` + `file_id` (respaldo) en el buffer. El worker transcribe pasando la `signed_url` a Groq (sin descargar el audio al proceso FastAPI).

**Alternativas consideradas**:
- *Opción A (solo file_id en buffer, worker descarga después)*: webhook más rápido. El `file_id` de Telegram **no expira** (es reutilizable indefinidamente para el mismo bot según la documentación de Bot API); lo que expira es la *download URL* que retorna `getFile` (TTL garantizado ≥1h, renovable). Sin embargo, la documentación no garantiza retención indefinida del archivo subyacente en servidores de Telegram, y el `file_id` no es estable entre bots. Aún así, confiar solo en Telegram para persistencia del binario viola el espíritu de RF01 V4 — la "persistencia" recaería en un servicio externo no controlado.
- *Opción B (descarga + transcripción síncrona en webhook)*: webhook bloquea 5-15s, Telegram hace timeout y reintenta → duplicados.
- *Opción C' (descarga asíncrona en BackgroundTask antes del 200)*: el 200 sale rápido pero si el BackgroundTask muere antes de descargar, el audio podría no estar disponible para recuperación (depende de retención de Telegram, no garantizada).

**Razón**: La descarga síncrona agrega 1-3s al webhook (aceptable para Telegram), pero garantiza durabilidad real del binario bajo nuestro control (Supabase Storage). Supabase Storage free tier (1GB) es amplio para voice notes personales. La signed URL permite que Groq descargue directamente sin pasar por la memoria del worker. El `file_id` se persiste como respaldo secundario (ver D9) pero la fuente de verdad durable es `storage_path`.

### D6: Groq STT directo como proveedor de ASR (vs. OpenRouter STT / faster-whisper local / multimodal)

**Decisión**: Proveedor inicial es Groq STT (`whisper-large-v3-turbo`, free tier, endpoint OpenAI-compatible), detrás de un adaptador `TranscriptionProvider`.

**Alternativas consideradas** (ver exploración previa para tabla comparativa completa):
- *OpenRouter STT (`/audio/transcriptions`)*: unifica proveedor pero es pago por segundo (no hay tier `:free` para STT) y solo acepta base64 (obliga a descargar+codificar en el worker).
- *OpenRouter multimodal (`input_audio` en chat completions)*: colapsaría transcripción + estructuración en una sola llamada, pero depende de modelos `:free` con input audio (incierto) y también es base64-only.
- *faster-whisper local*: $0 real y sin volatilidad de free tier, pero consume CPU/RAM del host FastAPI (free tier: 512MB/1vCPU), bloquea el event loop si no se aisla, y cold start de 5-10s. Calidad en español aceptable pero inferior a large-v3.

**Razón**: Groq encaja en el patrón existente "cloud gratuito rate-limited para uso personal" (como Supabase, OpenRouter, Google Calendar). Soporta `.ogg` nativo (formato Telegram) y parámetro `url` (Groq descarga, no el worker). Calidad `large-v3` state-of-the-art en español. El adaptador mitiga la volatilidad del free tier: si Groq cambia límites, se implementa faster-whisper como fallback sin tocar el pipeline.

### D7: `transcripcion` como cache para no retranscribir en reintentos

**Decisión**: El worker guarda el texto transcrito en la columna `transcripcion` del buffer. Al reclamar una fila para reintentar, si `transcripcion IS NOT NULL`, salta directo a OpenRouter.

**Alternativas consideradas**:
- *Contadores por fase (`intentos_groq`, `intentos_ia`)*: más justo para multi-fase pero rompe RF02 literal y duplica columnas. La "injusticia" del contador global se manifiesta solo cuando hay mezcla de fallos de Groq y OpenRouter en el mismo mensaje.
- *Autómata de fases con `fase_procesamiento`*: máxima flexibilidad pero máxima complejidad. Overkill para 2 fases.

**Razón**: La cache evita el costo más caro del reintento (volver a transcribir) sin añadir complejidad de autómata. RF02 se cumple literalmente (contador único, umbral 3). El caso "2 fallos Groq + 1 OpenRouter → DLQ injusto" es marginal en tráfico personal y se mitiga parcialmente porque la cache protege contra re-trabajo. Coherente con "Framework Simplicidad + Efectividad" (V3 §3).

### D8: Notificación de DLQ para audio con referencia reproducible

**Decisión**: Cuando un mensaje con `tipo_media='voz'` cae en `error_permanente` y `transcripcion IS NULL`, la notificación proactiva a Telegram (RF02) incluye una referencia reproducible al audio original. Si `transcripcion IS NOT NULL` (falló la IA pero la transcripción existe), se incluye el texto transcrito. La referencia al audio se implementa con la cadena de fallback definida en D9.

**Razón**: Para audio sin transcribir, no hay texto que mostrar al usuario. La notificación genérica "mensaje en DLQ, revisa manualmente" es inactionable cuando el contenido es un voice note que el usuario no puede ver desde la DB.

**Corrección de supuesto inicial**: El design.md temprano asumía que `file_id` tenía TTL ~1h y que `forwardMessage` lo usaba. Verificación contra la documentación de Telegram Bot API confirmó: (1) el TTL de 1h aplica a la *download URL* que retorna `getFile`, no al `file_id` — este es descrito como "Identifier for this file, which can be used to download or reuse the file" sin mención de expiración, y es reutilizable para el mismo bot "con sin límites"; (2) `forwardMessage` no usa `file_id` sino `from_chat_id` + `message_id`, sin límite de tiempo documentado. Esto reabrió las opciones de notificación (ver D9).

### D9: Cadena de fallback para reenvío de audio en notificación DLQ (resuelve Q1)

**Decisión**: La notificación de DLQ para audio (`tipo_media='voz'`, `transcripcion IS NULL`) SHALL intentar reenviar el audio original al usuario siguiendo esta cadena ordenada de fallback:

1. **`forwardMessage(from_chat_id, message_id)`** — reenvía el voice note original con atribución "Reenviado". Mejor UX: el usuario reconoce instantáneamente cuál es. Requiere persistir `telegram_message_id` (columna nueva en el buffer) y `chat_id` (ya existe). Falla si el usuario borró el mensaje original de su chat.
2. **`sendVoice(voice=file_id)`** — reenvía el audio como voice note nuevo (sin atribución de reenvío). Usa el `file_id` de Telegram ya persistido en el buffer. Falla si Telegram purgó el archivo subyacente (retención no garantizada explícitamente en la docs, pero en práctica persiste para el mismo bot).
3. **Referencia a `storage_path`** (futuro, no accionable hasta que exista app web) — último recurso durable 100% bajo nuestro control. Hoy se documenta como fallback terminal pero la notificación indica al usuario que contacte al administrador si las dos anteriores fallan.

**Alternativas consideradas**:
- *Solo `forwardMessage`*: óptimo en UX pero frágil ante mensaje borrado.
- *Solo `sendVoice(file_id)`*: robusto pero pierde atribución "reenviado", el usuario no sabe de qué mensaje se trata.
- *Solo `storage_path`*: durable pero no reproducible dentro de Telegram hoy (no hay app web).
- *Combinación A→B→C con los 3 botones accionables (Reintentar/Transcribir/Descartar)*: ver D12 — se decide minimal informativo para v1.

**Razón**: La cadena ordenada maximiza resiliencia con UX óptimo en el caso común (forwardMessage funciona la mayoría de las veces). El costo es una columna nueva (`telegram_message_id`) y lógica de fallback en el handler de notificación. El `file_id` ya estaba persistido por D5; ahora gana un rol funcional en DLQ además de respaldo.

### D10: Idioma de transcripción configurable, default 'es' (resuelve Q2)

**Decisión**: El worker SHALL invocar `TranscriptionProvider.transcribe(signed_url, language)` donde `language` se lee de la tabla `configuracion_sistema` (clave `transcripcion_idioma_default`). El valor por defecto SHALL ser `'es'`. Valores válidos: `'es'`, `'en'`, o `NULL` (auto-detección de Whisper).

**Alternativas consideradas**:
- *Hardcodear `'es'`*: simple pero inflexible si el usuario recibe audios en otro idioma ocasionalmente.
- *Auto-detección siempre (`language=NULL`)*: óptimo para multilingüe pero subóptimo para el caso común (español) — agrega latencia y reduce precisión marginal.
- *Per-mensaje (el usuario indica idioma con un comando)*: máxima flexibilidad pero UX pesada para uso personal.

**Razón**: El usuario opera en contexto corporativo peruano, mayoría español. Optimizar para el 95% (forzar `es`) con override vía `configuracion_sistema` (tabla que ya existe en V3) para el 5%. La lectura del config es un SELECT ligero que se puede cachear en el worker por N minutos si la latencia preocupa. El parámetro `language` en Groq es un hint de optimización, no un constraint — si el audio está en otro idioma, Whisper lo detecta y transcribe correctamente, solo con latencia/precisión marginalmente peor.

### D11: Umbral de stale lock fijo en 5 minutos, acoplamiento documentado (resuelve Q3)

**Decisión**: Mantener 5 minutos fijos como umbral de stale lock (sin configurabilidad por `tipo_media` en esta change). Documentar explícitamente el acoplamiento entre el umbral y el tiempo máximo de procesamiento esperado del proveedor de ASR configurado.

**Acoplamiento documentado**:
- Groq STT (`whisper-large-v3-turbo`): transcripción típica <15s para voice notes. Margen: 6.6x (5min / 45s worst case). Holgado.
- faster-whisper local (hipotético futuro): transcripción de audio largo (5min) ~2-3min en CPU free-tier. Margen: 1.4x (5min / 3.5min worst case). Apretado.

**Razón**: YAGNI para el proveedor actual (Groq). El adaptador `TranscriptionProvider` (D6) ya aísla el proveedor; el umbral es un knob separado que se puede retrofit facilmente cuando se añada faster-whisper. Costo de retrofit futuro: 1 columna `umbral_stale_segundos` en `configuracion_sistema` + 1 SELECT en `reclaim_stale_locks_buffer()`. Bajo.

### D12: Notificación de DLQ informativa en v1, sin botones accionables (resuelve Q4)

**Decisión**: La notificación de DLQ (RF02) SHALL ser informativa en v1 — incluye el contenido relevante (texto transcrito si existe, audio reenviado vía la cadena de D9 si no) y una indicación de que el mensaje requiere revisión manual. **No** incluye botones interactivos ("Reintentar", "Transcribir manualmente", "Descartar") en esta change.

**Alternativas consideradas**:
- *Botones accionables desde v1*: V3 RF07 ya introduce botones de snooze, el patrón existe. Pero añade 3 handlers de callback, un nuevo estado `descartado`, y un flujo conversacional para "Transcribir manualmente" (esperar próximo mensaje de texto del chat, tratarlo como `transcripcion`).
- *Solo botón "Transcribir manualmente"* (el de mayor valor para audio DLQ): oro para audio no transcrito, pero añade complejidad de flujo conversacional asimétrica respecto a los otros dos botones.

**Razón**: "Framework Simplicidad + Efectividad" (V3 §3). Shippear informativo primero, observar qué hace el usuario (que es también el desarrollador), añadir botones según necesidad real observada. El botón de mayor valor (`Transcribir manualmente`) se puede añadir solo, sin los otros dos, si el caso de audio no transcribido resulta frecuente en operación. Esto queda como extensión candidata para una change futura.

## Risks / Trade-offs

- **[Volatilidad del free tier de Groq]** → Mitigado por adaptador `TranscriptionProvider`; fallback faster-whisper local diseñado pero no implementado en esta change. Detección: si `error_permanente` por fallos de Groq aumenta, activar fallback.
- **[Expiración de signed URL antes del retry]** → Mitigado: el worker regenera la signed URL en el claim si detecta que expiró (comparación con `NOW()`). TTL por defecto: 24h, holgado para backoff máximo de 40s + tiempo de procesamiento.
- **[Audio > 25MB en free tier de Groq]** → Mitigado: voice notes de Telegram son cortos (típicamente <2MB). El webhook valida `file_size` y rechaza con mensaje explicativo si excede el límite (no va al buffer).
- **[Falsos positivos en DLQ por redeploys frecuentes]** → Trade-off aceptado (D4). Si se manifiesta, introducir `intentos_stale` separado en change futura. Para tráfico personal, 3 redeploys en ventana de 40s + 5min stale es improbable.
- **[Crecimiento indefinido del buffer]** → Fuera de scope (retención/purge es otra change). El buffer crece con `completado` y `error_permanente` sin purge. Para tráfico personal, crecimiento lento; se puede añadir job pg_cron de purge mensual después.
- **[Breaking change del esquema V4]** → Mitigado por migración. No hay datos en producción (sistema en diseño). La migración es aditiva (ADD COLUMN) + CHECK constraint update.
- **[Acoplamiento a Telegram para descarga de audio]** → Aceptado: Telegram es el único canal de ingesta actual. Si se añaden otros canales (WhatsApp, etc.), el paso de descarga se abstrae en el webhook handler correspondiente.

## Migration Plan

No hay datos en producción (sistema en diseño previo a implementación). La "migración" es la creación del esquema evolucionado desde cero:

1. **Crear bucket de Supabase Storage** `audio-ingesta` (privado, sin acceso público).
2. **Aplicar migración SQL**: `CREATE TABLE buffer_ingesta_contingencia` con el esquema evolucionado (columnas V4 + lease + multi-media + `telegram_message_id`). No hay tabla previa que migrar.
3. **Habilitar pg_cron** (si no está habilitado) y programar el job de reclaim: `SELECT cron.schedule('reclaim-stale-locks', '* * * * *', 'SELECT reclaim_stale_locks_buffer()')`.
4. **Crear función SQL** `reclaim_stale_locks_buffer()` con la lógica de UPDATE de stale locks.
5. **Seed de configuración**: insertar en `configuracion_sistema` la clave `transcripcion_idioma_default` con valor `'es'`.
6. **Configurar variables de entorno**: `GROQ_API_KEY`, `SUPABASE_BUCKET_AUDIO`, TTL de signed URLs.
7. **Desplegar FastAPI** con el webhook extendido y el worker de transcripción.

**Rollback**: al ser diseño previo, el rollback es eliminar la tabla y el bucket. En un escenario post-implementación, rollback requiere drop de columnas nuevas (pérdida de datos de audio pendientes) — por eso la change debe aplicar antes de que haya tráfico real.

## Open Questions

Todas las open questions originales fueron resueltas en esta iteración del design:

| Q | Decisión | Sección |
|---|---|---|
| Q1 — UX notificación DLQ audio | Cadena de fallback `forwardMessage` → `sendVoice` → `storage_path` | D9 |
| Q2 — Idioma transcripción | `language='es'` default, configurable vía `configuracion_sistema` | D10 |
| Q3 — Umbral stale lock configurable | 5 min fijo, acoplamiento proveedor↔umbral documentado | D11 |
| Q4 — Notificación DLQ accionable vs. informativa | Informativa en v1, botones como extensión futura | D12 |

**Open questions restantes (menores, no bloquean implementación)**:
- **UX del fallback terminal en D9**: cuando `forwardMessage` y `sendVoice` fallan ambos, la notificación indica "contacta al administrador". Para un sistema de usuario único, esto es razonable; si se abre a más usuarios, conviene una vista en la app web para reproducir audios desde `storage_path`.
- **Cache del valor de `configuracion_sistema.transcripcion_idioma_default` en el worker**: el SELECT por claim es ligero, pero si se quiere evitar, se puede cachear en memoria por 5 min. Decisión de implementación, no de diseño.
