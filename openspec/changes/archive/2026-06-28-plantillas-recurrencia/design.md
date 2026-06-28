## Context

El sistema Jimini tiene implementada la ingesta durable (change `evolucion-buffer-cola-durable-multimedia`) con buffer persistente, protocolo de lease, y transcripción de audio. La tabla `tareas` existe (V4) pero solo recibe tareas de ingesta manual. RF05 (V3) requiere un motor de recurrencias que genere tareas automáticamente desde plantillas, evaluadas diariamente por pg_cron (V4). Ni V3 ni V4 definen la tabla `plantillas_recurrencia` ni cómo el usuario crea plantillas.

Restricciones heredadas:
- **pg_cron** ya está en uso para reclaim de stale locks (cada minuto). Reusar para el job diario de evaluación.
- **Pipeline de IA existente**: webhook → buffer → worker → OpenRouter → INSERT. La creación de plantillas reusa este pipeline con un system prompt distinto y tabla destino distinta.
- **Capas gratuitas**: sin nuevas dependencias externas. Solo Postgres (pg_cron) + OpenRouter + Telegram.
- **Framework Simplicidad + Efectividad** (V3 §3): preferir soluciones simples. El modelado ad-hoc de recurrencias cubre el 90% de casos sin librerías pesadas.
- **Zona horaria**: pg_cron opera en UTC por defecto. El usuario está en Lima (UTC-5, sin DST). La evaluación debe percibir "hoy" en zona del usuario.

Stakeholders: usuario único (Jaime), uso personal, tráfico bajo. Los casos de uso típicos son pagos mensuales, revisiones semanales, y cumpleaños/aniversarios.

## Goals / Non-Goals

**Goals:**
- Definir y crear la tabla `plantillas_recurrencia` que V3/V4 asumían sin especificar.
- Implementar la función SQL de evaluación diaria con zona horaria configurable e idempotencia.
- Habilitar la creación de plantillas vía comando `/recurrencia` reusando el pipeline de IA existente.
- Bifurcar el procesamiento del worker por `tipo_mensaje` para que el mismo pipeline sirva tareas y recurrencias.
- Añadir `valor_texto` a `configuracion_sistema` para desbloquear config de texto (zona horaria ahora, idioma y otros futuros).

**Non-Goals:**
- **No** implementar detección automática de recurrencias (Opción B de la exploración). El comando `/recurrencia` es explícito y determinístico; la detección automática es una change futura si se quiere.
- **No** implementar catch-up de días perdidos. Skip missed universal: si el job no corre un día, las recurrencias de ese día no se generan. Aceptado para uso personal con servidor always-on.
- **No** soportar "Nth weekday of month" (ej: "primer lunes del mes"). El modelo ad-hoc no lo cubre; se resuelve con hand-edit o plantillas alternativas.
- **No** implementar edición de plantillas vía Telegram (solo creación y deshacer). La edición es via DB directo o app web futura.
- **No** implementar pausa temporal de plantillas (soft toggle `activa` existe en schema pero no hay comando de Telegram para togglearlo).
- **No** implementar vista de "próxima ejecución" de cada plantilla. El comando `/recurrencias` lista las activas pero no calcula próximas fechas.

## Decisions

### D1: Modelado ad-hoc con intervalo (vs. cron string, vs. RFC 5545)

**Decisión**: Campos ad-hoc (`tipo_recurrencia` + `intervalo` + `dia_del_mes` + `mes_del_anio` + `dia_de_semana`) con `intervalo` para soportar recurrencias multiperiodo (trimestral, cuatrimestral, semanal quincenal).

**Alternativas consideradas**:
- *Cron string (pg_cron)*: más expresivo pero opaco. El usuario no lo escribe directamente (la IA lo generaría), pero validar cron strings requiere parsing. Además, pg_cron ya opera en UTC, añadiendo complejidad de zona horaria.
- *RFC 5545 (RRULE)*: estándar iCal, máxima expresividad. Pero requiere librería de parsing (python-dateutil o similar) y es overkill para los casos de uso del usuario (pagos mensuales, revisiones semanales).

**Razón**: Ad-hoc cubre los casos de uso identificados (pagos mensuales, semanales, anuales, trimestrales con `intervalo=3`). La IA puede estructurar fácilmente a partir de lenguaje natural porque los campos son semánticamente claros. La validación en SQL es directa (CHECK constraints). El único caso no cubierto ("primer lunes del mes") es raro y se resuelve con dos plantillas o hand-edit.

### D2: Creación vía comando explícito `/recurrencia` + botón [Deshacer] (Opción D)

**Decisión**: El usuario crea plantillas con `/recurrencia <descripción textual>`. La IA estructura la descripción en los campos de la plantilla. Tras insertar, el bot responde con confirmación + botón inline [Deshacer] para cancelar si la IA malinterpretó.

**Alternativas consideradas**:
- *Detección automática por IA (Opción B)*: UX natural pero falsos positivos peligrosos para algo que genera tareas durante meses. Una tarea puntual confundida con recurrencia genera duplicados indefinidamente.
- *Conversacional con confirmación pre-hoc (Opción C)*: máximo control pero requiere estado conversacional en el webhook (recordar "este chat está creando una recurrencia"), que no existe hoy y es un salto arquitectónico.
- *Comando directo sin deshacer (Opción A)*: simple pero sin red de seguridad post-hoc.

**Razón**: El comando explícito garantiza cero falsos positivos. El botón [Deshacer] es un callback handler simple (un solo handler nuevo, no flujo conversacional) que reusa el patrón de botones de V3 RF07. Si la IA se equivoca, el usuario lo ve inmediatamente y deshace con un click. Scope pequeño, máximo control.

### D3: Skip missed universal (vs. catch-up selectivo)

**Decisión**: Si el job de evaluación no corre un día (servidor caído, Supabase indisponible), las recurrencias de ese día no se generan. No hay mecanismo de catch-up.

**Alternativas consideradas**:
- *Catch-up universal*: recorrer desde `ultima_generacion+1` hasta `CURRENT_DATE` generando todo lo que coincide. No pierde tareas pero puede generar muchas de golpe.
- *Catch-up selectivo*: catch-up solo para mensuales/anuales (pagos importantes), skip para semanales/diarias (rutinas ya pasadas). Más justo pero añade complejidad de lógica.

**Razón**: Con servidor always-on (Koyeb), los fallos son excepcionales (redeploys planificados, caídas breves). Para uso personal, perder un día de recurrencia es recuperable manualmente. El catch-up genera ruido (3 revisiones semanales acumuladas el viernes) y complejidad no justificada. Documentado como trade-off aceptado.

### D4: Zona horaria configurable vía `configuracion_sistema.valor_texto`

**Decisión**: La función SQL `evaluar_plantillas_recurrencia()` lee la zona horaria de `configuracion_sistema` (clave `zona_horaria_default`, default `America/Lima`). Opera con `CURRENT_DATE` en esa zona. El job pg_cron se programa a las 05:01 UTC (00:01 Lima).

**Alternativas consideradas**:
- *Hardcodear 'America/Lima' en la función SQL*: simple pero inflexible si el usuario viaja o se muda.
- *Ajustar solo el schedule de pg_cron*: `0 1 5 * * *` (05:01 UTC = 00:01 Lima). Pero la función seguiría evaluando `CURRENT_DATE` en UTC, causando off-by-one en meses de 31 días cerca de medianoche.

**Razón**: La zona horaria debe evaluarse dentro de la función SQL, no solo en el schedule. Añadir `valor_texto` a `configuracion_sistema` es un ALTER TABLE mínimo que desbloquea config de texto para todo el sistema (zona horaria ahora, idioma y otros futuros). El schedule de pg_cron queda en UTC (natural para la extensión) y la función traduce a zona del usuario.

### D5: `dia_del_mes = 0` = último día del mes

**Decisión**: Convención: si `dia_del_mes = 0`, la evaluación usa el último día del mes (28/29 en febrero, 30 en meses cortos, 31 en meses largos). Esto cubre pagos de fin de mes sin quebrar en febrero.

**Alternativas consideradas**:
- *Aceptar skip en meses cortos*: `dia_del_mes = 31` no coincide en febrero → skip. Simple pero pierde pagos de fin de mes, que es el caso más común para día 31.
- *Auto-adjust (dia_del_mes > último día del mes → usar último día)*: peligroso porque dos plantillas (día 28 y día 31→28) colisionarían en febrero.

**Razón**: `dia_del_mes = 0` es semánticamente claro ("fin de mes"), no colisiona con días específicos, y es fácil de implementar en SQL con `DATE_TRUNC('month', fecha) + INTERVAL '1 month - 1 day'`. La IA puede mapear "fin de mes" del lenguaje natural a `dia_del_mes = 0`.

### D6: `tipo_mensaje` como nueva dimensión del buffer

**Decisión**: Añadir `tipo_mensaje VARCHAR(20)` al buffer (`'tarea'` | `'recurrencia'`), ortogonal a `tipo_media` (`texto` | `voz`). El webhook detecta comandos y setea `tipo_mensaje` antes del INSERT. El worker bifurca el system prompt y la tabla destino según `tipo_mensaje`.

**Alternativas consideradas**:
- *Tabla separada para recurrencias (no buffer)*: rompe el patrón de "todo entra por el buffer". Pierde durabilidad, lease protocol, y DLQ para la creación de plantillas.
- *Detección en el worker (no webhook)*: el worker mandaría el texto a IA para clasificar antes de estructurar. Añade un paso de IA, más tokens, más latencia, y el comando `/recurrencia` ya es un indicador explícito que no necesita IA.

**Razón**: `tipo_mensaje` extiende el buffer reusando toda la infraestructura existente (lease, backoff, DLQ, transcripción de audio). La detección en webhook es determinística (`text.startswith("/recurrencia")`), cero latencia extra. La bifurcación en el worker es un `if` sobre `tipo_mensaje`. Es extensible a futuros comandos (`/vacaciones`, `/finde`) sin tocar el protocolo de lease.

## Risks / Trade-offs

- **[Casos raros no cubiertos por ad-hoc]** → "Primer lunes del mes", "SUNAT cron complejo" no son expresables. Mitigación: hand-edit en DB o múltiples plantillas simples. Si los casos raros superan el 20% de uso, migrar a cron string en change futura.
- **[Skip missed pierde recurrencias importantes]** → Si el servidor cae el día 5, "Pagar luz día 5" no se genera. Mitigación: servidor always-on (Koyeb) minimiza el caso. El usuario puede crear la tarea manualmente si nota que faltó. Para pagos críticos, el usuario puede configurar la recurrencia un día antes (`dia_del_mes = 4`) como margen.
- **[IA malinterpreta descripción de recurrencia]** → Mitigado por botón [Deshacer] post-creación (D2). Si la IA estructura mal, el usuario deshace y reintentta. Falso positivo silencioso posible si el usuario no lee la confirmación, pero es el mismo riesgo que la creación de tareas y se mitiga con feedback claro.
- **[Breaking change del buffer]** → `ALTER TABLE buffer_ingesta_contingencia ADD COLUMN tipo_mensaje` con default `'tarea'` es aditivo. Filas existentes (si las hay) quedan como `'tarea'` automáticamente. No hay pérdida de datos.
- **[Zona horaria mal configurada]** → Si `zona_horaria_default` se setea mal, las recurrencias se generan en el día equivocado. Mitigación: default `'America/Lima'` es correcto para el usuario. Cambio requiere INSERT/UPDATE explícito en `configuracion_sistema`.
- **[Crecimiento de `tareas` por recurrencias]** → Cada recurrencia activa genera 1 tarea por período (mensual = 12/año, semanal = 52/año). Para 10 recurrencias activas, ~200 tareas/año. Mitigación: la tabla `tareas` no tiene purge pero el volumen es bajo para uso personal. Purge de tareas completadas es otra change.

## Migration Plan

No hay datos en producción (sistema en diseño previo a implementación). La migración es aditiva:

1. **ALTER TABLE `configuracion_sistema`** ADD COLUMN `valor_texto TEXT` (nullable).
2. **Seed config**: INSERT `zona_horaria_default = 'America/Lima'` en `configuracion_sistema`.
3. **CREATE TABLE `plantillas_recurrencia`** con todas las columnas y CHECK constraints.
4. **ALTER TABLE `buffer_ingesta_contingencia`** ADD COLUMN `tipo_mensaje VARCHAR(20) NOT NULL DEFAULT 'tarea'` + CHECK constraint.
5. **CREATE FUNCTION `evaluar_plantillas_recurrencia()`** con lógica de zona horaria, idempotencia, y generación de tareas.
6. **Programar pg_cron**: `SELECT cron.schedule('evaluar-recurrencias', '1 5 * * *', 'SELECT evaluar_plantillas_recurrencia()')`.
7. **Desplegar FastAPI** con webhook extendido (detección de comandos) y worker extendido (bifurcación por `tipo_mensaje`).

**Rollback**: DROP TABLE `plantillas_recurrencia`, DROP FUNCTION `evaluar_plantillas_recurrencia()`, DROP COLUMN `tipo_mensaje` del buffer, DROP COLUMN `valor_texto` de `configuracion_sistema`, unschedule pg_cron. Sin pérdida de datos existentes (las tablas nuevas están vacías).

## Open Questions

Todas las decisiones de diseño están cerradas. Las open questions de la exploración fueron resueltas:

| Q | Decisión | Sección |
|---|---|---|
| Q1 — Modelado de criterios temporales | Ad-hoc con intervalo | D1 |
| Q2 — Recuperación de fallos | Skip missed universal | D3 |
| Q3 — Zona horaria | Configurable vía `configuracion_sistema.valor_texto` | D4 |
| Q4 — Caso "día 31" en febrero | `dia_del_mes = 0` = último día | D5 |
| Q5 — Creación de plantillas | Comando `/recurrencia` + botón [Deshacer] | D2 |

**Open questions restantes (menores, no bloquean implementación)**:
- **Vista de "próxima ejecución"**: el comando `/recurrencias` lista las activas pero no calcula cuándo es la próxima. ¿Valdría la pena añadirlo? Decisión: no en esta change, es cosmético y se puede añadir después.
- **Comando para pausar/activar plantillas**: `activa` existe en el schema pero no hay comando de Telegram para togglearlo. ¿`/recurrencia pause <id>` y `/recurrencia resume <id>`? Decisión: no en esta change, hand-edit en DB para v1.
