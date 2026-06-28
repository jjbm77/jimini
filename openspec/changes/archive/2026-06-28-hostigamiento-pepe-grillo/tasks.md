## 1. Migración de base de datos

- [x] 1.1 ALTER TABLE `tareas`: DROP CONSTRAINT existente de `estado` y ADD CONSTRAINT con `estado IN ('pendiente', 'completado', 'descartado')`
- [x] 1.2 Seed `configuracion_sistema`: INSERT claves `modo_vacaciones` (valor_booleano=false, fecha_liberacion=NULL) y `modo_finde` (valor_booleano=false, fecha_liberacion=NULL)
- [x] 1.3 Crear función SQL `calcular_nivel_hostigamiento(p_fecha_vence DATE, p_now TIMESTAMP) RETURNS INT`: nivel 0 si vence mañana, 1 si vence hoy, 2 si vencida 1-2 días, 3 si vencida 3-6 días, 4 si vencida 7+, -1 si no vencida y no es día anterior
- [x] 1.4 Crear función SQL `frecuencia_nivel(p_nivel INT) RETURNS INTERVAL`: nivel 0 → NULL (no repite), 1 → '4 hours', 2 → '3 hours', 3 → '4 hours', 4 → '1 day'

## 2. Módulo de hostigamiento

- [x] 2.1 Crear `src/jimini/hostigamiento/__init__.py`
- [x] 2.2 Implementar función `calcular_nivel(fecha_vence, now) -> int` que llama a la función SQL `calcular_nivel_hostigamiento` vía RPC
- [x] 2.3 Implementar función `frecuencia_nivel(nivel) -> timedelta` que llama a la función SQL `frecuencia_nivel` vía RPC (o mapeo en Python)
- [x] 2.4 Implementar función `get_modo_vacaciones() -> dict | None` que lee `configuracion_sistema` clave `modo_vacaciones` (returns {activo, fecha_liberacion} or None)
- [x] 2.5 Implementar función `get_modo_finde() -> dict | None` que lee `configuracion_sistema` clave `modo_finde`
- [x] 2.6 Implementar función `auto_limpiar_modos()`: si `modo_vacaciones.fecha_liberacion <= NOW()`, UPDATE a false/NULL; igual para `modo_finde`
- [x] 2.7 Implementar función `debe_alertar(tarea_ambito, nivel, modo_vacaciones, modo_finde) -> bool`: laboral silenciado si modo activo; personal silenciado si nivel 0-1 y modo activo; personal sigue si nivel 2+ y modo activo
- [x] 2.8 Implementar función `dentro_horario_activo(now) -> bool`: verifica si la hora en zona del usuario (usando `zona_horaria_default` de config) está entre 09:00 y 21:00

## 3. Worker de hostigamiento

- [x] 3.1 Implementar `worker_loop_hostigamiento()` que corre `while True`: auto_limpiar_modos() → query tareas → evaluar → enviar alertas → sleep 60s
- [x] 3.2 Query de tareas: `SELECT * FROM tareas WHERE estado='pendiente' AND fecha_vence IS NOT NULL AND (proxima_alerta_bloqueada_hasta IS NULL OR proxima_alerta_bloqueada_hasta <= NOW())`
- [x] 3.3 Para cada tarea: calcular nivel → comparar con `nivel_hostigamiento` actual → si subió, enviar alerta y UPDATE `nivel_hostigamiento` + `proxima_alerta_bloqueada_hasta` → si igual y toca repetir (frecuencia expirada), enviar alerta y UPDATE `proxima_alerta_bloqueada_hasta`
- [x] 3.4 Filtrar por `dentro_horario_activo`: si fuera de horario, skip envío (no skip cálculo de nivel)
- [x] 3.5 Filtrar por `debe_alertar`: si modo vacaciones/finde bloquea esa tarea/ámbito, skip
- [x] 3.6 Integrar en `main.py`: extender `asyncio.gather` con `worker_loop_hostigamiento()` además de `worker_loop_buffer()`

## 4. Envío de alertas por nivel

- [x] 4.1 Implementar función `enviar_alerta_telegram(chat_id, tarea, nivel)`: construye mensaje según nivel + botones inline según nivel + envía via Telegram API
- [x] 4.2 Mensaje nivel 0: `📅 Recuerda: '{titulo}' vence mañana.` + botón [✅ Completar]
- [x] 4.3 Mensaje nivel 1: `⚠️ '{titulo}' vence HOY. ¿Lo resolvemos?` + botones [⏳ 2h] [📅 Mañana] [✅ Completar]
- [x] 4.4 Mensaje nivel 2: `🔴 '{titulo}' está vencida (N días). Hay que resolverlo.` + botones [⏳ 2h] [📅 Mañana] [✅ Completar]
- [x] 4.5 Mensaje nivel 3: `🚨 '{titulo}' lleva N días vencida. ¿Sigue siendo relevante?` + botones [✅ Completar] [🗑️ Descartar]
- [x] 4.6 Mensaje nivel 4: `📈 '{titulo}' lleva una semana+ vencida. Necesito que la completes o descartes.` + botones [✅ Completar] [🗑️ Descartar]
- [x] 4.7 `callback_data` formato: `snooze_2h:<tarea_id>`, `snooze_manana:<tarea_id>`, `completar:<tarea_id>`, `descartar:<tarea_id>`

## 5. Callback handlers de hostigamiento

- [x] 5.1 Extender `handle_webhook` para procesar `callback_query` con prefijos `snooze_2h:`, `snooze_manana:`, `completar:`, `descartar:` (además de `recurrencia_deshacer:` ya existente)
- [x] 5.2 Handler `snooze_2h:<id>`: `UPDATE tareas SET proxima_alerta_bloqueada_hasta = NOW() + 2h WHERE id` + `answerCallbackQuery("⏳ Pospuesto 2 horas")`
- [x] 5.3 Handler `snooze_manana:<id>`: `UPDATE tareas SET proxima_alerta_bloqueada_hasta = TOMORROW 09:00 WHERE id` + `answerCallbackQuery("📅 Pospuesto para mañana")`
- [x] 5.4 Handler `completar:<id>`: `UPDATE tareas SET estado='completado' WHERE id` + `answerCallbackQuery("✅ Completada")`
- [x] 5.5 Handler `descartar:<id>`: `UPDATE tareas SET estado='descartado' WHERE id` + `answerCallbackQuery("🗑️ Descartada")`
- [x] 5.6 Handler con tarea inexistente: `answerCallbackQuery("Esta tarea ya no existe.")`
- [x] 5.7 Tras completar/descartar, editar el mensaje original de la alerta para indicar que fue resuelta (ej: tachar o añadir "✅ Resuelta")

## 6. Comandos /vacaciones y /finde

- [x] 6.1 Handler `/vacaciones <fecha>`: parsear fecha (formatos DD/MM/YYYY o YYYY-MM-DD), INSERT/UPDATE `configuracion_sistema` clave `modo_vacaciones` con `valor_booleano=true` y `fecha_liberacion=<fecha>`, responder confirmación
- [x] 6.2 Handler `/vacaciones` sin argumento: consultar estado actual de `modo_vacaciones`, responder "activado hasta {fecha}" o "no estás en modo vacaciones"
- [x] 6.3 Handler `/finde`: calcular próximo lunes 08:30 en zona del usuario, INSERT/UPDATE `configuracion_sistema` clave `modo_finde` con `valor_booleano=true` y `fecha_liberacion` calculada, responder confirmación
- [x] 6.4 Validación de fecha en `/vacaciones`: si el formato es inválido o la fecha es pasada, responder con error
- [x] 6.5 Ninguno de estos comandos inserta en el buffer (respuesta directa)

## 7. Comando /tareas

- [x] 7.1 Handler `/tareas`: consultar `SELECT id, titulo, fecha_vence, ambito, prioridad FROM tareas WHERE estado='pendiente' ORDER BY fecha_vence NULLS LAST`
- [x] 7.2 Agrupar resultados en: vencidas (fecha_vence < CURRENT_DATE), hoy (fecha_vence = CURRENT_DATE), próximas (fecha_vence > CURRENT_DATE), inbox (fecha_vence IS NULL)
- [x] 7.3 Formatear respuesta con emojis y secciones: `🔴 Vencidas:`, `⚠️ Hoy:`, `📅 Próximas:`, `📥 Inbox:`
- [x] 7.4 Si un grupo está vacío, omitir la sección. Si no hay tareas pendientes, responder "No tienes tareas pendientes. 🎉"
- [x] 7.5 No inserta en buffer, no invoca IA

## 8. Pruebas y verificación

- [x] 8.1 Test de la función SQL `calcular_nivel_hostigamiento`: casos fecha_vence=mañana→0,=hoy→1,ayer→2,-3días→3,-7días→4,+2días→-1
- [x] 8.2 Test de la función SQL `frecuencia_nivel`: nivel 0→NULL, 1→4h, 2→3h, 3→4h, 4→1day
- [x] 8.3 Test del worker: simular tarea vencida nivel 2, verificar que se envía alerta y se setea `proxima_alerta_bloqueada_hasta`
- [x] 8.4 Test del horario activo: simular hora 22:00, verificar que no se envía alerta
- [x] 8.5 Test de snooze: presionar callback `snooze_2h`, verificar `proxima_alerta_bloqueada_hasta = NOW() + 2h`
- [x] 8.6 Test de completar: presionar callback `completar`, verificar `estado='completado'`
- [x] 8.7 Test de descartar: presionar callback `descartar`, verificar `estado='descartado'`
- [x] 8.8 Test de modo vacaciones: activar `/vacaciones`, verificar que tareas laborales no se alertan, tareas personales nivel 2+ sí
- [x] 8.9 Test de auto-limpieza: simular `fecha_liberacion` pasada, verificar que el modo se desactiva
- [x] 8.10 Test de `/tareas`: verificar formato de la lista agrupada y que descartadas no aparecen
- [x] 8.11 Test de nivel subiendo: tarea pasa de nivel 1 a 2, verificar que se envía alerta nueva (no repetición)
- [x] 8.12 Test de tarea sin fecha_vence: verificar que no es seleccionada por el worker

## 9. Documentación

- [x] 9.1 Documentar el módulo de hostigamiento en el README: 5 niveles, horario activo, frecuencias
- [x] 9.2 Documentar los comandos `/vacaciones`, `/finde`, `/tareas` en el README
- [x] 9.3 Documentar el estado `descartado` y su diferencia con `completado`
- [x] 9.4 Actualizar `Documentación Inicial/NOTA_OPENSPEC.md` para referenciar los specs `hostigamiento-alertas` y `modo-descanso`