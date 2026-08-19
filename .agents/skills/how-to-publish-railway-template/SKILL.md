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
- [ ] Prompt the user with the copy-paste kit (Dockerfile var, start commands, values, descriptions, icon, healthchecks, sync cron); wait; verify
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
| `RAILWAY_DOCKERFILE_PATH` defaults | — | paste from kit (composer has **no** Config File field) |
| Start commands + sync cron / Never restart | — | paste from kit (**Settings** tab) |
| api / mcp / caddy healthcheck `/health` | — | paste from kit (**Settings** tab) |
| `PORT` defaults, optional, descriptions | — | paste from kit |
| Mark `QDRANT_URL` / `OPENHEDGE_API_URL` / `UPSTREAM_URL` optional + descriptions | — | paste from kit (keep generated defaults) |
| `OPENROUTER_API_KEY` required + description | — | paste from kit |

`templates create` has no flags for any of the card or variable fields. `templates publish` / `update` sets category, description, readme, and optional `--image` only — **not** service variables, start commands, or healthcheck paths.

## Prerequisites

- Railway CLI linked to the GitHub-sourced project from [how-to-deploy-to-railway](../how-to-deploy-to-railway/SKILL.md)
- Public HTTP only on **caddy**
- Qdrant is the Docker image `qdrant/qdrant:v1.19.0` with no API key and no `QDRANT__SERVICE__HTTP_PORT` / `QDRANT__STORAGE__STORAGE_PATH` (image defaults)

## Generate sanitizer

`railway templates create` (dashboard **Generate Template**) snapshots the live GitHub-sourced project. A one-click from a raw snapshot **builds with Railpack at the repo root** and crashes (`Railpack could not determine how to build the app` / `start.sh not found`). Qdrant (image + volume) succeeds; api / mcp / sync / caddy fail. Variables such as `QDRANT_URL` / `OPENHEDGE_API_URL` / `UPSTREAM_URL` usually interpolate. The dashboard builder on the live stack stays **RAILPACK** with empty dockerfile/start — deploys work there only because each GitHub service has `railwayConfigFile` (`/deploy/railway/api.toml`, `mcp.toml`, `sync.toml`, `caddy.toml`). Generate copies GitHub sources, `${{...}}` variable defaults, Qdrant’s image and volume, and caddy’s public domain. It does **not** copy `configFile`, Dockerfile builder, start commands, pre-deploy, sync cron, or canvas healthchecks.

What the composer can and cannot set:

- **Has:** Variables tab; Settings tab (Root Directory, public networking, Start Command, Healthcheck Path; Cron / Restart / Pre-deploy if shown).
- **Does not have:** Config File / Custom Config File / Config as Code. That control exists only on a **live** service. Do **not** send the user looking for it in the template editor.
- Paper over the drop with a **new** optional variable `RAILWAY_DOCKERFILE_PATH` (Variables → Add / New variable; it is not a Settings control and is not listed until created) plus Settings start / healthcheck / sync cron. Do **not** add a root `railway.toml` (four GitHub services, two Dockerfiles). Do **not** `templates create` again to “fix” anything — that makes a new draft and re-strips literals.

**Root Directory is not the fix.** Railway treats it as the Docker build context. These Dockerfiles `COPY` from the **repo root** (`README.md`, `openhedge-core/pyproject.toml`, `openhedge-core/src`, `deploy/caddy/Caddyfile`). Setting api/mcp/sync to `openhedge-core` or caddy to `deploy/caddy` finds a `Dockerfile` but those COPY paths miss. Local Compose uses context `.` with the same files. Root Directory also does not set start commands (shared `CMD` is `sync_markets`), sync cron, or `/health`. Leave Root Directory empty. Keep `source.rootDirectory` null.

Other generate rules:

- `${{...}}` references survive as `defaultValue` (`QDRANT_URL`, `OPENHEDGE_API_URL`, `UPSTREAM_URL`). Keep them.
- Literals are blanked (`PORT=8000`, `OPENROUTER_API_KEY`). Re-default `PORT` in the composer. `railway.toml` cannot declare service env vars.
- Runtime `PORT` is not dashboard-referenceable. Do not use `${{api.PORT}}`; URLs stay `:8000` / `:8001`.
- Caddy already has `healthcheckPath = "/health"` in [`deploy/railway/caddy.toml`](../../../deploy/railway/caddy.toml) (Caddyfile answers it locally; it does not proxy `/health` to MCP). Generate often leaves the **canvas** Healthcheck Path empty. The guidelines checker looks at that field, not the live toml, and warns: Service "caddy" has a public domain but no healthcheck path. Re-set `/health` on **caddy** (and api / mcp) in Settings.
- `railway templates publish` / `update` only changes marketplace metadata (category, description, readme). It does **not** change service variables, start commands, or healthchecks.

## Generate

```bash
railway templates create --json
```

Use `id`, `code`, and `editorUrl` from the JSON. Work in that draft. Delete leftover unpublished drafts; do not leave a second template.

## Composer (required, user must click)

Generate blanks `PORT`, drops each GitHub service’s `railwayConfigFile`, and drops canvas healthchecks and start commands. The template composer **Settings** tab can set Root Directory, public networking, Start Command, and Healthcheck Path — not Config File. Leave Root Directory empty (see sanitizer). The public CLI/GraphQL API **cannot** set template variable defaults, descriptions, the icon, or those Settings fields. Do **not** try to patch `serializedConfig`. Do **not** `templates create` again.

The dashboard **Publishing requirements** list is why a generated draft still says “Not published”. Generate copies services and `${{...}}` defaults, but it does **not** set marketplace card fields, variable descriptions, or an icon. `isOptional: false` vars without a description fail “A description on every required variable” even when they already have a default (`QDRANT_URL`, `OPENHEDGE_API_URL`, `UPSTREAM_URL`). Template **guidelines** also warn when public **caddy** has no canvas healthcheck — that is a composer paste, not a CLI publish field. Missing Dockerfiles are not a publishing-requirements row; one-click deploys still crash at build until the user pastes `RAILWAY_DOCKERFILE_PATH` and Settings from the kit.

**Stop.** Send the copy-paste kit below with `editorUrl` filled in. Do not ask them to invent values, descriptions, an icon, healthcheck paths, or start commands. Do not send them looking for Config File in the composer. Do not tell them to set Root Directory. They edit this generated draft (canvas shows `Qdrant`, `api`, `sync`, `mcp`, `caddy`). A blank **New Template** fails “At least one service”. Save after edits.

If Qdrant still has `QDRANT__SERVICE__HTTP_PORT` or `QDRANT__STORAGE__STORAGE_PATH`, **delete** those rows. Public HTTP only on **caddy**. No `cloudflared`, `TUNNEL_TOKEN`, or Qdrant API key.

### Copy-paste kit (send this to the user)

Substitute `<EDITOR_URL>` only. Everything else is ready to paste.

---

Open the generated draft (not a blank New Template):

`<EDITOR_URL>`

Canvas must show five services: `Qdrant`, `api`, `sync`, `mcp`, `caddy`. Then:

**1. Icon.** Upload [`deploy/railway/template-icon.svg`](../../../deploy/railway/template-icon.svg) (1:1 SVG, dark green card with a cream price path). In the composer, use the template icon control and pick that file. If the file picker wants a PNG, export that SVG at 512×512.

**2. Settings tab (not Config File, not Root Directory).** The live stack uses `railwayConfigFile` so each GitHub service reads its Dockerfile, start command, healthcheck, and sync cron from [`deploy/railway/`](../../../deploy/railway/). Generate Template drops that pointer. The composer has **no Config File** field — that exists only on a **live** service. Do not hunt for it.

Do not set **Root Directory** / Source root. It is the Docker build context. These Dockerfiles `COPY` repo-root paths (`README.md`, `openhedge-core/…`, `deploy/caddy/Caddyfile`). Pointing api at `openhedge-core` or caddy at `deploy/caddy` finds a Dockerfile and then fails those COPY lines. It also would not set start commands, cron, or `/health`. Leave the field empty.

Do not run Generate Template / `templates create` again. Do not add a root `railway.toml`. Leave Qdrant as the image.

Click each GitHub service → **Settings**:

| Service | Start Command | Healthcheck Path | Also set if the field exists |
| --- | --- | --- | --- |
| api | kit fence below | `/health` (timeout `300`) | Pre-deploy: `python -m openhedge_core.setup_qdrant` |
| mcp | kit fence below | `/health` (timeout `300`) | — |
| sync | `python -m openhedge_core.sync_markets` | leave empty | Cron Schedule `0 * * * *`; Restart Policy **Never** |
| caddy | leave empty | `/health` (timeout `300`) | — |

**api Start Command:**

```
/bin/sh -c 'export API_HOST=0.0.0.0 API_PORT="$PORT"; exec python -m openhedge_core.server'
```

**mcp Start Command:**

```
/bin/sh -c 'export MCP_HOST=0.0.0.0 MCP_PORT="$PORT"; exec python -m openhedge_core.mcp_server'
```

The Dockerfile `CMD` is `sync_markets`. Without those start commands, api and mcp would run the ingest job.

**3. Variables.** Click the service → **Variables**. `RAILWAY_DOCKERFILE_PATH` is **not** a Settings or Source field and will not appear until you create it. Use **New variable** (or Add variable) — same control you used for `PORT`. Name it exactly `RAILWAY_DOCKERFILE_PATH`, paste the Value, mark optional, paste the Description. Empty + optional omits the var on deploy, so optional rows must keep their value. Keep generated `${{...}}` defaults for the other rows — do not rewrite them.

If Settings already shows **Builder** / **Dockerfile Path**, you may set those too (`DOCKERFILE` + the same path). Still add the variable; Generate does not copy dashboard build settings. Do not set Root Directory.

| Service | Variable | Value | Optional? |
| --- | --- | --- | --- |
| api, mcp, sync | `RAILWAY_DOCKERFILE_PATH` | `openhedge-core/Dockerfile` | yes |
| caddy | `RAILWAY_DOCKERFILE_PATH` | `deploy/caddy/Dockerfile` | yes |
| api | `PORT` | `8000` | yes |
| mcp | `PORT` | `8001` | yes |
| caddy | `PORT` | `8080` | yes |
| api, sync | `QDRANT_URL` | keep generated default | yes |
| mcp | `OPENHEDGE_API_URL` | keep generated default | yes |
| caddy | `UPSTREAM_URL` | keep generated default | yes |
| api, sync | `OPENROUTER_API_KEY` | leave empty | **no** |

Paste these descriptions (same text on api and sync where the var appears twice). Each fence is one field — copy the body only, not the heading.

**`RAILWAY_DOCKERFILE_PATH` (api, mcp, sync):**

```
Path to the service Dockerfile. Keep openhedge-core/Dockerfile so Railway builds with Docker instead of Railpack. The repo root is not a language app.
```

**caddy `RAILWAY_DOCKERFILE_PATH`:**

```
Path to the Caddy Dockerfile. Keep deploy/caddy/Dockerfile so Railway builds with Docker instead of Railpack.
```

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

Must print `ok: only OPENROUTER_API_KEY is required; PORT defaults set; Dockerfiles and start commands set`. If it fails, show the errors and ask them to fix the composer. Do not publish until it passes.

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

This template deploys five services from GitHub (`api`, `sync`, `mcp`, `caddy`) plus Qdrant as `qdrant/qdrant:v1.19.0` with a volume at `/qdrant/storage`. `api` and `mcp` stay private. `caddy` is the only public HTTP edge and reverse-proxies streamable HTTP MCP. `sync` ingests open Kalshi markets and writes embeddings on an hourly cron. You must provide an OpenRouter API key (`OPENROUTER_API_KEY`) for embeddings and search. Point an MCP client at the Caddy public hostname plus `/mcp`. Search stays empty until the first successful `sync` pass (`open batch created=` in logs). After deploy, trigger **Run now** on `sync` if you do not want to wait until `:00` UTC.

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
- One-click must Docker-build via `RAILWAY_DOCKERFILE_PATH` plus Settings start/healthcheck/cron. If api/mcp/sync/caddy build with Railpack and fail at the repo root, those kit fields are missing — open the composer, paste them, save; do not `templates create` again. Already-deployed projects do not pick that up; on the **live** project, Service Settings → Config File **does** exist (`/deploy/railway/api.toml`, …), then redeploy.
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
- Do not `templates create` twice to fix variables, Dockerfiles, start commands, or healthcheck paths; prompt the user to edit the draft composer, then verify.
- Do not call `templateUpdateV2` or otherwise try to set composer variables from the CLI. Send the copy-paste kit.
- Do not ask the user to invent descriptions, PORT values, Dockerfile paths, start commands, an icon, or a healthcheck path. Paste the kit.
- Do not tell the user to set Config File in the **template composer**. That field is only on a live service. On an already-deployed one-click project, live Service Settings → Config File **does** exist (`/deploy/railway/api.toml`, …); set it and redeploy. That does not update the marketplace template.
- Do not tell the user to look for `RAILWAY_DOCKERFILE_PATH` under Settings or Source. It is a **new variable they add** (Variables → New / Add). If they cannot see it, they have not created it yet.
- Do not add a root `railway.toml` so one-click “just works”. Four GitHub services share one repo; two Dockerfiles.
- Do not set Root Directory (or `source.rootDirectory`) on api / mcp / sync / caddy. It is the build context; current Dockerfiles `COPY` from the repo root. Finding a subdirectory `Dockerfile` still breaks COPY, and the shared image `CMD` is still `sync_markets`. Leave it empty; use `RAILWAY_DOCKERFILE_PATH` instead.
- Do not ask the user to type marketplace category, card description, or overview in the dashboard. Run `templates publish` yourself.
- Dashboard “Publishing requirements”: **you** set category / description / overview / icon URL with `templates publish`. User pastes composer variables (including `RAILWAY_DOCKERFILE_PATH`) and Settings from the kit, and uploads the SVG if `--image` 404s. Five services come from `templates create` on the generated draft.
