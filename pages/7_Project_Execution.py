# pages/7_Project_Execution.py
# ─────────────────────────────────────────────────────────────────────────
# Spec §17 — Project Execution page. Placeholder per spec ("Can initially
# be placeholder"). Shows approved problems as candidate projects, with
# Project Name / Status / Owner / Milestones / Progress % — milestones and
# progress are placeholder fields for now since no execution-tracking
# schema exists yet; this lays out the UI shape for that future work.
# ─────────────────────────────────────────────────────────────────────────

import streamlit as st

from ui.theme import apply_theme
from ui.sidebar import render_sidebar
from database.db import db_load_all

st.set_page_config(page_title="Project Execution — AI Governance Platform",
                    page_icon="🚧", layout="wide", initial_sidebar_state="expanded")

apply_theme()
render_sidebar("project_execution")

st.title("🚧 Project Execution")
st.caption("Track execution of approved AI initiatives after governance sign-off.")

st.info("🛠️ This page is a placeholder. Full milestone tracking, progress percentage, "
        "and execution workflows will be built out in a future iteration.")

records = db_load_all()
approved = [r for r in records if (r.get("status") or "") == "Approved"]

if not approved:
    st.markdown("""<div style="text-align:center;padding:3rem;color:#888;">
        <div style="font-size:2.5rem;">📋</div>
        <h3>No approved projects yet</h3>
        <p>Once a problem statement is approved in Governance Review, it will appear here
        as a project ready for execution tracking.</p>
    </div>""", unsafe_allow_html=True)
    st.stop()

st.markdown(f"### {len(approved)} approved project(s)")

for r in approved:
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        with col1:
            st.markdown(f"**{r.get('id', '')}**")
            st.caption((r.get("problem_statement", "") or "")[:100])
        with col2:
            st.markdown("**Status**")
            st.markdown("🟢 Ready to start")
        with col3:
            st.markdown("**Owner**")
            st.markdown(r.get("action_owner", "") or "—")
        with col4:
            st.markdown("**Progress**")
            st.progress(0, text="0%")

        with st.expander("Milestones (placeholder)"):
            st.markdown("""
            - [ ] Kickoff & resourcing
            - [ ] Data access provisioned
            - [ ] Pilot build
            - [ ] Pilot review
            - [ ] Production rollout
            """)
            st.caption("Milestone tracking is not yet wired to a database — "
                       "this is a static placeholder checklist for now.")
