"""
tests/test_stability.py — Robustness and stability tests for Deferral Ledger Sobol indices.

Enforces FR-SENS-3 (C6): Perturb each prior's spread by ±20% and assert
the top Sobol sensitivity driver remains stable.
"""

from __future__ import annotations

import copy

import pytest

from catalog import load_edges
from models import EdgePrior, ScenarioRun, Tract
from sensitivity import sobol_indices


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
    return load_edges()


def test_sobol_ranking_stability_under_perturbations(base_tract, sample_catalog) -> None:
    """C6 (FR-SENS-3): Perturb each edge prior's bounds by ±20% and check top-1 driver stability."""
    scenario = ScenarioRun(
        id="run-stability",
        tract_id=base_tract.geoid,
        defer_years=5,
        discount_rate=0.03,
        enabled_edges=["E0_cost_per_line", "E1_lsl_to_bll", "E2_bll_to_iq", "E3_iq_to_earnings", "E4_bll_to_sped", "E5_bll_to_healthcare"],
        seed=42,
        n_draws=1000
    )

    # 1. Run baseline Sobol analysis — discover actual top driver (data-driven, not hardcoded)
    baseline_sobol = sobol_indices(scenario, base_tract, sample_catalog, n_base=256, seed=42)
    baseline_top_driver = list(baseline_sobol.keys())[0]

    # Verify the baseline has a clear dominant driver (ST > 0.3)
    assert baseline_sobol[baseline_top_driver]["ST"] > 0.3, (
        f"Expected a dominant edge (ST > 0.3) but got {baseline_sobol}"
    )

    # 2. Perturb each varying edge prior's spread by ±20% and run Sobol again
    for target_edge_id in ["E0_cost_per_line", "E1_lsl_to_bll", "E2_bll_to_iq",
                           "E3_iq_to_earnings", "E4_bll_to_sped", "E5_bll_to_healthcare"]:
        for scale in [0.8, 1.2]:
            # Clone catalog
            perturbed_catalog = copy.deepcopy(sample_catalog)

            # Find the target edge prior and perturb its bounds/CI
            edge = next(e for e in perturbed_catalog if e.id == target_edge_id)

            if edge.ci_low is not None and edge.ci_high is not None:
                mid = (edge.ci_high + edge.ci_low) / 2.0
                half_width = (edge.ci_high - edge.ci_low) / 2.0

                # Scale the spread (half width)
                new_half_width = half_width * scale
                edge.ci_low = mid - new_half_width
                edge.ci_high = mid + new_half_width

                # Also perturb the params dictionary to match the new spread
                if edge.dist_type == "uniform":
                    edge.params["low"] = mid - new_half_width
                    edge.params["high"] = mid + new_half_width
                elif edge.dist_type == "triangular":
                    edge.params["low"] = mid - new_half_width
                    edge.params["high"] = mid + new_half_width
                    edge.params["mode"] = max(
                        edge.params["low"], min(edge.params["high"], edge.params["mode"])
                    )
                elif edge.dist_type == "normal":
                    edge.params["sd"] = edge.params["sd"] * scale
                elif edge.dist_type == "lognormal":
                    edge.params["sigma"] = edge.params["sigma"] * scale

            # Run Sobol with perturbed catalog
            perturbed_sobol = sobol_indices(
                scenario, base_tract, perturbed_catalog, n_base=128, seed=42
            )
            perturbed_top_driver = list(perturbed_sobol.keys())[0]

            # FR-SENS-3: the top driver under ±20% perturbation must match the baseline top driver.
            # A ±20% shift in any individual prior's spread must not flip the #1 ranking.
            assert perturbed_top_driver == baseline_top_driver, (
                f"Sobol top driver flipped from {baseline_top_driver} to {perturbed_top_driver} "
                f"when perturbing {target_edge_id} by scale {scale} — ranking is NOT robust!"
            )
