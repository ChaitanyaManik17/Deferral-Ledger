# Software Requirements Specification (SRS)
## DEFERRAL LEDGER — A Cross-System Cascade-Cost Decision-Support Engine

| | |
|---|---|
| **Document** | Software Requirements Specification |
| **Product** | DEFERRAL LEDGER |
| **Competition** | USAII Global AI Hackathon 2026 — Graduate Track, Brief 6A (Public Systems & Policy: *The Cost of Doing Nothing*) |
| **Version** | 1.0 (draft for build week, June 14–21 2026) |
| **Status** | Baseline for implementation |
| **Standard** | Structured per ISO/IEC/IEEE 29148:2018 (adapted from IEEE 830) |
| **Authors** | Varun Bhandari · Chaitanya Manik · Manush Patel |

> **One-line product statement:** *We don't price the lead pipe — we trace the dollars it forces other public budgets to spend later. Every deferred replacement dollar creates an obligation cascade that DEFERRAL LEDGER quantifies as a **distribution**, not a scary single total.*

---

## 1. Introduction

### 1.1 Purpose
This SRS specifies the requirements for **DEFERRAL LEDGER**, an AI-powered decision-support system that estimates the **cross-system, downstream public cost of *deferring* a preventive capital investment** — using lead-service-line (LSL) replacement as the flagship domain. It is written for the development team (3 M.S. CS students), the hackathon judges (as evidence of solution design and AI reasoning), and any future maintainer.

The document defines the product scope, stakeholders, data, functional and non-functional requirements, the AI/analytics architecture, responsible-AI guardrails, model lifecycle requirements, and the evaluation/acceptance criteria.

### 1.2 Product Scope & Vision
Communities defer infrastructure replacement under budget pressure. The *true* cost of that deferral is not the pipe — it is the **obligatory downstream spending** the deferral forces onto **other agency budgets later** (special education, Medicaid, lost lifetime earnings, etc.). No single dataset spans "pipe → life outcome," and the foundational input is itself unstable: **on 25 Nov 2025 the EPA revised the national LSL count from ~9 million to ~4 million** [R1, R2]. A defensible product therefore *cannot* output a single number.

DEFERRAL LEDGER models the cascade as an **explicit, citable causal DAG** where every edge is a **literature-sourced prior distribution**, propagates uncertainty by **Monte-Carlo** to produce a posterior over a **"deferral multiplier"** (future obligated dollars per deferred dollar), and uses **variance-based (Sobol) sensitivity** to tell decision-makers *which uncertainty is worth buying down before they commit capital*.

**In scope (flagship domain):** deferral of LSL replacement → continued childhood lead exposure → cascading public costs.
**Designed for extensibility:** the engine is domain-agnostic (any deferred-prevention DAG); a second domain and a second region (e.g., an Indian city) are *Could*-priority extensions.

**Non-goals (hard, stated up front — see §8):** DEFERRAL LEDGER is **NOT** a tool that scores, predicts, or ranks outcomes for any individual child, household, or address; it is **NOT** a justification engine for involuntary intervention; and it does **NOT** make the funding decision — it informs a human one.

### 1.3 Definitions, Acronyms, Abbreviations
| Term | Definition |
|---|---|
| **LSL / GRR** | Lead Service Line / Galvanized pipe Requiring Replacement |
| **Deferral multiplier (M)** | Present value of incremental cross-budget downstream cost caused by deferring replacement, divided by the deferred replacement cost. `M > 1` ⇒ deferral compounds cost. |
| **Causal DAG** | Directed Acyclic Graph whose nodes are quantities (cost, exposure, outcomes) and whose edges are probabilistic causal relationships (effect-size priors). |
| **Edge prior** | A probability distribution (not a constant) for a causal effect, sourced from a named study with its reported effect size and confidence interval. |
| **Contested edge** | A socially-sensitive edge (e.g., lead→crime) that is **off by default** and must be consciously enabled by the user. |
| **BLL** | Blood Lead Level (µg/dL). |
| **Sobol index** | Variance-based global sensitivity measure attributing output variance to each input. |
| **HITL** | Human-in-the-Loop. |
| **PV** | Present Value (discounted). |
| **EPHT** | CDC Environmental Public Health Tracking network. **SVI** CDC/ATSDR Social Vulnerability Index. **DWINSA** Drinking Water Infrastructure Needs Survey & Assessment. **LCRI** Lead and Copper Rule Improvements. |

### 1.4 Intended Audience & Reading Order
- **Judges / evaluators:** §1, §2, §3, §8, §10 (problem understanding, architecture, responsible AI, evaluation).
- **Developers:** §3–§7, §9, Appendix C (build plan), Appendix B (edge catalog).
- **Future maintainers:** §9 (lifecycle), Appendix B, Appendix E.

### 1.5 References
- **[R1]** EPA, *Lead Service Line Inventory Recommendations* (21 Nov 2025) — https://www.epa.gov/system/files/documents/2025-11/lsl-inventory_2025.11.20.pdf
- **[R2]** NRDC, *The EPA Now Says There Aren't 9 Million Lead Pipes—There Are 4 Million. Be Skeptical.* — https://www.nrdc.org/media/epa-now-says-there-arent-9-million-lead-pipes-there-are-4-million-be-skeptical
- **[R3]** EPA, *Revised Lead and Copper Rule (LCRR/LCRI)* — https://www.epa.gov/ground-water-and-drinking-water/revised-lead-and-copper-rule
- **[R4]** Lanphear et al. (2005), pooled international analysis, BLL→IQ dose-response (~0.87 IQ pts per µg/dL; ~1.37 below 10 µg/dL).
- **[R5]** *Estimated IQ points and lifetime earnings lost to early-childhood blood lead levels in the U.S.* (Sci. Total Environ., 2021) — https://www.sciencedirect.com/science/article/abs/pii/S0048969721013759
- **[R6]** Unleaded Kids, *Calculating IQ-Related Increased Lifetime Earnings* (IQ point ≈ $10,600–$13,100, 3% discount) — https://unleadedkids.org/special-series-iq/2025/03/04/
- **[R7]** EPA LCRI fact sheet, *Calculating Service Line Replacement Cost* (avg ~$4,700/line; range $1,200–$12,300) — https://www.epa.gov/system/files/documents/2024-10/final_lcri_fact-sheet_calculating-service-line.pdf
- **[R8]** CDC, *Childhood Blood Lead Surveillance (national & state data)* — https://www.cdc.gov/lead-prevention/php/data/national-surveillance-data.html
- **[R9]** CDC, *Environmental Public Health Tracking — APIs* (JSON) — https://open.cdc.gov/apis.html
- **[R10]** Brookings, *What would it cost to replace all the nation's lead water pipes?* — https://www.brookings.edu/articles/what-would-it-cost-to-replace-all-the-nations-lead-water-pipes/
- **[R11]** Environmental Policy Innovation Center, *What Best Available Data Tells Us About Lead Service Lines* — https://www.policyinnovation.org/insights/what-best-available-data-tells-us-about-lead-service-lines

> Edge-specific source citations are catalogued in **Appendix B**. Every numeric prior in the running system MUST carry its citation (see DR-5, FR-DAG-3).

### 1.6 Document Conventions
- Requirement IDs: `FR-<MODULE>-<n>` (functional), `NFR-<CATEGORY>-<n>` (non-functional), `DR-<n>` (data), `RAI-<n>` (responsible AI), `LC-<n>` (lifecycle), `IF-<n>` (interface).
- **Priority (MoSCoW + demo flag):** **M** = Must (in 7-day demo), **S** = Should, **C** = Could (stretch), **W** = Won't this round (future). The 7-day MVP = all **M** requirements.
- Keywords **MUST / SHOULD / MAY** per RFC 2119.

---

## 2. Overall Description

### 2.1 Product Perspective
DEFERRAL LEDGER is a new, self-contained web application. It follows the Graduate-brief recommended layering **Data → Governance → Intelligence → Decision → Human Action → Feedback**:

```
            ┌──────────────────────────────────────────────────────────────────────┐
            │                          DEFERRAL LEDGER                               │
            │                                                                        │
 PUBLIC ───▶│  [1] DATA LAYER          ingest EPA LSL inventory + cost, CDC BLL/EPHT │
 DATA  +    │                          PLACES, SVI, EJScreen; + synthetic block-     │
 SYNTHETIC  │                          level inventory generator                     │
            │            │                                                           │
            │            ▼                                                           │
            │  [2] GOVERNANCE LAYER    edge-prior CATALOG (versioned, cited),        │
            │                          provenance + last-validated dates,            │
            │                          contested-edge registry & consent gate        │
            │            │                                                           │
            │            ▼                                                           │
            │  [3] INTELLIGENCE LAYER  Causal DAG ─▶ Monte-Carlo propagation ─▶       │
            │                          deferral-multiplier POSTERIOR ─▶ Sobol         │
            │                          sensitivity ─▶ (optional) budget optimizer     │
            │            │                                                           │
            │            ▼                                                           │
            │  [4] DECISION LAYER      scenario compare (defer Δyr vs replace now);   │
            │                          per-tract ranking with credible bands;        │
            │                          ABSTAIN gate when CI spans M<1                  │
            │            │                                                           │
            │            ▼                                                           │
            │  [5] HUMAN-ACTION LAYER  RAG-grounded plain-language decision brief     │
            │                          (every number cited); dashboard; audit log    │
            │            │                                                           │
            │            ▼                                                           │
            │  [6] FEEDBACK/LIFECYCLE  drift monitor (predicted vs observed BLL),     │
            │                          staleness flags, recalibration triggers        │
            └──────────────────────────────────────────────────────────────────────┘
                                  ▲
                         HUMAN DECISION-MAKERS (water/finance office; cross-agency leadership)
```

### 2.2 Product Functions (summary)
1. Ingest public + synthetic infrastructure, exposure, and cost data.
2. Assemble a transparent causal DAG with citable, distribution-valued edges.
3. Propagate uncertainty (Monte-Carlo) to a **deferral-multiplier posterior** with credible intervals.
4. Attribute the multiplier's *spread* to specific edges (Sobol) → "which study to commission first."
5. Compare scenarios (replace now vs defer Δ years) per neighborhood/budget cycle, with bands.
6. Let users consciously toggle **contested edges** and watch the multiplier re-fan.
7. Generate a citation-grounded decision brief and an auditable run record.
8. Abstain from a "must-fund-now" recommendation when the multiplier CI spans below 1.0.
9. Monitor drift and flag stale priors / superseded inventory counts.

### 2.3 User Classes & Characteristics
| User class | Description | Key needs |
|---|---|---|
| **City water / finance officer** (primary) | Holds the capital budget; chooses replace-vs-defer by neighborhood/year. | Defensible per-tract ranking with uncertainty; plain-language brief. |
| **Cross-agency leadership** (primary) | Health + education + finance directors. | Edge-sensitivity ranking → which uncertainty to commission a study on; contested-edge governance. |
| **Data / QI analyst** (secondary) | Configures priors, validates back-tests, runs scenarios. | Edge catalog editing, provenance, reproducibility. |
| **Advocacy / public (read-only)** (secondary) | Transparency consumers. | Default non-stigmatizing view; clear assumptions. |
| **System administrator** (support) | Deploys/operates the system. | Versioning, logs, recalibration triggers. |

### 2.4 Operating Environment
- Web application, modern browsers (Chrome/Firefox/Edge/Safari, last 2 versions).
- Backend deployable on free tiers (Streamlit Community Cloud / Render); Postgres on Neon free tier.
- Python 3.11+ runtime; optional GPU (RAPIDS/CuPy) for Monte-Carlo acceleration, with a **mandatory CPU/NumPy fallback** (no GPU may be required to run the demo).

### 2.5 Design & Implementation Constraints
- **C-1 (M):** No real personal/identifiable data may be used. Person-level inputs MUST be synthetic or public aggregates only.
- **C-2 (M):** Must run end-to-end on free-tier infrastructure (no paid dependency required); paid AI tools, if any, must have a free fallback (rubric rewards no paid-tool advantage).
- **C-3 (M):** Built within the June 14–21 2026 window; all **M** requirements demoable.
- **C-4 (M):** Every numeric prior surfaced to a user MUST be traceable to a cited source with a last-validated date.
- **C-5 (S):** Outputs MUST be reproducible from a stored random seed + edge-catalog version + input snapshot.
- **C-6 (M):** GPU is optional; CPU path is the reference implementation.

### 2.6 Assumptions & Dependencies
- **A-1:** Public datasets [R7,R8,R9] remain reachable during build; cached snapshots are kept (governance/availability risk: EJScreen was de-published from EPA.gov in 2025; SVI availability was contested → cache with provenance dates).
- **A-2:** Edge priors are drawn from peer-reviewed literature; the team is responsible for transcribing effect sizes + CIs faithfully (Appendix B).
- **A-3:** The causal structure is an explicit modeling assumption, presented as such; the product's value is *transparency + uncertainty*, not a claim of ground-truth causality.
- **A-4:** Granular block-level LSL inventories are often incomplete → a **documented synthetic inventory generator** is the primary data path for the demo.

### 2.7 User Documentation
- README (run + deploy), a one-page **Model Card**, an **Assumptions & Limitations** sheet, and an in-app "How to read this" panel.

---

## 3. System Architecture & Component Design

### 3.1 Components
| ID | Component | Responsibility | Owner (suggested) |
|---|---|---|---|
| **C-DATA** | Data ingestion & synthetic generator | Pull/cache public data; generate documented synthetic block-level inventory + cohort. | Varun |
| **C-CAT** | Edge-prior catalog & governance | Versioned, cited, distribution-valued edges; contested-edge registry; provenance. | Chaitanya |
| **C-DAG** | Causal DAG engine | Build graph, validate acyclicity, assemble cost cascade. | Varun |
| **C-MC** | Monte-Carlo propagation | Sample edges, propagate to deferral-multiplier posterior; GPU/CPU. | Varun |
| **C-SENS** | Sensitivity analysis | Sobol/variance attribution → tornado ranking. | Chaitanya |
| **C-OPT** | Budget allocator (stretch) | Rank tracts under budget given multiplier + equity floor. | Varun |
| **C-EXP** | RAG explanation layer | Citation-grounded decision brief; never invents numbers. | Chaitanya |
| **C-UI** | Dashboard & API | Fan charts, tornado, map, scenario controls, audit log; FastAPI glue. | Manush |
| **C-LIFE** | Lifecycle/feedback | Drift monitor, staleness flags, recalibration triggers, model card. | shared |

### 3.2 Primary Data Flow
`Inputs (public + synthetic)` → `C-DATA normalizes` → `C-CAT provides cited edge priors` → `C-DAG assembles cascade for scenario S` → `C-MC samples N draws → multiplier posterior` → `C-SENS attributes variance` → `C-DECISION (abstain gate, scenario compare, optional C-OPT)` → `C-EXP brief + C-UI dashboard` → `C-LIFE logs run, monitors drift`.

---

## 4. Data Requirements

### 4.1 External Datasets
| ID | Dataset | Use | Access / License |
|---|---|---|---|
| **DR-1** | EPA national LSL inventory + Service Line Dashboard; DWINSA; SDWIS [R1,R3] | LSL counts/locations, structural-uncertainty headline (9M→4M) | Public; CSV/dashboard; cache snapshot + date |
| **DR-2** | EPA LCRI replacement-cost figures [R7] | "Deferred dollar" denominator: ~$4,700/line (range $1,200–$12,300) | Public; document range as a prior |
| **DR-3** | CDC Childhood Blood Lead Surveillance (national/state) [R8] | BLL prevalence/aggregates for calibration | Public aggregates; micro-data gated → not used |
| **DR-4** | CDC EPHT API (JSON) [R9] | Programmatic BLL + environmental indicators | Public JSON API |
| **DR-5** | CDC PLACES | Small-area health outcomes for calibration | Public; CSV/API |
| **DR-6** | CDC/ATSDR SVI 2022 | Equity overlay; identify high-vulnerability tracts | Public (cache; availability contested 2025) |
| **DR-7** | EPA EJScreen | Environmental-justice overlay | Public mirror/cache (de-published from EPA.gov 2025) |
| **DR-8** | Effect-size literature [R4,R5,R6] | Edge priors (BLL→IQ, IQ→earnings, etc.) | Published; transcribed into Appendix B |
| **DR-9** | **Synthetic block-level inventory + child cohort** | Primary demo data; methodology-documented | Generated; "synthetic-data card" required |

- **DR-10 (M):** Real person-level data MUST NOT be ingested. All person-level quantities are synthetic or public aggregates (enforces C-1).
- **DR-11 (M):** Every dataset load MUST record source URL + retrieval timestamp + version for the audit log and provenance.
- **DR-12 (M):** The **synthetic generator** MUST be documented (distributional assumptions, seeds) and reproducible, and its outputs labeled "SYNTHETIC" throughout the UI.

### 4.2 Causal DAG Specification (flagship: LSL deferral → cascade)
**Decision/Exposure spine**
- `D` Defer replacement of LSLs in tract *t* by `Δ` years (vs replace now). → deferred dollars `$D = lines_t × cost_per_line` (cost from DR-2 prior).
- `E` Continued exposure: `Δ` × (children <6 in affected households) person-years of elevated water-lead.
- `B` Incremental sustained BLL (µg/dL) attributable to LSL during deferral (prior).

**Cascade edges (each a distribution; see Appendix B)**
- `B → IQ`: ~0.87 IQ pts per µg/dL (steeper, ~1.37, below 10 µg/dL) [R4].
- `IQ → lifetime earnings`: ≈ $10,600–$13,100 per IQ point, 3% discount (or 1.4%/IQ pt of lifetime earnings) [R5,R6].
- `B → special-education placement`: Δ probability × incremental cost/child/year × years (prior).
- `B → childhood healthcare / Medicaid`: management + sequelae cost (prior).
- `B(adult, cumulative) → cardiovascular/CKD` *(secondary/contested)*: mortality/morbidity cost (prior).
- `B → ADHD/behavioral → juvenile-justice/crime` *(**contested**, off by default)*: cost (prior).

**Output:** `Deferral multiplier M = PV(Σ incremental downstream obligated $ caused by deferral) / $D`, as a **posterior distribution** over Monte-Carlo draws.

- **DR-13 (M):** Each edge is stored as a parametric distribution (e.g., Normal/LogNormal/Triangular) with parameters derived from a cited point estimate + CI, plus a `contested` boolean and `last_validated` date.
- **DR-14 (M):** The DAG MUST be validated acyclic at load; cycles are a fatal config error.

### 4.3 Data Dictionary (core entities)
- **Tract**: `{geoid, lines_count(synthetic/derived), children_under6, svi_percentile, has_inventory_flag}`
- **EdgePrior**: `{id, from_node, to_node, dist_type, params, source_citation, effect_size, ci, contested:bool, last_validated, enabled:bool}`
- **ScenarioRun**: `{id, tract_set, defer_years, budget, enabled_edges[], seed, n_draws, discount_rate, created_at}`
- **MultiplierResult**: `{run_id, mean, median, ci_low, ci_high, p_gt_1, abstain:bool, per_edge_sobol[]}`
- **AuditRecord**: `{run_id, user, inputs_snapshot_ref, catalog_version, overrides[], timestamp}`

---

## 5. Functional Requirements

### 5.1 Data Ingestion & Synthetic Generation (C-DATA)
- **FR-ING-1 (M):** The system MUST load and cache the external datasets in §4.1 with provenance metadata (DR-11).
- **FR-ING-2 (M):** The system MUST generate a documented synthetic block-level LSL inventory + child cohort calibrated to public aggregates (counts, SVI, BLL priors), reproducible from a seed (DR-9, DR-12).
- **FR-ING-3 (S):** The system SHOULD reconcile a real partial inventory (where available) with synthetic fill and clearly label which tracts are synthetic vs reported.
- **FR-ING-4 (M):** Ingestion MUST surface the **inventory uncertainty** (e.g., "unknown" service-line material share) as a first-class input, not silently impute it.

### 5.2 Causal DAG Engine (C-DAG)
- **FR-DAG-1 (M):** Build the cascade DAG from the edge catalog for a given scenario; validate acyclicity (DR-14).
- **FR-DAG-2 (M):** Support enabling/disabling edges per scenario (esp. contested edges).
- **FR-DAG-3 (M):** Every edge used in a computation MUST expose its citation, effect size, CI, and last-validated date to the UI/brief (C-4).
- **FR-DAG-4 (S):** Support user-supplied edge overrides (with the override logged in the audit record).

### 5.3 Monte-Carlo Propagation (C-MC)
- **FR-MC-1 (M):** Draw `N` samples (default ≥ 10,000) from each enabled edge prior and propagate through the DAG to compute the deferral-multiplier distribution per scenario.
- **FR-MC-2 (M):** Output mean, median, **90% and 95% credible intervals**, and `P(M > 1)`. **Single point estimates without an interval are prohibited in any user-facing output.**
- **FR-MC-3 (S):** Provide a GPU-accelerated path (RAPIDS/CuPy) with an automatic CPU/NumPy fallback (C-6); results MUST match within Monte-Carlo tolerance.
- **FR-MC-4 (M):** All runs MUST be reproducible from `{seed, catalog_version, inputs_snapshot}` (C-5).

### 5.4 Sensitivity Analysis (C-SENS)
- **FR-SENS-1 (M):** Compute variance-based (Sobol first-order + total, e.g., via SALib) attribution of multiplier variance to each edge prior.
- **FR-SENS-2 (M):** Render a **tornado/ranked chart** of "which edge drives the spread" → drives decision point #3 (which study to commission).
- **FR-SENS-3 (S):** Report ranking **stability** under reasonable prior perturbation (does the top driver stay on top?).

### 5.5 Scenario & Decision Layer (C-OPT / decision)
- **FR-SCN-1 (M):** Compare **replace-now vs defer-Δ-years** for a tract or set, returning multiplier distributions and PV cost deltas with bands.
- **FR-SCN-2 (M):** Rank tracts by deferral-multiplier-adjusted value, **always with credible bands**, never a bare ranking.
- **FR-OPT-1 (C):** Under a stated budget + capacity, propose an allocation maximizing avoided downstream obligation, **subject to an equity floor** for high-SVI tracts (stretch; clearly "proposes, human allocates").
- **FR-ABS-1 (M):** **Abstention gate** — if the multiplier's 95% CI spans below 1.0, the system MUST NOT output a "must-fund-now" recommendation and MUST display "deferral may not compound here; insufficient evidence to compel funding."

### 5.6 Explanation Layer (C-EXP)
- **FR-EXP-1 (M):** Generate a plain-language **decision brief** for non-technical leadership, summarizing the scenario, the multiplier with its interval, the top sensitivity driver, and the enabled edges.
- **FR-EXP-2 (M):** The brief MUST be **RAG-grounded**: every numeric claim is traceable to a catalog edge/source; the LLM MUST NOT generate or alter numbers (numbers come from C-MC, the LLM only narrates).
- **FR-EXP-3 (M):** If the LLM layer is unavailable, a **templated (non-LLM) brief** MUST be produced from the same numbers (graceful degradation; the quantitative core never depends on the LLM).

### 5.7 Dashboard & API (C-UI)
- **FR-DASH-1 (M):** Display the multiplier as a **fan chart / distribution** with CI, not a single number.
- **FR-DASH-2 (M):** Display the **Sobol tornado** chart and an edge table (value, CI, source, contested flag, enabled toggle).
- **FR-DASH-3 (M):** Provide a **contested-edge consent gate**: contested edges are OFF by default and require an explicit, labeled user action to enable; the **default view excludes the most stigmatizing edges**.
- **FR-DASH-4 (M):** Provide scenario controls (tract set, defer years, discount rate, enabled edges, budget).
- **FR-DASH-5 (S):** Map view (tract-level) with an SVI/equity overlay; clearly labels synthetic tracts.
- **FR-DASH-6 (M):** Display the **audit log** for the current run (inputs snapshot, enabled edges, overrides, seed, catalog version, timestamp).
- **IF-API-1 (S):** A FastAPI backend SHOULD expose `/scenario`, `/multiplier`, `/sensitivity`, `/brief`, `/audit` endpoints returning JSON (enables programmatic use + clean front/back separation).

### 5.8 Governance & Audit (C-CAT / C-LIFE)
- **FR-GOV-1 (M):** Maintain a versioned edge-prior catalog; each edge carries provenance + last-validated date.
- **FR-GOV-2 (M):** Record an immutable audit record per run (DR entities §4.3).
- **FR-GOV-3 (M):** Contested edges are tracked in a registry; enabling one writes a logged, attributed consent event.

---

## 6. External Interface Requirements
- **IF-UI-1 (M):** Browser-based dashboard (Streamlit + Plotly reference implementation).
- **IF-SW-1 (M):** Consume CDC EPHT JSON API [R9] and cached EPA/CDC files [R1,R7,R8].
- **IF-SW-2 (S):** Optional LLM API for the brief (free-tier model, e.g., Gemini free tier or an open Hugging Face model) — disclosed free/paid; degrades gracefully (FR-EXP-3).
- **IF-HW-1 (M):** No special hardware required; GPU optional (FR-MC-3).
- **IF-DATA-1 (M):** Persist runs/audit in PostgreSQL (Neon free tier) or SQLite fallback.

---

## 7. Non-Functional Requirements
- **NFR-PERF-1 (M):** A 10,000-draw scenario for a single tract returns in ≤ 5 s on CPU free-tier; ≤ 30 s for a multi-tract (≤ 50) batch.
- **NFR-PERF-2 (S):** GPU path achieves ≥ 10× speedup on ≥ 10⁶ draws (demonstrable, not required).
- **NFR-SCALE-1 (S):** Handle ≥ 1,000 synthetic tracts without redesign.
- **NFR-REL-1 (M):** Deterministic, reproducible results given a fixed seed/catalog/inputs (C-5).
- **NFR-REL-2 (M):** Graceful degradation: LLM, GPU, and live-API failures each have a working fallback.
- **NFR-USE-1 (M):** A non-technical officer can run a replace-vs-defer comparison and read the brief without training; uncertainty is always visible.
- **NFR-USE-2 (S):** Accessibility — colorblind-safe palettes, readable contrast, keyboard navigation.
- **NFR-SEC-1 (M):** No PII stored; secrets via environment variables; least-privilege DB access.
- **NFR-PRIV-1 (M):** Only synthetic/aggregate person-level data (C-1, DR-10).
- **NFR-MAINT-1 (S):** Edge catalog is data-driven (YAML/JSON) so priors update without code changes.
- **NFR-PORT-1 (S):** Containerizable; deployable to Streamlit Cloud/Render with documented steps.
- **NFR-REPRO-1 (M):** A run is fully described by its audit record (re-runnable).

---

## 8. Responsible-AI, Ethics & Safety Requirements
> Maps directly to the Devpost **Responsible-AI Guardrail (≤500 chars)**, **Human-in-the-Loop (≤500 chars)**, and the 10% Responsible-AI rubric dimension; engineered to also compete for the **Best Responsible AI** and **Best Social Impact** side prizes.

**Risk register & mitigations**
- **RAI-1 (M) — Deficit/deterministic framing of disadvantaged neighborhoods.** Mitigation: socially-sensitive edges (crime, behavioral) are **contested + off by default** (FR-DASH-3); user must consciously enable each, labeled "contested"; default view excludes the most stigmatizing edges. **Named tradeoff:** excluding them understates total cost but prevents weaponizing the tool against communities.
- **RAI-2 (M) — Over-claiming harm (a falsely large multiplier used to justify coercion).** Mitigation: every output carries front-and-center credible intervals (FR-MC-2); abstention gate (FR-ABS-1) blocks "must-fund-now" when `M<1` is plausible.
- **RAI-3 (M) — Individual-level inference / surveillance.** Mitigation + **NON-GOAL:** multipliers are reported **only** as population-level *budget obligations*, never individual risk; the system never scores or predicts outcomes for any child/household/address.
- **RAI-4 (M) — Spurious precision from an unstable base count.** Mitigation: inventory uncertainty (9M→4M) is propagated as a first-class input (FR-ING-4), making the instability a feature, not a hidden assumption.
- **RAI-5 (M) — LLM hallucinating numbers.** Mitigation: the LLM only narrates C-MC outputs; numbers are never LLM-generated (FR-EXP-2); templated fallback (FR-EXP-3).

**Human-in-the-Loop decision points (the brief requires 2–3; see §11).** The AI informs; **humans decide**. Socially-sensitive (contested-edge-enabled) or high-stakes recommendations require a second review cycle.

**Explicit non-goals (stated in product + video):** NOT individual scoring/prediction; NOT a justification engine for involuntary intervention; NOT the entity that allocates the budget; NOT a claim of definitive causality.

**Bypass conditions:** abstain when `M`'s 95% CI spans < 1.0 (RAI-2); abstain/flag when a driving edge's prior is stale or its dataset snapshot is older than its validity window (LC-2).

---

## 9. Model Lifecycle / MLOps Requirements
> The graduate differentiator is "what happens after the demo." These requirements are deliberately first-class.

- **LC-1 (M):** Each edge carries provenance + `last_validated` date; the UI flags edges past their validity window as **stale**.
- **LC-2 (M):** **Recalibration trigger** — a revision to the upstream inventory count (the EPA 9M→4M event [R1,R2] is the canonical example) or a superseding dose-response meta-analysis marks dependent edges/inputs stale and prompts recalibration.
- **LC-3 (S):** **Drift monitor** — compare predicted vs observed BLL trends (where surveillance is available) and widen uncertainty / flag when divergence exceeds a threshold.
- **LC-4 (M):** Ship a one-page **Model Card** (intended use, data, assumptions, limitations, non-goals, abstention conditions).
- **LC-5 (S):** Versioned catalog + inputs snapshots enable re-running any historical decision after priors change ("what would we have decided under the old count?").

---

## 10. Evaluation, Validation & Verification Requirements
- **EV-1 (M) — Edge-prior validation:** each edge prior MUST be checked against its source study's reported effect size + CI (Appendix B is the evidence ledger).
- **EV-2 (S) — Multiplier back-test:** sanity-check assembled multipliers against a city with both LSL replacement and later BLL surveillance (e.g., Newark, Pittsburgh, Flint), with explicit observational caveats — *direction*, not proof.
- **EV-3 (M) — Uncertainty calibration:** verify CI widths behave sensibly (e.g., widen with longer defer horizons / fewer data).
- **EV-4 (M) — Sensitivity correctness:** Sobol indices sum/behave correctly on a known synthetic DAG with an injected dominant edge (recovery test).
- **EV-5 (S) — Ablation:** show the multiplier re-fans when contested edges are toggled, demonstrating governance has real effect.
- **EV-6 (M) — Abstention test:** construct a scenario whose CI spans `M<1` and confirm the system abstains (FR-ABS-1).

---

## 11. Human-in-the-Loop & Decision Points
1. **Replace which tracts this budget year vs defer?** — system ranks by deferral-multiplier-adjusted value **with credible bands**; the **water/finance officer decides**.
2. **Which contested causal edges enter the official figure?** (e.g., include lead→earnings or not) — a deliberate, logged **human policy choice** (each downstream cost is an accountable decision, not a default).
3. **Which uncertainty to commission a study on?** — the Sobol ranking surfaces the edge driving the spread; **cross-agency leadership decides** where to spend to buy down ignorance before committing capital.

*The AI never executes any of these; it quantifies and explains. Decisions enabling contested edges or compelling funding require a second human review.*

---

## 12. Representative Use Cases
- **UC-1 — "Now vs later" for a high-SVI tract.** Officer selects a tract, defer = 5 yr, default (non-contested) edges; system returns `M = 2.3 (90% CI 1.4–3.9)`, brief: "every deferred $1 tends to obligate ~$2.30 later (range $1.40–$3.90)." Officer prioritizes replacement.
- **UC-2 — Edge governance.** Leadership enables the contested lead→behavioral edge for an internal analysis; multiplier re-fans wider; consent event logged; public/default view unchanged.
- **UC-3 — Commission-a-study.** Sobol shows the BLL→special-education edge dominates the spread; leadership commissions a local study there rather than over-investing in a precise pipe count.
- **UC-4 — Abstain.** For a low-exposure tract the 95% CI spans `M = 0.7–1.6`; system abstains from "must-fund-now," states deferral may not compound.

---

## 13. Acceptance Criteria & Traceability (selected)
| Acceptance criterion | Requirement(s) | Rubric dimension |
|---|---|---|
| No user-facing point estimate lacks an interval | FR-MC-2 | AI Reasoning; Responsible AI |
| Every shown number has a citation + date | FR-DAG-3, C-4 | AI Reasoning; Problem Understanding |
| Contested edges off by default, consented + logged | FR-DASH-3, FR-GOV-3, RAI-1 | Responsible AI |
| Sobol tornado drives "commission-a-study" decision | FR-SENS-2, decision pt #3 | AI Reasoning; Impact |
| Abstains when `M<1` plausible | FR-ABS-1, EV-6 | Responsible AI |
| Stale-prior / inventory-revision recalibration trigger | LC-1, LC-2 | Responsible AI (lifecycle) |
| Runs reproducible from audit record | NFR-REPRO-1, FR-MC-4 | Solution Design |
| Works on free tier, LLM/GPU optional | C-2, FR-MC-3, FR-EXP-3 | Solution Design; fairness (no paid advantage) |

---

## Appendix A — Glossary
See §1.3.

## Appendix B — Edge-Prior Catalog (evidence ledger; to be finalized Day 1–2)
| Edge | Point estimate | Interval | Distribution (proposed) | Source | Contested |
|---|---|---|---|---|---|
| Replacement cost / line | $4,700 | $1,200–$12,300 | Triangular/LogNormal | EPA LCRI [R7] | No |
| BLL → IQ | −0.87 IQ/µg/dL (−1.37 <10 µg/dL) | per [R4] | Normal | Lanphear 2005 [R4] | No |
| IQ → lifetime earnings | $10,600–$13,100 / IQ pt (3% disc.) | per [R6] | Uniform/Normal | [R5,R6] | No |
| BLL → special-education cost | *team to source* | with CI | TBD | NCES/SEEP + lit. | No |
| BLL → childhood Medicaid/healthcare | *team to source* | with CI | TBD | lit. | No |
| Adult cumulative lead → CVD/CKD | *team to source* | with CI | TBD | Lanphear 2018 et al. | Secondary |
| BLL → behavioral → juvenile-justice | *team to source* | with CI | TBD | lit. | **Yes (off by default)** |

> **Action (EV-1):** before any number is shown in the UI, its row here MUST be filled with a verifiable citation + last-validated date.

## Appendix C — Technology Stack & 7-Day Build Plan
**Stack (all free / disclosed):** Python 3.11, NumPy/SciPy, **NetworkX** (DAG), **SALib** (Sobol), pandas, optional **PyMC** for structured priors, optional **CuPy/RAPIDS** (GPU MC, with NumPy fallback), **FastAPI**, **Streamlit + Plotly** (+ pydeck/folium map), **PostgreSQL/Neon** (SQLite fallback), **LangChain** + free-tier LLM for the brief. GitHub for VC. Disclose AI coding assistance.

| Day | Milestone | Lead |
|---|---|---|
| 1 (Jun 14) | Lock scope/non-goals/3 decision points; finalize DAG + Appendix-B priors; repo + data inventory; mentor office hours for problem-framing | All |
| 2–3 | C-DATA synthetic generator + ingestion; C-CAT catalog (YAML, cited); C-DAG engine + acyclicity | Varun / Chaitanya |
| 3–4 | C-MC propagation + multiplier posterior; C-SENS Sobol tornado | Varun / Chaitanya |
| 4–5 | C-UI dashboard (fan chart, tornado, edge table, contested toggle, audit log); FastAPI glue; free-tier deploy | Manush |
| 5 | C-EXP RAG brief (+ templated fallback); abstention gate; model card | Chaitanya |
| 6 | Evaluation (EV-1/3/4/6), optional back-test (EV-2), responsible-AI + lifecycle write-ups, polish, dry-run demo | All |
| 7 (Jun 21) | Record 3–5 min video; finalize Devpost answers; test links in incognito; **submit early** | All |

## Appendix D — Rubric Alignment (why this wins)
- **AI Reasoning (35%):** explicit causal DAG with cited distributional edges; Monte-Carlo uncertainty; Sobol attribution; named tradeoff (transparent per-edge graph vs end-to-end statistical fit, justified because *no dataset spans pipe→outcome*); stated evaluation strategy (§10).
- **Problem Understanding (20%):** real users + 3 decision points; non-goals; grounds in the real EPA 9M→4M instability.
- **Solution Design (20%):** modular Data→…→Feedback layers; free-tier deployable; graceful degradation.
- **Impact & Insight (15%):** converts inaction into a defensible, prioritizable budget decision; "commission-a-study" output is directly actionable.
- **Responsible AI (10%):** uncertainty-first, contested-edge consent, non-individual framing, abstention, drift/recalibration lifecycle.

## Appendix E — Indicative API / Schemas
`POST /scenario {tract_set, defer_years, enabled_edges[], budget?, discount_rate, seed, n_draws}` → `MultiplierResult` + `per_edge_sobol[]` + `audit_id`. `GET /audit/{id}` → `AuditRecord`. `GET /catalog` → edge list with provenance.

## Appendix F — Extensibility (stretch / "what's next")
- **Second domain (C/W):** swap the DAG (e.g., deferred early-childhood program → outcomes) to prove domain-agnosticism.
- **Second region (C/W):** re-target to an Indian city (e.g., using documented synthetic inventory + published priors) for the "global generalization" bonus, with transparent assumption flags.
