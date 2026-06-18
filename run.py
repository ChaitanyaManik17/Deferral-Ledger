"""
run.py — CLI deterministic spine runner for Deferral Ledger.

Usage:
  python -m run --tract T1 --defer 5
  python -m run --tract 26049900001 --defer 5
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path
from models import ScenarioRun, Tract
from synth import generate_tracts, SYNTH_TRACTS_FILE
from data_ingest import load_county
from dag import evaluate
from catalog import default_enabled_edges

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run deterministic causal-DAG cascade evaluation for a census tract."
    )
    parser.add_argument(
        "--tract",
        type=str,
        required=True,
        help="Target tract ID (e.g. 'T1' or 11-digit GEOID like '26049900001')"
    )
    parser.add_argument(
        "--defer",
        type=int,
        required=True,
        help="Number of years to defer replacement (e.g. 5)"
    )
    parser.add_argument(
        "--discount-rate",
        type=float,
        default=0.03,
        help="Annual discount rate (default: 0.03)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)"
    )

    args = parser.parse_args()

    # 1. Ensure synthetic tracts exist and load them
    if not SYNTH_TRACTS_FILE.exists():
        # Generate 10 synthetic tracts if they don't exist
        tracts = generate_tracts(10, args.seed)
    else:
        with open(SYNTH_TRACTS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            tracts = [Tract(**d) for d in data]

    # 2. Match target tract
    target_tract = None
    tract_label = args.tract

    if args.tract.upper() == "T1":
        if tracts:
            target_tract = tracts[0]
            tract_label = f"T1 (GEOID: {target_tract.geoid})"
        else:
            raise ValueError("No synthetic tracts available to map T1.")
    else:
        # Try to find in synthetic tracts first
        target_tract = next((t for t in tracts if t.geoid == args.tract), None)
        if target_tract is None:
            # Fall back to public cached data
            try:
                tracts_df, _, _ = load_county(args.tract)
                matching_row = tracts_df[tracts_df["geoid"] == args.tract]
                if not matching_row.empty:
                    row = matching_row.iloc[0]
                    target_tract = Tract(
                        geoid=row["geoid"],
                        lines_count=1200,  # default inventory count for real tracts
                        children_under6=int(row["children_under6"]),
                        svi_percentile=float(row["svi_percentile"]),
                        has_inventory_flag=bool(row["has_inventory_flag"]),
                        synthetic=True
                    )
            except Exception as e:
                pass

    if target_tract is None:
        print(f"Error: Target tract '{args.tract}' not found.")
        return

    # 3. Assemble enabled edges (safe default set: ON, contested: OFF)
    edges = default_enabled_edges()
    enabled_edge_ids = [e.id for e in edges]

    # 4. Construct ScenarioRun Pydantic model
    scenario = ScenarioRun(
        id=str(uuid.uuid4()),
        tract_id=target_tract.geoid,
        defer_years=args.defer,
        discount_rate=args.discount_rate,
        enabled_edges=enabled_edge_ids,
        seed=args.seed,
        n_draws=1
    )

    # 5. Evaluate deterministic cascade
    result = evaluate(scenario, target_tract)

    # Calculate deferred dollars directly
    cost_per_line = 4700.0  # default
    for e in edges:
        if e.id == "E0_cost_per_line":
            cost_per_line = e.point_estimate
            break
    deferred_dollars = target_tract.lines_count * cost_per_line

    # 6. Print formatted results
    print("==================================================")
    print("DEFERRAL LEDGER - Day 1 Deterministic Spine Run")
    print("==================================================")
    print(f"Tract:            {tract_label}")
    print(f"Deferral Horizon: {args.defer} years")
    print(f"Discount Rate:    {args.discount_rate * 100:.1f}%")
    print("--------------------------------------------------")
    print(f"Deferred Dollars ($D):     ${deferred_dollars:,.2f}")
    print(f"Deferral Multiplier (M):   {result.multiplier_point:.4f}")
    print("--------------------------------------------------")
    print("Per-Edge Contributions to M:")
    for edge_id, contrib in sorted(result.per_edge_contribution.items()):
        print(f"  * {edge_id:<25}: {contrib:.4f}")
    print("==================================================")

if __name__ == "__main__":
    main()
