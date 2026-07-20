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


def test_micromobility_bike_included_minutes():
    # 20 min bike within the 30-min included window → just the unlock.
    assert fares.micromobility_cost(20, "bike", None) == fares.BIKE_UNLOCK_USD


def test_rideshare_applies_minimum_and_lax_fee():
    # Very short trip clamps to the minimum fare.
    assert fares.rideshare_estimate(100, 60) == fares.RIDESHARE_MIN_FARE_USD
    with_lax = fares.rideshare_estimate(100, 60, lax_pickup=True)
    assert with_lax == round(fares.RIDESHARE_MIN_FARE_USD + fares.LAX_PICKUP_FEE_USD, 2)


def test_park_and_ride_uses_venue_price_when_available():
    assert fares.park_and_ride_estimate(12.0) == 12.0
    assert fares.park_and_ride_estimate(None) == fares.PARK_AND_RIDE_DEFAULT_USD
