"""
Synthetic delivery history for the Last Mile demo.

Three showcase stories + background filler:
  A. "The Fixed Buzzer"   — conflict reconciliation, recency wins
  B. "The Reliable"       — rich confirmed history, HIGH confidence
  C. "Cold Start"         — zero history, similarity fallback
  D. "Problem Address"    — high failure rate, ops dashboard spotlight
  E. "Stale Notes"        — old data flagged for decay
  F-T. Background addresses — variety for realistic ops dashboard
"""

from datetime import datetime, timedelta

BASE_DATE = datetime(2026, 6, 13)   # 3 weeks before hackathon date


def days_ago(n: int, hour: int = 10) -> str:
    return (BASE_DATE + timedelta(days=n, hours=hour)).isoformat()


DRIVERS = [
    {"id": "D001", "name": "Marcus T."},
    {"id": "D002", "name": "Priya K."},
    {"id": "D003", "name": "James O."},
    {"id": "D004", "name": "Sofia R."},
    {"id": "D005", "name": "Chen W."},
    {"id": "D006", "name": "Aisha M."},
    {"id": "D007", "name": "Liam B."},
]


SEED_NOTES = [

    # ── A. 142 Maple Avenue, Unit 3A — "The Fixed Buzzer" ─────────────────
    # Three drivers agree: buzzer broken. Then it gets fixed. Recency should win.
    {
        "address_id": "142_maple_3a",
        "address_text": "142 Maple Avenue, Unit 3A, Springfield",
        "driver_id": "D001", "driver_name": "Marcus T.",
        "status": "FAILED",
        "note_text": "Front door buzzer completely broken. Had to call the tenant. Use the side entrance on Maple Lane — green door, just knock.",
        "timestamp": days_ago(0, 9),
    },
    {
        "address_id": "142_maple_3a",
        "address_text": "142 Maple Avenue, Unit 3A, Springfield",
        "driver_id": "D002", "driver_name": "Priya K.",
        "status": "SUCCESS",
        "note_text": "Buzzer is busted. Tenant said use side door, ring the bell there. Works fine. No dog, friendly tenant.",
        "timestamp": days_ago(4, 14),
    },
    {
        "address_id": "142_maple_3a",
        "address_text": "142 Maple Avenue, Unit 3A, Springfield",
        "driver_id": "D003", "driver_name": "James O.",
        "status": "SUCCESS",
        "note_text": "Side door entry confirmed. Buzzer still broken as of today. Tenant usually home 9am–6pm weekdays.",
        "timestamp": days_ago(9, 11),
    },
    {
        "address_id": "142_maple_3a",
        "address_text": "142 Maple Avenue, Unit 3A, Springfield",
        "driver_id": "D005", "driver_name": "Chen W.",
        "status": "SUCCESS",
        "note_text": "Buzzer is FIXED now! Building management repaired it. Use main entrance buzzer, code 3A. Works perfectly.",
        "timestamp": days_ago(17, 10),
    },
    {
        "address_id": "142_maple_3a",
        "address_text": "142 Maple Avenue, Unit 3A, Springfield",
        "driver_id": "D007", "driver_name": "Liam B.",
        "status": "SUCCESS",
        "note_text": "Confirmed buzzer working, buzz 3A. Main entrance is fine now.",
        "timestamp": days_ago(19, 15),
    },

    # ── B. 88 Oak Street, Unit 12 — "The Reliable" ────────────────────────
    # Rich consistent history, multiple drivers, HIGH confidence.
    {
        "address_id": "88_oak_12",
        "address_text": "88 Oak Street, Unit 12, Springfield",
        "driver_id": "D004", "driver_name": "Sofia R.",
        "status": "SUCCESS",
        "note_text": "Gate code is #4521. Large dog in backyard — stay on the front path, it can't reach. If no answer, leave with Unit 11 (neighbor said ok).",
        "timestamp": days_ago(1, 10),
    },
    {
        "address_id": "88_oak_12",
        "address_text": "88 Oak Street, Unit 12, Springfield",
        "driver_id": "D002", "driver_name": "Priya K.",
        "status": "SUCCESS",
        "note_text": "Gate #4521 confirmed. Tenant prefers packages on the covered porch, not door. Dog barks loudly but is penned.",
        "timestamp": days_ago(5, 9),
    },
    {
        "address_id": "88_oak_12",
        "address_text": "88 Oak Street, Unit 12, Springfield",
        "driver_id": "D006", "driver_name": "Aisha M.",
        "status": "SUCCESS",
        "note_text": "Gate code #4521 still works. Leave on covered porch as usual. Tenant works from home, almost always in.",
        "timestamp": days_ago(10, 11),
    },
    {
        "address_id": "88_oak_12",
        "address_text": "88 Oak Street, Unit 12, Springfield",
        "driver_id": "D001", "driver_name": "Marcus T.",
        "status": "SUCCESS",
        "note_text": "Easy delivery. Gate 4521, porch drop. Tenant very friendly. Watch out for the dog noise — it sounds scary but it's safe.",
        "timestamp": days_ago(14, 16),
    },
    {
        "address_id": "88_oak_12",
        "address_text": "88 Oak Street, Unit 12, Springfield",
        "driver_id": "D003", "driver_name": "James O.",
        "status": "SUCCESS",
        "note_text": "All confirmed: gate 4521, drop on porch. Tenant leaves a water bottle for drivers in summer — nice touch.",
        "timestamp": days_ago(18, 8),
    },

    # ── C. 500 Pine Boulevard — "Cold Start" ──────────────────────────────
    # No notes. Zero history. Will trigger similarity-based fallback in recall().
    # (No entries — that's the point)

    # ── D. 33 Elm Court — "Problem Address" ───────────────────────────────
    # High failure rate, conflicting notes, ops dashboard spotlight.
    {
        "address_id": "33_elm_court",
        "address_text": "33 Elm Court, Springfield",
        "driver_id": "D001", "driver_name": "Marcus T.",
        "status": "FAILED",
        "note_text": "No one home. Intercom not working. No safe place to leave package. Returned to depot.",
        "timestamp": days_ago(1, 11),
    },
    {
        "address_id": "33_elm_court",
        "address_text": "33 Elm Court, Springfield",
        "driver_id": "D003", "driver_name": "James O.",
        "status": "FAILED",
        "note_text": "Nobody answered. A neighbor said tenant works night shifts — not home before 6pm. Try evenings.",
        "timestamp": days_ago(3, 10),
    },
    {
        "address_id": "33_elm_court",
        "address_text": "33 Elm Court, Springfield",
        "driver_id": "D005", "driver_name": "Chen W.",
        "status": "SUCCESS",
        "note_text": "Got lucky — tenant happened to be home at 7pm. Confirmed: works nights, home after 5:30pm. Always try after 5:30.",
        "timestamp": days_ago(6, 19),
    },
    {
        "address_id": "33_elm_court",
        "address_text": "33 Elm Court, Springfield",
        "driver_id": "D006", "driver_name": "Aisha M.",
        "status": "FAILED",
        "note_text": "Attempted 2pm — no answer. Intercom still broken. Left card. Should only attempt evenings per previous note.",
        "timestamp": days_ago(9, 14),
    },
    {
        "address_id": "33_elm_court",
        "address_text": "33 Elm Court, Springfield",
        "driver_id": "D007", "driver_name": "Liam B.",
        "status": "SUCCESS",
        "note_text": "Delivered at 6pm — tenant answered immediately. No intercom needed, just knock hard on front door.",
        "timestamp": days_ago(12, 18),
    },
    {
        "address_id": "33_elm_court",
        "address_text": "33 Elm Court, Springfield",
        "driver_id": "D002", "driver_name": "Priya K.",
        "status": "FAILED",
        "note_text": "Came at 3pm. No answer. I know, I know. Dispatch error — should be 5:30pm+.",
        "timestamp": days_ago(15, 15),
    },
    {
        "address_id": "33_elm_court",
        "address_text": "33 Elm Court, Springfield",
        "driver_id": "D004", "driver_name": "Sofia R.",
        "status": "FAILED",
        "note_text": "Another failed attempt in the morning. This address needs to be flagged for evening-only delivery.",
        "timestamp": days_ago(18, 9),
    },
    {
        "address_id": "33_elm_court",
        "address_text": "33 Elm Court, Springfield",
        "driver_id": "D001", "driver_name": "Marcus T.",
        "status": "FAILED",
        "note_text": "Failed again. Dispatch keeps sending us in the daytime. Evening only!",
        "timestamp": days_ago(20, 10),
    },

    # ── E. 201 Cedar Lane, Unit 7 — "Stale Notes" ─────────────────────────
    # Notes from 35+ days ago — should be flagged as potentially stale.
    {
        "address_id": "201_cedar_7",
        "address_text": "201 Cedar Lane, Unit 7, Springfield",
        "driver_id": "D003", "driver_name": "James O.",
        "status": "SUCCESS",
        "note_text": "Call ahead required — tenant is hard of hearing and can't hear buzzer. Mobile: 555-0147.",
        "timestamp": (BASE_DATE - timedelta(days=15)).isoformat(),
    },
    {
        "address_id": "201_cedar_7",
        "address_text": "201 Cedar Lane, Unit 7, Springfield",
        "driver_id": "D005", "driver_name": "Chen W.",
        "status": "SUCCESS",
        "note_text": "Confirmed: always call ahead. Tenant is very grateful when you do. Leave at door if no answer after 2 rings.",
        "timestamp": (BASE_DATE - timedelta(days=10)).isoformat(),
    },
    {
        "address_id": "201_cedar_7",
        "address_text": "201 Cedar Lane, Unit 7, Springfield",
        "driver_id": "D006", "driver_name": "Aisha M.",
        "status": "PARTIAL",
        "note_text": "Called ahead — number seems changed, got voicemail. Left at door. May need updated contact.",
        "timestamp": (BASE_DATE - timedelta(days=5)).isoformat(),
    },

    # ── F–T. Background addresses ──────────────────────────────────────────
    {
        "address_id": "77_birch_2b",
        "address_text": "77 Birch Road, Unit 2B, Springfield",
        "driver_id": "D004", "driver_name": "Sofia R.",
        "status": "SUCCESS",
        "note_text": "Apartment building, buzz 2B. Elevator is slow, take the stairs (2nd floor). Quick delivery.",
        "timestamp": days_ago(2, 10),
    },
    {
        "address_id": "77_birch_2b",
        "address_text": "77 Birch Road, Unit 2B, Springfield",
        "driver_id": "D007", "driver_name": "Liam B.",
        "status": "SUCCESS",
        "note_text": "Buzz 2B works. Stairs faster than elevator. Tenant usually at home in the morning.",
        "timestamp": days_ago(8, 9),
    },
    {
        "address_id": "15_spruce_penthouse",
        "address_text": "15 Spruce Street, Penthouse, Springfield",
        "driver_id": "D002", "driver_name": "Priya K.",
        "status": "FAILED",
        "note_text": "Security desk in lobby — must sign in and wait for concierge approval. Takes 10–15 min. Budget extra time.",
        "timestamp": days_ago(3, 11),
    },
    {
        "address_id": "15_spruce_penthouse",
        "address_text": "15 Spruce Street, Penthouse, Springfield",
        "driver_id": "D001", "driver_name": "Marcus T.",
        "status": "SUCCESS",
        "note_text": "Security sign-in confirmed. Ask for Carlos at the desk — he's helpful and speeds up the process.",
        "timestamp": days_ago(11, 14),
    },
    {
        "address_id": "304_willow_ave",
        "address_text": "304 Willow Avenue, Springfield",
        "driver_id": "D006", "driver_name": "Aisha M.",
        "status": "SUCCESS",
        "note_text": "House with a long driveway. Park on the street — tight turning radius for vans. Package goes to back door by default.",
        "timestamp": days_ago(5, 10),
    },
    {
        "address_id": "304_willow_ave",
        "address_text": "304 Willow Avenue, Springfield",
        "driver_id": "D003", "driver_name": "James O.",
        "status": "SUCCESS",
        "note_text": "Confirmed: back door. Two dogs, both friendly. Gate is usually unlocked.",
        "timestamp": days_ago(13, 9),
    },
    {
        "address_id": "22_riverside_dr_8c",
        "address_text": "22 Riverside Drive, Unit 8C, Springfield",
        "driver_id": "D005", "driver_name": "Chen W.",
        "status": "FAILED",
        "note_text": "Parking is brutal — no loading zone nearby. Took 8 minutes to find parking. Buzzer 8C works.",
        "timestamp": days_ago(4, 12),
    },
    {
        "address_id": "22_riverside_dr_8c",
        "address_text": "22 Riverside Drive, Unit 8C, Springfield",
        "driver_id": "D007", "driver_name": "Liam B.",
        "status": "SUCCESS",
        "note_text": "Use the alley behind the building for parking — unofficial but nobody bothers you for 10 min.",
        "timestamp": days_ago(10, 11),
    },
    {
        "address_id": "9_highland_ct",
        "address_text": "9 Highland Court, Springfield",
        "driver_id": "D004", "driver_name": "Sofia R.",
        "status": "SUCCESS",
        "note_text": "Gated community — main gate code is 7890#. Residents are strict about keeping it private.",
        "timestamp": days_ago(6, 8),
    },
    {
        "address_id": "9_highland_ct",
        "address_text": "9 Highland Court, Springfield",
        "driver_id": "D002", "driver_name": "Priya K.",
        "status": "SUCCESS",
        "note_text": "Gate code 7890# confirmed. House is third on the left after the gate. No issues.",
        "timestamp": days_ago(14, 10),
    },
    {
        "address_id": "60_park_lane_b1",
        "address_text": "60 Park Lane, Basement Unit B1, Springfield",
        "driver_id": "D001", "driver_name": "Marcus T.",
        "status": "FAILED",
        "note_text": "Basement unit is hard to find — go around the building to the back, look for the staircase going DOWN. No signage.",
        "timestamp": days_ago(7, 13),
    },
    {
        "address_id": "60_park_lane_b1",
        "address_text": "60 Park Lane, Basement Unit B1, Springfield",
        "driver_id": "D003", "driver_name": "James O.",
        "status": "SUCCESS",
        "note_text": "Found the back stairs. B1 is the first door at the bottom. Tenant asks you ring twice — they have hearing aids.",
        "timestamp": days_ago(15, 11),
    },
    {
        "address_id": "555_commerce_blvd",
        "address_text": "555 Commerce Boulevard, Suite 3, Springfield",
        "driver_id": "D006", "driver_name": "Aisha M.",
        "status": "SUCCESS",
        "note_text": "Commercial building. Loading dock is on the east side. Reception closes at 5pm — do not attempt after hours.",
        "timestamp": days_ago(2, 14),
    },
    {
        "address_id": "555_commerce_blvd",
        "address_text": "555 Commerce Boulevard, Suite 3, Springfield",
        "driver_id": "D005", "driver_name": "Chen W.",
        "status": "FAILED",
        "note_text": "Arrived at 5:20pm — reception closed. Dock locked. Must deliver before 5pm.",
        "timestamp": days_ago(7, 17),
    },
    {
        "address_id": "118_fern_st",
        "address_text": "118 Fern Street, Springfield",
        "driver_id": "D007", "driver_name": "Liam B.",
        "status": "SUCCESS",
        "note_text": "Tenant has mobility issues. Please bring package all the way inside if possible — do not leave on steps.",
        "timestamp": days_ago(3, 10),
    },
]


def get_all_seed_notes() -> list[dict]:
    return SEED_NOTES


def get_seed_addresses() -> list[dict]:
    """Return unique addresses from seed data, plus the cold-start address."""
    seen = {}
    for note in SEED_NOTES:
        if note["address_id"] not in seen:
            seen[note["address_id"]] = {
                "address_id": note["address_id"],
                "address_text": note["address_text"],
            }
    # Add the cold-start address explicitly
    seen["500_pine_blvd"] = {
        "address_id": "500_pine_blvd",
        "address_text": "500 Pine Boulevard, Springfield",
    }
    return list(seen.values())
