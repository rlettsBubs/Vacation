#!/usr/bin/env python3
"""Build the shareable trip portal from data/FareScout.db.

Reads every PriceCheck row, embeds it as JSON, and writes a fully
self-contained static page (no external assets, works offline):

    docs/index.html          — standalone page (open locally / GitHub Pages)
    docs/portal-fragment.html — same content without the <html>/<head>/<body>
                                skeleton, for hosts that wrap it themselves

Curated content (rankings, water-clarity scores, conditions research) comes
from reports/DeepDive_2026-07-17.md and reports/VacationScout_2026-07-17.md.
Re-run after each FareScout run: python3 scripts/build_portal.py
"""

import html
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "FareScout.db"
OUT_DIR = ROOT / "docs"

DESTINATIONS = {
    "ARUBA-001": "Aruba",
    "SCOUT-CUN": "Cancún / Riviera Maya",
    "SCOUT-PUJ": "Punta Cana",
    "SCOUT-CZM": "Cozumel",
    "SCOUT-MBJ": "Jamaica",
    "SCOUT-NAS": "Bahamas",
    "SCOUT-CUR": "Curaçao",
    "SCOUT-PLS": "Turks & Caicos",
    "SCOUT-GCM": "Grand Cayman",
    "SCOUT-SXM": "St. Maarten",
    "SCOUT-ANU": "Antigua",
    "SCOUT-UVF": "St. Lucia",
    "SCOUT-BGI": "Barbados",
    "SCOUT-SJU": "Puerto Rico",
}

# Final ranking v2 (DeepDive 2026-07-17): score out of 10 across 10 criteria.
# db_name matches PriceCheck.RouteOrResort so the board always shows the
# latest observed price. clarity = expected August water clarity 0-10 from
# the sargassum research; None = not scored in the research.
RANKING = [
    dict(rank=1,  name="Riu Latino",                 db="Riu Latino - AI - Adults Only",                  where="Costa Mujeres, Mexico",  ao=True,  stars="4.5★", score=7.90, clarity=7.5,  note="Cheapest adults-only anywhere; new resort (2024); 3h45m nonstop"),
    dict(rank=2,  name="Secrets Aura Cozumel",       db="Secrets Aura Cozumel - AI - Adults Only",        where="Cozumel west coast",     ao=True,  stars="5★",   score=7.45, clarity=9.0,  note="Swim-out suites; the island physically blocks the seaweed"),
    dict(rank=3,  name="Secrets The Vine",           db="Secrets The Vine - AI - Adults Only",            where="Cancún Hotel Zone",      ao=True,  stars="5★",   score=7.34, clarity=5.0,  note="The romantic splurge pick; 19,475 reviews"),
    dict(rank=4,  name="Catalonia Riviera Maya",     db="Catalonia Riviera Maya - AI",                    where="Riviera Maya",           ao=False, stars="5★",   score=7.30, clarity=4.5,  note="5-star at a 3-star price; swim-up rooms"),
    dict(rank=5,  name="Hotel Marina El Cid",        db="Hotel Marina El Cid Spa & Beach - AI",           where="Puerto Morelos",         ao=False, stars="4.5★", score=7.25, clarity=4.5,  note="10,786 reviews; calm bay 14 mi from the airport"),
    dict(rank=6,  name="Riu Negril",                 db="Riu Negril - AI",                                where="Negril, Jamaica",        ao=False, stars="4★",   score=7.23, clarity=8.0,  note="Seven-Mile-Beach area; historically seaweed-free"),
    dict(rank=7,  name="Riu Yucatan",                db="Riu Yucatan - AI",                               where="Playa del Carmen",       ao=False, stars="4★",   score=7.20, clarity=4.5,  note="Cheapest true beachfront; PDC nightlife walkable"),
    dict(rank=8,  name="Riu Palace Paradise Island", db="Riu Palace Paradise Island - AI - Adults Only",  where="Nassau, Bahamas",        ao=True,  stars="4.5★", score=7.18, clarity=None, note="Cabbage Beach postcard water; shortest flight (~3h)"),
    dict(rank=9,  name="Dreams Cozumel Cape",        db="Dreams Cozumel Cape - AI",                       where="Cozumel west coast",     ao=False, stars="5★",   score=7.05, clarity=9.0,  note="Same protected coast as Secrets Aura, family-friendly"),
    dict(rank=10, name="Barceló Bávaro Beach",       db="Barcelo Bavaro Beach - AI - Adults Only",        where="Punta Cana",             ao=True,  stars="4★",   score=6.95, clarity=4.0,  note="Moved +6% between verification passes — trending up"),
    dict(rank=11, name="Riu Palace Punta Cana",      db="Riu Palace Punta Cana - AI",                     where="Punta Cana",             ao=False, stars="5★",   score=6.85, clarity=4.0,  note="Palace tier under $1,250/pp"),
    dict(rank=12, name="Riu Palace Macao",           db="Riu Palace Macao - AI - Adults Only",            where="Punta Cana",             ao=True,  stars="5★",   score=6.85, clarity=4.0,  note="Beachfront swim-up suites"),
    dict(rank=13, name="Sonesta Ocean Point",        db="Sonesta Ocean Point - AI - Adults Only",         where="St. Maarten",            ao=True,  stars="5★",   score=6.52, clarity=None, note="Heavy seaweed landings expected island-wide"),
    dict(rank=14, name="Riu Palace Aruba",           db="Riu Palace Aruba",                               where="Palm Beach, Aruba",      ao=False, stars="4★",   score=6.18, clarity=8.0,  note="The original target — great water, brutal August pricing"),
    dict(rank=15, name="The Reef Beach Resort",      db="The Reef Beach Resort - AI",                     where="Grand Cayman",           ao=False, stars="3.5★", score=6.17, clarity=9.0,  note="Superb water; only true all-inclusive on the island"),
    dict(rank=16, name="Blue Haven Resort",          db="Blue Haven Resort - AI",                         where="Turks & Caicos",         ao=False, stars="4.5★", score=6.16, clarity=9.5,  note="Clearest water in the Caribbean; $8,300+ per couple"),
    dict(rank=17, name="The Verandah",               db="The Verandah - AI - Adults Only",                where="Antigua",                ao=True,  stars="4★",   score=6.11, clarity=None, note="East Caribbean at record seaweed levels"),
    dict(rank=18, name="Riu Palace Antillas",        db="Riu Palace Antillas (Adults Only)",              where="Palm Beach, Aruba",      ao=True,  stars="4★",   score=6.10, clarity=8.0,  note="~$1,000 premium over Palace Aruba on every source"),
    dict(rank=19, name="Royalton Hideaway",          db="Royalton Hideaway St Lucia - AI - Adults Only",  where="St. Lucia",              ao=True,  stars="5★",   score=5.89, clarity=None, note="Volcanic sand and the wettest month — not crystal"),
    dict(rank=20, name="The Club Barbados",          db="The Club Barbados - AI - Adults Only",           where="Barbados",               ao=True,  stars="3.5★", score=5.54, clarity=None, note="Worst seaweed year on record for Barbados — out"),
]


def load_rows():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute("SELECT * FROM PriceCheck ORDER BY CheckId")]
    con.close()
    return rows


def latest_price(rows, db_name):
    """Latest observed total (2 adults) for a resort, package rows preferred."""
    obs = [r for r in rows if r["RouteOrResort"] == db_name and r["TotalPrice"] > 0]
    if not obs:
        return None
    pkgs = [r for r in obs if r["Kind"] == "Package"]
    pick = (pkgs or obs)[-1]
    return pick["TotalPrice"]


def build(rows):
    n_obs = len(rows)
    last_checked = max(r["CheckedAt"] for r in rows)[:10]
    n_dest = len({r["TripId"] for r in rows})
    sources = sorted({r["Source"] for r in rows})

    board_rows = []
    for opt in RANKING:
        price = latest_price(rows, opt["db"])
        price_html = f"${price:,.0f}" if price else "—"
        pp_html = f"${price / 2:,.0f}" if price else "—"
        if opt["clarity"] is not None:
            pct = opt["clarity"] * 10
            clarity_html = (
                f'<div class="clarity" title="Expected August water clarity {opt["clarity"]}/10">'
                f'<div class="clarity-track"><div class="clarity-fill" style="width:{pct}%"></div></div>'
                f'<span class="clarity-num">{opt["clarity"]:g}</span></div>'
            )
        else:
            clarity_html = '<span class="dim">not scored</span>'
        ao_html = '<span class="tag">adults-only</span>' if opt["ao"] else ""
        medal = {1: "medal-1", 2: "medal-2", 3: "medal-3"}.get(opt["rank"], "")
        board_rows.append(f"""
        <tr class="{medal}">
          <td class="num rank">{opt['rank']}</td>
          <td><div class="resort">{html.escape(opt['name'])} <span class="stars">{opt['stars']}</span> {ao_html}</div>
              <div class="where">{html.escape(opt['where'])} — {html.escape(opt['note'])}</div></td>
          <td class="num price">{price_html}<div class="pp">{pp_html} pp</div></td>
          <td class="num score">{opt['score']:.2f}</td>
          <td class="clarity-cell">{clarity_html}</td>
        </tr>""")

    ledger_data = [
        dict(
            id=r["CheckId"], at=r["CheckedAt"][:16].replace("T", " "),
            dest=DESTINATIONS.get(r["TripId"], r["TripId"]), trip=r["TripId"],
            src=r["Source"], kind=r["Kind"], what=r["RouteOrResort"],
            dates=f"{r['DepartDate']}{' → ' + r['ReturnDate'] if r['ReturnDate'] else ''}",
            total=r["TotalPrice"], pp=r["PerPerson"], status=r["Status"] or "",
            promo=r["PromoNotes"] or "", notes=r["RawNotes"] or "",
        )
        for r in rows
    ]

    dest_options = "".join(
        f'<option value="{html.escape(d)}">{html.escape(d)}</option>'
        for d in sorted({e["dest"] for e in ledger_data})
    )
    src_options = "".join(f'<option value="{s}">{s}</option>' for s in sources)

    css = """
:root{
  --bg:#EDF4F3; --surface:#FFFFFF; --surface2:#E3EDEB; --ink:#0B242E;
  --muted:#51686E; --line:#C9D9D7; --accent:#0E7C7B; --accent-strong:#0A5C5B;
  --sand:#F2E9D6; --sand-ink:#6B5324;
  --green:#1E8A4C; --green-bg:#DCEFE3; --amber:#A8690F; --amber-bg:#F5E9D2;
  --red:#C0402F; --red-bg:#F6DFDA;
  --shadow:0 1px 3px rgba(11,36,46,.08);
}
@media (prefers-color-scheme: dark){:root{
  --bg:#081E26; --surface:#0F2E38; --surface2:#143641; --ink:#E4F0EF;
  --muted:#8FAAAE; --line:#1F4450; --accent:#3CC8BF; --accent-strong:#6FDCD4;
  --sand:#2E2A1D; --sand-ink:#D8C68F;
  --green:#4CC98A; --green-bg:#12382B; --amber:#E0A94E; --amber-bg:#3A2F14;
  --red:#E7705C; --red-bg:#421F19;
  --shadow:0 1px 3px rgba(0,0,0,.35);
}}
:root[data-theme="light"]{
  --bg:#EDF4F3; --surface:#FFFFFF; --surface2:#E3EDEB; --ink:#0B242E;
  --muted:#51686E; --line:#C9D9D7; --accent:#0E7C7B; --accent-strong:#0A5C5B;
  --sand:#F2E9D6; --sand-ink:#6B5324;
  --green:#1E8A4C; --green-bg:#DCEFE3; --amber:#A8690F; --amber-bg:#F5E9D2;
  --red:#C0402F; --red-bg:#F6DFDA;
  --shadow:0 1px 3px rgba(11,36,46,.08);
}
:root[data-theme="dark"]{
  --bg:#081E26; --surface:#0F2E38; --surface2:#143641; --ink:#E4F0EF;
  --muted:#8FAAAE; --line:#1F4450; --accent:#3CC8BF; --accent-strong:#6FDCD4;
  --sand:#2E2A1D; --sand-ink:#D8C68F;
  --green:#4CC98A; --green-bg:#12382B; --amber:#E0A94E; --amber-bg:#3A2F14;
  --red:#E7705C; --red-bg:#421F19;
  --shadow:0 1px 3px rgba(0,0,0,.35);
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.55 "Charter","Georgia",serif;-webkit-text-size-adjust:100%}
.wrap{max-width:980px;margin:0 auto;padding:0 20px 64px}
a{color:var(--accent-strong)}
.mono,.num,.tag,.pill,.eyebrow,th,.ledger td{
  font-family:ui-monospace,"Cascadia Code","SF Mono",Consolas,Menlo,monospace}
.num{font-variant-numeric:tabular-nums}
h1,h2,.sans{font-family:-apple-system,"Segoe UI","Helvetica Neue",Arial,sans-serif}

header{padding:44px 0 8px;border-bottom:3px solid var(--ink)}
.eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent-strong);margin:0 0 10px}
h1{font-size:clamp(30px,5.4vw,52px);font-weight:800;letter-spacing:-.02em;
  line-height:1.02;margin:0 0 14px;text-wrap:balance;text-transform:uppercase}
h1 .thin{color:var(--muted);font-weight:300}
.meta-row{display:flex;flex-wrap:wrap;gap:8px 22px;padding:10px 0 14px;
  font-family:ui-monospace,Consolas,monospace;font-size:12.5px;color:var(--muted)}
.meta-row b{color:var(--ink);font-weight:600}

section{margin-top:44px}
h2{font-size:14px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;
  margin:0 0 6px;display:flex;align-items:baseline;gap:10px}
h2::after{content:"";flex:1;border-top:1px solid var(--line);transform:translateY(-4px)}
.kicker{color:var(--muted);font-size:14.5px;margin:0 0 18px;max-width:62ch}

.verdict{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:18px}
@media(max-width:720px){.verdict{grid-template-columns:1fr}}
.card{background:var(--surface);border:1px solid var(--line);border-radius:6px;
  padding:20px 22px;box-shadow:var(--shadow)}
.card.win{border:2px solid var(--accent);position:relative}
.card .label{font-family:ui-monospace,Consolas,monospace;font-size:11px;
  letter-spacing:.14em;text-transform:uppercase;color:var(--accent-strong);margin-bottom:8px}
.card h3{font-family:-apple-system,"Segoe UI",Arial,sans-serif;font-size:22px;
  font-weight:800;margin:0 0 2px;letter-spacing:-.01em}
.card .sub{color:var(--muted);font-size:14px;margin-bottom:12px}
.bigprice{font-family:ui-monospace,Consolas,monospace;font-size:34px;font-weight:700;
  font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.bigprice small{font-size:14px;color:var(--muted);font-weight:400;letter-spacing:0}
.card p{font-size:14.5px;margin:10px 0 0}
.caveat{background:var(--sand);color:var(--sand-ink);border-radius:6px;
  padding:14px 18px;font-size:14.5px;margin-top:16px}
.caveat b{font-weight:700}

.tablewrap{overflow-x:auto;background:var(--surface);border:1px solid var(--line);
  border-radius:6px;box-shadow:var(--shadow)}
table{border-collapse:collapse;width:100%;font-size:14px}
th{font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);
  text-align:left;padding:10px 12px;border-bottom:2px solid var(--line);white-space:nowrap}
td{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:none}
td.num,th.num{text-align:right}
.rank{font-weight:700;color:var(--muted);width:2ch}
.medal-1 .rank,.medal-1 .price{color:var(--accent-strong);font-weight:700}
.medal-1{background:color-mix(in srgb,var(--accent) 7%,transparent)}
.resort{font-family:-apple-system,"Segoe UI",Arial,sans-serif;font-weight:700;font-size:15px}
.stars{color:var(--muted);font-weight:400;font-size:12.5px}
.where{color:var(--muted);font-size:13px;margin-top:2px;max-width:52ch}
.price{font-family:ui-monospace,Consolas,monospace;white-space:nowrap;font-size:15px}
.pp{color:var(--muted);font-size:11.5px}
.score{color:var(--muted)}
.tag{display:inline-block;font-size:10px;letter-spacing:.08em;text-transform:uppercase;
  border:1px solid var(--accent);color:var(--accent-strong);border-radius:999px;
  padding:1px 8px;vertical-align:2px}
.clarity{display:flex;align-items:center;gap:8px;min-width:110px}
.clarity-track{flex:1;height:8px;border-radius:4px;background:var(--surface2);overflow:hidden}
.clarity-fill{height:100%;border-radius:4px;
  background:linear-gradient(90deg,color-mix(in srgb,var(--accent) 40%,var(--surface2)),var(--accent))}
.clarity-num{font-family:ui-monospace,Consolas,monospace;font-size:12px;color:var(--muted)}
.dim{color:var(--muted);font-size:12.5px}

.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:720px){.cols{grid-template-columns:1fr}}
.zone{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:18px 20px;box-shadow:var(--shadow)}
.zone h4{font-family:-apple-system,"Segoe UI",Arial,sans-serif;font-size:13px;
  letter-spacing:.1em;text-transform:uppercase;margin:0 0 10px}
.zone.good h4{color:var(--green)} .zone.bad h4{color:var(--red)}
.zone ul{margin:0;padding:0;list-style:none;font-size:14.5px}
.zone li{display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-bottom:1px dashed var(--line)}
.zone li:last-child{border-bottom:none}
.zone .val{font-family:ui-monospace,Consolas,monospace;color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums}

.pill{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.08em;
  border-radius:3px;padding:2px 7px}
.pill.GREEN{background:var(--green-bg);color:var(--green)}
.pill.AMBER{background:var(--amber-bg);color:var(--amber)}
.pill.RED{background:var(--red-bg);color:var(--red)}

.filters{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 12px}
.filters select,.filters input{font-family:ui-monospace,Consolas,monospace;font-size:13px;
  color:var(--ink);background:var(--surface);border:1px solid var(--line);
  border-radius:4px;padding:7px 10px}
.filters input{flex:1;min-width:160px}
.filters select:focus,.filters input:focus{outline:2px solid var(--accent);outline-offset:1px}
.count{font-family:ui-monospace,Consolas,monospace;font-size:12px;color:var(--muted);
  align-self:center;margin-left:auto}
.ledger td{font-size:12.5px}
.ledger .what{max-width:30ch}
.ledger .notes{color:var(--muted);max-width:36ch}

.aruba{background:var(--surface);border:1px solid var(--line);border-radius:6px;
  padding:20px 22px;box-shadow:var(--shadow)}
.aruba .fig{display:flex;flex-wrap:wrap;gap:26px;margin-bottom:12px}
.aruba .fig div{min-width:120px}
.aruba .fig .n{font-family:ui-monospace,Consolas,monospace;font-size:26px;font-weight:700;font-variant-numeric:tabular-nums}
.aruba .fig .l{font-size:12px;color:var(--muted);letter-spacing:.06em;text-transform:uppercase;
  font-family:ui-monospace,Consolas,monospace}
.aruba p{font-size:14.5px;margin:8px 0 0;max-width:68ch}

ol.book{font-size:15px;max-width:66ch;padding-left:22px}
ol.book li{margin-bottom:10px}
footer{margin-top:56px;padding-top:16px;border-top:1px solid var(--line);
  font-family:ui-monospace,Consolas,monospace;font-size:12px;color:var(--muted);line-height:1.7}
@media (prefers-reduced-motion: no-preference){
  .clarity-fill{transition:width .6s ease}
}
"""

    board_html = "".join(board_rows)

    body = f"""<title>Caribbean Trip Portal — Aug 2026</title>
<style>{css}</style>
<div class="wrap">
<header>
  <p class="eyebrow">FareScout · shared trip portal</p>
  <h1>Where we should go <span class="thin">in August</span></h1>
  <div class="meta-row">
    <span><b>DTW</b> departure</span>
    <span>Sat <b>Aug 8</b> → Sat <b>Aug 15</b>, 2026</span>
    <span><b>2 adults</b> · all-inclusive · 1 room</span>
    <span><b>{n_obs}</b> live price observations · <b>{n_dest}</b> destinations</span>
    <span>last checked <b>{last_checked}</b></span>
  </div>
</header>

<section>
  <h2>The verdict</h2>
  <p class="kicker">Every price below is the full trip for both travelers — flights from Detroit, hotel, taxes — as displayed at the source. Verified across three passes on July 17.</p>
  <div class="verdict">
    <div class="card win">
      <div class="label">Book this — best value found</div>
      <h3>Riu Latino <span class="tag">adults-only</span></h3>
      <div class="sub">Costa Mujeres, Mexico · 4.5★ · opened 2024</div>
      <div class="bigprice">$2,412 <small>total for two</small></div>
      <p>Cheapest adults-only anywhere in the sweep, a 3h45m <em>nonstop</em> from DTW, and its northwest-facing beach is one of the few mainland-Mexico stretches expected to stay relatively clear in a record seaweed year. The Aug 8 start was confirmed cheapest against six date-shift variants.</p>
    </div>
    <div class="card">
      <div class="label">If crystal water is non-negotiable</div>
      <h3>Secrets Aura Cozumel <span class="tag">adults-only</span></h3>
      <div class="sub">Cozumel west coast · 5★ · swim-out suites</div>
      <div class="bigprice">$3,568 <small>total for two</small></div>
      <p>Cozumel's west coast is physically shielded from the sargassum flow — clarity there is a near-certainty, not a bet. The +$1,156 buys that certainty; the trade is a ~5.5h one-stop flight instead of a nonstop.</p>
    </div>
  </div>
  <div class="caveat"><b>The honest caveat:</b> Secrets The Vine and everything in Punta Cana are still great resorts at great prices — but in August 2026 you'd be gambling the "crystal clear" part of the trip on which way the wind blows that week. Resorts rake sand daily; they can't rake the water.</div>
</section>

<section>
  <h2>The board — all 20 options, conditions-adjusted</h2>
  <p class="kicker">Score is the 10-criterion model from the scorecard (price, water, flight, resort tier, adults-only fit, conditions…). Clarity is expected August water clarity from the sargassum research, 0–10. Prices are the latest observation in the database.</p>
  <div class="tablewrap">
  <table>
    <thead><tr>
      <th class="num">#</th><th>Resort</th><th class="num">Total (2)</th>
      <th class="num">Score</th><th>Water clarity</th>
    </tr></thead>
    <tbody>{board_html}
    </tbody>
  </table>
  </div>
</section>

<section>
  <h2>August conditions — the finding that changed the ranking</h2>
  <p class="kicker">2026 is the second-worst sargassum (seaweed) year ever recorded — 33.6M metric tons, per the USF Optical Oceanography Lab's June 30 bulletin, with beaching likely to increase through August. Hurricanes, by contrast, are a green light: CSU forecasts the quietest season since 2014, and Aug 8–15 sits before the climatological ramp.</p>
  <div class="cols">
    <div class="zone good">
      <h4>Protected water — safe bets</h4>
      <ul>
        <li><span>Grace Bay, Turks &amp; Caicos</span><span class="val">9.5 / 10</span></li>
        <li><span>Cozumel west coast</span><span class="val">9 / 10</span></li>
        <li><span>Seven Mile Beach, Cayman</span><span class="val">9 / 10</span></li>
        <li><span>Negril, Jamaica</span><span class="val">8 / 10</span></li>
        <li><span>Palm Beach, Aruba</span><span class="val">8 / 10</span></li>
        <li><span>Costa Mujeres, Mexico</span><span class="val">7.5 / 10</span></li>
      </ul>
    </div>
    <div class="zone bad">
      <h4>Hit zones — avoid for clear water</h4>
      <ul>
        <li><span>Punta Cana / Bávaro</span><span class="val">4 / 10 — worst</span></li>
        <li><span>Riviera Maya / Playa del Carmen</span><span class="val">4.5 / 10</span></li>
        <li><span>Cancún Hotel Zone</span><span class="val">5 / 10</span></li>
        <li><span>Barbados</span><span class="val">worst year on record</span></li>
        <li><span>Puerto Rico</span><span class="val">state of emergency</span></li>
        <li><span>St. Maarten / E. Caribbean</span><span class="val">record levels</span></li>
      </ul>
    </div>
  </div>
  <div class="caveat">Beach-level seaweed is wind-dependent day to day — USF explicitly declines to predict individual beaches. The scores are zone-level expectations, not guarantees.</div>
</section>

<section>
  <h2>Why Aruba — the original target — lost</h2>
  <div class="aruba">
    <div class="fig">
      <div><div class="n">$5,972</div><div class="l">best Aruba package</div></div>
      <div><div class="n">$2,412</div><div class="l">Riu Latino, same week</div></div>
      <div><div class="n">2.5×</div><div class="l">the price of equal-tier Mexico</div></div>
      <div><div class="n">6h40m+</div><div class="l">1-stop only until Dec 19</div></div>
    </div>
    <p>Aruba's water (and zero hurricane risk since 1851) is real — Palm Beach scores 8/10 even in a record seaweed year. But every August observation came in <span class="pill RED">RED</span> against the baselines: flights $921/pp vs a $650 AMBER ceiling, and the cheapest complete package at $5,972. Same week, same airport, Cancún and Punta Cana price at roughly a third. Aruba stays in the database as the winter-season candidate — the DTW nonstop returns Dec 19.</p>
  </div>
</section>

<section>
  <h2>The ledger — every price observed</h2>
  <p class="kicker">All {n_obs} observations from the read-only scouting runs, straight from the database. Status colors apply to the Aruba baselines only; SCOUT rows were exploratory. Prices are quotes, not offers — they can change at checkout.</p>
  <div class="filters">
    <select id="f-dest" aria-label="Filter by destination"><option value="">All destinations</option>{dest_options}</select>
    <select id="f-src" aria-label="Filter by source"><option value="">All sources</option>{src_options}</select>
    <select id="f-kind" aria-label="Filter by kind"><option value="">All kinds</option>
      <option>Flight</option><option>Hotel</option><option>Package</option></select>
    <select id="f-sort" aria-label="Sort">
      <option value="id">Order checked</option>
      <option value="asc">Price ↑</option>
      <option value="desc">Price ↓</option></select>
    <input id="f-q" type="search" placeholder="search resort, carrier, notes…" aria-label="Search observations">
    <span class="count" id="f-count"></span>
  </div>
  <div class="tablewrap ledger">
  <table>
    <thead><tr>
      <th>Checked</th><th>Destination</th><th>Source</th><th>Kind</th>
      <th>Route / resort</th><th class="num">Total (2)</th><th>Status</th><th>Notes</th>
    </tr></thead>
    <tbody id="ledger-body"></tbody>
  </table>
  </div>
</section>

<section>
  <h2>How to book (no bookings were made)</h2>
  <ol class="book">
    <li><b>CheapCaribbean.com</b> → Hotel + Flight → Detroit → destination → Aug 8–15 → 2 adults. The $200 Jet Set July promo applies automatically; 24-hour free cancellation.</li>
    <li>Filter to the resort by name, pick the entry room, then <b>review the flight it selected</b> — upgrade off a 2-stop if offered for ~$50–100.</li>
    <li>Cross-check <b>packagesus.riu.com</b> for Riu properties and <b>barcelo.com</b> direct for Barceló — direct occasionally beats the package price.</li>
  </ol>
</section>

<footer>
  Generated from <b>data/FareScout.db</b> ({n_obs} PriceCheck rows) and the scouting reports of 2026-07-17.<br>
  Read-only reconnaissance: no bookings made, no payment or passenger data touched. All prices USD, for 2 adults, as displayed at the source — quotes move; verify at checkout.
</footer>
</div>

<script>
const DATA = {json.dumps(ledger_data, ensure_ascii=False)};
const fmt = n => n > 0 ? '$' + n.toLocaleString('en-US', {{maximumFractionDigits: 0}}) : '—';
const esc = s => s.replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}})[c]);
const els = ['f-dest','f-src','f-kind','f-sort','f-q'].map(id => document.getElementById(id));
const body = document.getElementById('ledger-body');
const count = document.getElementById('f-count');
function render() {{
  const [dest, src, kind, sort, q] = els.map(e => e.value);
  const needle = q.trim().toLowerCase();
  let rows = DATA.filter(r =>
    (!dest || r.dest === dest) && (!src || r.src === src) && (!kind || r.kind === kind) &&
    (!needle || (r.what + ' ' + r.notes + ' ' + r.promo + ' ' + r.dest).toLowerCase().includes(needle)));
  if (sort === 'asc')  rows = rows.slice().sort((a, b) => a.total - b.total);
  if (sort === 'desc') rows = rows.slice().sort((a, b) => b.total - a.total);
  body.innerHTML = rows.map(r => `<tr>
    <td class="num">${{r.at.slice(5, 16)}}</td>
    <td>${{esc(r.dest)}}</td><td>${{r.src}}</td><td>${{r.kind}}</td>
    <td class="what">${{esc(r.what)}}<div class="dim">${{r.dates}}</div></td>
    <td class="num">${{fmt(r.total)}}${{r.pp ? `<div class="pp">${{fmt(r.pp)}} pp</div>` : ''}}</td>
    <td>${{r.status ? `<span class="pill ${{r.status}}">${{r.status}}</span>` : ''}}</td>
    <td class="notes">${{esc(r.promo ? r.promo + (r.notes ? ' — ' + r.notes : '') : r.notes)}}</td>
  </tr>`).join('');
  count.textContent = rows.length + ' / ' + DATA.length + ' rows';
}}
els.forEach(e => e.addEventListener('input', render));
render();
</script>
"""

    standalone = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{body}
</head>
</html>"""
    # Move visible content out of <head> for the standalone build: browsers
    # auto-open <body> at the first <div>, so this works, but be explicit.
    standalone = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Caribbean Trip Portal — Aug 2026</title>
<style>{css}</style>
</head>
<body>
{body.split('</style>', 1)[1]}
</body>
</html>"""
    return standalone, body


def main():
    rows = load_rows()
    standalone, fragment = build(rows)
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "index.html").write_text(standalone, encoding="utf-8")
    (OUT_DIR / "portal-fragment.html").write_text(fragment, encoding="utf-8")
    print(f"wrote docs/index.html ({len(standalone):,} bytes) from {len(rows)} observations")


if __name__ == "__main__":
    main()
