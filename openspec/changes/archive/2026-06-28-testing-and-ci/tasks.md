## 1. Configuración de linting y dependencias

- [x] 1.1 Añadir `ruff` a dependencias dev en `pyproject.toml`
- [x] 1.2 Añadir configuración `[tool.ruff]` en `pyproject.toml` (target-version = "py312", select = ["E","F","I","N","UP"], exclude = ["migrations/","openspec/"])
- [x] 1.3 Añadir `[tool.pytest.ini_options]` con `asyncio_mode = "auto"` en `pyproject.toml`
- [x] 1.4 Ejecutar `ruff check .` y arreglar todos los errores reportados

## 2. Rewrite de tests — core y comandos

- [x] 2.1 Revisar y corregir `tests/test_hostigamiento_core.py`: asegurar que tests de `calcular_nivel` (vía RPC mock), `frecuencia_nivel`, `debe_alertar`, `dentro_horario_activo`, `auto_limpiar_modos` usen mocks correctos y pasen
- [x] 2.2 Revisar y corregir `tests/test_hostigamiento_comandos.py`: asegurar que handlers de `/vacaciones`, `/finde`, `/tareas`, `/hoy`, `/semana`, `/mes` tengan `@pytest.mark.asyncio` o usen auto mode, y que `get_db` esté mockeado donde sea necesario
- [x] 2.3 Revisar y corregir `tests/test_lease.py`: verificar que mocks de `get_db` y `rpc` funcionen correctamente
- [x] 2.4 Revisar y corregir `tests/test_dlq.py`: añadir `@pytest.mark.asyncio`/auto mode + tipo_mensaje en fixtures
- [x] 2.5 Revisar y corregir `tests/test_groq_provider.py`: mockear `settings` a nivel de fixture, añadir async await
- [x] 2.6 Revisar y corregir `tests/test_vista_linea_tiempo.py`: mockear `_get_date_in_tz` si es necesario
- [x] 2.7 Revisar y corregir `tests/test_recurrencia_worker.py`: añadir `@pytest.mark.asyncio`/auto mode
- [x] 2.8 Revisar y corregir `tests/test_recurrencia_webhook.py`: arreglar import de `MagicMock`, añadir mock de DB
- [x] 2.9 Revisar y corregir `tests/test_recurrencia_callbacks.py`: verificar que `@pytest.mark.asyncio` esté presente

## 3. Verificación de tests

- [x] 3.1 Ejecutar `pytest -v` y verificar que todos los tests pasan
- [x] 3.2 Si algún test falla, arreglar el código de test (no el source code — ya fue arreglado en commit previo)

## 4. GitHub Actions CI workflow

- [x] 4.1 Crear `.github/workflows/ci.yml` con trigger `on: [push, pull_request]`, branches: master
- [x] 4.2 Job `test`: ubuntu-latest, Python 3.12, steps: checkout, setup-python, install deps, ruff check, pytest
- [x] 4.3 Verificar que el workflow se dispara en el próximo push

## 5. Documentación

- [x] 5.1 Actualizar README con instrucciones de testing (`pip install -e ".[dev]" && pytest`)
- [x] 5.2 Documentar el CI workflow en README