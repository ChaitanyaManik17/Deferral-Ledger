# DEFERRAL LEDGER — Day 2 Tasks: **CHAITANYA**
### Role: Sobol sensitivity + abstention gate + evaluation harness + uncertainty analytics
*Build team = Chaitanya + Varun (Manush unavailable; full scope via overtime). Day 2 = the Intelligence Core — the 35%-weighted "AI Reasoning" day. Your sensitivity + evaluation work is what proves the reasoning is real. Pair: Varun (cascade refactor + Monte-Carlo engine + API).*

---

## Day-2 goal (shared, you + Varun)
> **Given a tract + scenario, produce the deferral-multiplier *posterior* (mean + 90/95% CIs + P(M>1)), the *Sobol tornado* of which edge drives the spread, and the *abstain-when-CI-spans-M<1* gate** — reproducible by seed, runnable headless.

**Your demoable artifacts:** a **Sobol tornado** ranking the edges by variance contribution (expected: **E1 dominates** → "commission a water-lead study first"), the **abstention gate** firing correctly, and an **evaluation suite** proving the uncertainty + sensitivity behave.

---

## STEP 0 — Joint design lock (do together first, ~45 min) — CRITICAL
Same as Varun's STEP 0. The artifact you most depend on is the shared compute function:
```python
# cascade.py  (Varun builds; you call it)
def compute_multiplier(params: dict[str, np.ndarray], tract, scenario) -> np.ndarray: ...
#   params: edge_id -> array (k,)   →   returns M array (k,)
```
Also lock: (a) the **Sobol parameter-bounds convention** (use each edge's `ci_low`/`ci_high`; triangular → `low`/`high`; fallback ±X%); (b) **abstention semantics** (abstain when 95% CI crosses 1.0); (c) the **exposure/temporal model fix** (Day-1 is linear in `defer_years` and double-counts — agree the defensible cumulative-capped formulation with Varun; you'll document it in the model card).

> **Unblock trick:** if `compute_multiplier` isn't ready when you start C1, develop against a 1-line stub with the agreed signature (e.g., returns a weighted sum of params), then swap to Varun's real function — zero rework if the signature is frozen.

---

## YOUR TASKS (ordered)

### C1 — Sobol global sensitivity (`sensitivity.py`) *(~2.5 h)*
- `sobol_indices(scenario, tract, edges, n_base=1024, seed=42) -> dict`:
  - build a **SALib** problem: `names = enabled edge ids`, `bounds` from the STEP-0 convention (per edge);
  - `saltelli.sample(problem, n_base)` → param matrix; map columns → `params` dict of arrays; call **Varun's `compute_multiplier`** once on the whole matrix (vectorized);
  - `sobol.analyze` → **first-order `S1` and total-order `ST`** per edge;
  - return ranked tornado data `{edge_id: {S1, ST}}`, sorted by `ST`.
- Store the result into `MultiplierResult.sobol` (coordinate field with Varun).
- **DoD:** running on the default scenario returns indices that sum sensibly; the ranking is stable across two seeds; **verify E1 (the deliberately-wide prior) lands at/near the top** — that's the expected, defensible finding.

### C2 — Abstention gate (`gates.py`) *(~45 min)*
- `apply_abstention(result: MultiplierResult) -> MultiplierResult`: set `abstain=True` when `ci95` spans below 1.0 (i.e., `ci95[0] < 1.0`), and attach a short human message ("deferral may not compound here; insufficient evidence to compel funding" — SRS FR-ABS-1). Varun calls this at the end of `run_monte_carlo`.
- **DoD:** unit test — a scenario whose 95% CI spans <1.0 ⇒ `abstain=True`; a clearly-compounding scenario ⇒ `abstain=False`.

### C3 — Evaluation harness (`tests/` + `notebooks/eval.ipynb`) *(~2.5 h)* — this *is* the "evaluation strategy" the rubric asks for
- **EV-3 (CI calibration):** assert CI **width grows** with `defer_years` and **shrinks** with `n_draws`.
- **EV-4 (Sobol recovery):** build a tiny synthetic DAG/catalog with an **injected dominant edge**; assert Sobol ranks it #1 (proves the method, not just the result).
- **EV-6 (abstention):** construct a low-exposure scenario whose CI spans `M<1`; assert the gate fires.
- **MC reproducibility:** same seed ⇒ identical CIs.
- A short notebook that renders the tornado + a fan/histogram of M (seed for Day-3 dashboard charts + the pitch video).
- **DoD:** all four checks pass under `make test`; notebook runs top-to-bottom.

### C4 — "Commission-a-study" analytic (`sensitivity.py`) *(~1 h)* — drives decision point #3
- From the Sobol ranking, emit a structured recommendation: the edge with the highest `ST` = "buying this measurement down reduces decision uncertainty most." Return `{top_driver, ST, plain_language}` for the Day-3 brief.
- **DoD:** for the default scenario it names E1 (water-lead study) as the top study to commission, with its `ST`.

### C5 — Prior-refinement + lifecycle docs *(~1 h)*
- If Sobol shows an edge dominating *only because* its prior is needlessly wide and a citation could tighten it, tighten it (with source + `last_validated`); otherwise document *why* it stays wide (esp. **E1** — keep it wide, that's the point).
- Update `docs/edge_evidence_ledger.md` + `docs/model_card.md` with: the Day-2 exposure-model assumption (from STEP 0), the abstention rule, and the sensitivity finding.
- **DoD:** ledger/model-card reflect the Day-2 state; every prior still cited (EV-1 intact).

### C6 — Ranking-stability check (`tests/`, STRETCH) *(~45 min)* — FR-SENS-3
- Perturb each prior's spread ±20%; assert the top-1/top-2 Sobol driver is stable. Report it as a robustness result for the submission.

---

## Contracts you PRODUCE (others depend on)
- `sensitivity.sobol_indices` → **Varun's API `/sensitivity`** + the Day-3 tornado chart + the brief.
- `gates.apply_abstention` → **Varun's `run_monte_carlo`** calls this.
- The "commission-a-study" object + the eval notebook → Day-3 brief + pitch video.

## Contracts you CONSUME (from Varun)
- `cascade.compute_multiplier` (the linchpin — freeze signature in STEP 0; stub it if not ready).
- `montecarlo.run_monte_carlo` output (to test the abstention gate end-to-end).

## Definition of Done — Chaitanya (Day 2)
- [ ] `sobol_indices` returns ranked S1/ST; E1 verified near top; stable across seeds.
- [ ] `apply_abstention` gate + passing unit test.
- [ ] Eval suite EV-3 / EV-4 / EV-6 + MC reproducibility green; eval notebook runs.
- [ ] "Commission-a-study" analytic naming the top driver.
- [ ] Ledger + model card updated (exposure assumption, abstention rule, sensitivity finding); EV-1 intact.

## Risks / notes
- **Saltelli sampling explodes eval count** (`N·(2D+2)`). Keep `n_base` modest (e.g., 512–1024) and rely on Varun's **vectorized** `compute_multiplier` — if it's not vectorized, flag it immediately (it's his V1 DoD).
- Sobol bounds must bracket the realistic range, not the full sampling tail — use `ci_low/ci_high`, not ±5σ, or the indices get dominated by implausible extremes.
- Keep **E6/E7 OFF** for the default sensitivity run; offer a separate "with contested edges" Sobol only behind the consent flag (matches the governance design).
- The headline isn't a number — it's **"here's the uncertainty, here's which edge drives it, here's the study to buy."** That framing is what wins the 35%.
