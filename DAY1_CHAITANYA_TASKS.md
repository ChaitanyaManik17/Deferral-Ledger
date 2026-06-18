# DEFERRAL LEDGER — Day 1 Tasks: **CHAITANYA**
### Role: Edge-prior catalog + cascade structure + governance/model-card scaffolding
*Build team is just **Chaitanya + Varun** — Manush is unavailable for the entire build, so the two of you absorb his UI/deploy work and **carry the FULL scope via overtime — nothing is cut**. Day 1 = Foundations; no UI today. From Day 3 the dashboard is split between you two (you lead the analytics/brief panels). Your catalog is what makes the whole thing defensible — every number must be cited (SRS EV-1 / C-4). Pair: Varun (data layer + DAG engine).*

---

## Day-1 goal (shared, you + Varun)
> **A causal DAG loads from your cited edge-prior catalog and runs on Varun's synthetic + cached public data, producing a single *deterministic* deferral-multiplier for one tract.** (Monte-Carlo + Sobol = Day 2.)

**Your end-of-day demoable artifact:** `catalog/edges.yaml` — a validated, fully-cited edge catalog that Varun's `dag.py` loads and runs, plus a catalog validator that **refuses any edge missing a citation**, plus a filled `docs/edge_evidence_ledger.md`.

---

## STEP 0 — Joint kickoff (do together first, ~90 min)
Same as Varun's STEP 0. The critical shared artifact is the **DAG node/edge list** — you co-design it on a whiteboard, then you own turning it into `catalog/edges.yaml` while Varun builds `dag.py`. Agree the YAML keys now so his engine reads your file without rework.

---

## The cascade structure (flagship: LSL deferral → costs)
Nodes/edges you'll encode (confirm in STEP 0):
```
Defer Δyr ─▶ deferred $ = lines × cost_per_line          [E0 cost edge]
Defer Δyr ─▶ continued exposure (child person-years)     [structural — Varun's exposure calc]
exposure  ─▶ sustained BLL increment (µg/dL)             [E1]
BLL ─▶ IQ loss ─▶ lifetime-earnings loss                 [E2 → E3]
BLL ─▶ special-education cost                            [E4]
BLL ─▶ childhood healthcare / Medicaid cost              [E5]
BLL(adult, cumulative) ─▶ cardiovascular/CKD cost        [E6  secondary]
BLL ─▶ behavioral/ADHD ─▶ juvenile-justice/crime cost    [E7  CONTESTED, off by default]
```
Output (Varun computes): `M = PV(Σ enabled downstream $) / deferred $`.

---

## YOUR TASKS (ordered)

### C0 — Repo scaffolding & environment *(~45 min — do FIRST, right after STEP 0; both of you are blocked until the repo exists)*
- Init the git repo with the layout from Varun's doc. `pyproject.toml` (Python 3.11). Deps: `numpy scipy pandas networkx SALib pyyaml pydantic requests pytest`; dev: `ruff pytest`. Add `fastapi streamlit` now so the Day-3 dashboard work isn't blocked.
- Add `ruff` + `pytest` config, `.gitignore`, a `Makefile`/`justfile` (`make setup`, `make test`, `make run`), and a README skeleton with the scope/non-goals/3 decision points from STEP 0.
- **Push immediately** so Varun can pull and start his modules (he's blocked on this).
- **DoD:** `make setup && make test` runs (even with 0 tests) on a clean clone; repo pushed.

### C1 — Edge-prior catalog schema (`catalog/edges.yaml`) *(~45 min)*
Agree with Varun (his `EdgePrior` Pydantic model). Each edge:
```yaml
- id: E2_bll_to_iq
  from_node: bll
  to_node: iq_loss
  dist_type: normal           # normal | lognormal | triangular | uniform | point
  params: {mean: -0.87, sd: 0.12}   # derive sd from the published CI
  point_estimate: -0.87
  ci_low: -1.10
  ci_high: -0.64
  source: "Lanphear et al. 2005, pooled analysis"
  effect_size: "-0.87 IQ pts per 1 µg/dL (steeper, ~-1.37, below 10 µg/dL)"
  units: "IQ points per µg/dL"
  contested: false
  enabled: true
  last_validated: "2026-06-14"
```
- **DoD:** schema agreed; one fully-worked example edge committed.

### C2 — Fill the edge priors from sourced literature (`catalog/edges.yaml`) *(~120 min, your biggest task)*
Use the **starter table below** (already researched). For each: convert point + interval → distribution params (`priors.py` helper, C3), set `contested`/`enabled`, add `source` + `last_validated`.
- For ranges (e.g., cost/line $1,200–$12,300) → `triangular {low, mode, high}`.
- For point + CI (e.g., BLL→IQ) → `normal {mean, sd}` where `sd ≈ (ci_high − ci_low) / 3.29` (95% CI).
- For hazard ratios (E6) → convert to a cost via a documented step (VSL or medical+productivity) and record the assumption.
- **DoD:** all non-contested edges (E0–E6) filled + cited; E7 filled but `contested: true, enabled: false`.

### C3 — Distribution helper (`priors.py`) *(~45 min)*
- `to_distribution(edge) -> sampler` and `point(edge)` (returns mean/mode for Day-1 deterministic run).
- Today only `point()` is consumed by Varun's engine; the samplers are ready for Day-2 Monte-Carlo (hand-off).
- **DoD:** `point(edge)` returns the right central value per `dist_type`; samplers unit-tested for shape/mean.

### C4 — Catalog loader + validation (`catalog.py`, `tests/test_catalog.py`) *(~60 min)*
- Load YAML → list[`EdgePrior`]; **validation that FAILS the build if any edge lacks `source` or `last_validated`** (enforces EV-1 / SRS C-4). Validate `dist_type`/`params` consistency.
- **DoD:** loader returns validated edges; a test asserts a citation-less edge is **rejected**.

### C5 — Contested-edge registry + default safe set (`catalog/contested.yaml`) *(~30 min)*
- List contested edges (E7 crime; mark E6 CVD as "secondary"); define the **default enabled set** (contested OFF). This is the data behind Manush's later consent toggle (SRS FR-DASH-3, RAI-1).
- **DoD:** registry committed; loader exposes `default_enabled_edges()` excluding contested.

### C6 — Model Card skeleton + Evidence Ledger (`docs/model_card.md`, `docs/edge_evidence_ledger.md`) *(~45 min)*
- Model Card skeleton: intended use, data, assumptions, **non-goals** (copy SRS §8), abstention conditions, limitations (lifecycle deliverable LC-4).
- Evidence Ledger = the filled Appendix-B table (every edge: value, CI, distribution, source, contested, status).
- **DoD:** both docs committed; ledger rows match `edges.yaml`.

---

## Research-grounded edge-prior STARTER TABLE (verify + cite `last_validated`)
| Edge | Starter value | Interval | Proposed dist | Source | Contested / default | Status |
|---|---|---|---|---|---|---|
| **E0** cost / line | $4,700 | $1,200–$12,300 | Triangular | EPA LCRI cost fact sheet | No / ON | ✅ confirmed |
| **E1** LSL → sustained BLL increment (µg/dL) | ~+1–3 µg/dL while LSL present (conservative) | wide | Triangular (wide) | Water-lead→BLL lit.; Flint (Hanna-Attisha 2016) % elevated ~doubled | No / ON | ⚠️ **needs firmer source — top research priority** |
| **E2** BLL → IQ | −0.87 IQ/µg/dL (−1.37 <10 µg/dL) | per CI | Normal | Lanphear et al. 2005 (pooled) | No / ON | ✅ confirmed |
| **E3** IQ → lifetime earnings | $10,600–$13,100 / IQ pt (3% disc.) | range | Uniform/Normal | Sci. Total Environ. 2021; Unleaded Kids | No / ON | ✅ confirmed |
| **E4** BLL → special-education cost | special-ed ~$12,833/yr (1998 USD → inflate) ×~3 yr; or Gould lumped ~$5,600/child med+sped | with CI | Triangular | Gould 2009 (PMC2717145); EPA NCEE 2025 working paper; NCHH | No / ON | ✅ confirmed (inflate to 2026 USD) |
| **E5** BLL → childhood healthcare / Medicaid | per-child medical share of childhood env-disease burden ($76.6B/2008 env-disease, lead a major component) | wide | Triangular | Trasande & Liu 2011, *Health Affairs* | No / ON | ✅ confirmed (decompose to per-child) |
| **E6** adult cumulative lead → CVD/CKD | HR 1.70 (CVD mortality) for 1.0→6.7 µg/dL; ~256k premature CVD deaths/yr attributable | HR CI 1.30–2.22 | LogNormal (on HR) → cost via VSL/medical | Lanphear et al. 2018, *Lancet Public Health* | **Secondary / OFF or low-weight** | ✅ confirmed (long-horizon; document VSL assumption) |
| **E7** BLL → behavioral → juvenile-justice/crime | +15% detention/incarceration risk per 1 µg/dL preschool BLL | per study | LogNormal (on risk) → cost-of-crime | Aizer & Currie 2017 (NBER w23392) | **CONTESTED / OFF by default** | ✅ confirmed (stigmatizing — keep off by default) |

> **Top research priority for you today: edge E1** (how much BLL rises while an LSL stays in the ground). It's the hinge of the whole cascade and currently has the weakest number. Chase: EPA exposure/IEUBK model water contribution, Flint/Newark pre-post BLL studies. If you can't pin it, encode a **deliberately wide** Triangular prior and flag it — Day-2 Sobol will then correctly show E1 dominates the spread (which is itself a finding: "commission a water-lead study first").

---

## Contracts you PRODUCE (others depend on these)
- `catalog/edges.yaml` + `catalog/contested.yaml` + `priors.py` → **Varun's `dag.py`** consumes these.
- `default_enabled_edges()` / contested registry → the **Day-3 dashboard consent toggle** (now built by you two).
- Evidence ledger + model card → submission's Responsible-AI + lifecycle answers.

> **2-person ownership (Days 2–4) — FULL scope retained via overtime:** you = catalog/priors/Sobol + RAG brief + evaluation **+ second-region (India) data + contested/equity analyses**; Varun = data/sim/DAG/Monte-Carlo + GPU path + optimizer + FastAPI + deploy. The **Day-3 dashboard is co-owned** — you lead the analytics + brief panels, Varun wires data/deploy. **Stretch items stay IN-SCOPE** (GPU Monte-Carlo, budget optimizer, tract map, second region). Full split in the Day-3 deep-dive.

## Contracts you CONSUME (agree with Varun)
- `EdgePrior` / `Tract` Pydantic models (`models.py`) and the YAML keys — lock these in STEP 0 so your file loads into his engine with zero rework.

## Definition of Done — Chaitanya (Day 1)
- [ ] **Repo scaffolded + pushed** (`make setup/test` green on a clean clone) — unblocks Varun.
- [ ] DAG node/edge list agreed (joint) and encoded as `edges.yaml`.
- [ ] All edges E0–E7 filled with distributions + **sources** + `last_validated`.
- [ ] `priors.py` `point()` + samplers (samplers ready for Day-2 MC).
- [ ] `catalog.py` loader + validation; test **rejects a citation-less edge**.
- [ ] Contested registry + `default_enabled_edges()` (contested OFF).
- [ ] `model_card.md` skeleton + `edge_evidence_ledger.md` filled.

## Risks / notes
- **EV-1 is non-negotiable:** no number reaches the system without a citation. Your validator enforces it — write that test first (TDD).
- Keep E7 (crime) **off by default**; it exists for an internal, consented analysis only (RAI-1). Same for the most stigmatizing framing.
- Hand Varun the `point()` values early (even partial) so his engine isn't blocked; backfill citations as you go.

## Sources (for the evidence ledger)
- EPA LCRI replacement-cost fact sheet — https://www.epa.gov/system/files/documents/2024-10/final_lcri_fact-sheet_calculating-service-line.pdf
- Lanphear et al. 2005 (BLL→IQ pooled) — see [R4] in the SRS
- IQ→earnings: https://www.sciencedirect.com/science/article/abs/pii/S0048969721013759 · https://unleadedkids.org/special-series-iq/2025/03/04/
- Gould 2009 (benefits of lead hazard control) — https://pmc.ncbi.nlm.nih.gov/articles/PMC2717145/
- EPA NCEE 2025 (special education & lead) — https://www.epa.gov/system/files/documents/2025-10/2025_04.pdf
- Trasande & Liu 2011 (environmental disease in children, *Health Affairs*) — https://www.healthaffairs.org/doi/full/10.1377/hlthaff.2010.1239
- Lanphear et al. 2018 (low-level lead & mortality, *Lancet Public Health*) — https://www.sciencedirect.com/science/article/pii/S2468266718300252
- Aizer & Currie 2017 (lead & juvenile delinquency, NBER w23392) — https://www.nber.org/system/files/working_papers/w23392/w23392.pdf
- CDC blood-lead surveillance / EPHT API — https://www.cdc.gov/lead-prevention/php/data/national-surveillance-data.html · https://open.cdc.gov/apis.html
