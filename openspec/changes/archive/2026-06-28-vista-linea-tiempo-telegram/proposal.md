## Why

V3 identifica la "ausencia de vista de línea de tiempo" como uno de los gaps del sistema. El usuario necesita ver sus tareas en formato calendario para correlacionar vencimientos sin tener que revisar listados de texto. RF06 proponía Google Calendar como solución, pero el setup (OAuth/Service Account) es engorroso y desproporcionado para el valor marginal. Las tareas de Pepe Grillo son puntos en el tiempo (fechas de vencimiento), no rangos — una vista de línea de tiempo simple en Telegram resuelve el problema con cero dependencias nuevas.

## What Changes

- **Comando `/hoy`** — alias rápido de `/tareas` filtrado al día actual. Muestra solo tareas con `fecha_vence = CURRENT_DATE`.
- **Comando `/semana`** — tareas de los próximos 7 días agrupadas por día. Omite días sin tareas. Incluye tareas vencidas de días anteriores (acumuladas en el encabezado).
- **Comando `/mes [n]`** — vista calendario del mes actual (o mes especificado, 1-12) en formato monospace con emojis por ámbito. Cada celda muestra indicadores de cantidad y tipo de tareas.
- **Emojis por ámbito**: `🔵` laboral, `🟠` personal, `⚡` vencida, `🔄` recurrencia. Consistentes en los tres comandos.
- **Sin dependencias externas**: reusa el patrón de comandos existente (`/tareas`, `/recurrencias`). No API de Google Calendar, no OAuth, no Service Account.

## Capabilities

### New Capabilities
- `vista-linea-tiempo`: Vista de tareas en formato calendario vía comandos de Telegram: `/hoy` (día actual), `/semana` (7 días), `/mes [n]` (vista mensual). Los tres comandos usan agrupación por día con emojis por ámbito y origen. Decisión explícita de no usar Google Calendar como backend — puramente Telegram con datos de la tabla `tareas`.

### Modified Capabilities
- `ingesta-durable`: El webhook extiende la detección de comandos para incluir `/hoy`, `/semana`, y `/mes` (además de los ya implementados `/*`). Todos responden directamente sin insertar en buffer ni invocar IA.

## Impact

- **Backend FastAPI**: webhook extendido con 3 nuevos handlers de comando. Sin nuevas dependencias Python.
- **Telegram Bot**: 3 nuevos comandos. Sin nuevos callbacks.
- **Base de datos**: sin cambios. Los comandos solo leen la tabla `tareas` (filtrando `estado='pendiente'`).
- **Dependencias**: cero nuevas. Reusa httpx, supa base-py, python-dateutil (ya instalados para el sistema de hostigamiento).