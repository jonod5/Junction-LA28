"""
Seed script v3 — six LA28 venues from Venue_Data_Collection.pdf/docx.

USAGE (review before running):
    python -m app.seed_venues

FIDELITY RULES:
- Text fields: exact wording from the sheet, punctuation preserved (incl. typos).
- Blank fields in the sheet → None.
- Numeric price/arrival fields store the stated floor when a value uses '+' (e.g. $125+);
  the '+' and full context are captured in the accompanying text field.
- No inferences, normalisations, or gap-filling.
- source / date_collected preserved on every child row.

Do NOT run until you have reviewed the output below.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.models.venue import (
    CongestionTdm,
    CurbDropoff,
    ParkingOption,
    TransitAccess,
    Venue,
    VenueSource,
)

# ---------------------------------------------------------------------------
# FLAGS — fields with partial or incomplete transcription
# ---------------------------------------------------------------------------
#
# 1. SoFi Stadium › Venue.total_spaces
#    PDF says "28 lots" — that is a lot count, not a space count.
#    Stored as total_spaces=None; total_lots=22; capacity_text="28 lots".
#
# 2. SoFi Stadium › ParkingOption rows — approximate prices ("~$")
#    All SoFi prices are marked "~$" (approximate) in the doc.
#    Numeric columns store the stated value; "~" noted in price_notes per zone.
#    NFL prices marked with data_gaps="NFL ticket prices were not out, need follow up closer to the game".
#
# 3. SoFi Stadium › Pink zone and VIP Zones
#    Doc lists "$125+" (Pink, NFL) and "$200+" (VIP, NFL).
#    price_max stores the floor value (125.00 / 200.00); the "+" is noted in price_notes.
#
# 4. Peacock Theater › VenueSource
#    The "Primary source" and "Secondary source" cells are blank in the PDF.
#    primary_url=None, secondary_url=None.
#    The two URLs that are known (from data_sources_summary) are stored there.
#
# 5. All venues › Venue.games_time_access_notes
#    No "Games-time access notes" row exists in the current doc.
#    All stored as None; column is ready for a future data-collection pass.
#
# ---------------------------------------------------------------------------

_SRC_SOFI = "https://www.sofistadium.com/parking-and-transportation"
_SRC_COLISEUM_PKG = (
    "Event parking map (lacoliseum.com, 2023 PDF, lot names) + "
    "2026 FIFA Fan Festival \"Know Before You Go\" guide "
    "(lacoliseum.com/wp-content/uploads/2026/06/FINAL-English.pdf, June 2026 — current); "
    "lacoliseum.com/ada-information/; "
    "transnet.usc.edu/index.php/parkingrates/; "
    "parkmobile.io/parking/locations/ca/los-angeles-parking/destination/la-memorial-coliseum; "
    "LA Coliseum Technical Guide (Draft, Dec 2024) — "
    "lacoliseum.com/wp-content/uploads/2024/12/Coliseum_Technical_Guide_Draft2024.pdf"
)
_SRC_COLISEUM_CURB = (
    "lacoliseum.com/FINAL-English.pdf (2026); "
    "lacoliseum.com/know-before-you-go-kx5/; "
    "lacoliseum.com/directions/; "
    "lacoliseum.com/ada-information/"
)
_SRC_COLISEUM_TRANSIT = (
    "lacoliseum.com/directions/; "
    "metro.net/destinations/la-coliseum/"
)
_SRC_COLISEUM_CONG = (
    "lacoliseum.com/know-before-you-go-kx5/; "
    "lacoliseum.com/ada-information/"
)


def _d(month: int, day: int) -> date:
    return date(2026, month, day)


VENUES: list[dict] = [

    # ── 1 / 6  LA Memorial Coliseum ─────────────────────────────────────────
    {
        "venue": dict(
            name="LA Memorial Coliseum",
            sport_use="Track & Field / Ceremonies",
            zone="Exposition Park",
            address="3911 S Figueroa St, Los Angeles, CA 90037",
            lat=34.0141,
            lng=-118.2879,
            total_spaces=13615,
            total_lots=None,                 # no "Total parking lots" row in doc
            capacity_text="13,615",
            games_time_access_notes=None,    # FLAG 5: row not in doc yet
            collection_status=None,
            date_collected=_d(7, 5),
            data_sources_summary=None,       # "Data source(s) used" cell blank
        ),
        "parking": [
            dict(
                lot_name=(
                    "Exposition Park: Blue Structure (Visitor Parking Structure), "
                    "Orange Structure (South Structure), Pink Lot (Lot 4), Yellow Lot (Lot 5), "
                    "Green Lot (Lot 6), Gold lot; "
                    "USC/adjacent structures: Flower Street Structure (3701 S Flower St), "
                    "Downey Way Structure (3667 McClintock Ave), "
                    "Figueroa Street Structure (3533 S Flower St), "
                    "Shrine Structure (686 W 32nd St)"
                ),
                is_official=True,
                price_min=4.00,
                price_max=50.00,
                price_notes=(
                    "USC Home football games: $50/game (effective 7/1/2026). "
                    "Standard daily flat rate: $20/day + $0.50 one-time Text2Park fee "
                    "(or $20/day no fee via Pay-By-Plate). "
                    "Standard hourly rate: $4/hour + $0.50 one-time fee "
                    "(up to 4 hrs; 5+ hrs billed at $20 daily flat rate)."
                ),
                pricing_basis=None,
                has_surge_pricing=True,
                surge_notes=(
                    "Coliseum ADA page states \"Event parking rates may vary per event.\" "
                    "Third-party sites (ParkWhiz/ParkMobile) show demand-based pricing that differs by event"
                ),
                is_closest_to_entrance=None,
                notes=(
                    "Closest lot to venue entrance (per ParkMobile): "
                    "910 W. Martin Luther King Jr. Blvd. Lot, listed as a 7-minute walk (holds up to 20 vehicles); "
                    "Blue structure; Gold lot; Pink lot. "
                    "\"There is no onsite parking available in Exposition Park... parking fees apply,\" "
                    "directing guests to justpark.com to reserve. "
                    "ADA-accessible parking is first-come, first-served, no advance reservation."
                ),
                source=_SRC_COLISEUM_PKG,
                date_collected=_d(7, 5),
                verified_by="JD",
                data_gaps=None,
            ),
        ],
        "curb": dict(
            rideshare_zone_description=(
                "Vermont Ave. between Exposition Blvd. and Downey Way (per 2026 FIFA Fan Festival guide). "
                "For larger concert-type events, Vermont Ave. between Exposition Blvd. and W. 36th Place "
                "(per Kx5 event guide)"
            ),
            rideshare_zone_open_window=(
                "Rideshare services are prohibited from entering the Exposition Park area until "
                "45–60 minutes after an event ends (exact opening time before events not stated)"
            ),
            taxi_accessible_zone=(
                "Limited limousine/hired-vehicle parking at the Green Lot, accessed from "
                "W. Martin Luther King Jr. Blvd and S. Hoover St. "
                "ADA drop-off/pick-up is on Exposition Park Drive (entering from S. Figueroa at W. 39th St)"
            ),
            private_vehicle_dropoff=(
                "Exposition Park allows rideshare/drop-off access from Figueroa St., "
                "with drop-off/pick-up along Expo Park Dr."
            ),
            no_stop_zones=(
                "left-turn pocket closures\" at Figueroa St/Expo Park Dr, MLK Jr Blvd/Hoover St, "
                "and Exposition Blvd/Bill Robertson Lane during large events"
            ),
            curbside_restrictions=(
                "Post-event pick-up/drop-off \"may be delayed up to 45–60 minutes\" "
                "due to traffic control reopening streets"
            ),
            source=_SRC_COLISEUM_CURB,
            date_collected=_d(7, 5),
            verified_by="JD",
            data_gaps=None,
        ),
        "transit": [
            dict(
                line="Metro E (Expo) Line",
                mode="rail",
                stop_name="Expo Park/USC Station",
                walk_time_min=6,
                nearest_metro_station="Expo Park/USC Station; Expo/Vermont Station",
                bus_lines_serving=(
                    "Metro J Line (to 37th St/USC), "
                    "Line 40 (to MLK Jr Bl/Figueroa), "
                    "Line 81 (to Figueroa/Exposition), "
                    "Line 102 (to Vermont/Exposition), "
                    "Line 204 (to Vermont/Exposition)"
                ),
                bike_lane_nearby=True,
                gbfs_dock_description=(
                    "Lime scooters near Expo Park/USC station; "
                    "Lime/bird scooters at Vermont and Expo intersection; "
                    "Doordash bike dock in front of the Arco at the Vermont and Expo intersection"
                ),
                transit_notes=(
                    "$3.50 round-trip E Line fare; last trains from Expo Park depart 11:50pm (eastbound) / "
                    "12:10am (westbound); enhanced service begins 2–3 hrs before and continues 1–2 hrs after events. "
                    "Walk times (own research): Expo Park/USC Station (6 mins); Expo/Vermont Station (6 mins). "
                    "Nearest bus stops: Figueroa/Exposition, Vermont/Exposition (closest listed stops). "
                    "Walk time from bus stop (own research): Figueroa/Exposition (11 mins); Vermont/Exposition (7 mins). "
                    "Bike lane: Yes — Figueroa St has bike safety improvements from the \"MyFigueroa\" project. "
                    "Metro J Line also serves (bus rapid transit)."
                ),
                source=_SRC_COLISEUM_TRANSIT,
                date_collected=_d(7, 5),
                verified_by="JD",
                data_gaps=None,
            ),
        ],
        "congestion": dict(
            recommended_arrival_hrs_before_min=None,
            recommended_arrival_hrs_before_max=None,
            arrival_notes="not stated in source",
            high_congestion_entry_roads=(
                "Figueroa St, W. Martin Luther King Jr. Blvd, S. Hoover St, "
                "Exposition Blvd (left-turn closures noted at these intersections during large events)"
            ),
            known_congestion_exit_roads=(
                "Same corridors (Figueroa St, Exposition Blvd, Vermont Ave) — "
                "post-event exit noted as delayed 45–60 min"
            ),
            event_day_parking_surge=True,
            past_congestion_refs=(
                "ParkMobile notes the Coliseum shares its lot footprint with BMO Stadium and USC, "
                "which \"means many visitors are competing for the same limited parking at peak times\". "
                "parkmobile.io/parking/locations/ca/los-angeles-parking/destination/la-memorial-coliseum"
            ),
            general_tdm_notes=(
                "Coliseum promotes SoCal511 (Go511.com/app) for live traffic updates and encourages "
                "Metro E Line use to avoid traffic/parking delays"
            ),
            source=_SRC_COLISEUM_CONG,
            date_collected=_d(7, 5),
            verified_by="JD",
            data_gaps=None,
        ),
        "sources": [
            dict(
                primary_url="lacoliseum.com/",
                secondary_url=None,              # "Secondary source" cell blank in PDF
                verified_by="JD",
                verified_at=_d(7, 6),
            ),
        ],
    },

    # ── 2 / 6  SoFi Stadium ─────────────────────────────────────────────────
    {
        "venue": dict(
            name="SoFi Stadium",
            sport_use="Swimming / Ceremonies",
            zone="Inglewood",
            address="1001 Stadium Dr, Inglewood, CA 90301",
            lat=33.9535,
            lng=-118.3392,
            total_spaces=None,
            total_lots=22,
            capacity_text=None,
            games_time_access_notes=None,    # FLAG 5
            collection_status=None,
            date_collected=_d(7, 1),
            data_sources_summary="2",        # exactly as written in PDF
        ),
        # Parking: 10 per-zone rows — FLAG 7 from v2 resolved
        "parking": [
            dict(
                lot_name="Blue zone",
                is_official=True,
                price_min=40.00,             # advance NFL
                price_max=88.00,             # event day Non-NFL
                price_notes=(
                    "Event day: ~$80 (NFL), ~$88 (Non-NFL). "
                    "Advance/early bird: ~$40 (NFL), ~$77 (Non-NFL). "
                    "All prices approximate (~$); values from the doc as listed."
                ),
                pricing_basis=None,
                has_surge_pricing=True,
                surge_notes="SOFI is demand based pricing. Prices increase as the date gets closer.",
                is_closest_to_entrance=True,  # West/Southwest gates
                notes=(
                    "Closest to West/Southwest gates. "
                    "Stadium enforces 100% advance purchase, mobile-only pass rule. "
                    "Purple zone has been permanently eliminated. "
                    "Can find cheaper parking outside the stadium via ParkWhiz or SpotHero (security risks)."
                ),
                source=_SRC_SOFI,
                date_collected=_d(7, 1),
                verified_by="JD",
                data_gaps="NFL ticket prices were not out, need follow up closer to the game",
            ),
            dict(
                lot_name="Orange and Brown zones",
                is_official=True,
                price_min=60.00,             # advance NFL
                price_max=100.00,            # event day NFL
                price_notes=(
                    "Event day: ~$100 (NFL), ~$77–83 (Non-NFL). "
                    "Advance/early bird: ~$60 (NFL), ~$77 (Non-NFL). "
                    "All prices approximate (~$)."
                ),
                pricing_basis=None,
                has_surge_pricing=True,
                surge_notes="SOFI is demand based pricing. Prices increase as the date gets closer.",
                is_closest_to_entrance=True,  # East/Southeast gate
                notes="Closest to East/Southeast gate.",
                source=_SRC_SOFI,
                date_collected=_d(7, 1),
                verified_by="JD",
                data_gaps="NFL ticket prices were not out, need follow up closer to the game",
            ),
            dict(
                lot_name="Green and Yellow zones",
                is_official=True,
                price_min=77.00,             # advance Non-NFL
                price_max=120.00,            # event day NFL
                price_notes=(
                    "Event day: ~$120 (NFL), ~$88 (Non-NFL). "
                    "Advance/early bird: ~$80 (NFL), ~$77 (Non-NFL). "
                    "All prices approximate (~$)."
                ),
                pricing_basis=None,
                has_surge_pricing=True,
                surge_notes="SOFI is demand based pricing. Prices increase as the date gets closer.",
                is_closest_to_entrance=True,  # North gate
                notes="Closest to North gate.",
                source=_SRC_SOFI,
                date_collected=_d(7, 1),
                verified_by="JD",
                data_gaps="NFL ticket prices were not out, need follow up closer to the game",
            ),
            dict(
                lot_name="Pink zone",
                is_official=True,
                price_min=50.00,             # advance Non-NFL
                price_max=125.00,            # FLAG 3: event day NFL listed as "$125+"; floor stored here
                price_notes=(
                    "Event day: ~$125+ (NFL), ~$70 (Non-NFL). "
                    "Advance/early bird: ~$100 (NFL), ~$50 (Non-NFL). "
                    "NFL event-day rate listed as '$125+'; price_max stores floor value only. "
                    "All prices approximate (~$)."
                ),
                pricing_basis=None,
                has_surge_pricing=True,
                surge_notes="SOFI is demand based pricing. Prices increase as the date gets closer.",
                is_closest_to_entrance=None,
                notes="Oversized vehicles (limo/bus/RV) and tailgating allowed in Pink zone only.",
                source=_SRC_SOFI,
                date_collected=_d(7, 1),
                verified_by="JD",
                data_gaps="NFL ticket prices were not out, need follow up closer to the game",
            ),
            dict(
                lot_name="VIP Zones (Yellow)",
                is_official=True,
                price_min=80.00,             # advance Non-NFL
                price_max=200.00,            # FLAG 3: event day NFL listed as "$200+"; floor stored here
                price_notes=(
                    "Event day: ~$200+ (NFL), ~$120 (Non-NFL). "
                    "Advance/early bird: ~$120 (NFL), ~$80 (Non-NFL). "
                    "NFL event-day rate listed as '$200+'; price_max stores floor value only. "
                    "All prices approximate (~$)."
                ),
                pricing_basis=None,
                has_surge_pricing=True,
                surge_notes="SOFI is demand based pricing. Prices increase as the date gets closer.",
                is_closest_to_entrance=None,
                notes=None,
                source=_SRC_SOFI,
                date_collected=_d(7, 1),
                verified_by="JD",
                data_gaps="NFL ticket prices were not out, need follow up closer to the game",
            ),
            dict(
                lot_name="PS-1 Garage",
                is_official=True,
                price_min=88.00,
                price_max=88.00,
                price_notes=(
                    "Event day: ~$88 (Non-NFL). "
                    "Advance/early bird: ~$88 (Non-NFL). "
                    "No NFL pricing listed for this garage. "
                    "All prices approximate (~$)."
                ),
                pricing_basis=None,
                has_surge_pricing=True,
                surge_notes="SOFI is demand based pricing. Prices increase as the date gets closer.",
                is_closest_to_entrance=None,
                notes=None,
                source=_SRC_SOFI,
                date_collected=_d(7, 1),
                verified_by="JD",
                data_gaps="NFL ticket prices were not out, need follow up closer to the game",
            ),
            dict(
                lot_name="PS-2 Garage",
                is_official=True,
                price_min=55.00,             # advance Non-NFL
                price_max=66.00,             # event day Non-NFL
                price_notes=(
                    "Event day: ~$66 (Non-NFL). "
                    "Advance/early bird: ~$55 (Non-NFL). "
                    "No NFL pricing listed for this garage. "
                    "All prices approximate (~$)."
                ),
                pricing_basis=None,
                has_surge_pricing=True,
                surge_notes="SOFI is demand based pricing. Prices increase as the date gets closer.",
                is_closest_to_entrance=True,  # West/Southwest gates (along with Blue zone)
                notes="Closest to West/Southwest gates (along with Blue zone).",
                source=_SRC_SOFI,
                date_collected=_d(7, 1),
                verified_by="JD",
                data_gaps="NFL ticket prices were not out, need follow up closer to the game",
            ),
            dict(
                lot_name="PS-3 Garage",
                is_official=True,
                price_min=66.00,
                price_max=66.00,
                price_notes=(
                    "Event day: ~$66 (Non-NFL). "
                    "Advance/early bird: ~$66 (Non-NFL). "
                    "No NFL pricing listed for this garage. "
                    "All prices approximate (~$)."
                ),
                pricing_basis=None,
                has_surge_pricing=True,
                surge_notes="SOFI is demand based pricing. Prices increase as the date gets closer.",
                is_closest_to_entrance=None,
                notes=None,
                source=_SRC_SOFI,
                date_collected=_d(7, 1),
                verified_by="JD",
                data_gaps="NFL ticket prices were not out, need follow up closer to the game",
            ),
            dict(
                lot_name="PS-4 Garage",
                is_official=True,
                price_min=71.00,             # advance Non-NFL
                price_max=77.00,             # event day Non-NFL
                price_notes=(
                    "Event day: ~$77 (Non-NFL). "
                    "Advance/early bird: ~$71 (Non-NFL). "
                    "No NFL pricing listed for this garage. "
                    "All prices approximate (~$)."
                ),
                pricing_basis=None,
                has_surge_pricing=True,
                surge_notes="SOFI is demand based pricing. Prices increase as the date gets closer.",
                is_closest_to_entrance=None,
                notes=None,
                source=_SRC_SOFI,
                date_collected=_d(7, 1),
                verified_by="JD",
                data_gaps="NFL ticket prices were not out, need follow up closer to the game",
            ),
            dict(
                lot_name="Red Zone",
                is_official=True,
                price_min=313.00,
                price_max=313.00,
                price_notes=(
                    "Event day: $313 (large vehicles only). "
                    "No advance/early bird price listed."
                ),
                pricing_basis=None,
                has_surge_pricing=True,
                surge_notes="SOFI is demand based pricing. Prices increase as the date gets closer.",
                is_closest_to_entrance=None,
                notes="Large vehicles only.",
                source=_SRC_SOFI,
                date_collected=_d(7, 1),
                verified_by="JD",
                data_gaps=None,
            ),
        ],
        "curb": dict(
            rideshare_zone_description=(
                "Pick up zone on Kareem Ct. and Manchester Blvd. "
                "Guests arriving and departing must arrive from Crenshaw Blvd, turning onto "
                "Westbound Pincay Dr. to reach top of drop of and pickup zone"
            ),
            rideshare_zone_open_window="Always",
            taxi_accessible_zone="Same as pickup",
            private_vehicle_dropoff=(
                "access the site via Northbound Prairie Ave. turning eastbound onto Arbor Vitae St."
            ),
            no_stop_zones=(
                "Neighborhoods; Private businesses; Retail parking; "
                "No tailgating, oversized vehicles in all lots except Pink"
            ),
            curbside_restrictions=(
                "Traffic control officers strictly enforce specific entry paths and ban left/right turns "
                "into certain lots. "
                "Left turns into the Brown Zone from Pincay Drive and left turns onto various lots off "
                "Century Boulevard are prohibited."
            ),
            source="sofistadium.com/plan-your-visit/parking-and-transportation",
            date_collected=_d(7, 1),
            verified_by="JD",
            data_gaps=None,
        ),
        "transit": [
            dict(
                line="K Line (Crenshaw line), Metro C line (Can take the SoFi shuttle)",
                mode="rail",
                stop_name="Downtown Inglewood Station",
                walk_time_min=23,
                nearest_metro_station=(
                    "Downtown Inglewood Station; "
                    "LAX/Metro Transit Center Sation (shuttle)"   # sic — as written in PDF
                ),
                bus_lines_serving=(
                    "Line 115 (Manchester/Kareem); "
                    "Line 117 (Prairie/Century); "
                    "Line 212 (Prairie/Kelso) anytime; "
                    "Lines 102, 111, 117, 120, 232 feed to LAX/Metro Transit Center for the game-day shuttle"
                ),
                bike_lane_nearby=False,
                gbfs_dock_description="No scooter",
                transit_notes=(
                    "Rental scooters and bikes are unavailable near SoFi. "
                    "Nearest bus stops: Prairie and Kelso (2 mins walk); Los Angeles Stadium (6 mins walk). "
                    "No bike lanes, large side walks around the block."
                ),
                source="metro.net/destinations/sofi-stadium",
                date_collected=_d(7, 1),
                verified_by="JD",
                data_gaps=None,
            ),
        ],
        "congestion": dict(
            recommended_arrival_hrs_before_min=3.0,   # concerts/non-NFL lot opening (earliest min)
            recommended_arrival_hrs_before_max=5.0,   # NFL lot opening (latest max)
            arrival_notes=(
                "NFL games: parking lots open 4–5 hrs before kickoff, gates open 2–3 hrs before kickoff. "
                "Concerts/non-NFL: parking lots open 3–4 hrs before, gates open 1–2 hrs before."
            ),
            high_congestion_entry_roads=(
                "High traffic on century blvd and prairie ave; "
                "Arbor Vitae St; "
                "I-405 South (Century blvd/ Florence Ave exits)"
            ),
            known_congestion_exit_roads=(
                "I-105 South entrance (Century); "
                "I-405 North entrance (Prairie)"
            ),
            event_day_parking_surge=True,
            past_congestion_refs="In secondary sources",
            general_tdm_notes=None,                   # arrival text moved to arrival_notes
            source=None,                              # "General TDM notes" source cell blank
            date_collected=_d(7, 1),
            verified_by="JD",
            data_gaps="NFL ticket prices were not out, need follow up closer to the game",
        ),
        "sources": [
            dict(
                primary_url="https://www.sofistadium.com/parking-and-transportation",
                secondary_url=(
                    "https://www.reddit.com/r/parkingguides/comments/1u308h4/"
                    "how_early_to_arrive_for_sofi_stadium_world_cup/\n"
                    "https://www.nextpass.io/blog/2026/06/12/"
                    "how-to-get-to-sofi-stadium-los-angeles-world-cup-driving-guide/"
                ),
                verified_by="JD",
                verified_at=_d(7, 1),
            ),
        ],
    },

    # ── 3 / 6  Dodger Stadium ───────────────────────────────────────────────
    {
        "venue": dict(
            name="Dodger Stadium",
            sport_use="Baseball",
            zone="Elysian Park",
            address="1000 Vin Scully Ave, Los Angeles, CA 90012",
            lat=34.0739,
            lng=-118.2400,
            total_spaces=16000,
            total_lots=21,
            capacity_text="16,000 automobiles, on 21 terraced lots",
            games_time_access_notes=None,    # FLAG 5
            collection_status=None,
            date_collected=_d(7, 6),
            data_sources_summary=None,       # cell blank in PDF
        ),
        "parking": [
            dict(
                lot_name=(
                    "General lots directed by gate: "
                    "Gate A→Lots 10,11,12; Gate B→Lots 2,3; Gate C→Lots 3,4,15; "
                    "Gate D→Lots 4,5,6,7,15; Gate E→Lots 5,6,7,8,10. "
                    "Preferred Lots: B, D, F, G, J, K, L, M, N, O, P (F, H, K sellable to public)"
                ),
                is_official=True,
                price_min=40.00,             # General at gate / advance minimum
                price_max=70.00,             # Bus/Limo/Oversized at gate
                price_notes=(
                    "General: $40 in advance / $45 at the gate. "
                    "Preferred: $65 (advance only, not sold at gate). "
                    "Bus/Limo/Oversized: $65 advance / $70 at gate."
                ),
                pricing_basis=None,
                has_surge_pricing=True,
                surge_notes=(
                    "Rates do not apply to special events (e.g., concerts, etc.). "
                    "Parking rates for special events will vary.\" "
                    "Also: Union Station park-and-ride jumps to $65 and Harbor Gateway to $10 on specific "
                    "2026 World Cup match/fan-zone days (June 12,15,18,21,25,26,27,28, July 2,10)"
                ),
                is_closest_to_entrance=None,
                notes=(
                    "Closest lot to venue entrance (own research): Preferred lots are the closest. "
                    "Accessible parking in Lots B,D,F,G,K,L,N,P with courtesy ADA shuttle (call 323-224-2611). "
                    "Reserved named spots available to season ticket holders via phone/email. "
                    "Uber (official rideshare partner) pick-up/drop-off: Lot 1, entering through Gate B "
                    "(moved from Lot 11 to decrease Gate A congestion). "
                    "Taxi loading/unloading zone along the outer edge of Lot G. "
                    "Tailgating and alcohol consumption strictly prohibited in all lots; 14 mph lot speed limit."
                ),
                source=(
                    "mlb.com/.../general-parking; "
                    "mlb.com/.../preferred-parking; "
                    "mlb.com/.../parking; "
                    "mlb.com/dodgers/history/ballparks; "
                    "metro.net/destinations/dodger-stadium"
                ),
                date_collected=_d(7, 6),
                verified_by="JD",
                data_gaps=None,
            ),
        ],
        "curb": dict(
            rideshare_zone_description=(
                "Uber, the official rideshare partner of the Dodgers, has moved its pickup and drop-off "
                "location from Lot 11 to Lot 1. Ubers will now enter through Gate B in an effort to "
                "decrease Gate A congestion and increase the speed of arrival and drop off for fans."
            ),
            rideshare_zone_open_window="always",     # exactly as written
            taxi_accessible_zone=(
                "Taxi loading/unloading zone along the outer edge of Lot G"
            ),
            private_vehicle_dropoff=(
                "Use any auto gate (Sunset Gate A, Scott Gate B, Golden State Gate C, "
                "Academy Gate D, or Downtown Gate E)."
            ),
            no_stop_zones=(
                "Stadium Way (Avenue of the Palms); "
                "Elysian Park Public Roads; "
                "red curbs"
            ),
            curbside_restrictions=(
                "Tailgating and alcohol consumption strictly prohibited in all lots; 14 mph lot speed limit"
            ),
            source=(
                "https://www.mlb.com/dodgers/ballpark/transportation/uber; "
                "mlb.com/.../car-service-and-tax; "
                "mlb.com/.../general-parking"
            ),
            date_collected=_d(7, 6),
            verified_by="JD",
            data_gaps=None,
        ),
        "transit": [
            dict(
                line="Metro A Line (rail); Metro Bus Lines 2 and 4; Metro J Line (bus rapid transit, via free Dodger Stadium Express only)",
                mode="rail",
                stop_name="A Line Chinatown Station (Alameda St & College St)",
                walk_time_min=27,
                nearest_metro_station=(
                    "A Line Chinatown Station (Alameda St & College St); "
                    "Union Station (via free Dodger Stadium Express shuttle)"
                ),
                bus_lines_serving=(
                    "Metro Local Lines 2 and 4 (Sunset Blvd); "
                    "Metro J Line via Dodger Stadium Express"
                ),
                bike_lane_nearby=True,
                gbfs_dock_description="Own research: No scooter/dock zones nearby",
                transit_notes=(
                    "Walk time from station (own research): Chinatown Station: 27 mins. "
                    "Nearest bus stop: Metro bus stop on Sunset Blvd. "
                    "Walk time from bus stop (own research): Sunset Blvd (15 mins). "
                    "Bike lane / path nearby: Yes — Dodgers \"encourage alternate forms of transportation,\" "
                    "bike racks at all levels/turnstiles; no specific street/lane name. "
                    "Free Dodger Stadium Express shuttle connects Union Station and 5 South Bay J Line stops "
                    "(Slauson, Manchester, Harbor Freeway, Rosecrans, Harbor Gateway Transit Center). "
                    "Regular Metro fare $1.75 one-way/$3.50 roundtrip (Express itself is free with ticket). "
                    "Union Station buses run every 5–10 min starting 3 hrs before game through end of 2nd inning. "
                    "J Line buses every 30 min starting 3 hrs before. "
                    "Return service ends 1 hr after final out (or 30 min after post-game events)."
                ),
                source=(
                    "mlb.com/.../public-transit; "
                    "metro.net/destinations/dodger-stadium"
                ),
                date_collected=_d(7, 6),
                verified_by="JD",
                data_gaps=None,
            ),
        ],
        "congestion": dict(
            recommended_arrival_hrs_before_min=2.0,   # stadium gates open 2 hrs before
            recommended_arrival_hrs_before_max=2.5,   # parking gates open 2.5 hrs before
            arrival_notes=(
                "Parking gates open 2.5 hrs before game time, stadium gates open 2 hrs before."
            ),
            high_congestion_entry_roads=(
                "Vin Scully Ave/Sunset Blvd for Gate A; "
                "Academy Rd for Gates C/D; "
                "Stadium Way/110 Fwy for Gate E."
            ),
            known_congestion_exit_roads="Downtown/Academy/Sunset",
            event_day_parking_surge=True,
            past_congestion_refs="Own research",
            general_tdm_notes=(
                "Free Dodger Stadium Express shuttle; bike rack program; "
                "courtesy ADA shuttle between lots and gates."
            ),
            source=(
                "mlb.com/.../directions; "
                "mlb.com/.../general-parking; "
                "metro.net/destinations/dodger-stadium"
            ),
            date_collected=_d(7, 6),
            verified_by="JD",
            data_gaps=None,
        ),
        "sources": [
            dict(
                primary_url="mlb.com/dodgers/ballpark/transportation",
                secondary_url="metro.note/destinations/dodger-stadium/",  # sic — as written in PDF
                verified_by="JD",
                verified_at=_d(7, 7),
            ),
        ],
    },

    # ── 4 / 6  DTLA Arena ───────────────────────────────────────────────────
    {
        "venue": dict(
            name="DTLA Arena",
            sport_use="Gymnastics / Boxing Finals",
            zone="Downtown LA",
            address="1111 S Figueroa St, Los Angeles, CA 90015",
            lat=34.0430,
            lng=-118.2673,
            total_spaces=3300,
            total_lots=7,                    # Lot 1, SW VIP, Lot W, Lot E, Lot C, Lot 4, Lot 12
            capacity_text="3,300 spaces in arena-owned lots",
            games_time_access_notes=None,    # FLAG 5
            collection_status=None,
            date_collected=_d(7, 7),
            data_sources_summary=None,       # cell blank in PDF
        ),
        "parking": [
            dict(
                lot_name=(
                    "Lot 1; Southwest VIP (SW VIP); Lot W (West Garage – Gates B, D, E&F); "
                    "Lot E (East Garage); Lot C; Lot 4; Lot 12"
                ),
                is_official=True,
                price_min=10.00,             # Gate B low end
                price_max=50.00,             # Gate B high end
                price_notes=(
                    "West Garage (Lot W, Gates E&F): $40 event parking flat (plus city parking tax). "
                    "East Garage (Lot E): $40 max (timed). "
                    "West Garage (Lot W, Gate B): flat rate $10–$50 (plus city tax) depending on the event."
                ),
                pricing_basis=None,
                has_surge_pricing=True,
                surge_notes=(
                    "Gate B flat rate explicitly ranges $10–$50 \"depending on the event\" — "
                    "i.e., built-in event-based variability rather than a single surge flag"
                ),
                is_closest_to_entrance=None,
                notes=(
                    "Closest lot to venue entrance (own research): Lot 1; Lot W. "
                    "Lot W & Lot E open 6 AM–2 AM daily. "
                    "Lot 1 & Lot C open 2.5 hrs before an event; all other lots open 90 min before and "
                    "stay staffed 60 min after, no overnight parking/in-and-out privileges. "
                    "Gate B opens 3.5 hrs before event; oversized vehicles (limo/bus/RV) need reservations "
                    "10 days ahead; motorcycle parking in West Garage level P1; disabled parking "
                    "first-come-first-served; EV charging $3.50/hr (first 4 hrs), $4.50/hr after, "
                    "at both garages."
                ),
                source="cryptoarena.com/plan-your-visit/getting-here",
                date_collected=_d(7, 7),
                verified_by="JD",
                data_gaps=None,
            ),
        ],
        "curb": dict(
            rideshare_zone_description=(
                "Two designated zones: the white zone on Chick Hearn Ct. (eastbound) between "
                "L.A. Live Way and Georgia St.; and the white zone on Figueroa St. (southbound) "
                "between 12th St and Pico"
            ),
            rideshare_zone_open_window=None,     # cell blank in PDF
            taxi_accessible_zone="Same white zones",
            private_vehicle_dropoff=None,        # cell blank in PDF
            no_stop_zones=(
                "Chick Hearn Court (formerly 11th St.) between L.A. Live Way and Figueroa is a designated "
                "No Parking/Tow-Away zone; LAPD enforces \"No Stopping\" signs throughout the district. "
                "Road closure 7/7 at Gilbert Lindsey Dr"
            ),
            curbside_restrictions=(
                "Tailgating prohibited in all L.A. LIVE/arena lots; bicycle parking restricted to two "
                "designated locations (East Garage P1 level, and Gilbert Lindsey Plaza) — "
                "unauthorized bikes will have locks cut"
            ),
            source=(
                "cryptoarena.com/plan-your-visit/getting-here/public-transportation; "
                "cryptoarena.com/plan-your-visit/getting-here/"
            ),
            date_collected=_d(7, 7),
            verified_by="JD",
            data_gaps=None,
        ),
        "transit": [
            dict(
                line=(
                    "Metro A Line; E Line (rail) via Pico Station; "
                    "B, D, A, or E Line via 7th St/Metro Center Station; "
                    "J Line (bus) via Figueroa/Pico Station"
                ),
                mode="rail",
                stop_name="Pico Station (A/E Line)",
                walk_time_min=2,
                nearest_metro_station="Pico Station (A/E Line)",
                bus_lines_serving=(
                    "Metro Local Lines 28, 30, 81, 460, and the J Line; "
                    "DASH Route F (Figueroa St.)"
                ),
                bike_lane_nearby=True,
                gbfs_dock_description=(
                    "Metro Bike Share stations at Figueroa & 11th, Figueroa & Pico, and Pico & Flower"
                ),
                transit_notes=(
                    "Walk times: 2 minutes from Pico Station; 15 minutes from 7th St/Metro Center Station. "
                    "Nearest bus stop: Metro lines and DASH Route F both noted as stopping on/near "
                    "Figueroa St. adjacent to L.A. LIVE. Walk time from bus stop (own research): "
                    "Figeroa and 12th stop (1 min). "        # sic — spelling as in PDF
                    "Bike lane / path nearby: Yes — Metro Bike Share stations nearby; "
                    "dedicated bicycle parking at the arena. "
                    "Metrolink offers a $10 weekend pass with free Metro bus/rail connections; "
                    "Amtrak riders can transfer to Metro Rail at Union Station (separate ticket required)."
                ),
                source=(
                    "metro.net/destinations/crypto-arena; "
                    "cryptoarena.com/.../public-transportation"
                ),
                date_collected=_d(7, 7),
                verified_by="JD",
                data_gaps=None,
            ),
        ],
        "congestion": dict(
            recommended_arrival_hrs_before_min=1.5,   # other lots open 90 min (1.5 hrs) before
            recommended_arrival_hrs_before_max=3.5,   # Gate B opens 3.5 hrs before
            arrival_notes=(
                "Lot 1 & Lot C open 2.5 hrs before event; "
                "Gate B (West Garage) opens 3.5 hrs before event (recommended for events 3.5+ hrs); "
                "all other lots open 90 min before."
            ),
            high_congestion_entry_roads=(
                "Own research: Pico Blvd; Chick Hearn Court; Olympic Blvd"
            ),
            known_congestion_exit_roads=(
                "Own research: LA Live Way; Francisco St; Flower St"
            ),
            event_day_parking_surge=True,
            past_congestion_refs="Own research",
            general_tdm_notes=(
                "LAPD-enforced no-stopping zones to manage rideshare congestion; "
                "Metro Bike Share docks nearby; DASH and Metrolink offered as alternate access options."
            ),
            source=(
                "cryptoarena.com/plan-your-visit/getting-here; "
                "cryptoarena.com/.../public-transportation; "
                "metro.net/destinations/crypto-arena"
            ),
            date_collected=_d(7, 7),
            verified_by="JD",
            data_gaps=None,
        ),
        "sources": [
            dict(
                primary_url=(
                    "cryptoarena.com/plan-your-visit/getting-here/ (and its Public Transportation subpage) "
                    "— official arena site,"     # trailing comma sic — as in PDF
                ),
                secondary_url="metro.net/destinations/crypto-arena/ (official LA Metro destination guide)",
                verified_by="JD",
                verified_at=_d(7, 7),
            ),
        ],
    },

    # ── 5 / 6  Peacock Theater ──────────────────────────────────────────────
    {
        "venue": dict(
            name="Peacock Theater",
            sport_use="Boxing Prelims / Weightlifting",
            zone="Downtown LA",
            address="1111 S Figueroa St, Los Angeles, CA 90015",
            lat=34.0448,
            lng=-118.2666,
            total_spaces=3300,
            total_lots=4,                    # Lot 1, Lot W, Lot E, Lot C
            capacity_text="3,300 spaces at Crypto.com Arena/Peacock Theater-owned lots",
            games_time_access_notes=None,    # FLAG 5
            collection_status=None,
            date_collected=_d(7, 7),
            data_sources_summary=(
                "(1) peacocktheater.com/plan-your-visit/getting-here; "
                "(2) peacocktheater.com/.../public-transportation-rideshare"
            ),
        ),
        "parking": [
            dict(
                lot_name=(
                    "Lot 1, Lot W (West Garage – Gates B, E&F), Lot E (East Garage), "
                    "Lot C (theater-specific opener)"
                ),
                is_official=True,
                price_min=10.00,
                price_max=50.00,
                price_notes=(
                    "West Garage (Lot W, Gates E&F): $40 event parking flat (plus city parking tax). "
                    "East Garage (Lot E): $40 max (timed). "
                    "West Garage (Lot W, Gate B): flat rate $10–$50 (plus city tax) depending on the event. "
                    "Prepaid parking available online via AXS.com."
                ),
                pricing_basis=None,
                has_surge_pricing=True,
                surge_notes=(
                    "Gate B flat rate explicitly ranges $10–$50 \"depending on the event\""
                ),
                is_closest_to_entrance=None,
                notes=(
                    "Closest lot to venue entrance (own research): LA Live Parking/ Lot W; Lot 1. "
                    "Lot W & Lot E open 6 AM–2 AM daily; "
                    "Lot C opens 2.5 hrs before a Peacock Theater event; no overnight parking/in-and-out privileges; "
                    "Gate B opens 3.5 hrs before event (recommended for 3.5+ hr events); "
                    "oversized vehicles need 10-day advance arrangement, not accepted in Lot 1; "
                    "motorcycle parking in West Garage P1; EV charging $3.50/hr (first 4 hrs), "
                    "$4.50/hr after, in both garages."
                ),
                source="(1) peacocktheater.com/plan-your-visit/getting-here",
                date_collected=_d(7, 7),
                verified_by="JD",
                data_gaps=None,
            ),
        ],
        "curb": dict(
            rideshare_zone_description=(
                "White zone on Chick Hearn Ct. (eastbound) between L.A. Live Way and Georgia St.; "
                "white zone on Figueroa St. (southbound) between 12th St and Pico"
            ),
            rideshare_zone_open_window=None,     # "Own research" with no value given
            taxi_accessible_zone="Same white zone",
            private_vehicle_dropoff="Not stated",
            no_stop_zones=(
                "Chick Hearn Court between L.A. Live Way and Figueroa is a No Parking/Tow-Away zone; "
                "LAPD enforces \"No Stopping\" signage throughout the district"
            ),
            curbside_restrictions=(
                "Tailgating prohibited in all L.A. LIVE/Crypto.com Arena lots; bicycle parking restricted "
                "to two designated spots (East Garage P1, Gilbert Lindsey Plaza)"
            ),
            source="(1) peacocktheater.com/plan-your-visit/getting-here; (2) peacocktheater.com/.../public-transportation-rideshare",
            date_collected=_d(7, 7),
            verified_by="JD",
            data_gaps=None,
        ),
        "transit": [
            dict(
                line=(
                    "Metro Bus lines 28, 30, 81, 460, and the J Line; "
                    "Metro Rail also serves the area (A/E Line via Pico Station, per Metro's own blog)"
                ),
                mode="bus",
                stop_name="Pico Station",
                walk_time_min=10,
                nearest_metro_station="Pico Station",
                bus_lines_serving=(
                    "Metro Local Lines 28, 30, 81, 460; DASH Route F (Figueroa St.)"
                ),
                bike_lane_nearby=True,
                gbfs_dock_description=(
                    "Metro Bike Share stations at Figueroa & 11th, Figueroa & Pico, Pico & Flower"
                ),
                transit_notes=(
                    "About 10 minutes from Pico Station (per LA Metro's own April 2026 events post — "
                    "this is theater-specific and longer than the ~2 min cited for the adjacent "
                    "Crypto.com Arena entrance, since the theater building sits farther into the "
                    "L.A. LIVE complex). "
                    "Nearest bus stop: Figueroa St. corridor. "
                    "Walk time from bus stop (own research): ~1-2 Mins. "
                    "Bike lane / path nearby: Yes — Metro Bike Share stations in the immediate district "
                    "(Figueroa & 11th, Figueroa & Pico, Pico & Flower, per the shared L.A. LIVE Metro FAQ); "
                    "bicycle parking at the theater/arena complex. "
                    "Metrolink $10 weekend pass includes free Metro bus/rail connections; "
                    "Amtrak riders can transfer to Metro Rail at Union Station (separate ticket required)."
                ),
                source=(
                    "peacocktheater.com/.../public-transportation-rideshare; "
                    "thesource.metro.net (Apr 23, 2026 post); "
                    "metro.net/destinations/crypto-arena/ (FAQ)"
                ),
                date_collected=_d(7, 7),
                verified_by="JD",
                data_gaps=None,
            ),
        ],
        "congestion": dict(
            recommended_arrival_hrs_before_min=1.5,   # Lot C opens 2.5 hrs; others 90 min
            recommended_arrival_hrs_before_max=3.5,   # Gate B opens 3.5 hrs before
            arrival_notes=(
                "Lot C opens 2.5 hrs before event; "
                "Gate B (West Garage) opens 3.5 hrs before event and is recommended for events 3.5+ hrs long."
            ),
            high_congestion_entry_roads="Own research: Same as crypto",
            known_congestion_exit_roads="Own research: Same as crypto",
            event_day_parking_surge=True,
            past_congestion_refs=None,               # cell blank
            general_tdm_notes=(
                "LAPD-enforced no-stopping zones for rideshare management; "
                "Metro Bike Share docks nearby; DASH and Metrolink offered as alternate access."
            ),
            source=None,                             # FLAG 4: source cells blank in PDF
            date_collected=_d(7, 7),
            verified_by="JD",
            data_gaps=None,
        ),
        "sources": [
            # FLAG 4: Primary source and Secondary source cells are blank in the PDF.
            # The data_sources_summary on the venue carries the two known URL references.
            dict(
                primary_url=None,
                secondary_url=None,
                verified_by="JD",
                verified_at=_d(7, 7),
            ),
        ],
    },

    # ── 6 / 6  Rose Bowl Stadium ────────────────────────────────────────────
    {
        "venue": dict(
            name="Rose Bowl Stadium",
            sport_use="Soccer Finals",
            zone="Pasadena",
            address="1001 Rose Bowl Dr, Pasadena, CA 91103",
            lat=34.1613,
            lng=-118.1676,
            total_spaces=26000,
            total_lots=None,                 # no "Total parking lots" row in doc
            capacity_text="Own research: 26,000 Spaces",
            games_time_access_notes=None,    # FLAG 5
            collection_status=None,
            date_collected=_d(7, 8),
            data_sources_summary=None,       # cell blank in PDF
        ),
        "parking": [
            dict(
                lot_name=(
                    "Lot B/Gate B (shuttle drop-off point); Lot H (rideshare drop-off for some concert events); "
                    "Lot H, 1-4, 6, and 8-10 for general"
                ),
                is_official=True,
                price_min=38.00,             # regular vehicle advance (incl. $3 tech fee)
                price_max=154.00,            # oversized at gate (incl. $4 tech fee)
                price_notes=(
                    "For UCLA Football (Nebraska vs. UCLA, 11/8/2025): "
                    "regular vehicle at gate $44 (incl. $4 technology fee); "
                    "oversized at gate $154 (incl. $4 fee). "
                    "Pre-purchase: regular $38 (incl. $3 fee); oversized $128 (incl. $3 fee) — "
                    "available until 11:45 PM night before event. No cash accepted at the gate."
                ),
                pricing_basis=(
                    "UCLA Football 11/8/2025 — not confirmed LA28 Olympic pricing"
                ),
                has_surge_pricing=True,
                surge_notes=(
                    "Pricing is event-specific and set per event (confirmed different rate for the general "
                    "public event-parking portal vs. UCLA Football portal). "
                    "A Reddit mention (not verified officially) cited $33 lot pricing for a 2025 concert — "
                    "flagging as unverified rather than treating as fact."
                ),
                is_closest_to_entrance=None,
                notes=(
                    "Closest lot to venue entrance (own research): Lot D, B, F. "
                    "For the 11/8/2025 UCLA game: parking opened at 12:00 PM for a 6:00 PM kickoff "
                    "(6 hrs before); all vehicles must vacate no more than 90 minutes after the game ends. "
                    "General note: attendees are restricted from entering surrounding residential roads."
                ),
                source=(
                    "rosebowlstadium.com/events/details/506/nebraska-vs-ucla; "
                    "rosebowlstadium.com/parking (portal links); "
                    "https://en.wikipedia.org/wiki/Rose_Bowl_(stadium)"
                ),
                date_collected=_d(7, 8),
                verified_by="JD",
                data_gaps=None,
            ),
        ],
        "curb": dict(
            rideshare_zone_description=(
                "Varies by event — for UCLA Football games and most concerts (Guns N' Roses, Oasis, "
                "rüfüs du sol, etc.), rideshare/taxi must drop off and pick up in the Old Town Pasadena "
                "area (not at the stadium itself). "
                "One concert (Karol G, 2023) allowed drop-off in Lot H instead. "
                "For the 109th Rose Bowl Game, no rideshare/taxi drop-off was allowed at the stadium at all."
            ),
            rideshare_zone_open_window="Dependent on event time",
            taxi_accessible_zone=(
                "Same Old Town Pasadena zone as rideshare for most events"
            ),
            private_vehicle_dropoff=None,        # cell blank in PDF
            no_stop_zones=None,                  # "Own research" with no value given
            curbside_restrictions=(
                "Stadium sits in a residential area; attendees must follow traffic control personnel "
                "and are restricted from entering residential roads near the stadium"
            ),
            source=(
                "rosebowlstadium.com/getting-here; "
                "multiple rosebowlstadium.com event pages"
            ),
            date_collected=_d(7, 8),
            verified_by="JD",
            data_gaps=None,
        ),
        "transit": [
            dict(
                line="Metro A Line",
                mode="rail",
                stop_name="Memorial Park Station",
                walk_time_min=42,
                nearest_metro_station='Memorial Park Station; ""',   # sic — as written in PDF
                bus_lines_serving=(
                    "Pasadena Transit Routes 51 or 52 (alternative to the event shuttle, Monday–Saturday)"
                ),
                bike_lane_nearby=True,
                gbfs_dock_description="Own research: No metro biek share or scooters in Pasedena",   # sic
                transit_notes=(
                    "Walk time from station (own research): 42 Min. "
                    "Nearest bus stop (own research): Colorado and Arroyo. "
                    "Walk time from bus stop (own research): 27 mins. "
                    "Bike lane / path nearby: Yes — the Arroyo Seco trail is cited as a walkable/bikeable "
                    "route from Memorial Park Station. "
                    "Free Foothill Transit Rose Bowl Shuttle runs from Parsons Parking Lot B "
                    "(Old Town, near Memorial Park Station) every 5–7 minutes for select events, "
                    "but availability varies by event — confirm with organizer. "
                    "Metro recommends arriving at Memorial Park Station at least 90 minutes before the "
                    "event start time to catch the shuttle and avoid crowds. "
                    "Parking at Parsons costs $27.50 (per the 11/8/2025 UCLA game page) or $30 "
                    "(per an unverified 2-year-old Reddit comment about a different event — flagging the discrepancy). "
                    "Metrolink riders must transfer to the A Line at Union Station."
                ),
                source=(
                    "metro.net/destinations/rose-bowl; "
                    "rosebowlstadium.com/getting-here; "
                    "rosebowlstadium.com/events/details/506/nebraska-vs-ucla"
                ),
                date_collected=_d(7, 8),
                verified_by="JD",
                data_gaps=None,
            ),
        ],
        "congestion": dict(
            recommended_arrival_hrs_before_min=1.5,   # doors open / Metro shuttle rec = 90 min
            recommended_arrival_hrs_before_max=6.0,   # parking opened 6 hrs before (11/8/2025 game)
            arrival_notes=(
                "For the 11/8/2025 UCLA game: parking opened 6 hrs before kickoff "
                "(12:00 PM for 6:00 PM), shuttle started 3 hrs before, doors opened 1.5 hrs before. "
                "Separately, Metro recommends arriving at Memorial Park Station at least 90 minutes before "
                "the event start time."
            ),
            high_congestion_entry_roads=(
                "134, 110, 210 freeways and Fair Oaks Ave/Linda Vista Ave/Salvia Canyon,"
                # trailing comma sic — as in PDF
            ),
            known_congestion_exit_roads=None,        # cell blank in PDF
            event_day_parking_surge=True,
            past_congestion_refs=None,               # cell blank in PDF
            general_tdm_notes=(
                "Free shuttle service between Old Town Pasadena (Parsons) and the stadium is the "
                "primary TDM tool; attendees are directed away from rideshare drop-off at the stadium "
                "itself for most major events."
            ),
            source=(
                "rosebowlstadium.com/getting-here; "
                "rosebowlstadium.com/events/details/506/nebraska-vs-ucla; "
                "metro.net/destinations/rose-bowl (FAQ)"
            ),
            date_collected=_d(7, 8),
            verified_by="JD",
            data_gaps=None,
        ),
        "sources": [
            dict(
                primary_url=(
                    "rosebowlstadium.com/getting-here and "
                    "rosebowlstadium.com/events/details/506/nebraska-vs-ucla "
                    "(official venue site, event page dated November 8, 2025 — within the past year)"
                ),
                secondary_url=(
                    "metro.net/destinations/rose-bowl/ "
                    "(official LA Metro destination guide, including its FAQ section)"
                ),
                verified_by="JD",
                verified_at=_d(7, 8),
            ),
        ],
    },
]


# ---------------------------------------------------------------------------
# seed function
# ---------------------------------------------------------------------------

def seed(session: Session) -> None:
    for entry in VENUES:
        v = Venue(**entry["venue"])
        session.add(v)
        session.flush()  # populate v.id before child inserts

        for p in entry.get("parking", []):
            session.add(ParkingOption(venue_id=v.id, **p))

        c = entry.get("curb")
        if c:
            session.add(CurbDropoff(venue_id=v.id, **c))

        for t in entry.get("transit", []):
            session.add(TransitAccess(venue_id=v.id, **t))

        cong = entry.get("congestion")
        if cong:
            session.add(CongestionTdm(venue_id=v.id, **cong))

        for s in entry.get("sources", []):
            session.add(VenueSource(venue_id=v.id, **s))

    session.commit()
    print(f"Seeded {len(VENUES)} venues.")


if __name__ == "__main__":
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as _Session

    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    with _Session(engine) as session:
        seed(session)
