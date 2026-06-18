"""
montecarlo.py — Monte Carlo engine for Deferral Ledger.

Propagates edge uncertainties through the causal DAG to compute
the deferral multiplier posterior distribution and scenario comparisons.
"""

from __future__ import annotations

from datetime import datetime, timezone
import numpy as np
from models import Tract, ScenarioRun, MultiplierResult, EdgePrior
from catalog import load_edges
from priors import to_distribution, point
from cascade import compute_multiplier
from gates import apply_abstention


def run_monte_carlo(
    scenario: ScenarioRun,
    tract: Tract,
    edges: list[EdgePrior] | None = None,
    n_draws: int = 10000,
    seed: int = 42,
) -> MultiplierResult:
    """
    Run a Monte Carlo simulation for a given tract and scenario to compute M's posterior.

    Args:
        scenario: The ScenarioRun input specification.
        tract:    The Census Tract.
        edges:    List of EdgePrior objects (loaded if None).
        n_draws:  Number of draws to sample.
        seed:     RNG seed for reproducibility.

    Returns:
        A MultiplierResult populated with the posterior distribution statistics.
    """
    # 1. Ensure edges are loaded
    if edges is None:
        edges = load_edges()

    # 2. Set seed for reproducibility
    np.random.seed(seed)

    enabled_edges = set(scenario.enabled_edges)

    # 3. Draw parameter samples for each enabled edge
    params: dict[str, np.ndarray] = {}
    for edge in edges:
        if edge.id in enabled_edges:
            sampler = to_distribution(edge)
            # scipy distributions use NumPy global state, which is seeded
            params[edge.id] = sampler(n_draws)

    # 4. Evaluate cascade over all draws
    M_draws = compute_multiplier(params, tract, scenario)

    # 5. Compute deterministic point estimate for comparison
    params_point = {e.id: np.array([point(e)]) for e in edges if e.id in enabled_edges}
    M_point_array = compute_multiplier(params_point, tract, scenario)
    multiplier_point = float(M_point_array[0])

    # 6. Calculate posterior statistics
    mean_val = float(np.mean(M_draws))
    median_val = float(np.median(M_draws))
    ci90 = (float(np.percentile(M_draws, 5.0)), float(np.percentile(M_draws, 95.0)))
    ci95 = (float(np.percentile(M_draws, 2.5)), float(np.percentile(M_draws, 97.5)))
    p_gt_1 = float(np.mean(M_draws > 1.0))

    # 7. Construct result
    result = MultiplierResult(
        run_id=scenario.id,
        tract_id=tract.geoid,
        defer_years=scenario.defer_years,
        discount_rate=scenario.discount_rate,
        multiplier_point=round(multiplier_point, 4),
        per_edge_contribution={}, # Deterministic evaluation can fill if needed
        multiplier_mean=round(mean_val, 4),
        ci90=(round(ci90[0], 4), round(ci90[1], 4)),
        ci95=(round(ci95[0], 4), round(ci95[1], 4)),
        p_gt_1=round(p_gt_1, 4),
        abstain=False,
        sobol=None,
        enabled_edges=list(enabled_edges),
        catalog_version="07ae2eb70c80",
        seed=seed,
        created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "") + "Z"
    )

    # 8. Apply abstention gate
    result = apply_abstention(result)

    return result


def compare(
    now_scenario: ScenarioRun,
    defer_scenario: ScenarioRun,
    tract: Tract,
    edges: list[EdgePrior] | None = None,
    n_draws: int = 10000,
    seed: int = 42,
) -> dict:
    """
    Compare 'replace now' (defer_years=0) vs 'defer' scenarios.
    Computes cost distributions and delta statistics in terms of present value (PV).

    Args:
        now_scenario:   Scenario for immediate replacement (defer_years=0).
        defer_scenario: Scenario for deferred replacement (defer_years > 0).
        tract:          The Census Tract.
        edges:          List of EdgePrior objects.
        n_draws:        Number of draws.
        seed:           RNG seed.

    Returns:
        A dictionary containing cost delta statistics.
    """
    if edges is None:
        edges = load_edges()

    # 1. Run Monte Carlo for the defer scenario to get M
    defer_result = run_monte_carlo(defer_scenario, tract, edges, n_draws, seed)

    # 2. Draw cost parameters (E0_cost_per_line) to calculate actual costs
    np.random.seed(seed)
    cost_sampler = None
    for edge in edges:
        if edge.id == "E0_cost_per_line":
            cost_sampler = to_distribution(edge)
            break
    if cost_sampler is not None:
        cost_per_line_draws = cost_sampler(n_draws)
    else:
        cost_per_line_draws = np.full(n_draws, 4700.0)

    deferred_dollars = tract.lines_count * cost_per_line_draws

    # 3. Retrieve M draws for defer scenario
    enabled_edges = set(defer_scenario.enabled_edges)
    params: dict[str, np.ndarray] = {}
    np.random.seed(seed)
    for edge in edges:
        if edge.id in enabled_edges:
            sampler = to_distribution(edge)
            params[edge.id] = sampler(n_draws)

    M_draws = compute_multiplier(params, tract, defer_scenario)

    # 4. Calculate Net Present Value Cost Delta:
    # Delta = Downstream Costs - Savings from deferring capital replacement
    # Savings = replacement_cost * (1 - discount_factor)
    discount_factor = (1.0 + defer_scenario.discount_rate) ** -defer_scenario.defer_years
    savings = deferred_dollars * (1.0 - discount_factor)
    downstream_costs = M_draws * deferred_dollars

    cost_delta = downstream_costs - savings

    return {
        "defer_result": defer_result,
        "cost_delta_mean": float(np.mean(cost_delta)),
        "cost_delta_median": float(np.median(cost_delta)),
        "cost_delta_ci90": (float(np.percentile(cost_delta, 5.0)), float(np.percentile(cost_delta, 95.0))),
        "cost_delta_ci95": (float(np.percentile(cost_delta, 2.5)), float(np.percentile(cost_delta, 97.5))),
        "p_delta_gt_0": float(np.mean(cost_delta > 0.0))
    }
