"""
Last Mile — Streamlit frontend
Two views: Driver Briefing  |  Ops Dashboard
"""

import hashlib
import streamlit as st
import requests
from datetime import datetime
from audio_recorder_streamlit import audio_recorder

API_BASE = "http://localhost:8000"

# Quick-tap presets for the common cases — tapping one costs a driver ~1 second,
# versus typing a full sentence between stops. Maps chip label -> note phrase.
QUICK_TAGS = {
    "No answer": "No answer at the door.",
    "Left at door": "Left package at the door.",
    "Left with neighbor": "Left with a neighbor.",
    "Dog on property": "Dog on property — approach with caution.",
    "Gate code needed": "Gate code required for entry.",
    "Buzzer broken": "Buzzer is broken — knock or call instead.",
    "Buzzer fixed": "Buzzer works now.",
    "Call before arriving": "Call the customer before arriving.",
    "Use side entrance": "Use the side entrance.",
    "Signature required": "Signature required — hand to recipient only.",
}

st.set_page_config(
    page_title="Last Mile",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .confidence-HIGH    { background:#d4edda; color:#155724; padding:4px 10px; border-radius:12px; font-weight:600; }
    .confidence-MEDIUM  { background:#fff3cd; color:#856404; padding:4px 10px; border-radius:12px; font-weight:600; }
    .confidence-LOW     { background:#f8d7da; color:#721c24; padding:4px 10px; border-radius:12px; font-weight:600; }
    .confidence-COLD_START { background:#d1ecf1; color:#0c5460; padding:4px 10px; border-radius:12px; font-weight:600; }
    .briefing-box { background:#f8f9fa; border-left:4px solid #007bff; padding:16px; border-radius:4px; margin:12px 0; }
    .metric-card  { background:#ffffff; border:1px solid #dee2e6; border-radius:8px; padding:16px; text-align:center; }
    .stale-warning { background:#fff3cd; border:1px solid #ffc107; border-radius:4px; padding:8px 12px; margin:8px 0; }
    h1.app-title  { font-size:2rem; font-weight:700; margin-bottom:0; }
    .tagline      { color:#6c757d; font-size:1rem; margin-top:0; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def api_get(path: str, params: dict = None):
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Cannot reach the Last Mile API. Is the backend running? (`uvicorn backend.main:app --reload`)")
        return None
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_post(path: str, json: dict = None):
    try:
        r = requests.post(f"{API_BASE}{path}", json=json, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_delete(path: str):
    try:
        r = requests.delete(f"{API_BASE}{path}", timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def transcribe_voice_note(audio_bytes: bytes) -> str | None:
    """Send a recorded clip to the backend for Whisper transcription."""
    try:
        r = requests.post(
            f"{API_BASE}/transcribe",
            files={"audio": ("note.wav", audio_bytes, "audio/wav")},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["text"]
    except Exception as e:
        st.warning(f"Voice transcription unavailable ({e}). Use quick tags or type below instead.")
        return None


def confidence_badge(level: str) -> str:
    labels = {
        "HIGH": "Confirmed",
        "MEDIUM": "Likely accurate",
        "LOW": "Single report",
        "COLD_START": "No history",
    }
    return f'<span class="confidence-{level}">{labels.get(level, level)}</span>'


def get_addresses() -> list[dict]:
    data = api_get("/addresses")
    return data if data else []


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown('<h1 class="app-title">📦 Last Mile</h1>', unsafe_allow_html=True)
    st.markdown('<p class="tagline">Delivery memory that outlasts the driver</p>', unsafe_allow_html=True)
    st.divider()

    view = st.radio("View", ["Driver App", "Ops Dashboard"], label_visibility="collapsed")

    st.divider()
    st.subheader("Demo Setup")
    if st.button("Load demo data", use_container_width=True, type="primary"):
        with st.spinner("Seeding synthetic delivery history..."):
            result = api_post("/seed")
        if result:
            st.success(f"{result['notes_ingested']} notes loaded across {result['addresses_seeded']} addresses.")
            st.info("Memory graphs are building in the background (this calls Cognee's LLM — give it 20–30s then refresh).")

    health = api_get("/health")
    if health:
        st.caption(f"API online · {health.get('notes_in_db', 0)} notes in memory")
    else:
        st.caption("API offline")


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 1 — DRIVER APP
# ══════════════════════════════════════════════════════════════════════════════

if view == "Driver App":
    st.title("Driver Briefing")
    st.caption("What does Last Mile know about your next stop?")

    tab_brief, tab_log = st.tabs(["Pre-arrival briefing", "Log a delivery note"])

    # ── Tab: Briefing ────────────────────────────────────────────────────────
    with tab_brief:
        addresses = get_addresses()
        address_options = {a["address_text"]: a for a in addresses}

        col1, col2 = st.columns([3, 1])
        with col1:
            selected_label = st.selectbox(
                "Select delivery address",
                options=list(address_options.keys()) + ["Enter address manually..."],
            )
        with col2:
            st.write("")
            st.write("")
            get_brief = st.button("Get briefing", type="primary", use_container_width=True)

        if selected_label == "Enter address manually...":
            manual_addr = st.text_input("Address", placeholder="e.g. 500 Pine Boulevard, Springfield")
            addr_id = manual_addr.lower().replace(" ", "_").replace(",", "")
            addr_text = manual_addr
        else:
            addr_id = address_options[selected_label]["address_id"]
            addr_text = selected_label

        if get_brief and addr_id:
            with st.spinner("Querying memory..."):
                data = api_get(f"/briefing/{addr_id}", params={"address_text": addr_text})

            if data:
                conf = data["confidence"]
                st.markdown(
                    f"### {data['address_text']}&nbsp;&nbsp;{confidence_badge(conf)}",
                    unsafe_allow_html=True,
                )

                if data.get("is_stale"):
                    st.markdown(
                        '<div class="stale-warning">⚠️ Most recent notes for this address are older than 30 days — treat with caution.</div>',
                        unsafe_allow_html=True,
                    )

                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Total visits", data["total_visits"])
                col_b.metric("Failed attempts", data["failed_visits"])
                if data["last_visit"]:
                    try:
                        last = datetime.fromisoformat(data["last_visit"])
                        col_c.metric("Last visit", last.strftime("%b %d, %Y"))
                    except Exception:
                        col_c.metric("Last visit", data["last_visit"])

                st.markdown("#### What you need to know")
                st.markdown(
                    f'<div class="briefing-box">{data["briefing"].replace(chr(10), "<br>")}</div>',
                    unsafe_allow_html=True,
                )

                if data["key_facts"] and conf != "COLD_START":
                    with st.expander("Key facts extracted from driver reports"):
                        for fact in data["key_facts"]:
                            st.markdown(f"- {fact}")

    # ── Tab: Log note ────────────────────────────────────────────────────────
    with tab_log:
        st.subheader("Post-delivery note")
        st.caption("Your note becomes memory for the next driver at this address.")

        addresses = get_addresses()
        address_options = {a["address_text"]: a for a in addresses}

        selected_for_log = st.selectbox(
            "Address",
            options=list(address_options.keys()) + ["Enter manually..."],
            key="log_address_select",
        )

        if selected_for_log == "Enter manually...":
            log_addr_text = st.text_input("Address text", key="log_addr_text_manual")
            log_addr_id = log_addr_text.lower().replace(" ", "_").replace(",", "")
        else:
            log_addr_id = address_options[selected_for_log]["address_id"]
            log_addr_text = selected_for_log

        col_d, col_e = st.columns(2)
        with col_d:
            driver_name = st.text_input("Your name", placeholder="e.g. Alex P.")
            driver_id = st.text_input("Driver ID", placeholder="e.g. D008")
        with col_e:
            status = st.selectbox("Delivery outcome", ["SUCCESS", "FAILED", "PARTIAL"])

        st.markdown("**Quick tags** — tap what applies, no typing needed")
        selected_tags = st.pills(
            "Quick tags",
            options=list(QUICK_TAGS.keys()),
            selection_mode="multi",
            label_visibility="collapsed",
            key="log_quick_tags",
        )

        st.markdown("**Or record a voice note**")
        audio_bytes = audio_recorder(
            text="Tap to record, tap again to stop",
            icon_size="2x",
            key="log_voice_recorder",
        )

        if audio_bytes:
            audio_hash = hashlib.md5(audio_bytes).hexdigest()
            if st.session_state.get("log_last_audio_hash") != audio_hash:
                st.session_state["log_last_audio_hash"] = audio_hash
                with st.spinner("Transcribing voice note..."):
                    st.session_state["log_voice_text"] = transcribe_voice_note(audio_bytes) or ""

        voice_text = st.session_state.get("log_voice_text", "")
        if voice_text:
            st.caption(f'🎙️ Heard: "{voice_text}"')

        manual_extra = st.text_area(
            "Anything else? (optional)",
            placeholder="Only needed if quick tags + voice note don't cover it.",
            height=70,
        )

        # Compose the final note from tags + voice + manual text — the driver
        # rarely needs to type anything for the common cases.
        composed_parts = [QUICK_TAGS[t] for t in selected_tags]
        if voice_text:
            composed_parts.append(voice_text)
        if manual_extra:
            composed_parts.append(manual_extra)
        note_text = " ".join(composed_parts).strip()
        if not note_text and status == "SUCCESS":
            note_text = "Delivered without issues."

        if note_text:
            st.text_area("Note preview", value=note_text, height=80, disabled=True)

        if st.button("Submit note", type="primary"):
            if not all([log_addr_id, log_addr_text, driver_name, driver_id]):
                st.warning("Please fill in address and driver details.")
            elif not note_text:
                st.warning("Tap a quick tag, record a voice note, or add a few words first.")
            else:
                payload = {
                    "address_id": log_addr_id,
                    "address_text": log_addr_text,
                    "driver_id": driver_id,
                    "driver_name": driver_name,
                    "status": status,
                    "note_text": note_text,
                }
                with st.spinner("Saving to memory..."):
                    result = api_post("/notes", json=payload)
                if result:
                    st.success("Note saved. Memory graph updating in the background.")
                    st.session_state["log_voice_text"] = ""
                    st.session_state["log_last_audio_hash"] = None


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 2 — OPS DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

elif view == "Ops Dashboard":
    st.title("Ops Dashboard")
    st.caption("Delivery failure patterns, memory coverage, and cost impact.")

    with st.spinner("Loading dashboard..."):
        data = api_get("/dashboard")

    if not data:
        st.stop()

    # ── Top metrics ───────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Addresses tracked", data["total_addresses"])
    col2.metric("Total deliveries", data["total_deliveries"])
    col3.metric(
        "Network failure rate",
        f"{data['overall_failure_rate'] * 100:.1f}%",
    )
    col4.metric(
        "Est. cost avoided",
        f"${data['total_cost_avoided']:,.0f}",
        help="Assumes memory-guided delivery prevents ~60% of otherwise-failed attempts",
    )

    st.divider()

    # ── Address breakdown ─────────────────────────────────────────────────────
    st.subheader("Address breakdown")

    for entry in data["addresses"]:
        conf = entry["confidence"]
        failure_pct = entry["failure_rate"] * 100

        color = "#dc3545" if failure_pct > 50 else "#ffc107" if failure_pct > 25 else "#198754"

        with st.expander(
            f"{'🔴' if failure_pct > 50 else '🟡' if failure_pct > 25 else '🟢'}  "
            f"{entry['address_text']}  —  "
            f"{failure_pct:.0f}% failure rate"
        ):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total deliveries", entry["total_deliveries"])
            c2.metric("Failed attempts", entry["failed_deliveries"])
            c3.metric("Cost at risk", f"${entry['cost_at_risk']:.0f}")
            c4.metric("Cost avoided", f"${entry['cost_avoided']:.0f}")

            st.markdown(
                f"**Memory confidence:** {confidence_badge(conf)}&nbsp;&nbsp;"
                f"**Conflicts detected:** {entry['conflicts_detected']}",
                unsafe_allow_html=True,
            )

            if entry.get("last_delivery"):
                try:
                    last = datetime.fromisoformat(entry["last_delivery"])
                    st.caption(f"Last delivery: {last.strftime('%B %d, %Y')}")
                except Exception:
                    pass

            st.divider()

            col_act1, col_act2, col_act3 = st.columns(3)
            with col_act1:
                if st.button("Get briefing", key=f"brief_{entry['address_id']}"):
                    with st.spinner("Querying memory..."):
                        brief = api_get(
                            f"/briefing/{entry['address_id']}",
                            params={"address_text": entry["address_text"]},
                        )
                    if brief:
                        st.info(brief["briefing"])

            with col_act2:
                if st.button("Force improve()", key=f"improve_{entry['address_id']}"):
                    with st.spinner("Rebuilding memory graph..."):
                        result = api_post(f"/improve/{entry['address_id']}")
                    if result:
                        st.success(result["message"])

            with col_act3:
                if st.button("Purge (forget)", key=f"forget_{entry['address_id']}", type="secondary"):
                    result = api_delete(f"/forget/{entry['address_id']}")
                    if result:
                        st.warning(result["message"])
                        st.rerun()

    # ── Cost impact model ─────────────────────────────────────────────────────
    st.divider()
    st.subheader("Cost impact model")
    st.caption("Adjust the assumption to model different operator scenarios.")

    col_model1, col_model2 = st.columns(2)
    with col_model1:
        cost_per_failure = st.slider("Cost per failed attempt ($)", 5, 50, 15)
        memory_lift = st.slider("Memory prevents % of failures", 10, 90, 60)
    with col_model2:
        weekly_deliveries = st.number_input("Weekly deliveries in network", value=1000, step=100)
        baseline_failure = st.slider("Baseline failure rate (%)", 5, 40, 15)

    weekly_failures = weekly_deliveries * (baseline_failure / 100)
    prevented = weekly_failures * (memory_lift / 100)
    weekly_saving = prevented * cost_per_failure
    annual_saving = weekly_saving * 52

    st.metric("Estimated weekly savings", f"${weekly_saving:,.0f}")
    st.metric("Estimated annual savings", f"${annual_saving:,.0f}")
    st.caption(
        f"Model: {weekly_deliveries:,} deliveries/week × {baseline_failure}% failure rate = "
        f"{weekly_failures:.0f} failures → memory prevents {memory_lift}% → "
        f"{prevented:.0f} fewer failures × ${cost_per_failure} = ${weekly_saving:,.0f}/week"
    )
