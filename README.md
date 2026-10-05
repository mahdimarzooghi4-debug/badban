# Badban

Badban is implementing the bounded external-lender pilot defined by the accepted Business,
Technical, Product Backlog, and Sprint decisions in `docs/`.

## Current delivery state

```
Business ✓
→ Technical ✓
→ Scrum/Product Backlog ✓
→ Sprint 01 ✓
→ Code (foundation scope only)
→ Code Review
→ Stage
→ QA/Testing
→ Release Approval
→ Production
```

Decision 0021 authorizes code only for Sprint 01 BL-001 through BL-005.

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
