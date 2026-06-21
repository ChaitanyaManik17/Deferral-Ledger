"""
cascade.py — Vectorized pathway cascade evaluation for Deferral Ledger.

Powers deterministic, Monte Carlo, and Sobol runs by taking parameter
draws as arrays and performing vectorized calculations.
"""

from __future__ import annotations

import numpy as np

from models import ScenarioRun, Tract

# ── Economic & Epidemiological Conversion Constants ──────────────────────────
VSL_USD = 13_100_000.0           # Value of Statistical Life (EPA 2024)
CVD_BASELINE_RISK = 0.02         # 2% baseline risk of CVD mortality
INCARCERATION_COST_USD = 47_500.0 # Midpoint of BJS 35k-60k
CRIME_BASELINE_RATE = 0.01       # 1% baseline juvenile detention rate


def compute_multiplier(
    params: dict[str, np.ndarray],
    tract: Tract,
    scenario: ScenarioRun,
) -> np.ndarray:
    """
    Evaluate the pathway cost cascade using vectorized NumPy operations.

    Args:
        params:   A dictionary mapping edge IDs to NumPy arrays of shape (k,).
        tract:    The Census Tract containing demographics and LSL count.
        scenario: The ScenarioRun containing deferral parameters.

    Returns:
        A NumPy array of shape (k,) containing the calculated deferral multiplier M.
    """
    enabled = set(scenario.enabled_edges)
    defer_years = scenario.defer_years
    discount_rate = scenario.discount_rate
    lines_count = tract.lines_count
    children_under6 = tract.children_under6

    # Determine array shape (k,) from any provided parameter array
    shape = (1,)
    for val in params.values():
        if isinstance(val, np.ndarray):
            shape = val.shape
            break

    def get_param_array(edge_id: str, default: float) -> np.ndarray:
        if edge_id in enabled and edge_id in params:
            val = params[edge_id]
            if isinstance(val, np.ndarray):
                return val
            return np.full(shape, float(val))
        return np.full(shape, default)

    # 1. Denominator Driver
    cost_per_line = get_param_array("E0_cost_per_line", 4700.0)
    deferred_dollars = lines_count * cost_per_line

    # 2. Exposure & BLL Factors
    bll_increment_factor = get_param_array("E1_lsl_to_bll", 1.5)
    bll_to_iq_factor = get_param_array("E2_bll_to_iq", -0.87)

    # 3. Outcome Factors
    iq_to_earnings_factor = get_param_array("E3_iq_to_earnings", 11850.0)
    bll_to_sped_factor = get_param_array("E4_bll_to_sped", 11000.0)
    bll_to_healthcare_factor = get_param_array("E5_bll_to_healthcare", 7500.0)
    adult_bll_to_cvd_ckd_factor = get_param_array("E6_adult_bll_to_cvd_ckd", 1.70)
    bll_to_crime_factor = get_param_array("E7_bll_to_crime", 1.15)

    # 4. Exposure & Discount Factors
    # Defensible Exposure & Temporal Model:
    # - Blood lead level (BLL) increment is capped at 10.0 µg/dL (flatter dose-response curve above 10 µg/dL).
    # - Discount factor applied based on when the deferred replacements occur.
    bll_increment_per_child = np.minimum(defer_years * bll_increment_factor, 10.0)
    discount_factor = (1.0 + discount_rate) ** -defer_years

    # 5. Calculate Pathway Costs
    # Path 1: E1 -> E2 -> E3 (IQ & Lifetime Earnings Loss)
    if (
        "E1_lsl_to_bll" in enabled
        and "E2_bll_to_iq" in enabled
        and "E3_iq_to_earnings" in enabled
    ):
        undiscounted_earnings = children_under6 * bll_increment_per_child * np.abs(bll_to_iq_factor) * iq_to_earnings_factor
        earnings_cost = undiscounted_earnings * discount_factor
    else:
        earnings_cost = np.zeros(shape)

    # Path 2: E1 -> E4 (Special Education Cost)
    if "E1_lsl_to_bll" in enabled and "E4_bll_to_sped" in enabled:
        undiscounted_sped = children_under6 * bll_increment_per_child * bll_to_sped_factor
        sped_cost = undiscounted_sped * discount_factor
    else:
        sped_cost = np.zeros(shape)

    # Path 3: E1 -> E5 (Childhood Healthcare / Medicaid Cost)
    if "E1_lsl_to_bll" in enabled and "E5_bll_to_healthcare" in enabled:
        undiscounted_healthcare = children_under6 * bll_increment_per_child * bll_to_healthcare_factor
        healthcare_cost = undiscounted_healthcare * discount_factor
    else:
        healthcare_cost = np.zeros(shape)

    # Path 4: E1 -> E6 (Cardiovascular/CKD - Secondary)
    if "E1_lsl_to_bll" in enabled and "E6_adult_bll_to_cvd_ckd" in enabled:
        cvd_cost_per_child = (
            np.maximum(0.0, adult_bll_to_cvd_ckd_factor - 1.0)
            * (bll_increment_per_child / 5.7)
            * CVD_BASELINE_RISK
            * VSL_USD
        )
        undiscounted_cvd = children_under6 * cvd_cost_per_child
        cvd_cost = undiscounted_cvd * discount_factor
    else:
        cvd_cost = np.zeros(shape)

    # Path 5: E1 -> E7 (Crime - Contested)
    if "E1_lsl_to_bll" in enabled and "E7_bll_to_crime" in enabled:
        crime_cost_per_child = (
            np.maximum(0.0, bll_to_crime_factor - 1.0)
            * bll_increment_per_child
            * CRIME_BASELINE_RATE
            * INCARCERATION_COST_USD
        )
        undiscounted_crime = children_under6 * crime_cost_per_child
        crime_cost = undiscounted_crime * discount_factor
    else:
        crime_cost = np.zeros(shape)

    # 6. Sum cost and divide by deferred replacement cost
    total_downstream = earnings_cost + sped_cost + healthcare_cost + cvd_cost + crime_cost

    # Calculate multiplier M, avoiding division by zero warnings
    with np.errstate(divide='ignore', invalid='ignore'):
        M = np.where(deferred_dollars > 0.0, total_downstream / deferred_dollars, 0.0)
    return M


def compute_components(
    params: dict[str, np.ndarray],
    tract: Tract,
    scenario: ScenarioRun,
) -> dict[str, np.ndarray]:
    """
    Return the cascade's intermediate quantities (per-child BLL/IQ/cost + pathway $)
    using the SAME math as compute_multiplier. Used by validation.py to self-check
    the model against published plausible ranges. A consistency test asserts that
    total_downstream / deferred_dollars equals compute_multiplier.
    """
    enabled = set(scenario.enabled_edges)
    defer_years = scenario.defer_years
    discount_rate = scenario.discount_rate
    lines_count = tract.lines_count
    children_under6 = tract.children_under6

    shape = (1,)
    for val in params.values():
        if isinstance(val, np.ndarray):
            shape = val.shape
            break

    def get_param_array(edge_id: str, default: float) -> np.ndarray:
        if edge_id in enabled and edge_id in params:
            val = params[edge_id]
            if isinstance(val, np.ndarray):
                return val
            return np.full(shape, float(val))
        return np.full(shape, default)

    cost_per_line = get_param_array("E0_cost_per_line", 4700.0)
    deferred_dollars = lines_count * cost_per_line

    bll_increment_factor = get_param_array("E1_lsl_to_bll", 1.5)
    bll_to_iq_factor = get_param_array("E2_bll_to_iq", -0.87)
    iq_to_earnings_factor = get_param_array("E3_iq_to_earnings", 11850.0)
    bll_to_sped_factor = get_param_array("E4_bll_to_sped", 11000.0)
    bll_to_healthcare_factor = get_param_array("E5_bll_to_healthcare", 7500.0)
    adult_bll_to_cvd_ckd_factor = get_param_array("E6_adult_bll_to_cvd_ckd", 1.70)
    bll_to_crime_factor = get_param_array("E7_bll_to_crime", 1.15)

    bll_increment_per_child = np.minimum(defer_years * bll_increment_factor, 10.0)
    discount_factor = (1.0 + discount_rate) ** -defer_years

    iq_loss_per_child = bll_increment_per_child * np.abs(bll_to_iq_factor)
    earnings_per_child = iq_loss_per_child * iq_to_earnings_factor
    sped_per_child = bll_increment_per_child * bll_to_sped_factor
    healthcare_per_child = bll_increment_per_child * bll_to_healthcare_factor

    if ("E1_lsl_to_bll" in enabled and "E2_bll_to_iq" in enabled and "E3_iq_to_earnings" in enabled):
        earnings_cost = children_under6 * earnings_per_child * discount_factor
    else:
        earnings_cost = np.zeros(shape)
    if "E1_lsl_to_bll" in enabled and "E4_bll_to_sped" in enabled:
        sped_cost = children_under6 * sped_per_child * discount_factor
    else:
        sped_cost = np.zeros(shape)
    if "E1_lsl_to_bll" in enabled and "E5_bll_to_healthcare" in enabled:
        healthcare_cost = children_under6 * healthcare_per_child * discount_factor
    else:
        healthcare_cost = np.zeros(shape)
    if "E1_lsl_to_bll" in enabled and "E6_adult_bll_to_cvd_ckd" in enabled:
        cvd_cost_per_child = (
            np.maximum(0.0, adult_bll_to_cvd_ckd_factor - 1.0)
            * (bll_increment_per_child / 5.7) * CVD_BASELINE_RISK * VSL_USD
        )
        cvd_cost = children_under6 * cvd_cost_per_child * discount_factor
    else:
        cvd_cost = np.zeros(shape)
    if "E1_lsl_to_bll" in enabled and "E7_bll_to_crime" in enabled:
        crime_cost_per_child = (
            np.maximum(0.0, bll_to_crime_factor - 1.0)
            * bll_increment_per_child * CRIME_BASELINE_RATE * INCARCERATION_COST_USD
        )
        crime_cost = children_under6 * crime_cost_per_child * discount_factor
    else:
        crime_cost = np.zeros(shape)

    total_downstream = earnings_cost + sped_cost + healthcare_cost + cvd_cost + crime_cost
    return {
        "deferred_dollars": deferred_dollars,
        "total_downstream": total_downstream,
        "bll_increment_per_child": bll_increment_per_child,
        "iq_loss_per_child": iq_loss_per_child,
        "earnings_per_child": earnings_per_child,
        "sped_per_child": sped_per_child,
        "healthcare_per_child": healthcare_per_child,
    }
