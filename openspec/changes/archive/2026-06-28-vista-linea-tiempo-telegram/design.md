## Context

El sistema Jimini tiene implementados los comandos de Telegram: `/tareas` (listado), `/recurrencia` (crear plantilla), `/recurrencias` (listar plantillas), `/vacaciones`, `/finde`. Todos responden directamente sin pasar por el buffer. El patrón está establecido: el webhook detecta el comando, consulta la DB, formatea la respuesta, y la envía.

La tabla `tareas` tiene todas las columnas necesarias: `titulo`, `fecha_vence`, `ambito`, `prioridad`, `estado`, `chat_id`. Sin cambios de schema requeridos.

Restricciones:
- **Telegram como único canal**: las respuestas son mensajes de texto. No se renderiza HTML ni imágenes.
- **Sin dependencias externas**: mantenemos el principio de "capas gratuitas". No introducir APIs nuevas.
- **Commensrate**: reusar el patrón de `/tareas` ya implementado en `hostigamiento/comandos.py`.

Stakeholders: usuario único (Jaime), docenas de tareas pendientes (no cientos). Las vistas de semana y mes deben ser legibles con emojis como indicadores visuales.

## Goals / Non-Goals

**Goals:**
- Proporcionar al usuario una vista rápida de "qué vence hoy" (`/hoy`).
- Proporcionar una vista semanal que muestre tareas agrupadas por día para planificación a corto plazo (`/semana`).
- Proporcionar una vista mensual compacta con indicadores visuales para tener panorama del mes (`/mes [n]`).
- Mantener consistencia visual con `/tareas` (mismos emojis, mismo formato).

**Non-Goals:**
- **No** implementar sincronización con Google Calendar (RF06). Descartado por complejidad de setup.
- **No** renderizar HTML o gráficos. Puramente texto + emojis en Telegram.
- **No** implementar comandos de navegación entre meses (flechas, botones inline). V1 usa argumentos (`/mes 8` para agosto).
- **No** implementar vista semanal de semanas pasadas. `/semana` siempre muestra los próximos 7 días desde hoy.
- **No** implementar coloreo o formato rich text de Telegram. Solo emojis + texto.
- **No** implementar repetición del comando (no es interactivo más allá del envío). El usuario lo llama cuando lo necesita.

## Decisions

### D1: Vista semanal — 7 días desde hoy, con vencidas acumuladas

**Decisión**: `/semana` muestra tareas con `fecha_vence` entre `CURRENT_DATE` y `CURRENT_DATE + 7`. Las tareas vencidas (`fecha_vence < CURRENT_DATE`) se muestran en un encabezado separado. Los días sin tareas se omiten.

**Alternativas consideradas**:
- *Mostrar solo 7 días sin vencidas*: las tareas vencidas desaparecen visualmente. Malo para visibilidad de backlog.
- *Mostrar infinito hacia atrás*: abruma la vista. `/tareas` ya cubre el backlog completo.
- *Mostrar vencidas pero compactado*: "3 tareas vencidas" en vez de listarlas una a una. Podría ser un flag futuro (`/semana --compact`).

**Razón**: Las vencidas son importantes (requieren acción), pero dominarían la vista si se listan completas. El encabezado separado da visibilidad sin abrumar. Consistente con el diseño de `/tareas`.

### D2: Vista mensual — grid con emojis, sin texto completo

**Decisión**: `/mes [n]` muestra un grid ASCII del mes con indicadores de emoji por día. Cada celda muestra hasta 3 indicadores (🔵🟠⚡). El usuario puede pedir `/semana` o `/hoy` para ver detalle de un día específico.

```
┌───┬───┬───┬───┬───┬───┬───┐
│Lu │Ma │Mi │Ju │Vi │Sá │Do │
├───┼───┼───┼───┼───┼───┼───┤
│   │ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │
│   │   │   │   │   │🔵⚡│   │
├───┼───┼───┼───┼───┼───┼───┤
│ 7 │ 8 │ 9 │10 │11 │12 │13 │
│🔵⚡│🔵 │   │🔵🟠│   │🟡 │   │
└───┴───┴───┴───┴───┴───┴───┘
🔵 laboral  🟠 personal  🟡 recurrencia  ⚡ vencida
```

**Alternativas consideradas**:
- *Lista agrupada por día (como /semana)*: para un mes con varios días, la lista es larga. El grid es más compacto.
- *Grid con día clickable*: requiere botones inline y callbacks. Complejidad injustificada para v1.
- *Grid scrollable horizontal en Telegram*: Telegram no soporta scroll horizontal en mensajes.

**Razón**: El grid con emojis es la forma más compacta de mostrar un mes entero en un solo mensaje de Telegram. La clave es que los emojis son indicadores, no texto: `🔵⚡` = "al menos una tarea laboral, al menos una vencida". Para detalle, el usuario usa `/hoy` o `/semana`.

### D3: `/hoy` es un comando independiente (no alias de `/tareas` filtrado)

**Decisión**: `/hoy` es un comando separado de `/tareas`. Muestra solo tareas con `fecha_vence = CURRENT_DATE`, con formato más compacto (sin agrupación de inbox/proximas).

**Alternativas consideradas**:
- *`/tareas --hoy` o `/tareas hoy`*: unifica comandos pero requiere parsing de argumentos. Patrón establecido: comandos separados.
- *Redirigir `/hoy` al handler de `/tareas` con filtro*: más código compartido pero ¿qué pasa si el usuario quiere `/tareas` con todas las secciones?

**Razón**: Comandos separados son más simples de implementar y usar. El usuario entiende `/hoy` intuitivamente. El código es mínimo (un query adicional).

### D4: Sin cambios de schema, sin dependencias externas

**Decisión**: Esta change no modifica el schema de base de datos ni añade dependencias Python. Todo es extensión del webhook handler existente.

**Razón**: Los datos ya existen en `tareas`. Los comandos son consultas de lectura. El patrón de comandos está establecido en `hostigamiento/comandos.py` (`/tareas`, `/vacaciones`, `/finde`). Seguimos ese patrón sin inventar nada nuevo.

## Risks / Trade-offs

- **[Legibilidad en pantallas pequeñas]**: la vista mensual en mobile puede truncar líneas. Telegram permite ver mensajes completos con "more". Emojis funcionan bien en cualquier tamaño.
- **[Mes con muchas tareas]**: 30 tareas en un solo día → la celda muestra emojis por tipo, no por cantidad. Si el usuario necesita detalle, usa `/hoy` o `/semana`.
- **[Encoding de caracteres de tabla]**: caracteres Unicode como ─, ┼, ┬ deben preservarse. Telegram los soporta desde 2016. Verificar en pruebas con cliente real.
- **[Timezone en /hoy y /semana]**: CURRENT_DATE debe usar zona horaria del usuario. Reusa la misma lógica de `zona_horaria_default` ya implementada para hostigamiento y recurrencias.

## Migration Plan

Sin migración. Los comandos se añaden al webhook handler existente. Al ser solo lectura, no hay riesgo de pérdida de datos.

1. **Registrar nuevos comandos** en el handler de `_handle_text`: `/hoy`, `/semana`, `/mes`.
2. **Desplegar FastAPI** con el webhook extendido.
3. El usuario recibe el nuevo menú de comandos (Telegram los registra automáticamente vía BotFather o al usarlos).

**Rollback**: eliminar los handlers de los 3 comandos. Volver a desplegar. Sin data loss.

## Open Questions

- **Vista semanal de una semana específica**: `/semana 5` para la semana 5 del año? No para v1 — siempre es "próximos 7 días". Se puede añadir como flag futuro.
- **Toques en la vista numérica del /mes**: ¿convención Lunes-Domingo (ISO) o Domingo-Sábado (USA)? Decisión: Lunes-Domingo (ISO 8601, consistente con Latinoamérica).
- **Sobrecarga visual de emojis**: ¿demasiados emojis? Si resulta intrusivo, se puede hacer toggle con flag (`/mes --compact` sin emoji). Monitorizar uso real.
