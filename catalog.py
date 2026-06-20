"""
catalog.py — Edge-prior catalog loader and validator for Deferral Ledger.

Enforces SRS EV-1 / C-4: every edge MUST carry a `source` citation and a
`last_validated` date. Any edge missing these fields causes the build to FAIL.

Public API
----------
load_edges(path)          → list[EdgePrior]   (raises on any validation error)
default_enabled_edges()   → list[EdgePrior]   (contested=False, enabled=True)
get_edge(id, edges)       → EdgePrior | None
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from models import EdgePrior

# ── Default path to the catalog ───────────────────────────────────────────────

_DEFAULT_CATALOG_PATH = Path(__file__).parent / "catalog" / "edges.yaml"
_DEFAULT_CONTESTED_PATH = Path(__file__).parent / "catalog" / "contested.yaml"


# ── Custom exceptions ─────────────────────────────────────────────────────────

class CatalogValidationError(RuntimeError):
    """
    Raised when one or more edges fail validation.

    SRS EV-1 / C-4: this MUST fail the build — no uncited number
    reaches the user.
    """


class MissingCitationError(CatalogValidationError):
    """Raised specifically when an edge is missing `source` or `last_validated`."""


# ── load_edges() ──────────────────────────────────────────────────────────────

def load_edges(path: str | Path | None = None) -> list[EdgePrior]:
    """
    Load and validate the edge-prior catalog from a YAML file.

    Validation pipeline (all must pass, else raises CatalogValidationError):
      1. YAML parses without error.
      2. Every raw dict has non-empty `source` and `last_validated` fields
         (MissingCitationError — enforces EV-1 / C-4).
      3. Each dict deserialises into EdgePrior (Pydantic) — checks dist_type /
         params consistency, contested-edge governance, etc.

    Args:
        path: Path to the YAML file. Defaults to catalog/edges.yaml.

    Returns:
        A list of validated EdgePrior instances.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        CatalogValidationError: If any edge fails validation.
    """
    catalog_path = Path(path) if path is not None else _DEFAULT_CATALOG_PATH

    if not catalog_path.exists():
        raise FileNotFoundError(f"Catalog not found: {catalog_path}")

    with open(catalog_path, encoding="utf-8") as fh:
        raw: list[dict[str, Any]] = yaml.safe_load(fh)

    if not isinstance(raw, list):
        raise CatalogValidationError(
            f"Catalog YAML must be a list of edge dicts; got {type(raw).__name__}"
        )

    errors: list[str] = []
    edges: list[EdgePrior] = []

    for i, raw_edge in enumerate(raw):
        edge_id = raw_edge.get("id", f"<index {i}>")

        # ── Citation check (EV-1 / C-4) ──────────────────────────────────────
        source = raw_edge.get("source", "").strip()
        last_validated = raw_edge.get("last_validated", "")

        if not source:
            errors.append(
                f"[EV-1 VIOLATION] Edge '{edge_id}' is missing a `source` citation. "
                "Every numeric prior MUST be traceable to a named study (SRS C-4)."
            )
        if not last_validated:
            errors.append(
                f"[EV-1 VIOLATION] Edge '{edge_id}' is missing `last_validated`. "
                "Every prior MUST carry a last-validated date (SRS LC-1)."
            )

        # ── Pydantic validation ───────────────────────────────────────────────
        try:
            edge = EdgePrior(**raw_edge)
            edges.append(edge)
        except ValidationError as exc:
            for err in exc.errors():
                loc = " → ".join(str(loc_part) for loc_part in err["loc"])
                errors.append(f"Edge '{edge_id}' [{loc}]: {err['msg']}")

    if errors:
        msg = "\n".join(f"  • {e}" for e in errors)
        raise CatalogValidationError(
            f"Catalog validation FAILED ({len(errors)} error(s)):\n{msg}"
        )

    return edges


# ── default_enabled_edges() ───────────────────────────────────────────────────

def default_enabled_edges(path: str | Path | None = None) -> list[EdgePrior]:
    """
    Return the safe default set of edges: enabled=True AND contested=False.

    This is the set used for all public/default runs. Contested edges (e.g., E7
    lead→crime) are excluded here and can only be enabled via explicit, logged
    user consent (SRS FR-DASH-3, FR-GOV-3, RAI-1).

    Args:
        path: Path to the YAML file. Defaults to catalog/edges.yaml.

    Returns:
        Filtered list of EdgePrior instances.
    """
    all_edges = load_edges(path)
    return [e for e in all_edges if e.enabled and not e.contested]


# ── get_edge() ────────────────────────────────────────────────────────────────

def get_edge(edge_id: str, edges: list[EdgePrior]) -> EdgePrior | None:
    """
    Look up an edge by its ID from a pre-loaded edge list.

    Args:
        edge_id: The edge identifier (e.g., 'E2_bll_to_iq').
        edges:   A list of loaded EdgePrior instances.

    Returns:
        The matching EdgePrior, or None if not found.
    """
    for edge in edges:
        if edge.id == edge_id:
            return edge
    return None


# ── load_contested_registry() ─────────────────────────────────────────────────

def load_contested_registry(path: str | Path | None = None) -> dict[str, Any]:
    """
    Load the contested-edge registry from catalog/contested.yaml.

    Returns a dict with keys:
      contested_edges  — list of contested edge IDs with rationale
      default_enabled  — list of edge IDs that are ON by default

    Args:
        path: Path to contested.yaml. Defaults to catalog/contested.yaml.

    Returns:
        Parsed registry dict.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    contested_path = Path(path) if path is not None else _DEFAULT_CONTESTED_PATH
    if not contested_path.exists():
        raise FileNotFoundError(f"Contested registry not found: {contested_path}")
    with open(contested_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ── get_catalog_version() ─────────────────────────────────────────────────────

def get_catalog_version(path: str | Path | None = None) -> str:
    """
    Get a unique version identifier for the catalog.
    Tries git log first, falling back to a SHA-1 content hash of the file.
    """
    import hashlib
    import subprocess

    catalog_path = Path(path) if path is not None else _DEFAULT_CATALOG_PATH
    if not catalog_path.exists():
        return "unknown"

    try:
        # Run git log to get the short SHA of the catalog file
        res = subprocess.run(
            ["git", "log", "-n", "1", "--format=%h", "--", str(catalog_path)],
            capture_output=True,
            text=True,
            cwd=str(catalog_path.parent)
        )
        sha = res.stdout.strip()
        if sha and res.returncode == 0:
            return sha
    except Exception:
        pass

    try:
        hasher = hashlib.sha1()
        with open(catalog_path, "rb") as fh:
            hasher.update(fh.read())
        return hasher.hexdigest()[:8]
    except Exception:
        return "unknown"

