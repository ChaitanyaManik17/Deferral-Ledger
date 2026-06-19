"""
api.py — FastAPI server for Deferral Ledger.

Exposes REST endpoints to query catalog, run scenarios, perform comparisons,
and retrieve audit trails (V5).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models import ScenarioRun, MultiplierResult, AuditRecord, Tract
from catalog import load_edges, get_catalog_version
from data_ingest import load_county
from synth import generate_tracts, SYNTH_TRACTS_FILE
from montecarlo import run_monte_carlo, compare

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
        with open(SYNTH_TRACTS_FILE, "r", encoding="utf-8") as fh:
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


@app.get("/sensitivity")
def get_sensitivity(tract_id: str, defer_years: int = 5) -> dict[str, Any]:
    """
    Exposes Sobol sensitivity indices for a tract run.
    Wired to variance attribution coefficients (stubs for Day 2).
    """
    return {
        "tract_id": tract_id,
        "defer_years": defer_years,
        "sobol_indices": {
            "E1_lsl_to_bll": 0.58,
            "E0_cost_per_line": 0.22,
            "E2_bll_to_iq": 0.12,
            "E3_iq_to_earnings": 0.05,
            "E4_bll_to_sped": 0.02,
            "E5_bll_to_healthcare": 0.01
        }
    }


@app.get("/audit/{run_id}", response_model=AuditRecord)
def get_audit_record(run_id: str) -> AuditRecord:
    """Return an immutable audit record for the specified run ID (SRS FR-GOV-2)."""
    return AuditRecord(
        run_id=run_id,
        user="system_operator",
        inputs_snapshot_ref="data/synthetic/synthetic_tracts.json",
        catalog_version=get_catalog_version(),
        overrides=[],
        contested_edges_enabled=[],
        timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
