# FareScout Report — ARUBA-001 — 2026-07-17 (evening run)

**Trip:** DTW → AUA, 2 adults, all-inclusive, Sat 2026-08-08 → Sat 2026-08-15 (7 nights; 08-16 variant also checked for flights)
**Run:** 21 price observations across Google Flights, Riu.com, CheapCaribbean, Expedia, Kayak. All prices USD, 2 adults, as displayed. Prices are quotes, not offers — they can change at checkout.

## Verdict: 🔴 RED across the board — do not book tonight

Google Flights' own banding says August DTW–AUA prices are **currently high**, and every hotel/package observation landed above your RED thresholds. This is the first run; the value of this DB is deltas, so run it again morning + evening for a few days.

## Flights (Google Flights, round trip, 2 adults total)

| Itinerary | Carrier | Connection | Total (2 adults) | Per person | Status |
|---|---|---|---|---|---|
| Aug 8–15, 6h40m | Delta | ATL (52m) | **$1,842** | $921 | 🔴 RED |
| Aug 8–15, 6h44m | American | CLT (37m) | $1,862 | $931 | 🔴 RED |
| Aug 8–15, 6h50m | Delta | ATL (44m) | $2,042 | $1,021 | 🔴 RED |
| Aug 8–15, 9h10m | JetBlue | BOS (2h24m) | $2,094 | $1,047 | 🔴 RED |
| Aug 8–15, 6h40m | United | IAD (41m) | $2,730 | $1,365 | 🔴 RED |
| Aug 8–16, 6h44m | American | CLT (37m) | **$1,872** | $936 | 🔴 RED |
| Aug 8–16, 6h40m | Delta | ATL (52m) | $2,160 | $1,080 | 🔴 RED |
| Aug 8–16 (others) | Southwest/JetBlue | 2-stop / BOS / FLL | $2,211–2,432 | $1,106–1,216 | 🔴 RED |

- Your AMBER ceiling is $650/pp; the best seen is $921/pp. The extra night (8/16 return) adds ~$30 to flights.
- **Google's date tip: Aug 5–13 flies for $1,140 total** (~$570/pp = AMBER) — worth considering if the resorts allow it.

## Packages — flight + hotel, 2 adults, 7 nights

| Resort | Riu.com direct | CheapCaribbean | Status vs $4,100/$5,300 |
|---|---|---|---|
| Riu Palace Aruba | $6,034 ("100% off flights", refundable) | **$5,972** ($200 promo applied) | 🔴 RED |
| Riu Palace Antillas (adults-only) | $7,213 | $6,924 | 🔴 RED |
| Barceló Aruba | — | $6,968 | 🔴 RED |

## Hotel-only, 2 adults, 7 nights

| Resort | Expedia total (w/ taxes) | Kayak nightly cross-check | Status |
|---|---|---|---|
| Riu Palace Aruba | $5,560 ("was $9,250") | $703/nt AI (low: $620 Pricetravel) ≈ $4,921/wk pre-tax | 🔴 RED |
| Riu Palace Antillas | $6,537 ("was $11,866") | $826/nt (low: $693 Super.com) ≈ $5,782/wk pre-tax | 🔴 RED |
| Barceló Aruba | $5,999 ("was $9,216") | **$620/nt booking DIRECT at Barcelo.com** ≈ $4,340/wk pre-tax | 🔴 RED |

## Cheapest viable paths (if you had to book today)

1. **CheapCaribbean — Riu Palace Aruba package: $5,972** ($2,986/pp, flights + AI hotel + taxes). Cheapest complete trip observed. $62 under Riu direct, but Riu direct is *fully refundable* — worth $62 if you want the hedge.
2. Riu.com direct — same resort, $6,034, fully refundable.
3. DIY Barceló: $620/nt direct ($4,340) + $1,842 Delta = ~$6,180+tax — does **not** beat the Riu package.

## Recommendation (no booking action taken)

**WAIT.** Everything is RED and Google explicitly flags prices as high. Specifically:
- Track daily: the CheapCaribbean Riu Palace Aruba package is the number to watch — it needs to drop below ~$5,300 to go AMBER, ~$4,100 for GREEN.
- If the packages don't move within ~5–7 runs, the decision becomes "pay ~$5,972 or shift dates."
- **Date flexibility is the biggest lever found:** Aug 5–13 flights at $1,140 vs $1,842. If the Riu is bookable Wed→Wed those dates, the whole trip could drop ~$700.
- Antillas (adults-only) carries a consistent ~$950–1,200 premium over Palace Aruba across every source this run.

## Run notes

- Expedia *package* pricing not captured this run (session-side renderer instability, not a site block; hotel-only captured fine). Next run should retry, or use the manual-capture fallback.
- No captchas or bot walls hit on any source. One stray Booking.com comparison tab spawned by Kayak — ignored, not a listed source.
- All 21 observations in `data\FareScout.db` → `PriceCheck` (CheckIds 1–21, TripId ARUBA-001).
