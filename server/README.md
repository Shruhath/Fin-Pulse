# FinPulse server

Python 3.11 package `finpulse`: ingestion, parsing, the NLP pipeline stages, the job queue
worker and the FastAPI service the `web/` app reads.

```bash
docker compose -f ../infra/docker-compose.yml up -d db   # PostgreSQL 16 + pgvector on :5433
uv sync                                                  # creates .venv from uv.lock
uv run alembic upgrade head                              # schema
uv run finpulse ingest corpus                            # layer 2 documents -> database
uv run uvicorn finpulse.api.app:app --reload             # http://127.0.0.1:8000/docs
uv run pytest                                            # tests (the `db` ones need the container)
uv run ruff check . && uv run ruff format --check .
```

Settings come from `FINPULSE_*` environment variables or `server/.env` (see `.env.example`).

The OpenAPI document at `/openapi.json` is the API contract. The Pydantic response models in
`finpulse.api.schemas` are the single source of truth for what `web/` consumes.

Rules that the code enforces:

- Spans are `[start, end)` character offsets into `documents.clean_text`.
- Gold and silver labels are stored and exported separately.
- No figure is served unless it was computed from stored data; an empty corpus returns empty
  lists, never placeholder values.
