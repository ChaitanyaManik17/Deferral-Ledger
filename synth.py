"""
synth.py — Synthetic tract generator for Deferral Ledger.

Generates reproducible (seeded) synthetic census tracts calibrated to cached aggregates (SRS DR-9, DR-12).
Sets has_inventory_flag=False on purpose for some tracts to carry "unknown" service-line share (SRS FR-ING-4).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from data_ingest import DEMO_COUNTY_FIPS, load_county
from models import Tract

# ── Paths ─────────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent / "data"
SYNTH_DIR = DATA_DIR / "synthetic"
SYNTH_TRACTS_FILE = SYNTH_DIR / "synthetic_tracts.json"
METADATA_FILE = SYNTH_DIR / "metadata.json"


def generate_tracts(n: int = 10, seed: int = 42) -> list[Tract]:
    """
    Generate reproducible, calibrated synthetic census tracts.
    Uses cached county data to guide parameter ranges (e.g. svi_percentile).

    Args:
        n: Number of synthetic tracts to generate.
        seed: Random seed for reproducibility.

    Returns:
        A list of Tract Pydantic model instances.
    """
    # Create output directory
    SYNTH_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize NumPy generator
    rng = np.random.default_rng(seed)

    # Try to load county data to calibrate ranges, fallback to default ranges
    try:
        tracts_df, _, _ = load_county(DEMO_COUNTY_FIPS)
        min_children = int(tracts_df["children_under6"].min())
        max_children = int(tracts_df["children_under6"].max())
        min_svi = float(tracts_df["svi_percentile"].min())
        max_svi = float(tracts_df["svi_percentile"].max())
    except Exception:
        min_children, max_children = 80, 250
        min_svi, max_svi = 0.4, 0.95

    tracts: list[Tract] = []
    for i in range(n):
        # Generate 11-digit geoid (prefix with 26049 for Genesee County, MI)
        geoid = f"{DEMO_COUNTY_FIPS}{900000 + i + 1}"

        # Generate LSL inventory count (normally distributed, clipped at 0)
        lines_count = int(rng.normal(loc=1200, scale=400))
        if lines_count < 0:
            lines_count = 0

        # Generate children under 6 (calibrated range)
        children_under6 = int(rng.integers(min_children, max_children + 1))

        # Generate SVI percentile
        svi_percentile = float(rng.uniform(min_svi, max_svi))
        svi_percentile = round(max(0.0, min(1.0, svi_percentile)), 4)

        # has_inventory_flag: 60% True, 40% False (carries unknown service-line share)
        has_inventory_flag = bool(rng.choice([True, False], p=[0.6, 0.4]))

        tract = Tract(
            geoid=geoid,
            lines_count=lines_count,
            children_under6=children_under6,
            svi_percentile=svi_percentile,
            has_inventory_flag=has_inventory_flag,
            synthetic=True
        )
        tracts.append(tract)

    # Save tracts to JSON file
    tracts_json = [t.model_dump() for t in tracts]
    with open(SYNTH_TRACTS_FILE, "w", encoding="utf-8") as fh:
        json.dump(tracts_json, fh, indent=2)

    # Save metadata/seed information
    metadata = {
        "seed": seed,
        "n_tracts": n,
        "county_fips": DEMO_COUNTY_FIPS,
        "generated_at": "2026-06-18T04:40:00Z"
    }
    with open(METADATA_FILE, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2)

    return tracts


def generate_india_tracts(n: int = 10, seed: int = 42) -> list[Tract]:
    """
    Generate reproducible, calibrated synthetic census tracts for India.
    Calibrated to South Asian urban demographics (higher child density, lower line count).
    """
    # Create output directory
    SYNTH_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    # Calibration ranges for India (Delhi / urban tracts)
    min_children, max_children = 200, 500
    min_svi, max_svi = 0.5, 0.98

    tracts: list[Tract] = []
    for i in range(n):
        geoid = f"IND_DEL_{1000 + i + 1}"

        # Lower connection counts per tract due to shared utility points
        lines_count = int(rng.normal(loc=800, scale=250))
        if lines_count < 0:
            lines_count = 0

        children_under6 = int(rng.integers(min_children, max_children + 1))
        svi_percentile = float(rng.uniform(min_svi, max_svi))
        svi_percentile = round(max(0.0, min(1.0, svi_percentile)), 4)
        has_inventory_flag = bool(rng.choice([True, False], p=[0.7, 0.3]))

        tract = Tract(
            geoid=geoid,
            lines_count=lines_count,
            children_under6=children_under6,
            svi_percentile=svi_percentile,
            has_inventory_flag=has_inventory_flag,
            synthetic=True
        )
        tracts.append(tract)

    india_file = SYNTH_DIR / "synthetic_tracts_india.json"
    with open(india_file, "w", encoding="utf-8") as fh:
        json.dump([t.model_dump() for t in tracts], fh, indent=2)

    return tracts

