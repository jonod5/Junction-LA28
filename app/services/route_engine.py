"""
Multimodal route optimization engine — deterministic, no LLM.

Methodology (this docstring is the source for the journal/poster write-up):

1. CANDIDATE GENERATION is compositional, not a hard-coded list.  Each leg is
   modeled as [access] + [backbone] + [egress].  We start from Google's transit
   result (which itself already graph-routes rail/bus with walking access) and
   then compose variants by replacing the leading/trailing walking portion with
   shared micromobility WHERE a live GBFS vehicle is actually available, the
   distance is sensible, AND that walking portion is long enough (≥10 min) that
   riding it is a meaningfully different option — a 4-minute walk swapped for a
   scooter is a near-duplicate of plain transit, not a real alternative.  The
   swapped-in portion keeps the same streets (a scooter/bike takes the same
   route a pedestrian would here) but is relabeled to the vehicle's mode and
   paced at the vehicle's speed, so it renders and reads as "Scooter", not as
   another walk.  Direct single-mode candidates (walk-only, bike/scooter only,
   rideshare, Metro Micro) are added on their own feasibility terms.  So
   combinations like "scooter → rail → walk" or "bike end-to-end" emerge from
   the segment options rather than being enumerated by hand.

2. FEASIBILITY PRUNING only — never taste.  Walk-only is always offered
   (it's free, so it is essentially never strictly dominated, and a traveler
   should be able to see and judge a long walk rather than have it silently
   vanish).  Direct bike-only and scooter-only both ride the same Google
   bicycling route — identical path and time, cost-only difference — subject
   to a ~5 km cap; live GBFS *availability* is not required for these direct
   options, only for the transit access/egress swap-in variants (there a
   specific vehicle genuinely needs to be at the transfer point).  Metro
   Micro is offered only where both endpoints share one of its two
   venue-relevant zones.  We then drop strictly-dominated options (worse on
   BOTH time and cost than some other candidate) and cap the set.  What a
   traveler *prefers* is expressed through preferences + scoring, not by
   pre-filtering the menu.

   Park-and-ride is NOT currently offered as a candidate: modeling it
   correctly needs real park-and-ride lot locations and the car-free-zone
   data those lots sit outside of, neither of which exist yet.  A version that
   just drove to the venue and added a flat time/cost buffer would misrepresent
   the car-free framing the app exists to communicate.  Re-add once that data
   lands (see PRD FR-R1, FR-C3).

3. RANKING is a deterministic weighted score:
       score = w_time·norm(minutes) + w_cost·norm(cost) + w_transfer·transfers
   Time and cost are min-max normalized to 0–1 WITHIN the candidate set first,
   so the two commensurate.  Lower score ranks higher.  Identical inputs always
   produce an identical ranking (stable tie-breaks on time, then cost, then id).
   No language model is anywhere in this path — Gemini may only *explain* the
   already-ranked output later.

Excluded modes are filtered out before scoring, so a mode the traveler opted
out of can never surface as the top recommendation.
"""

from __future__ import annotations

import logging
import re

from app.data import metro_micro
from app.ingest import gbfs
from app.routers.directions import DirectionsError, _api_key, fetch_directions
from app.services import fares

log = logging.getLogger(__name__)

# ── Scoring weights (single source — cited in the methodology) ────────────────
WEIGHTS = {"time": 1.0, "cost": 1.0, "transfer": 0.15}

# ── Feasibility thresholds & speeds ───────────────────────────────────────────
MICRO_MAX_M = 5000         # bike/scooter legs beyond this are not offered
# Below this, swapping a transit leg's walking portion for a scooter/bike
# barely changes the time and produces a near-duplicate option — not worth
# offering as a separate choice.
MICRO_ACCESS_MIN_WALK_S = 600  # 10 minutes
MICRO_ACCESS_RADIUS_M = 300  # a rider will walk this far to reach a vehicle
BIKE_SPEED_MPS = 4.2       # ~15 km/h
SCOOTER_SPEED_MPS = 4.2    # ~15 km/h
METRO_MICRO_WAIT_MIN = metro_micro.MAX_WAIT_MIN

MAX_OPTIONS = 12

# LAX — trips touching it carry the TNC pickup surcharge and are a common
# origin (tourists landing).  Simple radius test.
_LAX = (33.9425, -118.4081)
_LAX_RADIUS_M = 2000

# Human-friendly label per primary mode.
MODE_LABEL = {
    "walk": "Walk",
    "bike": "Bike",
    "scooter": "Scooter",
    "transit": "Transit",
    "metro_micro": "Metro Micro",
    "ridehail": "Rideshare",
}


def _speed(vehicle_type: str) -> float:
    return BIKE_SPEED_MPS if vehicle_type == "bike" else SCOOTER_SPEED_MPS


def _is_lax(lat: float, lng: float) -> bool:
    return gbfs.haversine_m(lat, lng, _LAX[0], _LAX[1]) <= _LAX_RADIUS_M


def _micro_snapshot(lat: float, lng: float) -> dict:
    """
    What shared micromobility is available right at a point.

    Returns {types: set[str], pricing: list[dict]} where types ⊆ {bike, scooter,
    ebike}.  Isolated so tests can stub it without touching GBFS/Redis.
    """
    near = gbfs.get_nearby(lat, lng, MICRO_ACCESS_RADIUS_M)
    types: set[str] = set()
    for item in near["items"]:
        if item["kind"] == "station":
            avail = (item.get("num_bikes_available") or 0) + (item.get("num_ebikes_available") or 0)
            if avail <= 0:
                continue
        types.add(item["vehicle_type"])
    pricing: list[dict] = []
    for plans in near["pricing"].values():
        pricing.extend(plans)
    return {"types": types, "pricing": pricing}


def _label(primary_modes: list[str]) -> str:
    return " → ".join(MODE_LABEL.get(m, m.title()) for m in primary_modes)


def _leg(mode: str, distance_m, duration_s, polyline: str = "", steps: list | None = None) -> dict:
    return {
        "mode": mode,
        "distance_m": distance_m,
        "duration_s": duration_s,
        "polyline": polyline,
        "steps": steps or [],
    }


def _candidate(cid, primary_modes, minutes, cost, transfers, legs, compare_group=None) -> dict:
    return {
        "id": cid,
        "label": _label(primary_modes),
        "modes": primary_modes,
        "total_minutes": round(minutes, 1),
        "total_cost_usd": round(cost, 2),
        "cost_is_estimate": True,
        "num_transfers": transfers,
        "legs": legs,
        # Candidates sharing a compare_group are never allowed to dominate
        # each other (see _drop_dominated) — used for bike vs scooter, which
        # ride the identical route and only differ on cost model; a traveler
        # comparing them wants to see both, not have the cheaper one silently
        # hide the other.
        "compare_group": compare_group,
    }


def _split_walk_ends(steps: list[dict]) -> tuple[list, list, list]:
    """Return (leading_walk_steps, middle_steps, trailing_walk_steps)."""
    n = len(steps)
    i = 0
    while i < n and steps[i].get("mode") == "walking":
        i += 1
    j = n
    while j > i and steps[j - 1].get("mode") == "walking":
        j -= 1
    return steps[:i], steps[i:j], steps[j:]


def _sum(steps: list[dict], field: str) -> float:
    return float(sum(s.get(field, 0) or 0 for s in steps))


def _transit_boardings(steps: list[dict]) -> int:
    return sum(1 for s in steps if s.get("mode") == "transit")


# ── Candidate builders ────────────────────────────────────────────────────────

def _build_transit_candidates(origin, dest, departure_time, o_micro, d_micro) -> list[dict]:
    """Transit baseline + micromobility access/egress variants composed on top."""
    o = f"{origin[0]},{origin[1]}"
    d = f"{dest[0]},{dest[1]}"
    tr = fetch_directions(o, d, "transit", departure_time)
    if not tr:
        return []
    steps = tr["steps"]
    boardings = _transit_boardings(steps)
    if boardings == 0:
        return []  # Google returned a walking fallback — not a transit route

    lead, mid, trail = _split_walk_ends(steps)
    base_min = tr["duration_s"] / 60.0
    base_cost = fares.metro_fare(boardings)
    out: list[dict] = []

    # Baseline transit (incidental walking is not a "primary" mode for filtering).
    out.append(_candidate(
        "transit", ["transit"], base_min, base_cost, max(0, boardings - 1),
        [_leg("transit", tr["distance_m"], tr["duration_s"], tr["polyline"], steps)],
    ))

    lead_m, lead_s = _sum(lead, "distance_m"), _sum(lead, "duration_s")
    trail_m, trail_s = _sum(trail, "distance_m"), _sum(trail, "duration_s")

    def micro_leg_metrics(walk_m, walk_s, walk_steps, vtype, pricing):
        """
        Swap a walking portion for a micro vehicle: same streets, faster pace.

        Returns (duration_s, cost, time_saved_s, relabeled_steps).  The path
        genuinely is the same route a scooter/bike would take, so we keep each
        step's polyline but relabel its mode (so the map colors and the step
        list show "Scooter"/"Bike", not a walk), swap any leading "Walk" in
        the instruction text for the vehicle's name, and scale each step's
        own duration by the same factor the leg total was scaled by —
        otherwise the expanded step list would still read at walking pace.
        """
        micro_s = walk_m / _speed(vtype)
        micro_cost = fares.micromobility_cost(micro_s / 60.0, vtype, pricing)
        scale = micro_s / walk_s if walk_s > 0 else 1.0
        label = MODE_LABEL[vtype]
        relabeled = []
        for s in walk_steps:
            step = {**s, "mode": vtype, "duration_s": round(s.get("duration_s", 0) * scale)}
            instr = step.get("instruction") or ""
            step["instruction"] = re.sub(r"^walk\b", label, instr, count=1, flags=re.IGNORECASE)
            relabeled.append(step)
        return micro_s, micro_cost, (walk_s - micro_s), relabeled

    # Access variant: replace leading walk with an available micro vehicle —
    # only when that walk is long enough for the swap to be a meaningfully
    # different option, not a near-duplicate of the plain transit route.
    access_types = o_micro["types"] if lead_s >= MICRO_ACCESS_MIN_WALK_S and lead_m <= MICRO_MAX_M else set()
    for vtype in sorted(access_types):
        micro_s, micro_cost, saved, relabeled = micro_leg_metrics(lead_m, lead_s, lead, vtype, o_micro["pricing"])
        legs = [
            _leg(vtype, lead_m, micro_s, "", relabeled),
            _leg("transit", tr["distance_m"], tr["duration_s"] - lead_s, tr["polyline"], mid + trail),
        ]
        out.append(_candidate(
            f"transit+{vtype}-access", [vtype, "transit"],
            base_min - saved / 60.0, base_cost + micro_cost, boardings,
            legs,
        ))

    # Egress variant: replace trailing walk with an available micro vehicle.
    egress_types = d_micro["types"] if trail_s >= MICRO_ACCESS_MIN_WALK_S and trail_m <= MICRO_MAX_M else set()
    for vtype in sorted(egress_types):
        micro_s, micro_cost, saved, relabeled = micro_leg_metrics(trail_m, trail_s, trail, vtype, d_micro["pricing"])
        legs = [
            _leg("transit", tr["distance_m"], tr["duration_s"] - trail_s, tr["polyline"], lead + mid),
            _leg(vtype, trail_m, micro_s, "", relabeled),
        ]
        out.append(_candidate(
            f"transit+{vtype}-egress", ["transit", vtype],
            base_min - saved / 60.0, base_cost + micro_cost, boardings,
            legs,
        ))

    # Combined access + egress (single best-available pairing) to keep the set bounded.
    if access_types and egress_types:
        av = sorted(access_types)[0]
        ev = sorted(egress_types)[0]
        a_s, a_cost, a_saved, a_steps = micro_leg_metrics(lead_m, lead_s, lead, av, o_micro["pricing"])
        e_s, e_cost, e_saved, e_steps = micro_leg_metrics(trail_m, trail_s, trail, ev, d_micro["pricing"])
        legs = [
            _leg(av, lead_m, a_s, "", a_steps),
            _leg("transit", tr["distance_m"], tr["duration_s"] - lead_s - trail_s, tr["polyline"], mid),
            _leg(ev, trail_m, e_s, "", e_steps),
        ]
        out.append(_candidate(
            f"transit+{av}-access+{ev}-egress", [av, "transit", ev],
            base_min - (a_saved + e_saved) / 60.0, base_cost + a_cost + e_cost, boardings + 1,
            legs,
        ))
    return out


def _build_direct_candidates(origin, dest, o_micro, d_micro) -> list[dict]:
    o = f"{origin[0]},{origin[1]}"
    d = f"{dest[0]},{dest[1]}"
    out: list[dict] = []

    # Walk-only.  Always offered when a walking route exists — no distance
    # cap.  Walking is free, so it can only be strictly dominated by another
    # free, equal-or-faster option; in practice it always survives pruning
    # and stays visible, letting the traveler judge for themselves whether a
    # long walk is reasonable rather than having it silently disappear.
    walk = fetch_directions(o, d, "walking")
    if walk:
        out.append(_candidate(
            "walk", ["walk"], walk["duration_s"] / 60.0, 0.0, 0,
            [_leg("walk", walk["distance_m"], walk["duration_s"], walk["polyline"], walk["steps"])],
        ))

    # Bike and scooter end-to-end — always offered together (subject to the
    # distance cap), both riding the SAME Google bicycling route, so they
    # share identical path and time; only the cost model differs between
    # them.  Live GBFS pricing is used when available at either endpoint,
    # else the documented fallback per-type rates.  (Live GBFS *availability*
    # still gates the transit access/egress swap-in variants below, where a
    # vehicle genuinely needs to be at the transfer point — direct point-to-
    # point cycling doesn't depend on a specific shared vehicle being nearby
    # at query time.)
    bike = fetch_directions(o, d, "bicycling")
    if bike and bike["distance_m"] <= MICRO_MAX_M:
        pricing = o_micro["pricing"] or d_micro["pricing"]
        minutes = bike["duration_s"] / 60.0
        for vtype in ("bike", "scooter"):
            cost = fares.micromobility_cost(minutes, vtype, pricing)
            out.append(_candidate(
                f"{vtype}-only", [vtype], minutes, cost, 0,
                [_leg(vtype, bike["distance_m"], bike["duration_s"], bike["polyline"], bike["steps"])],
                compare_group="micro-direct",
            ))

    # Rideshare (driving proxy) — always feasible where a road route exists.
    drive = fetch_directions(o, d, "driving")
    if drive:
        lax = _is_lax(*origin) or _is_lax(*dest)
        cost = fares.rideshare_estimate(drive["distance_m"], drive["duration_s"], lax_pickup=lax)
        out.append(_candidate(
            "rideshare", ["ridehail"], drive["duration_s"] / 60.0, cost, 0,
            [_leg("ridehail", drive["distance_m"], drive["duration_s"], drive["polyline"], drive["steps"])],
        ))
    return out


def _build_metro_micro_candidate(origin, dest) -> dict | None:
    """Metro Micro only when BOTH endpoints share one of its two zones."""
    o_zones = {z.id for z in metro_micro.zones_for_point(*origin)}
    d_zones = {z.id for z in metro_micro.zones_for_point(*dest)}
    if not (o_zones & d_zones):
        return None
    o = f"{origin[0]},{origin[1]}"
    d = f"{dest[0]},{dest[1]}"
    drive = fetch_directions(o, d, "driving")
    if not drive:
        return None
    minutes = drive["duration_s"] / 60.0 + METRO_MICRO_WAIT_MIN
    return _candidate(
        "metro-micro", ["metro_micro"], minutes, metro_micro.BASE_FARE_USD, 0,
        [_leg("metro_micro", drive["distance_m"], int(minutes * 60), drive["polyline"], drive["steps"])],
    )


# ── Ranking ───────────────────────────────────────────────────────────────────

def _drop_dominated(cands: list[dict]) -> list[dict]:
    """
    Remove options worse on BOTH time and cost than some other option.

    Candidates sharing a non-None compare_group never dominate each other —
    see _candidate() — so directly-comparable options (bike vs scooter) both
    stay visible for the traveler to weigh, even if one is strictly cheaper.
    """
    kept: list[dict] = []
    for a in cands:
        dominated = False
        for b in cands:
            if b is a:
                continue
            if a.get("compare_group") is not None and a.get("compare_group") == b.get("compare_group"):
                continue
            if (b["total_minutes"] <= a["total_minutes"]
                    and b["total_cost_usd"] <= a["total_cost_usd"]
                    and (b["total_minutes"] < a["total_minutes"]
                         or b["total_cost_usd"] < a["total_cost_usd"])):
                dominated = True
                break
        if not dominated:
            kept.append(a)
    return kept


def _score_and_rank(cands: list[dict]) -> list[dict]:
    if not cands:
        return []
    times = [c["total_minutes"] for c in cands]
    costs = [c["total_cost_usd"] for c in cands]
    tmin, tmax = min(times), max(times)
    cmin, cmax = min(costs), max(costs)
    for c in cands:
        nt = 0.0 if tmax == tmin else (c["total_minutes"] - tmin) / (tmax - tmin)
        nc = 0.0 if cmax == cmin else (c["total_cost_usd"] - cmin) / (cmax - cmin)
        score = WEIGHTS["time"] * nt + WEIGHTS["cost"] * nc + WEIGHTS["transfer"] * c["num_transfers"]
        c["score"] = round(score, 4)
        c["score_breakdown"] = {
            "time_norm": round(nt, 3),
            "cost_norm": round(nc, 3),
            "num_transfers": c["num_transfers"],
            "weights": WEIGHTS,
        }
    # Deterministic ordering: lower score first, stable tie-breaks.
    cands.sort(key=lambda c: (c["score"], c["total_minutes"], c["total_cost_usd"], c["id"]))
    return cands


def _allowed(candidate: dict, preferences: set[str] | None) -> bool:
    if not preferences:
        return True
    return all(m in preferences for m in candidate["modes"])


def optimize(
    origin: tuple[float, float],
    destination: tuple[float, float],
    preferences: list[str] | None = None,
    departure_time: int | None = None,
) -> dict:
    """
    Rank multimodal options for one origin→destination leg.  Deterministic.

    `preferences` is the set of allowed primary mode keys (see MODE_LABEL); a
    candidate using any mode outside it is filtered out before scoring.  Empty
    or None means "all modes allowed".
    """
    # A missing Maps key is a server misconfiguration, not a per-candidate miss.
    if not _api_key():
        raise DirectionsError("Maps API key not configured", status_code=500)

    prefs = set(preferences) if preferences else None

    o_micro = _micro_snapshot(*origin)
    d_micro = _micro_snapshot(*destination)

    cands: list[dict] = []
    # Each builder swallows "no route" (None) internally; upstream failures for a
    # single mode shouldn't sink the whole request, so guard per group.
    for builder in (
        lambda: _build_transit_candidates(origin, destination, departure_time, o_micro, d_micro),
        lambda: _build_direct_candidates(origin, destination, o_micro, d_micro),
    ):
        try:
            cands.extend(builder())
        except DirectionsError as exc:
            if exc.status_code == 500:
                raise
            log.warning("Route candidate group failed: %s", exc.detail)

    mm = None
    try:
        mm = _build_metro_micro_candidate(origin, destination)
    except DirectionsError as exc:
        if exc.status_code == 500:
            raise
        log.warning("Optional candidate failed: %s", exc.detail)
    if mm:
        cands.append(mm)

    # Feasibility set is built; now apply preferences, dominance, cap, and score.
    cands = [c for c in cands if _allowed(c, prefs)]
    cands = _drop_dominated(cands)
    ranked = _score_and_rank(cands)[:MAX_OPTIONS]

    return {
        "origin": {"lat": origin[0], "lng": origin[1]},
        "destination": {"lat": destination[0], "lng": destination[1]},
        "departure_time": departure_time,
        "preferences": sorted(prefs) if prefs else None,
        "weights": WEIGHTS,
        "count": len(ranked),
        "options": ranked,
        "notes": [
            "All costs are modeled estimates, not quotes.",
            gbfs.ATTRIBUTION,
        ],
    }
