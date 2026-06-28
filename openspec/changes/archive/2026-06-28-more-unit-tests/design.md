## Decisions

### D1: Un solo archivo de test por módulo (patrón existente)

Seguir el naming del proyecto: `test_<modulo>.py`. Los tests nuevos se ubican en tests/ existentes o se crean archivos nuevos donde corresponda:
- `test_storage.py` → `signed_url_is_expired`
- `test_hostigamiento_worker.py` → `_build_keyboard`, `worker_loop_hostigamiento`
- `test_vista_linea_tiempo.py` → `_month_grid` (archivo existente)
- `test_buffer_worker.py` → `_get_text_for_ia` (archivo nuevo)

### D2: Tablas de casos para funciones puras

`_build_keyboard` y `signed_url_is_expired` se testean con `@pytest.mark.parametrize` para cubrir todas las ramas en pocas líneas de test.

### D3: Mocks mínimos para I/O

`_get_text_for_ia` y `worker_loop_hostigamiento` requieren mockear `get_db()`, `get_provider()`, y Telegram API. Se reusa el patrón de mocks existentes en el proyecto.