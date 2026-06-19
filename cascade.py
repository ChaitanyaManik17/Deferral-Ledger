"""
cascade.py — Vectorized Cascade Cost Engine for Deferral Ledger.

Powers deterministic, Monte-Carlo, and Sobol calculations using a single
vectorized compute core (V1, V2).
"""

from __future__ import annotations

import numpy as np
from models import Tract, ScenarioRun

# ── Constants for CVD & Crime Cost Calculations (SRS Appendix B) ─────────────
VSL_USD = 13_100_000.0            # Value of Statistical Life (EPA 2024)
CVD_BASELINE_RISK = 0.02          # 2% baseline risk of CVD mortality
INCARCERATION_COST_USD = 47_500.0  # Midpoint of BJS 35k-60k
CRIME_BASELINE_RATE = 0.01        # 1% baseline juvenile detention rate

# BLL Capping to prevent over-claiming harm (RAI-2 / SRS LC-2)
BLL_INCREMENT_CAP = 15.0          # ug/dL cap


def get_temporal_discount_sum(defer_years: int, discount_rate: float) -> float:
    """
    Compute the sum of discount factors over the deferral window.
    Acts as the multiplier for person-years of exposure.

    Sum_{t=1}^{defer_years} (1 + r)^(-t)

    Args:
        defer_years: Number of years replacement is deferred.
        discount_rate: Annual discount rate.

    Returns:
        The sum of discount factors.
    """
    if defer_years <= 0:
        return 0.0
    return sum((1.0 + discount_rate) ** -t for t in range(1, defer_years + 1))


def compute_multiplier(
    params: dict[str, np.ndarray],
    tract: Tract,
    scenario: ScenarioRun,
) -> np.ndarray:
    """
    Vectorized cascade compute core for the Deferral Ledger.

    Calculates the deferral multiplier M for each draw.
    Supports k draws simultaneously (k=1 for deterministic, k=N for MC/Sobol).

    Args:
        params: Mapping of edge_id -> np.ndarray of shape (k,).
        tract: The Tract context in scope.
        scenario: The ScenarioRun configuration.

    Returns:
        A np.ndarray of shape (k,) containing the calculated multipliers.
    """
    # 1. Determine number of draws k
    k = 1
    for val in params.values():
        arr = np.asarray(val)
        if arr.ndim > 0 and len(arr) > 0:
            k = len(arr)
            break

    # Helper to retrieve edge parameter array, respecting enabled toggles
    enabled_edges = set(scenario.enabled_edges)

    def get_param(edge_id: str, default: float) -> np.ndarray:
        if edge_id not in enabled_edges:
            # E0 is the cost per line. It is a denominator driver,
            # so if it's disabled, we fall back to default to avoid division by zero.
            if edge_id == "E0_cost_per_line":
                return np.full(k, default)
            return np.zeros(k)

        if edge_id in params:
            arr = np.asarray(params[edge_id])
            if arr.ndim == 0:
                return np.full(k, float(arr))
            return arr
        return np.full(k, default)

    # 2. Extract edge parameter arrays
    cost_per_line = get_param("E0_cost_per_line", 4700.0)
    e1_lsl_to_bll = get_param("E1_lsl_to_bll", 1.5)
    e2_bll_to_iq = get_param("E2_bll_to_iq", -0.87)
    e3_iq_to_earnings = get_param("E3_iq_to_earnings", 11850.0)
    e4_bll_to_sped = get_param("E4_bll_to_sped", 11000.0)
    e5_bll_to_healthcare = get_param("E5_bll_to_healthcare", 7500.0)
    e6_adult_bll_to_cvd_ckd = get_param("E6_adult_bll_to_cvd_ckd", 1.70)
    e7_bll_to_crime = get_param("E7_bll_to_crime", 1.15)

    # 3. Calculate Denominator (Deferred Dollars)
    deferred_dollars = tract.lines_count * cost_per_line

    # 4. Temporal discounting multiplier
    # Represents the sum of discounted child cohort-years exposed
    discount_sum = get_temporal_discount_sum(scenario.defer_years, scenario.discount_rate)

    # 5. Capped BLL elevation sustained during deferral
    # Sustained elevation is E1, capped at BLL_INCREMENT_CAP to prevent uncalibrated linear blowup
    bll_increment = np.minimum(BLL_INCREMENT_CAP, e1_lsl_to_bll)

    # 6. Calculate pathway costs per child per year of exposure
    # Path 1: E1 -> E2 -> E3 (Earnings Loss)
    earnings_loss_per_child = bll_increment * np.abs(e2_bll_to_iq) * e3_iq_to_earnings

    # Path 2: E1 -> E4 (Special Education)
    sped_loss_per_child = bll_increment * e4_bll_to_sped

    # Path 3: E1 -> E5 (Healthcare)
    healthcare_loss_per_child = bll_increment * e5_bll_to_healthcare

    # Path 4: E1 -> E6 (Cardiovascular/CKD - VSL Conversion)
    # CVD risk increase: max(0, HR - 1.0) * (BLL_increment / 5.7)
    cvd_loss_per_child = (
        np.maximum(0.0, e6_adult_bll_to_cvd_ckd - 1.0)
        * (bll_increment / 5.7)
        * CVD_BASELINE_RISK
        * VSL_USD
    )

    # Path 5: E1 -> E7 (Crime - Incarceration Cost)
    # Crime risk increase: max(0, RR - 1.0) * BLL_increment
    crime_loss_per_child = (
        np.maximum(0.0, e7_bll_to_crime - 1.0)
        * bll_increment
        * CRIME_BASELINE_RATE
        * INCARCERATION_COST_USD
    )

    # Sum of childhood outcomes per exposed child-year
    total_child_loss_per_year = (
        earnings_loss_per_child
        + sped_loss_per_child
        + healthcare_loss_per_child
        + cvd_loss_per_child
        + crime_loss_per_child
    )

    # Total discounted cascade cost for the tract cohort over the deferral period
    total_discounted_cost = tract.children_under6 * total_child_loss_per_year * discount_sum

    # 7. Compute Multiplier M
    multiplier = np.zeros(k)
    valid_mask = deferred_dollars > 0
    multiplier[valid_mask] = total_discounted_cost[valid_mask] / deferred_dollars[valid_mask]

    return multiplier
