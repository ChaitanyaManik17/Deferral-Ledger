"""Tests for the Tier 1 self-validation / failure-catching harness."""

from __future__ import annotations

import uuid

import numpy as np

import catalog
import models
from cascade import compute_components, compute_multiplier
from montecarlo import run_monte_carlo
from priors import point
from synth import generate_tracts
from validation import validate_result

_VALID_LEVELS = {"ok", "warn", "fail"}


def _setup(defer: int = 5, n: int = 500):
    edges = catalog.load_edges()
    enabled = [e.id for e in catalog.default_enabled_edges()]
    tract = generate_tracts(10, 42)[0]
    sc = models.ScenarioRun(
        id=str(uuid.uuid4()), tract_id=tract.geoid, defer_years=defer,
        discount_rate=0.03, enabled_edges=enabled, seed=42, n_draws=n,
    )
    return edges, tract, sc


def test_validation_present_and_structured():
    edges, tract, sc = _setup(defer=5, n=500)
    res = run_monte_carlo(sc, tract, edges, n_draws=500, seed=42)
    assert res.validation is not None
    v = res.validation
    assert v["status"] in ("ok", "review")
    assert isinstance(v["needs_human_review"], bool)
    assert len(v["checks"]) >= 4
    for c in v["checks"]:
        assert c["level"] in _VALID_LEVELS
        assert c["name"] and c["detail"]


def test_injected_implausible_M_triggers_review():
    edges, tract, sc = _setup(defer=5, n=500)
    res = run_monte_carlo(sc, tract, edges, n_draws=500, seed=42)
    res.multiplier_mean = 9999.0  # implausible obligation multiplier
    v = validate_result(res, tract, sc, edges)
    assert v["needs_human_review"] is True
    assert any(c["level"] == "fail" for c in v["checks"])


def test_components_consistent_with_multiplier():
    edges, tract, sc = _setup(defer=5, n=1)
    pp = {e.id: np.array([point(e)]) for e in edges}
    comp = compute_components(pp, tract, sc)
    m = float(compute_multiplier(pp, tract, sc)[0])
    expected = float(comp["total_downstream"][0] / comp["deferred_dollars"][0])
    assert abs(m - expected) < 1e-6
