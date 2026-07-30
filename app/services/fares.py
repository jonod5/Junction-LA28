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
# Point estimate for LA UberX/Lyft standard, fit by least-squares regression
# against 45 real UberX quotes gathered across all 6 venue pairs + 5 airports
# (own research, gathered 2026-07-29 — see docs/estimates-to-verify.md for the
# full source data and fit residuals).  The previous constants (composite of
# published rate cards) underpriced real trips by a mean of $20/trip, worst
# case >4x low — rate-card base fares don't capture LA's actual traffic-heavy
# per-minute cost.  Confirmed 2026-07-29.
RIDESHARE_BASE_USD = 16.00
RIDESHARE_PER_MILE_USD = 0.25
RIDESHARE_PER_MIN_USD = 0.65
# BASE_USD alone already exceeds this for any non-negative trip, so the floor
# is only reachable for degenerate (zero-distance/duration) inputs — kept as
# an explicit floor rather than relying on that being incidentally true.
RIDESHARE_MIN_FARE_USD = 9.00
# Airports charge/imply a per-trip TNC pickup premium beyond plain
# distance+time — modeled per-airport, not as a single LAX-only flag.
# Refit 2026-07-29 against real driving distances (Google Maps, hand-
# gathered) for all 30 airport<->venue quotes, replacing the earlier
# haversine-based fit: real distances confirmed BUR's premium is genuine
# (barely changed switching from haversine to real miles — ~$26 either way),
# not a distance-estimation artifact. ONT is omitted: its excess over the
# venue<->venue model was ~$0-2 and sometimes negative — not distinguishable
# from noise, i.e. ONT trips are already well explained by distance + time
# alone (long, mostly-freeway routes where the model holds up).
AIRPORT_PICKUP_FEE_USD: dict[str, float] = {
    "LAX": 9.00,   # flylax.com also documents a real LAX TNC pickup fee — consistent with the fit
    "BUR": 26.00,  # by far the largest — small/congested curb, real Sepulveda Pass congestion
    "LGB": 4.00,
    "VNY": 4.00,
}

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
    Pull (unlock_usd, per_min_usd) from a genuinely per-minute-metered GBFS
    plan, if the provider publishes one.

    GBFS `system_pricing_plans` commonly lists membership passes (monthly,
    annual, "24-hour access") ahead of the actual per-ride plan, in whatever
    order the operator happens to publish them — Metro Bike Share's feed, for
    example, lists a $17 monthly pass at index 0.  Blindly taking plans[0]
    would price a single ride at a month's subscription fee.  The only
    unambiguous signal that a plan prices ONE ride is a populated
    per_min_pricing tier, so we scan for the first plan that has one and
    ignore everything else.  Returns None when no such plan exists, so the
    caller falls back to our documented per-type rate — which is also more
    accurate for flat block-rate plans (e.g. Metro Bike Share's actual
    "$1.75 per 30 minutes") that aren't a per-minute plan at all.
    """
    for plan in pricing_plans or []:
        tiers = plan.get("per_min_pricing") or []
        if not tiers:
            continue
        tier = tiers[0]
        try:
            unlock = float(plan.get("price") or 0.0)
            rate = float(tier.get("rate") or 0.0)
            interval = float(tier.get("interval") or 1.0) or 1.0
        except (TypeError, ValueError):
            continue
        return unlock, rate / interval
    return None


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


def rideshare_estimate(distance_m: float, duration_s: float, airport_code: str | None = None) -> float:
    """Modeled rideshare fare.  `airport_code` (e.g. "LAX") adds that airport's pickup fee, if any."""
    miles = max(0.0, distance_m) / _METERS_PER_MILE
    minutes = max(0.0, duration_s) / 60.0
    fare = RIDESHARE_BASE_USD + RIDESHARE_PER_MILE_USD * miles + RIDESHARE_PER_MIN_USD * minutes
    fare = max(fare, RIDESHARE_MIN_FARE_USD)
    fare += AIRPORT_PICKUP_FEE_USD.get(airport_code or "", 0.0)
    return round(fare, 2)
