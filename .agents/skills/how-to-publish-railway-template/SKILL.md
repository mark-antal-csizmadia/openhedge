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
- [ ] Prompt the user with the copy-paste kit (values, descriptions, icon); wait; verify
- [ ] Agent runs railway templates publish with category, description, overview, and --image
- [ ] Put published code in the README Deploy button
```

**Who does what.** The agent runs every CLI step. Do **not** ask the user to invent marketplace copy. Send the copy-paste kit so they only paste or upload.

| Item | Agent (CLI) | User (composer) |
| --- | --- | --- |
| Create draft from the linked project | `templates create --json` | — |
| Category **Other** | `templates publish --category Other` | — |
| Card description (25–75 chars) | `--description "Discover hedges in event contracts and prediction markets"` | — |
| Overview (required headings) | `--readme-file -` with the heredoc below | — |
| Icon | `--image` GitHub raw URL of `deploy/railway/template-icon.svg` | Also upload that SVG in the composer if `--image` is not on the default branch yet |
| `PORT` defaults, optional, descriptions | — | paste from kit |
| Mark `QDRANT_URL` / `OPENHEDGE_API_URL` / `UPSTREAM_URL` optional + descriptions | — | paste from kit (keep generated defaults) |
| `OPENROUTER_API_KEY` required + description | — | paste from kit |

`templates create` has no flags for any of the card or variable fields. `templates publish` / `update` sets category, description, readme, and optional `--image` only — **not** service variables.

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

Generate blanks `PORT`. The public CLI/GraphQL API **cannot** set template variable defaults, descriptions, or the icon. Do **not** try to patch `serializedConfig`. Do **not** `templates create` again.

The dashboard **Publishing requirements** list is why a generated draft still says “Not published”. Generate copies services and `${{...}}` defaults, but it does **not** set marketplace card fields, variable descriptions, or an icon. `isOptional: false` vars without a description fail “A description on every required variable” even when they already have a default (`QDRANT_URL`, `OPENHEDGE_API_URL`, `UPSTREAM_URL`).

**Stop.** Send the copy-paste kit below with `editorUrl` filled in. Do not ask them to invent values, descriptions, or an icon. They edit this generated draft (canvas shows `Qdrant`, `api`, `sync`, `mcp`, `caddy`). A blank **New Template** fails “At least one service”. Save after edits.

If Qdrant still has `QDRANT__SERVICE__HTTP_PORT` or `QDRANT__STORAGE__STORAGE_PATH`, **delete** those rows. Public HTTP only on **caddy**. No `cloudflared`, `TUNNEL_TOKEN`, or Qdrant API key.

### Copy-paste kit (send this to the user)

Substitute `<EDITOR_URL>` only. Everything else is ready to paste.

---

Open the generated draft (not a blank New Template):

`<EDITOR_URL>`

Canvas must show five services: `Qdrant`, `api`, `sync`, `mcp`, `caddy`. Then:

**1. Icon.** Upload [`deploy/railway/template-icon.svg`](../../../deploy/railway/template-icon.svg) (1:1 SVG, dark green card with a cream price path). In the composer, use the template icon control and pick that file. If the file picker wants a PNG, export that SVG at 512×512.

**2. Variables.** For each row: paste **Value** if listed, check **Mark as optional** when the kit says yes, paste **Description** into the description field. Keep generated `${{...}}` defaults — do not rewrite them. Empty + optional omits the var on deploy, so optional rows must keep their value.

| Service | Variable | Value | Optional? |
| --- | --- | --- | --- |
| api | `PORT` | `8000` | yes |
| mcp | `PORT` | `8001` | yes |
| caddy | `PORT` | `8080` | yes |
| api, sync | `QDRANT_URL` | keep generated default | yes |
| mcp | `OPENHEDGE_API_URL` | keep generated default | yes |
| caddy | `UPSTREAM_URL` | keep generated default | yes |
| api, sync | `OPENROUTER_API_KEY` | leave empty | **no** |

Paste these descriptions (same text on api and sync where the var appears twice). Each fence is one field — copy the body only, not the heading.

**api `PORT`:**

```
HTTP listen port for the REST API. Keep 8000. MCP talks to this service on :8000; the port is not referenceable as ${{api.PORT}}.
```

**mcp `PORT`:**

```
HTTP listen port for streamable MCP. Keep 8001. Caddy reverse-proxies this service on :8001; the port is not referenceable as ${{mcp.PORT}}.
```

**caddy `PORT`:**

```
Public Caddy listen port. Keep 8080. Railway's healthcheck and the public domain bind here.
```

**`QDRANT_URL` (api and sync):**

```
Private Qdrant HTTP URL. Keep the generated default (${{Qdrant.RAILWAY_PRIVATE_DOMAIN}}:6333). No API key. Image defaults already use HTTP 6333 and /qdrant/storage.
```

**`OPENHEDGE_API_URL` (mcp):**

```
Private REST API base URL for MCP. Keep the generated default (${{api.RAILWAY_PRIVATE_DOMAIN}}:8000). No public domain on api.
```

**`UPSTREAM_URL` (caddy):**

```
Private MCP host:port for Caddy reverse_proxy. No http:// prefix. Keep the generated default (${{mcp.RAILWAY_PRIVATE_DOMAIN}}:8001). No public domain on mcp.
```

**`OPENROUTER_API_KEY` (api and sync)** — leave **required** and **empty**. Same name on both services so the one-click form asks once. This is the only field deployers type.

```
OpenRouter API key for embeddings and search. Create one at https://openrouter.ai/keys. The same key is applied to api and sync.
```

Save the composer. Reply here when it is saved.

---

Do not ask them to invent category, card description, or overview. You set those with `templates publish`. If the dashboard Publish form is already open, they may paste:

- Category: `Other`
- Description: `Discover hedges in event contracts and prediction markets`

After they confirm save, verify from the **repo root**:

```bash
python3 .agents/skills/how-to-publish-railway-template/scripts/verify_template_vars.py <TEMPLATE_ID>
```

Must print `ok: only OPENROUTER_API_KEY is required; PORT defaults set`. If it fails, show the errors and ask them to fix the composer. Do not publish until it passes.

## Marketplace publish (agent runs this)

Do **not** tell the user to fill description, category, or overview in the dashboard. After verify passes, **you** run `railway templates publish` with the flags below. That is what clears those three “Publishing requirements” rows. Repo `README.md` is over 10k characters and missing required headings — do not pass it as `--readme-file`.

Do **not** dashboard-Publish first; the UI list stays red until composer + this command. If they already tried the UI, still run this CLI.

Card description must be **25–75 characters**. Use this 58-character string exactly:

`--description "Discover hedges in event contracts and prediction markets"`

`--category Other`.

Always pass `--image` with the public GitHub raw URL of the repo icon (1:1 SVG). Use the default branch after the file is on GitHub:

`https://raw.githubusercontent.com/mark-antal-csizmadia/openhedge/main/deploy/railway/template-icon.svg`

If that URL 404s (file not on `main` yet), omit `--image` and rely on the composer upload from the copy-paste kit. Do not invent a different URL.

Overview must include `# Deploy and Host`, `## About Hosting`, `## Why Deploy`, `## Common Use Cases`, `## Dependencies for`, and `### Deployment Dependencies` (no scaffold placeholders). Pipe it:

```bash
railway templates publish <TEMPLATE_ID> \
  --category Other \
  --description "Discover hedges in event contracts and prediction markets" \
  --image https://raw.githubusercontent.com/mark-antal-csizmadia/openhedge/main/deploy/railway/template-icon.svg \
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
- Do not call `templateUpdateV2` or otherwise try to set composer variables from the CLI. Send the copy-paste kit.
- Do not ask the user to invent descriptions, PORT values, or an icon. Paste the kit; they copy and upload `deploy/railway/template-icon.svg`.
- Do not ask the user to type marketplace category, card description, or overview in the dashboard. Run `templates publish` yourself.
- Dashboard “Publishing requirements”: **you** set category / description / overview / icon URL with `templates publish`. User pastes composer variables from the kit and uploads the SVG if `--image` 404s. Five services come from `templates create` on the generated draft.
