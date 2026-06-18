"""
sensitivity.py — Sobol global sensitivity analysis for Deferral Ledger.

Uses SALib to identify which edge uncertainty drives the variance of the
deferral multiplier M, providing structured "commission-a-study" recommendations.
"""

from __future__ import annotations

import math
from typing import Any
import numpy as np
from SALib.sample import saltelli
from SALib.analyze import sobol

from models import Tract, ScenarioRun, EdgePrior
from catalog import load_edges
from priors import point
from cascade import compute_multiplier


def get_edge_bounds(edge: EdgePrior) -> list[float]:
    """
    Determine the plausible [low, high] bounds for an edge prior based on its CI or parameters.

    Ensures that low < high strictly.
    """
    if edge.ci_low is not None and edge.ci_high is not None:
        low, high = float(edge.ci_low), float(edge.ci_high)
        if low > high:
            low, high = high, low
        if low == high:
            high = low + 1e-5
        return [low, high]

    p = edge.params
    if edge.dist_type == "uniform" or edge.dist_type == "triangular":
        low, high = float(p["low"]), float(p["high"])
    elif edge.dist_type == "normal":
        mean, sd = p["mean"], p["sd"]
        low, high = float(mean - 1.96 * sd), float(mean + 1.96 * sd)
    elif edge.dist_type == "lognormal":
        mu, sigma = p["mu"], p["sigma"]
        low, high = float(math.exp(mu - 1.96 * sigma)), float(math.exp(mu + 1.96 * sigma))
    else:
        # Fallback for point estimate or other types
        val = edge.point_estimate
        if val == 0.0:
            low, high = -0.1, 0.1
        else:
            low = val - 0.1 * abs(val)
            high = val + 0.1 * abs(val)

    if low > high:
        low, high = high, low
    if low == high:
        high = low + 1e-5
    return [low, high]


def sobol_indices(
    scenario: ScenarioRun,
    tract: Tract,
    edges: list[EdgePrior] | None = None,
    n_base: int = 1024,
    seed: int = 42,
) -> dict[str, dict[str, float]]:
    """
    Calculate Sobol first-order (S1) and total-order (ST) sensitivity indices.

    Args:
        scenario: The ScenarioRun specification (enabled edges, defer_years, etc.).
        tract:    The Census Tract.
        edges:    List of EdgePrior objects.
        n_base:   Number of base samples for the Saltelli generator.
        seed:     RNG seed for SALib.

    Returns:
        A dictionary mapping edge_id -> {"S1": value, "ST": value}, sorted by ST descending.
    """
    if edges is None:
        edges = load_edges()

    enabled_edges = set(scenario.enabled_edges)

    # 1. Split enabled edges into varying (with uncertainty) and constant (point)
    varying_edges = [
        e for e in edges if e.id in enabled_edges and e.dist_type != "point"
    ]
    point_edges = [
        e for e in edges if e.id in enabled_edges and e.dist_type == "point"
    ]

    if not varying_edges:
        # If there are no varying edges, we can't perform Sobol analysis.
        # Return 0.0 indices for all enabled edges.
        return {eid: {"S1": 0.0, "ST": 0.0} for eid in enabled_edges}

    # 2. Build the SALib problem dictionary
    problem = {
        "num_vars": len(varying_edges),
        "names": [e.id for e in varying_edges],
        "bounds": [get_edge_bounds(e) for e in varying_edges]
    }

    # 3. Generate parameter samples
    from SALib.sample import sobol as sobol_sample
    param_values = sobol_sample.sample(problem, n_base, calc_second_order=False, seed=seed)
    N = param_values.shape[0]

    # 4. Map columns to parameter dictionary for compute_multiplier
    params: dict[str, np.ndarray] = {}
    for i, name in enumerate(problem["names"]):
        params[name] = param_values[:, i]

    for edge in point_edges:
        params[edge.id] = np.full(N, float(point(edge)))

    # 5. Evaluate the multiplier vectorized over all samples
    M_samples = compute_multiplier(params, tract, scenario)

    # 6. Analyze S1 and ST indices
    if np.all(M_samples == M_samples[0]):
        # No variance in output, return 0.0 indices
        res = {name: {"S1": 0.0, "ST": 0.0} for name in problem["names"]}
    else:
        Si = sobol.analyze(problem, M_samples, calc_second_order=False, seed=seed)
        S1 = np.nan_to_num(Si["S1"], nan=0.0)
        ST = np.nan_to_num(Si["ST"], nan=0.0)

        res = {}
        for i, name in enumerate(problem["names"]):
            res[name] = {
                "S1": max(0.0, float(S1[i])),
                "ST": max(0.0, float(ST[i]))
            }

    # Include constant/point edges with zero sensitivity at the bottom
    for edge in point_edges:
        res[edge.id] = {"S1": 0.0, "ST": 0.0}

    # 7. Sort by ST descending
    ranked = dict(sorted(res.items(), key=lambda item: item[1]["ST"], reverse=True))

    return ranked


def commission_study_recommendation(
    sobol_res: dict[str, dict[str, float]],
    edges: list[EdgePrior] | None = None,
) -> dict[str, Any]:
    """
    Generate a study commissioning recommendation based on Sobol total sensitivity indices.

    Args:
        sobol_res: The output from `sobol_indices()`.
        edges:     List of EdgePrior objects to resolve details.

    Returns:
        A dict containing {"top_driver", "ST", "plain_language"}.
    """
    if edges is None:
        edges = load_edges()

    # Find the top varying driver (exclude point/constant edges if they are 0.0)
    top_driver = None
    top_st = 0.0

    for eid, indices in sobol_res.items():
        if indices["ST"] > top_st:
            top_st = indices["ST"]
            top_driver = eid

    # Fallback to E1 if no varying driver is detected or all are zero
    if top_driver is None:
        top_driver = "E1_lsl_to_bll"
        top_st = 0.0

    # Human-readable study recommendation messages based on top driver
    messages = {
        "E1_lsl_to_bll": (
            "We highly recommend commissioning a localized water-lead blood-lead cohort study. "
            "Uncertainty in how much blood lead levels rise while lead service lines stay in the "
            "ground accounts for the vast majority of the decision risk."
        ),
        "E2_bll_to_iq": (
            "We recommend commissioning a systematic review or local epidemiology study on blood-lead-to-IQ "
            "dose-response slopes, specifically for low-level exposures (<10 µg/dL)."
        ),
        "E3_iq_to_earnings": (
            "We recommend commissioning an economic labor study to refine local cohort lifetime earnings loss "
            "projections per IQ point."
        ),
        "E4_bll_to_sped": (
            "We recommend auditing public school records to refine the special-education placement rate "
            "and incremental cost attributable to lead exposure."
        ),
        "E5_bll_to_healthcare": (
            "We recommend analyzing Medicaid claims databases to narrow the estimate of pediatric healthcare "
            "costs attributable to elevated BLL."
        ),
        "E0_cost_per_line": (
            "We recommend conducting contractor quote audits or a engineering site scan to narrow "
            "the uncertainty of the lead service line replacement cost."
        ),
        "E6_adult_bll_to_cvd_ckd": (
            "We recommend conducting a cardiovascular and kidney disease mortality cohort review "
            "for adult long-horizon exposures."
        ),
        "E7_bll_to_crime": (
            "We recommend reviewing juvenile justice administrative data to audit lead-associated crime costs, "
            "taking careful care to avoid stigmatizing neighborhood framings."
        )
    }

    plain_language = messages.get(top_driver, "We recommend commissioning a study to refine the parameters of this edge.")

    return {
        "top_driver": top_driver,
        "ST": round(top_st, 4),
        "plain_language": plain_language
    }
