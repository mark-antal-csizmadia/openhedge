---
name: try-hedging-examples
description: >-
  Connects Cursor to the local openhedge MCP and runs Blanket-style hedge
  example prompts. Use when the user wants to try hedging, run examples, install
  or connect MCP, or walk through search_markets / hedge / present_hedge.
---

# Try hedging examples

Walk the user through connecting MCP, then run one example hedge. Do not place trades. If the stack is not up, follow [how-to-get-started](../how-to-get-started/SKILL.md) first.

## Workflow

```
- [ ] MCP serving (`curl -sS http://localhost:8001/ready`)
- [ ] `.cursor/mcp.json` present (create if missing)
- [ ] User confirmed a green `openhedge` server in Cursor Settings
- [ ] Markets collection point count (scripts/count_markets.sh)
- [ ] User picked an example prompt
- [ ] Ran via MCP `hedge_risk` (or search → get_market → hedge → present_hedge)
```

## Install MCP

Confirm the server:

```bash
curl -sS http://localhost:8001/ready
```

If missing, create [`.cursor/mcp.json`](../../../.cursor/mcp.json):

```json
{
  "mcpServers": {
    "openhedge": {
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

Do not add a `type` field. Ask the user to reload MCP and confirm `openhedge` is green.

Use MCP tools `search_markets`, `get_market`, `hedge`, and `present_hedge`. Prefer the MCP `hedge_risk` prompt. State basis risk. If none fits, call `present_hedge` with `verdict=none`.

## Markets in Qdrant

From the repo root:

```bash
bash .agents/skills/try-hedging-examples/scripts/count_markets.sh
```

Report the count. There should be tens of thousands of markets for a meaningful search and hedging discovery. If the count is below 10,000 (empty or still filling via `sync_markets`), tell the user they can wait for ingest, or run now with degraded hedging opportunities. Do not block; proceed if they choose to run now.

## Example prompts

Source: [tryblanket.app/#examples](https://tryblanket.app/#examples). Offer these; run the one the user picks. Only Atlas publishes a first-person sentence; the rest match that voice from the case title and homepage chips.

**Sweden AI App Building Platform** (Sweden, AI compute)

> I run an AI app building platform in Stockholm, Sweden. NVIDIA H100 GPU hourly price above $2.75 could increase our inference cost by $1,000 next month.

**Berlin Sports Bar** (Germany, sports)

> I run a bar in Berlin, Germany. If the Union Berlin win a Bundesliga match, I want to fund a customer offer; the promo could cost us about $1,000.

**US Bowling Alley** (USA, electricity)

> I own a small bowling alley in Seattle, US. If electricity per kilowatt-hour exceeds $19.6, our operating costs would increase. Can I offset this risk?

**London Trucking Company** (UK, fuel)

> I run a four-truck fleet in London, UK. Diesel above 1.81 GBP per litre could cost us about £5,000 this year.
