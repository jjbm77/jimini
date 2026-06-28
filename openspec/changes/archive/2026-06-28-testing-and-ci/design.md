## Context

El proyecto tiene 14 módulos Python y 8 archivos de test. Los tests usan `pytest` + `pytest-mock` + `pytest-asyncio`, pero nunca fueron ejecutados. El diagnosis reveló: 3 bugs en source code (ya arreglados en commit `67f8da4`), 8+ bugs en tests (async sin await, imports faltantes, fixtures sin campos requeridos), y ningún CI configurado.

Restricciones:
- **Capas gratuitas**: GitHub Actions tiene 2000 min/mes gratis para repos públicos (ilimitado para este proyecto).
- **Sin DB en CI**: los tests no pueden conectarse a Supabase real. Todo lo que toca `get_db()` se mockea.
- **Linter mínimo**: `ruff` reemplaza flake8 + isort + black. Una sola herramienta, configuración mínima.
- **Python 3.12+**: ya especificado en `pyproject.toml`.

Stakeholders: desarrollador único (Jaime). El CI debe ser rápido (<2 min) y confiable (cero falsos positivos).

## Goals / Non-Goals

**Goals:**
- Que todos los tests existentes pasen en local (`pytest`) y en CI.
- Que `ruff check` no reporte errores.
- Que el CI se dispare automáticamente en `push` y `pull_request` a `master`.
- Cobertura de lógica de negocio: cálculo de niveles, frecuencias, detección de comandos, emojis, protocolo de lease, errores de transcripción.

**Non-Goals:**
- No alcanzar 80%+ de coverage. El objetivo es "toda la lógica testeable tiene tests", no un número.
- No tests de integración con Supabase real, Telegram real, Groq real, ni OpenRouter real.
- No tests de `main.py` (FastAPI app) — requiere servidor real.
- No migrar a otro test framework. `pytest` es el estándar.

## Decisions

### D1: Mantener solo tests que testean lógica, eliminar mocks profundos

**Decisión**: Los tests que mockean cadenas de `db.table().select().eq().not_.is_().order().execute()` se reemplazan por tests de funciones puras o se simplifican para mockear solo la capa de RPC.

**Alternativas consideradas**:
- *Arreglar los mocks existentes*: cada cambio en el código fuente requeriría actualizar cadenas de mock. Frágil.
- *Usar factory fixtures reutilizables*: más mantenible pero overkill para docenas de tests.

**Razón**: Mockear una cadena de 7 llamadas es frágil y no testea lógica de negocio — solo testea que escribiste bien el mock. Las funciones puras (`calcular_nivel`, `frecuencia_nivel`, `_build_emoji_for_tarea`, `_month_grid`) no requieren mocks.

### D2: `pytest-asyncio` en modo auto

**Decisión**: Configurar `pytest-asyncio` con `asyncio_mode = auto` en `pyproject.toml`. Esto evita tener que decorar cada test con `@pytest.mark.asyncio` y detecta automáticamente funciones `async def`.

**Razón**: Elimina la fuente más común de bugs en los tests actuales (falta de `@pytest.mark.asyncio`). Menos boilerplate, menos errores.

### D3: `ruff` como única herramienta de linting

**Decisión**: Usar `ruff` con configuración mínima: target-version py312, reglas `E`, `F`, `I`, `N`, `UP`.

**Alternativas consideradas**:
- *flake8 + isort + black*: tres herramientas, tres configuraciones, más lento.
- *ruff + mypy*: mypy añade valor pero requiere type annotations exhaustivas que el proyecto no tiene. Se posterga.

**Razón**: `ruff` es 10-100x más rápido, reemplaza las tres herramientas, y la configuración es mínima. Suficiente para un proyecto personal.

### D4: CI en GitHub Actions con matrix de Python 3.12

**Decisión**: Workflow `.github/workflows/ci.yml` que corre en `ubuntu-latest` con Python 3.12. Pasos: checkout, setup python, install deps, ruff check, pytest.

**Razón**: GitHub Actions es gratuito para repos públicos. El workflow es simple (sin matrix de versiones múltiples — solo 3.12). Ruff corre primero (más rápido, falla temprano), luego pytest.

### D5: Tests agrupados por dominio funcional

**Decisión**: Los tests se reorganizan en 7 archivos por dominio:

| Archivo | Qué testea |
|---|---|
| `test_hostigamiento_core.py` | `calcular_nivel`, `frecuencia_nivel`, `debe_alertar`, `auto_limpiar_modos`, `dentro_horario_activo` |
| `test_hostigamiento_comandos.py` | `/vacaciones`, `/finde`, `/tareas` handlers, `/hoy`, `/semana`, `/mes` handlers |
| `test_webhook_handler.py` | `_handle_text` (detección de comandos), `_handle_callback` routing |
| `test_dlq.py` | `notify_dlq_telegram` para texto y voz |
| `test_lease.py` | `claim_next_message`, `mark_completed`, `mark_failed`, `get_idioma_config` |
| `test_transcription.py` | `GroqTranscriptionProvider` errores, `RateLimitError`, `TranscriptionError` |
| `test_storage.py` | `signed_url_is_expired`, `_month_grid`, `_build_emoji_for_tarea`, `_get_date_in_tz` |

## Risks / Trade-offs

- **[Tests que mockean DB pueden romperse si cambia el schema]** → Bajo riesgo: el schema es estable (migraciones ya definidas). Si cambia, los tests se actualizan junto con el código.
- **[Ruff puede reportar errores en código legacy]** → Se configura `ruff` con reglas mínimas y se excluye `migrations/` y `openspec/`. Los warnings se arreglan como parte de la change.
- **[pytest-asyncio auto mode puede causar problemas con tests sync que usan event loop]** → Probado: funciona bien para tests sync puros. Solo afecta funciones `async def`.

## Migration Plan

Sin migración de datos. Los cambios son:

1. **Instalar dependencias dev**: `pip install -e ".[dev]"`.
2. **Reemplazar archivos de test** con versiones corregidas.
3. **Crear `.github/workflows/ci.yml`**.
4. **Ejecutar `ruff check .` y `pytest`** para verificar.
5. **Commit y push** — el CI se dispara automáticamente.

**Rollback**: revertir commit. Sin data loss.

## Open Questions

- **¿Coverage target?** No en v1. Se puede añadir `--cov` con threshold después de tener una línea base.
- **¿mypy?** No en v1. El proyecto no tiene type annotations exhaustivas. Añadir mypy requiere un esfuerzo separado.
- **¿Tests de integración?** Postergados. Cuando el proyecto esté deployado en Koyeb con Supabase real, se pueden añadir tests smoke.