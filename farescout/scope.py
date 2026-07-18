"""Phase 2 — scope cut: TripConfig with Active flag, scrape plan for active trips.

No historical rows are deleted; eliminated trips are simply Active=0 and the
scrape loop plans work for active trips only.
"""

import datetime

from . import config, db

TRIPCONFIG_SQL = """
CREATE TABLE IF NOT EXISTS TripConfig (
    TripId      TEXT PRIMARY KEY,
    Destination TEXT,
    Active      INTEGER NOT NULL DEFAULT 0,
    BookedAt    TEXT,
    BookedNotes TEXT
)"""


def apply(con):
    db.require_backup()
    con.execute(TRIPCONFIG_SQL)
    trips = [r[0] for r in con.execute("SELECT DISTINCT TripId FROM PriceCheck")]
    for trip in trips:
        con.execute(
            """INSERT INTO TripConfig (TripId, Destination, Active)
               VALUES (?,?,?)
               ON CONFLICT(TripId) DO UPDATE SET Active=excluded.Active,
                   Destination=excluded.Destination""",
            (trip, config.DESTINATIONS.get(trip, trip),
             1 if trip in config.ACTIVE_TRIPS else 0),
        )
    con.commit()
    return trips


def record_booking(con, trip_id, notes=""):
    con.execute(
        "UPDATE TripConfig SET BookedAt=?, BookedNotes=? WHERE TripId=?",
        (datetime.datetime.now().isoformat(timespec="seconds"), notes, trip_id),
    )
    con.commit()


def booking_recorded(con):
    return con.execute(
        "SELECT 1 FROM TripConfig WHERE BookedAt IS NOT NULL LIMIT 1"
    ).fetchone() is not None


def scrape_plan(con):
    """The scrape cycle's work list. Only Active trips ever appear."""
    active = {r["TripId"] for r in
              con.execute("SELECT TripId FROM TripConfig WHERE Active=1")}
    plan = []
    for prop in config.TRACKED_PROPERTIES:
        if prop["trip"] in active:
            for source in prop["sources"]:
                kind = "Package" if source in ("CheapCaribbean", "Riu") else "Hotel"
                plan.append(dict(trip=prop["trip"], source=source, kind=kind,
                                 target=prop["name"]))
    for flight in config.TRACKED_FLIGHTS:
        if flight["trip"] in active:
            plan.append(dict(trip=flight["trip"], source="GoogleFlights",
                             kind="Flight", target=flight["route"]))
    return plan


def dry_run(con):
    plan = scrape_plan(con)
    print(f"DRY RUN — scrape cycle would perform {len(plan)} checks:")
    for step in plan:
        print(f"  [{step['trip']}] {step['source']:<14} {step['kind']:<7} {step['target']}")
    return plan


def verify(con, backup_count):
    lines, ok = [], True
    active = [r["TripId"] for r in con.execute(
        "SELECT TripId FROM TripConfig WHERE Active=1 ORDER BY TripId")]
    if sorted(active) == sorted(config.ACTIVE_TRIPS):
        lines.append(f"OK   exactly {len(active)} active trips: {', '.join(active)}")
    else:
        ok = False
        lines.append(f"FAIL active trips = {active}, want {config.ACTIVE_TRIPS}")

    inactive = con.execute(
        "SELECT COUNT(*) FROM TripConfig WHERE Active=0").fetchone()[0]
    lines.append(f"OK   {inactive} trips deactivated (rows preserved)")

    plan = scrape_plan(con)
    stray = [s for s in plan if s["trip"] not in config.ACTIVE_TRIPS]
    if stray:
        ok = False
        lines.append(f"FAIL dry-run plan touches inactive trips: {stray}")
    else:
        lines.append(f"OK   dry-run scrape cycle: {len(plan)} steps, "
                     "all on active trips only")

    live = con.execute("SELECT COUNT(*) FROM PriceCheck").fetchone()[0]
    if live == backup_count:
        lines.append(f"OK   historical PriceCheck rows untouched ({live})")
    else:
        ok = False
        lines.append(f"FAIL PriceCheck count {live} != backup {backup_count}")
    return ok, lines
