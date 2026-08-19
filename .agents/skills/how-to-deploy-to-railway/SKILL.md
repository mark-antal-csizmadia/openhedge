---
name: how-to-deploy-to-railway
description: >-
  Deploys the GitHub-sourced Railway stack (Qdrant Docker image, api, sync
  cron, private MCP, public Caddy). Use when the user wants to self-host on
  Railway, fork and deploy, or stand up services with source connect — not to
  publish a marketplace template or add Cloudflare.
---

# How to deploy to Railway

GitHub-sourced hosted stack from this repo or a fork. Do not invent `OPENROUTER_API_KEY`. Never commit a root `railway.toml`. Never use `pip`. Ask the user for the OpenRouter key if it is missing. Do not `railway up` (local upload cannot be templated later).

Local Compose is [how-to-get-started](../how-to-get-started/SKILL.md). To publish a marketplace template from this project, follow [how-to-publish-railway-template](../how-to-publish-railway-template/SKILL.md) after Verify. For a custom domain, WAF, and rate limits, follow [how-to-add-cloudflare-tunnel](../how-to-add-cloudflare-tunnel/SKILL.md) after the stack is up. Do not add `cloudflared` here — a project used for Generate Template must stay template-safe.

## Workflow

```
- [ ] railway login; GitHub connected; project linked
- [ ] Qdrant image + volume (private, no API key)
- [ ] api, then sync, then mcp, then caddy (config file → vars → GitHub)
- [ ] public domain only on caddy; smoke /health
- [ ] sync Run now; logs show open batch created=
```

**Order:** `Qdrant` → `api` and `sync` → `mcp` → `caddy`. Create app services **one at a time** (a tight `railway add` loop can return an empty body).

Name the vector service **`Qdrant`**. Pin `PORT=8000` on `api`, `PORT=8001` on `mcp`, `PORT=8080` on `caddy`. Cross-service URLs cannot read `${{api.PORT}}`; put those literal ports in `OPENHEDGE_API_URL` and `UPSTREAM_URL`. `UPSTREAM_URL` is **host:port only** (no `http://`). Do **not** set `API_PORT`, `MCP_PORT`, `API_HOST`, `MCP_HOST`, `QDRANT_API_KEY`, `QDRANT__SERVICE__API_KEY`, `QDRANT__SERVICE__HTTP_PORT`, or `QDRANT__STORAGE__STORAGE_PATH`. zsh: keep `${{...}}` in single quotes.

No root `railway.toml`. Per-service config is [`deploy/railway/`](../../../deploy/railway/). Set `railwayConfigFile` **before** `source connect`.

Qdrant has **no API key** (same as local Compose). Keep it private. Empty `QDRANT_API_KEY` is ignored by the app; omit the var entirely. Do **not** set `QDRANT__SERVICE__HTTP_PORT` or `QDRANT__STORAGE__STORAGE_PATH` — the image already uses HTTP 6333 and `/qdrant/storage`. Generate Template blanks those literals into empty required fields.

## Prerequisites

- [Railway CLI](https://docs.railway.com/cli)
- GitHub connected in Railway with access to this repo or the user’s fork
- OpenRouter API key on **api** and **sync** only

```bash
export OPENROUTER_API_KEY='sk-or-...'   # from the user; never invent
export REPO="$(git remote get-url origin | sed -E 's#.*github.com[:/](.+)(\.git)?#\1#' | sed 's/\.git$//')"

railway login
railway init --name openhedge    # or: railway link
```

Confirm `REPO` is `owner/openhedge` with no `.git` (upstream or a fork such as `their-user/openhedge`). Railway must have GitHub access to that repo. `source connect` uses branch `main`.

## Helpers

Scripts live next to this skill. Run them from the **repo root**. `railwayConfigFile` is not a CLI flag.

```bash
python3 .agents/skills/how-to-deploy-to-railway/scripts/set_railway_config_file.py api /deploy/railway/api.toml
```

If `railway add --service <name>` returns `error decoding response body`, wait and retry once. Fallback:

```bash
python3 .agents/skills/how-to-deploy-to-railway/scripts/create_empty_service.py caddy
```

## 1. Qdrant

Image source (not `railway deploy --template i1tz3T`). No API key. No public domain.

```bash
railway add --image qdrant/qdrant:v1.19.0 --service Qdrant --json

railway service Qdrant
railway volume add --mount-path /qdrant/storage --json
```

`--service` is **not** valid after `volume add`. Link `Qdrant` first, then `add`. Do not use `railway volume --service Qdrant add` (CLI panic if the service is not already linked).

Wait until `Qdrant` is running before `api` / `sync` (pre-deploy `setup_qdrant` needs it).

## 2. api

```bash
railway add --service api --json
python3 .agents/skills/how-to-deploy-to-railway/scripts/set_railway_config_file.py api /deploy/railway/api.toml

railway variable set \
  'QDRANT_URL=http://${{Qdrant.RAILWAY_PRIVATE_DOMAIN}}:6333' \
  "OPENROUTER_API_KEY=${OPENROUTER_API_KEY}" \
  PORT=8000 \
  --service api --skip-deploys

railway service source connect --repo "$REPO" --branch main --service api
```

Do not set `QDRANT_API_KEY`. If healthcheck says “service unavailable”, `PORT` is not `8000` or `railwayConfigFile` is not `/deploy/railway/api.toml`.

## 3. sync

Hourly cron (`0 * * * *`), `restartPolicyType = NEVER`. No HTTP port. No `QDRANT_API_KEY`.

```bash
railway add --service sync --json
python3 .agents/skills/how-to-deploy-to-railway/scripts/set_railway_config_file.py sync /deploy/railway/sync.toml

railway variable set \
  'QDRANT_URL=http://${{Qdrant.RAILWAY_PRIVATE_DOMAIN}}:6333' \
  "OPENROUTER_API_KEY=${OPENROUTER_API_KEY}" \
  --service sync --skip-deploys

railway service source connect --repo "$REPO" --branch main --service sync
```

Wait until that deploy is SUCCESS (not INITIALIZING). `source connect` builds the image and registers the hourly schedule; the first tick waits until `:00` UTC. `railway service redeploy` is **not** Run now. Trigger one execution with `deploymentInstanceExecutionCreate` (service **instance** id, not service id):

```bash
python3 - <<'PY'
import json, subprocess

def sh(*args):
    return subprocess.check_output(args, text=True)

status = json.loads(sh("railway", "status", "--json"))
env_id = status["environments"]["edges"][0]["node"]["id"]
svc_id = next(e["node"]["id"] for e in status["services"]["edges"] if e["node"]["name"] == "sync")
inst = json.loads(sh(
    "railway", "api",
    "--var", f"environmentId={json.dumps(env_id)}",
    "--var", f"serviceId={json.dumps(svc_id)}",
    "query($environmentId: String!, $serviceId: String!) { serviceInstance(environmentId: $environmentId, serviceId: $serviceId) { id } }",
))
instance_id = inst["data"]["serviceInstance"]["id"]
out = json.loads(sh(
    "railway", "api",
    "--variables", json.dumps({"input": {"serviceInstanceId": instance_id}}),
    "mutation($input: DeploymentInstanceExecutionCreateInput!) { deploymentInstanceExecutionCreate(input: $input) }",
))
print(json.dumps(out, indent=2))
if out.get("errors") or not (out.get("data") or {}).get("deploymentInstanceExecutionCreate"):
    raise SystemExit("Run now failed; wait until sync is idle and retry. Do not railway service redeploy.")
PY

railway logs --service sync --latest --lines 80
```

Ingest has started when logs show `open batch created=` (or later `updated=`). `setup_qdrant` then `Stopping Container` is only the pre-deploy hook. You may continue with mcp / caddy once ingest lines appear.

## 4. mcp

Private. Pin `PORT=8001`.

```bash
railway add --service mcp --json
python3 .agents/skills/how-to-deploy-to-railway/scripts/set_railway_config_file.py mcp /deploy/railway/mcp.toml

railway variable set \
  'OPENHEDGE_API_URL=http://${{api.RAILWAY_PRIVATE_DOMAIN}}:8000' \
  PORT=8001 \
  --service mcp --skip-deploys

railway service source connect --repo "$REPO" --branch main --service mcp

railway domain list --service mcp
# if a public hostname is listed:
# railway domain delete --service mcp <the-domain>
```

Literal `:8000` in `OPENHEDGE_API_URL` (same as pinned `api` `PORT`).

## 5. caddy

Public edge. [`deploy/caddy/Caddyfile`](../../../deploy/caddy/Caddyfile) answers `/health` locally and proxies everything else to private MCP (`flush_interval -1`).

```bash
railway add --service caddy --json
python3 .agents/skills/how-to-deploy-to-railway/scripts/set_railway_config_file.py caddy /deploy/railway/caddy.toml

railway variable set \
  'UPSTREAM_URL=${{mcp.RAILWAY_PRIVATE_DOMAIN}}:8001' \
  PORT=8080 \
  --service caddy --skip-deploys

railway service source connect --repo "$REPO" --branch main --service caddy
railway domain --service caddy
```

Literal `:8001` in `UPSTREAM_URL` (same as pinned `mcp` `PORT`). Do **not** prefix `http://` — Caddy `{http.*}` placeholders swallow the host and the replica dials `:8001` on itself; Railway then fails `/health` with “service unavailable”.

If the next step is Cloudflare Tunnel, skip `railway domain --service caddy` (or delete that hostname in [how-to-add-cloudflare-tunnel](../how-to-add-cloudflare-tunnel/SKILL.md)). A `*.up.railway.app` hostname bypasses WAF and rate limits.

Do not `source connect` a service that is already on this repo. Point the client at `https://<caddy-domain>/mcp`.

```json
{
  "mcpServers": {
    "openhedge": {
      "url": "https://<caddy-domain>/mcp"
    }
  }
}
```

## Verify

```bash
curl -sS "https://<caddy-domain>/health"   # Caddy local; Railway healthcheck
curl -sS "https://<caddy-domain>/ready"    # MCP via Caddy
```

Confirm `sync` logs a successful `sync_markets` pass. `api` and `mcp` `/health` are private. If Caddy healthcheck says “service unavailable”, `UPSTREAM_URL` still has `http://` or Caddy is proxying `/health` to MCP.

## Pitfalls

- Do not `railway up`. Use GitHub `source connect`.
- Do not use `railway deploy --template i1tz3T` or a Caddy marketplace template as a nested source.
- Do not set `QDRANT_API_KEY`, `QDRANT__SERVICE__API_KEY`, `QDRANT__SERVICE__HTTP_PORT`, or `QDRANT__STORAGE__STORAGE_PATH` (image defaults; generate would strip literals into required empty fields).
- `railwayConfigFile` before `source connect`. There is no root `railway.toml`.
- `railway volume add` after `railway service Qdrant`. Not `--service` on `add`.
- Create `api` / `sync` / `mcp` / `caddy` one at a time. If caddy add fails with an empty body, retry or use `serviceCreate`.
- Do not set `API_PORT` / `MCP_PORT` / `API_HOST` / `MCP_HOST`.
- Do not use `${{api.PORT}}` or `${{mcp.PORT}}` in other services’ vars.
- Do not put `http://` in `UPSTREAM_URL`. Use `${{mcp.RAILWAY_PRIVATE_DOMAIN}}:8001`. Caddy `{http.*}` placeholders drop the host (`dial tcp :8001`).
- Caddy `/health` is local JSON. Do not reverse-proxy it to MCP or Caddy deploys wait on MCP.
- Do not attach a Railway public domain to `mcp` or `Qdrant`.
- Reference `Qdrant` (canvas name), not `qdrant`.
- `OPENROUTER_API_KEY` on api and sync only.
- Cron `sync`: Run now via `deploymentInstanceExecutionCreate`. Do not `railway service redeploy`. Confirm `open batch created=`, not only `setup_qdrant`.
- Do not add `cloudflared` or `TUNNEL_TOKEN` if this project will be used to generate the marketplace template.
