export const EXAMPLES = [
  {
    title: "Sweden AI App Building Platform",
    loc: "Sweden",
    chip: "AI compute",
    prompt:
      "I run an AI app building platform in Stockholm, Sweden. NVIDIA H100 GPU hourly price above $3.53 could increase our inference cost by $1,000 next month.",
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
    note: "Should find a good hedge.",
    updatedAt: "2026-09-09",
  },
  {
    title: "London Trucking Company",
    loc: "UK",
    chip: "fuel",
    prompt:
      "I run a four-truck fleet in London, UK. Diesel above 1.81 GBP per litre could cost us about £5,000 this year.",
    note: "Should not find a good hedge as Kalshi has US diesel in dollars per gallon this week and at month-end, same-day WTI and month-end Brent strikes, and US gasoline year-highs, but those do not pay when UK fuel duty, VAT, wholesale, or sterling moves London pump prices independently of a US gallon or crude print.",
    updatedAt: "2026-09-09",
  },
] as const;
