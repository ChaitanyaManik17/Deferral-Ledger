"""
models.py — Core Pydantic data models for Deferral Ledger.

Defines the shared data contracts used across catalog.py, priors.py,
dag.py (Varun's engine), and the API layer.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ── Supported distribution types ──────────────────────────────────────────────

DistType = Literal["normal", "lognormal", "triangular", "uniform", "point"]


# ── EdgePrior ─────────────────────────────────────────────────────────────────

class EdgePrior(BaseModel):
    """
    A single causal edge in the DAG, parameterised as a probability distribution.

    Every field with a numeric claim MUST have `source` and `last_validated`
    populated — the catalog loader enforces this (SRS EV-1 / C-4).
    """

    id: str = Field(..., description="Unique edge identifier, e.g. 'E2_bll_to_iq'")
    from_node: str = Field(..., description="Source node label in the causal DAG")
    to_node: str = Field(..., description="Target node label in the causal DAG")

    # ── Distribution ──────────────────────────────────────────────────────────
    dist_type: DistType = Field(..., description="Parametric family of the edge prior")
    params: dict[str, float] = Field(
        ...,
        description=(
            "Distribution parameters keyed by name. "
            "normal: {mean, sd}; lognormal: {mu, sigma}; "
            "triangular: {low, mode, high}; uniform: {low, high}; "
            "point: {value}"
        ),
    )
    point_estimate: float = Field(..., description="Central / best-estimate value")
    ci_low: float | None = Field(None, description="Lower bound of the reported CI")
    ci_high: float | None = Field(None, description="Upper bound of the reported CI")

    # ── Provenance (EV-1 / C-4) ───────────────────────────────────────────────
    source: str = Field(
        ...,
        min_length=1,
        description="Full citation: author, year, journal / document, URL if available",
    )
    effect_size: str | None = Field(
        None, description="Human-readable description of the effect size"
    )
    units: str | None = Field(None, description="Units of the effect size")
    last_validated: str = Field(
        ...,
        description="ISO date string when the edge was last checked against the source study",
    )

    # ── Governance ────────────────────────────────────────────────────────────
    contested: bool = Field(
        False,
        description=(
            "True for socially-sensitive edges (e.g., lead→crime). "
            "Contested edges are OFF by default (SRS RAI-1, FR-DASH-3)."
        ),
    )
    enabled: bool = Field(
        True,
        description="Runtime toggle; contested edges default to False.",
    )
    notes: str | None = Field(None, description="Optional explanatory notes")

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("params")
    @classmethod
    def _params_not_empty(cls, v: dict[str, float]) -> dict[str, float]:
        if not v:
            raise ValueError("params must not be empty")
        return v

    @model_validator(mode="after")
    def _validate_params_for_dist(self) -> EdgePrior:
        """Check that params contain the required keys for the declared dist_type."""
        required: dict[str, set[str]] = {
            "normal": {"mean", "sd"},
            "lognormal": {"mu", "sigma"},
            "triangular": {"low", "mode", "high"},
            "uniform": {"low", "high"},
            "point": {"value"},
        }
        needed = required[self.dist_type]
        missing = needed - self.params.keys()
        if missing:
            raise ValueError(
                f"Edge '{self.id}' ({self.dist_type}) is missing params: {missing}"
            )
        return self

    @model_validator(mode="after")
    def _contested_edges_disabled_by_default(self) -> EdgePrior:
        """Contested edges must be disabled by default (SRS RAI-1)."""
        if self.contested and self.enabled:
            raise ValueError(
                f"Edge '{self.id}' is contested but has enabled=True. "
                "Contested edges MUST default to enabled=False (SRS RAI-1)."
            )
        return self


# ── Tract ─────────────────────────────────────────────────────────────────────

class Tract(BaseModel):
    """A census tract with its LSL inventory and demographic attributes."""

    geoid: str = Field(..., description="11-digit census GEOID")
    lines_count: int = Field(..., ge=0, description="LSL count in this tract")
    children_under6: int = Field(..., ge=0, description="Children <6 years in tract")
    svi_percentile: float = Field(..., ge=0.0, le=1.0, description="CDC/ATSDR SVI percentile (0–1)")
    has_inventory_flag: bool = Field(
        False,
        description="True if inventory is from a real reported source; False = synthetic",
    )
    synthetic: bool = Field(
        True, description="True if tract data was synthetically generated"
    )

    @property
    def is_synthetic(self) -> bool:
        return self.synthetic


# ── ScenarioRun ───────────────────────────────────────────────────────────────

class ScenarioRun(BaseModel):
    """Input specification for a single deferral-vs-replace scenario."""

    id: str = Field(..., description="Unique run ID (UUID)")
    tract_id: str = Field(..., description="GEOID of the census tract in scope")
    defer_years: int = Field(..., ge=0, description="Years of deferral (0 = replace now)")
    discount_rate: float = Field(0.03, ge=0.0, le=0.20, description="Annual discount rate")
    enabled_edges: list[str] = Field(
        ..., description="List of EdgePrior.id values enabled for this run"
    )
    seed: int = Field(42, description="Random seed for reproducibility (C-5)")
    n_draws: int = Field(1, ge=1, description="Number of Monte-Carlo draws (1 for deterministic Day 1)")


# ── MultiplierResult ──────────────────────────────────────────────────────────

class MultiplierResult(BaseModel):
    """Output distribution of the deferral multiplier M for a scenario."""

    run_id: str
    tract_id: str
    defer_years: int
    discount_rate: float
    multiplier_point: float                         # Day 1 deterministic
    per_edge_contribution: dict[str, float]         # Day 1
    multiplier_mean: float | None = None            # Day 2 (MC)
    ci90: tuple[float, float] | None = None
    ci95: tuple[float, float] | None = None
    p_gt_1: float | None = None
    mc_draws: list[float] | None = None             # Day 3 draws serialization
    abstain: bool = False                           # Day 2 gate
    abstain_message: str | None = None              # Explanation for abstention
    sobol: dict | None = None                       # Day 2
    enabled_edges: list[str] = []
    catalog_version: str
    seed: int
    created_at: str


# ── AuditRecord ───────────────────────────────────────────────────────────────

class AuditRecord(BaseModel):
    """Immutable audit record for a scenario run (SRS FR-GOV-2)."""

    run_id: str
    user: str | None = None
    inputs_snapshot_ref: str = Field(..., description="Hash/path of the inputs snapshot")
    catalog_version: str = Field(..., description="Git SHA or semantic version of edges.yaml")
    overrides: list[dict[str, Any]] = Field(
        default_factory=list,
        description="User-supplied edge overrides, each with edge_id and changed fields",
    )
    contested_edges_enabled: list[str] = Field(
        default_factory=list,
        description="Contested edges explicitly enabled for this run (consent log)",
    )
    timestamp: str = Field(..., description="ISO 8601 timestamp of audit record creation")
