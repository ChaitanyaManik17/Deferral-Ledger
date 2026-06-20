"""
tests/test_montecarlo.py — Unit tests for the Deferral Ledger Monte-Carlo & API layers.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api import app
from cascade import compute_multiplier
from catalog import load_edges
from models import ScenarioRun, Tract
from montecarlo import compare, run_monte_carlo

client = TestClient(app)


@pytest.fixture
def test_context() -> tuple[Tract, list]:
    """Provide a standard tract and catalog list for testing."""
    tract = Tract(
        geoid="26049900001",
        lines_count=100,
        children_under6=50,
        svi_percentile=0.8,
        has_inventory_flag=True,
        synthetic=True
    )
    edges = load_edges()
    return tract, edges


def test_seed_reproducibility(test_context) -> None:
    """Verify that using the same seed yields identical results (SRS C-5)."""
    tract, edges = test_context

    scenario = ScenarioRun(
        id="test-run-repro",
        tract_id=tract.geoid,
        defer_years=5,
        discount_rate=0.03,
        enabled_edges=[e.id for e in edges if e.enabled],
        seed=42,
        n_draws=1000
    )

    res1 = run_monte_carlo(scenario, tract, edges, n_draws=1000, seed=42)
    res2 = run_monte_carlo(scenario, tract, edges, n_draws=1000, seed=42)
    res3 = run_monte_carlo(scenario, tract, edges, n_draws=1000, seed=100)

    # Identical seed => identical output
    assert res1.multiplier_mean == res2.multiplier_mean
    assert res1.ci95 == res2.ci95
    assert res1.p_gt_1 == res2.p_gt_1

    # Different seed => different output
    assert res1.multiplier_mean != res3.multiplier_mean
    assert res1.ci95 != res3.ci95


def test_vectorized_shape(test_context) -> None:
    """Verify that compute_multiplier runs vectorized without loops (V1)."""
    tract, edges = test_context
    scenario = ScenarioRun(
        id="test-run-shape",
        tract_id=tract.geoid,
        defer_years=5,
        discount_rate=0.03,
        enabled_edges=[e.id for e in edges if e.enabled],
        seed=42,
        n_draws=1
    )

    k = 500
    params = {e.id: np.random.uniform(1.0, 2.0, k) for e in edges}

    multipliers = compute_multiplier(params, tract, scenario)
    assert multipliers.shape == (k,)


def test_credible_interval_width_sanity(test_context) -> None:
    """Verify that CI width behaves sensibly (widens with longer defer horizon) (EV-3)."""
    tract, edges = test_context

    scenario_short = ScenarioRun(
        id="test-run-short",
        tract_id=tract.geoid,
        defer_years=2,
        discount_rate=0.03,
        enabled_edges=[e.id for e in edges if e.enabled],
        seed=42,
        n_draws=1000
    )

    scenario_long = ScenarioRun(
        id="test-run-long",
        tract_id=tract.geoid,
        defer_years=10,
        discount_rate=0.03,
        enabled_edges=[e.id for e in edges if e.enabled],
        seed=42,
        n_draws=1000
    )

    res_short = run_monte_carlo(scenario_short, tract, edges, n_draws=1000, seed=42)
    res_long = run_monte_carlo(scenario_long, tract, edges, n_draws=1000, seed=42)

    width_short = res_short.ci95[1] - res_short.ci95[0]
    width_long = res_long.ci95[1] - res_long.ci95[0]

    # Longer defer horizon should expand uncertainty band
    assert width_long > width_short


def test_scenario_compare(test_context) -> None:
    """Test that compare method calculates the cost delta correctly (FR-SCN-1)."""
    tract, edges = test_context

    scenario_defer = ScenarioRun(
        id="test-run-compare",
        tract_id=tract.geoid,
        defer_years=5,
        discount_rate=0.03,
        enabled_edges=[e.id for e in edges if e.enabled],
        seed=42,
        n_draws=1000
    )

    res = compare(scenario_defer, tract, edges, n_draws=1000, seed=42)
    assert "scenario_now" in res
    assert "scenario_defer" in res
    assert "cost_delta" in res
    assert "mean" in res["cost_delta"]
    assert "ci95" in res["cost_delta"]


def test_api_scenario_endpoints() -> None:
    """Verify FastAPI endpoint responses (V5, IF-API-1)."""
    # 1. Test POST /scenario (deterministic)
    sc_det = {
        "id": "a9c29f62-e9cb-4ef5-bbf3-4fb491e5699b",
        "tract_id": "26049000100",
        "defer_years": 5,
        "discount_rate": 0.03,
        "enabled_edges": [
            "E0_cost_per_line",
            "E1_lsl_to_bll",
            "E2_bll_to_iq",
            "E3_iq_to_earnings",
            "E4_bll_to_sped",
            "E5_bll_to_healthcare"
        ],
        "seed": 42,
        "n_draws": 1
    }
    resp1 = client.post("/scenario", json=sc_det)
    assert resp1.status_code == 200
    res_json1 = resp1.json()
    assert res_json1["multiplier_point"] > 0.0
    assert res_json1["multiplier_mean"] is None  # deterministic

    # 2. Test POST /scenario (Monte-Carlo)
    sc_mc = sc_det.copy()
    sc_mc["n_draws"] = 1000
    resp2 = client.post("/scenario", json=sc_mc)
    assert resp2.status_code == 200
    res_json2 = resp2.json()
    assert res_json2["multiplier_mean"] > 0.0
    assert res_json2["ci95"] is not None

    # 3. Test GET /catalog
    resp3 = client.get("/catalog")
    assert resp3.status_code == 200
    assert len(resp3.json()) > 0

    # 4. Test GET /sensitivity
    resp4 = client.get("/sensitivity?tract_id=26049000100")
    assert resp4.status_code == 200
    assert "sobol_indices" in resp4.json()

    # 5. Test GET /audit/{id}
    resp5 = client.get(f"/audit/{sc_det['id']}")
    assert resp5.status_code == 200
    assert resp5.json()["run_id"] == sc_det["id"]
