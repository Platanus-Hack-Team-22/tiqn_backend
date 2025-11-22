#!/bin/bash
echo "[ENTRYPOINT] Running Migrations"
uv run alembic upgrade head

echo "[ENTRYPOINT] Running FastAPI"
uv run uvicorn src.main:app --host 0.0.0.0 --port 9000 --timeout 300
