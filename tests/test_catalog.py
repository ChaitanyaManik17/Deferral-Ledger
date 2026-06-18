"""
tests/test_catalog.py — Catalog validation tests for Deferral Ledger.

Tests enforce:
  - EV-1 / C-4: citation-less edges are REJECTED (the main build-gate test)
  - All edges in edges.yaml load and validate successfully
  - default_enabled_edges() excludes contested edges
  - dist_type / params consistency is validated
  - Contested edges are disabled by default (RAI-1)

Run with: pytest tests/ -v
"""

from __future__ import annotations

import math
import textwrap
from pathlib import Path

import pytest
import yaml

from catalog import (
    CatalogValidationError,
    MissingCitationError,
    default_enabled_edges,
    load_edges,
    load_contested_registry,
)
from priors import point, to_distribution, ci_to_sd

# ── Paths ─────────────────────────────────────────────────────────────────────

CATALOG_DIR = Path(__file__).parent.parent / "catalog"
EDGES_YAML = CATALOG_DIR / "edges.yaml"
CONTESTED_YAML = CATALOG_DIR / "contested.yaml"


# ══════════════════════════════════════════════════════════════════════════════
# C4 — Catalog loader + validation tests
# ══════════════════════════════════════════════════════════════════════════════


class TestCatalogValidation:
    """Tests for the catalog loader's validation pipeline (catalog.py)."""

    # ── EV-1: Citation-less edges MUST be rejected ────────────────────────────

    def test_missing_source_is_rejected(self, tmp_path: Path) -> None:
        """
        EV-1 GATE TEST: An edge without a `source` citation MUST raise
        CatalogValidationError. This is the primary build-gate test.
        No uncited number may reach the user (SRS C-4).
        """
        bad_yaml = textwrap.dedent("""\
            - id: BAD_no_source
              from_node: bll
              to_node: iq_loss
              dist_type: normal
              params: {mean: -0.87, sd: 0.14}
              point_estimate: -0.87
              # source: intentionally omitted — must be rejected
              last_validated: "2026-06-14"
              contested: false
              enabled: true
        """)
        bad_file = tmp_path / "bad_edges.yaml"
        bad_file.write_text(bad_yaml)

        with pytest.raises(CatalogValidationError, match="source"):
            load_edges(bad_file)

    def test_missing_last_validated_is_rejected(self, tmp_path: Path) -> None:
        """
        EV-1 GATE TEST: An edge without `last_validated` MUST raise
        CatalogValidationError (SRS LC-1).
        """
        bad_yaml = textwrap.dedent("""\
            - id: BAD_no_date
              from_node: bll
              to_node: iq_loss
              dist_type: normal
              params: {mean: -0.87, sd: 0.14}
              point_estimate: -0.87
              source: "Some Author 2024, Some Journal"
              # last_validated: intentionally omitted — must be rejected
              contested: false
              enabled: true
        """)
        bad_file = tmp_path / "bad_edges.yaml"
        bad_file.write_text(bad_yaml)

        with pytest.raises(CatalogValidationError, match="last_validated"):
            load_edges(bad_file)

    def test_both_missing_citation_fields_rejected(self, tmp_path: Path) -> None:
        """An edge missing both source AND last_validated must report both errors."""
        bad_yaml = textwrap.dedent("""\
            - id: BAD_no_citation_at_all
              from_node: a
              to_node: b
              dist_type: point
              params: {value: 1.0}
              point_estimate: 1.0
              contested: false
              enabled: true
        """)
        bad_file = tmp_path / "bad_edges.yaml"
        bad_file.write_text(bad_yaml)

        with pytest.raises(CatalogValidationError) as exc_info:
            load_edges(bad_file)
        # Both violations should appear in the error message
        assert "source" in str(exc_info.value)
        assert "last_validated" in str(exc_info.value)

    # ── Valid catalog loads ────────────────────────────────────────────────────

    def test_main_catalog_loads_successfully(self) -> None:
        """
        All edges in catalog/edges.yaml must load without any validation error.
        This is the smoke test for the production catalog.
        """
        edges = load_edges(EDGES_YAML)
        assert len(edges) > 0, "Catalog must contain at least one edge"

    def test_all_seven_edges_present(self) -> None:
        """The catalog must contain all 8 edges: E0 through E7."""
        edges = load_edges(EDGES_YAML)
        edge_ids = {e.id for e in edges}
        expected_prefixes = ["E0", "E1", "E2", "E3", "E4", "E5", "E6", "E7"]
        for prefix in expected_prefixes:
            matching = [eid for eid in edge_ids if eid.startswith(prefix)]
            assert matching, f"No edge with prefix '{prefix}' found in catalog"

    def test_every_edge_has_source(self) -> None:
        """Every loaded edge must have a non-empty source (belt-and-suspenders check)."""
        edges = load_edges(EDGES_YAML)
        for edge in edges:
            assert edge.source.strip(), f"Edge '{edge.id}' has empty source"

    def test_every_edge_has_last_validated(self) -> None:
        """Every loaded edge must have a last_validated date."""
        edges = load_edges(EDGES_YAML)
        for edge in edges:
            assert edge.last_validated is not None, (
                f"Edge '{edge.id}' has no last_validated date"
            )

    # ── dist_type / params consistency ────────────────────────────────────────

    def test_normal_edge_requires_mean_and_sd(self, tmp_path: Path) -> None:
        """A normal edge missing 'sd' must be rejected."""
        bad_yaml = textwrap.dedent("""\
            - id: BAD_normal_no_sd
              from_node: a
              to_node: b
              dist_type: normal
              params: {mean: -0.87}   # missing sd
              point_estimate: -0.87
              source: "Test Author 2024"
              last_validated: "2026-06-14"
              contested: false
              enabled: true
        """)
        bad_file = tmp_path / "bad_normal.yaml"
        bad_file.write_text(bad_yaml)
        with pytest.raises(CatalogValidationError):
            load_edges(bad_file)

    def test_triangular_edge_requires_low_mode_high(self, tmp_path: Path) -> None:
        """A triangular edge missing 'high' must be rejected."""
        bad_yaml = textwrap.dedent("""\
            - id: BAD_triangular_missing_high
              from_node: a
              to_node: b
              dist_type: triangular
              params: {low: 1.0, mode: 5.0}   # missing high
              point_estimate: 5.0
              source: "Test Author 2024"
              last_validated: "2026-06-14"
              contested: false
              enabled: true
        """)
        bad_file = tmp_path / "bad_tri.yaml"
        bad_file.write_text(bad_yaml)
        with pytest.raises(CatalogValidationError):
            load_edges(bad_file)

    # ── Contested-edge governance (RAI-1) ─────────────────────────────────────

    def test_contested_edges_are_disabled_by_default(self) -> None:
        """
        RAI-1: All contested edges in the production catalog must have
        enabled=False (off by default, never enabled=True).
        """
        edges = load_edges(EDGES_YAML)
        contested = [e for e in edges if e.contested]
        assert contested, "There must be at least one contested edge in the catalog"
        for edge in contested:
            assert not edge.enabled, (
                f"Contested edge '{edge.id}' has enabled=True — "
                "contested edges MUST default to enabled=False (SRS RAI-1)"
            )

    def test_contested_edge_yaml_raises_if_enabled(self, tmp_path: Path) -> None:
        """
        The Pydantic model must REJECT a contested edge with enabled=True.
        """
        bad_yaml = textwrap.dedent("""\
            - id: BAD_contested_enabled
              from_node: bll
              to_node: crime_cost
              dist_type: point
              params: {value: 5000.0}
              point_estimate: 5000.0
              source: "Test Author 2024"
              last_validated: "2026-06-14"
              contested: true
              enabled: true    # This must be rejected
        """)
        bad_file = tmp_path / "bad_contested.yaml"
        bad_file.write_text(bad_yaml)
        with pytest.raises(CatalogValidationError):
            load_edges(bad_file)


# ══════════════════════════════════════════════════════════════════════════════
# C4 — default_enabled_edges() tests
# ══════════════════════════════════════════════════════════════════════════════


class TestDefaultEnabledEdges:
    """Tests for the default safe-set filter."""

    def test_default_enabled_excludes_contested(self) -> None:
        """
        default_enabled_edges() must NOT include any contested edge.
        This enforces the public default safe view (SRS FR-DASH-3, RAI-1).
        """
        enabled = default_enabled_edges(EDGES_YAML)
        contested_in_enabled = [e for e in enabled if e.contested]
        assert not contested_in_enabled, (
            f"default_enabled_edges() returned contested edges: "
            f"{[e.id for e in contested_in_enabled]}"
        )

    def test_default_enabled_excludes_disabled(self) -> None:
        """default_enabled_edges() must NOT include edges with enabled=False."""
        enabled = default_enabled_edges(EDGES_YAML)
        disabled_in_enabled = [e for e in enabled if not e.enabled]
        assert not disabled_in_enabled, (
            f"default_enabled_edges() returned disabled edges: "
            f"{[e.id for e in disabled_in_enabled]}"
        )

    def test_default_enabled_contains_core_edges(self) -> None:
        """E0–E5 (the non-contested, always-on edges) must be in the default set."""
        enabled = default_enabled_edges(EDGES_YAML)
        enabled_ids = {e.id for e in enabled}
        expected_prefixes = ["E0", "E1", "E2", "E3", "E4", "E5"]
        for prefix in expected_prefixes:
            matching = [eid for eid in enabled_ids if eid.startswith(prefix)]
            assert matching, (
                f"Edge with prefix '{prefix}' not found in default_enabled_edges()"
            )

    def test_e7_not_in_default_enabled(self) -> None:
        """E7 (contested crime edge) must NEVER appear in the default enabled set."""
        enabled = default_enabled_edges(EDGES_YAML)
        e7_in_enabled = [e for e in enabled if e.id.startswith("E7")]
        assert not e7_in_enabled, "E7 (contested) must not appear in default_enabled_edges()"


# ══════════════════════════════════════════════════════════════════════════════
# C3 — priors.py tests
# ══════════════════════════════════════════════════════════════════════════════


class TestPriorPoint:
    """Tests for priors.point() — Day-1 deterministic central values."""

    def _make_edge(self, **kwargs):
        """Helper: load a single edge from a temporary YAML."""
        import tempfile, yaml as _yaml
        from catalog import load_edges as _load
        data = {
            "id": "TEST_edge",
            "from_node": "a",
            "to_node": "b",
            "point_estimate": 1.0,
            "source": "Test Author 2024",
            "last_validated": "2026-06-14",
            "contested": False,
            "enabled": True,
            **kwargs,
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            _yaml.dump([data], f)
            fname = f.name
        return _load(fname)[0]

    def test_point_normal_returns_mean(self) -> None:
        edge = self._make_edge(dist_type="normal", params={"mean": -0.87, "sd": 0.14})
        assert point(edge) == pytest.approx(-0.87)

    def test_point_lognormal_returns_median(self) -> None:
        # median of lognormal = exp(mu)
        edge = self._make_edge(dist_type="lognormal", params={"mu": 0.5306, "sigma": 0.16})
        assert point(edge) == pytest.approx(math.exp(0.5306), rel=1e-6)

    def test_point_triangular_returns_mode(self) -> None:
        edge = self._make_edge(
            dist_type="triangular", params={"low": 1200.0, "mode": 4700.0, "high": 12300.0}
        )
        assert point(edge) == pytest.approx(4700.0)

    def test_point_uniform_returns_midpoint(self) -> None:
        edge = self._make_edge(
            dist_type="uniform", params={"low": 10600.0, "high": 13100.0}
        )
        assert point(edge) == pytest.approx(11850.0)

    def test_point_point_returns_value(self) -> None:
        edge = self._make_edge(dist_type="point", params={"value": 42.0})
        assert point(edge) == pytest.approx(42.0)


class TestPriorSamplers:
    """Tests for priors.to_distribution() — shape and mean checks for Day-2 MC."""

    N = 100_000  # large enough for reliable mean/shape checks

    def _make_edge(self, **kwargs):
        import tempfile, yaml as _yaml
        from catalog import load_edges as _load
        data = {
            "id": "SAMPLE_edge",
            "from_node": "a",
            "to_node": "b",
            "point_estimate": 1.0,
            "source": "Test Author 2024",
            "last_validated": "2026-06-14",
            "contested": False,
            "enabled": True,
            **kwargs,
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            _yaml.dump([data], f)
            fname = f.name
        return _load(fname)[0]

    def test_normal_sampler_shape_and_mean(self) -> None:
        edge = self._make_edge(dist_type="normal", params={"mean": 5.0, "sd": 1.0})
        sampler = to_distribution(edge)
        samples = sampler(self.N)
        assert samples.shape == (self.N,)
        assert abs(samples.mean() - 5.0) < 0.05  # within 3σ/√N

    def test_lognormal_sampler_median(self) -> None:
        mu = 1.0
        edge = self._make_edge(dist_type="lognormal", params={"mu": mu, "sigma": 0.5})
        sampler = to_distribution(edge)
        samples = sampler(self.N)
        assert samples.shape == (self.N,)
        # median of lognormal = exp(mu)
        assert abs(float(samples.mean()) - math.exp(mu + 0.5**2 / 2)) < 0.2

    def test_triangular_sampler_shape_and_range(self) -> None:
        edge = self._make_edge(
            dist_type="triangular", params={"low": 0.0, "mode": 5.0, "high": 10.0}
        )
        sampler = to_distribution(edge)
        samples = sampler(self.N)
        assert samples.shape == (self.N,)
        assert samples.min() >= -0.001  # no samples below low
        assert samples.max() <= 10.001  # no samples above high

    def test_uniform_sampler_range(self) -> None:
        edge = self._make_edge(
            dist_type="uniform", params={"low": 100.0, "high": 200.0}
        )
        sampler = to_distribution(edge)
        samples = sampler(self.N)
        assert samples.shape == (self.N,)
        assert samples.min() >= 99.99
        assert samples.max() <= 200.01
        assert abs(samples.mean() - 150.0) < 1.0

    def test_point_sampler_constant(self) -> None:
        edge = self._make_edge(dist_type="point", params={"value": 99.0})
        sampler = to_distribution(edge)
        samples = sampler(self.N)
        assert (samples == 99.0).all()


class TestCiToSd:
    """Tests for priors.ci_to_sd() helper."""

    def test_known_ci(self) -> None:
        # E2: ci_low=-1.10, ci_high=-0.64 → sd ≈ 0.14 (using z=1.96)
        sd = ci_to_sd(-1.10, -0.64, z=1.96)
        assert abs(sd - 0.23 / 2) < 0.01

    def test_symmetric(self) -> None:
        # ci_to_sd should be symmetric around the mean
        assert ci_to_sd(1.0, 3.0) == pytest.approx(ci_to_sd(-3.0, -1.0))


# ══════════════════════════════════════════════════════════════════════════════
# C5 — Contested registry tests
# ══════════════════════════════════════════════════════════════════════════════


class TestContestedRegistry:
    """Tests for the contested-edge registry (catalog/contested.yaml)."""

    def test_registry_loads(self) -> None:
        """contested.yaml must load without error."""
        registry = load_contested_registry(CONTESTED_YAML)
        assert registry is not None

    def test_default_enabled_list_present(self) -> None:
        """Registry must contain a 'default_enabled_edges' key."""
        registry = load_contested_registry(CONTESTED_YAML)
        assert "default_enabled_edges" in registry
        assert isinstance(registry["default_enabled_edges"], list)

    def test_contested_edges_list_present(self) -> None:
        """Registry must contain a 'contested_edges' key."""
        registry = load_contested_registry(CONTESTED_YAML)
        assert "contested_edges" in registry

    def test_e7_in_contested_list(self) -> None:
        """E7 must be listed in the contested_edges registry."""
        registry = load_contested_registry(CONTESTED_YAML)
        contested_ids = [c["id"] for c in registry["contested_edges"]]
        assert any("E7" in cid for cid in contested_ids), (
            "E7 (crime edge) must be listed in contested_edges"
        )

    def test_e7_not_in_default_enabled(self) -> None:
        """E7 must NOT be in the default_enabled_edges list."""
        registry = load_contested_registry(CONTESTED_YAML)
        default_ids = registry["default_enabled_edges"]
        assert not any("E7" in eid for eid in default_ids), (
            "E7 must not appear in default_enabled_edges"
        )
