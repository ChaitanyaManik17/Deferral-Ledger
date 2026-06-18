# Model Card — DEFERRAL LEDGER
**Version:** 0.1.0 (Day 1 baseline, June 2026)
**Authors:** Chaitanya Manik · Varun Bhandari · Manush Patel
**Competition:** USAII Global AI Hackathon 2026 — Graduate Track, Brief 6A

---

## 1. Intended Use

### What this system does
DEFERRAL LEDGER estimates the **cross-system, downstream public cost of deferring a preventive capital investment** — specifically, lead service line (LSL) replacement. It models the causal cascade from deferred infrastructure spending to downstream public obligations (healthcare, special education, lifetime earnings loss) as a **probability distribution**, not a point estimate.

The key output is the **Deferral Multiplier M**: the present value of incremental downstream obligated dollars caused by deferral, divided by the deferred replacement cost. `M > 1` means deferral compounds cost.

### Intended users
- **City water / finance officers** evaluating replace-vs-defer decisions by neighborhood/budget cycle.
- **Cross-agency leadership** (health + education + finance) identifying which uncertainty to commission a study on.
- **Data / QI analysts** validating or recalibrating edge priors.
- **Internal policy teams** (consented) evaluating contested edge scenarios.

### Intended use conditions
- Input data: population-level / aggregate only. No individual-level data.
- Output: distributional estimate (mean, median, 90%/95% CI) with abstention gate.
- Decision: human-made. The system informs, never decides.

---

## 2. Data

### Training / calibration data
DEFERRAL LEDGER does not use machine learning training data. It uses **literature-sourced prior distributions** for each causal edge, transcribed from peer-reviewed studies (see `docs/edge_evidence_ledger.md` and `catalog/edges.yaml`).

### Input data
| Source | Description | Status |
|--------|-------------|--------|
| EPA LCRI fact sheet | Replacement cost per LSL | Public; cached |
| CDC childhood BLL surveillance | Aggregate BLL prevalence | Public aggregates |
| CDC EPHT API | Environmental health tracking indicators | Public JSON API |
| CDC/ATSDR SVI 2022 | Social vulnerability index | Public; cached |
| EPA EJScreen | Environmental justice overlay | Public mirror |
| **Synthetic generator** | Block-level LSL inventory + child cohort | Generated; labeled SYNTHETIC |

### Data constraints
- **No real person-level data is used.** All person-level inputs are synthetic or public aggregates (SRS C-1, DR-10).
- Every dataset load records source URL + retrieval timestamp + version (DR-11).
- Synthetic data is labeled throughout the UI (DR-12).

---

## 3. Causal DAG & Edge Priors

The system models the following causal cascade:

```
Defer Δyr  ──▶  deferred $ = lines × cost_per_line     [E0]
Defer Δyr  ──▶  continued exposure (child person-years) [structural]
exposure   ──▶  sustained BLL increment (µg/dL)         [E1]
BLL        ──▶  IQ loss                                 [E2]
IQ loss    ──▶  lifetime earnings loss                  [E3]
BLL        ──▶  special-education cost                  [E4]
BLL        ──▶  childhood healthcare / Medicaid cost    [E5]
BLL (adult)──▶  cardiovascular / CKD cost (secondary)   [E6, off by default]
BLL        ──▶  behavioral → crime cost (contested)     [E7, off by default]
```

Each edge is a **parametric probability distribution** sourced from named peer-reviewed literature. Full citations in `docs/edge_evidence_ledger.md`.

---

## 4. Key Assumptions

1. **Causal structure is assumed, not proven.** The DAG is a modeling decision. The product's value is *transparency + uncertainty*, not a claim of ground-truth causality (SRS A-3).
2. **Effects are modeled as linear in BLL.** The Lanphear 2005 slope is applied linearly for most calculations; the steeper low-level slope (<10 µg/dL) is available as a sensitivity scenario.
3. **Discount rate defaults to 3%** (per SRS, following Grosse et al. 2021). Users can adjust.
4. **Inventory counts are uncertain** — the EPA revised the national LSL count from ~9M to ~4M on 25 Nov 2025 [R1, R2]. This instability is surfaced as a first-class input, not silently imputed.
5. **E1 (LSL→BLL) has a deliberately wide prior** — this is the hinge of the cascade and has the weakest empirical grounding at the tract level. Day-2 Sobol analysis is expected to show E1 dominates the spread.

---

## 5. Non-Goals (Hard Limits)

> These are architectural non-goals, not just disclaimers.

- ❌ **NOT** a tool that scores, predicts, or ranks outcomes for any individual child, household, or address.
- ❌ **NOT** a justification engine for involuntary intervention or coercive action.
- ❌ **NOT** the entity that allocates the budget — it informs a human decision.
- ❌ **NOT** a claim of definitive causality. The causal structure is a transparent modeling assumption.
- ❌ **NOT** safe for use with real person-level data.

---

## 6. Abstention Conditions

The system **MUST NOT** output a "must-fund-now" recommendation when:

| Condition | Response |
|-----------|----------|
| 95% CI of M spans below 1.0 | Abstain: "Deferral may not compound here; insufficient evidence to compel funding." (SRS FR-ABS-1) |
| A driving edge's prior is stale (past validity window) | Flag as stale; prompt recalibration (SRS LC-1, LC-2) |
| Inventory data is marked synthetic with no real data available | Label outputs SYNTHETIC throughout |
| Contested edge enabled without logged consent | Block output; require explicit consent event |

---

## 7. Limitations

- **Edge E1 (LSL→BLL) is the weakest link.** The water-lead-to-BLL relationship at the tract level is highly variable and poorly characterized in the literature. The wide Triangular prior (0.5–4.0 µg/dL) is intentional and honest.
- **Long-horizon effects (E6, E3) require discount-rate sensitivity.** Results depend on the discount rate assumption.
- **Cost estimates in USD; 2024–2026 vintage.** Inflation adjustments for older studies (Gould 2009, Trasande 2011) are documented in the edge catalog but carry uncertainty.
- **Geographic generalizability is limited.** The model is calibrated to US conditions. A second-region extension (e.g., India) would require new edge priors.
- **LLM brief is narrative only.** The language model narrates C-MC outputs; it never generates or modifies numbers. If unavailable, a templated brief is produced (SRS FR-EXP-3).

---

## 8. Responsible AI Guardrails

| Risk | Mitigation |
|------|------------|
| Deficit framing of disadvantaged neighborhoods | Contested edges (crime, behavioral) OFF by default; consent + audit log required to enable (RAI-1) |
| Over-claiming harm (falsely large M) | Every output includes credible intervals; abstention gate for M<1 (RAI-2) |
| Individual-level inference | Multipliers reported only as population-level budget obligations, never individual risk (RAI-3) |
| Spurious precision from unstable inventory | Inventory uncertainty (9M→4M) is a first-class input (RAI-4) |
| LLM hallucinating numbers | LLM only narrates; numbers come from C-MC only; templated fallback always available (RAI-5) |

---

## 9. Lifecycle & Recalibration

- Each edge carries a `last_validated` date. Edges past their validity window are flagged as **stale** in the UI (LC-1).
- A revision to the upstream inventory count or a superseding dose-response meta-analysis marks dependent edges stale and prompts recalibration (LC-2).
- Drift monitor (Day 3+): compare predicted vs observed BLL trends; widen uncertainty when divergence exceeds threshold (LC-3).
- All runs are reproducible from `{seed, catalog_version, inputs_snapshot}` (NFR-REPRO-1).

---

*This model card was generated as part of the Day 1 deliverable (C6) per `DAY1_CHAITANYA_TASKS.md`. It will be updated as the system evolves through Days 2–7.*
