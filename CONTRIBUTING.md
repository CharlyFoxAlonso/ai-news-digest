# Contribuir

## Preparación

Instala Python 3.12 y uv, ejecuta `uv sync --frozen` y copia `.env.example` a
`.env` sólo si necesitas una prueba manual. La suite normal no necesita secretos.

## Ramas y commits

Crea ramas cortas desde `main`, por ejemplo `feat/feed-health`. Usa commits
pequeños en estilo Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`).
No reescribas ramas compartidas ni hagas force-push sobre `digest-state`.

## Estilo y pruebas

Antes de abrir un pull request:

```bash
uv run ruff check .
uv run mypy src
uv run pytest --cov=ai_news --cov-report=term-missing --cov-fail-under=70
```

Añade type hints y pruebas para cualquier regla. Usa fixtures locales y mocks;
no agregues llamadas reales de red a pytest.

## Pull requests

Describe problema, solución, riesgos y validación. Mantén el alcance acotado,
actualiza documentación cuando cambie comportamiento y completa el checklist.
Los cambios de fuentes deben incluir evidencia reciente de preflight.
