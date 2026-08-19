---
name: how-to-create-a-railway-template
description: >-
  Builds a template-safe Railway scratch project (Qdrant Docker image, GitHub
  sources, no railway up) and generates the marketplace template. Use when the
  user wants to create, generate, or publish a Railway template, or when
  Generate Template fails with "does not have a source".
---

# How to create a Railway template

Scratch project for **Generate Template**. Do not generate from a `railway up` deploy. Do not invent `OPENROUTER_API_KEY`. Never commit a root `railway.toml`. Never use `pip`. Ask the user for the OpenRouter key if it is missing.

A hosted stack to *run* (local snapshot) is [how-to-deploy-to-railway-using-railway-cli](../how-to-deploy-to-railway-using-railway-cli/SKILL.md). Cloudflare Tunnel is [how-to-deploy-to-railway-with-cloudflare-tunnel](../how-to-deploy-to-railway-with-cloudflare-tunnel/SKILL.md) — do not add `cloudflared` here.

Templates can only copy **GitHub** or **Docker image** sources. `railway up` (local upload) and nested marketplace templates (`i1tz3T`, official Caddy) fail with `Service <name> does not have a source that can be used to generate a template`.

## Workflow

```
- [ ] railway login; GitHub connected; new scratch project
- [ ] Qdrant image + volume (private, no API key)
- [ ] api, then sync, then mcp, then caddy (config file → vars → GitHub)
- [ ] public domain only on caddy; smoke /health
- [ ] sync Run now; logs show open batch created=
- [ ] railway templates create; mark OPENROUTER_API_KEY required; publish
```

**Order:** `Qdrant` → `api` and `sync` → `mcp` → `caddy`. Create app services **one at a time** (a tight `railway add` loop can return an empty body).

Name the vector service **`Qdrant`**. Pin `PORT=8000` on `api`, `PORT=8001` on `mcp`, `PORT=8080` on `caddy`. Cross-service URLs cannot read `${{api.PORT}}`; put those literal ports in `OPENHEDGE_API_URL` and `UPSTREAM_URL`. `UPSTREAM_URL` is **host:port only** (no `http://`). Do **not** set `API_PORT`, `MCP_PORT`, `API_HOST`, `MCP_HOST`, `QDRANT_API_KEY`, or `QDRANT__SERVICE__API_KEY`. zsh: keep `${{...}}` in single quotes.

No root `railway.toml`. Per-service config is [`deploy/railway/`](../../../deploy/railway/). Set `railwayConfigFile` **before** `source connect`.

Qdrant has **no API key** (same as local Compose). Keep it private. Empty `QDRANT_API_KEY` is ignored by the app; omit the var entirely.

## Prerequisites

- [Railway CLI](https://docs.railway.com/cli)
- GitHub connected in Railway with access to this repo
- OpenRouter API key on **api** and **sync** only

```bash
export OPENROUTER_API_KEY='sk-or-...'   # from the user; never invent
export REPO="$(git remote get-url origin | sed -E 's#.*github.com[:/](.+)(\.git)?#\1#' | sed 's/\.git$//')"

railway login
railway init --name openhedge-template
```

Confirm `REPO` is `owner/openhedge` (no `.git`). If a CLI-uploaded project is already linked, `railway init` a **new** project instead of generating from that one.

## Helpers

Scripts live next to this skill. Run them from the **repo root**. `railwayConfigFile` is not a CLI flag.

```bash
python3 .agents/skills/how-to-create-a-railway-template/scripts/set_railway_config_file.py api /deploy/railway/api.toml
```

If `railway add --service <name>` returns `error decoding response body`, wait and retry once. Fallback:

```bash
python3 .agents/skills/how-to-create-a-railway-template/scripts/create_empty_service.py caddy
```

## 1. Qdrant

Image source (not `railway deploy --template i1tz3T`). No API key. No public domain.

```bash
railway add --image qdrant/qdrant:v1.19.0 --service Qdrant \
  --variables 'QDRANT__SERVICE__HTTP_PORT=6333' \
  --variables 'QDRANT__STORAGE__STORAGE_PATH=/qdrant/storage' \
  --json

railway service Qdrant
railway volume add --mount-path /qdrant/storage --json
```

`--service` is **not** valid after `volume add`. Link `Qdrant` first, then `add`. Do not use `railway volume --service Qdrant add` (CLI panic if the service is not already linked).

Wait until `Qdrant` is running before `api` / `sync` (pre-deploy `setup_qdrant` needs it).

## 2. api

```bash
railway add --service api --json
python3 .agents/skills/how-to-create-a-railway-template/scripts/set_railway_config_file.py api /deploy/railway/api.toml

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
python3 .agents/skills/how-to-create-a-railway-template/scripts/set_railway_config_file.py sync /deploy/railway/sync.toml

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
python3 .agents/skills/how-to-create-a-railway-template/scripts/set_railway_config_file.py mcp /deploy/railway/mcp.toml

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
python3 .agents/skills/how-to-create-a-railway-template/scripts/set_railway_config_file.py caddy /deploy/railway/caddy.toml

railway variable set \
  'UPSTREAM_URL=${{mcp.RAILWAY_PRIVATE_DOMAIN}}:8001' \
  PORT=8080 \
  --service caddy --skip-deploys

railway service source connect --repo "$REPO" --branch main --service caddy
railway domain --service caddy
```

Literal `:8001` in `UPSTREAM_URL` (same as pinned `mcp` `PORT`). Do **not** prefix `http://` — Caddy `{http.*}` placeholders swallow the host and the replica dials `:8001` on itself; Railway then fails `/health` with “service unavailable”.

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

## Generate and publish

```bash
railway templates create --json
```

In the template editor:

1. Mark `OPENROUTER_API_KEY` required (api + sync).
2. Public HTTP only on **caddy**.
3. Do not include `cloudflared` or `TUNNEL_TOKEN`.
4. Do not add a Qdrant API key.

Then publish and put the template code in the README Deploy button (`<TEMPLATE_CODE>`):

```bash
railway templates publish <TEMPLATE_CODE> \
  --category Other \
  --description "Discover hedges in event contracts and prediction markets" \
  --readme-file README.md
```

## Pitfalls

- Do not `railway up`. Do not generate a template from a CLI-upload project.
- Do not use `railway deploy --template i1tz3T` or a Caddy marketplace template as a nested source.
- Do not set `QDRANT_API_KEY` or `QDRANT__SERVICE__API_KEY`.
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
