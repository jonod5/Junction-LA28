"""Cost model — figures are estimates, but the arithmetic must be exact."""

from app.services import fares


def test_metro_fare_respects_daily_cap():
    assert fares.metro_fare(0) == 0.0
    assert fares.metro_fare(1) == 1.75
    assert fares.metro_fare(2) == 3.50
    # 4 taps would be $7.00 but the daily cap holds it at $5.00.
    assert fares.metro_fare(4) == 5.00
    assert fares.metro_fare(10) == 5.00


def test_micromobility_prefers_live_pricing():
    plans = [{"price": 0.50, "per_min_pricing": [{"start": 0, "rate": 0.30, "interval": 1}]}]
    # 10 min → 0.50 unlock + 10 * 0.30 = 3.50
    assert fares.micromobility_cost(10, "scooter", plans) == 3.50


def test_micromobility_falls_back_when_no_plan():
    # scooter default: 1.00 unlock + 0.39/min
    assert fares.micromobility_cost(10, "scooter", None) == round(1.00 + 3.9, 2)


def test_micromobility_skips_subscription_plans_with_no_per_minute_rate():
    # Regression: real GBFS feeds (e.g. Metro Bike Share) list membership
    # passes ahead of the actual single-ride plan, with no reliable field
    # order. A $17 monthly pass at index 0 must never get priced as if it
    # were a single ride — none of these plans has per_min_pricing, so the
    # engine must fall back to the documented per-type rate, not plans[0].
    plans = [
        {"plan_id": "monthly", "price": 17.0, "per_min_pricing": None},
        {"plan_id": "annual", "price": 150.0, "per_min_pricing": None},
        {"plan_id": "single-ride", "price": 1.75, "per_min_pricing": None},
    ]
    cost = fares.micromobility_cost(20, "bike", plans)
    assert cost == fares.BIKE_UNLOCK_USD  # fallback, not $17 or $150


def test_micromobility_finds_metered_plan_past_subscriptions():
    # A subscription plan precedes the real per-minute plan — the metered
    # one must still be found and used, not skipped just for not being first.
    plans = [
        {"plan_id": "monthly", "price": 17.0, "per_min_pricing": None},
        {"plan_id": "pay-per-ride", "price": 0.50, "per_min_pricing": [{"start": 0, "rate": 0.30, "interval": 1}]},
    ]
    assert fares.micromobility_cost(10, "scooter", plans) == 3.50


def test_micromobility_bike_included_minutes():
    # 20 min bike within the 30-min included window → just the unlock.
    assert fares.micromobility_cost(20, "bike", None) == fares.BIKE_UNLOCK_USD


def test_rideshare_computes_from_distance_and_duration():
    miles, minutes = 2.0, 10.0
    expected = round(
        fares.RIDESHARE_BASE_USD
        + fares.RIDESHARE_PER_MILE_USD * miles
        + fares.RIDESHARE_PER_MIN_USD * minutes,
        2,
    )
    assert fares.rideshare_estimate(miles * fares._METERS_PER_MILE, minutes * 60) == expected


def test_rideshare_applies_airport_fee():
    fare = fares.rideshare_estimate(1000, 300)
    with_lax = fares.rideshare_estimate(1000, 300, airport_code="LAX")
    assert round(with_lax - fare, 2) == fares.AIRPORT_PICKUP_FEE_USD["LAX"]


def test_rideshare_no_fee_for_unlisted_airport():
    # ONT is deliberately not in the fee table — its measured excess wasn't
    # distinguishable from noise (see fares.py comment).
    fare = fares.rideshare_estimate(1000, 300)
    ont = fares.rideshare_estimate(1000, 300, airport_code="ONT")
    assert ont == fare


def test_rideshare_clamps_to_minimum_fare(monkeypatch):
    # RIDESHARE_BASE_USD alone exceeds RIDESHARE_MIN_FARE_USD under the
    # current calibration, so the floor is never normally reached — isolate
    # the max()-clamp logic itself from that calibration to confirm it still
    # holds if the base ever drops below the floor again.
    monkeypatch.setattr(fares, "RIDESHARE_BASE_USD", 1.0)
    monkeypatch.setattr(fares, "RIDESHARE_PER_MILE_USD", 0.0)
    monkeypatch.setattr(fares, "RIDESHARE_PER_MIN_USD", 0.0)
    assert fares.rideshare_estimate(0, 0) == fares.RIDESHARE_MIN_FARE_USD
