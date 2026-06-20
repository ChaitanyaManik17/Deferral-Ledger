"""
montecarlo.py — Monte Carlo engine for Deferral Ledger.

Propagates edge uncertainties through the causal DAG to compute
the deferral multiplier posterior distribution and scenario comparisons.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np

from cascade import compute_multiplier
from catalog import get_catalog_version, load_edges
from gates import apply_abstention
from models import EdgePrior, MultiplierResult, ScenarioRun, Tract
from priors import point, to_distribution


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

    # 3. Compute deterministic point estimate as a baseline reference
    point_params = {e.id: np.array([point(e)]) for e in edges}
    multiplier_point = float(compute_multiplier(point_params, tract, scenario)[0])

    # Early return for deterministic run
    if n_draws <= 1:
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

        result = MultiplierResult(
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
            mc_draws=None,
            abstain=False,
            abstain_message=None,
            sobol=None,
            enabled_edges=list(enabled_edges),
            catalog_version=get_catalog_version(),
            seed=seed,
            created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z")
        )
        try:
            from audit import save_audit_record, log_consent_event
            from models import AuditRecord
            contested_enabled = [e for e in ["E6_adult_bll_to_cvd_ckd", "E7_bll_to_crime"] if e in enabled_edges]
            audit_rec = AuditRecord(
                run_id=result.run_id,
                user="system_operator",
                inputs_snapshot_ref="data/synthetic/synthetic_tracts.json",
                catalog_version=result.catalog_version,
                overrides=[],
                contested_edges_enabled=contested_enabled,
                timestamp=result.created_at
            )
            save_audit_record(audit_rec)
            for edge_id in contested_enabled:
                log_consent_event(user="system_operator", edge_id=edge_id, action="enable", details=f"Deterministic run {result.run_id} executed.")
        except Exception:
            pass
        return result


    # 4. Draw parameter samples for each enabled edge (Monte-Carlo)
    params: dict[str, np.ndarray] = {}
    for edge in edges:
        if edge.id in enabled_edges:
            sampler = to_distribution(edge)
            # scipy distributions use NumPy global state, which is seeded
            params[edge.id] = sampler(n_draws)

    # 5. Evaluate cascade over all draws
    M_draws = compute_multiplier(params, tract, scenario)

    # 6. Calculate posterior statistics
    mean_val = float(np.mean(M_draws))
    ci90 = (float(np.percentile(M_draws, 5.0)), float(np.percentile(M_draws, 95.0)))
    ci95 = (float(np.percentile(M_draws, 2.5)), float(np.percentile(M_draws, 97.5)))
    p_gt_1 = float(np.mean(M_draws > 1.0))

    # Calculate per-edge contribution under MC (attributing mean cost contribution)
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
        contribs["E1_lsl_to_bll"] = mean_val

    # 7. Construct result
    result = MultiplierResult(
        run_id=scenario.id,
        tract_id=tract.geoid,
        defer_years=scenario.defer_years,
        discount_rate=scenario.discount_rate,
        multiplier_point=round(multiplier_point, 4),
        per_edge_contribution={k: round(v, 4) for k, v in contribs.items()},
        multiplier_mean=round(mean_val, 4),
        ci90=(round(ci90[0], 4), round(ci90[1], 4)),
        ci95=(round(ci95[0], 4), round(ci95[1], 4)),
        p_gt_1=round(p_gt_1, 4),
        mc_draws=[round(float(x), 4) for x in M_draws],
        abstain=False,
        abstain_message=None,
        sobol=None,
        enabled_edges=list(enabled_edges),
        catalog_version=get_catalog_version(),
        seed=seed,
        created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )

    # 8. Apply abstention gate
    result = apply_abstention(result)

    # 9. Save audit record and log consent events
    try:
        from audit import save_audit_record, log_consent_event
        from models import AuditRecord
        contested_enabled = [e for e in ["E6_adult_bll_to_cvd_ckd", "E7_bll_to_crime"] if e in enabled_edges]
        audit_rec = AuditRecord(
            run_id=result.run_id,
            user="system_operator",
            inputs_snapshot_ref="data/synthetic/synthetic_tracts.json",
            catalog_version=result.catalog_version,
            overrides=[],
            contested_edges_enabled=contested_enabled,
            timestamp=result.created_at
        )
        save_audit_record(audit_rec)
        for edge_id in contested_enabled:
            log_consent_event(user="system_operator", edge_id=edge_id, action="enable", details=f"Scenario run ID {result.run_id} executed.")
    except Exception:
        pass

    return result


def compare(
    scenario_defer: ScenarioRun,
    tract: Tract,
    edges: list[EdgePrior] | None = None,
    n_draws: int = 10000,
    seed: int = 42,
) -> dict:
    """
    Compare 'replace now' (defer_years=0) vs 'defer' scenarios.
    Computes cost distributions and delta statistics in terms of present value (PV).

    Args:
        scenario_defer: Scenario specifying the deferral.
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
    defer_result = run_monte_carlo(scenario_defer, tract, edges, n_draws, seed)

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
    enabled_edges = set(scenario_defer.enabled_edges)
    params: dict[str, np.ndarray] = {}
    np.random.seed(seed)
    for edge in edges:
        if edge.id in enabled_edges:
            sampler = to_distribution(edge)
            params[edge.id] = sampler(n_draws)

    M_draws = compute_multiplier(params, tract, scenario_defer)

    # 4. Calculate Net Present Value Cost Delta:
    # Delta = Downstream Costs - Savings from deferring capital replacement
    # Savings = replacement_cost * (1 - discount_factor)
    discount_factor = (1.0 + scenario_defer.discount_rate) ** -scenario_defer.defer_years
    savings = deferred_dollars * (1.0 - discount_factor)
    downstream_costs = M_draws * deferred_dollars

    cost_delta = downstream_costs - savings

    mean_delta = float(np.mean(cost_delta))
    ci90 = (float(np.percentile(cost_delta, 5.0)), float(np.percentile(cost_delta, 95.0)))
    ci95 = (float(np.percentile(cost_delta, 2.5)), float(np.percentile(cost_delta, 97.5)))

    # Create now scenario for result_now
    import uuid
    scenario_now = scenario_defer.model_copy(update={
        "id": str(uuid.uuid4()),
        "defer_years": 0
    })
    result_now = run_monte_carlo(scenario_now, tract, edges, n_draws, seed)

    return {
        # Our keys (test_montecarlo.py expects these)
        "scenario_now": result_now.model_dump(),
        "scenario_defer": defer_result.model_dump(),
        "cost_delta": {
            "mean": round(mean_delta, 2),
            "ci90": (round(ci90[0], 2), round(ci90[1], 2)),
            "ci95": (round(ci95[0], 2), round(ci95[1], 2)),
            "p_gt_0": round(float(np.mean(cost_delta > 0.0)), 4)
        },
        # Chaitanya's keys
        "defer_result": defer_result,
        "cost_delta_mean": mean_delta,
        "cost_delta_median": float(np.median(cost_delta)),
        "cost_delta_ci90": ci90,
        "cost_delta_ci95": ci95,
        "p_delta_gt_0": float(np.mean(cost_delta > 0.0)),
        "cost_now_draws": deferred_dollars.tolist() if hasattr(deferred_dollars, "tolist") else list(deferred_dollars),
        "cost_defer_draws": (deferred_dollars * discount_factor + M_draws * deferred_dollars).tolist() if hasattr(M_draws, "tolist") else list(deferred_dollars * discount_factor + M_draws * deferred_dollars),
        "cost_delta_draws": cost_delta.tolist() if hasattr(cost_delta, "tolist") else list(cost_delta)
    }
