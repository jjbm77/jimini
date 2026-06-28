# ===================================================
# JIMINI — Deployment Guide
# ===================================================

## PASO 1: Supabase (base de datos + storage)
## ================================================

1. Ve a https://supabase.com y crea cuenta (gratis).
2. Crea un proyecto nuevo (nombre: `jimini`, región más cercana a Lima).
3. Espera a que la DB se aprovisione (~2 min).
4. Ve a Settings → Database → Connection string.
5. Copia la **URI** (formato `postgresql://postgres:...@db.xxx.supabase.co:5432/postgres`).
   Extrae de ahí:
   - SUPABASE_URL: `https://xxx.supabase.co`
   - SUPABASE_SERVICE_KEY: ve a Settings → API → `service_role` key (secreta)

### Ejecutar migraciones

6. Ve a SQL Editor en Supabase dashboard.
7. Copia y pega CADA migración en orden, ejecutándolas una por una:

   **001_buffer_schema.sql**
   - Crea la tabla buffer con columnas de lease + multi-media

   **002_reclaim_function.sql**
   - Crea funciones RPC (claim, mark_completed, mark_failed, get_idioma_config, reclaim_stale_locks)
   - Programa pg_cron job de reclaim cada minuto
   - ⚠️ Debes habilitar `pg_cron` en Supabase: Settings → Database → Extensions → buscar pg_cron → Enable

   **003_seed_config.sql**
   - Siembra config defaults (idioma)

   **004_plantillas_recurrencia.sql**
   - Crea tabla de plantillas de recurrencia
   - Añade valor_texto a configuracion_sistema
   - Añade tipo_mensaje al buffer
   - ⚠️ Asegúrate de tener pg_cron habilitado

   **005_evaluar_recurrencias.sql**
   - Crea función evaluar_plantillas_recurrencia()
   - Programa pg_cron job diario a 05:01 UTC (00:01 Lima)

   **006_hostigamiento.sql**
   - Añade estado 'descartado' a tareas
   - Añade chat_id a tareas
   - Crea funciones de nivel/frecuencia de hostigamiento
   - Siembra config de modo vacaciones/finde

### Crear bucket de storage

8. Ve a Storage en Supabase dashboard.
9. Crea un bucket llamado `audio-ingesta` (marcar como **privado**, no público).

## PASO 2: APIs externas (Groq + OpenRouter)
## ================================================

10. Ve a https://console.groq.com
    - Crea cuenta (gratis)
    - Ve a API Keys → Create API Key
    - Copia: GROQ_API_KEY

11. Ve a https://openrouter.ai
    - Crea cuenta (gratis, $1 crédito inicial)
    - Ve a API Keys → Create Key
    - Copia: OPENROUTER_API_KEY

## PASO 3: Telegram Bot
## ================================================

12. Abre Telegram y busca @BotFather.

13. Crea el bot:
    /newbot
    Jimini (o el nombre que quieras)
    @JiminiPepeGrilloBot (username único, termina en 'bot')

14. BotFather te da el TOKEN. Cópialo: TELEGRAM_BOT_TOKEN

15. **NO configures el webhook todavía.** Lo haremos DESPUÉS del deploy.

## PASO 4: Deploy a Koyeb
## ================================================

16. Ve a https://www.koyeb.com y crea cuenta (gratis, login con GitHub).

17. En el dashboard, haz click en "Create App".

18. Elige "Deploy from GitHub":
    - Conecta tu cuenta de GitHub
    - Selecciona el repositorio: `jjbm77/jimini`
    - Branch: `master`

19. Configura el deploy:
    - **Type:** Web Service
    - **Port:** 8000
    - **Build:** Dockerfile (detecta automático)
    - En la sección "Environment variables" añade TODAS estas:

```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJhbG... (la service_role key)
SUPABASE_BUCKET_AUDIO=audio-ingesta
GROQ_API_KEY=gsk_...
OPENROUTER_API_KEY=sk-or-...
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
WEBHOOK_SECRET_TOKEN=jimini-secret-2026 (inventa uno, cualquier string)
TRANSCRIPCION_IDIOMA_DEFAULT=es
SIGNED_URL_TTL_HOURS=24
WORKER_POLL_INTERVAL_SECONDS=5
```

20. Haz click en "Deploy". Koyeb construye la imagen Docker y la despliega (~2-3 min).

21. Después del deploy exitoso, copia la URL pública (ej: `https://jimini-xxx.koyeb.app`).

## PASO 5: Configurar webhook de Telegram
## ================================================

22. Abre tu navegador y visita esta URL (reemplaza con tus valores):

```
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://<TU_URL_KOYEB>/api/v1/tg/webhook&secret_token=<WEBHOOK_SECRET_TOKEN>
```

Ejemplo:
```
https://api.telegram.org/bot123456:ABC-DEF/setWebhook?url=https://jimini-pepe-grillo-abc123.koyeb.app/api/v1/tg/webhook&secret_token=jimini-secret-2026
```

Telegram responderá: `{"ok":true,"result":true,"description":"Webhook was set"}`

23. Verifica que funcione:
```
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getWebhookInfo
```

Debe mostrar `"url": "https://<TU_URL_KOYEB>/api/v1/tg/webhook"` y `"last_error_message": ""`.

## PASO 6: Probar Pepe Grillo
## ================================================

24. Abre Telegram y busca tu bot (@JiminiPepeGrilloBot).

25. Manda un mensaje de prueba:
```
Reunión con Juan el 5 de julio, laboral, prioridad alta
```

26. Pepe debería:
    - Recibir el mensaje vía webhook
    - Insertarlo en buffer_ingesta_contingencia
    - Procesarlo con OpenRouter (extraer tarea)
    - Insertar la tarea en tareas
    - El worker de hostigamiento la evaluará cada 60s

27. Para verificar que la tarea se creó, ve a Supabase → SQL Editor y ejecuta:
```sql
SELECT * FROM tareas ORDER BY creado_en DESC LIMIT 5;
```

28. Prueba otros comandos:
    - `/recurrencia Pagar luz el día 5 de cada mes, personal`
    - `/tareas`
    - `/semana`
    - `/hoy`

## Troubleshooting

- **Webhook no recibido:** Ve a Supabase → SQL Editor y ejecuta `SELECT * FROM buffer_ingesta_contingencia ORDER BY id DESC LIMIT 5;`. Si no hay filas nuevas, el webhook no está llegando. Revisa `getWebhookInfo` en Telegram para ver errores.

- **Tareas no se crean:** El worker procesa el buffer cada 5s. Si después de 30s no hay tarea en `tareas`, revisa las filas del buffer con `estado_procesamiento='error_permanente'`.

- **Logs de Koyeb:** Ve al dashboard de Koyeb → tu app → Logs. Busca errores de Python (KeyError, connection refused, etc.).

- **pg_cron no funciona:** En Supabase, ve a Settings → Database → Extensions y verifica que `pg_cron` esté enabled. Si no, ejecuta `CREATE EXTENSION IF NOT EXISTS pg_cron;` en SQL Editor.
