---
name: how-to-add-cloudflare-tunnel
description: >-
  Adds Cloudflare Tunnel in front of an existing Railway Caddy edge for a
  custom domain, WAF, and rate limits. Use when the user asks for a Cloudflare
  tunnel, showcase/prod hostname, or edge rate limiting. Requires the Railway
  stack already up. Do not add cloudflared to the published template.
---

# How to add a Cloudflare Tunnel

Add-on on an existing hosted stack. Same Caddy + private MCP; the only topology change is **Cloudflare-only ingress** (custom hostname, WAF, rate limits).

Do **not** leave a Railway public domain on `caddy` or `mcp`. A `*.up.railway.app` hostname bypasses Cloudflare WAF and rate limits. Do not invent `TUNNEL_TOKEN` or `OPENROUTER_API_KEY`. Do not add `cloudflared` to the published Railway template.

If the five services are not up yet, follow [how-to-deploy-to-railway](../how-to-deploy-to-railway/SKILL.md) first (skip `railway domain --service caddy`), or use the README **Deploy on Railway** button. One-click template users also start here after the stack exists. Do not generate a marketplace template from a project that includes this tunnel — [how-to-publish-railway-template](../how-to-publish-railway-template/SKILL.md) needs a project without `cloudflared`.

## Workflow

```
- [ ] Railway stack already up (deploy skill or one-click template)
- [ ] User has a domain on Cloudflare and a tunnel token
- [ ] Delete Railway public domains on caddy and mcp
- [ ] Deploy cloudflared (cf-tunnel template)
- [ ] User: public hostname mcp.<domain> → caddy.railway.internal:8080
- [ ] User: SSL Full, rate limits, no Bot Fight on that host
- [ ] Smoke https://mcp.<domain>/health and /mcp
```

Caddy is already the edge (`PORT=8080`, `UPSTREAM_URL` → `mcp:8001`). This skill does not retarget Caddy unless those vars are missing.

## Prerequisites (ask the user; stop if missing)

- Domain whose nameservers are **Active** on Cloudflare
- Cloudflare Zero Trust access to create a **Cloudflared** tunnel
- Tunnel token (the long `--token` value from the Docker run snippet — not the whole command)
- Railway CLI linked to the same project as the OSS stack

Never invent the token. If the OSS stack is not up, follow [how-to-deploy-to-railway](../how-to-deploy-to-railway/SKILL.md) first (skip `railway domain --service caddy`).

## 1. Confirm Caddy is the edge

```bash
railway variable list --service caddy
railway variable list --service mcp
```

Expect `PORT=8080` and `UPSTREAM_URL=${{mcp.RAILWAY_PRIVATE_DOMAIN}}:8001` (host:port, no `http://`) on **caddy**, `PORT=8001` on **mcp**. Fix with the deploy skill’s Caddy/MCP steps if those are wrong. Caddy `/health` is local; `/mcp` and `/ready` proxy to MCP.

## 2. Detach Railway public domains

Rate limits only apply on the Cloudflare hostname.

```bash
railway domain list --service caddy
railway domain list --service mcp
# for each listed hostname:
# railway domain delete --service caddy <the-domain>
# railway domain delete --service mcp <the-domain>
```

Do not run `railway domain --service caddy` after this.

## 3. Cloudflare dashboard (human; do not fake clicks)

Stop and ask the user to complete these. Keep this page open while they copy the token.

1. [Zero Trust](https://one.dash.cloudflare.com) → **Networks** → **Tunnels** → **Create a tunnel** → **Cloudflared**.
2. Name it (e.g. `openhedge-caddy`).
3. Choose **Docker**; copy **only** the long token from `docker run ... --token <token>`.
4. Zone **SSL/TLS** mode: **Full** (not Flexible). Wait until the zone status is **Active**.

Paste the token into the shell (user provides it):

```bash
export TUNNEL_TOKEN='...'   # from the user; never invent
```

## 4. cloudflared on Railway

```bash
railway deploy --template cf-tunnel --variable "TUNNEL_TOKEN=${TUNNEL_TOKEN}"
```

The template service is often named **`Cloudflared`**. If so, rename it to **`cloudflared`** in the Railway dashboard (stable name for later deploys). Wait until the connector is **Healthy** in Zero Trust.

If `cloudflared` already exists, set `TUNNEL_TOKEN` on that service instead of deploying a second template.

## 5. Public hostname (human)

Back in the tunnel → **Configure** → **Public Hostname** → **Add**:

- **Subdomain:** `mcp`
- **Domain:** the user’s zone
- **Type:** HTTP
- **URL:** `caddy.railway.internal:8080`

Save. Clients use `https://mcp.<domain>/mcp`.

Do **not** enable Cloudflare Access or Bot Fight / JS challenge on this hostname (non-browser MCP clients break). Prefer rate limits:

- Hostname `mcp.<domain>`: ~30 requests / 10 seconds per IP (Block)
- Hostname + path `/mcp` + POST: ~15 requests / 10 seconds per IP (Block)

Confirm with Security Events / HTTP error **1015** when testing.

## Verify

```bash
curl -sS "https://mcp.<domain>/health"
curl -sS "https://mcp.<domain>/ready"
```

Cursor / MCP client:

```json
{
  "mcpServers": {
    "openhedge": {
      "url": "https://mcp.<domain>/mcp"
    }
  }
}
```

If health works on a Railway `*.up.railway.app` URL but not on `mcp.<domain>`, a Railway public domain is still attached — delete it and use only the tunnel.

## Pitfalls

- Railway public domain on **caddy** or **mcp** bypasses Cloudflare. Detach both.
- Tunnel URL must be `caddy.railway.internal:8080` (pinned Caddy `PORT`). Not MCP’s port.
- SSL **Flexible** will fail or loop; use **Full**.
- Do not invent `TUNNEL_TOKEN`. Do not commit it. Do not put it in the OSS template.
- Bot Fight on `/mcp` blocks Cursor and other MCP clients.
- Do not generate the marketplace template from this project after adding `cloudflared`.
