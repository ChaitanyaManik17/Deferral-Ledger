"""
gates.py — Safety gates and compliance monitors for Deferral Ledger.

Implements the 95% CI abstention gate (SRS FR-ABS-1).
"""

from __future__ import annotations

from models import MultiplierResult


def apply_abstention(result: MultiplierResult) -> MultiplierResult:
    """
    Apply safety gates (abstention rules) to a MultiplierResult.

    SRS FR-ABS-1: The system MUST NOT output a "must-fund-now" recommendation
    when the 95% CI of the multiplier M spans below 1.0. If M < 1.0 is plausible,
    deferral might not compound cost, so we abstain from compiling a recommendation.

    Args:
        result: A MultiplierResult instance.

    Returns:
        The mutated/updated MultiplierResult.
    """
    if result.ci95 is not None:
        low, high = result.ci95
        if low < 1.0:
            result.abstain = True
            result.abstain_message = "deferral may not compound here; insufficient evidence to compel funding"
        else:
            result.abstain = False
            result.abstain_message = None
    return result
