## Why

RF05 (V3) requiere un motor de generación de tareas recurrentes que evalúe plantillas diariamente y clone las que coincidan con el día actual. V4 confirma que pg_cron debe disparar la evaluación a las 00:01 AM. Sin embargo, ni V3 ni V4 definen la tabla `plantillas_recurrencia`, su esquema, ni cómo el usuario crea plantillas. Esta es la segunda capacidad foundational del sistema (después de la ingesta durable): sin recurrencias, Jimini solo tiene tareas que el usuario ingresa manualmente, perdiendo el valor de automatización para pagos mensuales, revisiones semanales y rutinas cíclicas.

## What Changes

- **Nueva tabla `plantillas_recurrencia`** con modelado ad-hoc de criterios temporales (tipo_recurrencia + intervalo + dia_del_mes + mes_del_anio + dia_de_semana), offset de vencimiento (dias_para_vencer), y ciclo de vida (activa, fecha_inicio, fecha_fin, ultima_generacion).
- **Función SQL `evaluar_plantillas_recurrencia()`** que opera en zona horaria configurable (default `America/Lima`), evalúa plantillas contra `CURRENT_DATE` en esa zona, y genera tareas con idempotencia vía `ultima_generacion`.
- **Job pg_cron** a las 05:01 UTC (00:01 Lima) que dispara la evaluación diaria.
- **Extensión de `configuracion_sistema`** con columna `valor_texto TEXT` para almacenar configuración de texto (zona horaria, futuras configs).
- **Extensión del buffer `buffer_ingesta_contingencia`** con columna `tipo_mensaje` (`'tarea'` | `'recurrencia'`) — **BREAKING** frente al esquema de la change anterior.
- **Extensión del webhook** para detectar comando `/recurrencia` y setear `tipo_mensaje='recurrencia'` en el INSERT al buffer.
- **Extensión del worker** para procesar mensajes con `tipo_mensaje='recurrencia'`: usa un system prompt distinto para estructurar plantillas (no tareas) e inserta en `plantillas_recurrencia`.
- **Confirmación post-creación con botón [Deshacer]**: tras crear una plantilla, el bot responde con el detalle + botón inline para deshacer si la IA malinterpretó.
- **Comando `/recurrencias`** para listar las plantillas activas.
- **Convención `dia_del_mes = 0`** = último día del mes (cubre pagos de fin de mes en meses cortos).
- **Postura skip missed**: si el job no corre un día, las recurrencias de ese día se pierden (no hay catch-up). Documentado como trade-off aceptado para uso personal con servidor always-on.

## Capabilities

### New Capabilities
- `plantillas-recurrencia`: Motor de tareas recurrentes: tabla de plantillas con criterios temporales ad-hoc, función SQL de evaluación diaria vía pg_cron con zona horaria configurable, generación idempotente de tareas, y comando `/recurrencia` para creación conversacional con IA + botón de deshacer.

### Modified Capabilities
- `ingesta-durable`: El buffer extiende su esquema con `tipo_mensaje` (`'tarea'` | `'recurrencia'`) para distinguir el propósito semántico del mensaje independientemente de su formato (`tipo_media`). El webhook detecta comandos y setea `tipo_mensaje` antes del INSERT. El worker bifurca el procesamiento según `tipo_mensaje`.

## Impact

- **Base de datos (Supabase/PostgreSQL)**: nueva tabla `plantillas_recurrencia`, `ALTER TABLE configuracion_sistema ADD COLUMN valor_texto TEXT`, `ALTER TABLE buffer_ingesta_contingencia ADD COLUMN tipo_mensaje VARCHAR(20)`, nueva función SQL `evaluar_plantillas_recurrencia()`, nuevo job pg_cron.
- **Backend FastAPI**: webhook extendido con detección de comandos (`/recurrencia`, `/recurrencias`), worker extendido con bifurcación por `tipo_mensaje`, nuevo callback handler para botón [Deshacer], nuevo system prompt para estructuración de plantillas.
- **Telegram Bot**: dos nuevos comandos (`/recurrencia`, `/recurrencias`), botón inline [Deshacer] en confirmaciones de creación.
- **Dependencias**: sin nuevas dependencias externas. Reusa OpenRouter (IA), supabase-py (DB), httpx (Telegram API).
- **Documentación inicial**: V3 RF05 queda formalmente especificado. La tabla que V3/V4 asumían ahora existe con contrato normativo.
