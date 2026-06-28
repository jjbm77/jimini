## Why

Los tests del proyecto fueron escritos en paralelo con la implementación pero nunca ejecutados. El 90% de los archivos de test tienen bugs: async sin await, mocks rotos, fixtures faltantes, y un source file con código corrupto que impedía importar módulos. Además, el proyecto no tiene CI automatizado: cada commit debe verificarse con tests + lint. Esto es especialmente crítico para un sistema de gestión personal — bugs en producción significan tareas perdidas o alertas no enviadas.

## What Changes

- **Rewrite de tests** enfocados en unidades testeables (lógica de negocio, funciones puras, cálculo de niveles y fechas). Se mantienen tests que mockean DB/APIs donde es necesario, pero con mocks corregidos y sintaxis async correcta.
- **Eliminación de tests rotos** que mockean cadenas largas de `supabase-py` sin valor de cobertura real. Se reemplazan por tests de funciones puras.
- **`@pytest.mark.asyncio`** añadido a todos los tests que testean funciones async.
- **GitHub Actions CI workflow** (`.github/workflows/ci.yml`): ejecuta `pytest` + `ruff` en cada push y pull request a `master`.
- **Configuración de `ruff`** como linter (reemplaza flake8/isort/black, single tool).
- **Dependencias dev** añadidas a `pyproject.toml`: `ruff`, `pytest-asyncio`, `pytest-cov`.

## Capabilities

### New Capabilities
- `testing-and-ci`: Suite de tests unitarios funcionales (pytest) cubriendo lógica de negocio testeable + pipeline CI en GitHub Actions con lint + tests automáticos en cada commit.

### Modified Capabilities
*(Ninguna — esta change no modifica specs funcionales, solo añade testing infraestructura.)*

## Impact

- **tests/**: 8 archivos de test actualmente con bugs → ~7 archivos reescritos con tests funcionales y sintaxis correcta.
- **`.github/workflows/ci.yml`**: nuevo workflow de CI.
- **`pyproject.toml`**: dependencias dev añadidas (`ruff`, `pytest-asyncio`, `pytest-cov`), configuración de `ruff`.
- **`src/jimini/`**: sin cambios funcionales (los bugs de source ya se arreglaron en commit previo).