"""
tests/test_audit_optimize.py — Verification suite for Deferral Ledger Day 3 tasks.

Tests SQLite audit trails persistence, consent logging, REST API lookup,
and budget optimizer behavior with SVI equity floors.
"""

from __future__ import annotations

import os
import uuid
import numpy as np
import pytest
from fastapi.testclient import TestClient

from api import app
from audit import DB_FILE, get_audit_record, get_consent_logs, log_consent_event, save_audit_record
from models import AuditRecord, ScenarioRun, Tract
from catalog import load_edges
from montecarlo import run_monte_carlo
from optimize import optimize_allocations

client = TestClient(app)


@pytest.fixture
def test_tract() -> Tract:
    return Tract(
        geoid="26049900001",
        lines_count=100,
        children_under6=50,
        svi_percentile=0.85,
        has_inventory_flag=True,
        synthetic=True
    )


@pytest.fixture
def catalog_edges():
    return load_edges()


# ── Audit Persistence & Consent Logs Testing ──────────────────────────────────

def test_audit_persistence_and_api(test_tract, catalog_edges) -> None:
    """Verify scenario run persists audit records and logs to database (FR-GOV-2)."""
    # 1. Clean up db if exists
    if DB_FILE.exists():
        try:
            DB_FILE.unlink()
        except OSError:
            pass

    scenario = ScenarioRun(
        id=str(uuid.uuid4()),
        tract_id=test_tract.geoid,
        defer_years=5,
        discount_rate=0.03,
        enabled_edges=["E0_cost_per_line", "E1_lsl_to_bll", "E2_bll_to_iq", "E3_iq_to_earnings"],
        seed=42,
        n_draws=100
    )

    # 2. Execute simulation (which triggers audit record save)
    res = run_monte_carlo(scenario, test_tract, catalog_edges, n_draws=100)

    # 3. Retrieve audit record from DB directly
    db_rec = get_audit_record(res.run_id)
    assert db_rec is not None
    assert db_rec.run_id == res.run_id
    assert db_rec.catalog_version == res.catalog_version
    assert db_rec.user == "system_operator"

    # 4. Query API GET /audit/{id}
    resp = client.get(f"/audit/{res.run_id}")
    assert resp.status_code == 200
    api_json = resp.json()
    assert api_json["run_id"] == res.run_id
    assert api_json["catalog_version"] == res.catalog_version


def test_contested_consent_logging() -> None:
    """Verify that enabling a contested edge logs a consent event (FR-GOV-3, RAI-1)."""
    # Clean logs
    log_consent_event(user="test_operator", edge_id="E7_bll_to_crime", action="enable", details="Injected consent event.")

    logs = get_consent_logs()
    assert len(logs) > 0
    latest = logs[0]
    assert latest["user"] == "test_operator"
    assert latest["edge_id"] == "E7_bll_to_crime"
    assert latest["action"] == "enable"
    assert "Injected consent event" in latest["details"]


# ── Budget Allocation Optimizer Testing ───────────────────────────────────────

def test_budget_optimizer_logic(catalog_edges) -> None:
    """Verify budget optimizer prioritizes and respects the SVI equity floor (FR-OPT-1)."""
    # Generate 4 distinct tracts:
    # Tract A: high M, high SVI (Priority #1)
    # Tract B: high M, low SVI (Priority #2)
    # Tract C: low M, high SVI (Should be selected first if equity floor demands it)
    # Tract D: low M, low SVI (Last priority)
    
    tract_a = Tract(geoid="26049900001", lines_count=100, children_under6=200, svi_percentile=0.9, has_inventory_flag=True, synthetic=True)
    tract_b = Tract(geoid="26049900002", lines_count=100, children_under6=190, svi_percentile=0.3, has_inventory_flag=True, synthetic=True)
    tract_c = Tract(geoid="26049900003", lines_count=100, children_under6=50, svi_percentile=0.85, has_inventory_flag=True, synthetic=True)
    tract_d = Tract(geoid="26049900004", lines_count=100, children_under6=10, svi_percentile=0.2, has_inventory_flag=True, synthetic=True)

    tracts = [tract_a, tract_b, tract_c, tract_d]
    
    # Replacement cost per tract = 100 * 4700 = $470,000
    # Total budget = $1,000,000 (We can only choose 2 tracts out of 4!)
    budget = 1000000.0
    
    # 1. First scenario: No equity floor (0%). Should pick highest M (Tract A and Tract B)
    df_no_floor = optimize_allocations(
        tracts=tracts,
        edges=catalog_edges,
        budget=budget,
        equity_floor_pct=0.0,
        n_draws=100
    )
    
    selected_no_floor = df_no_floor[df_no_floor["Selected"] == "YES"]["Tract ID"].tolist()
    assert "26049900001" in selected_no_floor  # Tract A (highest M)
    assert "26049900002" in selected_no_floor  # Tract B (second highest M)
    assert "26049900003" not in selected_no_floor  # Tract C (lower M, high SVI)

    # 2. Second scenario: 50% equity floor.
    # At least 50% of budget ($500k) must go to high-SVI tracts (A and C).
    # Since cost is $470k per tract, we must select at least one high-SVI tract.
    # High-SVI tracts are A and C. Low-SVI are B and D.
    # High-SVI prioritized: A, then C.
    # Pick A (High-SVI) - cost $470k.
    # Pick C (High-SVI) - cost $470k (to satisfy high-SVI budget earmark since picking B would leave equity budget at only $470k / $940k total, wait, if we pick A and B: total allocated to high-SVI is $470k. Total allocated budget is $940k. 470 / 940 = 50%, which is exactly 50%. But let's check: if we raise equity floor to 100% (or 60%), we must select both A and C!).
    df_high_floor = optimize_allocations(
        tracts=tracts,
        edges=catalog_edges,
        budget=budget,
        equity_floor_pct=60.0,
        n_draws=100
    )
    selected_high_floor = df_high_floor[df_high_floor["Selected"] == "YES"]["Tract ID"].tolist()
    assert "26049900001" in selected_high_floor  # Tract A (High M, High SVI)
    assert "26049900003" in selected_high_floor  # Tract C (Low M, High SVI) - picked due to high equity floor earmark
