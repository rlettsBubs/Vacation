"""Phase 2b — channel expansion pulls for tracked properties.

One PriceCheck row per successfully parsed property/source pair, Source set
to the channel. Hotel-only quotes (HyattDirect) are paired with the current
GoogleFlights low for the matching route and the combined figure stored in
RawNotes as 'SYNTH_TOTAL: <amount>' — never in TotalPrice.

Sites that block automation are SKIPped after MAX_ATTEMPTS — recorded in the
run result (with URL) but never fought with captcha workarounds, and never
written to PriceCheck as fake rows.
"""

import datetime
import re
import time

from . import config
from .conditions import FetchError, fetch_plain, fetch_chrome, strip_tags

MAX_ATTEMPTS = 3
RETRY_PAUSE_S = 2.0

RE_PRICE = re.compile(r"\$\s?(\d{1,2},?\d{3})(?:\.\d{2})?")
PLAUSIBLE = (500, 20000)  # package/hotel total for 2 adults, 7 nights


def fetch_with_retries(url):
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            try:
                return fetch_plain(url)
            except FetchError:
                return fetch_chrome(url)
        except FetchError as exc:
            last = exc
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_PAUSE_S)
    raise FetchError(f"blocked/unreachable after {MAX_ATTEMPTS} attempts: {last}")


def parse_price(page_text, hints):
    """Lowest plausible $-figure within a window around a property mention."""
    for hint in hints:
        idx = page_text.find(hint)
        if idx < 0:
            continue
        window = page_text[max(0, idx - 200): idx + 400]
        prices = [float(m.replace(",", "")) for m in RE_PRICE.findall(window)]
        prices = [p for p in prices if PLAUSIBLE[0] <= p <= PLAUSIBLE[1]]
        if prices:
            return min(prices)
    return None


def google_flights_low(con, route):
    """Cheapest flight total (2 adults) from the most recent check of a route."""
    row = con.execute(
        """SELECT MIN(TotalPrice) low FROM PriceCheck
           WHERE Kind='Flight' AND RouteOrResort=? AND TotalPrice > 0
             AND DATE(CheckedAt) = (SELECT MAX(DATE(CheckedAt)) FROM PriceCheck
                                    WHERE Kind='Flight' AND RouteOrResort=?)""",
        (route, route),
    ).fetchone()
    return row["low"] if row and row["low"] else None


def run(con, now=None, fetcher=fetch_with_retries):
    """One expansion pull. Returns per-target results; SKIPs carry the URL."""
    checked_at = (now or datetime.datetime.now()).isoformat(timespec="seconds")
    results = []
    pages = {}  # url -> text or FetchError, one fetch per site
    for t in config.CHANNEL_TARGETS:
        if t["url"] not in pages:
            try:
                pages[t["url"]] = strip_tags(fetcher(t["url"]))
            except FetchError as exc:
                pages[t["url"]] = exc

        page = pages[t["url"]]
        label = f"{t['source']} × {t['name']}"
        if isinstance(page, FetchError):
            results.append(dict(target=t, price=None,
                                skip=f"SKIP {t['url']} — {page}"))
            continue
        price = parse_price(page, t["hints"])
        if price is None:
            results.append(dict(target=t, price=None,
                                skip=f"SKIP {t['url']} — page fetched but no "
                                     f"parseable price near {t['hints']}"))
            continue

        notes = f"Phase 2b channel pull ({label})"
        if t["kind"] == "Hotel":
            low = google_flights_low(con, t.get("route", ""))
            if low:
                notes += f"; SYNTH_TOTAL: {price + low:.0f} " \
                         f"(hotel {price:.0f} + GoogleFlights low {low:.0f})"
            else:
                notes += f"; SYNTH_TOTAL unavailable (no GoogleFlights rows " \
                         f"for {t.get('route')})"
        con.execute(
            """INSERT INTO PriceCheck (CheckedAt, TripId, Source, Kind,
                   RouteOrResort, DepartDate, ReturnDate, TotalPrice,
                   PerPerson, SourceUrl, RawNotes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (checked_at, t["trip"], t["source"], t["kind"], t["name"],
             config.DEPART, config.RETURN, price, price / 2, t["url"], notes),
        )
        results.append(dict(target=t, price=price, skip=None))
    con.commit()
    return results


def verify(results):
    """Phase 2b verify: a parsed price for >= 4 of the 6 pairs; failures
    logged with their URL."""
    lines = []
    parsed = [r for r in results if r["price"] is not None]
    for r in results:
        t = r["target"]
        if r["price"] is not None:
            lines.append(f"OK   {t['source']:<14} {t['name'][:40]:<40} "
                         f"${r['price']:,.0f}")
        else:
            lines.append(f"FAIL {t['source']:<14} {t['name'][:40]:<40} {r['skip']}")
    ok = len(parsed) >= 4
    lines.append(f"{'OK  ' if ok else 'FAIL'} parsed {len(parsed)}/"
                 f"{len(results)} property/source pairs (need >= 4)")
    return ok, lines
