# pages/8_Tracking.py
# ─────────────────────────────────────────────────────────────────────────
# Spec §18 — Tracking page. Tracks lifecycle of all submissions:
# Submitted / Under Review / Approved / Rejected / In Progress / Completed.
# Uses existing database records (problem_statements.status +
# governance_decisions) — no new schema required for this first pass.
# ─────────────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd

from ui.theme import apply_theme
from ui.sidebar import render_sidebar
from database.db import db_load_all, db_load_governance_decisions
from config.constants import STATUS_BADGE

st.set_page_config(page_title="Tracking — AI Governance Platform",
                    page_icon="📍", layout="wide", initial_sidebar_state="expanded")

apply_theme()
render_sidebar("tracking")

st.title("📍 Tracking")
st.caption("Lifecycle status of every submission — Submitted → Under Review → Approved / "
           "Rejected / Deferred → In Progress → Completed.")

records = db_load_all()
decisions = db_load_governance_decisions()
decision_by_problem = {}
for d in decisions:
    pid = d[1]
    decision_by_problem.setdefault(pid, []).append(d)

LIFECYCLE_STAGES = ["Submitted", "Under Review", "Approved", "Rejected", "Deferred",
                    "In Progress", "Completed"]

if not records:
    st.markdown("""<div style="text-align:center;padding:3rem;color:#888;">
        <div style="font-size:2.5rem;">📭</div>
        <h3>No submissions yet</h3>
        <p>Once ideas are submitted, their lifecycle status will appear here.</p>
    </div>""", unsafe_allow_html=True)
    st.stop()

# ── Summary counts ───────────────────────────────────────────────────────
status_counts = {}
for r in records:
    s = r.get("status", "Submitted") or "Submitted"
    status_counts[s] = status_counts.get(s, 0) + 1

cols = st.columns(len(LIFECYCLE_STAGES))
for col, stage in zip(cols, LIFECYCLE_STAGES):
    with col:
        count = status_counts.get(stage, 0)
        sc = STATUS_BADGE.get(stage, "b-submitted")
        st.markdown(f"""
        <div class="card" style="text-align:center;padding:1rem 0.5rem;min-height:0;">
          <div style="font-size:1.6rem;font-weight:800;">{count}</div>
          <div class="badge {sc}" style="margin-top:6px;">{stage}</div>
        </div>""", unsafe_allow_html=True)

st.write("")
st.divider()

# ── Filter ───────────────────────────────────────────────────────────────
col_f1, col_f2 = st.columns([3, 2])
with col_f1:
    search = st.text_input("🔍 Search by ID, problem statement, or owner", label_visibility="collapsed",
                            placeholder="🔍 Search by ID, problem statement, or owner")
with col_f2:
    status_filter = st.selectbox("Filter by stage", ["All"] + LIFECYCLE_STAGES, label_visibility="collapsed")

filtered = records
if search:
    q = search.lower()
    filtered = [r for r in filtered if
                q in (r.get("id", "") or "").lower() or
                q in (r.get("problem_statement", "") or "").lower() or
                q in (r.get("action_owner", "") or "").lower()]
if status_filter != "All":
    filtered = [r for r in filtered if (r.get("status") or "Submitted") == status_filter]

st.caption(f"Showing {len(filtered)} of {len(records)} submissions")

# ── Table ────────────────────────────────────────────────────────────────
table_rows = []
for r in filtered:
    pid = r.get("id", "")
    latest_decision = decision_by_problem.get(pid, [])
    reviewer = latest_decision[0][3] if latest_decision else "—"
    table_rows.append({
        "ID": pid,
        "Problem Statement": (r.get("problem_statement", "") or "")[:80],
        "Status": r.get("status", "Submitted") or "Submitted",
        "Owner": r.get("action_owner", "") or "—",
        "Workflow Location": r.get("workflow_location", "") or "—",
        "Submitted": r.get("submitted_at", "") or "—",
        "Reviewer": reviewer,
    })

df = pd.DataFrame(table_rows)
st.dataframe(df, width='stretch', hide_index=True)

st.caption("ℹ️ **In Progress** and **Completed** stages will populate once a submission is "
           "activated from Project Execution — that workflow is being built out next.")
