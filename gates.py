"""
gates.py — Decision Gating & Responsible AI rules for Deferral Ledger.

Implements the abstention gate logic (SRS FR-ABS-1, RAI-2).
"""

from __future__ import annotations

from models import MultiplierResult


def apply_abstention(result: MultiplierResult) -> MultiplierResult:
    """
    Apply the abstention gate check to a MultiplierResult.

    SRS FR-ABS-1: If the 95% credible interval spans below 1.0 (i.e. it is plausible
    that the deferral multiplier is less than 1.0, meaning deferring may not compound costs),
    the system MUST set abstain=True and refrain from compelling funding.

    Args:
        result: The MultiplierResult to check and update.

    Returns:
        The updated MultiplierResult.
    """
    if result.ci95 is not None:
        low_95, high_95 = result.ci95
        if low_95 < 1.0:
            result.abstain = True
        else:
            result.abstain = False
    return result
