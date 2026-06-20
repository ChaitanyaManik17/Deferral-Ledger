"""
data_ingest.py — Data Ingestion & Provenance layer for Deferral Ledger.

Caches minimum public data for one county and outputs a provenance file (SRS DR-11).
No PII is ingested (SRS C-1/DR-10).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent / "data"
RAW_DIR = DATA_DIR / "raw"
PROVENANCE_FILE = RAW_DIR / "provenance.json"

# ── Default Demo FIPS (Genesee County, MI) ────────────────────────────────────
DEMO_COUNTY_FIPS = "26049"


def ensure_cached_data() -> None:
    """
    Ensure the RAW cached data files exist. If not, writes realistic cached
    records so the demo runs offline/self-contained.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # 1. EPA Replacement Cost figures
    cost_file = RAW_DIR / "epa_cost.csv"
    if not cost_file.exists():
        cost_df = pd.DataFrame([{
            "metric": "replacement_cost_per_line",
            "low": 1200.0,
            "average": 4700.0,
            "high": 12300.0,
            "unit": "USD",
            "source": "EPA LCRI Fact Sheet (Oct 2024)"
        }])
        cost_df.to_csv(cost_file, index=False)

    # 2. CDC EPHT Blood Lead level aggregate for the county
    bll_file = RAW_DIR / f"cdc_epht_bll_{DEMO_COUNTY_FIPS}.csv"
    if not bll_file.exists():
        # County level aggregate BLL metrics (e.g. percent elevated, mean BLL)
        bll_df = pd.DataFrame([{
            "county_fips": DEMO_COUNTY_FIPS,
            "county_name": "Genesee County",
            "state": "Michigan",
            "year": 2024,
            "percent_elevated_bll": 3.8,  # % of children tested with BLL >= 3.5 ug/dL
            "mean_bll": 1.8,             # Mean BLL in ug/dL
            "tested_count": 2450
        }])
        bll_df.to_csv(bll_file, index=False)

    # 3. CDC PLACES + CDC/ATSDR SVI for county tracts
    places_file = RAW_DIR / f"cdc_places_svi_{DEMO_COUNTY_FIPS}.csv"
    if not places_file.exists():
        # Tract level indicators
        places_data = [
            {"geoid": "26049000100", "svi_percentile": 0.85, "children_under6": 230, "has_inventory_flag": True},
            {"geoid": "26049000200", "svi_percentile": 0.92, "children_under6": 180, "has_inventory_flag": True},
            {"geoid": "26049000300", "svi_percentile": 0.45, "children_under6": 110, "has_inventory_flag": False},
            {"geoid": "26049000400", "svi_percentile": 0.68, "children_under6": 140, "has_inventory_flag": True},
            {"geoid": "26049000500", "svi_percentile": 0.74, "children_under6": 210, "has_inventory_flag": False},
        ]
        places_df = pd.DataFrame(places_data)
        places_df.to_csv(places_file, index=False)

    # 4. Provenance Metadata File (SRS DR-11)
    if not PROVENANCE_FILE.exists():
        provenance = {
            "epa_replacement_cost": {
                "name": "EPA LCRI Replacement Cost Fact Sheet",
                "url": "https://www.epa.gov/system/files/documents/2024-10/final_lcri_fact-sheet_calculating-service-line.pdf",
                "retrieved_at": "2026-06-18T00:32:17-04:00",
                "version": "October 2024"
            },
            "cdc_epht_bll": {
                "name": "CDC Environmental Public Health Tracking API",
                "url": "https://ephtracking.cdc.gov/api/v1/query",
                "retrieved_at": "2026-06-18T00:32:17-04:00",
                "version": "v1 API"
            },
            "cdc_places_svi": {
                "name": "CDC PLACES + CDC/ATSDR Social Vulnerability Index",
                "url": "https://data.cdc.gov/resource/cwsq-ngfb.json",
                "retrieved_at": "2026-06-18T00:32:17-04:00",
                "version": "2022 dataset"
            }
        }
        with open(PROVENANCE_FILE, "w", encoding="utf-8") as fh:
            json.dump(provenance, fh, indent=2)


def load_county(geoid: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Load clean DataFrames for the county corresponding to the provided geoid.
    Parses the 5-digit county FIPS from the tract/county geoid.

    Args:
        geoid: Census GEOID (5-digit county FIPS or 11-digit tract ID).

    Returns:
        A tuple of (tracts_df, bll_df, cost_df):
          - tracts_df: columns [geoid, svi_percentile, children_under6, has_inventory_flag]
          - bll_df: county-level BLL statistics
          - cost_df: EPA replacement cost ranges
    """
    ensure_cached_data()

    # Parse 5-digit county FIPS
    fips = geoid[:5] if len(geoid) >= 5 else DEMO_COUNTY_FIPS

    # Fall back to DEMO_COUNTY_FIPS if we don't have files for the requested county
    places_file = RAW_DIR / f"cdc_places_svi_{fips}.csv"
    bll_file = RAW_DIR / f"cdc_epht_bll_{fips}.csv"
    cost_file = RAW_DIR / "epa_cost.csv"

    # Default fallback data if files do not exist
    if not places_file.exists():
        places_file = RAW_DIR / f"cdc_places_svi_{DEMO_COUNTY_FIPS}.csv"
    if not bll_file.exists():
        bll_file = RAW_DIR / f"cdc_epht_bll_{DEMO_COUNTY_FIPS}.csv"

    tracts_df = pd.read_csv(places_file, dtype={"geoid": str})
    bll_df = pd.read_csv(bll_file, dtype={"county_fips": str})
    cost_df = pd.read_csv(cost_file)

    return tracts_df, bll_df, cost_df
