"""
optimize.py — Equity-weighted capital allocation budget optimizer.

Prioritizes lead service line replacement across tracts to maximize
downstream cost aversion under budget constraints, with an SVI equity floor (SRS FR-OPT-1).
"""

from __future__ import annotations

import uuid
from typing import Any
import pandas as pd
from models import Tract, ScenarioRun, EdgePrior
from montecarlo import run_monte_carlo


def optimize_allocations(
    tracts: list[Tract],
    edges: list[EdgePrior],
    budget: float,
    discount_rate: float = 0.03,
    defer_years: int = 5,
    equity_floor_pct: float = 30.0,
    seed: int = 42,
    n_draws: int = 1000
) -> pd.DataFrame:
    """
    Greedy budget allocation optimizer.

    1. For each tract, run Monte Carlo simulation to get the posterior mean of M.
    2. Compute replacement cost D = lines_count * cost_per_line (E0 point estimate).
    3. Calculate 'Avoided Downstream Cost' = (M - 1) * D (if M > 1, else 0).
    4. Segregate high-SVI tracts (SVI percentile > 0.8) and low-SVI tracts.
    5. Allocate at least equity_floor_pct% of the budget to high-SVI tracts first,
       prioritizing by M descending.
    6. Allocate the remaining budget to all remaining tracts, prioritized by M descending.
    7. Return a DataFrame listing each tract, lines, SVI, mean M, replacement cost,
       avoided cost, allocated/priority status, and selection explanation.
    """
    # 1. Resolve LSL replacement cost per line (E0 point estimate)
    cost_per_line = 4700.0
    for edge in edges:
        if edge.id == "E0_cost_per_line":
            cost_per_line = edge.point_estimate
            break

    # 2. Compute metrics for each tract
    records = []
    enabled_edges = [e.id for e in edges if e.enabled]

    for tract in tracts:
        scenario = ScenarioRun(
            id=str(uuid.uuid4()),
            tract_id=tract.geoid,
            defer_years=defer_years,
            discount_rate=discount_rate,
            enabled_edges=enabled_edges,
            seed=seed,
            n_draws=n_draws
        )
        res = run_monte_carlo(scenario, tract, edges, n_draws=n_draws, seed=seed)
        mean_m = res.multiplier_mean if res.multiplier_mean is not None else res.multiplier_point
        cost = tract.lines_count * cost_per_line
        avoided_cost = max(0.0, (mean_m - 1.0) * cost)

        records.append({
            "geoid": tract.geoid,
            "svi_percentile": tract.svi_percentile,
            "lines_count": tract.lines_count,
            "mean_m": mean_m,
            "replacement_cost": cost,
            "avoided_cost": avoided_cost,
            "is_high_svi": tract.svi_percentile > 0.8
        })

    # Sort records by multiplier M descending
    records = sorted(records, key=lambda r: r["mean_m"], reverse=True)

    # 3. Calculate target equity budget earmark
    equity_budget_target = budget * (equity_floor_pct / 100.0)
    allocated_equity_budget = 0.0
    allocated_total_budget = 0.0

    for r in records:
        r["selected"] = False
        r["reason"] = "Budget exhausted"

    # Phase 1: Equity floor allocation (SVI > 0.8)
    if equity_budget_target > 0:
        for r in records:
            if r["is_high_svi"] and allocated_equity_budget < equity_budget_target:
                if allocated_total_budget + r["replacement_cost"] <= budget:
                    r["selected"] = True
                    r["reason"] = "Selected (High SVI Equity Floor Earmark)"
                    allocated_equity_budget += r["replacement_cost"]
                    allocated_total_budget += r["replacement_cost"]

    # Phase 2: Standard allocation by highest M
    for r in records:
        if not r["selected"]:
            if allocated_total_budget + r["replacement_cost"] <= budget:
                r["selected"] = True
                r["reason"] = "Selected (Highest Deferral Multiplier)"
                allocated_total_budget += r["replacement_cost"]

    # Build final DataFrame
    out_df = pd.DataFrame([
        {
            "Tract ID": r["geoid"],
            "SVI Percentile": r["svi_percentile"],
            "LSL Count": r["lines_count"],
            "Multiplier M": round(r["mean_m"], 4),
            "Replacement Cost ($)": r["replacement_cost"],
            "Avoided Obligation ($)": round(r["avoided_cost"], 2),
            "Selected": "YES" if r["selected"] else "NO",
            "Allocation Reason": r["reason"]
        }
        for r in records
    ])
    return out_df
