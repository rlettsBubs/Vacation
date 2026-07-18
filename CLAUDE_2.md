# CLAUDE.md — 014 fare-scout

Live travel-price reconnaissance using Claude Code driving a real Chrome instance.
Read-only price collection. **This repo NEVER books, never enters payment or passenger
data, never clicks past a checkout gate. Hard rule, no exceptions, no phase unlocks it.**

## Mission

Collect real, current prices for the Aruba trip (and future trips) directly from
booking sites using the operator's own Chrome browser, store every observation in
SQLite, and produce a GREEN/AMBER/RED comparison report so the operator can book
manually with confidence.

Human-in-the-loop by design: Claude drives navigation and extraction; the operator
(Richard) handles logins, captchas, and any bot-challenge friction, and makes all
booking decisions himself.

## DECISION MODE (since 2026-07-18) — this supersedes survey mode

A decision has been made. The repo no longer surveys the Caribbean; it
monitors one decision until it is booked (see REFACTOR_LOG.md).

| Role | Property | Trip | Baseline |
|---|---|---|---|
| **PRIMARY** | Secrets Aura Cozumel (adults-only 5★) | SCOUT-CZM | **$3,568** CheapCaribbean pkg ($200 Jet Set July promo) |
| BACKUP | Dreams Cozumel Cape | SCOUT-CZM | $3,396 |
| BUDGET | Riu Latino, Costa Mujeres (adults-only) | SCOUT-CUN | $2,412 |
| HEDGE | Riu Palace Aruba / Riu Palace Antillas (fully refundable) · Barceló Aruba | ARUBA-001 | $5,972 / $6,924 / $6,968 |

- Dates unchanged: Sat 2026-08-08 → Sat 2026-08-15, 2 adults, all-inclusive, DTW.
- **Active trips: exactly 3** — ARUBA-001, SCOUT-CZM, SCOUT-CUN (`TripConfig.Active`).
  All other SCOUT-* trips are Active=0; their history is preserved, never deleted.
- **Decision deadline: 2026-07-24.** Record the booking with
  `python3 -m farescout book <TripId> -m "note"` or the deadline alert fires.

### Alert rules (run after every scrape cycle: `python3 -m farescout alerts`)

1. Aura Cozumel package moves ±$150 from last observation
2. Any DTW-CZM nonstop appears
3. Cozumel West worse than LIGHT on 2 consecutive checks
4. Palm Beach Aruba worse than LIGHT
5. Riu Aruba packages lose the refundable flag or rise >$300
6. 2026-07-24 reached with no booking recorded

### Condition monitoring

Daily `python3 -m farescout conditions` scrapes howisthesargassum.com
per-beach status (Cozumel West, Playa Mujeres, Palm Beach Aruba) into
`ConditionCheck` (CLEAR/LIGHT/MODERATE/HEAVY; ambiguous maps to the worse
status; unparseable inserts MODERATE with a PARSE_FAIL note — never skips).
JS-rendered pages go through the Chrome automation path, not plain fetch.

### Status view

`python3 -m farescout status` — latest price per tracked property with delta,
latest beach conditions with 7-day trend, days to deadline, open alerts, and a
GREEN/AMBER/RED summary (GREEN = Cozumel LIGHT-or-better AND Aura within $150
of baseline; AMBER = one degraded; RED = both, or deadline passed unbooked).

## Original survey-mode target (superseded, kept for context)

| Parameter | Value |
|---|---|
| Route | DTW → AUA, round trip, 2 adults |
| Depart | Sat 2026-08-08 |
| Return | Sat 2026-08-15 (7 nights) — also check Sun 08-16 (8 nights) |
| Resorts | Riu Palace Aruba · Riu Palace Antillas (adults-only) · Barceló Aruba |
| Room basis | All-inclusive, 2 adults, 1 room, entry ocean-facing category where offered |

### Price baselines (research 2026-07-17 — thresholds for status colors)

| Item | GREEN (jump on it) | AMBER (fair) | RED (wait/overpriced) |
|---|---|---|---|
| Flight RT per person, 1-stop | < $450 | $450–650 | > $650 |
| Riu Palace Aruba, 7nt/2ppl AI | < $3,700 | $3,700–4,600 | > $4,600 |
| Riu Palace Antillas, 7nt/2ppl AI | < $3,200 | $3,200–4,200 | > $4,200 |
| Barceló Aruba, 7nt/2ppl AI | < $2,500 | $2,500–3,500 | > $3,500 |
| Package (flight+hotel, 2ppl, Riu tier) | < $4,100 | $4,100–5,300 | > $5,300 |

Known context: no DTW–AUA nonstop until 2026-12-19 (Delta winter seasonal).
All August itineraries are 1-stop; prefer ATL or JFK connections over FLL when
prices are within ~$75.

## Sources (decision-mode scope; check in this order)

1. **CheapCaribbean** — packages for all six tracked properties (primary price signal).
2. **Google Flights** — DTW-CZM (nonstop watch) and DTW-AUA.
3. **Riu.com packages** (packagesus.riu.com) — both Riu Aruba properties (refundable hedge).
4. **Kayak / Expedia** — hotel-only cross-check, the three Aruba properties only.
5. **howisthesargassum.com** — daily beach conditions (see Condition monitoring).
6. **Phase 2b channels** (`python3 -m farescout channels`): Apple Vacations and
   Funjet packages for Secrets Aura Cozumel + Dreams Cozumel Cape; Hyatt
   Inclusive Collection direct rate for Aura (hotel-only — paired with the
   current Google Flights low and stored in RawNotes as `SYNTH_TOTAL: <amt>`,
   never in TotalPrice); riu.com direct for Riu Latino. Any channel that beats
   CheapCaribbean by >$100 on the same property/dates fires a `CHANNEL_BEAT`
   alert. Sites that block automation are SKIP-logged after 3 attempts — never
   fight captchas.
7. **Costco Travel** — MANUAL weekly check (login wall, ToS forbids
   automation). The status view surfaces a reminder every Monday.

The scrape cycle plans work for Active trips only — `python3 -m farescout scrape --dry-run` shows the 22-step cycle.

Record every price seen, even off-target dates — history is the point.

## Toolchain

- Claude Code on Windows desktop, this repo at `C:\014 fare-scout`
- **chrome-devtools-mcp** attached to a real Chrome instance over CDP (see SETUP.md).
  Real Chrome + persistent profile = real fingerprint and cookies; dramatically
  fewer bot walls than headless Chromium.
- Python 3.11+ for the SQLite layer and report generation
- SQLite DB at `data\FareScout.db` (PascalCase schema, consistent with 003/012 conventions)

## Schema

```sql
CREATE TABLE IF NOT EXISTS PriceCheck (
    CheckId         INTEGER PRIMARY KEY AUTOINCREMENT,
    CheckedAt       TEXT NOT NULL,            -- ISO 8601 local
    TripId          TEXT NOT NULL,            -- 'ARUBA-001'
    Source          TEXT NOT NULL,            -- GoogleFlights | Riu | CheapCaribbean | Expedia | Kayak
    Kind            TEXT NOT NULL,            -- Flight | Hotel | Package
    Carrier         TEXT,                     -- flights only
    RouteOrResort   TEXT NOT NULL,            -- 'DTW-AUA' or resort name
    DepartDate      TEXT NOT NULL,
    ReturnDate      TEXT,
    Stops           INTEGER,                  -- flights only
    ConnectionAirport TEXT,                   -- flights only
    RoomType        TEXT,                     -- hotel/package only
    Occupancy       TEXT DEFAULT '2 adults',
    TotalPrice      REAL NOT NULL,            -- USD, all-in as displayed
    PerPerson       REAL,
    PromoNotes      TEXT,                     -- e.g. '$590 resort credit'
    SourceUrl       TEXT,
    Status          TEXT,                     -- GREEN | AMBER | RED (vs baselines above)
    RawNotes        TEXT
);
```

## Phases — each ends at a STOP gate. Do not proceed without operator "GO".

### Phase 0 — Environment verification
1. Confirm chrome-devtools-mcp is connected: list open tabs.
2. Create `data\FareScout.db`, apply schema, insert a test row, read it back, delete it.
3. Print a one-line GREEN/RED status for: CDP connection, DB, Python env.
**STOP. Report status. Wait for GO.**

### Phase 1 — Flights (Google Flights)
1. Navigate to Google Flights, DTW→AUA, 2026-08-08 → 08-15, 2 adults.
2. Extract: top 5 itineraries (carrier, price, stops, connection, duration) and
   Google's price-insight banding (low/typical/high) if shown.
3. Repeat for the 08-08 → 08-16 variant.
4. Write all rows to PriceCheck with Status computed from baselines.
5. If any page throws a captcha or consent wall: pause, tell the operator exactly
   what to click, wait, then resume. Never attempt to bypass.
**STOP. Show flight summary table. Wait for GO.**

### Phase 2 — Packages and hotels
1. Riu.com package search: both Riu properties, same dates, 2 adults, from DTW.
2. CheapCaribbean: Antillas package; record promo/resort-credit terms in PromoNotes.
3. Expedia: package and hotel-only for all three resorts.
4. Kayak: hotel-only nightly cross-check.
5. Same captcha protocol as Phase 1. Operator may need to complete a login once;
   the profile persists it for future runs.
**STOP. Show package summary. Wait for GO.**

### Phase 3 — Report
1. Generate `reports\FareScout_<date>.md`: comparison table (all sources × all
   targets), Status colors, cheapest viable path highlighted, deltas vs prior runs
   once ≥2 runs exist.
2. Print the booking recommendation as: what to book, where, and why — but take
   no booking action.
**STOP. End of run.**

### Phase 4 (later, separate GO) — Repeatability
- Wrap Phases 1–3 as a single "run" command the operator can trigger daily.
- Trend deltas per source; flag any price that dropped ≥5% since last run.
- ~~(Future) surface PriceCheck history to the trip portal as its data layer.~~
  Done: `python3 scripts/build_portal.py` regenerates `docs/index.html` from the DB.

## Standing rules

- READ-ONLY. No booking, no payment fields, no passenger data, ever.
- Never store credentials in this repo. Logins live only in the Chrome profile.
- Respect the sites: human-paced navigation, no rapid-fire loops, no parallel
  scraping, back off immediately if blocked. This is one user checking prices,
  not a crawler.
- Every price observed gets a PriceCheck row — no exceptions, even failures
  (log with TotalPrice of the displayed value or a RawNotes failure entry).
- Prices are quotes, not offers. Always tell the operator the displayed price can
  change at checkout.
- If a site hard-blocks the automated session, record it and move to the next
  source. Do not fight bot detection.
