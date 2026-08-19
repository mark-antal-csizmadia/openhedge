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
- [ ] railway templates create; mark OPENROUTER_API_KEY required; publish
- [ ] Put TEMPLATE_CODE in the README Deploy button
```

## Prerequisites

- Railway CLI linked to the GitHub-sourced project from [how-to-deploy-to-railway](../how-to-deploy-to-railway/SKILL.md)
- Public HTTP only on **caddy**
- Qdrant is the Docker image `qdrant/qdrant:v1.19.0` with no API key

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

- Do not generate from a project that has `cloudflared` or other extra services.
- Do not use `railway deploy --template i1tz3T` or a Caddy marketplace template as a nested source.
- Do not `railway up`. Sources must be GitHub or a Docker image.
- Do not set `QDRANT_API_KEY` or `QDRANT__SERVICE__API_KEY` on the template.
- Do not attach a Railway public domain to `mcp` or `Qdrant`.
