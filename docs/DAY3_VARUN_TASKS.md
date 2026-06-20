# DEFERRAL LEDGER — Day 3 Tasks: **VARUN**
### Role: Dashboard wiring + governance/audit persistence + API completion + deploy
*Build team = Varun + Chaitanya (Manush unavailable; full scope via overtime). Day 3 = "make it usable & responsible" — turn the Day-2 compute core into a deployed, integrated, demoable app. Pair: Chaitanya (RAG brief + analytics panels).*

---

## Day-3 goal (shared, you + Chaitanya)
> **A deployed Streamlit app: pick a tract + defer years → see the M posterior (fan/histogram + CI), the abstention banner, the Sobol tornado + "commission this study" callout, an edge table with citations + a contested-edge consent toggle that re-fans the distribution, a generated decision brief, and a persisted audit record — live on a public URL.**

**Your slice of the milestone:** the app runs end-to-end on a public URL; the contested-edge **consent gate** works and is **logged**; `/sensitivity` and `/audit` are real (no stubs).

---

## STEP 0 — Joint design lock (~40 min)
1. **Demo architecture:** for robustness, the Streamlit app **imports the compute modules directly** (`run_monte_carlo`, `compare`, `sobol_indices`, `commission_study_recommendation`, `apply_abstention`) with `@st.cache_data`; keep the **FastAPI as the documented "API layer"** but don't make the live demo depend on a second running service.
2. **Audit persistence format** (SQLite via `sqlite3`/SQLModel, or append-only JSONL) — pick the simplest that survives a redeploy.
3. **Dashboard layout/sections** so you two don't collide: agree which panels each owns (you: controls, contested-consent gate, audit panel, map; Chaitanya: M fan chart, Sobol tornado, edge table, brief, compare view).
4. **The "golden scenario"** for the demo: a specific tract + defer-years that yields a compelling `M > 1` with **E1 dominating** the tornado (test it now, hardcode it as the default).

---

## YOUR TASKS (ordered)

### V1 — Wire the real `/sensitivity` endpoint (`api.py`) *(~45 min)* — fixes a Day-2 stub
- Replace the hardcoded `sobol_indices` dict with a real call to `sensitivity.sobol_indices(scenario, tract, edges)` + `commission_study_recommendation(...)`. Add a `/compare` endpoint wrapping `montecarlo.compare`.
- Add an endpoint (or extend `/scenario`) that returns the **M draws / histogram bins** the fan chart needs (e.g., `mc_draws` summary or percentile series) so the UI can render the distribution.
- **DoD:** `GET /sensitivity?tract_id=...&defer_years=5` returns real S1/ST + the study recommendation; `/compare` works.

### V2 — Governance & audit persistence (`audit.py`) *(~1.5 h)* — fixes a Day-2 stub
- Persist an `AuditRecord` per run to a store (SQLite/JSONL): `run_id, inputs_snapshot_ref, catalog_version (get_catalog_version()), enabled_edges, contested_edges_enabled, overrides, seed, timestamp`.
- Log a **contested-edge consent event** whenever a contested edge (E7, or secondary E6) is enabled — attributed + timestamped (SRS FR-GOV-3, RAI-1).
- Make `/audit/{run_id}` **read from the store** (not synthesize).
- **DoD:** running a scenario writes an audit row; enabling E7 writes a consent event; `/audit/{id}` returns the stored record.

### V3 — Streamlit app skeleton + scenario controls (`app.py`) *(~2 h)*
- Sidebar controls: **tract selector** (synthetic tracts + the golden default), **defer-years slider**, **discount-rate**, **n_draws**, and the **edge enable/disable** panel.
- **Contested-edge consent gate** (UI): E6/E7 **OFF by default**, shown with a "contested" label + a required explicit checkbox + a confirmation note; enabling re-runs MC (the distribution visibly **re-fans**) and triggers the audit consent log (V2).
- Wire to the compute modules (cached). Render the **abstention banner** prominently when `result.abstain` is True.
- **DoD:** controls drive a live MC run; contested gate works + logs; abstain banner shows.

### V4 — Deploy to free tier *(~1 h)*
- Add `requirements.txt` (or configure Streamlit Cloud to read `pyproject`), pin versions, ensure synthetic data + catalog ship in the repo so the app self-bootstraps.
- Deploy the Streamlit app to **Streamlit Community Cloud** (repo is public); smoke-test the public URL in **incognito**.
- **DoD:** a working public URL; cold-start loads the golden scenario without manual setup.

### V5 — Audit panel + lifecycle surfacing in UI (`app.py`) *(~1 h)*
- Audit panel: show the current run's inputs snapshot, enabled edges, contested-consent, seed, **catalog version**, timestamp.
- Lifecycle: surface each edge's **`last_validated`** + a **stale flag** (older than a window), and a one-line **recalibration-trigger** note (EPA 9M→4M inventory revision) — coordinate the copy with Chaitanya's model card.
- **DoD:** audit + lifecycle visible in-app.

### V6 — STRETCH (if ahead): map view + optimizer
- **Map:** pydeck/folium tract map with an SVI overlay, synthetic tracts clearly labeled.
- **Optimizer:** `optimize.py` — under a budget, rank/allocate tracts by deferral-multiplier-adjusted value with an **equity floor** for high-SVI tracts ("proposes, human allocates"). Surface as a "prioritized list" panel.

---

## Contracts you PRODUCE
- `app.py` (the deployed demo) · `audit.py` (persistence + consent log) · real `/sensitivity`, `/compare`, `/audit` · the public URL.

## Contracts you CONSUME (from Chaitanya)
- `brief.generate_brief(result, sobol, commission_rec, compare, edges)` → render its output in the app.
- His panel components (fan chart, tornado, edge table) — agree function signatures in STEP 0 so you can drop them into the layout.

## Definition of Done — Varun (Day 3)
- [ ] `/sensitivity` + `/compare` real (no stubs); `/audit` reads from a store.
- [ ] Audit persistence + contested-consent logging.
- [ ] Streamlit controls + contested-consent gate (re-fans + logs) + abstain banner.
- [ ] Deployed public URL, golden scenario loads cold, tested in incognito.
- [ ] Audit + lifecycle (stale flags, recalibration note) surfaced in-app.

## Risks / notes
- **Sobol is slow** on a cold Streamlit box — `@st.cache_data` the `sobol_indices` call keyed on (tract, defer_years, enabled_edges, seed); consider a smaller `n_base` for the live UI and the full run in the notebook.
- Make the app **self-bootstrapping** (generate synthetic tracts if missing) so the deploy has no manual step.
- Don't let the demo depend on a separately-hosted API — direct module imports are the safe path; the API is the "we also built a clean service layer" bonus.
