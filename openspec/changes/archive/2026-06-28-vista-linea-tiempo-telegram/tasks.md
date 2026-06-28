## 1. Handlers de comando

- [x] 1.1 Crear `src/jimini/hostigamiento/comandos.py` (si no existe) o añadir funciones `handle_hoy`, `handle_semana`, `handle_mes`
- [x] 1.2 Implementar `handle_hoy(chat_id)`: query `tareas WHERE estado='pendiente' AND fecha_vence = CURRENT_DATE` (en zona del usuario), formatear respuesta con emojis de ámbito, responder con "🎉 No tienes tareas para hoy." si vacío
- [x] 1.3 Implementar `handle_semana(chat_id)`: query `tareas WHERE estado='pendiente' AND fecha_vence BETWEEN CURRENT_DATE AND CURRENT_DATE + 7 + vencidas`, agrupar por día con encabezado `📅 DiaSem DD`, días sin tareas omitidos, encabezado `🔴 Vencidas:` para tareas anteriorees
- [x] 1.4 Implementar `handle_mes(chat_id, mes=None)`: calcular primer día del mes (Lunes-Domingo), generar grid ASCII con semanas, poblar celdas con indicadores emoji (🔵🟠🟡⚡), incluir leyenda
- [x] 1.5 Formato de celda en /mes: hasta 3 emojis por día (🔵 laboral, 🟠 personal, 🟡 recurrencia, ⚡ vencida), sin repetir el mismo emoji

## 2. Extensión del webhook

- [x] 2.1 Añadir constantes `_CMD_HOY`, `_CMD_SEMANA`, `_CMD_MES` en `webhook/handler.py`
- [x] 2.2 Extender `_handle_text` para detectar `/hoy`, `/semana`, `/mes [N]` antes del INSERT en buffer
- [x] 2.3 Llamar a los handlers correspondientes vía import de `hostigamiento/comandos`
- [x] 2.4 `/mes` sin argumento → mes actual; `/mes N` (1-12) → mes N del año actual

## 3. Funciones auxiliares

- [x] 3.1 Implementar `_get_date_in_tz()` que retorne CURRENT_DATE en la zona horaria configurada (reusa lógica de `zona_horaria_default`)
- [x] 3.2 Implementar `_build_emoji_for_tarea(tarea) -> str`: retorna el emoji correspondiente según ámbito (🔵/🟠) más ⚡ si vencida, 🔄 si recurrencia
- [x] 3.3 Implementar `_month_grid(year, month, tareas_por_dia) -> str`: genera el grid ASCII del mes con días de la semana y celdas
- [x] 3.4 Implementar `_format_dia_semana(dia_semana_iso: int) -> str`: Lun, Mar, Mié, Jue, Vie, Sáb, Dom

## 4. Pruebas

- [x] 4.1 Test de `/hoy` con tareas hoy: verifica formato y emojis
- [x] 4.2 Test de `/hoy` sin tareas: verifica mensaje de celebración
- [x] 4.3 Test de `/semana` con días con y sin tareas: verifica agrupación y omisión de días vacíos
- [x] 4.4 Test de `/semana` con tareas vencidas: verifica encabezado `🔴 Vencidas:`
- [x] 4.5 Test de `/mes` actual: verifica grid ASCII con longitud de semanas correcta
- [x] 4.6 Test de `/mes 8` (agosto): verifica selección de mes y título
- [x] 4.7 Test de consistencia de emojis entre comandos: misma tarea tiene mismo emoji en /hoy, /semana, /mes
- [x] 4.8 Test de zona horaria: tarea con fecha_vence en UTC-5, CURRENT_DATE en zona Lima → aparece en /hoy correctamente

## 5. Documentación

- [x] 5.1 Documentar `/hoy`, `/semana`, `/mes` en el README como comandos de vista de línea de tiempo
- [x] 5.2 Documentar la convención de emojis en `README.md`
- [x] 5.3 Actualizar `Documentación Inicial/NOTA_OPENSPEC.md` para referenciar el spec `vista-linea-tiempo`