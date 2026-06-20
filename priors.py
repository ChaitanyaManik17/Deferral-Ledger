"""
priors.py — Distribution helper for Deferral Ledger edge priors.

Provides:
  - point(edge)              → deterministic central value (used by Day-1 DAG run)
  - to_distribution(edge)    → scipy / numpy sampler (used by Day-2 Monte-Carlo)

Consumed by:
  - Varun's dag.py (point() for deterministic Day-1 run)
  - C-MC propagation layer (to_distribution() samplers for Monte-Carlo)
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
from scipy import stats

if TYPE_CHECKING:
    from models import EdgePrior


# ── point() ───────────────────────────────────────────────────────────────────

def point(edge: EdgePrior) -> float:
    """
    Return the single deterministic central value for the edge prior.

    Used by Varun's dag.py for the Day-1 deterministic (non-stochastic) run.
    The convention per dist_type is:

      normal     → mean
      lognormal  → exp(mu)  (median of the log-normal)
      triangular → mode
      uniform    → (low + high) / 2
      point      → value

    Args:
        edge: A validated EdgePrior model instance.

    Returns:
        The central value as a float.

    Raises:
        ValueError: If the dist_type is unrecognised (shouldn't happen after
                    Pydantic validation, but kept as a safety net).
    """
    p = edge.params
    match edge.dist_type:
        case "normal":
            return float(p["mean"])
        case "lognormal":
            # Median of a log-normal = exp(mu)
            return float(math.exp(p["mu"]))
        case "triangular":
            return float(p["mode"])
        case "uniform":
            return float((p["low"] + p["high"]) / 2.0)
        case "point":
            return float(p["value"])
        case _:
            raise ValueError(f"Unknown dist_type '{edge.dist_type}' for edge '{edge.id}'")


# ── to_distribution() ─────────────────────────────────────────────────────────

def to_distribution(edge: EdgePrior) -> Callable[[int], np.ndarray]:
    """
    Return a sampler function for the edge prior.

    The sampler takes `n_samples: int` and returns a 1-D np.ndarray of shape (n,).
    Used by the Day-2 Monte-Carlo propagation layer.

    Samplers are backed by scipy.stats frozen distributions or NumPy random
    generators, seeded externally (the caller controls the RNG seed).

    Args:
        edge: A validated EdgePrior model instance.

    Returns:
        A callable `sample(n: int) -> np.ndarray`.
    """
    p = edge.params

    match edge.dist_type:
        case "normal":
            dist = stats.norm(loc=p["mean"], scale=p["sd"])
            return lambda n, _d=dist: _d.rvs(n)

        case "lognormal":
            # scipy lognorm: shape=sigma, scale=exp(mu)
            dist = stats.lognorm(s=p["sigma"], scale=math.exp(p["mu"]))
            return lambda n, _d=dist: _d.rvs(n)

        case "triangular":
            low, mode, high = p["low"], p["mode"], p["high"]
            if not (low <= mode <= high):
                raise ValueError(
                    f"Edge '{edge.id}': triangular params require low ≤ mode ≤ high, "
                    f"got ({low}, {mode}, {high})"
                )
            # scipy triang: c=(mode-low)/(high-low), loc=low, scale=high-low
            span = high - low
            c = (mode - low) / span if span > 0 else 0.0
            dist = stats.triang(c=c, loc=low, scale=span)
            return lambda n, _d=dist: _d.rvs(n)

        case "uniform":
            low, high = p["low"], p["high"]
            dist = stats.uniform(loc=low, scale=high - low)
            return lambda n, _d=dist: _d.rvs(n)

        case "point":
            val = float(p["value"])
            return lambda n, _v=val: np.full(n, _v)

        case _:
            raise ValueError(f"Unknown dist_type '{edge.dist_type}' for edge '{edge.id}'")


# ── ci_to_sd() ────────────────────────────────────────────────────────────────

def ci_to_sd(ci_low: float, ci_high: float, z: float = 1.96) -> float:
    """
    Convert a two-sided confidence interval to a Normal standard deviation.

    Convention: sd ≈ (ci_high - ci_low) / (2 * z)
    For a 95% CI, z = 1.96 → sd ≈ (hi - lo) / 3.92.
    For a 95% CI via the 3.29 rule (half-range / 1.645): use z=1.645.

    The task doc suggests sd ≈ (ci_high - ci_low) / 3.29 which corresponds
    to z ≈ 1.645 (one-tailed 95th percentile), i.e. treating the interval as
    ±1.645σ. We default to the two-tailed z=1.96 but expose z as a parameter.

    Args:
        ci_low:  Lower bound of the confidence interval.
        ci_high: Upper bound of the confidence interval.
        z:       The z-score corresponding to the CI half-width.

    Returns:
        Estimated standard deviation.
    """
    return (ci_high - ci_low) / (2.0 * z)
