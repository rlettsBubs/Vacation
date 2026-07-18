"""Phase 4 verification: every alert rule fires and clears on synthetic rows.

All tests run against a temp copy of the live DB (never the live file).
"""

import datetime
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from farescout import DB_PATH, alerts, config, db, scope

BEFORE_DEADLINE = datetime.datetime(2026, 7, 20, 12, 0)
AT_DEADLINE = datetime.datetime(2026, 7, 24, 12, 0)


def insert_price(con, resort, total, kind="Package", refundable=None,
                 stops=None, route=None, trip="SCOUT-CZM", source="CheapCaribbean"):
    con.execute(
        """INSERT INTO PriceCheck (CheckedAt, TripId, Source, Kind, RouteOrResort,
               DepartDate, ReturnDate, TotalPrice, Refundable, Stops)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (datetime.datetime.now().isoformat(timespec="seconds"), trip, source,
         kind, route or resort, "2026-08-08", "2026-08-15", total,
         refundable, stops),
    )
    con.commit()


def insert_condition(con, beach, status):
    con.execute(
        """INSERT INTO ConditionCheck (CheckedAt, Beach, Status, Source)
           VALUES (?,?,?,?)""",
        (datetime.datetime.now().isoformat(timespec="seconds"), beach, status,
         "synthetic"),
    )
    con.commit()


class AlertRuleTests(unittest.TestCase):
    """Each rule must fire on trigger data and stay quiet (clear) otherwise."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.db_path = self.tmp / "test.db"
        shutil.copy(DB_PATH, self.db_path)
        self.assertNotEqual(self.db_path, DB_PATH)
        self.con = db.connect(self.db_path)
        # Synthetic slate: acknowledge inherited alerts so dedupe starts
        # re-armed, and clear condition history (the live DB may hold
        # conservative PARSE_FAIL=MODERATE rows that would pre-trigger the
        # condition rules).
        self.con.execute("UPDATE Alert SET Acknowledged=1")
        self.con.execute("DELETE FROM ConditionCheck")
        self.con.commit()

    def tearDown(self):
        self.con.close()
        shutil.rmtree(self.tmp)

    def fired_kinds(self, now=BEFORE_DEADLINE):
        return {k for _, k, _ in alerts.fire(self.con, now=now, quiet=True)}

    # --- Rule 1: Aura ±$150 -------------------------------------------------
    def test_aura_price_move_fires_and_clears(self):
        insert_price(self.con, alerts.AURA, 3568)
        self.assertNotIn("AURA_PRICE_MOVE", self.fired_kinds())  # clear
        insert_price(self.con, alerts.AURA, 3568 + 151)
        self.assertIn("AURA_PRICE_MOVE", self.fired_kinds())     # fires
        self.assertNotIn("AURA_PRICE_MOVE", self.fired_kinds())  # dedupes
        alerts.acknowledge(self.con)
        insert_price(self.con, alerts.AURA, 3568 + 151)          # stable again
        self.assertNotIn("AURA_PRICE_MOVE", self.fired_kinds())  # cleared

    def test_aura_drop_also_fires(self):
        insert_price(self.con, alerts.AURA, 3568)
        insert_price(self.con, alerts.AURA, 3568 - 200)
        self.assertIn("AURA_PRICE_MOVE", self.fired_kinds())

    # --- Rule 2: DTW-CZM nonstop -------------------------------------------
    def test_czm_nonstop_fires_and_clears(self):
        insert_price(self.con, None, 900, kind="Flight", route="DTW-CZM",
                     stops=1, source="GoogleFlights")
        self.assertNotIn("CZM_NONSTOP", self.fired_kinds())      # 1-stop: clear
        insert_price(self.con, None, 980, kind="Flight", route="DTW-CZM",
                     stops=0, source="GoogleFlights")
        self.assertIn("CZM_NONSTOP", self.fired_kinds())         # fires
        self.assertNotIn("CZM_NONSTOP", self.fired_kinds())      # dedupes

    # --- Rule 3: Cozumel West 2 consecutive degraded -------------------------
    def test_cozumel_conditions_fires_and_clears(self):
        insert_condition(self.con, "Cozumel West", "MODERATE")
        self.assertNotIn("CZM_WEST_CONDITIONS", self.fired_kinds())  # 1 check only
        insert_condition(self.con, "Cozumel West", "HEAVY")
        self.assertIn("CZM_WEST_CONDITIONS", self.fired_kinds())     # fires
        alerts.acknowledge(self.con)
        insert_condition(self.con, "Cozumel West", "LIGHT")
        self.assertNotIn("CZM_WEST_CONDITIONS", self.fired_kinds())  # cleared

    # --- Rule 4: Palm Beach Aruba degraded -----------------------------------
    def test_aruba_conditions_fires_and_clears(self):
        insert_condition(self.con, "Palm Beach Aruba", "LIGHT")
        self.assertNotIn("ARUBA_CONDITIONS", self.fired_kinds())
        insert_condition(self.con, "Palm Beach Aruba", "HEAVY")
        self.assertIn("ARUBA_CONDITIONS", self.fired_kinds())
        alerts.acknowledge(self.con)
        insert_condition(self.con, "Palm Beach Aruba", "CLEAR")
        self.assertNotIn("ARUBA_CONDITIONS", self.fired_kinds())

    # --- Rule 5: hedge refundable / rise -------------------------------------
    def test_hedge_refundable_lost_fires(self):
        insert_price(self.con, "Riu Palace Aruba", 5972, refundable=1,
                     trip="ARUBA-001")
        self.assertNotIn("HEDGE_REFUNDABLE_LOST", self.fired_kinds())
        insert_price(self.con, "Riu Palace Aruba", 5972, refundable=0,
                     trip="ARUBA-001")
        self.assertIn("HEDGE_REFUNDABLE_LOST", self.fired_kinds())

    def test_hedge_price_rise_fires_and_clears(self):
        insert_price(self.con, "Riu Palace Antillas (Adults Only)", 6924,
                     trip="ARUBA-001")
        insert_price(self.con, "Riu Palace Antillas (Adults Only)", 7000,
                     trip="ARUBA-001")
        self.assertNotIn("HEDGE_PRICE_RISE", self.fired_kinds())  # +$76: clear
        insert_price(self.con, "Riu Palace Antillas (Adults Only)", 7400,
                     trip="ARUBA-001")
        self.assertIn("HEDGE_PRICE_RISE", self.fired_kinds())     # +$400: fires

    # --- Rule 6: decision deadline -------------------------------------------
    def test_deadline_fires_and_clears_on_booking(self):
        self.assertNotIn("DECISION_DEADLINE",
                         self.fired_kinds(now=BEFORE_DEADLINE))   # early: clear
        self.assertIn("DECISION_DEADLINE",
                      self.fired_kinds(now=AT_DEADLINE))          # fires
        alerts.acknowledge(self.con)
        scope.record_booking(self.con, "SCOUT-CZM", "booked Aura")
        self.assertNotIn("DECISION_DEADLINE",
                         self.fired_kinds(now=AT_DEADLINE))       # cleared

    # --- Safety ----------------------------------------------------------------
    def test_never_touches_live_db(self):
        live = sqlite3.connect(DB_PATH).execute(
            "SELECT COUNT(*) FROM PriceCheck").fetchone()[0]
        insert_price(self.con, alerts.AURA, 9999)
        live_after = sqlite3.connect(DB_PATH).execute(
            "SELECT COUNT(*) FROM PriceCheck").fetchone()[0]
        self.assertEqual(live, live_after)


if __name__ == "__main__":
    unittest.main()
