"""
dag.py — Causal-DAG engine for Deferral Ledger.

Builds a NetworkX DiGraph from the catalog, validates acyclicity (SRS DR-14),
and implements the deterministic single-draw cascade evaluator (V5).
"""

from __future__ import annotations

from datetime import UTC
from pathlib import Path

import networkx as nx
import numpy as np

from cascade import compute_multiplier
from catalog import get_catalog_version, load_edges
from models import EdgePrior, MultiplierResult, ScenarioRun, Tract
from priors import point


def build_dag(edges: list[EdgePrior]) -> nx.DiGraph:
    """
    Build a networkx.DiGraph from a list of EdgePrior instances and validate acyclicity.

    Args:
        edges: List of validated EdgePrior instances.

    Returns:
        A validated networkx.DiGraph.

    Raises:
        ValueError: If a cycle is detected in the graph (SRS DR-14).
    """
    G = nx.DiGraph()

    for edge in edges:
        # Add edge to graph with its ID and prior data
        G.add_edge(edge.from_node, edge.to_node, id=edge.id, prior=edge)

    # Validate acyclicity (fatal error on cycle - SRS DR-14)
    if not nx.is_directed_acyclic_graph(G):
        cycles = list(nx.simple_cycles(G))
        raise ValueError(
            f"Causal-DAG validation FAILED: Cycle(s) detected in the catalog: {cycles}. "
            "The network MUST be a directed acyclic graph (SRS DR-14)."
        )

    return G


def evaluate(
    scenario: ScenarioRun,
    tracts: list[Tract] | Tract,
    catalog_path_or_edges: str | Path | list[EdgePrior] | None = None
) -> MultiplierResult:
    """
    Evaluate the deterministic single-draw cost cascade for a given tract.

    Delegates calculation to cascade.compute_multiplier using length-1 arrays.

    Args:
        scenario: The ScenarioRun input specification.
        tracts: A single Tract or list of Tracts.
        catalog_path_or_edges: Path to edges.yaml or a list of pre-loaded EdgePriors.

    Returns:
        A MultiplierResult containing the deterministic point estimate and contributions.
    """
    # 1. Load catalog edges and build/validate DAG
    if isinstance(catalog_path_or_edges, list):
        edges = catalog_path_or_edges
    else:
        edges = load_edges(catalog_path_or_edges)

    # Validate acyclicity
    build_dag(edges)

    # 2. Extract target tract
    if isinstance(tracts, Tract):
        tract = tracts
    else:
        # Find the tract matching scenario.tract_id
        tract = next((t for t in tracts if t.geoid == scenario.tract_id), None)
        if tract is None:
            raise ValueError(f"Tract '{scenario.tract_id}' not found in the provided tracts list.")

    # 3. Setup point parameter dictionary as shape (1,) arrays
    params: dict[str, np.ndarray] = {}
    for edge in edges:
        params[edge.id] = np.array([point(edge)])

    # 4. Evaluate full multiplier using vectorized cascade
    multiplier_arr = compute_multiplier(params, tract, scenario)
    multiplier_point = float(multiplier_arr[0])

    # 5. Compute individual edge contributions using sub-scenarios
    contribs: dict[str, float] = {}
    enabled_edges = set(scenario.enabled_edges)

    # Helper to calculate single enabled path contribution
    def get_path_multiplier(path_edges: list[str]) -> float:
        sub_sc = scenario.model_copy(update={"enabled_edges": path_edges})
        return float(compute_multiplier(params, tract, sub_sc)[0])

    # Path 1: E1 -> E2 -> E3 (Earnings Loss)
    if (
        "E1_lsl_to_bll" in enabled_edges
        and "E2_bll_to_iq" in enabled_edges
        and "E3_iq_to_earnings" in enabled_edges
    ):
        earnings_val = get_path_multiplier(["E0_cost_per_line", "E1_lsl_to_bll", "E2_bll_to_iq", "E3_iq_to_earnings"])
        contribs["E3_iq_to_earnings"] = earnings_val
        contribs["E2_bll_to_iq"] = earnings_val

    # Path 2: E1 -> E4 (Special Education)
    if "E1_lsl_to_bll" in enabled_edges and "E4_bll_to_sped" in enabled_edges:
        contribs["E4_bll_to_sped"] = get_path_multiplier(["E0_cost_per_line", "E1_lsl_to_bll", "E4_bll_to_sped"])

    # Path 3: E1 -> E5 (Healthcare)
    if "E1_lsl_to_bll" in enabled_edges and "E5_bll_to_healthcare" in enabled_edges:
        contribs["E5_bll_to_healthcare"] = get_path_multiplier(["E0_cost_per_line", "E1_lsl_to_bll", "E5_bll_to_healthcare"])

    # Path 4: E1 -> E6 (Cardiovascular/CKD - Secondary)
    if "E1_lsl_to_bll" in enabled_edges and "E6_adult_bll_to_cvd_ckd" in enabled_edges:
        contribs["E6_adult_bll_to_cvd_ckd"] = get_path_multiplier(["E0_cost_per_line", "E1_lsl_to_bll", "E6_adult_bll_to_cvd_ckd"])

    # Path 5: E1 -> E7 (Crime - Contested)
    if "E1_lsl_to_bll" in enabled_edges and "E7_bll_to_crime" in enabled_edges:
        contribs["E7_bll_to_crime"] = get_path_multiplier(["E0_cost_per_line", "E1_lsl_to_bll", "E7_bll_to_crime"])

    # Intermediate E1 node (sum of all downstream)
    if "E1_lsl_to_bll" in enabled_edges:
        contribs["E1_lsl_to_bll"] = multiplier_point

    # 6. Return MultiplierResult
    from datetime import datetime

    return MultiplierResult(
        run_id=scenario.id,
        tract_id=tract.geoid,
        defer_years=scenario.defer_years,
        discount_rate=scenario.discount_rate,
        multiplier_point=round(multiplier_point, 4),
        per_edge_contribution={k: round(v, 4) for k, v in contribs.items()},
        multiplier_mean=None,
        ci90=None,
        ci95=None,
        p_gt_1=None,
        abstain=False,
        sobol=None,
        enabled_edges=list(enabled_edges),
        catalog_version=get_catalog_version(),
        seed=scenario.seed,
        created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )
