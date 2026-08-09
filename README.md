# Vacation — Beach Week ’26

Price reconnaissance and decision support for a one-week, two-person, all-inclusive
beach trip out of Detroit (DTW). A read-only fare scout collected **106 live price
observations across 14 Caribbean destinations** (July 17, 2026 runs), scored twenty
resort options on ten criteria — including August 2026 sargassum/water-clarity
conditions — and produced the reports in `reports/`.

**Nothing here books anything.** No payment data, no passenger data, ever.

## 🌐 The trip portal

`docs/index.html` is a self-contained, shareable web portal built from this data:
the shortlist, price comparison, water report, the full 20-option ranking, and the
complete price log. It has no build step and no external dependencies — one HTML file.

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
