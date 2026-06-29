# ui/sidebar.py
# ─────────────────────────────────────────────────────────────────────────
# Idea Submission v2 nav redesign. Visual theme (gradient background, top
# badge) is preserved from the original unified sidebar — only the
# navigation structure changes, per the new spec:
#
#   Instructions / Readme        (shown only when clicked — no auto-display)
#   Problem Selection  (expandable)
#       ├── Idea Submission
#       ├── Feasibility Assessment
#       ├── Governance Review
#       └── Dashboard
#   Project Execution
#   Tracking
#
# Streamlit's sidebar has no native collapsible nav-group widget, so
# "Problem Selection" is implemented as a sidebar st.expander wrapping the
# four page_links — clicking the group header expands/collapses it, and
# each link inside still uses the normal page_link contract.
# ─────────────────────────────────────────────────────────────────────────

import streamlit as st

from utils.helpers import get_api_key, resolve_model

PAGE_BADGES = {
    "landing":           ("🤖", "AI Governance Platform"),
    "instructions":      ("📘", "Instructions"),
    "idea_submission":   ("💡", "Idea Submission"),
    "m2":                ("📊", "Feasibility Assessment"),
    "m3":                ("⚖️", "Gain-Pain Analysis"),
    "m4":                ("🏛️", "Governance Review"),
    "m5":                ("📊", "Analytics Dashboard"),
    "m6":                ("🧑‍⚖️", "Expert Advice"),
    "project_execution": ("🚧", "Project Execution"),
    "tracking":          ("📍", "Tracking"),
}


def _init_llm_defaults():
    """Resolve provider + model automatically from whichever API key is
    available (Streamlit secrets > env vars > config/app_config.json),
    with zero UI. Runs once per session — call_ai() reads the results
    from st.session_state. Unchanged from the original sidebar."""
    if "llm_provider" in st.session_state and "llm_model" in st.session_state:
        return
    api_key = get_api_key()
    if not api_key:
        return
    provider, model = resolve_model(api_key)
    st.session_state["api_key_input"] = api_key
    st.session_state["llm_provider"] = provider
    st.session_state["llm_model"] = model


def render_sidebar(active: str = "landing"):

    st.markdown("""
        <style>
        /* Expander header */
        [data-testid="stExpander"] details summary {
            background: #1f2b4d !important;
            color: white !important;
            border-radius: 10px !important;
            border: none !important;
        }

        /* Hover */
        [data-testid="stExpander"] details summary:hover {
            background: #2b3b66 !important;
        }

        /* Expanded content */
        [data-testid="stExpander"] details {
            background: transparent !important;
            border: none !important;
        }

        /* Remove white body */
        [data-testid="stExpander"] details div[role="group"] {
            background: transparent !important;
        }
        </style>
        """, unsafe_allow_html=True)
    
    """Render the unified sidebar with the new grouped navigation.
    `active` is one of PAGE_BADGES' keys."""
    _init_llm_defaults()

    icon, label = PAGE_BADGES.get(active, ("🤖", "AI Governance Platform"))
    st.sidebar.markdown(f"""
    <div style="background:#6D5DF6;padding:12px;border-radius:12px;
                margin-bottom:10px;font-weight:bold;">
    {icon} {label}
    </div>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("# 🤖 AI Governance")
        st.caption("TekFrameWorks Governance Platform")
        st.divider()

        st.write("")

        # ── Problem Selection — expandable group ────────────────────────────
        problem_selection_active = active in ("idea_submission", "m2", "m3", "m4", "m5", "m6")
        # ── Instructions / Readme — link only, never auto-displayed ────────
        st.page_link("pages/0_Instructions.py", label="📘 Instructions / Readme")
        with st.expander("🗂️ **Problem Selection**", expanded=problem_selection_active):
            st.page_link("pages/1_Idea_Submission.py", label="💡 Idea Submission")
            st.page_link("pages/2_Feasibility_Assessment.py", label="📊 Feasibility Assessment")
            st.page_link("pages/3_Gain_Pain_Analysis.py", label="⚖️ Gain-Pain Analysis")
            st.page_link("pages/4_Governance_Review.py", label="🏛️ Governance Review")
            st.page_link("pages/5_Analytics_Dashboard.py", label="📊 Dashboard")

        st.write("")
        st.page_link("pages/7_Project_Execution.py", label="🚧 Project Execution")
        st.page_link("pages/8_Tracking.py", label="📍 Tracking")

        # ── Secondary / supporting pages kept reachable but out of the way ──
        st.write("")
        with st.expander("More"):
            st.page_link("pages/6_Expert_Advice.py", label="🧑‍⚖️ Expert Advice")