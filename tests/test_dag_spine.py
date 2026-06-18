"""
tests/test_dag_spine.py — Smoke tests for the Deferral Ledger DAG engine.
"""

from __future__ import annotations

import subprocess
import sys
import pytest
from models import Tract, ScenarioRun, EdgePrior
from dag import build_dag, evaluate


@pytest.fixture
def tiny_catalog() -> list[EdgePrior]:
    """Return a simple 3-edge catalog stub for testing."""
    return [
        EdgePrior(
            id="E0_cost_per_line",
            from_node="defer_decision",
            to_node="deferred_dollars",
            dist_type="point",
            params={"value": 5000.0},
            point_estimate=5000.0,
            source="Test Source",
            last_validated="2026-06-18",
            contested=False,
            enabled=True
        ),
        EdgePrior(
            id="E1_lsl_to_bll",
            from_node="continued_exposure_person_years",
            to_node="bll_increment_ugdl",
            dist_type="point",
            params={"value": 2.0},
            point_estimate=2.0,
            source="Test Source",
            last_validated="2026-06-18",
            contested=False,
            enabled=True
        ),
        EdgePrior(
            id="E2_bll_to_iq",
            from_node="bll_increment_ugdl",
            to_node="iq_loss_points",
            dist_type="point",
            params={"value": -1.0},
            point_estimate=-1.0,
            source="Test Source",
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
            source="Test Source",
            last_validated="2026-06-18",
            contested=False,
            enabled=True
        )
    ]


def test_acyclicity_check(tiny_catalog) -> None:
    """Check that building a valid DAG passes, and adding a cycle raises ValueError."""
    # Valid DAG
    build_dag(tiny_catalog)

    # Introduce a cycle: E3 goes from iq_loss_points to lifetime_earnings_loss_dollars
    # Let's add a cycle by creating an edge from lifetime_earnings_loss_dollars back to bll_increment_ugdl
    cycle_edge = EdgePrior(
        id="E_cycle",
        from_node="lifetime_earnings_loss_dollars",
        to_node="bll_increment_ugdl",
        dist_type="point",
        params={"value": 1.0},
        point_estimate=1.0,
        source="Test Cycle",
        last_validated="2026-06-18",
        contested=False,
        enabled=True
    )
    bad_catalog = tiny_catalog + [cycle_edge]

    with pytest.raises(ValueError, match="Cycle"):
        build_dag(bad_catalog)


def test_evaluate_deterministic_known_multiplier(tiny_catalog) -> None:
    """
    Evaluate on a known synthetic tract + tiny fixed catalog and verify the expected M.

    Parameters:
      Tract: lines_count=100, children_under6=50
      Scenario: defer_years=5, discount_rate=0.0 (no discounting)
      E0 = 5000.0
      E1 = 2.0
      E2 = -1.0
      E3 = 10000.0

    Calculation:
      Deferred Dollars (D) = 100 lines * $5,000/line = $500,000
      BLL increment per child = 5 years * 2.0 BLL/year = 10.0 BLL
      IQ loss per child = 10.0 BLL * 1.0 IQ/BLL = 10.0 IQ pts
      Earnings loss per child = 10.0 IQ * $10,000/IQ = $100,000
      Total Earnings Loss = 50 children * $100,000 = $5,000,000
      Discounted Cost = $5,000,000 * 1.0 = $5,000,000
      Multiplier M = $5,000,000 / $500,000 = 10.0
    """
    tract = Tract(
        geoid="26049900001",
        lines_count=100,
        children_under6=50,
        svi_percentile=0.8,
        has_inventory_flag=True,
        synthetic=True
    )

    scenario = ScenarioRun(
        id="test-run-uuid",
        tract_id="26049900001",
        defer_years=5,
        discount_rate=0.0,
        enabled_edges=["E0_cost_per_line", "E1_lsl_to_bll", "E2_bll_to_iq", "E3_iq_to_earnings"],
        seed=42,
        n_draws=1
    )

    res = evaluate(scenario, tract, tiny_catalog)
    assert res.multiplier_point == pytest.approx(10.0)
    assert res.per_edge_contribution["E3_iq_to_earnings"] == pytest.approx(10.0)
    assert res.per_edge_contribution["E1_lsl_to_bll"] == pytest.approx(10.0)
    assert res.per_edge_contribution["E2_bll_to_iq"] == pytest.approx(10.0)


def test_evaluate_zero_inventory(tiny_catalog) -> None:
    """Evaluating a tract with zero lines should return 0.0 multiplier and not crash."""
    tract = Tract(
        geoid="26049900001",
        lines_count=0,
        children_under6=50,
        svi_percentile=0.8,
        has_inventory_flag=True,
        synthetic=True
    )

    scenario = ScenarioRun(
        id="test-run-uuid",
        tract_id="26049900001",
        defer_years=5,
        discount_rate=0.05,
        enabled_edges=["E0_cost_per_line", "E1_lsl_to_bll", "E2_bll_to_iq", "E3_iq_to_earnings"],
        seed=42,
        n_draws=1
    )

    res = evaluate(scenario, tract, tiny_catalog)
    assert res.multiplier_point == 0.0
    assert all(v == 0.0 for v in res.per_edge_contribution.values())


def test_cli_smoke_run() -> None:
    """Test that the CLI runner executes successfully and produces formatting."""
    cmd = [sys.executable, "-m", "run", "--tract", "T1", "--defer", "5"]
    res = subprocess.run(cmd, capture_output=True, text=True)

    assert res.returncode == 0, f"CLI execution failed with error: {res.stderr}"
    assert "DEFERRAL LEDGER" in res.stdout
    assert "Deferral Multiplier" in res.stdout
    assert "Per-Edge Contributions to M:" in res.stdout
