"""
tests/test_brief_panels.py — Verification suite for Deferral Ledger Day 3 tasks (Chaitanya).
"""

from __future__ import annotations

import os

import pandas as pd
import plotly.graph_objects as go
import pytest

from brief import generate_brief
from catalog import default_enabled_edges, load_edges
from models import ScenarioRun, Tract
from montecarlo import compare, run_monte_carlo
from panels import (
    plot_compare_distributions,
    plot_m_posterior,
    plot_sobol_tornado,
    render_edge_citation_table,
)
from sensitivity import commission_study_recommendation, sobol_indices


@pytest.fixture
def test_setup() -> dict:
    """Prepare a standard tract, catalog, scenario run, and outputs for testing."""
    tract = Tract(
        geoid="26049900001",
        lines_count=100,
        children_under6=50,
        svi_percentile=0.8,
        has_inventory_flag=True,
        synthetic=True
    )
    edges = load_edges()
    enabled_edge_ids = [e.id for e in default_enabled_edges()]
    
    scenario = ScenarioRun(
        id="test-run-day3",
        tract_id=tract.geoid,
        defer_years=5,
        discount_rate=0.03,
        enabled_edges=enabled_edge_ids,
        seed=42,
        n_draws=200
    )
    
    mc_result = run_monte_carlo(scenario, tract, edges, n_draws=200, seed=42)
    sobol = sobol_indices(scenario, tract, edges, n_base=64, seed=42)
    commission_rec = commission_study_recommendation(sobol, edges)
    compare_res = compare(scenario, tract, edges, n_draws=200, seed=42)
    
    return {
        "tract": tract,
        "edges": edges,
        "scenario": scenario,
        "mc_result": mc_result,
        "sobol": sobol,
        "commission_rec": commission_rec,
        "compare_res": compare_res,
    }


def test_generate_brief_templated_fallback(test_setup) -> None:
    """Verify that generate_brief outputs a properly structured markdown document."""
    setup = test_setup
    
    # Force API key to be absent to test fallback
    old_gemini_key = os.environ.pop("GEMINI_API_KEY", None)
    old_google_key = os.environ.pop("GOOGLE_API_KEY", None)
    
    try:
        brief_text = generate_brief(
            result=setup["mc_result"],
            sobol=setup["sobol"],
            commission_rec=setup["commission_rec"],
            compare=setup["compare_res"],
            edges=setup["edges"]
        )
        
        assert isinstance(brief_text, str)
        assert "# DEFERRAL LEDGER — DECISION BRIEF" in brief_text
        assert f"Tract ID:** {setup['mc_result'].tract_id}" in brief_text
        assert "Headline Estimate:" in brief_text
        assert "90% Credible Interval:" in brief_text
        assert "Risk Driver & Study Recommendation" in brief_text
        assert "Comparison of Scenarios" in brief_text
        assert "Edge Catalog and Evidence Citations" in brief_text
        
        # Verify that all active edges are cited
        for edge_id in setup["mc_result"].enabled_edges:
            assert edge_id in brief_text
            
    finally:
        # Restore environment keys
        if old_gemini_key is not None:
            os.environ["GEMINI_API_KEY"] = old_gemini_key
        if old_google_key is not None:
            os.environ["GOOGLE_API_KEY"] = old_google_key


def test_generate_brief_abstention(test_setup) -> None:
    """Verify that generate_brief includes the warning banner when abstention trips."""
    setup = test_setup
    mc_result_abstain = setup["mc_result"].model_copy(update={
        "abstain": True,
        "abstain_message": "insufficient evidence warning"
    })
    
    brief_text = generate_brief(
        result=mc_result_abstain,
        sobol=setup["sobol"],
        commission_rec=setup["commission_rec"],
        compare=setup["compare_res"],
        edges=setup["edges"]
    )
    
    assert "ABSTENTION ACTIVE: insufficient evidence warning" in brief_text
    assert "[!WARNING]" in brief_text


def test_plotly_panels_figures(test_setup) -> None:
    """Verify that Plotly figures are returned correctly from plot functions."""
    setup = test_setup
    
    # 1. Posterior Plot
    fig_posterior = plot_m_posterior(
        result=setup["mc_result"],
        m_draws=None,  # test reconstruction
        tract=setup["tract"],
        edges=setup["edges"]
    )
    assert isinstance(fig_posterior, go.Figure)
    assert "Posterior Distribution" in fig_posterior.layout.title.text
    
    # 2. Sobol Tornado Plot
    fig_sobol = plot_sobol_tornado(
        sobol_res=setup["sobol"],
        commission_rec=setup["commission_rec"]
    )
    assert isinstance(fig_sobol, go.Figure)
    assert "Sobol Sensitivity Analysis" in fig_sobol.layout.title.text
    
    # 3. Compare Plot
    fig_compare = plot_compare_distributions(
        compare_res=setup["compare_res"]
    )
    assert isinstance(fig_compare, go.Figure)
    assert "Cost Distribution comparison" in fig_compare.layout.title.text


def test_render_edge_citation_table(test_setup) -> None:
    """Verify that render_edge_citation_table produces a valid Pandas DataFrame."""
    setup = test_setup
    enabled_ids = setup["mc_result"].enabled_edges
    
    df = render_edge_citation_table(
        edges=setup["edges"],
        enabled_edge_ids=enabled_ids
    )
    
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "ID" in df.columns
    assert "Description" in df.columns
    assert "Citation Source" in df.columns
    assert len(df) == len(enabled_ids)
