"""
Synthetic delivery history for the Last Mile demo — Indian addresses.

Five showcase stories + background filler:
  A. "The Landmark Address"   — no formal address, landmark-based directions, conflict
  B. "The Sector Confusion"   — multiple Sector 14s, drivers clarify which one
  C. "The Night Shift"        — tenant works nights, repeated daytime failures
  D. "The Reliable"           — commercial address, HIGH confidence, consistent notes
  E. "Cold Start"             — informal address, zero history, similarity fallback
  F–N. Background addresses   — variety across Indian cities for realistic dashboard
"""

from datetime import datetime, timedelta

BASE_DATE = datetime(2026, 6, 13)


def days_ago(n: int, hour: int = 10) -> str:
    return (BASE_DATE + timedelta(days=n, hours=hour)).isoformat()


DRIVERS = [
    {"id": "D001", "name": "Arjun Sharma"},
    {"id": "D002", "name": "Priya Nair"},
    {"id": "D003", "name": "Suresh Kumar"},
    {"id": "D004", "name": "Sana Shaikh"},
    {"id": "D005", "name": "Ravi Verma"},
    {"id": "D006", "name": "Meena Iyer"},
    {"id": "D007", "name": "Imran Siddiqui"},
]


SEED_NOTES = [

    # ── A. Near Shiv Mandir, Laxmi Nagar, Delhi — "The Landmark Address" ────
    # No door number. Directions given relative to a temple and a paan shop.
    # Conflict: left vs right after the mandir. Recency should win.
    {
        "address_id":   "shiv_mandir_laxmi_nagar",
        "address_text": "Near Shiv Mandir, Gali No. 4, Laxmi Nagar, Delhi",
        "driver_id": "D001", "driver_name": "Arjun Sharma",
        "status": "FAILED",
        "note_text": "No door number anywhere. Mandir is easy to find but the gali behind it has 3 turns. Went left after mandir — wrong house. Tenant called and said turn RIGHT after the mandir, then first blue gate.",
        "timestamp": days_ago(0, 9),
    },
    {
        "address_id":   "shiv_mandir_laxmi_nagar",
        "address_text": "Near Shiv Mandir, Gali No. 4, Laxmi Nagar, Delhi",
        "driver_id": "D002", "driver_name": "Priya Nair",
        "status": "SUCCESS",
        "note_text": "Turn RIGHT after the Shiv Mandir — not left. First blue gate on the left side of the gali. The gate has a small Ganesh sticker. Tenant is usually home till noon.",
        "timestamp": days_ago(3, 11),
    },
    {
        "address_id":   "shiv_mandir_laxmi_nagar",
        "address_text": "Near Shiv Mandir, Gali No. 4, Laxmi Nagar, Delhi",
        "driver_id": "D004", "driver_name": "Sana Shaikh",
        "status": "SUCCESS",
        "note_text": "Confirmed — right after mandir, blue gate with Ganesh sticker. Don't go towards the paan shop side, that's the wrong lane entirely.",
        "timestamp": days_ago(7, 10),
    },
    {
        "address_id":   "shiv_mandir_laxmi_nagar",
        "address_text": "Near Shiv Mandir, Gali No. 4, Laxmi Nagar, Delhi",
        "driver_id": "D006", "driver_name": "Meena Iyer",
        "status": "FAILED",
        "note_text": "Made the mistake of going left — previous note from D001 caused confusion. The RIGHT turn is correct. Wasted 15 minutes.",
        "timestamp": days_ago(12, 9),
    },
    {
        "address_id":   "shiv_mandir_laxmi_nagar",
        "address_text": "Near Shiv Mandir, Gali No. 4, Laxmi Nagar, Delhi",
        "driver_id": "D003", "driver_name": "Suresh Kumar",
        "status": "SUCCESS",
        "note_text": "Blue gate confirmed. Gali is too narrow for a bike — park at the mandir and walk 50 metres. Tenant name is Ramesh bhai, very helpful.",
        "timestamp": days_ago(18, 11),
    },

    # ── B. Plot 22, Sector 14, Gurugram — "The Sector Confusion" ────────────
    # Two Sector 14s in Gurugram (old and new). Drivers keep going to the wrong one.
    {
        "address_id":   "plot22_sector14_gurugram",
        "address_text": "Plot 22, Sector 14, Gurugram, Haryana",
        "driver_id": "D005", "driver_name": "Ravi Verma",
        "status": "FAILED",
        "note_text": "Went to Sector 14 near Iffco Chowk — wrong area entirely. There are two Sector 14s in Gurgaon. This address is the OLD Sector 14, near Sadar Bazar, not the new one near the highway.",
        "timestamp": days_ago(1, 14),
    },
    {
        "address_id":   "plot22_sector14_gurugram",
        "address_text": "Plot 22, Sector 14, Gurugram, Haryana",
        "driver_id": "D007", "driver_name": "Imran Siddiqui",
        "status": "SUCCESS",
        "note_text": "OLD Sector 14 near Sadar Bazar — confirmed. Plot 22 is a yellow house, second lane after the govt school. Main gate has a blue letterbox. Don't go to Sector 14 near Iffco, that's wrong.",
        "timestamp": days_ago(5, 10),
    },
    {
        "address_id":   "plot22_sector14_gurugram",
        "address_text": "Plot 22, Sector 14, Gurugram, Haryana",
        "driver_id": "D001", "driver_name": "Arjun Sharma",
        "status": "SUCCESS",
        "note_text": "Yellow house, blue letterbox confirmed. Search for 'Sadar Bazar Gurugram' on maps then navigate from there — direct Sector 14 search takes you to the wrong one.",
        "timestamp": days_ago(10, 9),
    },
    {
        "address_id":   "plot22_sector14_gurugram",
        "address_text": "Plot 22, Sector 14, Gurugram, Haryana",
        "driver_id": "D003", "driver_name": "Suresh Kumar",
        "status": "FAILED",
        "note_text": "New driver mistake — went to the highway Sector 14 again. Must add note in app: OLD Sector 14 only.",
        "timestamp": days_ago(15, 13),
    },

    # ── C. Flat 4B, Sai Nagar, Pune — "The Night Shift" ─────────────────────
    # Tenant works night shifts at a factory. Never home before 6 PM.
    {
        "address_id":   "flat4b_sai_nagar_pune",
        "address_text": "Flat 4B, Sai Nagar Chawl, Near Kothrud Bus Depot, Pune",
        "driver_id": "D002", "driver_name": "Priya Nair",
        "status": "FAILED",
        "note_text": "No one home at 11 AM. Building is easy to find — just past the Kothrud depot. Neighbour says tenant works night shift at Bajaj plant, comes home after 7 PM.",
        "timestamp": days_ago(1, 11),
    },
    {
        "address_id":   "flat4b_sai_nagar_pune",
        "address_text": "Flat 4B, Sai Nagar Chawl, Near Kothrud Bus Depot, Pune",
        "driver_id": "D004", "driver_name": "Sana Shaikh",
        "status": "FAILED",
        "note_text": "Tried at 2 PM — still nobody. Same neighbour confirmed: night shift, home after 7 PM only. Do not attempt morning or afternoon.",
        "timestamp": days_ago(4, 14),
    },
    {
        "address_id":   "flat4b_sai_nagar_pune",
        "address_text": "Flat 4B, Sai Nagar Chawl, Near Kothrud Bus Depot, Pune",
        "driver_id": "D006", "driver_name": "Meena Iyer",
        "status": "SUCCESS",
        "note_text": "Delivered at 7:30 PM — tenant answered right away. Friendly. Confirmed: home only after 7 PM on weekdays. Weekends he's home from noon.",
        "timestamp": days_ago(7, 19),
    },
    {
        "address_id":   "flat4b_sai_nagar_pune",
        "address_text": "Flat 4B, Sai Nagar Chawl, Near Kothrud Bus Depot, Pune",
        "driver_id": "D005", "driver_name": "Ravi Verma",
        "status": "FAILED",
        "note_text": "Dispatch sent me at 3 PM again. I know, I know. Night shift only — after 7 PM.",
        "timestamp": days_ago(11, 15),
    },
    {
        "address_id":   "flat4b_sai_nagar_pune",
        "address_text": "Flat 4B, Sai Nagar Chawl, Near Kothrud Bus Depot, Pune",
        "driver_id": "D007", "driver_name": "Imran Siddiqui",
        "status": "SUCCESS",
        "note_text": "7:45 PM delivery — perfect. Chawl building has no lift, Flat 4B is on second floor. Staircase is on the left as you enter.",
        "timestamp": days_ago(14, 20),
    },
    {
        "address_id":   "flat4b_sai_nagar_pune",
        "address_text": "Flat 4B, Sai Nagar Chawl, Near Kothrud Bus Depot, Pune",
        "driver_id": "D001", "driver_name": "Arjun Sharma",
        "status": "FAILED",
        "note_text": "Another morning attempt by dispatch. Evening only — after 7 PM!",
        "timestamp": days_ago(19, 10),
    },

    # ── D. Shop 7, DLF Phase 2 Market, Gurugram — "The Reliable" ────────────
    # Commercial address, security desk, consistent notes, HIGH confidence.
    {
        "address_id":   "shop7_dlf_phase2_gurgaon",
        "address_text": "Shop No. 7, DLF Phase 2 Market, Sector 25, Gurugram",
        "driver_id": "D003", "driver_name": "Suresh Kumar",
        "status": "SUCCESS",
        "note_text": "Commercial market complex. Enter from the main gate on MG Road side — the Phase 2 internal gate is locked during deliveries. Shop 7 is ground floor, left wing. Security at gate signs for packages.",
        "timestamp": days_ago(1, 10),
    },
    {
        "address_id":   "shop7_dlf_phase2_gurgaon",
        "address_text": "Shop No. 7, DLF Phase 2 Market, Sector 25, Gurugram",
        "driver_id": "D001", "driver_name": "Arjun Sharma",
        "status": "SUCCESS",
        "note_text": "MG Road main gate confirmed. Security guard Ramcharan is very helpful — just show the package and he'll sign. Shop is open 10 AM to 8 PM. Don't go after 8.",
        "timestamp": days_ago(5, 11),
    },
    {
        "address_id":   "shop7_dlf_phase2_gurgaon",
        "address_text": "Shop No. 7, DLF Phase 2 Market, Sector 25, Gurugram",
        "driver_id": "D007", "driver_name": "Imran Siddiqui",
        "status": "SUCCESS",
        "note_text": "All confirmed. Parking is tight — use the two-wheeler bay near the gate, never blocked. Quick in-out, under 5 minutes.",
        "timestamp": days_ago(10, 14),
    },
    {
        "address_id":   "shop7_dlf_phase2_gurgaon",
        "address_text": "Shop No. 7, DLF Phase 2 Market, Sector 25, Gurugram",
        "driver_id": "D005", "driver_name": "Ravi Verma",
        "status": "SUCCESS",
        "note_text": "Easy delivery. MG Road gate, ground floor left, Ramcharan at security. Fastest stop of the day.",
        "timestamp": days_ago(15, 10),
    },
    {
        "address_id":   "shop7_dlf_phase2_gurgaon",
        "address_text": "Shop No. 7, DLF Phase 2 Market, Sector 25, Gurugram",
        "driver_id": "D002", "driver_name": "Priya Nair",
        "status": "SUCCESS",
        "note_text": "Seamless. Note: the side entrance near the parking looks closer on maps but it's locked. Always use MG Road main gate.",
        "timestamp": days_ago(19, 9),
    },

    # ── E. Cold Start — zero history, triggers similarity fallback ───────────
    # (no notes — that's the point)
    # "Behind Salim Bhai Ki Dukan, Civil Lines, Nagpur" — address_id: civil_lines_nagpur_cold

    # ── F–N. Background addresses across Indian cities ────────────────────────
    {
        "address_id":   "hsr_layout_b1_bengaluru",
        "address_text": "No. 14, 27th Cross, HSR Layout Sector 1, Bengaluru",
        "driver_id": "D004", "driver_name": "Sana Shaikh",
        "status": "SUCCESS",
        "note_text": "Independent house, green gate. 27th Cross is one-way — approach from the Agara Lake side, not from the main road. Gate is usually open during the day.",
        "timestamp": days_ago(2, 10),
    },
    {
        "address_id":   "hsr_layout_b1_bengaluru",
        "address_text": "No. 14, 27th Cross, HSR Layout Sector 1, Bengaluru",
        "driver_id": "D006", "driver_name": "Meena Iyer",
        "status": "SUCCESS",
        "note_text": "Confirmed: Agara Lake approach only. Green gate. Dog inside but behind a mesh door — doesn't come out. Ring the bell twice.",
        "timestamp": days_ago(9, 11),
    },
    {
        "address_id":   "bandra_west_mumbai",
        "address_text": "Flat 302, Sea Breeze Apartments, Linking Road, Bandra West, Mumbai",
        "driver_id": "D002", "driver_name": "Priya Nair",
        "status": "FAILED",
        "note_text": "Building has a strict society guard — no entry without resident calling down first. Called the number on the order, no answer. Left a missed delivery card.",
        "timestamp": days_ago(3, 12),
    },
    {
        "address_id":   "bandra_west_mumbai",
        "address_text": "Flat 302, Sea Breeze Apartments, Linking Road, Bandra West, Mumbai",
        "driver_id": "D005", "driver_name": "Ravi Verma",
        "status": "SUCCESS",
        "note_text": "Call the tenant 10 minutes before arriving — they'll inform the guard. Guard's name is Santosh. Without prior call, no entry at all. Lift is working, 3rd floor.",
        "timestamp": days_ago(8, 11),
    },
    {
        "address_id":   "bandra_west_mumbai",
        "address_text": "Flat 302, Sea Breeze Apartments, Linking Road, Bandra West, Mumbai",
        "driver_id": "D007", "driver_name": "Imran Siddiqui",
        "status": "SUCCESS",
        "note_text": "Called ahead — smooth entry. Santosh the guard confirmed. Parking on Linking Road is chaotic, use the lane behind the building.",
        "timestamp": days_ago(14, 10),
    },
    {
        "address_id":   "t_nagar_chennai",
        "address_text": "New No. 8, Venkatnarayana Road, T. Nagar, Chennai",
        "driver_id": "D003", "driver_name": "Suresh Kumar",
        "status": "SUCCESS",
        "note_text": "T. Nagar traffic is very heavy 5–8 PM. Old and new numbering on this street — look for New No. 8, not old No. 8 which is a different building. Pink building with a pharmacy on ground floor.",
        "timestamp": days_ago(4, 10),
    },
    {
        "address_id":   "t_nagar_chennai",
        "address_text": "New No. 8, Venkatnarayana Road, T. Nagar, Chennai",
        "driver_id": "D001", "driver_name": "Arjun Sharma",
        "status": "SUCCESS",
        "note_text": "Pink building, pharmacy on ground floor — confirmed. Avoid the evening rush. Resident on 2nd floor, staircase next to the pharmacy entrance.",
        "timestamp": days_ago(12, 9),
    },
    {
        "address_id":   "hitech_city_hyderabad",
        "address_text": "Tower B, Flat 1104, My Home Tarkshya, Hitech City, Hyderabad",
        "driver_id": "D006", "driver_name": "Meena Iyer",
        "status": "FAILED",
        "note_text": "Gated community with multiple towers — security at main gate needs the flat number and resident name before letting you in. I didn't have the resident name on the order. Turned away.",
        "timestamp": days_ago(2, 14),
    },
    {
        "address_id":   "hitech_city_hyderabad",
        "address_text": "Tower B, Flat 1104, My Home Tarkshya, Hitech City, Hyderabad",
        "driver_id": "D004", "driver_name": "Sana Shaikh",
        "status": "SUCCESS",
        "note_text": "Resident name is Kiran Reddy — tell security at gate. Tower B is the second tower from the main entrance, not the first. Lift goes to 11th floor directly. Quick delivery once inside.",
        "timestamp": days_ago(6, 11),
    },
    {
        "address_id":   "salt_lake_kolkata",
        "address_text": "Block CF, Plot 201, Salt Lake Sector 1, Kolkata",
        "driver_id": "D007", "driver_name": "Imran Siddiqui",
        "status": "SUCCESS",
        "note_text": "Salt Lake blocks are confusing — CF block is near the central park, not near the main road. GPS drops here, navigate by the block signboards. Plot 201 is a white house with a red boundary wall.",
        "timestamp": days_ago(5, 10),
    },
    {
        "address_id":   "salt_lake_kolkata",
        "address_text": "Block CF, Plot 201, Salt Lake Sector 1, Kolkata",
        "driver_id": "D002", "driver_name": "Priya Nair",
        "status": "SUCCESS",
        "note_text": "White house, red boundary — confirmed. Don't trust GPS here, use block signboards. Gate is open but ring the bell at the front door. Elderly resident, takes a minute to answer.",
        "timestamp": days_ago(11, 9),
    },
]


def get_all_seed_notes() -> list[dict]:
    return SEED_NOTES


def get_seed_addresses() -> list[dict]:
    seen = {}
    for note in SEED_NOTES:
        if note["address_id"] not in seen:
            seen[note["address_id"]] = {
                "address_id":   note["address_id"],
                "address_text": note["address_text"],
            }
    # Cold-start address — zero notes, triggers similarity fallback
    seen["civil_lines_nagpur_cold"] = {
        "address_id":   "civil_lines_nagpur_cold",
        "address_text": "Behind Salim Bhai Ki Dukan, Near Water Tank, Civil Lines, Nagpur",
    }
    return list(seen.values())
