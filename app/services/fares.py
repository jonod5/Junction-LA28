"""
Per-mode cost model for the route engine.

Every figure here is a MODELED ESTIMATE, not a quote — the API labels them as
such and the UI must too.  Rideshare especially varies with surge/time of day;
we deliberately model a stable point estimate for reproducible research output
rather than chasing live prices (Uber's cost API is enterprise-gated — deferred
per PRD FR-D3).

Sources are cited inline per constant.  Anything time-sensitive is tagged
`# VERIFY before 8/5` so the Week-7 data-accuracy pass re-checks it before the
poster deadline.
"""

from __future__ import annotations

# ── Metro rail/bus (TAP) ──────────────────────────────────────────────────────
# Base fare per boarding/tap.  Source: metro.net/riding/fares (accessed 2026-07-19).
METRO_FARE_PER_TAP_USD = 1.75
# LA Metro fare capping: riders never pay more than this per day across taps.
# Source: metro.net/fares/fare-capping (accessed 2026-07-19).  # VERIFY before 8/5
METRO_DAILY_CAP_USD = 5.00

# ── Micromobility fallback pricing ────────────────────────────────────────────
# Used ONLY when a provider's live system_pricing_plans is unavailable.  When
# GBFS pricing is present we prefer it (see micromobility_cost()).
# Typical LA shared-scooter pricing.  # VERIFY before 8/5
SCOOTER_UNLOCK_USD = 1.00
SCOOTER_PER_MIN_USD = 0.39
# Metro Bike Share single-ride ~ $1.75 / 30 min.  Source: bikeshare.metro.net.  # VERIFY before 8/5
BIKE_UNLOCK_USD = 1.75
BIKE_INCLUDED_MIN = 30
BIKE_PER_MIN_OVERAGE_USD = 0.15

# ── Rideshare (modeled estimate) ──────────────────────────────────────────────
# Point estimate for LA UberX/Lyft standard.  These are deliberately stable
# modeled values, not live prices.  Source: composite of published LA-market
# rate cards, 2026-07.  # VERIFY before 8/5
RIDESHARE_BASE_USD = 2.55
RIDESHARE_PER_MILE_USD = 1.05
RIDESHARE_PER_MIN_USD = 0.34
RIDESHARE_MIN_FARE_USD = 8.00
# LAX charges a per-trip pickup surcharge on TNC trips; modeled separately so it
# only applies to LAX legs.  Source: flylax.com TNC info.  # VERIFY before 8/5
LAX_PICKUP_FEE_USD = 4.00

# ── Metro Micro (on-demand microtransit) ──────────────────────────────────────
# Mirrors app/data/metro_micro (kept there as the single source of truth); the
# engine reads it from that module — this constant is only a documentation
# anchor for the cost layer.
METRO_MICRO_FLAT_USD = 2.50  # see app.data.metro_micro.BASE_FARE_USD

_METERS_PER_MILE = 1609.34


def metro_fare(num_taps: int) -> float:
    """Transit fare for `num_taps` boardings, respecting the daily cap."""
    if num_taps <= 0:
        return 0.0
    return round(min(num_taps * METRO_FARE_PER_TAP_USD, METRO_DAILY_CAP_USD), 2)


def _plan_rates(pricing_plans: list[dict] | None) -> tuple[float, float] | None:
    """
    Pull (unlock_usd, per_min_usd) from GBFS system_pricing_plans if usable.

    GBFS `price` is the unlock/base; `per_min_pricing` is a list of tiers with a
    `rate` per `interval` minutes.  We take the first tier as the headline rate.
    Returns None if the plan can't be interpreted, so the caller falls back.
    """
    if not pricing_plans:
        return None
    plan = pricing_plans[0]
    try:
        unlock = float(plan.get("price") or 0.0)
    except (TypeError, ValueError):
        return None
    per_min = 0.0
    tiers = plan.get("per_min_pricing") or []
    if tiers:
        tier = tiers[0]
        try:
            rate = float(tier.get("rate") or 0.0)
            interval = float(tier.get("interval") or 1.0) or 1.0
            per_min = rate / interval
        except (TypeError, ValueError):
            per_min = 0.0
    return unlock, per_min


def micromobility_cost(
    minutes: float, vehicle_type: str = "scooter", pricing_plans: list[dict] | None = None
) -> float:
    """
    Cost of a shared bike/scooter ride of `minutes`, preferring live GBFS pricing.

    Falls back to the documented per-type constants when the provider doesn't
    publish an interpretable pricing plan.
    """
    minutes = max(0.0, minutes)
    rates = _plan_rates(pricing_plans)
    if rates is not None:
        unlock, per_min = rates
        return round(unlock + per_min * minutes, 2)

    if vehicle_type == "bike":
        overage = max(0.0, minutes - BIKE_INCLUDED_MIN)
        return round(BIKE_UNLOCK_USD + overage * BIKE_PER_MIN_OVERAGE_USD, 2)
    # scooter / ebike default
    return round(SCOOTER_UNLOCK_USD + SCOOTER_PER_MIN_USD * minutes, 2)


def rideshare_estimate(distance_m: float, duration_s: float, lax_pickup: bool = False) -> float:
    """Modeled rideshare fare.  `lax_pickup` adds the LAX TNC surcharge."""
    miles = max(0.0, distance_m) / _METERS_PER_MILE
    minutes = max(0.0, duration_s) / 60.0
    fare = RIDESHARE_BASE_USD + RIDESHARE_PER_MILE_USD * miles + RIDESHARE_PER_MIN_USD * minutes
    fare = max(fare, RIDESHARE_MIN_FARE_USD)
    if lax_pickup:
        fare += LAX_PICKUP_FEE_USD
    return round(fare, 2)
