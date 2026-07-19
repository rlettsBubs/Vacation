"""Phase 4 — alert rules, evaluated after each scrape cycle.

Each rule returns zero or more (TripId, Kind, Message) tuples. fire() writes
them to Alert and prints them prominently. A rule that is already represented
by an unacknowledged alert of the same Kind does not re-fire (no duplicate
noise); acknowledging the alert re-arms the rule.
"""

import datetime
import re

from . import config, scope

AURA = "Secrets Aura Cozumel - AI - Adults Only"
RIU_ARUBA_HEDGES = ["Riu Palace Aruba", "Riu Palace Antillas (Adults Only)"]
DEGRADED = ("MODERATE", "HEAVY")


def _last_two_packages(con, resort):
    return con.execute(
        """SELECT CheckId, CheckedAt, TotalPrice, Refundable FROM PriceCheck
           WHERE RouteOrResort=? AND Kind='Package' AND TotalPrice > 0
           ORDER BY CheckId DESC LIMIT 2""", (resort,)
    ).fetchall()


def _last_conditions(con, beach, n):
    # PARSE_FAIL rows are the scraper saying "couldn't read the page", not an
    # observed beach state — they stay conservative in the status view but
    # must not fire condition alerts (they re-fired ARUBA_CONDITIONS every
    # cycle for beaches the source doesn't cover).
    return con.execute(
        """SELECT Status FROM ConditionCheck WHERE Beach=?
             AND (Notes IS NULL OR Notes NOT LIKE 'PARSE_FAIL%')
           ORDER BY CheckId DESC LIMIT ?""", (beach, n)
    ).fetchall()


def rule_aura_price_move(con, now=None):
    rows = _last_two_packages(con, AURA)
    if len(rows) < 2:
        return []
    latest, prev = rows[0]["TotalPrice"], rows[1]["TotalPrice"]
    delta = latest - prev
    if abs(delta) >= config.PRICE_MOVE_THRESHOLD:
        return [("SCOUT-CZM", "AURA_PRICE_MOVE",
                 f"Secrets Aura Cozumel package moved {delta:+,.0f} "
                 f"(${prev:,.0f} -> ${latest:,.0f}, baseline ${config.AURA_BASELINE:,.0f})")]
    return []


def rule_czm_nonstop(con, now=None):
    row = con.execute(
        """SELECT CheckId, Carrier, TotalPrice FROM PriceCheck
           WHERE RouteOrResort='DTW-CZM' AND Kind='Flight'
             AND (Stops=0 OR NonstopAvailable=1)
           ORDER BY CheckId DESC LIMIT 1"""
    ).fetchone()
    if row:
        return [("SCOUT-CZM", "CZM_NONSTOP",
                 f"DTW-CZM nonstop appeared: {row['Carrier'] or 'carrier?'} "
                 f"${row['TotalPrice']:,.0f} (check #{row['CheckId']})")]
    return []


def rule_cozumel_conditions(con, now=None):
    rows = _last_conditions(con, "Cozumel West", 2)
    if len(rows) == 2 and all(r["Status"] in DEGRADED for r in rows):
        return [("SCOUT-CZM", "CZM_WEST_CONDITIONS",
                 f"Cozumel West worse than LIGHT on 2 consecutive checks "
                 f"({rows[1]['Status']}, {rows[0]['Status']})")]
    return []


def rule_aruba_conditions(con, now=None):
    rows = _last_conditions(con, "Palm Beach Aruba", 1)
    if rows and rows[0]["Status"] in DEGRADED:
        return [("ARUBA-001", "ARUBA_CONDITIONS",
                 f"Palm Beach Aruba worse than LIGHT ({rows[0]['Status']})")]
    return []


def rule_riu_aruba_hedge(con, now=None):
    alerts = []
    for resort in RIU_ARUBA_HEDGES:
        rows = _last_two_packages(con, resort)
        if len(rows) < 2:
            continue
        latest, prev = rows[0], rows[1]
        if prev["Refundable"] == 1 and latest["Refundable"] == 0:
            alerts.append(("ARUBA-001", "HEDGE_REFUNDABLE_LOST",
                           f"{resort} package lost the refundable flag"))
        rise = latest["TotalPrice"] - prev["TotalPrice"]
        if rise > config.HEDGE_RISE_THRESHOLD:
            alerts.append(("ARUBA-001", "HEDGE_PRICE_RISE",
                           f"{resort} package rose {rise:+,.0f} "
                           f"(${prev['TotalPrice']:,.0f} -> ${latest['TotalPrice']:,.0f})"))
    return alerts


def rule_deadline(con, now=None):
    today = (now or datetime.datetime.now()).date()
    if today >= config.DECISION_DEADLINE and not scope.booking_recorded(con):
        days = (today - config.DECISION_DEADLINE).days
        return [(None, "DECISION_DEADLINE",
                 f"Decision deadline {config.DECISION_DEADLINE} reached "
                 f"({days} day(s) past) with no booking recorded")]
    return []


RE_SYNTH_TOTAL = re.compile(r"SYNTH_TOTAL:\s*(\d+(?:\.\d+)?)")


def _comparable_total(row):
    """Package rows compare on TotalPrice; hotel-only rows only via their
    SYNTH_TOTAL note (hotel-only vs package would be a false undercut)."""
    if row["Kind"] == "Package":
        return row["TotalPrice"]
    m = RE_SYNTH_TOTAL.search(row["RawNotes"] or "")
    return float(m.group(1)) if m else None


def rule_channel_beat(con, now=None):
    """Phase 2b: another channel undercuts CheapCaribbean by >$100 for the
    same property/dates."""
    alerts_out = []
    for prop in config.TRACKED_PROPERTIES:
        cc = con.execute(
            """SELECT TotalPrice FROM PriceCheck
               WHERE RouteOrResort=? AND Source='CheapCaribbean'
                 AND Kind='Package' AND TotalPrice > 0
               ORDER BY CheckId DESC LIMIT 1""", (prop["name"],)
        ).fetchone()
        if not cc:
            continue
        rivals = con.execute(
            """SELECT Source, Kind, TotalPrice, RawNotes,
                      MAX(CheckId) FROM PriceCheck
               WHERE RouteOrResort=? AND Source != 'CheapCaribbean'
                 AND Kind IN ('Package','Hotel') AND TotalPrice > 0
                 AND DepartDate=?
               GROUP BY Source""", (prop["name"], config.DEPART)
        ).fetchall()
        for rival in rivals:
            total = _comparable_total(rival)
            if total is None:
                continue
            saving = cc["TotalPrice"] - total
            if saving > config.CHANNEL_BEAT_THRESHOLD:
                alerts_out.append((prop["trip"], "CHANNEL_BEAT",
                                   f"{rival['Source']} beats CheapCaribbean on "
                                   f"{prop['label']} by ${saving:,.0f} "
                                   f"(${total:,.0f} vs ${cc['TotalPrice']:,.0f})"))
    return alerts_out


RULES = [
    rule_aura_price_move,
    rule_czm_nonstop,
    rule_cozumel_conditions,
    rule_aruba_conditions,
    rule_riu_aruba_hedge,
    rule_channel_beat,
    rule_deadline,
]


def evaluate(con, now=None):
    found = []
    for rule in RULES:
        found.extend(rule(con, now=now))
    return found


def fire(con, now=None, quiet=False):
    """Evaluate all rules, insert new alerts, print them prominently."""
    created_at = (now or datetime.datetime.now()).isoformat(timespec="seconds")
    fired = []
    for trip_id, kind, message in evaluate(con, now=now):
        # Dedupe on Kind+Message so e.g. two different CHANNEL_BEAT findings
        # both surface, while the same finding doesn't repeat every cycle.
        dup = con.execute(
            "SELECT 1 FROM Alert WHERE Kind=? AND Message=? AND Acknowledged=0 "
            "LIMIT 1", (kind, message),
        ).fetchone()
        if dup:
            continue
        con.execute(
            "INSERT INTO Alert (CreatedAt, TripId, Kind, Message) VALUES (?,?,?,?)",
            (created_at, trip_id, kind, message),
        )
        fired.append((trip_id, kind, message))
    con.commit()
    if fired and not quiet:
        print("\n" + "!" * 72)
        for trip_id, kind, message in fired:
            print(f"!! ALERT [{kind}] {message}")
        print("!" * 72 + "\n")
    return fired


def acknowledge(con, alert_id=None):
    if alert_id is None:
        con.execute("UPDATE Alert SET Acknowledged=1 WHERE Acknowledged=0")
    else:
        con.execute("UPDATE Alert SET Acknowledged=1 WHERE AlertId=?", (alert_id,))
    con.commit()


def unacknowledged(con):
    return con.execute(
        "SELECT * FROM Alert WHERE Acknowledged=0 ORDER BY AlertId"
    ).fetchall()
