FROM ghcr.io/astral-sh/uv:python3.13-bookworm

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv pip install --system --requirement pyproject.toml

COPY . .

ENTRYPOINT ["./entrypoint.sh"]
