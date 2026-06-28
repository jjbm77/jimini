## ADDED Requirements

### Requirement: Tests unitarios funcionales con pytest

El proyecto SHALL tener tests unitarios funcionales que cubran la lógica de negocio testeable. Los tests SHALL ejecutarse con `pytest` sin conexión a servicios externos (Supabase, Telegram, Groq, OpenRouter). Todo acceso a base de datos SHALL ser mockeado.

#### Scenario: Todos los tests pasan en local
- **WHEN** se ejecuta `pytest -v` en el directorio raíz del proyecto
- **THEN** todos los tests pasan sin errores ni failures
- **AND** ningún test requiere variables de entorno reales
- **AND** ningún test se conecta a Supabase, Telegram, Groq, ni OpenRouter

#### Scenario: Tests cubren lógica de negocio
- **WHEN** se revisan los archivos de test
- **THEN** existe cobertura para: cálculo de nivel de hostigamiento, frecuencia por nivel, debe_alertar, detección de comandos en webhook, emojis por ámbito, formato de calendario mensual, expiración de signed URLs, y errores de transcripción

### Requirement: CI pipeline en GitHub Actions

El proyecto SHALL tener un workflow de GitHub Actions (`.github/workflows/ci.yml`) que ejecute linting y tests automáticamente en cada push y pull request a la rama `master`.

#### Scenario: CI en push a master
- **WHEN** se hace push a `master`
- **THEN** GitHub Actions ejecuta `ruff check` seguido de `pytest`
- **AND** si ruff reporta errores, el job falla
- **AND** si pytest reporta failures, el job falla

#### Scenario: CI en pull request
- **WHEN** se abre un pull request hacia `master`
- **THEN** GitHub Actions ejecuta el mismo pipeline (ruff + pytest)

### Requirement: Linting con ruff

El proyecto SHALL usar `ruff` como linter con reglas mínimas (E, F, I, N, UP) para detectar errores de sintaxis, imports no usados, y convenciones de estilo. `ruff` SHALL estar configurado en `pyproject.toml`.

#### Scenario: ruff no reporta errores
- **WHEN** se ejecuta `ruff check .`
- **THEN** no hay errores de linting en el código fuente (`src/`)
- **AND** los directorios `migrations/` y `openspec/` están excluidos del linting

### Requirement: Dependencias de desarrollo

El proyecto SHALL incluir `pytest`, `pytest-asyncio`, `pytest-mock`, y `ruff` como dependencias de desarrollo en `pyproject.toml` bajo `[project.optional-dependencies] dev`.

#### Scenario: Instalación de dependencias dev
- **WHEN** se ejecuta `pip install -e ".[dev]"`
- **THEN** pytest, pytest-asyncio, pytest-mock, y ruff están disponibles en el entorno virtual