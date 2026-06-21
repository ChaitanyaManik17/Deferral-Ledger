"""
validation.py — Self-validation / failure-catching harness (Tier 1).

Answers the mentor question: "If the AI gives a wrong answer, how would you catch it?"
Every result runs three independent self-checks; any failure routes the run to a
HUMAN review (the AI never finalizes a flagged decision):

  1. Output sanity tripwire — M finite, non-negative, and within a plausibility bound.
  2. Literature-range check — the run's implied per-child intermediates (BLL increment,
     IQ loss, lifetime-earnings $) must fall within published plausible ranges
     (Lanphear 2005; Grosse 2021). Out-of-range ⇒ the model is extrapolating implausibly.
  3. Internal cross-check — the deterministic point M must broadly agree with the
     Monte-Carlo mean (catches sampling / code regressions).
"""

from __future__ import annotations

import math

import numpy as np

from cascade import compute_components
from models import EdgePrior, MultiplierResult, ScenarioRun, Tract
from priors import point

# Published plausible ranges for single-pathway, per-child intermediates.
# Deliberately generous sanity limits — exceeding them means the model is
# extrapolating beyond what the source studies support.
#   key: (low, high, unit/explanation)
LIT_RANGES: dict[str, tuple[float, float, str]] = {
    "bll_increment_per_child": (0.0, 10.0, "µg/dL (dose-response flattens / is capped above 10)"),
    "iq_loss_per_child": (0.0, 15.0, "IQ points (Lanphear 2005 slope on a single LSL pathway)"),
    "earnings_per_child": (0.0, 250_000.0, "USD lifetime, 3% discount (Grosse 2021)"),
}
M_SANITY_MAX = 50.0  # an obligation multiplier above ~50x is implausible → human review


def _level(value: float, lo: float, hi: float) -> str:
    """ok / warn (approaching bound) / fail (outside bound)."""
    if value < lo or value > hi:
        return "fail"
    if value > hi - 0.10 * (hi - lo):  # within 10% of the upper bound
        return "warn"
    return "ok"


def validate_result(
    result: MultiplierResult,
    tract: Tract,
    scenario: ScenarioRun,
    edges: list[EdgePrior],
) -> dict:
    """Run the three self-checks and return a structured verdict."""
    checks: list[dict] = []

    # Deterministic intermediates (point estimates) via the shared cascade math.
    point_params = {e.id: np.array([point(e)]) for e in edges}
    comp = compute_components(point_params, tract, scenario)

    # 1 + 2. Per-child intermediates vs literature ranges
    for key, (lo, hi, unit) in LIT_RANGES.items():
        v = float(comp[key][0])
        checks.append({
            "name": f"{key} within literature range",
            "level": _level(v, lo, hi),
            "detail": f"{v:,.2f} {unit} (plausible {lo:g}–{hi:g})",
        })

    # 1. Output sanity tripwire on M
    m_point = result.multiplier_point
    m_mean = result.multiplier_mean
    m_for_check = m_mean if m_mean is not None else m_point
    if m_for_check is None or math.isnan(m_for_check) or m_for_check < 0:
        checks.append({"name": "M finite & non-negative", "level": "fail", "detail": f"M={m_for_check}"})
    elif m_for_check > M_SANITY_MAX:
        checks.append({"name": "M within sanity bound", "level": "fail",
                       "detail": f"M={m_for_check:.2f} exceeds {M_SANITY_MAX:g}x"})
    else:
        checks.append({"name": "M within sanity bound", "level": "ok",
                       "detail": f"M={m_for_check:.2f} ≤ {M_SANITY_MAX:g}x"})

    # 3. Internal cross-check: deterministic point vs Monte-Carlo mean
    if m_mean is not None:
        denom = max(abs(m_mean), 1e-9)
        rel = abs(m_mean - m_point) / denom
        lvl = "ok" if rel <= 0.5 else ("warn" if rel <= 2.0 else "fail")
        checks.append({"name": "deterministic vs Monte-Carlo agreement", "level": lvl,
                       "detail": f"point={m_point:.2f}, mean={m_mean:.2f} (rel diff {rel:.0%})"})

    fails = sum(1 for c in checks if c["level"] == "fail")
    warns = sum(1 for c in checks if c["level"] == "warn")
    needs_review = fails >= 1 or warns >= 2

    return {
        "status": "review" if needs_review else "ok",
        "needs_human_review": needs_review,
        "summary": (
            f"{fails} failed, {warns} warning(s) — routed to human review"
            if needs_review else "All self-checks passed"
        ),
        "checks": checks,
    }
