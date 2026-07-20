"""FareScout decision-mode CLI.

    python3 -m farescout status              # the Phase 5 status view
    python3 -m farescout migrate             # Phase 1 schema + backfill
    python3 -m farescout scope               # Phase 2 TripConfig scope cut
    python3 -m farescout scrape --dry-run    # plan the cycle (active trips only)
    python3 -m farescout conditions          # one sargassum scrape cycle
    python3 -m farescout alerts              # evaluate + fire alert rules
    python3 -m farescout ack [id]            # acknowledge alerts (all or one)
    python3 -m farescout book <TripId> [-m note]   # record the booking
"""

import argparse
import sys

from . import alerts, channels, conditions, db, migrate, scope, status


def main(argv=None):
    ap = argparse.ArgumentParser(prog="farescout")
    ap.add_argument("--db", help="alternate DB path (testing only)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run", help="one full cycle: conditions + channels + alerts + status")
    p.add_argument("--no-channels", action="store_true",
                   help="skip the Phase 2b channel pulls")
    sub.add_parser("migrate")
    sub.add_parser("scope")
    p = sub.add_parser("scrape")
    p.add_argument("--dry-run", action="store_true")
    sub.add_parser("conditions")
    sub.add_parser("channels")
    sub.add_parser("alerts")
    p = sub.add_parser("ack")
    p.add_argument("alert_id", nargs="?", type=int)
    p = sub.add_parser("book")
    p.add_argument("trip_id")
    p.add_argument("-m", "--note", default="")
    sub.add_parser("status")
    args = ap.parse_args(argv)

    con = db.connect(args.db)
    try:
        if args.cmd == "run":
            print("== conditions ==")
            for row in conditions.run(con):
                print(f"  {row['beach']:<18} {row['status']:<9} {row['notes'][:70]}")
            if not args.no_channels:
                print("== channels ==")
                _, lines = channels.verify(channels.run(con))
                print("\n".join(f"  {l}" for l in lines))
            print("== alerts ==")
            fired = alerts.fire(con)
            print(f"  {len(fired)} new alert(s)")
            out, _ = status.render(con)
            print(out)
            return 0
        if args.cmd == "migrate":
            result = migrate.apply(con)
            print(f"added columns: {result['added'] or 'none'}; "
                  f"already present: {result['skipped'] or 'none'}; "
                  f"backfilled {len(result['backfilled'])} row(s)")
        elif args.cmd == "scope":
            trips = scope.apply(con)
            print(f"TripConfig updated for {len(trips)} trips; "
                  f"active: ARUBA-001, SCOUT-CZM, SCOUT-CUN")
        elif args.cmd == "scrape":
            if not args.dry_run:
                print("Live price scraping runs on the operator machine via "
                      "Chrome automation; use --dry-run here.", file=sys.stderr)
                return 2
            scope.dry_run(con)
        elif args.cmd == "conditions":
            inserted = conditions.run(con)
            for row in inserted:
                print(f"  {row['beach']:<18} {row['status']:<9} {row['notes'][:70]}")
            alerts.fire(con)
        elif args.cmd == "channels":
            results = channels.run(con)
            _, lines = channels.verify(results)
            print("\n".join(lines))
            alerts.fire(con)
        elif args.cmd == "alerts":
            fired = alerts.fire(con)
            print(f"{len(fired)} new alert(s)")
        elif args.cmd == "ack":
            alerts.acknowledge(con, args.alert_id)
            print("acknowledged")
        elif args.cmd == "book":
            scope.record_booking(con, args.trip_id, args.note)
            print(f"booking recorded on {args.trip_id}")
        elif args.cmd == "status":
            out, _ = status.render(con)
            print(out)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
