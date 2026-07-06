"""
Last Mile — Streamlit frontend
Two views: Driver App  |  Ops Dashboard
"""

import hashlib
import streamlit as st
import requests
from datetime import datetime
from audio_recorder_streamlit import audio_recorder

API_BASE = "http://localhost:8000"

QUICK_TAGS = {
    "No answer":          "No answer at the door.",
    "Left at door":       "Left package at the door.",
    "Left with neighbor": "Left with a neighbor.",
    "Dog on property":    "Dog on property — approach with caution.",
    "Gate code needed":   "Gate code required for entry.",
    "Buzzer broken":      "Buzzer is broken — knock or call instead.",
    "Buzzer fixed":       "Buzzer is working again.",
    "Call before arriving": "Call the customer before arriving.",
    "Use side entrance":  "Use the side entrance.",
    "Signature required": "Signature required — hand to recipient only.",
}

st.set_page_config(
    page_title="Last Mile",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* Confidence badges */
    .badge-HIGH       { background:#166534; color:#bbf7d0; padding:4px 12px; border-radius:20px; font-weight:600; font-size:0.85rem; }
    .badge-MEDIUM     { background:#854d0e; color:#fef08a; padding:4px 12px; border-radius:20px; font-weight:600; font-size:0.85rem; }
    .badge-LOW        { background:#7f1d1d; color:#fecaca; padding:4px 12px; border-radius:20px; font-weight:600; font-size:0.85rem; }
    .badge-COLD_START { background:#164e63; color:#a5f3fc; padding:4px 12px; border-radius:20px; font-weight:600; font-size:0.85rem; }

    /* Briefing box */
    .briefing-box {
        background: #1e2a3a;
        border-left: 4px solid #3b82f6;
        padding: 18px 20px;
        border-radius: 6px;
        margin: 12px 0;
        font-size: 1rem;
        line-height: 1.6;
        color: #e2e8f0;
    }

    /* Stale warning */
    .stale-warning {
        background: #2d2006;
        border: 1px solid #f59e0b;
        border-radius: 6px;
        padding: 10px 14px;
        margin: 8px 0;
        font-size: 0.9rem;
        color: #fde68a;
    }

    /* Risk cards */
    .risk-low      { background:#14532d; color:#bbf7d0; border-radius:8px; padding:12px 16px; }
    .risk-medium   { background:#422006; color:#fef08a; border-radius:8px; padding:12px 16px; }
    .risk-high     { background:#7f1d1d; color:#fecaca; border-radius:8px; padding:12px 16px; }
    .risk-critical { background:#450a0a; color:#fca5a5; border-radius:8px; padding:12px 16px; border:2px solid #ef4444; }

    /* Section label */
    .section-label {
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #6b7280;
        margin-bottom: 6px;
    }

    /* Hide Streamlit branding */
    #MainMenu { visibility: hidden; }
    footer    { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def api_get(path: str, params: dict = None):
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("Can't reach the backend. Is it running? Try: `bash run.sh`")
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


def transcribe_voice(audio_bytes: bytes) -> str | None:
    try:
        r = requests.post(
            f"{API_BASE}/transcribe",
            files={"audio": ("note.wav", audio_bytes, "audio/wav")},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["text"]
    except Exception as e:
        st.warning(f"Voice transcription unavailable. Use tags or type your note instead.")
        return None


def confidence_badge(level: str) -> str:
    labels = {
        "HIGH":       "Confirmed by multiple drivers",
        "MEDIUM":     "Likely accurate",
        "LOW":        "One report — unverified",
        "COLD_START": "No history yet",
    }
    return f'<span class="badge-{level}">{labels.get(level, level)}</span>'


def risk_icon(level: str) -> str:
    return {"low": "🟢", "medium": "🟡", "high": "🔴", "critical": "🚨"}.get(level, "⚪")


def get_addresses() -> list[dict]:
    data = api_get("/addresses")
    return data if data else []


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.image("assets/logo2.png", width=120)
    st.markdown("## Last Mile")
    st.caption("Delivery memory that outlasts the driver.")
    st.divider()

    view = st.radio(
        "Who are you?",
        ["🚗  I'm a driver", "📊  I manage deliveries"],
        label_visibility="visible",
    )

    st.divider()
    st.markdown("**Demo**")
    st.caption("Load sample delivery history to explore the app.")
    if st.button("Load demo data", use_container_width=True, type="primary"):
        with st.spinner("Loading sample addresses and notes..."):
            result = api_post("/seed")
        if result:
            st.success(f"Loaded {result['notes_ingested']} notes across {result['addresses_seeded']} addresses.")
            st.info("Memory graphs are building in the background — wait ~30 seconds then refresh.")

    st.divider()
    health = api_get("/health")
    if health:
        st.caption(f"✅ API online · {health.get('notes_in_db', 0)} notes stored")
    else:
        st.caption("❌ API offline")


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 1 — DRIVER APP
# ══════════════════════════════════════════════════════════════════════════════

if "driver" in view:
    st.title("📦 What should I know before I arrive?")
    st.caption("Get a briefing based on everything previous drivers have reported about this address.")

    tab_brief, tab_log = st.tabs(["Get a briefing", "Log a delivery note"])

    # ── Tab: Briefing ────────────────────────────────────────────────────────
    with tab_brief:
        addresses = get_addresses()
        address_options = {a["address_text"]: a for a in addresses}

        st.markdown('<p class="section-label">Select your delivery address</p>', unsafe_allow_html=True)
        col1, col2 = st.columns([4, 1])
        with col1:
            selected_label = st.selectbox(
                "Address",
                options=list(address_options.keys()) + ["Type an address manually..."],
                label_visibility="collapsed",
            )
        with col2:
            st.write("")
            get_brief = st.button("Get briefing →", type="primary", use_container_width=True)

        if selected_label == "Type an address manually...":
            manual_addr = st.text_input("Address", placeholder="e.g. 500 Pine Boulevard, Springfield", label_visibility="collapsed")
            addr_id   = manual_addr.lower().replace(" ", "_").replace(",", "")
            addr_text = manual_addr
        else:
            addr_id   = address_options[selected_label]["address_id"]
            addr_text = selected_label

        if get_brief and addr_id:
            with st.spinner("Checking delivery memory..."):
                data = api_get(f"/briefing/{addr_id}", params={"address_text": addr_text})

            if data:
                st.session_state["last_briefing"]   = data["briefing"]
                st.session_state["last_addr_id"]    = addr_id
                st.session_state["last_addr_text"]  = addr_text

                conf = data["confidence"]
                st.markdown(f"### {data['address_text']}")
                st.markdown(confidence_badge(conf), unsafe_allow_html=True)
                st.write("")

                if data.get("is_stale"):
                    st.markdown(
                        '<div class="stale-warning">⚠️ The most recent notes for this address are over 30 days old. Treat this information with caution.</div>',
                        unsafe_allow_html=True,
                    )

                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Total deliveries", data["total_visits"])
                col_b.metric("Failed attempts",  data["failed_visits"])
                if data["last_visit"]:
                    try:
                        last = datetime.fromisoformat(data["last_visit"])
                        col_c.metric("Last visited", last.strftime("%b %d, %Y"))
                    except Exception:
                        col_c.metric("Last visited", str(data["last_visit"])[:10])

                st.markdown("#### Here's what you need to know")
                st.markdown(
                    f'<div class="briefing-box">{data["briefing"].replace(chr(10), "<br>")}</div>',
                    unsafe_allow_html=True,
                )

                if data["key_facts"] and conf != "COLD_START":
                    with st.expander("See all reported facts"):
                        for fact in data["key_facts"]:
                            st.markdown(f"- {fact}")

        # ── Feedback loop ─────────────────────────────────────────────────────
        if st.session_state.get("last_briefing") and st.session_state.get("last_addr_id") == addr_id:
            st.divider()
            st.markdown("#### After your delivery")
            st.caption("Your feedback helps improve briefings for the next driver.")

            fb_col1, fb_col2, fb_col3 = st.columns(3)
            fb_rating = None
            if fb_col1.button("✅  That was accurate", use_container_width=True):
                fb_rating = "accurate"
            if fb_col2.button("⚠️  Partially right", use_container_width=True):
                fb_rating = "partial"
            if fb_col3.button("❌  That was wrong", use_container_width=True):
                fb_rating = "inaccurate"

            if fb_rating:
                st.session_state["fb_rating"] = fb_rating

            if st.session_state.get("fb_rating"):
                rating = st.session_state["fb_rating"]
                if rating in ("inaccurate", "partial"):
                    fb_comment = st.text_area(
                        "What was wrong or missing?",
                        placeholder="e.g. The buzzer is fixed now. Use the main entrance.",
                        height=80,
                        key="fb_comment",
                    )
                else:
                    fb_comment = ""
                    st.success("Great — we'll use this to reinforce what's in memory.")

                fb_col_a, fb_col_b = st.columns(2)
                fb_driver_name = fb_col_a.text_input("Your name", placeholder="e.g. Alex P.", key="fb_name")
                fb_driver_id   = fb_col_b.text_input("Driver ID",  placeholder="e.g. D008",   key="fb_id")

                if st.button("Submit feedback", type="primary"):
                    if not fb_driver_name or not fb_driver_id:
                        st.warning("Please enter your name and driver ID.")
                    else:
                        payload = {
                            "address_id":        st.session_state["last_addr_id"],
                            "address_text":      st.session_state["last_addr_text"],
                            "rating":            rating,
                            "original_briefing": st.session_state["last_briefing"],
                            "driver_comment":    fb_comment,
                            "driver_id":         fb_driver_id,
                            "driver_name":       fb_driver_name,
                        }
                        with st.spinner("Updating memory..."):
                            result = api_post("/feedback", json=payload)
                        if result:
                            st.success(result["message"])
                            for k in ["fb_rating", "last_briefing", "last_addr_id", "last_addr_text"]:
                                st.session_state.pop(k, None)

    # ── Tab: Log note ────────────────────────────────────────────────────────
    with tab_log:
        st.markdown("### Log what you found")
        st.caption("Your note becomes memory for the next driver. Takes 10 seconds.")

        addresses = get_addresses()
        address_options = {a["address_text"]: a for a in addresses}

        st.markdown('<p class="section-label">Address</p>', unsafe_allow_html=True)
        selected_for_log = st.selectbox(
            "Address",
            options=list(address_options.keys()) + ["Type manually..."],
            key="log_address_select",
            label_visibility="collapsed",
        )
        if selected_for_log == "Type manually...":
            log_addr_text = st.text_input("Address", key="log_addr_manual", label_visibility="collapsed", placeholder="Full address")
            log_addr_id   = log_addr_text.lower().replace(" ", "_").replace(",", "")
        else:
            log_addr_id   = address_options[selected_for_log]["address_id"]
            log_addr_text = selected_for_log

        col_d, col_e, col_f = st.columns(3)
        driver_name = col_d.text_input("Your name",   placeholder="e.g. Alex P.")
        driver_id   = col_e.text_input("Driver ID",   placeholder="e.g. D008")
        status      = col_f.selectbox("How did it go?", ["SUCCESS — delivered", "FAILED — couldn't deliver", "PARTIAL — left at door / neighbour"])
        status_code = status.split(" ")[0]

        st.markdown('<p class="section-label" style="margin-top:12px">What happened? (tap what applies)</p>', unsafe_allow_html=True)
        selected_tags = st.pills(
            "Quick tags",
            options=list(QUICK_TAGS.keys()),
            selection_mode="multi",
            label_visibility="collapsed",
            key="log_quick_tags",
        )

        st.markdown('<p class="section-label" style="margin-top:8px">Or record a voice note</p>', unsafe_allow_html=True)
        audio_bytes = audio_recorder(
            text="Tap to record · tap again to stop",
            icon_size="2x",
            key="log_voice_recorder",
        )
        if audio_bytes:
            audio_hash = hashlib.md5(audio_bytes).hexdigest()
            if st.session_state.get("log_last_audio_hash") != audio_hash:
                st.session_state["log_last_audio_hash"] = audio_hash
                with st.spinner("Transcribing..."):
                    st.session_state["log_voice_text"] = transcribe_voice(audio_bytes) or ""

        voice_text = st.session_state.get("log_voice_text", "")
        if voice_text:
            st.caption(f'🎙️ Heard: "{voice_text}"')

        extra = st.text_area(
            "Anything else to add? (optional)",
            placeholder="Any detail that would help the next driver.",
            height=70,
        )

        composed = [QUICK_TAGS[t] for t in selected_tags]
        if voice_text:  composed.append(voice_text)
        if extra:       composed.append(extra)
        note_text = " ".join(composed).strip()
        if not note_text and status_code == "SUCCESS":
            note_text = "Delivered without issues."

        if note_text:
            st.markdown('<p class="section-label" style="margin-top:8px">Your note</p>', unsafe_allow_html=True)
            st.info(note_text)

        if st.button("Save note →", type="primary"):
            if not all([log_addr_id, log_addr_text, driver_name, driver_id]):
                st.warning("Please fill in the address and your driver details.")
            elif not note_text:
                st.warning("Tap a quick tag, record a voice note, or add a few words first.")
            else:
                payload = {
                    "address_id":   log_addr_id,
                    "address_text": log_addr_text,
                    "driver_id":    driver_id,
                    "driver_name":  driver_name,
                    "status":       status_code,
                    "note_text":    note_text,
                }
                with st.spinner("Saving to memory..."):
                    result = api_post("/notes", json=payload)
                if result:
                    st.success("Note saved. The next driver at this address will see it.")
                    st.session_state["log_voice_text"]      = ""
                    st.session_state["log_last_audio_hash"] = None


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 2 — OPS DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

elif "manage" in view:
    st.title("📊 Delivery Operations")
    st.caption("Failure patterns, memory coverage, and cost impact across your network.")

    with st.spinner("Loading..."):
        data = api_get("/dashboard")

    if not data:
        st.stop()

    # ── Summary metrics ───────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Addresses tracked",   data["total_addresses"])
    col2.metric("Total deliveries",    data["total_deliveries"])
    col3.metric(
        "Network failure rate",
        f"{data['overall_failure_rate'] * 100:.1f}%",
    )
    col4.metric(
        "Estimated savings",
        f"${data['total_cost_avoided']:,.0f}",
        help="Assumes memory-guided delivery prevents ~60% of otherwise-failed attempts",
    )

    st.divider()

    # ── Address breakdown ─────────────────────────────────────────────────────
    st.subheader("Address breakdown")
    st.caption("Click any address to see details and run agent actions.")

    for entry in data["addresses"]:
        conf        = entry["confidence"]
        failure_pct = entry["failure_rate"] * 100
        icon        = "🔴" if failure_pct > 50 else "🟡" if failure_pct > 25 else "🟢"

        with st.expander(f"{icon}  {entry['address_text']}  —  {failure_pct:.0f}% failure rate"):

            # Stats row
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Deliveries",     entry["total_deliveries"])
            c2.metric("Failed",         entry["failed_deliveries"])
            c3.metric("Cost at risk",   f"${entry['cost_at_risk']:.0f}")
            c4.metric("Cost avoided",   f"${entry['cost_avoided']:.0f}")

            meta_col1, meta_col2 = st.columns(2)
            with meta_col1:
                st.markdown(f"**Memory quality:** {confidence_badge(conf)}", unsafe_allow_html=True)
            with meta_col2:
                if entry["conflicts_detected"]:
                    st.markdown(f"⚠️ **{entry['conflicts_detected']} conflict(s) detected**")
            if entry.get("last_delivery"):
                try:
                    last = datetime.fromisoformat(entry["last_delivery"])
                    st.caption(f"Last delivery: {last.strftime('%B %d, %Y')}")
                except Exception:
                    pass

            st.divider()
            st.markdown("**Actions**")

            # Row 1: briefing + risk check
            act1, act2 = st.columns(2)

            with act1:
                if st.button("📋  Get driver briefing", key=f"brief_{entry['address_id']}", use_container_width=True):
                    with st.spinner("Checking memory..."):
                        brief = api_get(
                            f"/briefing/{entry['address_id']}",
                            params={"address_text": entry["address_text"]},
                        )
                    if brief:
                        st.markdown(
                            f'<div class="briefing-box">{brief["briefing"].replace(chr(10), "<br>")}</div>',
                            unsafe_allow_html=True,
                        )

            with act2:
                hour_col, btn_col = st.columns([2, 3])
                planned_hour = hour_col.number_input(
                    "Hour", min_value=0, max_value=23, value=10,
                    key=f"risk_hour_{entry['address_id']}",
                    help="Planned delivery hour (24h clock)",
                )
                with btn_col:
                    st.write("")
                    run_risk = st.button("⚠️  Check delivery risk", key=f"risk_{entry['address_id']}", use_container_width=True)
                if run_risk:
                    with st.spinner("Assessing risk..."):
                        risk = api_get(
                            f"/risk/{entry['address_id']}",
                            params={"address_text": entry["address_text"], "hour": planned_hour},
                        )
                    if risk:
                        lvl = risk["risk_level"]
                        css = f"risk-{lvl}"
                        st.markdown(
                            f'<div class="{css}">'
                            f'{risk_icon(lvl)} <strong>{lvl.upper()} RISK</strong><br>'
                            f'{risk["recommendation"]}'
                            f'{"<br>📞 Call ahead before sending a driver." if risk["should_call_ahead"] else ""}'
                            f'{"<br>🕐 Best window: " + risk["best_time_window"] if risk["best_time_window"] != "any time" else ""}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

            # Row 2: resolve + improve + forget
            act3, act4, act5 = st.columns(3)

            with act3:
                if st.button("🔍  Resolve conflicts", key=f"resolve_{entry['address_id']}", use_container_width=True):
                    with st.spinner("Running conflict analysis..."):
                        result = api_post(f"/resolve/{entry['address_id']}?address_text={entry['address_text']}")
                    if result:
                        if result.get("has_conflict"):
                            st.warning(f"Conflict found: {', '.join(result['conflicting_facts'])}")
                            st.info(f"Resolved to: {result['resolved_truth']}")
                        else:
                            st.success("No conflicts — all driver notes are consistent.")

            with act4:
                if st.button("🔄  Rebuild memory", key=f"improve_{entry['address_id']}", use_container_width=True, help="Re-runs graph construction and conflict detection for this address"):
                    with st.spinner("Rebuilding..."):
                        result = api_post(f"/improve/{entry['address_id']}")
                    if result:
                        st.success("Memory graph updated.")

            with act5:
                if st.button("🗑️  Erase all data", key=f"forget_{entry['address_id']}", use_container_width=True, type="secondary", help="Permanently removes all notes and memory for this address"):
                    result = api_delete(f"/forget/{entry['address_id']}")
                    if result:
                        st.warning(f"All data erased for this address.")
                        st.rerun()

    # ── Cost model ────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Cost impact calculator")
    st.caption("Adjust the numbers to match your operation and see the projected savings.")

    col_left, col_right = st.columns(2)
    with col_left:
        cost_per_failure  = st.slider("Cost per failed delivery ($)", 5, 50, 15)
        memory_lift       = st.slider("% of failures memory can prevent", 10, 90, 60)
    with col_right:
        weekly_deliveries = st.number_input("Deliveries per week", value=1000, step=100)
        baseline_failure  = st.slider("Current failure rate (%)", 5, 40, 15)

    weekly_failures = weekly_deliveries * (baseline_failure / 100)
    prevented       = weekly_failures * (memory_lift / 100)
    weekly_saving   = prevented * cost_per_failure
    annual_saving   = weekly_saving * 52

    r1, r2 = st.columns(2)
    r1.metric("Weekly savings", f"${weekly_saving:,.0f}")
    r2.metric("Annual savings", f"${annual_saving:,.0f}")
    st.caption(
        f"{weekly_deliveries:,} deliveries/week · {baseline_failure}% fail rate · "
        f"memory prevents {memory_lift}% of those · ${cost_per_failure} each = "
        f"${weekly_saving:,.0f}/week saved"
    )
