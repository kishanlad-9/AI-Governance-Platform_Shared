# pages/1_Idea_Submission.py
# ─────────────────────────────────────────────────────────────────────────
# Idea Submission v2 — document-aware intake flow (replaces the purely
# conversational Module 1 experience for this project copy). Implements,
# in order:
#
#   Step 1  Text input + file upload (PDF/DOCX/PPTX/XLSX/CSV/TXT, multiple)
#   Step 2  Document extraction -> unified context -> auto-captured
#           Problem Statement + Business Objective (editable)
#   Step 3  Business Value / Workflow Location / Decision Support questions
#           (never invented by the LLM — always asked of the user directly)
#   Step 4  AI-proposed solution + Yes/No validation loop with clarification
#           questions on "No", looping until accepted
#   Step 5  Contradiction check between user claims and uploaded documents,
#           with file + page/slide/sheet level evidence
#   Step 6  Review & Save (reuses the existing ISO sensitivity fields so
#           Module 2/3/4 downstream logic keeps working unchanged)
#
# Everything below Step 6 (Feasibility, Gain-Pain, Governance, Dashboard)
# is untouched, per the merge spec.
# ─────────────────────────────────────────────────────────────────────────

import streamlit as st

from ui.theme import apply_theme
from ui.sidebar import render_sidebar

from document_intel.extractors import SUPPORTED_EXTENSIONS
from document_intel.context_builder import extract_all, build_unified_context, documents_summary

from llm.idea_intake import (
    autocapture_fields,
    propose_solution,
    generate_clarification_questions,
    detect_contradictions,
)
from llm.missing_fields import get_missing_fields
from llm.question_generator import QUESTION_MAP

from database.problem_repository import new_draft_id, save_problem_v2
from database.db import (
    db_save_uploaded_documents, db_save_contradiction_flags,
    db_save_solution_proposal,
)

st.set_page_config(page_title="Idea Submission — AI Governance Platform",
                    page_icon="💡", layout="wide", initial_sidebar_state="expanded")

apply_theme()
render_sidebar("idea_submission")

st.title("💡 Idea Submission")
st.caption("Describe your business idea, optionally attach supporting documents, "
           "and let AI help you shape it into a governance-ready proposal.")

# ── Session state scaffolding ───────────────────────────────────────────────
ss = st.session_state
ss.setdefault("idea_step", 1)
ss.setdefault("idea_draft_id", None)
ss.setdefault("idea_documents", [])          # list[ExtractedDocument]
ss.setdefault("idea_unified_context", "")
ss.setdefault("idea_autocapture", {})
ss.setdefault("idea_fields", {})             # accumulates all collected fields
ss.setdefault("idea_proposal_round", 0)
ss.setdefault("idea_current_proposal", None)
ss.setdefault("idea_clarification_qa", [])
ss.setdefault("idea_contradictions", None)
ss.setdefault("idea_documents_saved", False)
ss.setdefault("idea_pending_questions", None)
ss.setdefault("idea_saved_record_id", None)

STEP_LABELS = ["Describe", "Auto-Capture", "Key Details", "Proposed Solution",
               "Consistency Check", "Review & Save"]


def stepper():
    current = ss.idea_step
    current_num = 4 if current == "4_clarify" else current
    cols = st.columns(len(STEP_LABELS))
    for i, (col, label) in enumerate(zip(cols, STEP_LABELS), start=1):
        with col:
            if i < current_num:
                st.markdown(f"<div style='text-align:center;color:#1D9E75;font-weight:700;font-size:0.8rem;'>✅ {label}</div>", unsafe_allow_html=True)
            elif i == current_num:
                st.markdown(f"<div style='text-align:center;color:#6C63FF;font-weight:800;font-size:0.8rem;'>🟣 {label}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align:center;color:#aaa;font-size:0.8rem;'>{label}</div>", unsafe_allow_html=True)
    st.markdown("<hr style='margin-top:0.4rem;'>", unsafe_allow_html=True)


def goto(step: int):
    ss.idea_step = step
    st.rerun()


def restart():
    for k in list(ss.keys()):
        if k.startswith("idea_"):
            del ss[k]
    st.rerun()


stepper()

# ═══════════════════════════════════════════════════════════════════════════
# STEP 1 — Describe the idea (text + optional file uploads)
# ═══════════════════════════════════════════════════════════════════════════
if ss.idea_step == 1:
    with st.container(border=True):
        st.subheader("Step 1 — Describe your idea")
        st.caption("Provide a business idea, problem statement, or use case description. "
                    "You can also attach supporting documents instead of (or in addition to) typing.")

        user_text = st.text_area(
            "Business idea / problem statement / use case description",
            value=ss.idea_fields.get("_user_text", ""),
            height=180,
            placeholder="Describe the business idea, problem, or use case...",
        )

        st.markdown(f"**Optional: attach supporting documents** "
                    f"({', '.join(e.upper() for e in SUPPORTED_EXTENSIONS)})")
        st.caption("Business requirement docs, meeting notes, transcripts, business cases — "
                    "multiple files supported.")
        uploaded_files = st.file_uploader(
            "Upload files", type=SUPPORTED_EXTENSIONS, accept_multiple_files=True,
            label_visibility="collapsed"
        )

        col_a, col_b = st.columns([1, 5])
        with col_a:
            proceed = st.button("Analyze →", type="primary", width='stretch')

        if proceed:
            if not user_text.strip() and not uploaded_files:
                st.warning("Please provide a description or upload at least one document.")
                st.stop()

            ss.idea_fields["_user_text"] = user_text
            ss.idea_draft_id = ss.idea_draft_id or new_draft_id()

            if uploaded_files:
                with st.spinner("Extracting content from uploaded documents…"):
                    ss.idea_documents = extract_all(uploaded_files)
            else:
                ss.idea_documents = []

            ss.idea_unified_context = build_unified_context(user_text, ss.idea_documents)

            with st.spinner("AI is identifying the problem statement and business objective…"):
                ss.idea_autocapture = autocapture_fields(ss.idea_unified_context)

            ss.idea_fields["problem_statement"] = ss.idea_autocapture.get("problem_statement", "")
            ss.idea_fields["business_objective"] = ss.idea_autocapture.get("business_objective", "")

            goto(2)

# ═══════════════════════════════════════════════════════════════════════════
# STEP 2 — Auto-captured fields (editable)
# ═══════════════════════════════════════════════════════════════════════════
elif ss.idea_step == 2:
    with st.container(border=True):
        st.subheader("Step 2 — Auto-captured fields")

        if ss.idea_documents:
            st.markdown("**Document processing results**")
            st.code(documents_summary(ss.idea_documents), language=None)

        confidence = ss.idea_autocapture.get("confidence", "")
        grounded_in = ss.idea_autocapture.get("grounded_in", "")
        if confidence:
            badge_color = {"high": "#1D9E75", "medium": "#C07A10", "low": "#C0392B"}.get(confidence, "#888")
            st.markdown(
                f"<span style='background:{badge_color}1A;color:{badge_color};padding:2px 10px;"
                f"border-radius:20px;font-size:0.75rem;font-weight:700;'>Confidence: {confidence.title()}</span>",
                unsafe_allow_html=True)
            if grounded_in:
                st.caption(f"Grounded in: {grounded_in}")

        st.write("")
        st.markdown("**Detected Problem Statement** — edit if needed")
        ss.idea_fields["problem_statement"] = st.text_area(
            "Detected Problem Statement", value=ss.idea_fields.get("problem_statement", ""),
            height=120, label_visibility="collapsed")

        st.markdown("**Detected Business Objective** — edit if needed")
        ss.idea_fields["business_objective"] = st.text_area(
            "Detected Business Objective", value=ss.idea_fields.get("business_objective", ""),
            height=100, label_visibility="collapsed")

        if not ss.idea_fields.get("problem_statement", "").strip():
            st.info("No problem statement could be auto-detected from your input — please write one above before continuing.")

        col_back, col_next = st.columns([1, 1])
        with col_back:
            if st.button("← Back", width='stretch'):
                goto(1)
        with col_next:
            if st.button("Continue →", type="primary", width='stretch'):
                if not ss.idea_fields.get("problem_statement", "").strip():
                    st.warning("Problem Statement is required.")
                    st.stop()
                goto(3)

# ═══════════════════════════════════════════════════════════════════════════
# STEP 3 — Business Value / Workflow Location / Decision Support
# (asked directly of the user — never invented by the LLM)
# ═══════════════════════════════════════════════════════════════════════════
elif ss.idea_step == 3:
    with st.container(border=True):
        st.subheader("Step 3 — Key business details")
        st.caption("These are always confirmed with you directly — AI will not invent business value.")

        st.markdown(f"**{QUESTION_MAP.get('business_value', 'What measurable business value is expected?')}**")
        st.caption("Examples: annual cost savings, revenue increase, productivity improvement, "
                    "time saved, customer satisfaction improvement. Be specific and quantified — avoid vague entries.")
        business_value = st.text_area(
            "Business value", value=ss.idea_fields.get("business_value", ""),
            height=90, label_visibility="collapsed",
            placeholder="e.g. Reduce average claims processing time by 30%, saving ~$450K/year in labor costs")

        st.markdown(f"**{QUESTION_MAP.get('workflow_location', 'Where in the workflow does this problem occur?')}**")
        st.caption("Examples: Claims Processing, Customer Support, Manufacturing, Procurement, Supply Chain, HR Operations.")
        workflow_location = st.text_input(
            "Workflow location", value=ss.idea_fields.get("workflow_location", ""),
            label_visibility="collapsed", placeholder="e.g. Claims Processing")

        st.markdown(f"**{QUESTION_MAP.get('decision_support', 'What decisions should the AI assist with?')}**")
        st.caption("Examples: approval decisions, prioritization, routing, classification, recommendations.")
        decision_support = st.text_area(
            "Decision support", value=ss.idea_fields.get("decision_support", ""),
            height=90, label_visibility="collapsed",
            placeholder="e.g. Recommend approve/deny/escalate on each incoming claim")

        col_back, col_next = st.columns([1, 1])
        with col_back:
            if st.button("← Back", width='stretch', key="b3"):
                goto(2)
        with col_next:
            if st.button("Continue →", type="primary", width='stretch', key="n3"):
                empty = []
                if not business_value.strip():
                    empty.append("business value")
                if not workflow_location.strip():
                    empty.append("workflow location")
                if not decision_support.strip():
                    empty.append("decision support")
                if empty:
                    st.warning(f"Please provide: {', '.join(empty)}.")
                    st.stop()

                ss.idea_fields["business_value"] = business_value.strip()
                ss.idea_fields["workflow_location"] = workflow_location.strip()
                ss.idea_fields["decision_support"] = decision_support.strip()
                ss.idea_current_proposal = None
                goto(4)

# ═══════════════════════════════════════════════════════════════════════════
# STEP 4 — AI Proposed Solution + validation loop
# ═══════════════════════════════════════════════════════════════════════════
elif ss.idea_step == 4:
    with st.container(border=True):
        st.subheader("Step 4 — AI-proposed solution")

        if ss.idea_current_proposal is None:
            with st.spinner("AI is proposing a solution…"):
                proposal = propose_solution(ss.idea_fields, ss.idea_clarification_qa)
            ss.idea_proposal_round += 1
            ss.idea_current_proposal = proposal
            db_save_solution_proposal(ss.idea_draft_id, ss.idea_proposal_round, proposal,
                                       accepted=False, clarification_qa=ss.idea_clarification_qa)

        proposal = ss.idea_current_proposal

        st.markdown(f"""
        <div style="background:#F7F7FF;border:1.5px solid #C5C1FF;border-radius:14px;padding:1.2rem 1.6rem;">
          <div style="font-size:0.7rem;color:#6C63FF;font-weight:700;letter-spacing:0.08em;">
            PROPOSED SOLUTION — ROUND {ss.idea_proposal_round}
          </div>
          <div style="font-size:1.3rem;font-weight:800;color:#1a1a2e;margin-top:4px;">
            {proposal.get('solution_name', '—')}
          </div>
          <div style="font-size:0.78rem;color:#6C63FF;font-weight:700;margin-top:2px;">
            {proposal.get('solution_type', '')}
          </div>
          <div style="font-size:0.85rem;color:#444;margin-top:10px;line-height:1.6;">
            {proposal.get('solution_description', '')}
          </div>
        </div>""", unsafe_allow_html=True)

        benefits = proposal.get("expected_benefits", [])
        if benefits:
            st.markdown("**Expected Benefits**")
            for b in benefits:
                st.markdown(f"- {b}")

        assumptions = proposal.get("key_assumptions", [])
        if assumptions:
            with st.expander("Key assumptions"):
                for a in assumptions:
                    st.markdown(f"- {a}")

        if ss.idea_clarification_qa:
            with st.expander(f"Clarification history (round {ss.idea_proposal_round - 1} feedback)"):
                for qa in ss.idea_clarification_qa:
                    st.markdown(f"**Q:** {qa['question']}\n\n**A:** {qa['answer']}")

        st.write("")
        st.markdown("**Are you satisfied with the proposed solution?**")
        col_yes, col_no, col_back = st.columns([1, 1, 1])
        with col_yes:
            if st.button("✅ Yes, proceed", type="primary", width='stretch'):
                ss.idea_fields["proposed_solution"] = (
                    f"{proposal.get('solution_name', '')} ({proposal.get('solution_type', '')}): "
                    f"{proposal.get('solution_description', '')}"
                )
                db_save_solution_proposal(ss.idea_draft_id, ss.idea_proposal_round, proposal,
                                           accepted=True, clarification_qa=ss.idea_clarification_qa)
                goto(5)
        with col_no:
            if st.button("❌ No, refine it", width='stretch'):
                ss.idea_step = "4_clarify"
                st.rerun()
        with col_back:
            if st.button("← Back to details", width='stretch'):
                ss.idea_current_proposal = None
                goto(3)

elif ss.idea_step == "4_clarify":
    with st.container(border=True):
        st.subheader("Help us improve the proposal")
        st.caption("Answer a few targeted questions so the AI can propose something more specific.")

        if ss.idea_pending_questions is None:
            with st.spinner("Generating clarification questions…"):
                q_result = generate_clarification_questions(ss.idea_fields, ss.idea_current_proposal)
            ss.idea_pending_questions = q_result.get("questions", [])

        answers = {}
        for q in ss.idea_pending_questions:
            answers[q["id"]] = st.text_area(q["question"], key=f"clarify_{q['id']}", height=70)

        col_submit, col_skip = st.columns([1, 1])
        with col_submit:
            if st.button("Submit answers →", type="primary", width='stretch'):
                unanswered = [q["question"] for q in ss.idea_pending_questions if not answers.get(q["id"], "").strip()]
                if unanswered:
                    st.warning("Please answer all questions, or use 'Skip & retry' to let AI try again without them.")
                    st.stop()
                for q in ss.idea_pending_questions:
                    ss.idea_clarification_qa.append({"question": q["question"], "answer": answers[q["id"]]})
                ss.idea_current_proposal = None
                ss.idea_pending_questions = None
                ss.idea_step = 4
                st.rerun()
        with col_skip:
            if st.button("Skip & retry", width='stretch'):
                ss.idea_current_proposal = None
                ss.idea_pending_questions = None
                ss.idea_step = 4
                st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# STEP 5 — Contradiction Detection
# ═══════════════════════════════════════════════════════════════════════════
elif ss.idea_step == 5:
    with st.container(border=True):
        st.subheader("Step 5 — Consistency check")
        st.caption("Comparing what you entered against your uploaded documents for any material contradictions.")

        if ss.idea_contradictions is None:
            doc_only_context = build_unified_context("", ss.idea_documents)
            if not doc_only_context.strip():
                ss.idea_contradictions = {"contradictions": [], "has_contradictions": False}
            else:
                with st.spinner("Checking for contradictions between your input and uploaded documents…"):
                    claims = {
                        "problem_statement": ss.idea_fields.get("problem_statement", ""),
                        "business_objective": ss.idea_fields.get("business_objective", ""),
                        "business_value": ss.idea_fields.get("business_value", ""),
                        "workflow_location": ss.idea_fields.get("workflow_location", ""),
                        "decision_support": ss.idea_fields.get("decision_support", ""),
                    }
                    ss.idea_contradictions = detect_contradictions(claims, doc_only_context)

        result = ss.idea_contradictions
        contradictions = result.get("contradictions", [])

        # ── Field map: contradiction field label → session state key ─────────
        FIELD_TO_KEY = {
            "problem statement":  "problem_statement",
            "business objective": "business_objective",
            "business value":     "business_value",
            "workflow location":  "workflow_location",
            "decision support":   "decision_support",
        }

        if not contradictions:
            st.success("✅ No material contradictions found between your input and uploaded documents.")
        else:
            st.warning(
                f"⚠️ {len(contradictions)} genuine conflict(s) found where your inputs differ from "
                f"the uploaded documents. Review each one — you can correct your entry if the "
                f"document is the authoritative source."
            )

            for i, c in enumerate(contradictions, start=1):
                conf       = c.get("confidence_pct", 0)
                conf_color = "#C0392B" if conf >= 80 else "#C07A10"
                corr_key   = f"idea_correction_applied_{i}"
                ss.setdefault(corr_key, False)

                # ── Contradiction card ────────────────────────────────────────
                st.markdown(f"""
                <div style="background:#FFF8F0;border:1.5px solid {conf_color}55;
                            border-radius:12px;padding:1rem 1.3rem;margin-bottom:0.3rem;">
                  <div style="font-size:0.7rem;color:{conf_color};font-weight:700;
                              letter-spacing:0.06em;">
                    INCONSISTENCY #{i} — {conf}% CONFIDENCE
                  </div>
                  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px;">
                    <div style="background:#FFF0F0;border-radius:8px;padding:0.6rem 0.8rem;">
                      <div style="font-size:0.68rem;color:{conf_color};font-weight:700;
                                  text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px;">
                        What you entered
                      </div>
                      <div style="font-size:0.83rem;color:#1a1a2e;">
                        "{c.get('user_input','')}"
                      </div>
                    </div>
                    <div style="background:#FEF9EE;border-radius:8px;padding:0.6rem 0.8rem;">
                      <div style="font-size:0.68rem;color:{conf_color};font-weight:700;
                                  text-transform:uppercase;letter-spacing:0.05em;margin-bottom:4px;">
                        Document says — {c.get('source_file','')} ({c.get('source_location','')})
                      </div>
                      <div style="font-size:0.83rem;color:#1a1a2e;">
                        "{c.get('extracted_statement','')}"
                      </div>
                    </div>
                  </div>
                  <div style="margin-top:8px;font-size:0.78rem;color:#666;font-style:italic;">
                    {c.get('explanation','')}
                  </div>
                </div>""", unsafe_allow_html=True)

                # ── Correction applied badge ──────────────────────────────────
                if ss[corr_key]:
                    st.markdown(
                        "<div style='background:#D1F5EA;border-radius:6px;padding:4px 12px;"
                        "font-size:0.78rem;color:#1D9E75;font-weight:700;margin-bottom:0.5rem;'>"
                        "✅ Correction applied</div>",
                        unsafe_allow_html=True
                    )

                # ── Correct this expander ─────────────────────────────────────
                with st.expander(f"✏️ Correct inconsistency #{i}", expanded=False):
                    st.caption(
                        "Pick which field this correction applies to, enter the corrected value, "
                        "and click Apply. The corrected value will be used when you save."
                    )

                    field_options = [
                        "Problem Statement",
                        "Business Objective",
                        "Business Value",
                        "Workflow Location",
                        "Decision Support",
                    ]

                    # Pre-select the field closest to what the LLM flagged
                    user_input_lower = c.get("user_input", "").lower()
                    default_idx = 0
                    for fi, fo in enumerate(field_options):
                        if fo.lower() in user_input_lower or any(
                            w in user_input_lower for w in fo.lower().split()
                        ):
                            default_idx = fi
                            break

                    col_field, col_val = st.columns([1, 2])
                    with col_field:
                        selected_field = st.selectbox(
                            "Field to correct",
                            field_options,
                            index=default_idx,
                            key=f"contra_field_sel_{i}",
                        )
                    with col_val:
                        corrected_value = st.text_area(
                            "Corrected value",
                            value=c.get("extracted_statement", ""),
                            height=80,
                            key=f"contra_val_{i}",
                            help=f"Document source: {c.get('source_file','')} — {c.get('source_location','')}",
                        )

                    reason = st.text_input(
                        "Reason (optional)",
                        placeholder="e.g. Document figure is from the approved business case",
                        key=f"contra_reason_{i}",
                    )

                    if st.button(
                        f"Apply correction to '{selected_field}'",
                        key=f"contra_apply_{i}",
                        type="primary",
                    ):
                        session_key = FIELD_TO_KEY.get(selected_field.lower())
                        if session_key and corrected_value.strip():
                            ss.idea_fields[session_key] = corrected_value.strip()
                            ss[corr_key] = True
                            # Stamp the correction onto the contradiction record so
                            # it's saved to the DB with the corrected value
                            c["corrected_to"] = corrected_value.strip()
                            c["correction_field"] = selected_field
                            c["correction_reason"] = reason.strip()
                            st.success(
                                f"✅ **{selected_field}** updated to the corrected value. "
                                f"It will be used when you save in Step 6."
                            )
                            st.rerun()
                        else:
                            st.warning("Please enter a corrected value before applying.")

                st.write("")  # breathing room between cards

        st.write("")
        col_back, col_next = st.columns([1, 1])
        with col_back:
            if st.button("← Back", width='stretch'):
                ss.idea_contradictions = None
                # clear any correction flags so re-running the check starts fresh
                for k in list(ss.keys()):
                    if k.startswith("idea_correction_applied_"):
                        del ss[k]
                goto(4)
        with col_next:
            label = "Continue →" if not contradictions else "Acknowledge & continue →"
            if st.button(label, type="primary", width='stretch'):
                goto(6)
# ═══════════════════════════════════════════════════════════════════════════
# STEP 6 — Review & Save
# ═══════════════════════════════════════════════════════════════════════════
elif ss.idea_step == 6:
    with st.container(border=True):
        st.subheader("Step 6 — Review & Save")

        sensitivity_options = ["Public", "Internal", "Confidential", "Personal Data (PII)"]

        review_left, review_right = st.columns(2)
        with review_left:
            ss.idea_fields["problem_statement"] = st.text_area(
                "Problem Statement", value=ss.idea_fields.get("problem_statement", ""), height=110)
            ss.idea_fields["business_objective"] = st.text_area(
                "Business Objective", value=ss.idea_fields.get("business_objective", ""), height=110)
            ss.idea_fields["proposed_solution"] = st.text_area(
                "Proposed Solution", value=ss.idea_fields.get("proposed_solution", ""), height=110)
            ss.idea_fields["business_value"] = st.text_area(
                "Business Value", value=ss.idea_fields.get("business_value", ""), height=90)

        with review_right:
            ss.idea_fields["workflow_location"] = st.text_input(
                "Workflow Location", value=ss.idea_fields.get("workflow_location", ""))
            ss.idea_fields["decision_support"] = st.text_area(
                "Decision Support", value=ss.idea_fields.get("decision_support", ""), height=90)

        if ss.idea_documents:
            with st.expander(f"📎 {len(ss.idea_documents)} document(s) attached"):
                st.code(documents_summary(ss.idea_documents), language=None)

        if ss.idea_contradictions and ss.idea_contradictions.get("contradictions"):
            st.caption(f"⚠️ {len(ss.idea_contradictions['contradictions'])} contradiction(s) were flagged in Step 5 "
                       f"and will be saved alongside this submission for governance review.")

        st.write("")
        col_back, col_save = st.columns([1, 1])
        with col_back:
            if st.button("← Back", width='stretch'):
                goto(5)
        with col_save:
            if st.button("💾 Save Idea", type="primary", width='stretch'):
                missing = get_missing_fields({
                    "problem_statement": ss.idea_fields.get("problem_statement", ""),
                    "business_objective": ss.idea_fields.get("business_objective", ""),
                    "proposed_solution": ss.idea_fields.get("proposed_solution", ""),
                    "business_value": ss.idea_fields.get("business_value", ""),
                    "workflow_location": ss.idea_fields.get("workflow_location", ""),
                    "decision_support": ss.idea_fields.get("decision_support", ""),
                })
                if missing:
                    st.error(f"Cannot save. Missing: {', '.join(missing)}")
                    st.stop()

                record_id = save_problem_v2(ss.idea_fields, record_id=ss.idea_draft_id)

                if ss.idea_documents and not ss.idea_documents_saved:
                    db_save_uploaded_documents(record_id, ss.idea_documents)
                    ss.idea_documents_saved = True

                if ss.idea_contradictions and ss.idea_contradictions.get("contradictions"):
                    db_save_contradiction_flags(record_id, ss.idea_contradictions["contradictions"])

                ss.idea_saved_record_id = record_id
                st.rerun()

    if ss.get("idea_saved_record_id"):
        st.success(f"✅ Idea saved as **{ss.idea_saved_record_id}**. You can track it in Feasibility Assessment, "
                   f"Gain-Pain Analysis, or Governance Review.")
        if st.button("Submit another idea"):
            restart()
