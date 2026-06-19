"""
montecarlo.py — Monte-Carlo simulation engine for Deferral Ledger.

Propagates uncertainty through the causal DAG to compute the deferral-multiplier
posterior distribution and compares scenario options (V3, V4).
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
import numpy as np
from models import Tract, ScenarioRun, MultiplierResult, EdgePrior
from priors import to_distribution, point
from cascade import compute_multiplier
import gates
from catalog import get_catalog_version


def run_monte_carlo(
    scenario: ScenarioRun,
    tract: Tract,
    edges: list[EdgePrior],
    n_draws: int = 10_000,
    seed: int = 42
) -> MultiplierResult:
    """
    Run Monte-Carlo propagation of uncertainty for a tract and scenario.

    Draws n_draws samples from each enabled edge prior, evaluates the cascade,
    and returns a MultiplierResult with posterior statistics.

    Args:
        scenario: Input ScenarioRun specification.
        tract: Target census Tract context.
        edges: List of loaded EdgePrior distributions.
        n_draws: Number of Monte-Carlo draws (default: 10,000).
        seed: Random seed for reproducibility (default: 42).

    Returns:
        A MultiplierResult populated with mean, median, CIs, and P(M > 1).
    """
    # 1. Guarantee seed reproducibility (C-5)
    np.random.seed(seed)

    # 2. Compute deterministic point estimate as a baseline reference
    point_params = {e.id: np.array([point(e)]) for e in edges}
    multiplier_point = float(compute_multiplier(point_params, tract, scenario)[0])

    # Early return for deterministic run
    if n_draws <= 1:
        enabled_edges = set(scenario.enabled_edges)
        contribs: dict[str, float] = {}

        def get_path_point(path_edges: list[str]) -> float:
            sub_sc = scenario.model_copy(update={"enabled_edges": path_edges})
            sub_multiplier = compute_multiplier(point_params, tract, sub_sc)
            return float(sub_multiplier[0])

        # Path 1: Earnings Loss
        if (
            "E1_lsl_to_bll" in enabled_edges
            and "E2_bll_to_iq" in enabled_edges
            and "E3_iq_to_earnings" in enabled_edges
        ):
            earnings_val = get_path_point(["E0_cost_per_line", "E1_lsl_to_bll", "E2_bll_to_iq", "E3_iq_to_earnings"])
            contribs["E3_iq_to_earnings"] = earnings_val
            contribs["E2_bll_to_iq"] = earnings_val

        # Path 2: Special Education
        if "E1_lsl_to_bll" in enabled_edges and "E4_bll_to_sped" in enabled_edges:
            contribs["E4_bll_to_sped"] = get_path_point(["E0_cost_per_line", "E1_lsl_to_bll", "E4_bll_to_sped"])

        # Path 3: Healthcare
        if "E1_lsl_to_bll" in enabled_edges and "E5_bll_to_healthcare" in enabled_edges:
            contribs["E5_bll_to_healthcare"] = get_path_point(["E0_cost_per_line", "E1_lsl_to_bll", "E5_bll_to_healthcare"])

        # Path 4: CVD (Secondary)
        if "E1_lsl_to_bll" in enabled_edges and "E6_adult_bll_to_cvd_ckd" in enabled_edges:
            contribs["E6_adult_bll_to_cvd_ckd"] = get_path_point(["E0_cost_per_line", "E1_lsl_to_bll", "E6_adult_bll_to_cvd_ckd"])

        # Path 5: Crime (Contested)
        if "E1_lsl_to_bll" in enabled_edges and "E7_bll_to_crime" in enabled_edges:
            contribs["E7_bll_to_crime"] = get_path_point(["E0_cost_per_line", "E1_lsl_to_bll", "E7_bll_to_crime"])

        # Intermediate E1 node (sum of all downstream)
        if "E1_lsl_to_bll" in enabled_edges:
            contribs["E1_lsl_to_bll"] = multiplier_point

        return MultiplierResult(
            run_id=scenario.id,
            tract_id=tract.geoid,
            defer_years=scenario.defer_years,
            discount_rate=scenario.discount_rate,
            multiplier_point=round(multiplier_point, 4),
            per_edge_contribution={k: round(v, 4) for k, v in contribs.items()},
            multiplier_mean=None,
            ci90=None,
            ci95=None,
            p_gt_1=None,
            abstain=False,
            sobol=None,
            enabled_edges=list(enabled_edges),
            catalog_version=get_catalog_version(),
            seed=seed,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )

    # 3. Sample distributions for all edges in the catalog (Monte-Carlo)
    params: dict[str, np.ndarray] = {}
    for edge in edges:
        sampler = to_distribution(edge)
        # scipy frozen distribution rvs uses np.random state, so seed is respected
        params[edge.id] = sampler(n_draws)

    # 4. Run vectorized MC multiplier calculation
    multipliers = compute_multiplier(params, tract, scenario)

    # Calculate statistics
    multiplier_mean = float(np.mean(multipliers))
    ci90 = (float(np.percentile(multipliers, 5.0)), float(np.percentile(multipliers, 95.0)))
    ci95 = (float(np.percentile(multipliers, 2.5)), float(np.percentile(multipliers, 97.5)))
    p_gt_1 = float(np.mean(multipliers > 1.0))

    # Calculate per-edge contribution under MC (attributing mean cost contribution)
    enabled_edges = set(scenario.enabled_edges)
    contribs: dict[str, float] = {}

    def get_path_mean(path_edges: list[str]) -> float:
        sub_sc = scenario.model_copy(update={"enabled_edges": path_edges})
        sub_multipliers = compute_multiplier(params, tract, sub_sc)
        return float(np.mean(sub_multipliers))

    # Path 1: Earnings Loss
    if (
        "E1_lsl_to_bll" in enabled_edges
        and "E2_bll_to_iq" in enabled_edges
        and "E3_iq_to_earnings" in enabled_edges
    ):
        earnings_val = get_path_mean(["E0_cost_per_line", "E1_lsl_to_bll", "E2_bll_to_iq", "E3_iq_to_earnings"])
        contribs["E3_iq_to_earnings"] = earnings_val
        contribs["E2_bll_to_iq"] = earnings_val

    # Path 2: Special Education
    if "E1_lsl_to_bll" in enabled_edges and "E4_bll_to_sped" in enabled_edges:
        contribs["E4_bll_to_sped"] = get_path_mean(["E0_cost_per_line", "E1_lsl_to_bll", "E4_bll_to_sped"])

    # Path 3: Healthcare
    if "E1_lsl_to_bll" in enabled_edges and "E5_bll_to_healthcare" in enabled_edges:
        contribs["E5_bll_to_healthcare"] = get_path_mean(["E0_cost_per_line", "E1_lsl_to_bll", "E5_bll_to_healthcare"])

    # Path 4: CVD (Secondary)
    if "E1_lsl_to_bll" in enabled_edges and "E6_adult_bll_to_cvd_ckd" in enabled_edges:
        contribs["E6_adult_bll_to_cvd_ckd"] = get_path_mean(["E0_cost_per_line", "E1_lsl_to_bll", "E6_adult_bll_to_cvd_ckd"])

    # Path 5: Crime (Contested)
    if "E1_lsl_to_bll" in enabled_edges and "E7_bll_to_crime" in enabled_edges:
        contribs["E7_bll_to_crime"] = get_path_mean(["E0_cost_per_line", "E1_lsl_to_bll", "E7_bll_to_crime"])

    # Intermediate E1 node (sum of all downstream)
    if "E1_lsl_to_bll" in enabled_edges:
        contribs["E1_lsl_to_bll"] = multiplier_mean

    # 5. Build base result
    result = MultiplierResult(
        run_id=scenario.id,
        tract_id=tract.geoid,
        defer_years=scenario.defer_years,
        discount_rate=scenario.discount_rate,
        multiplier_point=round(multiplier_point, 4),
        per_edge_contribution={k: round(v, 4) for k, v in contribs.items()},
        multiplier_mean=round(multiplier_mean, 4),
        ci90=(round(ci90[0], 4), round(ci90[1], 4)),
        ci95=(round(ci95[0], 4), round(ci95[1], 4)),
        p_gt_1=round(p_gt_1, 4),
        abstain=False,
        sobol=None,
        enabled_edges=list(enabled_edges),
        catalog_version=get_catalog_version(),
        seed=seed,
        created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )

    # 6. Apply Chaitanya's abstention gate (C-DECISION)
    result = gates.apply_abstention(result)

    return result


def compare(
    scenario_defer: ScenarioRun,
    tract: Tract,
    edges: list[EdgePrior],
    n_draws: int = 10_000,
    seed: int = 42
) -> dict:
    """
    Compare replacing now (defer_years=0) vs deferring replacement (defer_years=Δ).
    Computes the present value cost delta distribution (FR-SCN-1).

    Args:
        scenario_defer: ScenarioRun specifying the deferral.
        tract: Target census Tract context.
        edges: List of loaded EdgePrior distributions.
        n_draws: Number of Monte-Carlo draws (default: 10,000).
        seed: Random seed for reproducibility (default: 42).

    Returns:
        A dictionary containing cost delta statistics and scenario results.
    """
    # 1. Guarantee seed reproducibility (C-5)
    np.random.seed(seed)

    # 2. Sample distributions
    params: dict[str, np.ndarray] = {}
    for edge in edges:
        params[edge.id] = to_distribution(edge)(n_draws)

    # 3. Create scenario for replacing now (defer_years = 0)
    scenario_now = scenario_defer.model_copy(update={
        "id": str(uuid.uuid4()),
        "defer_years": 0
    })

    # Run MC for both scenarios
    result_now = run_monte_carlo(scenario_now, tract, edges, n_draws, seed)
    result_defer = run_monte_carlo(scenario_defer, tract, edges, n_draws, seed)

    # 4. Calculate PV cost delta distribution
    # D_i = lines_count * cost_per_line_i
    cost_per_line = params.get("E0_cost_per_line", np.full(n_draws, 4700.0))
    deferred_dollars = tract.lines_count * cost_per_line

    # Replace Now: cost is exactly deferred_dollars (spent today)
    # Defer: cost is PV_downstream_cost + deferred_dollars * (1 + r)**-defer_years
    # Wait, PV_downstream_cost is the numerator of result_defer multiplier
    # So PV_downstream_cost = result_defer_multipliers * deferred_dollars
    multipliers_defer = compute_multiplier(params, tract, scenario_defer)
    pv_downstream = multipliers_defer * deferred_dollars

    discount_factor = (1.0 + scenario_defer.discount_rate) ** -scenario_defer.defer_years
    pv_defer_replacement = deferred_dollars * discount_factor

    # PV Delta = Total Cost (Defer) - Total Cost (Replace Now)
    pv_delta = pv_downstream + pv_defer_replacement - deferred_dollars

    mean_delta = float(np.mean(pv_delta))
    ci90 = (float(np.percentile(pv_delta, 5.0)), float(np.percentile(pv_delta, 95.0)))
    ci95 = (float(np.percentile(pv_delta, 2.5)), float(np.percentile(pv_delta, 97.5)))

    return {
        "scenario_now": result_now.model_dump(),
        "scenario_defer": result_defer.model_dump(),
        "cost_delta": {
            "mean": round(mean_delta, 2),
            "ci90": (round(ci90[0], 2), round(ci90[1], 2)),
            "ci95": (round(ci95[0], 2), round(ci95[1], 2)),
            "p_gt_0": round(float(np.mean(pv_delta > 0.0)), 4)
        }
    }
