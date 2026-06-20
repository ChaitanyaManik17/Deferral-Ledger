"""
api.py — FastAPI server for Deferral Ledger.

Exposes REST endpoints to query catalog, run scenarios, perform comparisons,
and retrieve audit trails (V5).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from catalog import get_catalog_version, load_edges
from data_ingest import load_county
from models import AuditRecord, MultiplierResult, ScenarioRun, Tract
from montecarlo import run_monte_carlo, compare
from synth import SYNTH_TRACTS_FILE

app = FastAPI(
    title="DEFERRAL LEDGER API",
    description="Vectorized causal-DAG cascade compute backend for preventative infrastructure decisions.",
    version="0.2.0"
)

# Enable CORS for Streamlit / Frontend dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_tract_context(tract_id: str) -> Tract:
    """Helper to locate tract data in synthetic or raw cache."""
    # Try loading from synthetic file first
    if SYNTH_TRACTS_FILE.exists():
        with open(SYNTH_TRACTS_FILE, encoding="utf-8") as fh:
            tracts_data = json.load(fh)
            for td in tracts_data:
                if td["geoid"] == tract_id:
                    return Tract(**td)

    # Fall back to loading from public Genesee County cached records
    try:
        tracts_df, _, _ = load_county(tract_id)
        match = tracts_df[tracts_df["geoid"] == tract_id]
        if not match.empty:
            row = match.iloc[0]
            return Tract(
                geoid=row["geoid"],
                lines_count=1200,  # default standard LSL count
                children_under6=int(row["children_under6"]),
                svi_percentile=float(row["svi_percentile"]),
                has_inventory_flag=bool(row["has_inventory_flag"]),
                synthetic=True
            )
    except Exception:
        pass

    raise HTTPException(status_code=404, detail=f"Tract '{tract_id}' context not found.")


@app.post("/scenario", response_model=MultiplierResult)
def post_scenario(scenario: ScenarioRun) -> MultiplierResult:
    """
    Run a causal cost scenario for a target tract.
    Performs Monte-Carlo simulation if n_draws > 1, else returns deterministic.
    """
    tract = get_tract_context(scenario.tract_id)
    edges = load_edges()

    try:
        result = run_monte_carlo(
            scenario=scenario,
            tract=tract,
            edges=edges,
            n_draws=scenario.n_draws,
            seed=scenario.seed
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scenario evaluation failed: {str(exc)}")


@app.get("/catalog")
def get_catalog() -> list[dict[str, Any]]:
    """Return all edge-priors currently defined in the cited catalog."""
    try:
        edges = load_edges()
        return [e.model_dump() for e in edges]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load catalog: {str(exc)}")


def serialize_compare_result(res: dict) -> dict:
    import numpy as np
    out = {}
    for k, v in res.items():
        if isinstance(v, np.ndarray):
            out[k] = [round(float(x), 2) for x in v]
        elif k == "defer_result":
            out[k] = v.model_dump()
        elif isinstance(v, dict):
            out[k] = serialize_compare_result(v)
        elif isinstance(v, tuple):
            out[k] = list(v)
        else:
            out[k] = v
    return out


@app.get("/sensitivity")
def get_sensitivity(tract_id: str, defer_years: int = 5) -> dict[str, Any]:
    """
    Exposes Sobol sensitivity indices and study recommendations for a tract run (FR-SENS-1).
    """
    import uuid
    from sensitivity import sobol_indices, commission_study_recommendation

    tract = get_tract_context(tract_id)
    edges = load_edges()
    enabled_edge_ids = [e.id for e in edges if e.enabled and not e.contested]

    # Construct ScenarioRun config
    scenario = ScenarioRun(
        id=str(uuid.uuid4()),
        tract_id=tract_id,
        defer_years=defer_years,
        discount_rate=0.03,
        enabled_edges=enabled_edge_ids,
        seed=42,
        n_draws=1000
    )

    try:
        # Compute Sobol indices
        sobol_res = sobol_indices(scenario, tract, edges, n_base=128, seed=42)
        recommendation = commission_study_recommendation(sobol_res, edges)
        return {
            "tract_id": tract_id,
            "defer_years": defer_years,
            "sobol_indices": sobol_res,
            "recommendation": recommendation
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sensitivity analysis failed: {str(exc)}")


@app.post("/compare")
def post_compare(scenario: ScenarioRun) -> dict[str, Any]:
    """
    Compare replacing now vs deferring replacement for a tract and scenario (FR-SCN-1).
    """
    tract = get_tract_context(scenario.tract_id)
    edges = load_edges()
    try:
        res = compare(
            scenario_defer=scenario,
            tract=tract,
            edges=edges,
            n_draws=scenario.n_draws,
            seed=scenario.seed
        )
        return serialize_compare_result(res)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(exc)}")


@app.get("/audit/{run_id}", response_model=AuditRecord)
def get_audit_record(run_id: str) -> AuditRecord:
    """Return an immutable audit record from the database for the specified run ID (SRS FR-GOV-2)."""
    from audit import get_audit_record as read_audit
    record = read_audit(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Audit record '{run_id}' not found.")
    return record
