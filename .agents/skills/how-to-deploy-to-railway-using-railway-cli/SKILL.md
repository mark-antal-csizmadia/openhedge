---
name: how-to-deploy-to-railway-using-railway-cli
description: >-
  Deploys openhedge to Railway with the Railway CLI (Qdrant template, api,
  sync cron, private MCP, public Caddy). Use when the user asks to deploy to
  Railway, run railway up, or set Railway service variables — not to publish
  a marketplace template.
---

# How to deploy to Railway using Railway CLI

Stand up the hosted stack from the **repo root**. Do not invent `OPENROUTER_API_KEY`. Do not commit a root `railway.toml` (copy per service, then delete). Never use `pip`. Ask the user for the OpenRouter key if it is missing.

Local Compose is a different path — [how-to-get-started](../how-to-get-started/SKILL.md). For a custom domain, Cloudflare Tunnel, and edge rate limits, follow [how-to-deploy-to-railway-with-cloudflare-tunnel](../how-to-deploy-to-railway-with-cloudflare-tunnel/SKILL.md) after this stack is up. To generate a marketplace template, follow [how-to-create-a-railway-template](../how-to-create-a-railway-template/SKILL.md) (`railway up` sources cannot be templated).

## Workflow

```
- [ ] railway login; project linked
- [ ] Qdrant template (private)
- [ ] api (PORT=8000, Qdrant vars, railway up)
- [ ] sync (same Qdrant vars, railway up, Run now mutation, watch ingest logs)
- [ ] mcp (PORT=8001, OPENHEDGE_API_URL with :8000, railway up, no public domain)
- [ ] caddy (PORT=8080, UPSTREAM_URL with :8001, railway up, public domain)
- [ ] smoke /health and /mcp on the Caddy hostname
```

**Order:** `Qdrant` → `api` and `sync` → `mcp` → `caddy`.

The Qdrant marketplace template names the service **`Qdrant`**. Reference variables must use that name. App code only reads `API_PORT` / `MCP_PORT`; [`deploy/railway/api.toml`](../../../deploy/railway/api.toml) and [`mcp.toml`](../../../deploy/railway/mcp.toml) copy Railway `$PORT` onto those env vars in the start command. Do **not** set `API_PORT`, `MCP_PORT`, `API_HOST`, or `MCP_HOST` as Railway variables.

`${{api.PORT}}` and `${{mcp.PORT}}` are **not** shared across services. Pin `PORT=8000` on `api`, `PORT=8001` on `mcp`, `PORT=8080` on `caddy`, and put those literal ports in `OPENHEDGE_API_URL` and `UPSTREAM_URL`. `UPSTREAM_URL` is **host:port only** (no `http://`).

Config-as-code lives in [`deploy/railway/`](../../../deploy/railway/). `railway up` reads **root** `railway.toml`, so copy the matching file before each `up`.

Only **caddy** gets a public Railway domain. `mcp` stays private. If an earlier deploy attached a hostname to `mcp`, delete it.

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
```

Wait until that deploy is SUCCESS (not INITIALIZING). `railway up` only builds the image and registers the hourly schedule; the first tick waits until `:00` UTC. `railway service redeploy` is **not** Run now (it runs `setup_qdrant` then stops). Trigger one execution with `deploymentInstanceExecutionCreate`. That does not change `cronSchedule` or other service settings. Use the service **instance** id, not the service id.

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

Ingest has started when logs show `open batch created=` (or later `updated=`). `setup_qdrant` then `Stopping Container` is only the pre-deploy hook. Search stays empty until the pass finishes. If a previous execution is still Active, Railway skips the new run — wait for it to exit, then retry the mutation. You may continue with mcp / caddy once ingest lines appear; the first fill can take a long time.

## 4. mcp

Private. Pin `PORT=8001` so Caddy can use a literal port in `UPSTREAM_URL`.

```bash
railway add --service mcp

railway variable set \
  'OPENHEDGE_API_URL=http://${{api.RAILWAY_PRIVATE_DOMAIN}}:8000' \
  PORT=8001 \
  --service mcp --skip-deploys

cp deploy/railway/mcp.toml railway.toml
railway up . --service mcp --path-as-root
rm railway.toml

railway domain list --service mcp
# if a public hostname is listed:
# railway domain delete --service mcp <the-domain>
```

Use **literal** `:8000` in `OPENHEDGE_API_URL` (same as pinned `api` `PORT`). zsh: keep `${{...}}` in single quotes.

## 5. caddy

Public edge. [`deploy/caddy/Caddyfile`](../../../deploy/caddy/Caddyfile) answers `/health` locally and proxies everything else to private MCP (`flush_interval -1` for streamable HTTP).

```bash
railway add --service caddy

railway variable set \
  'UPSTREAM_URL=${{mcp.RAILWAY_PRIVATE_DOMAIN}}:8001' \
  PORT=8080 \
  --service caddy --skip-deploys

cp deploy/railway/caddy.toml railway.toml
railway up . --service caddy --path-as-root
rm railway.toml

railway domain --service caddy
```

Literal `:8001` in `UPSTREAM_URL` (same as pinned `mcp` `PORT`). Do **not** prefix `http://` — Caddy `{http.*}` placeholders swallow the host and the replica dials `:8001` on itself; Railway then fails `/health` with “service unavailable”.

Point the client at `https://<caddy-domain>/mcp`.

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

Confirm `sync` logs a successful `sync_markets` pass. `api` and `mcp` `/health` and `/ready` are private (no public domain). If Caddy healthcheck says “service unavailable”, `UPSTREAM_URL` still has `http://` or Caddy is proxying `/health` to MCP.

## Publish template

Do not generate a template from this `railway up` project. Follow [how-to-create-a-railway-template](../how-to-create-a-railway-template/SKILL.md).

## Pitfalls

- Copy `deploy/railway/<service>.toml` → `railway.toml` **immediately before** that service’s `railway up`; `rm` it after. Never leave or commit root `railway.toml`.
- Do not set `API_PORT` / `MCP_PORT` / `API_HOST` / `MCP_HOST` on Railway.
- Do not use `${{api.PORT}}` or `${{mcp.PORT}}` in other services’ vars.
- Do not put `http://` in `UPSTREAM_URL`. Use `${{mcp.RAILWAY_PRIVATE_DOMAIN}}:8001`. Caddy `{http.*}` placeholders drop the host (`dial tcp :8001`).
- Caddy `/health` is local JSON. Do not reverse-proxy it to MCP or Caddy deploys wait on MCP.
- Do not attach a Railway public domain to `mcp`.
- Reference `Qdrant` (template name), not `qdrant`.
- `OPENROUTER_API_KEY` on api and sync only. MCP talks only to the API. Caddy talks only to MCP.
- Cron `sync` does not stay running; after `railway up`, trigger one run with `deploymentInstanceExecutionCreate` (service **instance** id). Do not `railway service redeploy`. Confirm logs show `open batch created=`, not only `setup_qdrant`.
- Use `uv` for repo work; Railway builds API/MCP/sync from [`openhedge-core/Dockerfile`](../../../openhedge-core/Dockerfile) and Caddy from [`deploy/caddy/Dockerfile`](../../../deploy/caddy/Dockerfile).
