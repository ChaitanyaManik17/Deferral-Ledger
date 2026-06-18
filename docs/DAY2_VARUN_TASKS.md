# DEFERRAL LEDGER — Day 2 Tasks: **VARUN**
### Role: Monte-Carlo engine + cascade refactor + scenario compare + API (the compute core)
*Build team = Varun + Chaitanya (Manush unavailable; full scope via overtime). Day 2 = the Intelligence Core — this is the 35%-weighted "AI Reasoning" day. Pair: Chaitanya (Sobol sensitivity + abstention + evaluation).*

---

## Day-2 goal (shared, you + Chaitanya)
> **Given a tract + scenario, produce the deferral-multiplier *posterior* (mean + 90/95% CIs + P(M>1)), the *Sobol tornado* of which edge drives the spread, and the *abstain-when-CI-spans-M<1* gate** — reproducible by seed, runnable headless, and ideally exposed via an API endpoint.

**Demoable artifact:** `python -m run --tract T1 --defer 5 --mc` prints the multiplier **distribution** (not a point), the abstain flag, and the top sensitivity driver — same seed ⇒ identical output.

---

## STEP 0 — Joint design lock (do together first, ~45 min) — CRITICAL
Day-1 `dag.evaluate()` works but hardcodes the math on point estimates. Lock these 5 decisions before splitting:

1. **The one compute function both of you call** — agree this signature:
   ```python
   # cascade.py
   def compute_multiplier(
       params: dict[str, np.ndarray],   # edge_id -> array of shape (k,)  (k=1 for point, k=N for MC, k=Saltelli-N for Sobol)
       tract: Tract,
       scenario: ScenarioRun,
   ) -> np.ndarray:                      # returns multiplier M, shape (k,)
       ...
   ```
   This single vectorized function powers **deterministic, Monte-Carlo, AND Sobol**. It is the day's linchpin — Chaitanya's Sobol (C1) consumes it.
2. **Fix the exposure/temporal model (the 35% lever).** Day-1 uses `bll_increment_per_child = defer_years × factor`, which double-counts cumulative IQ/earnings loss. Decide the defensible formulation, e.g.: model **person-years of exposure** over the deferral window; treat per-child IQ/earnings loss as a **one-time cumulative** effect of the BLL elevation sustained during deferral (cap it), not a fresh full hit每 year. Document the assumption explicitly (judges reward this).
3. **Sobol parameter bounds convention** (so C1 can start): use each edge's `ci_low`/`ci_high`; for triangular use `low`/`high`; fallback ±X% — agree the rule.
4. **Abstention semantics:** `abstain=True` when the 95% CI crosses 1.0 (Chaitanya owns the gate fn; you wire it into the MC result).
5. **Who populates which `MultiplierResult` field** (you: MC fields; Chaitanya: `sobol`, `abstain`).

---

## YOUR TASKS (ordered)

### V1 — Extract the vectorized cascade (`cascade.py`) *(~2.5 h, linchpin)*
- Move the per-path math out of `dag.evaluate()` into `compute_multiplier(params, tract, scenario)` per the STEP-0 signature. Must:
  - compute the denominator `$D = lines_count × E0`;
  - run paths E1→E2→E3 (earnings), E1→E4 (sped), E1→E5 (healthcare), E1→E6 (CVD via the **VSL conversion** currently in `dag.py`), E1→E7 (crime via the **incarceration conversion**) — **move those conversion constants** (`VSL_USD`, `CVD_BASELINE_RISK`, `INCARCERATION_COST_USD`, `CRIME_BASELINE_RATE`) into `cascade.py` so MC and Sobol use identical math;
  - respect `scenario.enabled_edges` (missing/disabled edge ⇒ that path contributes 0);
  - be fully **vectorized over the array axis** (no Python loops over draws).
- **Refactor `dag.evaluate()` to call `compute_multiplier` with length-1 arrays** so the Day-1 deterministic path + `tests/test_dag_spine.py` stay green (regression guard).
- **DoD:** `compute_multiplier` returns identical point value to Day-1 for the same inputs; existing tests pass.

### V2 — Defensible exposure/temporal model *(~1.5 h)*
- Implement the STEP-0 exposure decision (person-years; cumulative-capped per-child loss; per-year discounting within the deferral window). Keep it a clearly-named, documented function inside `cascade.py`.
- **DoD:** doubling `defer_years` no longer linearly doubles per-child lifetime loss in a way that double-counts; the assumption is documented in a docstring + `docs/model_card.md` note (coordinate with Chaitanya).

### V3 — Monte-Carlo engine (`montecarlo.py`) *(~2 h)*
- `run_monte_carlo(scenario, tract, edges, n_draws=10_000, seed=42) -> MultiplierResult`:
  - build a **seeded** `np.random.default_rng(seed)`; sample each enabled edge via `priors.to_distribution(edge)` (pass the rng / set scipy seed for reproducibility);
  - assemble `params = {edge_id: samples}`, call `compute_multiplier`, get the M array;
  - populate `multiplier_mean`, `ci90`, `ci95` (np.percentile 5/95 and 2.5/97.5), `p_gt_1 = mean(M > 1)`; keep `multiplier_point` from the deterministic path.
- **Reproducibility (C-5):** same `seed` ⇒ identical CIs (assert in a test).
- Call Chaitanya's `gates.apply_abstention(result)` before returning.
- **DoD:** `--mc` flag in `run.py` prints mean + 90/95 CI + P(M>1) + abstain.

### V4 — Scenario compare (`montecarlo.py::compare`) *(~1 h)*
- `compare(now_vs_defer)` → run MC for `defer_years=0` and `defer_years=Δ`, return both distributions + the **PV cost delta** with a band (FR-SCN-1).
- **DoD:** returns a small struct the dashboard/brief can render.

### V5 — FastAPI skeleton (`api.py`) *(~1.5 h, pulls Day-3 forward)*
- Endpoints returning JSON: `POST /scenario` (body→`ScenarioRun`)→`MultiplierResult`; `GET /catalog`→edge list w/ provenance; `GET /sensitivity`→Sobol; `GET /audit/{id}`. Wire to `run_monte_carlo` + Chaitanya's `sobol_indices`.
- **DoD:** `uvicorn api:app` serves `/scenario` returning a valid `MultiplierResult`; matches `samples/multiplier_result.example.json` shape.

### V6 — GPU path (`cascade.py`, STRETCH) *(if ahead)*
- Optional CuPy backend for `compute_multiplier` (NumPy fallback mandatory; results match within MC tolerance). Demonstrates the GPU-Monte-Carlo scope item.

### V7 — Cleanups + reproducibility test *(~45 min)*
- Fix `created_at` (drop the stray `Z` on the already-tz-aware ISO string); set `catalog_version` dynamically (git SHA or `edges.yaml` hash).
- `tests/test_montecarlo.py`: seed reproducibility + CI-width sanity (wider for larger `defer_years`).
- **DoD:** tests green; `make test` clean.

---

## Contracts you PRODUCE (others depend on)
- `cascade.compute_multiplier` → **Chaitanya's Sobol (C1) + abstention/eval** call this. Freeze its signature in STEP 0 and don't change it without telling him.
- `run_monte_carlo` / `compare` / `api.py` endpoints / MC-populated `MultiplierResult`.

## Contracts you CONSUME
- `priors.to_distribution` + `ci_to_sd` (samplers) · `catalog.default_enabled_edges` / `get_edge` · **`gates.apply_abstention(result)`** (Chaitanya, C2) — until ready, leave a no-op stub and swap in.

## Definition of Done — Varun (Day 2)
- [ ] `compute_multiplier` extracted, vectorized, Day-1 regression tests green.
- [ ] Exposure/temporal model fixed + documented.
- [ ] `run_monte_carlo` → posterior (mean, 90/95 CI, P(M>1)); reproducible by seed.
- [ ] Scenario compare (now vs defer) with PV delta.
- [ ] FastAPI `/scenario` serves a valid `MultiplierResult`.
- [ ] Cleanups + MC tests green.

## Risks / notes
- **Vectorize from the start** — if `compute_multiplier` loops over draws, Sobol (Saltelli ⇒ many thousands of evals) and the GPU path both suffer. Keep all paths as array ops.
- Keep the deterministic path alive (it's the regression oracle + the demo fallback if MC misbehaves).
- E6/E7 stay **off by default**; MC/Sobol only include them when explicitly enabled (don't let a sampler touch a disabled edge).
