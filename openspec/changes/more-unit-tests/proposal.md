## Why

El auditorio de cobertura del proyecto reveló que 26 de ~55 funciones carecen de tests, incluyendo 9 funciones de lógica pura sin ninguna dependencia externa. En particular, 4 funciones críticas para el pipeline del sistema (procesamiento de audio, generación de teclados de botones, expiración de URLs, y generación del grid de calendario) están completamente sin testear a pesar de ser lógica determinística y fácilmente testeable.

## What Changes

- **Tests para `signed_url_is_expired()`**: 4 escenarios (sin parámetro expires, expirada, vigente, error de parsing) en un nuevo archivo `test_storage.py`.
- **Tests para `_build_keyboard()`**: 6 escenarios (niveles 0 a 4 + default) verificando la estructura exacta de `inline_keyboard` retornada.
- **Tests para `_month_grid()`**: 3 escenarios (mes con 31 días, mes con 28 días, mes con tareas en algunas celdas) verificando el formato ASCII + emojis de salida.
- **Tests para `_get_text_for_ia()`**: pipeline de procesamiento de voz (transcripción, renovación de signed URL expirada, detección automática de comando `/recurrencia`).
- **Tests para `worker_loop_hostigamiento()`**: lógica de decisión de alertas (cambio de nivel, repetición, bloqueo por modo vacaciones/horario).

## Capabilities

### New Capabilities
- `more-unit-tests`: Ampliación de cobertura de tests unitarios para cubrir las 5 funciones con mayor brecha de cobertura según el audit. No modifica código de producción, solo añade tests.

## Impact

- Añade tests sin modificar código fuente. Sin migraciones, sin cambios de schema, sin nuevas dependencias.