# app.py — Landing page / entry point. Run: streamlit run app.py
# ─────────────────────────────────────────────────────────────────────────
# Idea Submission v2 nav redesign (spec §1 — Branding Updates). This is now
# a clean welcome screen only — it does NOT contain the intake form, which
# has moved to pages/1_Idea_Submission.py. Existing theme/CSS is reused
# unchanged (apply_theme()); nothing here introduces new colors or styles.
# ─────────────────────────────────────────────────────────────────────────

import base64
import streamlit as st

from database.db import init_db, db_remove_duplicate_problems
from ui.theme import apply_theme
from ui.sidebar import render_sidebar

st.set_page_config(
    page_title="AI Governance Platform",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

init_db()
if not st.session_state.get("_dedup_done"):
    db_remove_duplicate_problems()
    st.session_state["_dedup_done"] = True

apply_theme()
render_sidebar("landing")


def _logo_base64():
    try:
        with open("assets/logo.png", "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None


logo_b64 = _logo_base64()

st.write("")
st.write("")

logo_html = (
    f'<img src="data:image/png;base64,{logo_b64}" style="height:64px;margin-bottom:18px;" />'
    if logo_b64 else
    '<div style="font-size:2.2rem;font-weight:800;color:#6C63FF;margin-bottom:10px;">TekFrameWorks</div>'
)

st.markdown(f"""
<div class="card" style="text-align:center;padding:3.2rem 2rem;min-height:0;">
  {logo_html}
  <div style="font-size:2.1rem;font-weight:800;color:#1a1a2e;margin-top:6px;">
    AI Governance Platform
  </div>
  <div style="font-size:1.05rem;color:#666;margin-top:10px;max-width:620px;margin-left:auto;margin-right:auto;">
    End-to-End AI Governance, Assessment, and Approval Platform
  </div>
</div>
""", unsafe_allow_html=True)

st.write("")

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("""
    <div class="card" style="min-height:160px;">
      <div style="font-size:1.6rem;">💡</div>
      <div style="font-weight:700;margin-top:6px;">Submit an Idea</div>
      <div style="font-size:0.85rem;color:#666;margin-top:4px;">
        Describe a business problem, attach supporting documents, and let AI
        help shape it into a governance-ready proposal.
      </div>
    </div>""", unsafe_allow_html=True)
with col2:
    st.markdown("""
    <div class="card" style="min-height:160px;">
      <div style="font-size:1.6rem;">📊</div>
      <div style="font-weight:700;margin-top:6px;">Assess & Prioritize</div>
      <div style="font-size:0.85rem;color:#666;margin-top:4px;">
        Run feasibility and gain-pain analysis grounded in NIST AI RMF and
        ISO 42001 frameworks.
      </div>
    </div>""", unsafe_allow_html=True)
with col3:
    st.markdown("""
    <div class="card" style="min-height:160px;">
      <div style="font-size:1.6rem;">🏛️</div>
      <div style="font-weight:700;margin-top:6px;">Govern & Track</div>
      <div style="font-size:0.85rem;color:#666;margin-top:4px;">
        Route ideas through committee review, then track execution and
        lifecycle status end to end.
      </div>
    </div>""", unsafe_allow_html=True)

st.write("")
st.write("")

col_a, col_b, col_c = st.columns([1, 1, 1])
with col_b:
    if st.button("💡 Start a New Idea Submission", type="primary", width='stretch'):
        st.switch_page("pages/1_Idea_Submission.py")

st.write("")
st.caption("Need help getting started? Open **Instructions / Readme** in the sidebar.")
