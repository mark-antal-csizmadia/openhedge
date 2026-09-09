export const EXAMPLES = [
  {
    title: "Sweden AI App Building Platform",
    loc: "Sweden",
    chip: "AI compute",
    prompt:
      "I run an AI app building platform in Stockholm, Sweden. NVIDIA H100 GPU hourly price above $3.53 could increase our inference cost by $1,000.",
    note: "Should find a good hedge.",
    updatedAt: "2026-09-09",
  },
  {
    title: "Berlin Sports Bar",
    loc: "Germany",
    chip: "sports",
    prompt:
      "I run a bar in Berlin, Germany. If the Union Berlin win a Bundesliga match, I want to fund a customer offer; the promo could cost us about $1,000.",
    note: "Should find a good hedge.",
    updatedAt: "2026-09-09",
  },
  {
    title: "US Bowling Alley",
    loc: "USA",
    chip: "electricity",
    prompt:
      "I own a small bowling alley in Providence, Rhode Island. If electricity per kilowatt-hour exceeds 30.0¢, our operating costs would increase. Can I offset this risk?",
    note: "Should find a good hedge. Without a quantified sum of money at risk, the openhedge MCP calculates unit economics.",
    updatedAt: "2026-09-09",
  },
  {
    title: "Breckenridge Ski Shop",
    loc: "USA",
    chip: "weather",
    prompt:
      "I run a ski rental shop in Breckenridge, Colorado. If Breckenridge Ski Resort does not open before November 8, we could miss about $1,000 of early-season revenue.",
    note: "Should find a good hedge.",
    updatedAt: "2026-09-09",
  },
  {
    title: "London Bookshop",
    loc: "UK",
    chip: "flood",
    prompt:
      "I run a bookshop by the Thames in London, UK. If the street floods, we could lose about £5,000 in stock and closed days.",
    note: "Should not find a good hedge as Kalshi has US city rainfall but not UK.",
    updatedAt: "2026-09-09",
  },
] as const;
