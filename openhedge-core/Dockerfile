FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.8.4 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY README.md openhedge-core/pyproject.toml openhedge-core/uv.lock ./
COPY openhedge-core/src ./src
COPY openhedge-core/scripts/sync-loop.sh /app/sync-loop.sh

RUN chmod +x /app/sync-loop.sh \
    && uv sync --frozen --no-dev

CMD ["python", "-m", "openhedge_core.sync_markets"]
