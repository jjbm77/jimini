## Context

El sistema Jimini tiene implementadas la ingesta durable (buffer con lease, transcripción de audio) y las plantillas de recurrencia (creación vía `/recurrencia`, evaluación di vía pg_cron). La tabla `tareas` recibe tareas de ambas fuentes, pero **nadie las alerta al usuario**. Las columnas `nivel_hostigamiento INT DEFAULT 0` y `proxima_alerta_bloqueada_hasta TIMESTAMP DEFAULT NULL` existen en el schema V3 pero ningún código las lee o escribe. RF07 (snooze inteligente) y RF10 (modo vacaciones) definen el comportamiento deseado pero no la implementación.

Restricciones heredadas:
- **Proceso FastAPI único**: el worker del buffer ya corre como `asyncio.create_task` en `startup`. El worker de hostigamiento debe coexistir en el mismo proceso.
- **pg_cron ya en uso**: 3 jobs activos (reclaim stale locks, evaluar recurrencias). No se necesita un nuevo job pg_cron para hostigamiento — el polling del worker es suficiente.
- **Callback handler existente**: `handle_webhook` ya procesa `callback_query` updates (implementado en `plantillas-recurrencia` para el botón [Deshacer]). El patrón se extiende con nuevos prefijos de callback_data.
- **Zona horaria configurable**: `configuracion_sistema.zona_horaria_default` ya existe (default `America/Lima`), sembrado en la change de plantillas. El horario activo 09-21 se evalúa en esa zona.
- **Framework Simplicidad + Efectividad** (V3 §3): el worker de hostigamiento reusa el patrón del worker del buffer. El cálculo de nivel es una función SQL pura. Los callbacks reusan el handler existente.

Stakeholders: usuario único (Jaime), uso personal, tráfico bajo. El hostigamiento es la capacidad que da identidad al sistema — sin él, Jimini es un gestor de tareas pasivo.

## Goals / Non-Goals

**Goals:**
- Implementar el motor de hostigamiento que V3 definió conceptualmente pero dejó sin lógica.
- Escalar las alertas en 5 niveles según el vencimiento, con frecuencia de repetición decreciente.
- Implementar botones de snooze (RF07) y resolución (completar, descartar) vía callbacks de Telegram.
- Implementar modos de descanso (RF10) con auto-limpieza.
- Añadir el comando `/tareas` para consultar el backlog activivo.

**Non-Goals:**
- **No** implementar button [Reprogramar] en nivel 4. Postergado a change futura (D5). Nivel 4 usa solo [Completar] y [Descartar].
- **No** implementar tono dinámico de mensajes con IA. Los mensajes por nivel son templates fijos (no se usa OpenRouter para generarlos). Es más simple, más predecible, y cuesta 0 tokens.
- **No** implementar `/vacaciones` con retorno automático vía pg_cron. La auto-limpieza la hace el worker en cada iteración (chequea `fecha_liberacion < NOW()`). No necesita job adicional.
- **No** implementar un dashboard web de tareas. El comando `/tareas` lista en Telegram. La app web es change futura.
- **No** implementar alertas antes del día -1. El nivel 0 (aviso preventivo) dispara solo el día anterior al vencimiento, no antes.
- **No** implementar notificaciones por canal distinto a Telegram. Sin email, sin push web. Telegram es el único canal.

## Decisions

### D1: Filosofía híbrida (vencimiento + inacción)

**Decisión**: El hostigamiento se basa en el vencimiento (`fecha_vence`) para determinar cuándo empezar y el nivel. La inacción del usuario (no presionar botones) determina la frecuencia de repetición dentro de cada nivel. Tareas sin `fecha_vence` no son hostigadas (viven en inbox).

**Alternativas consideradas**:
- *Calendario puro (Filosofía A)*: nivel basado solo en fecha_vence, sin repetición si el usuario ignora. Derrota el propósito de "hostigamiento" — un calendar pasivo.
- *Inacción pura (Filosofía B)*: hostiga desde la creación, sin fecha_vence. Hostiga tareas de "dumping" (inbox) que no necesitan presión. Inapropiado para ideas sin compromiso de fecha.

**Razón**: El usuario es jefatura de proyectos — la mayoría de tareas tienen fecha_vence (entregables, reuniones, pagos). Las tareas sin fecha son "dumping" de ideas que no necesitan hostigamiento. El vencimiento es el trigger natural; la repetición por inacción es lo que hace a Pepe "agresivo".

### D2: 5 niveles con horario activo 09-21, nuevo estado `descartado`

**Decisión**: 5 niveles (0-4) con triggers temporales, frecuencias, mensajes y botones distintos:

| Nivel | Trigger | Frecuencia | Botones |
|---|---|---|---|
| 0 (aviso) | -1 día | Una vez | [Completar] |
| 1 (hoy) | día 0 | Cada 4h (09,13,17,21) | [Snooze 2h] [Snooze Mañana] [Completar] |
| 2 (vencida corto) | +1 a +2 días | Cada 3h (09,12,15,18,21) | [Snooze 2h] [Snooze Mañana] [Completar] |
| 3 (vencida medio) | +3 a +6 días | Cada 4h (09,13,17,21) | [Completar] [Descartar] |
| 4 (vencida largo) | +7 días o más | Diario 09:00 | [Completar] [Descartar] |

Horario activo 09:00-21:00 en zona horaria del usuario. Fuera de ese rango, el worker no envía alertas pero el cálculo de nivel sí avanza.

Nuevo estado `descartado` en `tareas.estado` — distinto de `completado` (se hizo) y `pendiente` (sigue activa). `descartado` = "se reconoce que ya no aplica".

**Alternativas consideradas**:
- *3 niveles (aviso, vencida, vencida crítica)*: demasiado granular, no permite diferenciar "1 día vencida" de "7 días vencida".
- *Sin horario activo*: Pepe despierta al usuario a las 3am. Inaceptable.
- *Estado `descartado` = DELETE*: pierde auditoría. Saber qué se descartó vs qué se completó es valioso para reportes futuros.

**Razón**: 5 niveles dan granularidad suficiente para escalar la presión sin ser una ametralladora. El horario 09-21 respeta el descanso. `descartado` preserva historial. Los snooze solo en niveles 1-2 (RF07 los menciona explícitamente para "nivel 1 y 2"). Niveles 3-4 pierden snooze — a los 3+ días no es aceptable "posponer 2 horas".

### D3: Worker while True en mismo proceso FastAPI

**Decisión**: `worker_loop_hostigamiento()` corre en el mismo proceso FastAPI vía `asyncio.gather(worker_loop_buffer(), worker_loop_hostigamiento())`. Polling cada 60s.

**Alternativas consideradas**:
- *pg_cron puro*: pg_cron no puede enviar HTTP a Telegram (no tiene client HTTP). Necesitaría tabla intermedia + worker que la drene = Opción 1 con pasos extra.
- *Híbrido pg_cron + worker*: añade columna `proxima_alerta` y complejidad de dos fases. El worker puede calcular directamente qué tocaría alertar.

**Razón**: Reusa el patrón existente (worker_loop_buffer). Polling cada 60s es trivial para tráfico personal. Un solo proceso, sin nueva infraestructura. Si el proceso cae, el hostigamiento se pausa — pero las recurrencias (pg_cron) siguen generando tareas que se acumularán para cuando el worker levante.

### D4: Modo vacaciones — laboral silenciado, personal niveles 2-4

**Decisión**: En modo vacaciones/finde, el ámbito `laboral` se silencia completamente (niveles 0-4). El ámbito `personal` se silencia para niveles 0-1 (aviso preventivo y vence-hoy) pero continúa para niveles 2-4 (vencidas).

**Alternativas consideradas**:
- *Personal completamente silenciado*: algo vencido 5 días (pago atrasado, multa) no se alerta. Riesgoso para finanzas personales.
- *Personal completamente activo*:Pepe te recuerda "mañana vence X personal" en vacaciones. Innecesario, arruina el descanso.

**Razón**: "Esencial" (RF10) se interpreta como compromiso roto con consecuencias. Niveles 0-1 son preventivos (no vencidos); niveles 2-4 son reactivos (ya vencidos). Solo lo reactivo justifica interrumpir vacaciones.

Auto-limpieza: el worker chequea `fecha_liberacion < NOW()` en cada iteración. Si expiró, limpia el flag en `configuracion_sistema`. No necesita job pg_cron.

### D5: [Reprogramar] postergado a change futura

**Decisión**: El botón [Reprogramar] en nivel 4 no se implementa en esta change. Nivel 4 usa solo [Completar] y [Descartar].

**Alternativas consideradas**:
- *Implementar con estado conversacional*: pedir fecha al usuario por texto, parsear con IA, actualizar `fecha_vence`. Añade estado conversacional (flag temporal, timeout) que no existe hoy.
- *Implementar con botones de fecha prefabricados*: [+1 semana] [+1 mes] [Próximo lunes]. Limita opciones pero más simple.

**Razón**: Postergar reduce scope. El usuario que quiere reprogramar puede descartar la tarea y crear una nueva con `/recurrencia` o mensaje de texto. Es menos elegante pero funcional. El estado conversacional es un patrón nuevo que merece su propia exploración (beneficia a múltiples features, no solo hostigamiento).

### D6: `proxima_alerta_bloqueada_hasta` dual-use (snooze + frecuencia)

**Decisión**: La columna `proxima_alerta_bloqueada_hasta` (ya existe en V3) se usa para dos propósitos: (1) snooze manual (el usuario presiona [⏳ 2h], se setea a `NOW() + 2h`), y (2) frecuencia automática (el worker envía una alerta y setea a `NOW() + frecuencia_nivel`).

**Alternativas consideradas**:
- *Dos columnas separadas (`proxima_snooze_hasta` + `proxima_alerta_hasta`)*: más explícito pero más complejo. Hay que decidir cuál tiene prioridad.
- *Columna `ultima_alerta_en` y calcular si toca*: más implicit, requiere cálculo en cada iteración.

**Razón**: Dual-use es simple y coherente. Si `proxima_alerta_bloqueada_hasta > NOW()`, el worker salta la tarea — sin importar si el bloqueo vino de snooze manual o de frecuencia automática. Snooze "gana" porque sobreescribe la frecuencia. Un solo mecanismo de "no molestar hasta".

## Risks / Trade-offs

- **[Polling cada 60s consume CPU]** → Trivial para tráfico personal (docenas de tareas, no miles). El query está indexado (`estado='pendiente'` + `fecha_vence IS NOT NULL`). Si el sistema escala a más usuarios, migrar a pg_cron + tabla de alertas pendientes.
- **[Proceso cae = hostigamiento pausado]** → Las alertas se pausan pero las tareas siguen acumulándose (las recurrencias las generan vía pg_cron). Al levantar el proceso, el worker evalúa todas las pendientes y dispara las que correspondan. No hay pérdida, solo retraso.
- **[Falsa sensación de "no olvidé nada"]** → Si el usuario snoozea indefinidamente, una tarea puede quedar vencida sin que Pepe la escale (snooze sobreescribe frecuencia). Mitigado: snooze solo disponible en niveles 1-2; niveles 3-4 no tienen snooze y la frecuencia los alcanza.
- **[Horario activo 09-21 puede perder alertas]** → Si una tarea vence a las 22:00, Pepe no alerta hasta las 09:00 del día siguiente. La tarea ya está vencida nivel 2 en ese momento. Aceptado: el horario respeta el descanso; la alerta llega a primera hora.
- **[Estado `descartado` rompe queries existentes]** → Queries que filtran `estado IN ('pendiente', 'completado')` deben actualizarse para incluir/excluir `descartado` según corresponda. El worker de hostigamiento filtra `estado='pendiente'` (excluye `descartado` por defecto). El comando `/tareas` debe decidir si muestra descartadas (probablemente no, o con flag).
- **[Modo vacaciones no se activa si el proceso está caído]** → Si el usuario manda `/vacaciones` y el proceso está caído, el webhook no responde. Telegram reintentará. Mitigado: servidor always-on (Koyeb).
- **[Zona horaria del horario activo]** → El horario 09-21 se evalúa en la zona del usuario (`zona_horaria_default`). Si el usuario viaja a otra zona, debe actualizar el config. Aceptado para uso personal.

## Migration Plan

No hay datos en producción. La migración es aditiva:

1. **ALTER TABLE `tareas`**: modificar CHECK constraint de `estado` para incluir `'descartado'`:
   ```sql
   ALTER TABLE tareas DROP CONSTRAINT tareas_estado_check;
   ALTER TABLE tareas ADD CONSTRAINT tareas_estado_check
       CHECK (estado IN ('pendiente', 'completado', 'descartado'));
   ```
2. **Seed config**: INSERT en `configuracion_sistema` claves `modo_vacaciones` y `modo_finde` con `valor_booleano=false` y `fecha_liberacion=NULL`.
3. **CREATE FUNCTION `calcular_nivel_hostigamiento(p_fecha_vence DATE, p_now TIMESTAMP) RETURNS INT`** con la lógica de niveles 0-4.
4. **CREATE FUNCTION `frecuencia_nivel(p_nivel INT) RETURNS INTERVAL`** que retorne el intervalo de repetición según el nivel.
5. **Desplegar FastAPI** con el nuevo módulo `hostigamiento/` y la extensión de `asyncio.gather`.

**Rollback**: DROP functions, DROP seed config, restaurar CHECK constraint sin `descartado`. Sin pérdida de datos existentes.

## Open Questions

Todas las open questions de la exploración fueron resueltas:

| Q | Decisión | Sección |
|---|---|---|
| Q1 — Filosofía | Híbrida (vencimiento + inacción) | D1 |
| Q2 — Niveles | 5 niveles (0-4), horario 09-21, estado descartado | D2 |
| Q3 — Motor | Worker while True en mismo proceso | D3 |
| Q4 — Vacaciones: qué personales siguen | Niveles 2+ (vencidas) | D4 |
| Q5 — [Reprogramar] | Postergado a change futura | D5 |

**Open questions restantes (menores, no bloquean implementación)**:
- **Tono de mensajes**: ¿los mensajes de alerta usan informalidad ("Oye, X vence hoy") o formalidad ("Recordatorio: la tarea X vence hoy")? Decision: informal pero respetuoso, consistente con el nombre "Pepe Grillo" del diseño. Emojis incluidos en el nivel del mensaje.
- **`/tareas` muestra descartadas?**: probablemente no por defecto, con flag `/tareas --descartadas` para verlas. Decision: no mostrar descartadas en `/tareas` normal; se ven en DB directo si se necesita auditoría.
- **Snooze [📅 Mañana] setea a qué hora exactamente?**: `TOMORROW 09:00` en zona del usuario (inicio del horario activo). Documentado en D2.