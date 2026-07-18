"""Decision-mode configuration: what we track, baselines, and the deadline."""

import datetime as _dt

# --- The decision -----------------------------------------------------------
DEPART = "2026-08-08"
RETURN = "2026-08-15"
DECISION_DEADLINE = _dt.date(2026, 7, 24)

# Baseline: Secrets Aura Cozumel package, CheapCaribbean, $200 Jet Set July
# promo applied (verified across 3 passes on 2026-07-17).
AURA_BASELINE = 3568.0
PRICE_MOVE_THRESHOLD = 150.0     # ± vs last observation fires an alert
HEDGE_RISE_THRESHOLD = 300.0     # Riu Aruba package rise that fires an alert

ACTIVE_TRIPS = ("ARUBA-001", "SCOUT-CZM", "SCOUT-CUN")

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

# --- Tracked properties (name = PriceCheck.RouteOrResort, exactly) ----------
# CheapCaribbean packages for all six; Kayak/Expedia hotel-only cross-check
# for the three Aruba properties only.
TRACKED_PROPERTIES = [
    dict(trip="SCOUT-CZM", name="Secrets Aura Cozumel - AI - Adults Only",
         label="Secrets Aura Cozumel", role="PRIMARY",
         sources=["CheapCaribbean"]),
    dict(trip="SCOUT-CZM", name="Dreams Cozumel Cape - AI",
         label="Dreams Cozumel Cape", role="BACKUP",
         sources=["CheapCaribbean"]),
    dict(trip="SCOUT-CUN", name="Riu Latino - AI - Adults Only",
         label="Riu Latino", role="BUDGET",
         sources=["CheapCaribbean"]),
    dict(trip="ARUBA-001", name="Riu Palace Aruba",
         label="Riu Palace Aruba", role="HEDGE",
         sources=["CheapCaribbean", "Riu", "Kayak", "Expedia"]),
    dict(trip="ARUBA-001", name="Riu Palace Antillas (Adults Only)",
         label="Riu Palace Antillas", role="HEDGE",
         sources=["CheapCaribbean", "Riu", "Kayak", "Expedia"]),
    dict(trip="ARUBA-001", name="Barcelo Aruba",
         label="Barceló Aruba", role="HEDGE",
         sources=["CheapCaribbean", "Kayak", "Expedia"]),
]

# GoogleFlights routes to watch (nonstop appearance on DTW-CZM is an alert).
TRACKED_FLIGHTS = [
    dict(trip="SCOUT-CZM", route="DTW-CZM"),
    dict(trip="ARUBA-001", route="DTW-AUA"),
]

# --- Condition monitoring ----------------------------------------------------
CONDITION_SOURCE = "howisthesargassum.com"
BEACHES = ["Cozumel West", "Playa Mujeres", "Palm Beach Aruba"]

# Beach -> query hints for the condition page parser.
BEACH_PAGE_HINTS = {
    "Cozumel West": ["cozumel"],
    "Playa Mujeres": ["playa mujeres", "costa mujeres", "mujeres"],
    "Palm Beach Aruba": ["aruba", "palm beach"],
}

STATUS_ORDER = ["CLEAR", "LIGHT", "MODERATE", "HEAVY"]  # best -> worst
