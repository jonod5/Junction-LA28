# Estimates to Verify — before Poster draft #2 (2026-08-05)

Every number below is a **modeled estimate**, not a live quote. The app labels
them as estimates everywhere they appear, but they drift over time and must be
re-checked against their cited source before they show up in the poster or
journal (PRD Week-7 data-accuracy pass; risk note: "re-verify before each
poster/journal deadline").

**How to work this list before 8/5:**

1. `grep -rn "VERIFY before 8/5" app/` — should match every row tagged below.
2. Open each source, confirm or update the value in the code.
3. Bump the `checked` date here (and in the code comment). When a number is
   confirmed against a citable source, you can drop its `# VERIFY` tag.

Last full review: _not yet done_ · Target: **2026-08-05**

---

## Transit fares — `app/services/fares.py`

| Constant | Value | Source | Status |
|---|---|---|---|
| `METRO_FARE_PER_TAP_USD` | $1.75 | metro.net/riding/fares | x verify |
| `METRO_DAILY_CAP_USD` | $5.00 | metro.net fare-capping | x verify |

## Micromobility fallback pricing — `app/services/fares.py`

Used only when a provider's live GBFS `system_pricing_plans` is unavailable
(live pricing is preferred when present).

| Constant | Value | Source | Status |
|---|---|---|---|
| `SCOOTER_UNLOCK_USD` | $1.00 | typical LA shared-scooter | x verify |
| `SCOOTER_PER_MIN_USD` | $0.39 | typical LA shared-scooter | x verify |
| `BIKE_UNLOCK_USD` | $1.75 / 30 min | bikeshare.metro.net | x verify |
| `BIKE_PER_MIN_OVERAGE_USD` | $0.15 | bikeshare.metro.net | x verify |

## Rideshare (modeled) — `app/services/fares.py`

Deliberately a stable point estimate, not live surge pricing (Uber cost API is
enterprise-gated — deferred, PRD FR-D3).

**Confirmed 2026-07-29** against 45 real UberX quotes gathered by hand (own
research — all 15 venue↔venue pairs + all 5 airports×6 venues, price + ETA
captured from the Uber app; see "Verify Uber prices - Sheet1" for the raw
data, plus real driving distances gathered separately for all 45 routes).
The composite-rate-card constants were badly miscalculated — a least-squares
fit against the real quotes shows the old constants underpriced real trips
by a **mean of $20.21/trip** (up to $63 low on the worst case, BUR→SoFi) and
were *never* once too high across all 45 rows.

| Constant | Old value | New value | Source | Status |
|---|---|---|---|---|
| `RIDESHARE_BASE_USD` | $2.55 | **$16.00** | least-squares fit, 15 venue↔venue quotes + real driving distances, 2026-07-29 | done |
| `RIDESHARE_PER_MILE_USD` | $1.05 | **$0.25** | least-squares fit, 15 venue↔venue quotes + real driving distances, 2026-07-29 | done |
| `RIDESHARE_PER_MIN_USD` | $0.34 | **$0.65** | least-squares fit, 15 venue↔venue quotes + real driving distances, 2026-07-29 | done |
| `RIDESHARE_MIN_FARE_USD` | $8.00 | **$9.00** | cheapest real quote observed ($9.95, Crypto.com↔Peacock) | done |

Post-fit residuals: venue↔venue mean abs error ~$3.37/trip (was $20+) — a
large accuracy improvement, though not exact (this is still a point-estimate
model, not live pricing). Re-checked against real driving distances (not the
original haversine proxy) — fit barely moved (base $16.32→$16.35, per-mile
$0.25→$0.20, per-min unchanged), so no further change needed here.

### Airport pickup fee — now per-airport, not LAX-only

`LAX_PICKUP_FEE_USD` (a single flag on `rideshare_estimate()`) has been
replaced with `AIRPORT_PICKUP_FEE_USD: dict[str, float]` and an
`airport_code` parameter, because the first pass (with haversine-estimated
distances) already showed BUR/LGB/VNY carrying a real premium beyond
distance+time that only LAX was being charged. **Re-verified 2026-07-29
against real driving distances** (not haversine) for all 30 airport↔venue
routes — the premium held up: BUR's excess over the venue↔venue model was
*unchanged* switching from haversine to real miles (~$26/trip either way),
confirming it's a genuine premium, not a distance-estimation artifact.

| Airport | Fee | Real-distance excess observed | Status |
|---|---|---|---|
| `LAX` | **$9.00** | mean $8.59/trip (range $0.30–$14.65, n=6) | done |
| `BUR` | **$26.00** | mean $26.04/trip (range $13.68–$45.83, n=6) — small/congested curb + real Sepulveda Pass congestion | done |
| `LGB` | **$4.00** | mean $4.14/trip (range $1.09–$7.69, n=6) | done |
| `VNY` | **$4.00** | mean $3.99/trip (range −$1.49–$6.06, n=6) | done |
| `ONT` | *(none — no fee applied)* | mean $2.28/trip, sometimes negative (range −$10.62–$9.92, n=6) — not distinguishable from noise; ONT trips are long, mostly-freeway routes the base model already explains | done |

`app/services/route_engine.py` now checks proximity against all 5 airports
(`_AIRPORTS` dict, was LAX-only `_LAX`/`_is_lax`) instead of just one.

## Park-and-ride — deferred, not yet in the engine

Removed from the candidate set (2026-07-19) rather than shipped as a
placeholder. A version that just drove to the venue and added a flat buffer
would misrepresent the car-free framing the app exists to communicate.
Re-add once real park-and-ride lot locations and the car-free-zone data those
lots sit outside of are available (PRD FR-R1, FR-C3).

---

## Metro Micro — `app/data/metro_micro.py`

Fares verified from metro.net on **2026-07-19**; re-confirm in the Week-7 pass.
Zone **boundaries** are approximate bounding polygons (labeled "approximate,
subject to change — metro.net/micro"), not Metro's official GIS — the Week-7
pass should tighten them against the published service-area maps.

| Item | Value | Source | Status |
|---|---|---|---|
| `BASE_FARE_USD` | $2.50 | metro.net/riding/metro-micro | x re-confirm |
| `REDUCED_FARE_USD` | $1.00 (senior/disabled/student) | metro.net | x re-confirm |
| `TRANSFER_FARE_USD` | $0.75 (≤2h from Metro bus/rail) | metro.net | x re-confirm |
| `MAX_WAIT_MIN` | 15 | metro.net | ☐ re-confirm |
| Zone polygon: `lax-inglewood` (→ SoFi) | approximate | metro.net/micro | ☐ tighten |
| Zone polygon: `altadena-pasadena-sierra-madre` (→ Rose Bowl) | approximate | metro.net/micro | ☐ tighten |
Add north holywood/burbank for burbank airport
---

## Live transit (Swiftly GTFS-RT) — `app/ingest/transit_rt.py`

Live **vehicle positions** work via Swiftly (`SWIFTLY_API_KEY`, server-side).
One follow-on, not a blocker for the demo:

- ~~**Rail feed access**~~ — **resolved 2026-07-23.** Swiftly approved rail
  scope on our key; `lametro-rail` no longer 403s. Confirmed live against
  `/api/vehicles` (135 rail vehicles, `errors: {}`) and `/api/transit/live`
  (A/E/K lines all report `"status": "live"` with real vehicle counts). No
  code change was needed — `_DEFAULT_AGENCIES` already included
  `lametro-rail`; it was purely blocked on API access, not on logic.
- **True delay / next-arrival** — we surface "is the line running live + how many
  vehicles", not per-stop arrival predictions. Those need the GTFS **static**
  schedule loaded (FR-G1) to map a boarding stop → stop_id. Load static, then
  add trip-updates.
- Line label → route matching (`app/ingest/transit_rt.py::line_targets`) uses a
  small rail letter→code map; re-check if Metro renumbers lines before the demo.
