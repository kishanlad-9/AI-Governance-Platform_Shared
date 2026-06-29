# AI Governance Platform — Unified (v2: Document-Aware Idea Submission)

> **This is a separate copy** of the unified platform with a redesigned
> Idea Submission flow. See "What's new in v2" below for the full list of
> changes. Everything else (Feasibility Assessment, Gain-Pain Analysis,
> Governance Review, Analytics Dashboard, Expert Advice, ISO/NIST mappings,
> scoring formulas, CSS theme) is unchanged from the original project.

## What's new in v2

- **Landing page** (`app.py`) — now a clean welcome screen (TekFrameWorks
  branding placeholder, platform description, quick links) instead of the
  intake form. The intake form moved to `pages/1_Idea_Submission.py`.
- **New sidebar navigation** (`ui/sidebar.py`) — Instructions / Readme,
  an expandable **Problem Selection** group (Idea Submission, Feasibility
  Assessment, Governance Review, Dashboard), plus new **Project Execution**
  and **Tracking** pages. Gain-Pain Analysis and Expert Advice are still
  reachable under a "More" expander.
- **Document-aware Idea Submission** (`pages/1_Idea_Submission.py`) — a
  6-step flow: describe (text + optional file upload) → AI auto-captures
  Problem Statement & Business Objective → you confirm Business Value /
  Workflow Location / Decision Support directly (never invented by AI) →
  AI proposes a solution with a Yes/No validation loop (clarification
  questions on "No", repeats until accepted) → contradiction check against
  uploaded documents (with file + page/slide/sheet evidence) → review & save.
- **Document Intelligence layer** (`document_intel/`) — extracts text and
  tables from PDF (pdfplumber, with PyMuPDF fallback), DOCX (python-docx),
  PPTX (python-pptx, incl. speaker notes), XLSX (openpyxl), CSV, and TXT —
  every extracted unit carries a page/slide/sheet locator for traceability.
- **Contradiction detection** (`llm/idea_intake.py`) — compares user-entered
  claims against uploaded document content and flags material conflicts
  with confidence score + exact source citation.
- **New database tables** (`database/db.py`): `uploaded_documents`,
  `contradiction_flags`, `solution_proposals` — additive only, the original
  `problem_statements` schema and all downstream tables are untouched.
- **New placeholder pages**: `pages/7_Project_Execution.py` and
  `pages/8_Tracking.py` (lifecycle status across all submissions, using
  existing database records).

---


business logic / AI workflow / ISO 42001 + NIST AI RMF implementation
preserved, plus the new Expert Review workflow and horizontal dashboard
graphs. Run with:

```
pip install -r requirements.txt
streamlit run app.py
```

A pre-seeded `ai_governance.db` ships with this app — see "Data migration"
below.

## How each module was assembled

**Module 1 — Problem Definition** (`app.py`) is Friend's app.py unchanged:
same free-text → AI extraction → missing-field follow-up → review & save
flow, same fields. Only the repeated CSS/sidebar block was pulled into
`ui/theme.py` / `ui/sidebar.py` so it's identical on every page instead of
copy-pasted six times.

**Module 2 — Feasibility Assessment** (`pages/2_Feasibility_Assessment.py`):
Friend's dropdown/cards for picking a problem, then My Project's AI
feasibility logic (`call_m2_assessment`, same prompt, same 6 dimensions,
same hard-gate rules) runs automatically — no extra button — and the page
scrolls through Problem Selection → Assessment Running → Dimension Scores
→ Reasoning → Verdict → Recommendations, all on one page as requested.

**Module 3 — Gain-Pain Analysis** (`pages/3_Gain_Pain_Analysis.py`):
Friend's dropdown/cards, then a new "Ask Clarifying Questions" vs "Run
Directly" choice, then My Project's gain-pain AI logic and formulas
unchanged. A new "Satisfied with Analysis? Yes / Request Expert Review"
prompt appears after results; the latter hands off to the new Expert
Advice page.

**Module 4 — Governance Review** (`pages/4_Governance_Review.py`): Friend's
page, byte-for-byte the same UI and flow. It still imports
`get_problems`/`get_problem_by_id`/`get_feasibility_by_problem`/
`get_gain_pain_by_problem`/`save_decision`/`get_decisions` exactly as
written — those names now live in `database/*_repository.py` adapters
that translate the canonical (My Project) schema into the exact positional
tuples this page was written against, so the page itself needed zero edits.

**Module 5 — Governance Dashboard** (`pages/5_Analytics_Dashboard.py`): My
Project's dashboard.py in full (Overview / ISO 42001 Org Governance / NIST
Technical Monitoring / Graphs tabs, all scoring and compliance logic
unchanged), re-skinned with Friend's theme. The two requested graphs are
now horizontal bar charts: Priority distribution (Y: High/Medium/Low, X:
number of problem statements) and Committee Decision Summary (Y: committee
status, X: number of use cases), both full-width and responsive.

**Expert Advice** (`pages/6_Expert_Advice.py`, new): a "Submit Feedback"
tab for raising a Query/Suggestion/Concern/Explanation about a Gain-Pain
analysis, and an "Expert Review Panel" tab where an expert sees the
Problem Statement, Gain/Pain/Priority values and the user's query, can
adjust the 8 Gain-Pain dimensions, and Save — which recomputes the
Priority Score using the same formula as Module 3
(`priority_score = avg_gains*0.6 - avg_pains*0.4`, scaled to 0–10) and
writes one audit-trail row per changed field (old value → expert value,
timestamp, expert name, reason). Because the Dashboard and Governance
Review pages read the same `gainpain_analyses` table, they reflect the
updated score immediately — no extra wiring needed.

## Database

One canonical SQLite database (`ai_governance.db`), schema inherited from
My Project and extended with: `governance_decisions` (drives Module 4),
`expert_review_requests` and the expert-override path in
`gainpain_analyses` (drives Expert Advice), and a generic `audit_log` table
used for committee decisions, expert overrides, and the migration itself.
`database/problem_repository.py`, `feasibility_repository.py`,
`gain_pain_repository.py`, and `governance_repository.py` are thin
adapters so Friend's Module 4 page can keep using its original function
names and positional-tuple access pattern against this schema.

One mapping note worth flagging: Friend's Module 4 page shows a
"Technology" metric (`feasibility[5]`) that doesn't exist as a separate
field in My Project's model — My Project's "Data & Technology Readiness"
dimension already covers both, so that one dimension's score is shown in
both columns. See the comment in `feasibility_repository.py`.

## Data migration ("Do NOT lose existing records")

Both projects had real data in their respective databases. The shipped
`ai_governance.db` was seeded once (`migration/seed_migration_one_time.py`,
kept for transparency — it is not part of the running app) by:
- starting from My Project's `ai_governance.db` (schema already canonical)
- merging in Friend's 23 `problems` and 9 `governance_decisions` (clean,
  lossless column renames), prefixed `FS-` to avoid id collisions
- archiving Friend's `feasibility_assessments` (19 rows) and
  `gain_pain_analysis` (12 rows) into `legacy_friend_feasibility_assessments`
  / `legacy_friend_gain_pain_analysis`, byte-for-byte, rather than force-fitting
  them into My Project's scoring columns — Friend's rubric used different
  fields (e.g. `revenue_increase`, `fairness_risk`) with no honest 1:1
  mapping onto My Project's 6/8-dimension model, and fabricating that
  mapping would have created assessment data that no AI logic actually
  produced. They're preserved and queryable, just not surfaced as if they
  were live scores.
- running the duplicate-problem cleanup (`db_remove_duplicate_problems`,
  also run automatically on first app load) — it removed 3 rows that were
  textual duplicates between the two seed sets.

## AI Settings (no UI — configured entirely via secrets)

The sidebar has no Provider/Model/API Key fields. `utils/helpers.get_api_key()`
checks, in order: `st.secrets` → environment variables →
`config/app_config.json`. Whichever of those has a key (`GEMINI_API_KEY`,
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GROQ_API_KEY`), the provider and
best available model are auto-detected from the key's format
(`utils/helpers.resolve_model()`) — nothing to pick manually, and every
user of the deployment uses the same key automatically.

For Streamlit Cloud: **Settings → Secrets** →
```
GEMINI_API_KEY = "your-key-here"
```
— that's the only step needed; the key never touches the repo. The same
applies locally via `.streamlit/secrets.toml` (already gitignored). Only
use `config/app_config.json` instead if the repo is private or exposing
the key in source is acceptable — anything in that file is visible to
anyone who can read the repo.

## Assumptions worth knowing about

- Module 2's "Question generation" was interpreted as the dimension list
  shown to the user during assessment (what the AI is evaluating), not a
  manual per-question Likert flow — the only Module 2 logic actually wired
  into My Project's running app was the fully-automated single AI call;
  an older, unused manual-question variant existed in the code but was
  never reachable from the app, so it wasn't carried forward.
- Module 5's brief ("Executive Summary, Risk Register, Compliance
  Checklist, Accountability Map") was treated as a description of the
  dashboard's overall scope rather than four literally-named sections to
  build from scratch — the existing Overview / ISO Governance / NIST
  Monitoring / Graphs tabs cover that scope and were carried over whole.
- "Satisfied? Yes" on the Gain-Pain page is a lightweight acknowledgement
  (no extra status change) since the spec didn't ask for one; "Request
  Expert Review" is the action with real downstream effects.
