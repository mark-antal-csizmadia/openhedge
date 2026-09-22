export const EXAMPLES = [
  {
    title: "Sweden AI App Building Platform",
    loc: "Sweden",
    chip: "AI compute",
    prompt:
      "I run an AI app building platform in Stockholm, Sweden. NVIDIA H100 GPU hourly price above $3.53 could increase our inference cost by $1,000.",
    note: "Should find a good hedge.",
    updatedAt: "2026-09-22",
    output: {
      tools: [
        { name: "search_markets", args: 'q="NVIDIA H100 GPU hourly price"' },
        { name: "search_markets", args: 'q="Price of NVIDIA H100 SXM compute by Dec 31 2026"' },
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
$295.00

Gross payout if YES
$500.00

If both happen
The business loss occurs and the contract pays.

Estimated business loss
-$1,000.00
Market payout
+$500.00
Cost today
-$295.00
Net impact
-$795.00

Book quoted 500 of 1,000 contracts ($1,000.00 target); filled 500 ($500.00 gross, coverage 0.5). Size is capped at that ask.



Still uncovered
$500.00


If the contract does not pay
The business loss does not occur; you still paid for the contracts.

Cost today
-$295.00
Net impact
-$295.00

What can differ
The contract is H100 SXM on Ornn's USD index by Dec 31, 2026, not Stockholm cloud invoices or a nearer billing window. It can close early if the index prints.`,
    },
  },
  {
    title: "Berlin Sports Bar",
    loc: "Germany",
    chip: "sports",
    prompt:
      "I run a bar in Berlin, Germany. If Bayern Munich win their women's Champions League match against Manchester City, I want to fund a customer offer; the promo could cost us about $1,000.",
    note: "Should find a good hedge.",
    updatedAt: "2026-09-22",
    output: {
      tools: [
        { name: "search_markets", args: 'q="Bayern Munich vs Manchester City Champions League"' },
        { name: "get_event", args: "event_ticker=KXUCLWGAME-26SEP22BMUMCI" },
        { name: "get_market", args: "ticker=KXUCLWGAME-26SEP22BMUMCI-BMU" },
        {
          name: "hedge",
          args: "ticker=KXUCLWGAME-26SEP22BMUMCI-BMU side=yes estimated_hit_dollars=1000",
        },
        { name: "present_hedge", args: "verdict=fit" },
      ],
      reply: `Your business risk: A Bayern Munich women's Champions League win against Manchester City could cost this bar about $1,000 in a customer offer.


YES pays if Bayern wins the Sep 22 women's Champions League match against Manchester City in 90 minutes plus stoppage, which is the promo trigger.. Filled 530.56 contracts ($530.56 gross) against the $1,000.00 you estimated (coverage 0.5306).


The relevant market(s) identified:
On Kalshi · YES outcome · Bayern - Bayern vs Manchester City, URL: https://kalshi.com/markets/KXUCLWGAME/KXUCLWGAME-26SEP22BMUMCI?op_market_ticker=KXUCLWGAME-26SEP22BMUMCI-BMU

Your estimated business loss
$1,000.00

Cost today
$238.75

Gross payout if YES
$530.56

If both happen
The business loss occurs and the contract pays.

Estimated business loss
-$1,000.00
Market payout
+$530.56
Cost today
-$238.75
Net impact
-$708.19

Book quoted 530.56 of 1,000 contracts ($1,000.00 target); filled 530.56 ($530.56 gross, coverage 0.5306). Size is capped at that ask.



Still uncovered
$469.44


If the contract does not pay
The business loss does not occur; you still paid for the contracts.

Cost today
-$238.75
Net impact
-$238.75

What can differ
This is one scheduled women's Champions League match, not any Bayern win. Extra time and penalties do not count; a tie is a separate market. The book can close early once a winner is declared.`,
    },
  },
  {
    title: "US Bowling Alley",
    loc: "USA",
    chip: "electricity",
    prompt:
      "I own a small bowling alley in Providence, Rhode Island. If electricity per kilowatt-hour exceeds 30.0¢, our operating costs would increase. Can I offset this risk?",
    note: "Should find a good hedge. Without a quantified sum of money at risk, the openhedge MCP calculates unit economics.",
    updatedAt: "2026-09-22",
    output: {
      tools: [
        {
          name: "search_markets",
          args: 'q="Rhode Island residential electricity price per kilowatt-hour"',
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
$0.37

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
      "I run a ski rental shop in Breckenridge, Colorado. If Breckenridge Ski Resort does not open before November 8, we could miss about $1,000 of early-season revenue.",
    note: "Should find a good hedge.",
    updatedAt: "2026-09-22",
    output: {
      tools: [
        { name: "search_markets", args: 'q="Breckenridge Ski Resort open"' },
        { name: "get_event", args: "event_ticker=KXBRECKOPEN-27" },
        { name: "get_market", args: "ticker=KXBRECKOPEN-27-08NOV26" },
        {
          name: "hedge",
          args: "ticker=KXBRECKOPEN-27-08NOV26 side=no estimated_hit_dollars=1000",
        },
        { name: "present_hedge", args: "verdict=fit" },
      ],
      reply: `Your business risk: If Breckenridge Ski Resort does not open before November 8, this shop could miss about $1,000 of early-season revenue.


NO pays if the resort does not run seasonal opening operations before Nov 8, 2026, which is the late-open case this shop flagged.. Filled 7 contracts ($7.00 gross) against the $1,000.00 you estimated (coverage 0.007).


The relevant market(s) identified:
On Kalshi · NO outcome · Before Nov 8, 2026 - When will Breckenridge Ski Resort open for the 26/27 winter season?, URL: https://kalshi.com/markets/KXBRECKOPEN/KXBRECKOPEN-27?op_market_ticker=KXBRECKOPEN-27-08NOV26

Your estimated business loss
$1,000.00

Cost today
$3.29

Gross payout if NO
$7.00

If both happen
The business loss occurs and the contract pays.

Estimated business loss
-$1,000.00
Market payout
+$7.00
Cost today
-$3.29
Net impact
-$996.29

Book quoted 7 of 1,000 contracts ($1,000.00 target); filled 7 ($7.00 gross, coverage 0.007). Size is capped at that ask.



Still uncovered
$993.00


If the contract does not pay
The business loss does not occur; you still paid for the contracts.

Cost today
-$3.29
Net impact
-$3.29

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
    updatedAt: "2026-09-22",
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
