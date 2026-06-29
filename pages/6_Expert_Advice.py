# pages/6_Expert_Advice.py
#
# NEW FEATURE — Expert Advice.
#   User Side: submit a Query / Suggestion / Concern / Explanation about a
#              completed Gain-Pain analysis.
#   Expert Side: see the Problem Statement, Gain values, Pain values,
#              Priority Score, and the user's query; the expert can modify
#              the 8 Gain-Pain dimensions and Save, which recomputes the
#              Priority Score and updates the Governance Dashboard and
#              Governance Review (committee) view automatically because
#              they all read from the same canonical `gainpain_analyses`
#              table. Every change is written to the audit trail (old
#              value -> expert value, timestamp, expert name, reason).

import streamlit as st
import pandas as pd
from datetime import datetime

from config.constants import GAIN_DIMENSIONS, PAIN_DIMENSIONS, PRIORITY_BANDS
from database.problem_repository import get_problems
from database.db import (
    db_get_problem, db_load_gainpain, db_get_gainpain,
    db_save_expert_review_request, db_load_expert_review_requests,
    db_mark_expert_review_reviewed, db_apply_expert_overrides, db_load_audit,
)

from ui.theme import apply_theme
from ui.sidebar import render_sidebar

st.set_page_config(page_title="AI Governance Platform", page_icon="🤖",
                    layout="wide", initial_sidebar_state="expanded")

apply_theme()
render_sidebar("m6")

st.title("Expert Advice")
st.caption("Raise a concern about a Gain-Pain analysis, or — as an expert — review and adjust the scoring.")

all_gp = db_load_gainpain()
analysed_problem_ids = sorted({g["problem_id"] for g in all_gp})

if not analysed_problem_ids:
    st.warning("No Gain-Pain analyses found yet. Complete **⚖️ Gain Pain Analysis** first.")
    st.stop()

id_to_label = {pid: (db_get_problem(pid) or {}).get("problem_statement", pid) for pid in analysed_problem_ids}

tab_user, tab_expert = st.tabs(["📝 Submit Feedback", "🧑‍⚖️ Expert Review Panel"])

# ════════════════════════════════════════════════════════════════════════
# USER SIDE
# ════════════════════════════════════════════════════════════════════════
with tab_user:
    st.markdown("### Submit Feedback on a Gain-Pain Analysis")

    prefill_pid = st.session_state.pop("expert_review_problem_id", None)
    options = list(id_to_label.keys())
    default_index = options.index(prefill_pid) if prefill_pid in options else 0

    sel_pid = st.selectbox(
        "Problem", options, index=default_index,
        format_func=lambda pid: f"{id_to_label[pid][:90]}  ({pid})",
        key="user_feedback_pid",
    )

    latest_gp = db_load_gainpain(sel_pid)[0]

    with st.container(border=True):
        st.write("**Problem Statement**")
        st.info(id_to_label[sel_pid])
        c1, c2, c3 = st.columns(3)
        c1.metric("Gain Score", f"{latest_gp['avg_gains']:.2f}")
        c2.metric("Pain Score", f"{latest_gp['avg_pains']:.2f}")
        c3.metric("Priority Score", f"{latest_gp['priority_score_scaled']:.1f}/10")

    query_type = st.radio(
        "What would you like to raise?",
        ["Query", "Suggestion", "Concern", "Explanation"],
        horizontal=True,
    )
    query_text = st.text_area(
        "Details",
        placeholder='e.g. "I believe implementation cost should be lower." or "I disagree with operational risk."',
        height=120,
    )

    if st.button("Submit", type="primary"):
        if not query_text.strip():
            st.warning("Please enter a query, suggestion, concern, or explanation before submitting.")
        else:
            db_save_expert_review_request({
                "problem_id": sel_pid,
                "gainpain_id": latest_gp["id"],
                "query_type": query_type,
                "query_text": query_text.strip(),
            })
            st.success("Submitted. An expert will review this Gain-Pain analysis.")

    st.divider()
    st.markdown("##### Your previously submitted feedback for this problem")
    history = db_load_expert_review_requests(sel_pid)
    if history:
        st.dataframe(
            pd.DataFrame(history)[["submitted_at", "query_type", "query_text", "status"]]
              .rename(columns={"submitted_at": "Submitted", "query_type": "Type",
                                "query_text": "Details", "status": "Status"}),
            width='stretch', hide_index=True,
        )
    else:
        st.caption("No feedback submitted yet for this problem.")

# ════════════════════════════════════════════════════════════════════════
# EXPERT SIDE
# ════════════════════════════════════════════════════════════════════════
with tab_expert:
    st.markdown("### Expert Review Panel")

    exp_pid = st.selectbox(
        "Problem", options,
        format_func=lambda pid: f"{id_to_label[pid][:90]}  ({pid})",
        key="expert_review_pid",
    )

    gp = db_load_gainpain(exp_pid)[0]
    problem = db_get_problem(exp_pid)

    st.write("**Problem Statement**")
    st.info(problem.get("problem_statement", ""))

    m1, m2, m3 = st.columns(3)
    m1.metric("Gain Score", f"{gp['avg_gains']:.2f}")
    m2.metric("Pain Score", f"{gp['avg_pains']:.2f}")
    m3.metric("Priority Score", f"{gp['priority_score_scaled']:.1f}/10  ({gp['priority_band']})")

    pending = [r for r in db_load_expert_review_requests(exp_pid) if r["status"] == "Pending"]
    if pending:
        st.markdown("**User Query**")
        for req in pending:
            st.markdown(f"- *{req['query_type']}* — {req['query_text']}  \n"
                        f"  <span style='font-size:0.75rem;color:#888;'>submitted {req['submitted_at']}</span>",
                        unsafe_allow_html=True)
    else:
        st.caption("No pending user queries for this problem — you can still review and adjust scores below.")

    st.divider()
    st.markdown("##### Adjust Gain-Pain Dimensions")

    col_g, col_p = st.columns(2)
    new_values = {}
    with col_g:
        st.markdown("**📈 Gains**")
        for d in GAIN_DIMENSIONS:
            new_values[d["id"]] = st.slider(
                d["label"], 1.0, 5.0, float(gp.get(d["id"]) or 1.0), 0.5,
                key=f"expert_{exp_pid}_{d['id']}",
            )
    with col_p:
        st.markdown("**📉 Pains**")
        for d in PAIN_DIMENSIONS:
            new_values[d["id"]] = st.slider(
                d["label"], 1.0, 5.0, float(gp.get(d["id"]) or 1.0), 0.5,
                key=f"expert_{exp_pid}_{d['id']}",
            )

    expert_name = st.text_input("Expert Name", key=f"expert_name_{exp_pid}")
    reason = st.text_area("Reason for adjustment", height=90, key=f"expert_reason_{exp_pid}")

    if st.button("💾 Save", type="primary"):
        if not expert_name.strip():
            st.warning("Please enter your name before saving — it is recorded in the audit trail.")
        elif not reason.strip():
            st.warning("Please provide a reason for the adjustment — it is recorded in the audit trail.")
        else:
            updated = db_apply_expert_overrides(gp["id"], new_values, expert_name.strip(), reason.strip())
            if updated:
                for req in pending:
                    db_mark_expert_review_reviewed(req["id"])
                st.success(
                    f"Saved. Priority Score recomputed to {updated['priority_score_scaled']:.1f}/10 "
                    f"({updated['priority_band']}). The Governance Dashboard and Governance Review "
                    f"pages will reflect this immediately."
                )
                st.rerun()

    st.divider()
    st.markdown("##### Audit Trail")
    audit_rows = [a for a in db_load_audit(exp_pid) if a["action_type"] == "expert_gainpain_override"]
    if audit_rows:
        st.dataframe(
            pd.DataFrame(audit_rows)[["timestamp", "field_name", "old_value", "new_value", "user_name", "reason"]]
              .rename(columns={"timestamp": "Timestamp", "field_name": "Field", "old_value": "Old Value",
                                "new_value": "Expert Value", "user_name": "Expert Name", "reason": "Reason"}),
            width='stretch', hide_index=True,
        )
    else:
        st.caption("No expert adjustments recorded yet for this problem.")
