# Vacation — Beach Week ’26

Price reconnaissance and decision support for a one-week, two-person, all-inclusive
beach trip out of Detroit (DTW). A read-only fare scout collected **106 live price
observations across 14 Caribbean destinations** (July 17, 2026 runs), scored twenty
resort options on ten criteria — including August 2026 sargassum/water-clarity
conditions — and produced the reports in `reports/`.

**Nothing here books anything.** No payment data, no passenger data, ever.

## 🌐 The trip portal

**The trip is booked: Nassau, Bahamas — Riu Palace Paradise Island, Aug 9–16, 2026.**

`docs/index.html` is the public trip guide — date-aware "Today" view, day-by-day
itinerary, flight schedule, hotel/dining guide, booking checklist, venue cards with
a schematic map. Self-contained, no build step, mobile-first, works offline once
loaded. `docs/research.html` is the FareScout decision board that picked the trip.

**The public copy is sanitized by design.** Confirmation numbers, ticket numbers,
seats, payment details, and loyalty numbers are excluded; those live only in the
private copy of the portal (not in this repo). Keep it that way — never commit the
raw trip-data JSON or any booking confirmations here.

### Publishing it with GitHub Pages

1. Merge this branch to `main`.
2. Repo **Settings → Pages → Build and deployment**: Source = *Deploy from a branch*,
   Branch = `main`, Folder = `/docs`. Save.
3. The portal goes live at `https://rlettsbubs.github.io/Vacation/` within a minute
   or two. Share that link.

To preview locally, just open `docs/index.html` in a browser.

> The repo is **public**, so the portal and everything in it is public. It contains
> only resort names, prices, and conditions research — keep it that way. No names,
> booking confirmations, flight records, or personal details belong here.

## Repo layout

```
docs/         the web portal (GitHub Pages root) + downloadable deck/scorecard
data/         FareScout.db — SQLite, every price observation (PriceCheck table)
reports/      FareScout (Aruba), VacationScout (top 10), DeepDive (14 destinations)
CLAUDE_2.md   the fare-scout methodology & guardrails
SETUP.md      one-time toolchain bootstrap (Chrome CDP + MCP)
```

## Updating the portal

Prices are quotes captured 2026-07-17 for the Aug 8–15 window; they move daily.
If dates shift, re-run the fare scout for the new week, then regenerate the price
log embedded in `docs/index.html` from `data/FareScout.db` (the JSON assigned to
`PRICE_LOG` is a straight dump of the `PriceCheck` table ordered by price).
