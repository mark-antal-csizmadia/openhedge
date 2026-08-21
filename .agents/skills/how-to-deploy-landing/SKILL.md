---
name: how-to-deploy-landing
description: >-
  Deploys the Next.js landing page (web/) to its own Railway project at
  openhedge.app. Use when the user wants to ship, update, or debug the public
  MCP install site — not the OSS Qdrant/api/sync/mcp/caddy stack.
---

# How to deploy the landing page

Visitor site at [openhedge.app](https://openhedge.app). Points clients at `https://mcp.openhedge.app/mcp`. **Separate Railway project** from the OSS stack. Never add `web` to Compose, [`deploy/railway/`](../../../deploy/railway/), the marketplace template, or the project that has `Qdrant` / `api` / `sync` / `mcp` / `caddy`. Never commit a root `railway.toml`. Do not `railway up`. Do not generate a template from this project. Do not add a public hostname on the OSS Cloudflare tunnel.

Local preview: `npm install` and `npm run dev` in [`web/`](../../../web/).

## Workflow

```
- [ ] railway login; GitHub connected
- [ ] New empty project (not the OSS stack)
- [ ] web service: config file → Root Directory web → GitHub
- [ ] Railway domain, then custom domain openhedge.app
- [ ] Cloudflare DNS CNAME flattening to Railway (proxied OK)
- [ ] Smoke https://openhedge.app → 200
```

## Prerequisites

- [Railway CLI](https://docs.railway.com/cli)
- GitHub connected in Railway with access to this repo
- Cloudflare zone for `openhedge.app` (apex CNAME flattening)

```bash
export REPO="$(git remote get-url origin | sed -E 's#.*github.com[:/](.+)(\.git)?#\1#' | sed 's/\.git$//')"

railway login
railway init --name openhedge-web    # or: railway link  (new empty project only)
```

Confirm `REPO` is `owner/openhedge` with no `.git`. `source connect` uses branch `main`.

Refuse if the linked project is the OSS stack:

```bash
python3 .agents/skills/how-to-deploy-landing/scripts/assert_not_oss_stack.py
```

## 1. web service

Config-as-code is [`deploy/web/railway.toml`](../../../deploy/web/railway.toml). Dockerfile context is [`web/`](../../../web/) (Root Directory **`web`**). `dockerfilePath` in the toml is `Dockerfile`, relative to that directory — not `web/Dockerfile`.

```bash
railway add --service web --json
python3 .agents/skills/how-to-deploy-to-railway/scripts/set_railway_config_file.py web /deploy/web/railway.toml
```

In Railway **Settings** for `web`: set **Root Directory** to `web`. Leave it empty and the image looks for `Dockerfile` at the repo root and fails.

```bash
railway service source connect --repo "$REPO" --branch main --service web
```

Wait until the deploy is SUCCESS. Healthcheck is `/`.

## 2. Public hostname

```bash
railway domain --service web
```

Then attach the custom domain `openhedge.app` on **web** (Settings → Networking / Custom Domain). Railway will show a CNAME target.

## 3. Cloudflare DNS (human)

On the existing `openhedge.app` zone, **do not** add a public hostname to the OSS `cloudflared` tunnel (that couples the two Railway projects).

Create a DNS record:

- **Type:** CNAME (apex flattening)
- **Name:** `@`
- **Target:** the Railway hostname for `web`
- **Proxy:** orange cloud is OK (this is a browser page, not MCP)

SSL/TLS mode **Full**.

## Verify

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://openhedge.app
```

Expect `200`. Clients still use `https://mcp.openhedge.app/mcp` (OSS Caddy + tunnel), not this site.

## Pitfalls

- Do not `railway link` the OSS project. `assert_not_oss_stack.py` must pass.
- Do not add `web` to [`deploy/railway/`](../../../deploy/railway/) or the marketplace template.
- Do not commit a root `railway.toml`.
- Do not `railway up`.
- Do not `templates create` / publish from this project.
- Do not point the OSS tunnel at this service.
- Root Directory must be `web`. Empty Root Directory + `dockerfilePath = "Dockerfile"` builds the wrong context.
- Do not set Root Directory on OSS api/mcp/sync/caddy (those Dockerfiles `COPY` from the repo root).
- `uv` is Python-only. Landing page uses npm in `web/`.
