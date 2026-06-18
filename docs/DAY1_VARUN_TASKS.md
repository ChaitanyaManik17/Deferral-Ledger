# DEFERRAL LEDGER — Day 1 Tasks: **VARUN**
### Role: Data layer + Causal-DAG engine (the "spine")
*Build team is just **Varun + Chaitanya** — Manush is unavailable for the entire build, so the two of you absorb his UI/deploy work and **carry the FULL scope via overtime — nothing is cut**. Day 1 = Foundations: the quantitative spine (no UI today anyway). Pair: Chaitanya (edge-prior catalog).*

---

## Day-1 goal (shared, you + Chaitanya)
> **A causal DAG loads from Chaitanya's cited edge-prior catalog and runs on your synthetic + cached public data, producing a single *deterministic* deferral-multiplier for one tract.** (No Monte-Carlo yet — that's Day 2. Today proves the spine end-to-end.)

**Your end-of-day demoable artifact:** a CLI command
`python -m deferral_ledger.run --tract T1 --defer 5` → prints a deterministic multiplier `M` + per-edge contribution, reading the synthetic data **and** Chaitanya's `catalog/edges.yaml`.

---

## STEP 0 — Joint kickoff (do together first, ~90 min, BEFORE splitting)
These unblock both of you; don't start solo work until these are agreed:
1. **Lock scope / non-goals / the 3 decision points** (copy from the SRS §8, §11) into `README.md`.
2. **Agree the DAG node/edge list** (the cascade structure) — this is the shared artifact you both depend on. Draw it on a whiteboard; Chaitanya turns it into `catalog/edges.yaml`, you turn it into `dag.py`.
3. **Freeze the data contracts** (the Pydantic models below) — so Day 2 + Manush's UI are unblocked.
4. **Agree repo layout + tooling** (below).

---

## Repo layout (scaffolding owned by **Chaitanya** — see C0; the per-module tags below still apply to you)
```
deferral-ledger/
  pyproject.toml                 # deps + tooling
  README.md                      # scope, non-goals, 3 decision points, run steps
  data/raw/                      # cached public datasets + provenance.json   (YOU)
  data/synthetic/                # generated synthetic inventory + seed        (YOU)
  catalog/edges.yaml             # edge-prior catalog                          (Chaitanya)
  catalog/contested.yaml         # contested-edge registry                     (Chaitanya)
  src/deferral_ledger/
    models.py                    # Pydantic contracts                          (YOU)
    data_ingest.py               # C-DATA: cached public data + provenance      (YOU)
    synth.py                     # C-DATA: synthetic generator                  (YOU)
    catalog.py                   # catalog loader + validation                  (Chaitanya)
    priors.py                    # point+CI -> distribution params/samplers     (Chaitanya)
    dag.py                       # C-DAG engine: build, acyclicity, cascade     (YOU)
    run.py                       # CLI deterministic spine                      (YOU)
  samples/multiplier_result.example.json   # contract sample for Manush's UI   (YOU)
  tests/test_dag_spine.py        # (YOU)   tests/test_catalog.py (Chaitanya)
```

---

## YOUR TASKS (ordered)

### V1 — (Repo scaffolding MOVED to Chaitanya — see his **C0**)
- Repo init, `pyproject.toml`, tooling, README skeleton, `Makefile` are now **Chaitanya's** Day-1 first task.
- **Your dependency:** wait for his repo push, then start **V2**. If it isn't up within the first hour, ping him / pair on it — both of you are blocked until it exists. You can sketch `models.py` and the DAG node/edge list (STEP 0) on paper meanwhile.

### V2 — Define the shared data contracts (`models.py`) *(~45 min)*
Implement Pydantic models (agreed in STEP 0). Day-1 fields marked; MC fields nullable today.
```python
class Tract(BaseModel):
    geoid: str; lines_count: int; children_under6: int
    svi_percentile: float; has_inventory_flag: bool; synthetic: bool = True

class EdgePrior(BaseModel):            # produced by Chaitanya's catalog, validated here
    id: str; from_node: str; to_node: str
    dist_type: Literal["normal","lognormal","triangular","uniform","point"]
    params: dict; point_estimate: float
    ci_low: float | None; ci_high: float | None
    source: str; effect_size: str; units: str
    contested: bool = False; enabled: bool = True; last_validated: str  # ISO date

class ScenarioRun(BaseModel):
    id: str; tract_id: str; defer_years: int; discount_rate: float = 0.03
    enabled_edges: list[str]; seed: int = 42; n_draws: int = 1   # n_draws=1 today

class MultiplierResult(BaseModel):
    run_id: str; tract_id: str; defer_years: int; discount_rate: float
    multiplier_point: float                         # Day 1 deterministic
    per_edge_contribution: dict[str, float]         # Day 1
    multiplier_mean: float | None = None            # Day 2 (MC)
    ci90: tuple[float,float] | None = None
    ci95: tuple[float,float] | None = None
    p_gt_1: float | None = None
    abstain: bool = False                           # Day 2 gate
    sobol: dict | None = None                       # Day 2
    enabled_edges: list[str] = []
    catalog_version: str; seed: int; created_at: str
```
- Export a `samples/multiplier_result.example.json` (hand-filled) — this is the contract the **Day-3 dashboard (which you/Chaitanya now build) will render**; freezing it now makes wiring the UI trivial.
- **DoD:** models import; example JSON validates against `MultiplierResult`.

### V3 — Data ingestion + provenance (`data_ingest.py`) *(~75 min)*
- Pull & **cache** the minimum public data for ONE demo county into `data/raw/`:
  - EPA replacement-cost figure(s) [avg $4,700; range $1,200–$12,300] — can be a small static file.
  - CDC EPHT blood-lead **aggregate** via the EPHT JSON API (county/state level).
  - CDC PLACES + CDC/ATSDR SVI for the demo county tracts.
- Write `data/raw/provenance.json`: for each source `{name, url, retrieved_at, version}` (SRS DR-11).
- **No PII** — aggregates only (SRS C-1/DR-10).
- **DoD:** a `load_county(geoid)` function returns clean DataFrames; `provenance.json` populated.

### V4 — Synthetic generator (`synth.py`) — *the primary demo data path* *(~75 min)*
- Generate reproducible (seeded) synthetic **tracts** calibrated to the cached aggregates: `lines_count`, `children_under6`, `svi_percentile`, `has_inventory_flag`. Label every record `synthetic=True`.
- Make `has_inventory_flag` partly False on purpose → carry the **"unknown service-line material" share** as a first-class field (SRS FR-ING-4 — the 9M→4M instability is the headline).
- Write outputs + the seed to `data/synthetic/`.
- **DoD:** `generate_tracts(n, seed)` → list[`Tract`]; same seed ⇒ identical output (reproducibility, SRS C-5).

### V5 — Causal-DAG engine (`dag.py`) *(~90 min)*
- Build a `networkx.DiGraph` from Chaitanya's `catalog/edges.yaml`; **validate acyclicity** (fatal error on cycle — SRS DR-14).
- Implement a **deterministic single-draw cascade evaluator**: walk the DAG using each edge's `point_estimate`, combine with a scenario `{tract, defer_years, discount_rate}` and the synthetic exposure (defer_years × children × BLL-increment edge) to compute:
  - deferred dollars `$D = lines_count × cost_per_line`
  - downstream PV cost per enabled edge → **deferral multiplier `M = PV(Σ downstream) / $D`**
  - `per_edge_contribution` (how much each edge adds) — sets up Day-2 Sobol.
- Respect `enabled` flags (contested edges OFF unless enabled).
- **DoD:** `evaluate(scenario, tracts, catalog) -> MultiplierResult` (point only).

### V6 — CLI spine + smoke test (`run.py`, `tests/test_dag_spine.py`) *(~45 min)*
- `python -m deferral_ledger.run --tract T1 --defer 5` → prints `M`, `$D`, and `per_edge_contribution`.
- One pytest: a known synthetic tract + a tiny fixed catalog ⇒ expected `M` (deterministic).
- **DoD:** CLI runs end-to-end on synthetic data + Chaitanya's catalog; test green.

---

## Contracts you PRODUCE (others depend on these)
- `models.py` (everyone) · `MultiplierResult` + `samples/*.json` (the **Day-3 Streamlit dashboard**) · `Tract` + synthetic data (Chaitanya's loader sanity-checks against it) · `dag.py.evaluate()` (Day-2 Monte-Carlo wraps this).

> **2-person ownership (Days 2–4) — FULL scope retained via overtime:** Varun = data/sim/DAG/Monte-Carlo **+ GPU path + budget optimizer** + FastAPI + deploy. Chaitanya = catalog/priors/Sobol + RAG brief + eval **+ second-region data**. The **Day-3 dashboard is co-owned** (Chaitanya leads analytics/brief panels; you wire data + deploy + the tract map). **Stretch items stay IN-SCOPE** — GPU Monte-Carlo, budget optimizer, tract map, second region (India). They're how we still ship the full vision short-handed. Detailed split in the Day-3 deep-dive.

## Contracts you CONSUME (wait on Chaitanya)
- `catalog/edges.yaml` + `priors.py` (the cited edge priors). **Mitigation if he's mid-flight:** code `dag.py` against a 3-edge stub catalog you write, then swap to his file — agree the YAML keys in STEP 0 so the swap is trivial.

## Definition of Done — Varun (Day 1)
- [ ] Repo + tooling runs on clean clone (`make setup/test/run`).
- [ ] `models.py` contracts + validating `samples/multiplier_result.example.json`.
- [ ] Cached public data + `provenance.json`.
- [ ] Reproducible synthetic tract generator (seeded).
- [ ] DAG engine: builds, validates acyclicity, deterministic multiplier.
- [ ] CLI prints `M` for one tract reading Chaitanya's catalog; smoke test green.

## Risks / notes
- Keep the deterministic evaluator **structured so Day-2 only swaps `point_estimate` → N sampled draws** (vectorize over draws later). Don't hardcode point-math in a way that blocks vectorization.
- Time-box ingestion (V3): if an API is slow, cache a static CSV and note it in `provenance.json` — the synthetic path (V4) is what the demo runs on anyway.
