"""
Metro Micro — LA Metro's on-demand microtransit — as a STATIC transit option.

Why static (not live like GBFS): Metro Micro has no public real-time
availability API.  It is a booked, on-demand shuttle within fixed service
zones.  So we model what we *can* state with confidence — the fares and which
of our venues sit inside a zone — and never fake live vehicle positions.

Coverage reality (this is the important constraint for the route engine):
Metro Micro runs in eight discrete zones, but only TWO touch our six venues:
  • LAX/Inglewood                 → SoFi Stadium (venue 2)
  • Altadena/Pasadena/Sierra Madre → Rose Bowl Stadium (venue 6)
The four central venues (Coliseum, Crypto.com Arena, Peacock Theater, Dodger
Stadium) are in NO Micro zone.  The route engine must therefore only propose
Metro Micro for a leg endpoint that actually falls inside one of these two
zones — see `zones_for_point()`.

Zone boundaries here are APPROXIMATE bounding polygons, not Metro's official
GIS.  They are deliberately labeled so the UI and write-ups never present them
as precise.  Hand-verification against metro.net/micro is scheduled for the
Week 7 data-accuracy pass.

Fares verified from metro.net (accessed 2026-07-19).  Re-verify before the
poster deadline.
"""

from dataclasses import asdict, dataclass

# ── Provenance ────────────────────────────────────────────────────────────────
SOURCE_URL = "https://www.metro.net/riding/metro-micro/"
ACCESS_DATE = "2026-07-19"
BOUNDARY_CAVEAT = "approximate, subject to change — metro.net/micro"

# ── Fares & service facts (metro.net, accessed 2026-07-19) ────────────────────
# Flat per-ride fare regardless of trip length inside the zone.
BASE_FARE_USD = 2.50
# Seniors (62+), disabled riders, and students.
REDUCED_FARE_USD = 1.00
# Discount when transferring from Metro bus/rail within 2 hours (TAP-based).
TRANSFER_FARE_USD = 0.75
TRANSFER_WINDOW_MIN = 120
# Typical quoted maximum wait after booking.
MAX_WAIT_MIN = 15
# How far ahead a ride can be booked.
ADVANCE_BOOKING_DAYS = 7
BOOKING_URL = "https://micro.metro.net"
BOOKING_METHODS = ["Metro Micro app", "micro.metro.net", "323-GO-METRO"]
PAYMENT_METHODS = ["TAP card", "credit card"]

# Attribution surfaced in API metadata so the provenance travels with the data.
ATTRIBUTION = (
    "Metro Micro zone and fare data compiled from metro.net "
    f"(accessed {ACCESS_DATE}); zone boundaries are {BOUNDARY_CAVEAT}."
)


@dataclass(frozen=True)
class MetroMicroZone:
    id: str
    name: str
    # Venue ids (see constants/venues) this zone provides access to.
    venue_ids: tuple[int, ...]
    # Approximate boundary as a ring of [lat, lng] vertices (not Metro's GIS).
    polygon: tuple[tuple[float, float], ...]
    boundary_note: str = BOUNDARY_CAVEAT
    source: str = SOURCE_URL
    access_date: str = ACCESS_DATE

    def to_dict(self) -> dict:
        d = asdict(self)
        # JSON-friendly: tuples → lists.
        d["venue_ids"] = list(self.venue_ids)
        d["polygon"] = [list(pt) for pt in self.polygon]
        return d


# Approximate bounding polygons.  Vertices are [lat, lng], counter-clockwise.
# Kept intentionally coarse; the only guarantee we make is "does this point
# plausibly fall in the zone", not precise edge accuracy.
ZONES: list[MetroMicroZone] = [
    MetroMicroZone(
        id="lax-inglewood",
        name="LAX / Inglewood",
        venue_ids=(2,),  # SoFi Stadium
        polygon=(
            (33.900, -118.440),
            (33.900, -118.300),
            (33.985, -118.300),
            (33.985, -118.440),
        ),
    ),
    MetroMicroZone(
        id="altadena-pasadena-sierra-madre",
        name="Altadena / Pasadena / Sierra Madre",
        venue_ids=(6,),  # Rose Bowl Stadium
        polygon=(
            (34.130, -118.200),
            (34.130, -118.030),
            (34.215, -118.030),
            (34.215, -118.200),
        ),
    ),
]


def point_in_polygon(lat: float, lng: float, polygon) -> bool:
    """
    Ray-casting point-in-polygon test.

    Works for the simple convex boxes used here and for any future refined
    (non-self-intersecting) polygon.  Points exactly on an edge may resolve
    either way — acceptable given the boundaries are explicitly approximate.
    """
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        yi, xi = polygon[i]
        yj, xj = polygon[j]
        # Does a horizontal ray at `lat` cross the edge (i, j)?
        if (yi > lat) != (yj > lat):
            x_cross = xi + (lat - yi) * (xj - xi) / (yj - yi)
            if lng < x_cross:
                inside = not inside
        j = i
    return inside


def zones_for_point(lat: float, lng: float) -> list[MetroMicroZone]:
    """Return the Metro Micro zone(s) containing this point (usually 0 or 1)."""
    return [z for z in ZONES if point_in_polygon(lat, lng, z.polygon)]


def is_serviced(lat: float, lng: float) -> bool:
    """True if Metro Micro serves this point at all."""
    return bool(zones_for_point(lat, lng))


def service_at_point(lat: float, lng: float) -> dict:
    """
    Compact, JSON-serializable summary of Metro Micro availability at a point.

    Shape is stable so the route engine (Phase 2) and the UI can both consume
    it, and so shown-vs-chosen logging stays a pure-additive change later.
    """
    zones = zones_for_point(lat, lng)
    return {
        "available": bool(zones),
        "zones": [{"id": z.id, "name": z.name} for z in zones],
        "base_fare_usd": BASE_FARE_USD,
        "reduced_fare_usd": REDUCED_FARE_USD,
        "transfer_fare_usd": TRANSFER_FARE_USD,
        "transfer_window_min": TRANSFER_WINDOW_MIN,
        "max_wait_min": MAX_WAIT_MIN,
        "booking_url": BOOKING_URL,
        "fare_is_estimate": True,
        "attribution": ATTRIBUTION,
    }
