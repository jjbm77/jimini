## Why

V3 define a Pepe Grillo como un sistema "proactivo y agresivo de alertas" que "fuerza al usuario a responder", pero los documentos iniciales solo dejaron las columnas `nivel_hostigamiento` y `proxima_alerta_bloqueada_hasta` en la tabla `tareas` sin definir la lógica del motor que las lee y escribe. Sin hostigamiento, Jimini es un gestor de tareas pasivo: las tareas se crean (manualmente o vía recurrencias) pero el usuario nunca recibe alertas de vencimiento. Esta es la capacidad que da identidad al sistema — el alma de Pepe Grillo.

## What Changes

- **Worker de hostigamiento** (`worker_loop_hostigamiento`) que corre en el mismo proceso FastAPI vía `asyncio.gather` junto al worker del buffer. Evalúa tareas pendientes con `fecha_vence`, calcula el nivel de hostigamiento según los días de vencimiento, y envía alertas por Telegram con botones inline según el nivel.
- **5 niveles de hostigamiento (0-4)** basados en días respecto al vencimiento: aviso preventivo (-1 día), vence hoy (día 0), vencida corto (1-2 días), vencida medio (3-6 días), vencida largo (7+ días). Cada nivel tiene frecuencia de repetición, mensaje, y botones distintos.
- **Horario activo 09:00-21:00** (zona horaria configurable): las alertas solo se envían en este rango. Pepe no despierta al usuario de madrugada.
- **Botones inline de snooze (RF07)**: `[⏳ 2h]` y `[📅 Mañana]` en niveles 1 y 2. Pausan la escalada temporalmente vía `proxima_alerta_bloqueada_hasta` sin alterar `fecha_vence`.
- **Botones inline de resolución**: `[✅ Completar]` en todos los niveles, `[🗑️ Descartar]` en niveles 3-4, `[📅 Reprogramar]` postergado a change futura.
- **Nuevo estado `descartado`** en `tareas` — distinto de `completado` (se hizo) y `pendiente` (sigue activa). Descartar significa "se reconoce que ya no aplica".
- **Comando `/vacaciones <fecha>`** (RF10): activa modo vacaciones que silencia TODO el ámbito laboral hasta la fecha de retorno. Las alertas personales de nivel 2+ (vencidas) siguen activas.
- **Comando `/finde`** (RF10): activa modo fin de semana que silencia el ámbito laboral hasta lunes 08:30. Mismo comportamiento que vacaciones para alertas personales.
- **Auto-limpieza de modos**: el worker detecta cuando `fecha_liberacion < NOW()` y desactiva el modo automáticamente, sin job pg_cron adicional.
- **Comando `/tareas`**: lista tareas pendientes agrupadas por estado (vencidas, hoy, próximas, inbox). Complemento natural al hostigamiento — el usuario puede consultar el backlog cuando quiera.
- **Función SQL `calcular_nivel_hostigamiento(fecha_vence, now)`**: cálculo puro del nivel según días de vencimiento, reutilizable y testeable.

## Capabilities

### New Capabilities
- `hostigamiento-alertas`: Motor proactivo de alertas de vencimiento por Telegram. Cubre los 5 niveles de escalada, el worker de evaluación continua, los botones inline (snooze, completar, descartar), el horario activo, y la interacción con el sistema de hostigamiento. Resuelve RF07 (snooze inteligente) parcialmente (snooze implementado, reprogramar postergado).
- `modo-descanso`: Control de estados de desconexión global vía comandos `/vacaciones` y `/finde`. Silencia el ámbito laboral, mantiene alertas personales esenciales (nivel 2+), y auto-limpia cuando expira. Resuelve RF10.

### Modified Capabilities
- `ingesta-durable`: El webhook extiende la detección de comandos para incluir `/vacaciones`, `/finde`, y `/tareas` (además de `/recurrencia` y `/recurrencias` ya implementados). Los callbacks de snooze/completar/descartar se rutean vía el handler de `callback_query` existente. El estado `descartado` se añade al CHECK constraint de `tareas.estado`.

## Impact

- **Base de datos**: `ALTER TABLE tareas` para añadir `descartado` al CHECK constraint de `estado`. Seed de `configuracion_sistema` con claves `modo_vacaciones` y `modo_finde` (default inactivo). Sin nuevas tablas.
- **Backend FastAPI**: nuevo módulo `hostigamiento/` con el worker loop, cálculo de nivel, y envío de alertas. `main.py` extiende `asyncio.gather` para incluir `worker_loop_hostigamiento`. Webhook extiende detección de comandos (`/vacaciones`, `/finde`, `/tareas`).
- **Telegram Bot**: 5 nuevos tipos de callback (`snooze_2h`, `snooze_manana`, `completar`, `descartar`, `info_tarea`). 3 nuevos comandos (`/vacaciones`, `/finde`, `/tareas`). Mensajes de alerta con formatos distintos por nivel.
- **Dependencias**: sin nuevas. Reusa httpx (Telegram API), supabase-py (DB), asyncio (worker).
- **Documentación inicial**: RF07 y RF10 quedan formalmente especificados. Las columnas `nivel_hostigamiento` y `proxima_alerta_bloqueada_hasta` que V3 dejó sin lógica ahora tienen contrato normativo.