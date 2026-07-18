"""Phase 1 — schema migration and explicit-text-only backfill.

Adds decision-mode columns to PriceCheck, creates ConditionCheck and Alert.
Backfill reads RawNotes/PromoNotes and only writes a value when the text
states it explicitly; anything ambiguous stays NULL.
"""

import re
import sqlite3

from . import db

PRICECHECK_NEW_COLUMNS = {
    "GuestRating": "REAL",
    "Refundable": "INTEGER",
    "Stops": "INTEGER",          # pre-existing in the original schema
    "NonstopAvailable": "INTEGER",
}

CONDITIONCHECK_SQL = """
CREATE TABLE IF NOT EXISTS ConditionCheck (
    CheckId     INTEGER PRIMARY KEY AUTOINCREMENT,
    CheckedAt   TEXT NOT NULL,
    Beach       TEXT NOT NULL,
    Status      TEXT NOT NULL CHECK(Status IN ('CLEAR','LIGHT','MODERATE','HEAVY')),
    Source      TEXT,
    Notes       TEXT
)"""

ALERT_SQL = """
CREATE TABLE IF NOT EXISTS Alert (
    AlertId      INTEGER PRIMARY KEY AUTOINCREMENT,
    CreatedAt    TEXT NOT NULL,
    TripId       TEXT,
    Kind         TEXT NOT NULL,
    Message      TEXT NOT NULL,
    Acknowledged INTEGER NOT NULL DEFAULT 0
)"""

# Explicit-text patterns only. Negated forms checked first.
RE_NON_REFUNDABLE = re.compile(r"non[- ]?refundable", re.I)
RE_REFUNDABLE = re.compile(r"refundable", re.I)
RE_NO_NONSTOP = re.compile(r"no\s+(?:[A-Z]{3}[-–][A-Z]{3}\s+)?nonstop", re.I)
RE_NONSTOP = re.compile(r"\bnon[- ]?stop\b", re.I)
# "guest rating: 8.2" or the Riu.com "8.2/10 (1762 reviews)" form — both are
# the text explicitly stating a guest rating; star ratings ("4-star") are not.
RE_GUEST_RATING = re.compile(
    r"guest rating[:\s]+(\d(?:\.\d)?)|(\d(?:\.\d)?)/10\s*\(\d+\s+reviews?\)", re.I)


def classify_refundable(text):
    if RE_NON_REFUNDABLE.search(text):
        return 0
    if RE_REFUNDABLE.search(text):
        return 1
    return None


def classify_nonstop(text):
    if RE_NO_NONSTOP.search(text):
        return 0
    if RE_NONSTOP.search(text):
        return 1
    return None


def apply(con):
    db.require_backup()
    added, skipped = [], []
    existing = db.table_columns(con, "PriceCheck")
    for col, ctype in PRICECHECK_NEW_COLUMNS.items():
        if col in existing:
            skipped.append(col)
        else:
            con.execute(f"ALTER TABLE PriceCheck ADD COLUMN {col} {ctype}")
            added.append(col)
    con.execute(CONDITIONCHECK_SQL)
    con.execute(ALERT_SQL)

    backfilled = []
    for r in con.execute(
        "SELECT CheckId, PromoNotes, RawNotes FROM PriceCheck"
    ).fetchall():
        text = " ".join(filter(None, [r["PromoNotes"], r["RawNotes"]]))
        if not text:
            continue
        updates = {}
        ref = classify_refundable(text)
        if ref is not None:
            updates["Refundable"] = ref
        nonstop = classify_nonstop(text)
        if nonstop is not None:
            updates["NonstopAvailable"] = nonstop
        m = RE_GUEST_RATING.search(text)
        if m:
            updates["GuestRating"] = float(m.group(1) or m.group(2))
        if updates:
            sets = ", ".join(f"{k}=?" for k in updates)
            con.execute(
                f"UPDATE PriceCheck SET {sets} WHERE CheckId=?",
                (*updates.values(), r["CheckId"]),
            )
            backfilled.append((r["CheckId"], updates, text))
    con.commit()
    return dict(added=added, skipped=skipped, backfilled=backfilled)


def verify(con, backup_path):
    """Phase 1 verification loop. Returns (ok, list-of-log-lines)."""
    lines, ok = [], True

    cols = {r["name"]: (r["type"] or "").upper()
            for r in con.execute("PRAGMA table_info(PriceCheck)")}
    for col, ctype in PRICECHECK_NEW_COLUMNS.items():
        if col not in cols:
            ok = False
            lines.append(f"FAIL PriceCheck missing column {col}")
        elif cols[col] != ctype:
            ok = False
            lines.append(f"FAIL PriceCheck.{col} type {cols[col]} != {ctype}")
        else:
            lines.append(f"OK   PriceCheck.{col} {ctype}")

    spec = {
        "ConditionCheck": {"CheckId": "INTEGER", "CheckedAt": "TEXT",
                           "Beach": "TEXT", "Status": "TEXT",
                           "Source": "TEXT", "Notes": "TEXT"},
        "Alert": {"AlertId": "INTEGER", "CreatedAt": "TEXT", "TripId": "TEXT",
                  "Kind": "TEXT", "Message": "TEXT", "Acknowledged": "INTEGER"},
    }
    for table, want in spec.items():
        have = {r["name"]: (r["type"] or "").upper()
                for r in con.execute(f"PRAGMA table_info({table})")}
        if have == want:
            lines.append(f"OK   {table} columns match spec")
        else:
            ok = False
            lines.append(f"FAIL {table}: have {have}, want {want}")

    live = con.execute("SELECT COUNT(*) FROM PriceCheck").fetchone()[0]
    bak = sqlite3.connect(backup_path).execute(
        "SELECT COUNT(*) FROM PriceCheck").fetchone()[0]
    if live == bak:
        lines.append(f"OK   PriceCheck row count unchanged ({live})")
    else:
        ok = False
        lines.append(f"FAIL row count live={live} backup={bak}")

    rows = con.execute(
        """SELECT CheckId, RouteOrResort, Refundable, NonstopAvailable,
                  GuestRating, PromoNotes, RawNotes
           FROM PriceCheck
           WHERE Refundable IS NOT NULL OR NonstopAvailable IS NOT NULL
              OR GuestRating IS NOT NULL
           ORDER BY CheckId LIMIT 5"""
    ).fetchall()
    lines.append(f"Spot-check — {len(rows)} backfilled row(s) shown "
                 "(all matched explicit text):")
    for r in rows:
        text = " | ".join(filter(None, [r["PromoNotes"], r["RawNotes"]]))
        lines.append(
            f"  #{r['CheckId']} {r['RouteOrResort']}: "
            f"Refundable={r['Refundable']} Nonstop={r['NonstopAvailable']} "
            f"GuestRating={r['GuestRating']}  <- {text[:110]}"
        )
        vals = [v for v in (r["Refundable"], r["NonstopAvailable"]) if v is not None]
        if vals and not (RE_REFUNDABLE.search(text) or RE_NONSTOP.search(text)):
            ok = False
            lines.append(f"  FAIL #{r['CheckId']}: backfill without explicit text")
    return ok, lines
