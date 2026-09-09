---
name: update-hedging-examples
description: >-
  Refreshes Blanket-style hedging example prompts and updatedAt dates from the
  live openhedge MCP catalog. Use when example strikes are stale or expired, the
  landing or README copy no longer finds a fit, or the user asks to update the
  hedging examples.
---

# Update hedging examples

Rewrite the example prompts from the live catalog so a visitor still has a nearby strike (or an honest none). Do not place trades. Do not add YAML or a refresh script. This skill does not run a demo hedge for the user; that is [try-hedging-examples](../try-hedging-examples/SKILL.md).

## Workflow

```
- [ ] Openhedge MCP connected (prefer hosted)
- [ ] Searched each example; read rules via get_market
- [ ] Picked strikes (or honest none) per policy below
- [ ] Wrote identical prompt, note, and updatedAt on all three surfaces
- [ ] One commit (copy + dates only); do not push unless asked
```

## MCP

Do not require a local stack. Use the openhedge MCP already connected in Cursor. If none is connected, ask the user to add:

```json
{
  "mcpServers": {
    "openhedge": {
      "url": "https://mcp.openhedge.app/mcp"
    }
  }
}
```

Do not add a `type` field. Prefer that hosted URL over localhost unless the user already has a filled local catalog.

Walk `search_markets` → `get_event` when hits share an `event_ticker` (strike ladder) → `get_market` on shortlisted tickers (read `description`, `end_datetime`, `can_close_early`). Optionally call `hedge` once per kept fit ticker to confirm it sizes. Do not call `present_hedge` unless the user also asked to run the demo. Do not put tickers or URLs in public prompts.

## Surfaces (must stay identical)

Prompt text must match character-for-character across all three. Notes and `updatedAt` must match too.

1. [`web/lib/examples.ts`](../../../web/lib/examples.ts) — `prompt`, `note`, `updatedAt` on each object in `EXAMPLES`
2. [`README.md`](../../../README.md) — block quotes, notes, and `Updated YYYY-MM-DD.` lines under **Try hedging examples**
3. [`.agents/skills/try-hedging-examples/SKILL.md`](../try-hedging-examples/SKILL.md) — the same block quotes, notes, and `Updated YYYY-MM-DD.` lines under **Example prompts**

Do not change titles, `loc`, `chip`, or the first-person Blanket voice. Only the numeric threshold in the sentence, the verdict note, and `updatedAt` change.

Landing cards read `updatedAt` from `examples.ts` via [`web/components/example-prompts.tsx`](../../../web/components/example-prompts.tsx). Do not restyle that line; keep `Updated {updatedAt}`.

## Timestamp

When you touch an example, set `updatedAt` to **today’s UTC date** as `YYYY-MM-DD` on all three copies of that example.

- `examples.ts`: `updatedAt: "YYYY-MM-DD"`
- README and try-hedging skill: a line `Updated YYYY-MM-DD.` after the note

Untouched examples keep their old date. Fit notes stay `Should find a good hedge.` (no “as of”). London keeps a why-none note with no date inside the note.

## Strike policy

**Sweden AI App Building Platform**, **Berlin Sports Bar**, **US Bowling Alley**, **Breckenridge Ski Shop** — expected **fit**.

- Search the same exposure (H100 hourly compute, Union Berlin match, Rhode Island residential kWh, Breckenridge ski resort opening). Keep the bowling alley in Providence and the ski shop in Breckenridge; only rewrite the ¢ strike or the November open-by date.
- Prefer an open market whose `end_datetime` is still useful (not a leftover print in a few days), YES ask not pinned near 0 or 1, and `yes_ask_size` > 0.
- Rewrite only the threshold already in the sentence (H100 hourly price, Union Berlin, kWh, Breckenridge open-by date). Keep hit dollars (`$1,000`) unless the user asks otherwise. A late opening is a NO on “before {date}”.
- If nothing maps cleanly, do not invent a strike. Change the note to say no live strike, still bump `updatedAt`.

**London Trucking Company** — expected **none**.

- Do not promote Brent, WTI, or US diesel ($/gallon) into a fit.
- Re-run search and rewrite the why-none note from today’s nearest neighbors (what exists and why it still does not pay a UK pump bill).
- Leave `1.81 GBP` unless a real UK-litre contract appears.

## Commit

After a successful refresh, create **one** commit with only these copy/date files. Message focuses on why (live catalog, expired strikes). Do not push unless asked.

`web/` may auto-deploy [openhedge.app](https://openhedge.app) if the landing Railway project tracks `main`. Do not follow [how-to-deploy-landing](../how-to-deploy-landing/SKILL.md) unless the user asks.
