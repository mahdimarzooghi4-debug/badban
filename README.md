# Badban

Badban is implementing the bounded external-lender pilot defined by the accepted Business,
Technical, Product Backlog, and Sprint decisions in `docs/`.

## Current delivery state

```
Business ✓
→ Technical ✓
→ Scrum/Product Backlog ✓
→ Sprint 01 ✓
→ Code + Code Review ✓
→ Sprint 02 ✓
→ Code + Code Review ✓
→ Stage (deferred; environment unavailable)
→ Sprint 03 Proposed
→ QA/Testing
→ Release Approval
→ Production
```

Decision 0021 authorized Sprint 01 foundation code and Decision 0022 closed its Code Review. Decision 0023 defers Stage while the environment is unavailable. Decision 0024 authorized Sprint 02 and Decision 0025 records Sprint 02 Code Review completion. Sprint 03 is Proposed under Decision 0026; Code is not yet authorized.

## Sprint 01 stack

- Python 3.12
- FastAPI / Pydantic v2
- SQLAlchemy 2 async / asyncpg / Alembic
- PostgreSQL 16+
- NATS JetStream
- OpenTelemetry / structured logging
- Docker / Docker Compose
- Pytest / Ruff / Pyright
- GitHub Actions

## Local foundation setup

Start infrastructure:

```bash
docker compose up -d
```

Create a virtual environment and install development dependencies:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Load non-secret local settings:

```bash
set -a
source .env.example
set +a
```

Apply migrations and run checks:

```bash
alembic upgrade head
ruff format --check .
ruff check .
pyright
pytest
```

Run the API:

```bash
uvicorn badban.api.app:app --reload
```

Run the worker:

```bash
python -m badban.worker
```

No production credentials belong in this repository.
