export const EXAMPLES = [
  {
    title: "Sweden AI App Building Platform",
    loc: "Sweden",
    chip: "AI compute",
    prompt:
      "I run an AI app building platform in Stockholm, Sweden. NVIDIA H100 GPU hourly price above $3.53 could increase our inference cost by $1,000.",
    note: "Should find a good hedge.",
    updatedAt: "2026-09-17",
    output: {
      tools: [
        { name: "search_markets", args: 'q="NVIDIA H100 GPU hourly price above $3.53"' },
        { name: "get_event", args: "event_ticker=KXH100MAX-26DEC31" },
        { name: "get_market", args: "ticker=KXH100MAX-26DEC31-3.530" },
        {
          name: "hedge",
          args: "ticker=KXH100MAX-26DEC31-3.530 side=yes estimated_hit_dollars=1000",
        },
        { name: "present_hedge", args: "verdict=fit" },
      ],
      reply: `Your business risk: NVIDIA H100 hourly price above $3.53 could increase this platform's inference cost by $1,000.


YES pays if Ornn reports H100 SXM compute per hour above the named strike by year-end 2026, which is the inference-cost jump this platform flagged.. Filled 500 contracts ($500.00 gross) against the $1,000.00 you estimated (coverage 0.5).


The relevant market(s) identified:
On Kalshi · YES outcome · Above $3.53 - Price of NVIDIA H100 SXM compute by Dec 31, 2026?, URL: https://kalshi.com/markets/KXH100MAX/KXH100MAX-26DEC31?op_market_ticker=KXH100MAX-26DEC31-3.530

Your estimated business loss
$1,000.00

Cost today
$240.00

Gross payout if YES
$500.00

If both happen
The business loss occurs and the contract pays.

Estimated business loss
-$1,000.00
Market payout
+$500.00
Cost today
-$240.00
Net impact
-$740.00

Book quoted 500 of 1,000 contracts ($1,000.00 target); filled 500 ($500.00 gross, coverage 0.5). Size is capped at that ask.



Still uncovered
$500.00


If the contract does not pay
The business loss does not occur; you still paid for the contracts.

Cost today
-$240.00
Net impact
-$240.00

What can differ
The contract is H100 SXM on Ornn's USD index by Dec 31, 2026, not Stockholm cloud invoices or a nearer billing window. It can close early if the index prints.`,
    },
  },
  {
    title: "Berlin Sports Bar",
    loc: "Germany",
    chip: "sports",
    prompt:
      "I run a bar in Berlin, Germany. If the Union Berlin win a Bundesliga match, I want to fund a customer offer; the promo could cost us about $1,000.",
    note: "Should find a good hedge.",
    updatedAt: "2026-09-17",
    output: {
      tools: [
        { name: "search_markets", args: 'q="Union Berlin win a Bundesliga match"' },
        { name: "get_event", args: "event_ticker=KXBUNDESLIGAGAME-26SEP18BMUUNI" },
        { name: "get_market", args: "ticker=KXBUNDESLIGAGAME-26SEP18BMUUNI-UNI" },
        {
          name: "hedge",
          args: "ticker=KXBUNDESLIGAGAME-26SEP18BMUUNI-UNI side=yes estimated_hit_dollars=1000",
        },
        { name: "present_hedge", args: "verdict=fit" },
      ],
      reply: `Your business risk: A Union Berlin Bundesliga win could cost this bar about $1,000 in a customer offer.


YES pays if Union Berlin wins the Sep 18 Bundesliga match against Bayern Munich in 90 minutes plus stoppage, which is the promo trigger., covering the $1,000.00 you estimated with 1,000 contracts.


The relevant market(s) identified:
On Kalshi · YES outcome · Union Berlin - Bayern Munich vs Union Berlin, URL: https://kalshi.com/markets/KXBUNDESLIGAGAME/KXBUNDESLIGAGAME-26SEP18BMUUNI?op_market_ticker=KXBUNDESLIGAGAME-26SEP18BMUUNI-UNI

Your estimated business loss
$1,000.00

Cost today
$30.00

Gross payout if YES
$1,000.00

If both happen
The business loss occurs and the contract pays.

Estimated business loss
-$1,000.00
Market payout
+$1,000.00
Cost today
-$30.00
Net impact
-$30.00



If the contract does not pay
The business loss does not occur; you still paid for the contracts.

Cost today
-$30.00
Net impact
-$30.00

What can differ
This is one scheduled match, not any Union Berlin win. Extra time and penalties do not count; a tie is a separate market. The book can close early once a winner is declared.`,
    },
  },
  {
    title: "US Bowling Alley",
    loc: "USA",
    chip: "electricity",
    prompt:
      "I own a small bowling alley in Providence, Rhode Island. If electricity per kilowatt-hour exceeds 30.0¢, our operating costs would increase. Can I offset this risk?",
    note: "Should find a good hedge. Without a quantified sum of money at risk, the openhedge MCP calculates unit economics.",
    updatedAt: "2026-09-17",
    output: {
      tools: [
        {
          name: "search_markets",
          args: 'q="Rhode Island residential electricity price per kilowatt-hour exceeds 30.0 cents"',
        },
        { name: "get_event", args: "event_ticker=KXRIRESPOWER-27FEB28" },
        { name: "get_market", args: "ticker=KXRIRESPOWER-27FEB28-T30.0" },
        { name: "hedge", args: "ticker=KXRIRESPOWER-27FEB28-T30.0 side=yes" },
        { name: "present_hedge", args: "verdict=fit" },
      ],
      reply: `Your business risk: Rhode Island electricity above 30.0¢ per kilowatt-hour would raise this bowling alley's operating costs.


YES pays if EIA's 2026 Rhode Island average residential cents per kWh prints above the named strike.

The relevant market(s) identified:
On Kalshi · YES outcome · Above 30.0¢/kWh - Rhode Island average residential electricity price in 2026, URL: https://kalshi.com/markets/KXRIRESPOWER/KXRIRESPOWER-27FEB28?op_market_ticker=KXRIRESPOWER-27FEB28-T30.0

Cost today
$0.44

Gross payout if YES
$1.00 (unit $1.00 payout)

What can differ
EIA statewide residential average is a proxy for a Providence bowling alley's commercial tariff, and the print is calendar-year 2026, not the next utility bill.`,
    },
  },
  {
    title: "Breckenridge Ski Shop",
    loc: "USA",
    chip: "weather",
    prompt:
      "I run a ski rental shop in Breckenridge, Colorado. If Breckenridge Ski Resort does not open before November 15, we could miss about $1,000 of early-season revenue.",
    note: "Should find a good hedge.",
    updatedAt: "2026-09-17",
    output: {
      tools: [
        { name: "search_markets", args: 'q="Breckenridge Ski Resort open before November 15"' },
        { name: "get_event", args: "event_ticker=KXBRECKOPEN-27" },
        { name: "get_market", args: "ticker=KXBRECKOPEN-27-15NOV26" },
        {
          name: "hedge",
          args: "ticker=KXBRECKOPEN-27-15NOV26 side=no estimated_hit_dollars=1000",
        },
        { name: "present_hedge", args: "verdict=fit" },
      ],
      reply: `Your business risk: If Breckenridge Ski Resort does not open before November 15, this shop could miss about $1,000 of early-season revenue.


NO pays if the resort does not run seasonal opening operations before Nov 15, 2026, which is the late-open case this shop flagged.. Filled 55.39 contracts ($55.39 gross) against the $1,000.00 you estimated (coverage 0.0554).


The relevant market(s) identified:
On Kalshi · NO outcome · Before Nov 15, 2026 - When will Breckenridge Ski Resort open for the 26/27 winter season?, URL: https://kalshi.com/markets/KXBRECKOPEN/KXBRECKOPEN-27?op_market_ticker=KXBRECKOPEN-27-15NOV26

Your estimated business loss
$1,000.00

Cost today
$6.09

Gross payout if NO
$55.39

If both happen
The business loss occurs and the contract pays.

Estimated business loss
-$1,000.00
Market payout
+$55.39
Cost today
-$6.09
Net impact
-$950.70

Book quoted 55.39 of 1,000 contracts ($1,000.00 target); filled 55.39 ($55.39 gross, coverage 0.0554). Size is capped at that ask.



Still uncovered
$944.61


If the contract does not pay
The business loss does not occur; you still paid for the contracts.

Cost today
-$6.09
Net impact
-$6.09

What can differ
Opening is defined as a public passenger lift for downhill skiing, not a projected date. Season-passholder access can count; preview or employee days do not. Size is capped at the quoted NO ask.`,
    },
  },
  {
    title: "London Bookshop",
    loc: "UK",
    chip: "flood",
    prompt:
      "I run a bookshop by the Thames in London, UK. If the street floods, we could lose about £5,000 in stock and closed days.",
    note: "Should not find a good hedge as Kalshi has US city rainfall but not UK.",
    updatedAt: "2026-09-17",
    output: {
      tools: [
        { name: "search_markets", args: 'q="London Thames flood street flooding UK rainfall"' },
        { name: "search_markets", args: 'q="UK flood Thames London rainfall"' },
        { name: "present_hedge", args: "verdict=none" },
      ],
      reply: `Your business risk: A Thames-side flood could cost this London bookshop about £5,000 in stock and closed days.


No market found — no hedge.

Kalshi lists US city rainfall contracts (NYC, Los Angeles) but not UK rainfall, Thames flooding, or London street flooding. Those US prints do not map to this shop's exposure.`,
    },
  },
] as const;
