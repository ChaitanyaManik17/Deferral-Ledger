"""
tests/test_sensitivity_gates.py — Verification suite for Day 2 Deferral Ledger tasks.

Tests include:
  - EV-3: CI width grows with defer_years, and standard error of mean shrinks with n_draws
  - EV-4: Sobol sensitivity recovery of an injected dominant edge
  - EV-6: Abstention gate fires when 95% CI spans M < 1.0
  - MC Reproducibility: Same seed yields identical results
"""

from __future__ import annotations

import numpy as np
import pytest
from models import Tract, ScenarioRun, EdgePrior
from montecarlo import run_monte_carlo
from sensitivity import sobol_indices, commission_study_recommendation
from gates import apply_abstention


@pytest.fixture
def base_tract() -> Tract:
    return Tract(
        geoid="26049900001",
        lines_count=100,
        children_under6=50,
        svi_percentile=0.8,
        has_inventory_flag=True,
        synthetic=True
    )


@pytest.fixture
def sample_catalog() -> list[EdgePrior]:
    # Standard Day 1 catalog representation
    from catalog import load_edges
    return load_edges()


# ── EV-3: CI Calibration ──────────────────────────────────────────────────────

def test_ci_width_grows_with_defer_years(base_tract, sample_catalog) -> None:
    """EV-3: Assert that the 95% CI width of M grows as defer_years increases."""
    scenario_2yr = ScenarioRun(
        id="run-2yr",
        tract_id=base_tract.geoid,
        defer_years=2,
        discount_rate=0.03,
        enabled_edges=["E0_cost_per_line", "E1_lsl_to_bll", "E2_bll_to_iq", "E3_iq_to_earnings"],
        seed=42,
        n_draws=1000
    )
    scenario_10yr = ScenarioRun(
        id="run-10yr",
        tract_id=base_tract.geoid,
        defer_years=10,
        discount_rate=0.03,
        enabled_edges=["E0_cost_per_line", "E1_lsl_to_bll", "E2_bll_to_iq", "E3_iq_to_earnings"],
        seed=42,
        n_draws=1000
    )

    res_2yr = run_monte_carlo(scenario_2yr, base_tract, sample_catalog, n_draws=1000)
    res_10yr = run_monte_carlo(scenario_10yr, base_tract, sample_catalog, n_draws=1000)

    ci_width_2yr = res_2yr.ci95[1] - res_2yr.ci95[0]
    ci_width_10yr = res_10yr.ci95[1] - res_10yr.ci95[0]

    # Longer deferral increases exposure BLL increment, compounding variance, so CI must be wider
    assert ci_width_10yr > ci_width_2yr


def test_standard_error_shrinks_with_n_draws(base_tract, sample_catalog) -> None:
    """EV-3: Assert that the standard error of the mean estimate shrinks with larger n_draws."""
    scenario = ScenarioRun(
        id="run-se",
        tract_id=base_tract.geoid,
        defer_years=5,
        discount_rate=0.03,
        enabled_edges=["E0_cost_per_line", "E1_lsl_to_bll", "E2_bll_to_iq", "E3_iq_to_earnings"],
        seed=42,
        n_draws=1000
    )

    # We draw samples and compute the standard error of the mean (std / sqrt(N))
    # Draw 1000
    np.random.seed(42)
    res_1000 = run_monte_carlo(scenario, base_tract, sample_catalog, n_draws=1000)
    
    # Let's verify standard error directly.
    # Since we can't easily fetch the raw draws from MultiplierResult, we can reconstruct the standard error.
    # Standard error of the mean = standard_deviation / sqrt(N)
    # Let's run a manual check or verify standard deviation is stable while sqrt(N) scales down the error.
    from catalog import default_enabled_edges
    from priors import to_distribution
    from cascade import compute_multiplier

    enabled_ids = scenario.enabled_edges
    params_1000 = {}
    np.random.seed(42)
    for edge in sample_catalog:
        if edge.id in enabled_ids:
            params_1000[edge.id] = to_distribution(edge)(1000)
    M_1000 = compute_multiplier(params_1000, base_tract, scenario)
    se_1000 = np.std(M_1000) / np.sqrt(1000)

    params_5000 = {}
    np.random.seed(42)
    for edge in sample_catalog:
        if edge.id in enabled_ids:
            params_5000[edge.id] = to_distribution(edge)(5000)
    M_5000 = compute_multiplier(params_5000, base_tract, scenario)
    se_5000 = np.std(M_5000) / np.sqrt(5000)

    assert se_5000 < se_1000


# ── EV-4: Sobol Recovery ──────────────────────────────────────────────────────

def test_sobol_recovery_of_dominant_edge(base_tract) -> None:
    """EV-4: Injected dominant edge is recovered as the #1 Sobol driver."""
    # Build a tiny catalog where E1 has massive uncertainty, and E2 has almost zero uncertainty
    dominant_catalog = [
        EdgePrior(
            id="E0_cost_per_line",
            from_node="defer_decision",
            to_node="deferred_dollars",
            dist_type="point",
            params={"value": 5000.0},
            point_estimate=5000.0,
            source="Test",
            last_validated="2026-06-18",
            contested=False,
            enabled=True
        ),
        EdgePrior(
            id="E1_lsl_to_bll",
            from_node="continued_exposure_person_years",
            to_node="bll_increment_ugdl",
            dist_type="uniform",
            params={"low": 1.0, "high": 100.0},  # Huge variance
            point_estimate=50.0,
            ci_low=1.0,
            ci_high=100.0,
            source="Test",
            last_validated="2026-06-18",
            contested=False,
            enabled=True
        ),
        EdgePrior(
            id="E2_bll_to_iq",
            from_node="bll_increment_ugdl",
            to_node="iq_loss_points",
            dist_type="uniform",
            params={"low": 1.0, "high": 1.01},  # Almost no variance
            point_estimate=1.0,
            ci_low=1.0,
            ci_high=1.01,
            source="Test",
            last_validated="2026-06-18",
            contested=False,
            enabled=True
        ),
        EdgePrior(
            id="E3_iq_to_earnings",
            from_node="iq_loss_points",
            to_node="lifetime_earnings_loss_dollars",
            dist_type="point",
            params={"value": 10000.0},
            point_estimate=10000.0,
            source="Test",
            last_validated="2026-06-18",
            contested=False,
            enabled=True
        )
    ]

    scenario = ScenarioRun(
        id="test-run-sobol-rec",
        tract_id=base_tract.geoid,
        defer_years=5,
        discount_rate=0.0,
        enabled_edges=["E0_cost_per_line", "E1_lsl_to_bll", "E2_bll_to_iq", "E3_iq_to_earnings"],
        seed=42,
        n_draws=1000
    )

    sobol_res = sobol_indices(scenario, base_tract, dominant_catalog, n_base=256, seed=42)

    # E1 must be ranked #1 by ST index
    ranked_edge_ids = list(sobol_res.keys())
    assert ranked_edge_ids[0] == "E1_lsl_to_bll"
    assert sobol_res["E1_lsl_to_bll"]["ST"] > sobol_res["E2_bll_to_iq"]["ST"]

    # Check recommendation engine
    recommendation = commission_study_recommendation(sobol_res, dominant_catalog)
    assert recommendation["top_driver"] == "E1_lsl_to_bll"


# ── EV-6: Abstention Gate ─────────────────────────────────────────────────────

def test_abstention_gate_low_vs_high_exposure(base_tract, sample_catalog) -> None:
    """EV-6: Verify that the abstention gate fires when 95% CI spans below 1.0."""
    # Low exposure scenario (defer 1 year with only 1 child under 6)
    low_exposure_tract = Tract(
        geoid="26049900002",
        lines_count=100,
        children_under6=1,      # very few children
        svi_percentile=0.5,
        has_inventory_flag=True,
        synthetic=True
    )
    
    scenario_low = ScenarioRun(
        id="run-low",
        tract_id=low_exposure_tract.geoid,
        defer_years=1,
        discount_rate=0.10,     # high discount rate reduces PV further
        enabled_edges=["E0_cost_per_line", "E1_lsl_to_bll", "E2_bll_to_iq", "E3_iq_to_earnings"],
        seed=42,
        n_draws=1000
    )

    res_low = run_monte_carlo(scenario_low, low_exposure_tract, sample_catalog, n_draws=1000)

    # Plausible M < 1.0, so the gate must trigger abstention
    assert res_low.abstain is True
    assert "insufficient evidence" in res_low.abstain_message

    # High exposure scenario (defer 10 years with 200 children)
    high_exposure_tract = Tract(
        geoid="26049900003",
        lines_count=10,         # cheap replacement cost
        children_under6=200,    # many children exposed
        svi_percentile=0.9,
        has_inventory_flag=True,
        synthetic=True
    )

    scenario_high = ScenarioRun(
        id="run-high",
        tract_id=high_exposure_tract.geoid,
        defer_years=10,
        discount_rate=0.01,
        enabled_edges=["E0_cost_per_line", "E1_lsl_to_bll", "E2_bll_to_iq", "E3_iq_to_earnings"],
        seed=42,
        n_draws=1000
    )

    res_high = run_monte_carlo(scenario_high, high_exposure_tract, sample_catalog, n_draws=1000)

    # Multiplier CI is entirely above 1.0, so abstention should be False
    assert res_high.abstain is False
    assert res_high.abstain_message is None


# ── MC Reproducibility ────────────────────────────────────────────────────────

def test_mc_reproducibility(base_tract, sample_catalog) -> None:
    """Verify that identical seeds yield identical MultiplierResult outputs."""
    scenario = ScenarioRun(
        id="run-repro",
        tract_id=base_tract.geoid,
        defer_years=5,
        discount_rate=0.03,
        enabled_edges=["E0_cost_per_line", "E1_lsl_to_bll", "E2_bll_to_iq", "E3_iq_to_earnings"],
        seed=42,
        n_draws=1000
    )

    res_1 = run_monte_carlo(scenario, base_tract, sample_catalog, n_draws=1000, seed=12345)
    res_2 = run_monte_carlo(scenario, base_tract, sample_catalog, n_draws=1000, seed=12345)
    res_diff = run_monte_carlo(scenario, base_tract, sample_catalog, n_draws=1000, seed=99999)

    # Identical seed -> Identical results
    assert res_1.multiplier_mean == res_2.multiplier_mean
    assert res_1.ci95 == res_2.ci95
    assert res_1.p_gt_1 == res_2.p_gt_1
    assert res_1.abstain == res_2.abstain

    # Different seed -> Different results (due to sampling variance)
    assert res_1.multiplier_mean != res_diff.multiplier_mean
