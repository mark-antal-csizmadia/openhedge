---
description:
alwaysApply: true
---

# Project Instructions for Agents

## Project Description

openhedge is an open source experimental tool that helps discover and find relevant hedges using event contracts and prediction markets.

Components:
- `openhedge-core`: a Python library (`src/openhedge_core`), Python 3.12+

For install and how to run the stack, follow [`.agents/skills/how-to-get-started/SKILL.md`](.agents/skills/how-to-get-started/SKILL.md).
To self-host on Railway (GitHub-sourced), follow [`.agents/skills/how-to-deploy-to-railway/SKILL.md`](.agents/skills/how-to-deploy-to-railway/SKILL.md).
To publish the Railway marketplace template, follow [`.agents/skills/how-to-publish-railway-template/SKILL.md`](.agents/skills/how-to-publish-railway-template/SKILL.md).
To add Cloudflare Tunnel on an existing stack, follow [`.agents/skills/how-to-add-cloudflare-tunnel/SKILL.md`](.agents/skills/how-to-add-cloudflare-tunnel/SKILL.md).
To connect MCP and try example hedges, follow [`.agents/skills/try-hedging-examples/SKILL.md`](.agents/skills/try-hedging-examples/SKILL.md).

## Layout

- [`openhedge-core/`](openhedge-core/) — uv project (`pyproject.toml`, `uv.lock`, `src/`)
- [`deploy/caddy/`](deploy/caddy/) — Caddy reverse proxy (Railway public edge; streamable HTTP)
- [`deploy/railway/`](deploy/railway/) — per-service Railway config-as-code for the hosted template (not a root `railway.toml`)
- [`.pre-commit-config.yaml`](.pre-commit-config.yaml) — root hooks for ruff format/check and mypy on `openhedge-core/`

## Package Management with `uv`

Use `uv` exclusively. Never use `pip`, `pip-tools`, or `poetry` for dependency management.

Run commands from the repo root with `--project openhedge-core`:

```bash
# Add or upgrade dependencies
uv add --project openhedge-core <package>

# Remove dependencies
uv remove --project openhedge-core <package>

# Reinstall all dependencies from lock file
uv sync --project openhedge-core

# Run a command with the project environment
uv run --project openhedge-core <command>
```

## Lint, Format, and Types

Ruff (E/F/I, line length 120) and mypy are configured in [`openhedge-core/pyproject.toml`](openhedge-core/pyproject.toml). Prefer matching the pre-commit hooks:

```bash
uv run --project openhedge-core ruff format --config openhedge-core/pyproject.toml
uv run --project openhedge-core ruff check --fix --config openhedge-core/pyproject.toml
uv run --project openhedge-core mypy --config-file openhedge-core/pyproject.toml
```

Run all hooks:

```bash
pre-commit run --all-files
```
