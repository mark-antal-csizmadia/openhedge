---
name: how-to-deploy-to-railway-using-railway-cli
description: >-
  Deploys openhedge to Railway with the Railway CLI (Qdrant template, api,
  sync cron, public MCP). Use when the user asks to deploy to Railway, run
  railway up, publish a Railway template, or set Railway service variables.
---

# How to deploy to Railway using Railway CLI

Stand up the hosted stack from the **repo root**. Do not invent `OPENROUTER_API_KEY`. Do not commit a root `railway.toml` (copy per service, then delete). Never use `pip`. Ask the user for the OpenRouter key if it is missing.

Local Compose is a different path — [how-to-get-started](../how-to-get-started/SKILL.md).

## Workflow

```
- [ ] railway login; project linked
- [ ] Qdrant template (private)
- [ ] api (PORT=8000, Qdrant vars, railway up)
- [ ] sync (same Qdrant vars, railway up, manual redeploy for first ingest)
- [ ] mcp (OPENHEDGE_API_URL with :8000, railway up, public domain)
- [ ] smoke /health and /mcp
```

**Order:** `Qdrant` → `api` and `sync` → `mcp`.

The Qdrant marketplace template names the service **`Qdrant`**. Reference variables must use that name. App code only reads `API_PORT` / `MCP_PORT`; [`deploy/railway/api.toml`](../../../deploy/railway/api.toml) and [`mcp.toml`](../../../deploy/railway/mcp.toml) copy Railway `$PORT` onto those env vars in the start command. Do **not** set `API_PORT`, `MCP_PORT`, `API_HOST`, or `MCP_HOST` as Railway variables.

`${{api.PORT}}` is **not** shared across services. Pin `PORT=8000` on `api` and put `:8000` in `OPENHEDGE_API_URL`.

Config-as-code lives in [`deploy/railway/`](../../../deploy/railway/). `railway up` reads **root** `railway.toml`, so copy the matching file before each `up`.

## Prerequisites

- [Railway CLI](https://docs.railway.com/cli)
- OpenRouter API key (`OPENROUTER_API_KEY`) on **api** and **sync**

```bash
export OPENROUTER_API_KEY='sk-or-...'   # from the user; never invent

railway login
railway init --name openhedge    # or: railway link
```

## 1. Qdrant

```bash
railway deploy --template i1tz3T

railway variable set \
  QDRANT__SERVICE__HTTP_PORT=6333 \
  QDRANT__STORAGE__STORAGE_PATH=/qdrant/storage \
  --service Qdrant --skip-deploys
```

Wait until `Qdrant` is running before `api` / `sync` (pre-deploy `setup_qdrant` needs it).

## 2. api

```bash
railway add --service api

railway variable set \
  'QDRANT_URL=http://${{Qdrant.RAILWAY_PRIVATE_DOMAIN}}:6333' \
  'QDRANT_API_KEY=${{Qdrant.QDRANT__SERVICE__API_KEY}}' \
  "OPENROUTER_API_KEY=${OPENROUTER_API_KEY}" \
  PORT=8000 \
  --service api --skip-deploys


cp deploy/railway/api.toml railway.toml
railway up . --service api --path-as-root
rm railway.toml
```

If healthcheck says “service unavailable”, `PORT` is not `8000` or the app is not using the copied `api.toml` start command.

## 3. sync

Hourly cron (`0 * * * *`), `restartPolicyType = NEVER`. No HTTP port.

```bash
railway add --service sync

railway variable set \
  'QDRANT_URL=http://${{Qdrant.RAILWAY_PRIVATE_DOMAIN}}:6333' \
  'QDRANT_API_KEY=${{Qdrant.QDRANT__SERVICE__API_KEY}}' \
  "OPENROUTER_API_KEY=${OPENROUTER_API_KEY}" \
  --service sync --skip-deploys

cp deploy/railway/sync.toml railway.toml
railway up . --service sync --path-as-root
rm railway.toml

railway service redeploy --service sync --yes
```

The first cron tick may wait until `:00`; the redeploy runs ingest now. Search stays empty until that pass finishes.

## 4. mcp

```bash
railway add --service mcp

railway variable set \
  'OPENHEDGE_API_URL=http://${{api.RAILWAY_PRIVATE_DOMAIN}}:8000' \
  --service mcp --skip-deploys


cp deploy/railway/mcp.toml railway.toml
railway up . --service mcp --path-as-root
rm railway.toml

railway domain --service mcp
```

Use **literal** `:8000` in `OPENHEDGE_API_URL` (same as pinned `api` `PORT`). zsh: keep `${{...}}` in single quotes.

Only `mcp` gets a public domain. Point the client at `https://<mcp-domain>/mcp`.

```json
{
  "mcpServers": {
    "openhedge": {
      "url": "https://<mcp-domain>/mcp"
    }
  }
}
```

## Verify

```bash
curl -sS "https://<mcp-domain>/health"
curl -sS "https://<mcp-domain>/ready"
```

Confirm `sync` logs a successful `sync_markets` pass. `api` `/health` and `/ready` are private (no public domain).

## Publish template (optional, after a working project)

1. Project settings → **Generate Template from Project**.
2. Mark `OPENROUTER_API_KEY` required (api + sync). Only `mcp` public.
3. Publish; put the template code in the README Deploy button (`<TEMPLATE_CODE>`).

## Pitfalls

- Copy `deploy/railway/<service>.toml` → `railway.toml` **immediately before** that service’s `railway up`; `rm` it after. Never leave or commit root `railway.toml`.
- Do not set `API_PORT` / `MCP_PORT` / `API_HOST` / `MCP_HOST` on Railway.
- Do not use `${{api.PORT}}` in MCP vars.
- Reference `Qdrant` (template name), not `qdrant`.
- `OPENROUTER_API_KEY` on api and sync only. MCP talks only to the API.
- Cron `sync` does not stay running; use `railway service redeploy --service sync --yes` for a first fill.
- Use `uv` for repo work; Railway builds from [`openhedge-core/Dockerfile`](../../../openhedge-core/Dockerfile).
