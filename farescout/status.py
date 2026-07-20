"""Phase 5 — the decision-mode status view.

Summary line:
  GREEN = Cozumel West LIGHT-or-better AND Aura within $150 of baseline
  AMBER = exactly one of those degraded
  RED   = both degraded, or the decision deadline passed without a booking
"""

import datetime

from . import alerts, config, scope

GOOD_CONDITIONS = ("CLEAR", "LIGHT")


def latest_prices(con):
    out = []
    for prop in config.TRACKED_PROPERTIES:
        # The headline number is pinned to CheapCaribbean Package rows — the
        # baseline channel. A hotel-only pull (e.g. HyattDirect) must never
        # display as the property price or trip the baseline comparison.
        latest = con.execute(
            """SELECT CheckedAt, Source, Kind, TotalPrice FROM PriceCheck
               WHERE RouteOrResort=? AND Source='CheapCaribbean'
                 AND Kind='Package' AND TotalPrice > 0
               ORDER BY CheckId DESC LIMIT 1""", (prop["name"],)
        ).fetchone()
        if not latest:
            latest = con.execute(
                """SELECT CheckedAt, Source, Kind, TotalPrice FROM PriceCheck
                   WHERE RouteOrResort=? AND TotalPrice > 0
                     AND Kind IN ('Package','Hotel')
                   ORDER BY CheckId DESC LIMIT 1""", (prop["name"],)
            ).fetchone()
        if not latest:
            continue
        # Delta only against the prior observation from the same source and
        # kind — a Kayak-hotel vs Expedia-hotel "delta" would be noise.
        prior = con.execute(
            """SELECT TotalPrice FROM PriceCheck
               WHERE RouteOrResort=? AND Source=? AND Kind=? AND TotalPrice > 0
               ORDER BY CheckId DESC LIMIT 1 OFFSET 1""",
            (prop["name"], latest["Source"], latest["Kind"]),
        ).fetchone()
        delta = latest["TotalPrice"] - prior["TotalPrice"] if prior else None
        out.append(dict(label=prop["label"], role=prop["role"],
                        price=latest["TotalPrice"], delta=delta,
                        source=latest["Source"], kind=latest["Kind"],
                        at=latest["CheckedAt"][:10]))
    return out


def latest_conditions(con, now=None):
    now = now or datetime.datetime.now()
    week_ago = (now - datetime.timedelta(days=7)).isoformat(timespec="seconds")
    out = []
    for beach in config.BEACHES:
        latest = con.execute(
            """SELECT CheckedAt, Status, Notes FROM ConditionCheck
               WHERE Beach=? ORDER BY CheckId DESC LIMIT 1""", (beach,)
        ).fetchone()
        trend = con.execute(
            """SELECT Status, COUNT(*) c FROM ConditionCheck
               WHERE Beach=? AND CheckedAt >= ? GROUP BY Status""",
            (beach, week_ago),
        ).fetchall()
        trend_s = " ".join(
            f"{r['Status']}x{r['c']}" for r in
            sorted(trend, key=lambda r: config.STATUS_ORDER.index(r["Status"]))
        ) or "no checks"
        out.append(dict(beach=beach,
                        status=latest["Status"] if latest else None,
                        at=latest["CheckedAt"][:10] if latest else "—",
                        parse_fail=bool(latest and "PARSE_FAIL" in (latest["Notes"] or "")),
                        trend=trend_s))
    return out


def summary_state(prices, conditions, con, now=None):
    today = (now or datetime.datetime.now()).date()
    if today >= config.DECISION_DEADLINE and not scope.booking_recorded(con):
        return "RED", "decision deadline passed with no booking recorded"

    cozumel = next((c for c in conditions if c["beach"] == "Cozumel West"), None)
    water_ok = bool(cozumel and cozumel["status"] in GOOD_CONDITIONS)
    aura = next((p for p in prices if p["label"] == "Secrets Aura Cozumel"), None)
    price_ok = bool(aura and abs(aura["price"] - config.AURA_BASELINE)
                    <= config.PRICE_MOVE_THRESHOLD)

    reasons = []
    if not water_ok:
        reasons.append(f"Cozumel West {cozumel['status'] if cozumel else 'unchecked'}")
    if not price_ok:
        reasons.append("Aura off baseline" if aura else "Aura unpriced")
    if water_ok and price_ok:
        return "GREEN", "Cozumel LIGHT-or-better and Aura within $150 of baseline"
    if len(reasons) == 1:
        return "AMBER", reasons[0]
    return "RED", "; ".join(reasons)


def render(con, now=None):
    now = now or datetime.datetime.now()
    prices = latest_prices(con)
    conditions = latest_conditions(con, now=now)
    state, why = summary_state(prices, conditions, con, now=now)
    days_left = (config.DECISION_DEADLINE - now.date()).days
    open_alerts = alerts.unacknowledged(con)

    w = 74
    lines = []
    lines.append("=" * w)
    lines.append(f"  FARESCOUT DECISION MODE — {state}  ({why})")
    lines.append(f"  {config.DEPART} -> {config.RETURN} · 2 adults · DTW"
                 f" · deadline {config.DECISION_DEADLINE}"
                 f" ({days_left} day(s) left)" if days_left >= 0 else
                 f"  deadline PASSED {-days_left} day(s) ago")
    lines.append("=" * w)

    lines.append("  PRICES (latest observation, total for 2)")
    for p in prices:
        delta = (f"{p['delta']:+,.0f}" if p["delta"] not in (None, 0)
                 else "unchanged" if p["delta"] == 0 else "first obs")
        lines.append(f"    {p['role']:<7} {p['label']:<22} ${p['price']:>6,.0f}"
                     f"  {delta:<11} {p['source']} {p['kind']} {p['at']}")
    aura = next((p for p in prices if p["label"] == "Secrets Aura Cozumel"), None)
    if aura:
        lines.append(f"    baseline Secrets Aura ${config.AURA_BASELINE:,.0f}"
                     f" (alert at ±${config.PRICE_MOVE_THRESHOLD:,.0f})")

    lines.append("  CONDITIONS (latest check, 7-day trend)")
    for c in conditions:
        flag = "  [PARSE_FAIL - conservative default]" if c["parse_fail"] else ""
        lines.append(f"    {c['beach']:<18} {c['status'] or '—':<9}"
                     f" {c['at']}  trend: {c['trend']}{flag}")

    if open_alerts:
        lines.append(f"  UNACKNOWLEDGED ALERTS ({len(open_alerts)})")
        for a in open_alerts:
            lines.append(f"    #{a['AlertId']} [{a['Kind']}] {a['Message']}")
    else:
        lines.append("  UNACKNOWLEDGED ALERTS: none")
    for check in config.MANUAL_CHECKS:
        if now.date().weekday() == check["day"]:
            lines.append(f"  MANUAL CHECK DUE TODAY: {check['label']}")
    lines.append("=" * w)
    return "\n".join(lines), state


def verify(con, now=None):
    """Phase 5 verification: render must succeed and the summary state must
    be re-derivable from the same rows it printed."""
    out, state = render(con, now=now)
    prices = latest_prices(con)
    conditions = latest_conditions(con, now=now)
    expected, _ = summary_state(prices, conditions, con, now=now)
    ok = state == expected and f"— {state}" in out
    lines = [f"OK   status view rendered ({len(out.splitlines())} lines), "
             f"summary {state} consistent with printed rows"
             if ok else f"FAIL state {state} != derived {expected}"]
    return ok, lines
