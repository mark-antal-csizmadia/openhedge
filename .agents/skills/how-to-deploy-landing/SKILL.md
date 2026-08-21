---
name: how-to-deploy-landing
description: >-
  Deploys the Next.js landing page (web/) to its own Railway project at
  openhedge.app. Use when the user wants to ship, update, or debug the public
  MCP install site — not the OSS Qdrant/api/sync/mcp/caddy stack.
---

# How to deploy the landing page

Visitor site at [openhedge.app](https://openhedge.app). Points clients at `https://mcp.openhedge.app/mcp`. **Separate Railway project** from the OSS stack. Never add `web` to Compose, [`deploy/railway/`](../../../deploy/railway/), the marketplace template, or the project that has `Qdrant` / `api` / `sync` / `mcp` / `caddy`. Never commit a root `railway.toml`. Do not `railway up`. Do not generate a template from this project. Do not add a public hostname on the OSS Cloudflare tunnel. Do not put Caddy or Cloudflared in this project.

Local preview: `npm install` and `npm run dev` in [`web/`](../../../web/).

## Workflow

```
- [ ] railway login; GitHub connected
- [ ] New empty project (not the OSS stack)
- [ ] web service: config file → Root Directory web → GitHub; wait SUCCESS
- [ ] Custom domain openhedge.app on web (CNAME target from Railway, not the generated *.up.railway.app)
- [ ] Cloudflare: replace parking A on @; CNAME @ → Railway target; TXT _railway-verify
- [ ] Wait until Railway cert is VALID, then orange-cloud is OK
- [ ] www: CNAME + Redirect Rule to apex; delete unused wildcard parking A
- [ ] Delete the generated Railway service domain
- [ ] Smoke apex 200, www 301→200, mcp /health 200
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

Do **not** reuse OSS Caddy + Cloudflared for this site. `*.railway.internal` is project-scoped; the OSS tunnel cannot reach `web` in `openhedge-web`. Adding `openhedge.app` as a tunnel public hostname couples the two Railway projects. Next.js already speaks HTTP on `PORT`; Caddy is the MCP edge, not a landing-page requirement.

## 1. web service

Config-as-code is [`deploy/web/railway.toml`](../../../deploy/web/railway.toml). Dockerfile context is [`web/`](../../../web/) (Root Directory **`web`**). `dockerfilePath` in the toml is `Dockerfile`, relative to that directory — not `web/Dockerfile`.

Set **config file and Root Directory before** `source connect`. Empty Root Directory + `dockerfilePath = "Dockerfile"` builds the repo root and fails.

```bash
railway add --service web --json
python3 .agents/skills/how-to-deploy-to-railway/scripts/set_railway_config_file.py web /deploy/web/railway.toml
```

Root Directory is `ServiceInstanceUpdateInput.rootDirectory` (not a CLI flag). Settings → Root Directory **`web`**, or:

```bash
python3 - <<'PY'
import json, subprocess

def sh(*args):
    return subprocess.check_output(args, text=True)

status = json.loads(sh("railway", "status", "--json"))
env_id = status["environments"]["edges"][0]["node"]["id"]
svc_id = next(e["node"]["id"] for e in status["services"]["edges"] if e["node"]["name"] == "web")
out = json.loads(
    sh(
        "railway",
        "api",
        "--variables",
        json.dumps({"serviceId": svc_id, "environmentId": env_id, "input": {"rootDirectory": "web"}}),
        "mutation($serviceId: String!, $environmentId: String!, $input: ServiceInstanceUpdateInput!) { serviceInstanceUpdate(serviceId: $serviceId, environmentId: $environmentId, input: $input) }",
    )
)
if out.get("errors"):
    raise SystemExit(json.dumps(out, indent=2))
print("web rootDirectory -> web")
PY
```

```bash
railway service source connect --repo "$REPO" --branch main --service web
railway service status --service web --json   # wait until status SUCCESS
```

Healthcheck is `/`.

## 2. Public hostname

```bash
railway domain --service web --json
railway domain openhedge.app --service web --json
railway domain status openhedge.app --service web --json
```

The generated `*.up.railway.app` service domain is only for debugging the first deploy. The DNS **CNAME target** is `dnsRecords[].requiredValue` on the **custom** domain (a host like `ob2z58sb.up.railway.app`) — not `web-production-….up.railway.app`. Copy `verification.token` and `verification.dnsHost` (`_railway-verify`) for Cloudflare.

Wait until `verification.verified` is true and `certificate.status` is `CERTIFICATE_STATUS_TYPE_VALID` (not `VALIDATING_OWNERSHIP`). `railway domain certificate retry` only works after issuance **fails**, not while it is still validating.

After apex returns 200, delete the generated service domain so visitors cannot skip Cloudflare. Keep the custom domain `openhedge.app`. Do not delete the CNAME target; Cloudflare still origins there.

```bash
railway domain list --service web --json
railway domain delete --service web <generated>.up.railway.app --yes
```

## 3. Cloudflare DNS (human)

On the existing `openhedge.app` zone, **do not** add a public hostname to the OSS `cloudflared` tunnel.

`@` in the Cloudflare **Name** field is the zone apex (`openhedge.app`).

Replace leftover **parking A** records on `@` / `www` / `*` (for example `91.195.240.94`). A proxied A to that origin is **525** (Cloudflare reached a host that will not finish TLS). That is not a Railway or Next.js failure.

Create:

| Type | Name | Content | Proxy |
|---|---|---|---|
| CNAME | `@` | the custom-domain CNAME target from Railway | DNS only (grey) until the Railway cert is VALID, then orange is OK |
| TXT | `_railway-verify` | the `railway-verify=…` token from `railway domain status` | DNS only |

Orange-cloud hides the CNAME from public DNS (flattened to Cloudflare A records). Railway then shows `currentValue` empty and may leave the CNAME as `REQUIRES_UPDATE` — expected. The TXT record is how Railway proves ownership behind Cloudflare. `mcp.openhedge.app` CNAME to `….cfargotunnel.com` stays as-is (more specific than `@`).

SSL/TLS mode **Full** (not Flexible). **Full (Strict)** needs a cert that names `openhedge.app`; keep **Full** until Railway shows VALID, then Strict is optional.

While the CNAME points at Railway but the cert is not issued yet, apex is often **404** with `x-railway-fallback: true` (`Application not found`). That means Cloudflare reached Railway; wait for the cert. **525** means Cloudflare is still hitting the old parking/tunnel origin.

### www

Do not add `www.openhedge.app` as a second Railway custom domain unless you want the page on two hostnames. Canonical URL is `https://openhedge.app`.

1. Delete the `www` parking A (and the `*.openhedge.app` parking A — otherwise `www` still 525s via the wildcard).
2. **CNAME** `www` → `openhedge.app` (or the same Railway target), **proxied**.
3. **Rules → Overview → Create rule → Redirect Rule** (not Page Rules, not the tunnel):
   - Wildcard **Request URL:** `https://www.openhedge.app/*`
   - **Target URL:** `https://openhedge.app/${1}`
   - **Status:** 301, preserve query string
   - **Deploy**

Without the redirect, Cloudflare sends `Host: www.openhedge.app` to Railway and you get the same 404 fallback.

## Verify

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://openhedge.app
curl -sS -D - -o /dev/null https://www.openhedge.app | head -15
curl -sS -o /dev/null -w '%{http_code} %{url_effective}\n' -L https://www.openhedge.app
curl -sS "https://mcp.openhedge.app/health"
```

Expect apex `200`, www `301` to `https://openhedge.app/`, then `200`. MCP stays on the OSS Caddy + tunnel (`https://mcp.openhedge.app/mcp`), not this site. After deleting the generated service domain, that `*.up.railway.app` URL should 404.

## Pitfalls

- Do not `railway link` the OSS project. `assert_not_oss_stack.py` must pass.
- Do not add `web` to [`deploy/railway/`](../../../deploy/railway/) or the marketplace template.
- Do not commit a root `railway.toml`.
- Do not `railway up`.
- Do not `templates create` / publish from this project.
- Do not point the OSS tunnel at this service. Do not add Caddy or Cloudflared here.
- Root Directory must be `web`, set **before** GitHub connect. Empty Root Directory + `dockerfilePath = "Dockerfile"` builds the wrong context.
- Do not set Root Directory on OSS api/mcp/sync/caddy (those Dockerfiles `COPY` from the repo root).
- CNAME target is the custom-domain `requiredValue`, not the generated `web-production-….up.railway.app`.
- Parking A on `@` → **525**. Railway not ready / wrong Host → **404** `x-railway-fallback`.
- Orange-cloud CNAME: add `_railway-verify` TXT; empty `currentValue` is expected.
- Delete the generated Railway service domain after apex 200; do not delete the custom domain.
- `uv` is Python-only. Landing page uses npm in `web/`.
