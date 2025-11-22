#!/bin/bash

echo "[ENTRYPOINT] Running FastAPI"
uv run uvicorn src.main:app --host 0.0.0.0 --port 9000
