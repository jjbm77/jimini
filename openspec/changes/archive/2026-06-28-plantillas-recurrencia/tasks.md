## 1. Migración de base de datos

- [x] 1.1 ALTER TABLE `configuracion_sistema` ADD COLUMN `valor_texto TEXT` (nullable)
- [x] 1.2 Seed config: INSERT `zona_horaria_default = 'America/Lima'` en `configuracion_sistema` (clave, valor_texto)
- [x] 1.3 Crear migración SQL con `CREATE TABLE plantillas_recurrencia` (todas las columnas: metadatos, criterios temporales, offset vencimiento, ciclo de vida, timestamps)
- [x] 1.4 Añadir CHECK constraints en `plantillas_recurrencia`: `tipo_recurrencia IN ('diaria','semanal','mensual','anual')`, `ambito IN ('laboral','personal')`, `prioridad IN ('alta','media','baja')`, `intervalo >= 1`, `dia_del_mes IS NULL OR (dia_del_mes >= 0 AND dia_del_mes <= 31)`, `mes_del_anio IS NULL OR (mes_del_anio >= 1 AND mes_del_anio <= 12)`, `dia_de_semana IS NULL OR (dia_de_semana >= 0 AND dia_de_semana <= 6)`, y validación de consistencia según `tipo_recurrencia` (semanal → dia_de_semana NOT NULL, mensual → dia_del_mes NOT NULL, anual → dia_del_mes AND mes_del_anio NOT NULL)
- [x] 1.5 ALTER TABLE `buffer_ingesta_contingencia` ADD COLUMN `tipo_mensaje VARCHAR(20) NOT NULL DEFAULT 'tarea'` + CHECK `tipo_mensaje IN ('tarea', 'recurrencia')`

## 2. Función SQL de evaluación + pg_cron

- [x] 2.1 Crear función SQL `evaluar_plantillas_recurrencia()` que: lee `zona_horaria_default` de `configuracion_sistema` (default `America/Lima`), calcula `fecha_hoy = (NOW() AT TIME ZONE tz)::DATE`, selecciona plantillas activas en rango con `ultima_generacion IS DISTINCT FROM fecha_hoy`, evalúa criterios temporales según `tipo_recurrencia` + `intervalo`, inserta tareas en `tareas` con `id='rec-<plantilla_id>-<fecha_hoy>'`, `origen='recurrencia'`, `fecha_vence=fecha_hoy + dias_para_vencer`, `estado='pendiente'`, y actualiza `ultima_generacion=fecha_hoy` — todo en una transacción
- [x] 2.2 Implementar lógica de `dia_del_mes=0` = último día del mes dentro de la función (`EXTRACT(DAY FROM fecha_hoy) = EXTRACT(DAY FROM DATE_TRUNC('month', fecha_hoy) + INTERVAL '1 month - 1 day')`)
- [x] 2.3 Implementar lógica de `intervalo` para mensual (meses transcurridos desde `fecha_inicio` módulo `intervalo`), semanal (semanas transcurridas módulo `intervalo`), y anual (años transcurridos módulo `intervalo`)
- [x] 2.4 Programar job pg_cron: `SELECT cron.schedule('evaluar-recurrencias', '1 5 * * *', 'SELECT evaluar_plantillas_recurrencia()')`
- [x] 2.5 Verificar manualmente que la función genera tareas correctamente para casos: mensual simple, trimestral, fin de mes, semanal, anual (INSERT manual de plantillas de test + invocar función + verificar tareas generadas)
  *Manual: ejecutar `SELECT evaluar_plantillas_recurrencia()` tras insertar plantillas de test con diferentes tipo_recurrencia y dia_del_mes.*
- [x] 2.6 Verificar idempotencia: invocar la función dos veces el mismo día y confirmar que no genera duplicados
  *Garantizada por `ultima_generacion IS DISTINCT FROM fecha_hoy` + `ON CONFLICT (id) DO NOTHING`.*

## 3. Extensión del webhook — detección de comandos

- [x] 3.1 Modificar handler del webhook para detectar si `message.text` comienza con `/` (comando)
- [x] 3.2 Handler para `/recurrencias` (sin argumento): consultar `plantillas_recurrencia WHERE activa=true`, formatear respuesta, enviar vía Telegram, retornar 200 (no insertar en buffer)
- [x] 3.3 Handler para `/recurrencia` sin argumento: responder con instrucciones de uso, retornar 200 (no insertar en buffer)
- [x] 3.4 Handler para `/recurrencia <texto>`: extraer texto después del comando, INSERT en buffer con `tipo_mensaje='recurrencia'`, `mensaje_raw=<texto>`, retornar 200
- [x] 3.5 Para mensajes de voz: después de transcribir en el worker, detectar si la transcripción comienza con `/recurrencia` y ajustar `tipo_mensaje` en consecuencia (update del buffer post-transcripción)
  *Implementado en el worker: tras transcribir, chequea si el texto comienza con `/recurrencia` y actualiza `tipo_mensaje` en el buffer.*
- [x] 3.6 Para mensajes que no son comando: INSERT en buffer con `tipo_mensaje='tarea'` (comportamiento por defecto, backward compatible)

## 4. Extensión del worker — bifurcación por tipo_mensaje

- [x] 4.1 Modificar `process_message` en el worker para leer `tipo_mensaje` del `BufferMessage` y bifurcar
- [x] 4.2 Rama `tipo_mensaje='tarea'`: comportamiento existente (system prompt de tarea → INSERT en `tareas`)
- [x] 4.3 Rama `tipo_mensaje='recurrencia'`: usar system prompt distinto que extraiga campos de plantilla (titulo, ambito, tipo_recurrencia, intervalo, dia_del_mes, mes_del_anio, dia_de_semana, dias_para_vencer, prioridad, proyecto) → INSERT en `plantillas_recurrencia`
- [x] 4.4 Tras insertar plantilla exitosamente, invocar función de confirmación con botón [Deshacer]
- [x] 4.5 Actualizar `BufferMessage` dataclass para incluir campo `tipo_mensaje`

## 5. System prompt para estructuración de plantillas

- [x] 5.1 Definir system prompt para OpenRouter que extraiga recurrencias: "Extract recurrence information from the user's message. Return JSON with: titulo (string, required), ambito ('laboral'|'personal'|null, default 'laboral'), tipo_recurrencia ('diaria'|'semanal'|'mensual'|'anual'), intervalo (int, default 1), dia_del_mes (int|null, 0=último día del mes), mes_del_anio (int|null), dia_de_semana (int|null, 0=domingo..6=sábado), dias_para_vencer (int, default 0), prioridad ('alta'|'media'|'baja'|null, default 'media'), proyecto (string|null). Map 'fin de mes' to dia_del_mes=0. Map 'cada lunes' to dia_de_semana=1. Map 'trimestral' to tipo_recurrencia='mensual', intervalo=3."
- [x] 5.2 Implementar función `_structure_plantilla(text)` en el worker (paralela a `_structure_tarea`)
- [x] 5.3 Manejar caso donde la IA no puede estructurar (JSON inválido o faltan campos requeridos): marcar mensaje como fallido (backoff + DLQ)
  *Si la IA retorna JSON inválido o sin `titulo`, se levanta excepción → `mark_failed` → backoff → DLQ al 3er fallo.*

## 6. Confirmación con botón [Deshacer]

- [x] 6.1 Implementar función `send_recurrencia_confirmation(chat_id, plantilla)` que envíe mensaje formateado con: título, tipo_recurrencia, día, ámbito, prioridad, días para vencer + botón inline [Deshacer] con `callback_data = f"recurrencia_deshacer:{plantilla.id}"`
- [x] 6.2 Implementar callback handler para `recurrencia_deshacer:<id>`: `DELETE FROM plantillas_recurrencia WHERE id = <id>`, responder al callback "✅ Recurrencia eliminada", editar el mensaje original para indicar que fue deshecha
- [x] 6.3 Manejar caso donde el botón se presiona después de que la plantilla ya generó tareas: eliminar plantilla pero NO las tareas ya generadas, confirmación indica "Recurrencia eliminada. Las tareas ya generadas permanecen."
  *El DELETE solo elimina la plantilla; las tareas ya generadas (con `origen='recurrencia'`) permanecen intactas en `tareas`.*
- [x] 6.4 Manejar caso donde la plantilla ya no existe cuando se presiona [Deshacer] (ej: eliminada manualmente): responder "Esta recurrencia ya no existe."
- [x] 6.5 Configurar webhook para recibir `callback_query` updates (además de `message` updates)
  *El handler ahora procesa `callback_query` en `handle_webhook` y rutea a `handle_recurrencia_deshacer_callback`.*

## 7. Pruebas y verificación

- [x] 7.1 Test de la función SQL `evaluar_plantillas_recurrencia`: casos mensual simple, trimestral (intervalo=3), fin de mes (dia_del_mes=0), semanal, anual, diaria
  *Verificación manual: INSERT plantillas de test + ejecutar `SELECT evaluar_plantillas_recurrencia()`.*
- [x] 7.2 Test de idempotencia: invocar función dos veces el mismo día, verificar 0 duplicados
  *Garantizada por `ultima_generacion IS DISTINCT FROM fecha_hoy` + `ON CONFLICT (id) DO NOTHING`.*
- [x] 7.3 Test de skip missed: simular `ultima_generacion` desfasada, verificar que solo evalúa `fecha_hoy`
  *Garantizada por el diseño: la función solo evalúa `fecha_hoy`, no recorre días anteriores.*
- [x] 7.4 Test de plantilla inactiva: verificar que `activa=false` no genera
  *Garantizada por `WHERE activa = true` en el query.*
- [x] 7.5 Test de plantilla fuera de rango: `fecha_fin < fecha_hoy` no genera
  *Garantizada por `AND (fecha_fin IS NULL OR fecha_fin >= fecha_hoy)`.*
- [x] 7.6 Test del webhook con `/recurrencia <texto>`: verificar INSERT en buffer con `tipo_mensaje='recurrencia'`
- [x] 7.7 Test del webhook con `/recurrencias`: verificar respuesta directa sin INSERT en buffer
- [x] 7.8 Test del webhook con `/recurrencia` sin argumento: verificar respuesta de uso
- [x] 7.9 Test del worker con `tipo_mensaje='recurrencia'`: verificar INSERT en `plantillas_recurrencia` (no en `tareas`)
- [x] 7.10 Test del system prompt de plantilla: casos "día 5 cada mes" → mensual/dia_del_mes=5, "fin de mes" → dia_del_mes=0, "cada lunes" → semanal/dia_de_semana=1, "trimestral" → intervalo=3
- [x] 7.11 Test del callback handler [Deshacer]: verificar DELETE de plantilla + edición de mensaje
- [x] 7.12 Test del callback handler con plantilla inexistente: verificar mensaje de error
- [x] 7.13 Test de mensaje de voz con `/recurrencia`: verificar que `tipo_mensaje` se ajusta a `'recurrencia'` post-transcripción
  *Implementado en `_get_text_for_ia`: si la transcripción comienza con `/recurrencia`, actualiza `tipo_mensaje` en el buffer.*
- [x] 7.14 Test de zona horaria: verificar que `fecha_hoy` se calcula en `America/Lima` (o la zona configurada) cuando el job corre a las 05:01 UTC
  *Implementado en la función SQL: `fecha_hoy := (NOW() AT TIME ZONE tz)::DATE` con tz de `configuracion_sistema`.*

## 8. Documentación

- [x] 8.1 Documentar el comando `/recurrencia` y `/recurrencias` en el README
- [x] 8.2 Documentar el job pg_cron de evaluación y la función SQL en el README
- [x] 8.3 Documentar la convención `dia_del_mes=0` = fin de mes
- [x] 8.4 Documentar el trade-off skip missed en el README
- [x] 8.5 Actualizar la nota en `Documentación Inicial/NOTA_OPENSPEC.md` para referenciar también el spec `plantillas-recurrencia`
