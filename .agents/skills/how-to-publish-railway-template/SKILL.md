---
name: how-to-publish-railway-template
description: >-
  Generates and publishes the Railway marketplace template from an existing
  GitHub-sourced project. Use when the user wants to create, generate, or
  publish a Railway template. Requires the deploy skill stack first. Do not
  include cloudflared.
---

# How to publish a Railway template

Maintainer path. Snapshot a **GitHub-sourced** stack that is already up. Do not invent `OPENROUTER_API_KEY`. Never commit a root `railway.toml`. Never use `pip`. Do not add `cloudflared` or `TUNNEL_TOKEN`.

If the five services are not up yet, follow [how-to-deploy-to-railway](../how-to-deploy-to-railway/SKILL.md) first. Cloudflare Tunnel is [how-to-add-cloudflare-tunnel](../how-to-add-cloudflare-tunnel/SKILL.md) — generate the template from a project **without** that extra service.

Templates can only copy **GitHub** or **Docker image** sources. Nested marketplace templates (`i1tz3T`, official Caddy) fail with `Service <name> does not have a source that can be used to generate a template`.

## Workflow

```
- [ ] GitHub-sourced stack already up (Qdrant image, api, sync, mcp, caddy)
- [ ] No cloudflared / TUNNEL_TOKEN on this project
- [ ] railway templates create --json
- [ ] Prompt the user to set PORT in the unpublished composer; wait; verify_template_vars.py
- [ ] publish with short marketplace overview (not repo README.md)
- [ ] Put published code in the README Deploy button
```

## Prerequisites

- Railway CLI linked to the GitHub-sourced project from [how-to-deploy-to-railway](../how-to-deploy-to-railway/SKILL.md)
- Public HTTP only on **caddy**
- Qdrant is the Docker image `qdrant/qdrant:v1.19.0` with no API key and no `QDRANT__SERVICE__HTTP_PORT` / `QDRANT__STORAGE__STORAGE_PATH` (image defaults)

## Generate sanitizer

`railway templates create` (dashboard **Generate Template**) copies the live project:

- `${{...}}` references survive as `defaultValue` (`QDRANT_URL`, `OPENHEDGE_API_URL`, `UPSTREAM_URL`).
- Literals are blanked (`PORT=8000`, `OPENROUTER_API_KEY`). That is why `PORT` must be re-defaulted in the composer. `railway.toml` cannot declare service env vars.
- Runtime `PORT` is not dashboard-referenceable. Do not use `${{api.PORT}}` in other services; URLs stay `:8000` / `:8001`.
- Do **not** `templates create` again to “fix” PORT — that makes a new draft and re-strips literals.
- `railway templates publish` / `update` only changes marketplace metadata (category, description, readme). It does **not** change service variables.

## Generate

```bash
railway templates create --json
```

Use `id`, `code`, and `editorUrl` from the JSON. Work in that draft. Delete leftover unpublished drafts; do not leave a second template.

## Composer (required, user must click)

Generate blanks `PORT`. The public CLI/GraphQL API **cannot** set template variable defaults (`templateUpdateV2` is not on the CLI schema). Do **not** try to patch `serializedConfig`, cookies, or the browser. Do **not** `templates create` again.

**Stop and prompt the user** with `editorUrl` from create JSON. Ask them to open that unpublished template, edit each service’s **Variables** tab, then tell you when they have saved.

For each row: set **Variable value**, check **Mark as optional**. Empty + optional omits the var on deploy, so the value must be filled.

| Service | Variable | Value | Mark optional? |
| --- | --- | --- | --- |
| api | `PORT` | `8000` | yes |
| mcp | `PORT` | `8001` | yes |
| caddy | `PORT` | `8080` | yes |

Leave `OPENROUTER_API_KEY` on **api** and **sync** **required** and **empty** (no default). Same name so the deploy form asks once.

If Qdrant still has `QDRANT__SERVICE__HTTP_PORT` or `QDRANT__STORAGE__STORAGE_PATH`, **delete** those variables (image defaults). Do not leave them required and empty.

Public HTTP only on **caddy**. No `cloudflared`, `TUNNEL_TOKEN`, or Qdrant API key.

After the user confirms they saved, verify from the **repo root**:

```bash
python3 .agents/skills/how-to-publish-railway-template/scripts/verify_template_vars.py <TEMPLATE_ID>
```

Must print `ok: only OPENROUTER_API_KEY is required; PORT defaults set`. If it fails, show the errors and ask the user to fix the composer. Do not publish until it passes.

## Marketplace publish

Do **not** pass repo `README.md` as `--readme-file` (over 10k characters; missing required headings). Pipe a short overview that includes `# Deploy and Host`, `## About Hosting`, `## Why Deploy`, `## Common Use Cases`, `## Dependencies for`, and `### Deployment Dependencies`:

```bash
railway templates publish <TEMPLATE_ID> \
  --category Other \
  --description "Discover hedges in event contracts and prediction markets" \
  --readme-file - \
  --json <<'EOF'
# Deploy and Host openhedge with Railway

openhedge is an open source experimental tool for discovering relevant hedges using event contracts and prediction markets. It does not hold money or place trades. Any order happens on the source venue (today, Kalshi).

## About Hosting openhedge

This template deploys five services from GitHub (`api`, `sync`, `mcp`, `caddy`) plus Qdrant as `qdrant/qdrant:v1.19.0` with a volume at `/qdrant/storage`. `api` and `mcp` stay private. `caddy` is the only public HTTP edge and reverse-proxies streamable HTTP MCP. `sync` ingests open Kalshi markets and writes embeddings on an hourly cron. You must provide an OpenRouter API key (`OPENROUTER_API_KEY`) for embeddings and search. Point an MCP client at `https://<caddy-domain>/mcp`. Search stays empty until the first successful `sync` pass (`open batch created=` in logs). After deploy, trigger **Run now** on `sync` if you do not want to wait until `:00` UTC.

## Why Deploy openhedge on Railway

Railway is a singular platform to deploy your infrastructure stack. Railway will host your infrastructure so you don't have to deal with configuration, while allowing you to vertically and horizontally scale it.

By deploying openhedge on Railway, you are one step closer to supporting a complete full-stack application with minimal burden. Host your servers, databases, AI agents, and more on Railway.

## Common Use Cases

- Point a coding agent at live Kalshi markets via streamable HTTP MCP
- Search event contracts semantically for a described exposure
- Size a cash-flow hedge and present basis risk, including when nothing fits
- Self-host the catalog, embeddings, and MCP edge without running local Compose

## Dependencies for openhedge Hosting

- Qdrant `qdrant/qdrant:v1.19.0` (private, volume at `/qdrant/storage`, no API key)
- OpenRouter API key for embeddings (`OPENROUTER_API_KEY` on `api` and `sync`)
- Caddy reverse proxy (public) in front of private MCP
- Kalshi public market API (read-only ingest)

### Deployment Dependencies

- [openhedge GitHub repository](https://github.com/mark-antal-csizmadia/openhedge)
- [OpenRouter](https://openrouter.ai/)
- [Kalshi](https://kalshi.com)
- [Qdrant](https://qdrant.tech)
EOF
```

After publish, JSON `code` may change from the draft id to a slug. Put **that** `code` in the README Deploy button (`https://railway.com/new/template/<code>?utm_medium=integration&utm_source=button&utm_campaign=openhedge`) and the maintainer note. Do not invent a code.

## One-click deploy (consumers)

The README **Deploy on Railway** button is the one-click path. Do not invent a template URL.

- The deploy form should ask only for `OPENROUTER_API_KEY`.
- MCP is `https://<caddy-domain>/mcp` (Railway domain on **caddy**).
- Search stays empty until `sync` ingest (`open batch created=`). Cron is `0 * * * *`; the first tick waits until `:00` UTC. One-click deploys do **not** auto Run now (that is only [how-to-deploy-to-railway](../how-to-deploy-to-railway/SKILL.md)). After the stack is up, tell the user to **Run now** on `sync`.
- Do not attach a public domain to `mcp` or `Qdrant`.

## Pitfalls

- Do not generate from a project that has `cloudflared` or other extra services.
- Do not use `railway deploy --template i1tz3T` or a Caddy marketplace template as a nested source.
- Do not `railway up`. Sources must be GitHub or a Docker image.
- Do not set `QDRANT_API_KEY` or `QDRANT__SERVICE__API_KEY` on the template.
- Do not set `QDRANT__SERVICE__HTTP_PORT` or `QDRANT__STORAGE__STORAGE_PATH` on the source project or the template.
- Do not attach a Railway public domain to `mcp` or `Qdrant`.
- Do not pass repo `README.md` to `templates publish`.
- Do not `templates create` twice to fix variables; prompt the user to edit the draft composer, then verify.
- Do not call `templateUpdateV2` or otherwise try to set composer variables from the CLI. Prompt the user.
