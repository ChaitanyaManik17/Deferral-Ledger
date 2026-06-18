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
make setup        # create venv + install deps
make test         # run test suite
make run          # launch dashboard (Day 3+)
```

---

## Repository Layout

```
Deferral-Ledger/
├── catalog/
│   ├── edges.yaml          # Edge-prior catalog (cited distributions)
│   └── contested.yaml      # Contested-edge registry + default enabled set
├── docs/
│   ├── model_card.md       # Model Card (LC-4)
│   └── edge_evidence_ledger.md  # Appendix-B evidence ledger
├── tests/
│   └── test_catalog.py     # Catalog validation tests
├── models.py               # Pydantic data models
├── catalog.py              # Catalog loader + validator
├── priors.py               # Distribution helper (point() + samplers)
├── pyproject.toml
├── Makefile
└── README.md
```

---

## Authors

Varun Bhandari · Chaitanya Manik · Manush Patel