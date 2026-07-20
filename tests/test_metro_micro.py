"""
Metro Micro static-data guarantees.

The critical correctness property: the engine must ONLY offer Metro Micro where
a point actually falls inside one of the two venue-relevant zones.  SoFi and
the Rose Bowl are inside; the four central venues are not.
"""

from app.data import metro_micro

# Venue coordinates (mirror constants/venues.ts).
SOFI = (33.9535, -118.3392)          # venue 2 — LAX/Inglewood zone
ROSE_BOWL = (34.1613, -118.1676)     # venue 6 — Altadena/Pasadena/Sierra Madre
COLISEUM = (34.0141, -118.2879)      # venue 1 — no zone
CRYPTO = (34.043, -118.2673)         # venue 4 — no zone
PEACOCK = (34.0448, -118.2666)       # venue 5 — no zone
DODGER = (34.0739, -118.24)          # venue 3 — no zone


def test_sofi_is_in_lax_inglewood_zone():
    zones = metro_micro.zones_for_point(*SOFI)
    assert [z.id for z in zones] == ["lax-inglewood"]


def test_rose_bowl_is_in_pasadena_zone():
    zones = metro_micro.zones_for_point(*ROSE_BOWL)
    assert [z.id for z in zones] == ["altadena-pasadena-sierra-madre"]


def test_central_venues_have_no_micro_zone():
    for pt in (COLISEUM, CRYPTO, PEACOCK, DODGER):
        assert metro_micro.zones_for_point(*pt) == []
        assert metro_micro.is_serviced(*pt) is False


def test_service_at_point_shape_and_fares():
    svc = metro_micro.service_at_point(*SOFI)
    assert svc["available"] is True
    assert svc["base_fare_usd"] == 2.50
    assert svc["reduced_fare_usd"] == 1.00
    assert svc["transfer_fare_usd"] == 0.75
    assert svc["fare_is_estimate"] is True
    assert "metro.net" in svc["attribution"]


def test_service_at_point_reports_unavailable_off_zone():
    svc = metro_micro.service_at_point(*COLISEUM)
    assert svc["available"] is False
    assert svc["zones"] == []


def test_zone_to_dict_is_json_friendly():
    z = metro_micro.ZONES[0].to_dict()
    assert isinstance(z["venue_ids"], list)
    assert isinstance(z["polygon"], list)
    assert all(isinstance(pt, list) and len(pt) == 2 for pt in z["polygon"])
    assert "approximate" in z["boundary_note"]
