---
name: update-hedging-examples
description: >-
  Refreshes Blanket-style hedging example prompts, updatedAt dates, and landing
  MCP output transcripts from the live openhedge MCP catalog. Use when example
  strikes are stale or expired, the landing or README copy no longer finds a
  fit, or the user asks to update the hedging examples.
---

# Update hedging examples

Rewrite the example prompts from the live catalog so a visitor still has a nearby strike (or an honest none). Recapture each touched example’s MCP tool trace and `present_hedge` markdown for the landing page. Do not place trades. Do not add YAML or a refresh script. This skill does not walk the user through a live demo; that is [try-hedging-examples](../try-hedging-examples/SKILL.md).

## Workflow

```
- [ ] Openhedge MCP connected (prefer hosted)
- [ ] Searched each example; read rules via get_market
- [ ] Picked strikes (or honest none) per policy below
- [ ] Ran hedge / present_hedge for each touched example; wrote output on examples.ts
- [ ] Wrote identical prompt, note, and updatedAt on all three surfaces
- [ ] One commit (copy + dates + landing outputs); do not push unless asked
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

Walk `search_markets` → `get_event` when hits share an `event_ticker` (strike ladder) → `get_market` on shortlisted tickers (read `description`, `end_datetime`, `can_close_early`). For each example you touch, finish the run: call `hedge` once per kept fit ticker, then `present_hedge` (`verdict=fit` with the unmodified hedge payload, or `verdict=none` with no candidate). Do not put tickers or URLs in public prompts; they belong in `output` only.

## Surfaces

Prompt text must match character-for-character across all three. Notes and `updatedAt` must match too.

1. [`web/lib/examples.ts`](../../../web/lib/examples.ts) — `prompt`, `note`, `updatedAt` on each object in `EXAMPLES`
2. [`README.md`](../../../README.md) — block quotes, notes, and `Updated YYYY-MM-DD.` lines under **Try hedging examples**
3. [`.agents/skills/try-hedging-examples/SKILL.md`](../try-hedging-examples/SKILL.md) — the same block quotes, notes, and `Updated YYYY-MM-DD.` lines under **Example prompts**

`output` is **landing-only** (`examples.ts`). Do not copy the transcript into README or the try-hedging skill.

Do not change titles, `loc`, `chip`, or the first-person Blanket voice. Only the numeric threshold in the sentence, the verdict note, `updatedAt`, and `output` change.

Landing cards read `updatedAt` from `examples.ts` via [`web/components/example-prompts.tsx`](../../../web/components/example-prompts.tsx). Do not restyle that line; keep `Updated {updatedAt}`.

## Timestamp

When you touch an example, set `updatedAt` to **today’s UTC date** as `YYYY-MM-DD` on all three copies of that example.

- `examples.ts`: `updatedAt: "YYYY-MM-DD"`
- README and try-hedging skill: a line `Updated YYYY-MM-DD.` after the note

Untouched examples keep their old date **and** their old `output`. Fit notes stay `Should find a good hedge.` (no “as of”), except **US Bowling Alley**, which keeps the unit-economics sentence because that prompt names no dollar hit. **London Bookshop** keeps a why-none note with no date inside the note.

## Landing `output`

Whenever you touch an example, rewrite `output` on that object in `examples.ts`, even if the prompt strike is unchanged (prices and sizes move).

```ts
output: {
  tools: [{ name: "search_markets", args: 'q="…"' }],
  reply: "…verbatim present_hedge markdown…",
}
```

- `tools`: every MCP tool you actually called, in order. Compact `args` only (`q`, `event_ticker`, `ticker`, `side`, `estimated_hit_dollars`, `verdict`). Do not dump search JSON or full market records.
- `reply`: the unmodified `present_hedge` `markdown` field. Tickers and Kalshi URLs belong here.

**US Bowling Alley** omits `estimated_hit_dollars` on `hedge` (unit economics). **London Bookshop** is `verdict=none` (search, then `present_hedge` with no candidate; do not call `hedge`). A late Breckenridge opening is `side=no` on “before {date}”.

## Strike policy

**Sweden AI App Building Platform**, **Berlin Sports Bar**, **US Bowling Alley**, **Breckenridge Ski Shop** — expected **fit**.

- Search the same exposure (H100 hourly compute, a Champions League match, Rhode Island residential kWh, Breckenridge ski resort opening). Keep the bar in Berlin, the bowling alley in Providence, and the ski shop in Breckenridge; only rewrite the ¢ strike, the Champions League team and opponent, or the November open-by date.
- Prefer an open market whose `end_datetime` is still useful (not a leftover print in a few days), YES ask not pinned near 0 or 1, and `yes_ask_size` > 0.
- Rewrite only the threshold already in the sentence (H100 hourly price, Champions League team and opponent, kWh, Breckenridge open-by date). Keep hit dollars (`$1,000`) on Sweden, Berlin, and Breckenridge unless the user asks otherwise. Do not add a dollar hit to the bowling alley prompt. Berlin stays one open match, not a season-long winner. A late opening is a NO on “before {date}”.
- Sweden’s cost line stays `could increase our inference cost by $1,000` with no time window (`next month`, `this year`).
- If nothing maps cleanly, do not invent a strike. Change the note to say no live strike, still bump `updatedAt`, and store a `verdict=none` `output`.

**London Bookshop** — expected **none**.

- Do not promote US city rainfall into a UK flood fit.
- Re-run search and keep the why-none note brief: Kalshi has US city rainfall but not UK, unless a real UK rainfall or flood contract appears.
- Keep the bookshop by the Thames unless a real UK flood or Thames contract appears.

## Commit

After a successful refresh, create **one** commit with only these copy/date/output files. Message focuses on why (live catalog, expired strikes). Do not push unless asked.

`web/` may auto-deploy [openhedge.app](https://openhedge.app) if the landing Railway project tracks `main`. Do not follow [how-to-deploy-landing](../how-to-deploy-landing/SKILL.md) unless the user asks.
