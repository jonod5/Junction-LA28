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
| `METRO_FARE_PER_TAP_USD` | $1.75 | metro.net/riding/fares | ☐ verify |
| `METRO_DAILY_CAP_USD` | $5.00 | metro.net fare-capping | ☐ verify |

## Micromobility fallback pricing — `app/services/fares.py`

Used only when a provider's live GBFS `system_pricing_plans` is unavailable
(live pricing is preferred when present).

| Constant | Value | Source | Status |
|---|---|---|---|
| `SCOOTER_UNLOCK_USD` | $1.00 | typical LA shared-scooter | ☐ verify |
| `SCOOTER_PER_MIN_USD` | $0.39 | typical LA shared-scooter | ☐ verify |
| `BIKE_UNLOCK_USD` | $1.75 / 30 min | bikeshare.metro.net | ☐ verify |
| `BIKE_PER_MIN_OVERAGE_USD` | $0.15 | bikeshare.metro.net | ☐ verify |

## Rideshare (modeled) — `app/services/fares.py`

Deliberately a stable point estimate, not live surge pricing (Uber cost API is
enterprise-gated — deferred, PRD FR-D3).

| Constant | Value | Source | Status |
|---|---|---|---|
| `RIDESHARE_BASE_USD` | $2.55 | composite LA rate cards, 2026-07 | ☐ verify |
| `RIDESHARE_PER_MILE_USD` | $1.05 | composite LA rate cards, 2026-07 | ☐ verify |
| `RIDESHARE_PER_MIN_USD` | $0.34 | composite LA rate cards, 2026-07 | ☐ verify |
| `RIDESHARE_MIN_FARE_USD` | $8.00 | composite LA rate cards, 2026-07 | ☐ verify |
| `LAX_PICKUP_FEE_USD` | $4.00 | flylax.com TNC info | ☐ verify |

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
| `BASE_FARE_USD` | $2.50 | metro.net/riding/metro-micro | ☐ re-confirm |
| `REDUCED_FARE_USD` | $1.00 (senior/disabled/student) | metro.net | ☐ re-confirm |
| `TRANSFER_FARE_USD` | $0.75 (≤2h from Metro bus/rail) | metro.net | ☐ re-confirm |
| `MAX_WAIT_MIN` | 15 | metro.net | ☐ re-confirm |
| Zone polygon: `lax-inglewood` (→ SoFi) | approximate | metro.net/micro | ☐ tighten |
| Zone polygon: `altadena-pasadena-sierra-madre` (→ Rose Bowl) | approximate | metro.net/micro | ☐ tighten |

---

## Live transit (Swiftly GTFS-RT) — `app/ingest/transit_rt.py`

Live **vehicle positions** work via Swiftly (`SWIFTLY_API_KEY`, server-side).
Two follow-ons, not blockers for the demo:

- **Rail feed access** — the `lametro-rail` agency currently returns **403** on
  our key, so rail lines (A/B/C/D/E/K) fall back to "scheduled". Confirm the key
  has rail scope or the correct Swiftly agency slug; adjust `SWIFTLY_AGENCIES`.
- **True delay / next-arrival** — we surface "is the line running live + how many
  vehicles", not per-stop arrival predictions. Those need the GTFS **static**
  schedule loaded (FR-G1) to map a boarding stop → stop_id. Load static, then
  add trip-updates.
- Line label → route matching (`app/ingest/transit_rt.py::line_targets`) uses a
  small rail letter→code map; re-check if Metro renumbers lines before the demo.
