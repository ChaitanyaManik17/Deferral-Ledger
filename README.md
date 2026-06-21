# DEFERRAL LEDGER

> *We don't price the lead pipe — we trace the dollars it forces other public budgets to spend later. Every deferred replacement dollar creates an obligation cascade that DEFERRAL LEDGER quantifies as a **distribution**, not a scary single total.*

**Competition:** USAII Global AI Hackathon 2026 — Graduate Track, Brief 6A (Public Systems & Policy: *The Cost of Doing Nothing*)

---

## What It Does

DEFERRAL LEDGER models the downstream public cost of **deferring** a preventive capital investment (e.g., lead-service-line replacement) as an **explicit, citable causal DAG** with probabilistic edge priors. It propagates uncertainty via Monte-Carlo to produce a **deferral-multiplier posterior** — and uses **Sobol sensitivity analysis** to tell decision-makers *which uncertainty is worth buying down first*.

**Output:** `M = PV(Σ downstream obligated $) / deferred $` — as a distribution, never a single point estimate.

---

## Product Scope

| | |
|---|---|
| **In scope** | LSL deferral → childhood lead exposure → cascading public costs |
| **Extensible to** | Any deferred-prevention DAG; second domain / second region (India) as stretch |
| **NOT in scope** | Individual child/household scoring; involuntary intervention justification; funding decisions |

---

## 3 Core Decision Points (HITL)

1. **Replace which tracts this budget year vs defer?** — system ranks by deferral-multiplier-adjusted value with credible bands; the water/finance officer decides.
2. **Which contested causal edges enter the official figure?** — a deliberate, logged human policy choice (e.g., include lead→crime or not).
3. **Which uncertainty to commission a study on?** — the Sobol ranking surfaces the top driver; cross-agency leadership decides where to spend to buy down ignorance.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| DAG engine | NetworkX |
| Monte-Carlo / Sobol | NumPy/SciPy + SALib |
| Data / models | pandas + Pydantic |
| API | FastAPI |
| Dashboard | Streamlit + Plotly |
| Database | PostgreSQL (Neon) / SQLite fallback |
| GPU (optional) | CuPy/RAPIDS with CPU/NumPy fallback |

---

## Quickstart

```bash
git clone https://github.com/ChaitanyaManik17/Deferral-Ledger.git
cd Deferral-Ledger
pip install -r requirements.txt      # or: make setup
python -m pytest -q                  # 57 tests
streamlit run app.py                 # launch the dashboard

# Optional — enable LLM narration of the decision brief (free Google AI Studio key).
# Falls back to a deterministic template if unset/invalid, so the demo never depends on it.
export GEMINI_API_KEY=...            # set in Streamlit → Secrets when deployed
```

---

## Repository Layout

```
Deferral-Ledger/
├── app.py            # Streamlit dashboard (impact, analytics, brief, map, optimizer, governance)
├── api.py            # FastAPI service layer (/scenario, /catalog, /sensitivity, /audit)
├── cascade.py        # Vectorized cost cascade (compute_multiplier / compute_components)
├── montecarlo.py     # Monte-Carlo posterior + scenario compare (now vs defer)
├── sensitivity.py    # Sobol global sensitivity + commission-a-study recommendation
├── validation.py     # Self-validation harness — "how we catch a wrong answer"
├── gates.py          # Abstention gate (FR-ABS-1)
├── brief.py          # Decision brief (deterministic template + optional Gemini narration)
├── optimize.py       # Equity-weighted budget allocator
├── panels.py         # Plotly chart components
├── audit.py          # SQLite audit records + contested-edge consent log
├── catalog.py        # Cited edge-prior loader (build FAILS on any uncited edge)
├── priors.py         # Distribution helpers (point() + samplers)
├── models.py         # Pydantic data contracts
├── synth.py · data_ingest.py   # synthetic generator + cached public data
├── catalog/          # edges.yaml (cited priors) + contested.yaml
└── tests/            # 57 tests
# docs/ (SRS, model card, evidence ledger) are kept locally and not tracked in git.
```

## Responsible AI — how we catch a wrong answer

- **Uncertainty, not false precision** — every output is a distribution with credible intervals; the **abstention gate** refuses a "fund-now" recommendation when the 95% CI of M spans below 1.0.
- **Self-validation harness** (`validation.py`) — intermediate **tripwires**, **literature-range** checks (Lanphear/Grosse), and a **deterministic-vs-Monte-Carlo** cross-check; any failure routes the run to **human review**. The AI never finalizes a flagged decision.
- **Governance** — every run is cited (`catalog.py` rejects uncited edges), versioned, and audit-logged; the stigmatizing **lead→crime** edge is contested and **off by default**, requiring explicit, logged consent.

---

## Authors

Varun Bhandari · Chaitanya Manik · Manush Patel