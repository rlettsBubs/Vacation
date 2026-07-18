"""Phase 3 — daily sargassum condition scrape into ConditionCheck.

Source: howisthesargassum.com, per-beach status for Cozumel West,
Playa Mujeres, and Palm Beach Aruba.

Fetch ladder:
  1. plain HTTPS fetch (urllib, honors proxy env vars);
  2. if the page is JS-rendered or the plain fetch fails, the existing
     Chrome automation path (Playwright against the operator's Chrome /
     the pinned chromium build) — never a bot-evading workaround;
  3. if a beach still can't be parsed, insert a row with the conservative
     Status 'MODERATE' and Notes starting 'PARSE_FAIL' — never silently skip.

Wording maps onto the enum conservatively: when several levels are mentioned
near a beach name, the worse one wins; unrecognizable wording is MODERATE.
"""

import datetime
import re
import urllib.request

from . import config, db

URL = "https://howisthesargassum.com/"

# keyword -> enum, checked worst-first so ambiguity resolves to worse.
WORDING = [
    ("HEAVY", ["heavy", "severe", "abundant", "excessive", "massive", "critical"]),
    ("MODERATE", ["moderate", "medium", "some sargassum", "partial"]),
    ("LIGHT", ["light", "low", "minimal", "slight", "traces", "very little"]),
    ("CLEAR", ["clear", "no sargassum", "clean", "none", "free of sargassum"]),
]


class FetchError(RuntimeError):
    pass


def fetch_plain(url=URL, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001 - any failure moves down the ladder
        raise FetchError(f"plain fetch failed: {exc}") from exc


def fetch_chrome(url=URL, timeout_ms=45000):
    """JS-rendered fallback via the Chrome automation path."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise FetchError(f"chrome path unavailable: {exc}") from exc
    import os
    try:
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch()
            except Exception:  # noqa: BLE001 - version-mismatched install
                alt = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
                browser = pw.chromium.launch(executable_path=f"{alt}/chromium")
            page = browser.new_page()
            page.goto(url, timeout=timeout_ms, wait_until="networkidle")
            html = page.content()
            browser.close()
            return html
    except Exception as exc:  # noqa: BLE001
        raise FetchError(f"chrome fetch failed: {exc}") from exc


def fetch(url=URL):
    try:
        return fetch_plain(url)
    except FetchError:
        return fetch_chrome(url)


def strip_tags(html):
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html,
                  flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).lower()


def classify(text_window):
    """Map wording near a beach mention onto the enum, worst level wins."""
    found = [status for status, words in WORDING
             if any(w in text_window for w in words)]
    if not found:
        return None
    return min(found, key=lambda s: -config.STATUS_ORDER.index(s))


def parse_beach(page_text, beach):
    """Find the beach mention and classify the wording around it."""
    for hint in config.BEACH_PAGE_HINTS[beach]:
        idx = page_text.find(hint)
        if idx >= 0:
            window = page_text[max(0, idx - 120): idx + 240]
            status = classify(window)
            if status:
                return status, f"matched '{hint}'"
    return None, "beach/status wording not found on page"


def run(con, now=None, fetcher=fetch):
    """One scrape cycle: exactly one row per beach, no silent skips."""
    checked_at = (now or datetime.datetime.now()).isoformat(timespec="seconds")
    inserted = []
    try:
        page_text = strip_tags(fetcher())
        fetch_err = None
    except FetchError as exc:
        page_text, fetch_err = None, str(exc)

    for beach in config.BEACHES:
        if page_text is None:
            status, notes = "MODERATE", f"PARSE_FAIL — {fetch_err}"
        else:
            status, detail = parse_beach(page_text, beach)
            if status is None:
                status, notes = "MODERATE", f"PARSE_FAIL — {detail}"
            else:
                notes = detail
        cur = con.execute(
            """INSERT INTO ConditionCheck (CheckedAt, Beach, Status, Source, Notes)
               VALUES (?,?,?,?,?)""",
            (checked_at, beach, status, config.CONDITION_SOURCE, notes),
        )
        inserted.append(dict(id=cur.lastrowid, beach=beach, status=status,
                             notes=notes))
    con.commit()
    return inserted


def verify(con, inserted):
    lines, ok = [], True
    if len(inserted) == 3:
        lines.append("OK   3 rows inserted (one per beach)")
    else:
        ok = False
        lines.append(f"FAIL inserted {len(inserted)} rows, want 3")
    for row in inserted:
        dbrow = con.execute(
            "SELECT * FROM ConditionCheck WHERE CheckId=?", (row["id"],)
        ).fetchone()
        valid = dbrow and dbrow["Status"] in config.STATUS_ORDER
        if not valid:
            ok = False
        lines.append(
            f"{'OK  ' if valid else 'FAIL'} #{row['id']} {dbrow['Beach']}: "
            f"{dbrow['Status']} ({dbrow['Notes'][:80]})"
        )
    return ok, lines
