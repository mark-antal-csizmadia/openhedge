---
name: how-to-get-started
description: >-
  Installs and runs openhedge for a new user. Use when the user is new to the
  repo, asks how to get started, install, set up, or run the API/MCP, or when
  an agent needs the stack up before using search, hedges, or MCP tools.
---

# How to get started

Get the user running quickly. Prefer Docker Compose for local use; if they want a hosted stack, point them at the Railway template in [README.md](../../../README.md). Use uv for local dev and tests. Never use pip, pip-tools, or poetry. Never commit `.env`.

## Hosted (Railway)

If the user wants to deploy rather than run locally, use the **Deploy on Railway** button in [README.md](../../../README.md). They need an OpenRouter API key. After deploy, MCP is at `https://<mcp-domain>/mcp`. Railway sync is hourly cron, so the first ingest may wait until the next hour unless they manually deploy `sync`. Do not invent a template URL; if `<TEMPLATE_CODE>` is still a placeholder, use Docker Compose instead.

## Workflow

Copy this checklist and tick items as you go (skip Docker items if using Railway):

```
- [ ] Prerequisites present (Python 3.12+, uv, Docker)
- [ ] Dev deps synced (`uv sync --project openhedge-core`)
- [ ] `.env` created from `.env.example` with OPENROUTER_API_KEY
- [ ] Stack up (`docker compose up`) unless the user only wants tests
- [ ] Health checks pass
```

Install only what is missing. Run commands from the repo root.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker (full stack)
- OpenRouter API key (`OPENROUTER_API_KEY`) for market sync and `/v1/search`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install pre-commit
```

## Dev install

```bash
uv sync --project openhedge-core
pre-commit install
cp .env.example .env
```

Ask the user to fill `OPENROUTER_API_KEY` in `.env`. Do not invent or commit the key.

## Run the product (default)

After `.env` is filled:

```bash
docker compose up
```

Compose injects env into services. Local Qdrant needs no API key. It starts Qdrant, `setup_qdrant`, looping `sync_markets`, the API (`python -m openhedge_core.server`), and MCP (`python -m openhedge_core.mcp_server`).

| Service | URL |
| --- | --- |
| REST API | `http://localhost:8000/v1` |
| API health | `http://localhost:8000/health` |
| API ready | `http://localhost:8000/ready` |
| MCP (Streamable HTTP) | `http://localhost:8001/mcp` |
| MCP ready | `http://localhost:8001/ready` |

MCP client config:

```json
{
  "mcpServers": {
    "openhedge": {
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

## Verify

```bash
curl -sS http://localhost:8000/health
curl -sS http://localhost:8000/ready
curl -sS http://localhost:8001/ready
```

Tests (no Docker):

```bash
uv run --project openhedge-core pytest
```

Lint/types: see [AGENTS.md](../../../AGENTS.md).

## Local modules without Compose

Only when the user is developing a single service. Qdrant must already be on `http://localhost:6333`. Settings do **not** load `.env`; Compose does. Export env first:

```bash
set -a && source .env && set +a
```

Then, in order:

```bash
uv run --project openhedge-core python -m openhedge_core.setup_qdrant
uv run --project openhedge-core python -m openhedge_core.sync_markets
uv run --project openhedge-core python -m openhedge_core.server
uv run --project openhedge-core python -m openhedge_core.mcp_server
```

`OPENROUTER_API_KEY` is required for `sync_markets`. Without it, `/v1/search` returns 503.

## Pitfalls

- Use `uv` exclusively; always `--project openhedge-core` from the repo root.
- Do not commit `.env` (gitignored). `.env.example` is the template.
- Docker Compose reads `.env`; local `python -m` does not unless the shell has the vars exported.
