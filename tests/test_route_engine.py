"""
Route engine — the properties that make it research-grade:

  • deterministic: identical inputs → identical ranking (FR-R2)
  • excluded modes never surface, let alone rank top (FR-R3)
  • feasibility pruning (walk > 2 km, micro > 5 km, GBFS availability)
  • Metro Micro offered only inside its two venue zones (FR-MM3)
  • strictly-dominated options dropped

Directions and GBFS are stubbed so these run offline and are fully controlled.
"""

import pytest

from app.routers.directions import DirectionsError
from app.services import route_engine

# Coordinates well outside any Metro Micro zone (central LA).
ORIGIN = (34.05, -118.25)
DEST = (34.02, -118.29)

# Two points inside the LAX/Inglewood Micro zone (lat 33.90–33.985, lng -118.44..-118.30).
ZONE_A = (33.95, -118.34)
ZONE_B = (33.96, -118.36)


def _transit_result():
    return {
        "mode": "transit",
        "distance_m": 8000,
        "duration_s": 1800,
        "polyline": "T",
        "steps": [
            {"mode": "walking", "distance_m": 600, "duration_s": 480, "polyline": "w1"},
            {"mode": "transit", "distance_m": 6900, "duration_s": 900, "polyline": "t1"},
            {"mode": "walking", "distance_m": 500, "duration_s": 420, "polyline": "w2"},
        ],
    }


# A self-consistent ~7 km leg: walking (6 km) is too far to walk end-to-end and
# cycling (7 km) is past the 5 km micro ceiling, so the interesting options are
# transit (with micro access/egress on its short walk sub-legs) and rideshare.
DEFAULT_DIRECTIONS = {
    "transit": _transit_result(),
    "walking": {"mode": "walking", "distance_m": 6000, "duration_s": 4300, "polyline": "W", "steps": []},
    "bicycling": {"mode": "bicycling", "distance_m": 7000, "duration_s": 1500, "polyline": "B", "steps": []},
    "driving": {"mode": "driving", "distance_m": 7000, "duration_s": 1000, "polyline": "D", "steps": []},
}


def patch_engine(monkeypatch, directions=None, types=None):
    directions = DEFAULT_DIRECTIONS if directions is None else directions
    micro_types = {"scooter", "bike"} if types is None else types

    def fake_fetch(origin, destination, mode, departure_time=None):
        return directions.get(mode)

    monkeypatch.setattr(route_engine, "_api_key", lambda: "TEST_KEY")
    monkeypatch.setattr(route_engine, "fetch_directions", fake_fetch)
    monkeypatch.setattr(
        route_engine, "_micro_snapshot",
        lambda lat, lng: {"types": set(micro_types), "pricing": []},
    )


# ── Determinism (FR-R2) ───────────────────────────────────────────────────────

def test_ranking_is_deterministic(monkeypatch):
    patch_engine(monkeypatch)
    a = route_engine.optimize(ORIGIN, DEST)
    b = route_engine.optimize(ORIGIN, DEST)
    assert [o["id"] for o in a["options"]] == [o["id"] for o in b["options"]]
    assert [o["score"] for o in a["options"]] == [o["score"] for o in b["options"]]


def test_produces_at_least_three_distinct_combinations(monkeypatch):
    patch_engine(monkeypatch)
    res = route_engine.optimize(ORIGIN, DEST)
    labels = {o["label"] for o in res["options"]}
    assert len(labels) >= 3


def test_options_are_capped(monkeypatch):
    patch_engine(monkeypatch)
    res = route_engine.optimize(ORIGIN, DEST)
    assert len(res["options"]) <= route_engine.MAX_OPTIONS


# ── Preferences (FR-R3) ───────────────────────────────────────────────────────

def test_excluded_mode_never_appears(monkeypatch):
    patch_engine(monkeypatch)
    # Traveler is open only to transit + walking.
    res = route_engine.optimize(ORIGIN, DEST, preferences=["transit", "walk"])
    assert res["options"], "expected at least one allowed option"
    for opt in res["options"]:
        assert set(opt["modes"]) <= {"transit", "walk"}


def test_excluded_mode_never_ranks_top(monkeypatch):
    patch_engine(monkeypatch)
    full = route_engine.optimize(ORIGIN, DEST)
    top_modes = set(full["options"][0]["modes"])
    # Exclude whatever the unconstrained winner used; the new winner must avoid it.
    allowed = [m for m in route_engine.MODE_LABEL if m not in top_modes]
    res = route_engine.optimize(ORIGIN, DEST, preferences=allowed)
    if res["options"]:
        assert not (set(res["options"][0]["modes"]) & top_modes)


def test_walk_only_preference_filters_everything_else(monkeypatch):
    # Short leg so a walk-only option is actually feasible.
    directions = dict(DEFAULT_DIRECTIONS)
    directions["walking"] = {"mode": "walking", "distance_m": 1500, "duration_s": 1080, "polyline": "W", "steps": []}
    patch_engine(monkeypatch, directions=directions)
    res = route_engine.optimize(ORIGIN, DEST, preferences=["walk"])
    assert res["options"]
    assert all(o["modes"] == ["walk"] for o in res["options"])


# ── Feasibility pruning ───────────────────────────────────────────────────────

def test_long_walk_is_not_offered(monkeypatch):
    directions = dict(DEFAULT_DIRECTIONS)
    directions["walking"] = {"mode": "walking", "distance_m": 3000, "duration_s": 2200, "polyline": "W", "steps": []}
    patch_engine(monkeypatch, directions=directions)
    res = route_engine.optimize(ORIGIN, DEST, preferences=["walk"])
    assert res["options"] == []  # 3 km walk exceeds the 2 km ceiling


def test_micromobility_gated_on_availability(monkeypatch):
    # No vehicles available anywhere → no bike/scooter modes at all.
    patch_engine(monkeypatch, types=set())
    res = route_engine.optimize(ORIGIN, DEST)
    for opt in res["options"]:
        assert "bike" not in opt["modes"] and "scooter" not in opt["modes"]


def test_micromobility_appears_when_available(monkeypatch):
    patch_engine(monkeypatch)
    res = route_engine.optimize(ORIGIN, DEST)
    all_modes = {m for o in res["options"] for m in o["modes"]}
    assert all_modes & {"bike", "scooter"}


# ── Metro Micro zone gating (FR-MM3) ──────────────────────────────────────────

def test_metro_micro_only_inside_a_shared_zone(monkeypatch):
    patch_engine(monkeypatch)
    # Gating happens at the builder: proposed only when both endpoints share a
    # zone.  (Whether it then survives ranking is a separate dominance question.)
    assert route_engine._build_metro_micro_candidate(ORIGIN, DEST) is None
    inzone = route_engine._build_metro_micro_candidate(ZONE_A, ZONE_B)
    assert inzone is not None
    assert inzone["modes"] == ["metro_micro"]

    # And it is never *proposed* for an off-zone leg through the full pipeline.
    off = route_engine.optimize(ORIGIN, DEST)
    assert all("metro_micro" not in o["modes"] for o in off["options"])


# ── Dominated pruning + scoring internals ─────────────────────────────────────

def test_drop_dominated_removes_worse_on_both_axes():
    cands = [
        {"id": "good", "total_minutes": 10, "total_cost_usd": 2.0},
        {"id": "dominated", "total_minutes": 20, "total_cost_usd": 5.0},
        {"id": "cheap-slow", "total_minutes": 30, "total_cost_usd": 1.0},
    ]
    kept = {c["id"] for c in route_engine._drop_dominated(cands)}
    assert "dominated" not in kept
    assert {"good", "cheap-slow"} <= kept


def test_score_normalisation_bounds():
    cands = [
        {"id": "a", "total_minutes": 10, "total_cost_usd": 1.0, "num_transfers": 0},
        {"id": "b", "total_minutes": 30, "total_cost_usd": 5.0, "num_transfers": 2},
    ]
    ranked = route_engine._score_and_rank(cands)
    # Cheapest + fastest wins; every breakdown norm stays within [0, 1].
    assert ranked[0]["id"] == "a"
    for c in ranked:
        assert 0.0 <= c["score_breakdown"]["time_norm"] <= 1.0
        assert 0.0 <= c["score_breakdown"]["cost_norm"] <= 1.0


# ── Config guard ──────────────────────────────────────────────────────────────

def test_missing_maps_key_raises_500(monkeypatch):
    patch_engine(monkeypatch)
    monkeypatch.setattr(route_engine, "_api_key", lambda: None)
    with pytest.raises(DirectionsError) as exc:
        route_engine.optimize(ORIGIN, DEST)
    assert exc.value.status_code == 500
