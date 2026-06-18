"""
dag.py — Causal-DAG engine for Deferral Ledger.

Builds a NetworkX DiGraph from the catalog, validates acyclicity (SRS DR-14),
and implements the deterministic single-draw cascade evaluator (V5).
"""

from __future__ import annotations

from pathlib import Path
import networkx as nx
from models import Tract, ScenarioRun, MultiplierResult, EdgePrior
from catalog import load_edges, get_edge
from priors import point

# ── Constants for CVD & Crime Cost Calculations ──────────────────────────────
VSL_USD = 13_100_000.0           # Value of Statistical Life (EPA 2024)
CVD_BASELINE_RISK = 0.02         # 2% baseline risk of CVD mortality
INCARCERATION_COST_USD = 47_500.0 # Midpoint of BJS 35k-60k
CRIME_BASELINE_RATE = 0.01       # 1% baseline juvenile detention rate


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

    Walks the causal DAG using each edge's point estimate, combining with the
    scenario properties to compute the deferral multiplier M and per-edge contribution.

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

    # 3. Setup scenario parameters
    defer_years = scenario.defer_years
    discount_rate = scenario.discount_rate
    lines_count = tract.lines_count
    children_under6 = tract.children_under6
    enabled_edges = set(scenario.enabled_edges)

    # 4. Read edge priors (point estimates)
    # Helper to get point estimate or default if edge is absent
    def get_point(edge_id: str, default: float) -> float:
        edge = get_edge(edge_id, edges)
        if edge is not None and edge.id in enabled_edges:
            return point(edge)
        return default

    # Denominator driver
    cost_per_line = get_point("E0_cost_per_line", 4700.0)

    # Exposure & BLL factors
    bll_increment_factor = get_point("E1_lsl_to_bll", 1.5)
    bll_to_iq_factor = get_point("E2_bll_to_iq", -0.87)

    # Outcome factors
    iq_to_earnings_factor = get_point("E3_iq_to_earnings", 11850.0)
    bll_to_sped_factor = get_point("E4_bll_to_sped", 11000.0)
    bll_to_healthcare_factor = get_point("E5_bll_to_healthcare", 7500.0)
    adult_bll_to_cvd_ckd_factor = get_point("E6_adult_bll_to_cvd_ckd", 1.70)
    bll_to_crime_factor = get_point("E7_bll_to_crime", 1.15)

    # 5. Deferred Dollars (Denominator)
    deferred_dollars = lines_count * cost_per_line

    # 6. Calculate pathway costs (discounted to year 0)
    discount_factor = (1.0 + discount_rate) ** -defer_years

    # Shared exposure inputs
    bll_increment_per_child = defer_years * bll_increment_factor

    # Path -> E2 -> E3 (IQ & Earnings Loss)
    if (
        "E1_lsl_to_bll" in enabled_edges
        and "E2_bll_to_iq" in enabled_edges
        and "E3_iq_to_earnings" in enabled_edges
    ):
        undiscounted_earnings = children_under6 * bll_increment_per_child * abs(bll_to_iq_factor) * iq_to_earnings_factor
        earnings_cost = undiscounted_earnings * discount_factor
    else:
        earnings_cost = 0.0

    # Path 2: E1 -> E4 (Special Education)
    if "E1_lsl_to_bll" in enabled_edges and "E4_bll_to_sped" in enabled_edges:
        undiscounted_sped = children_under6 * bll_increment_per_child * bll_to_sped_factor
        sped_cost = undiscounted_sped * discount_factor
    else:
        sped_cost = 0.0

    # Path 3: E1 -> E5 (Healthcare)
    if "E1_lsl_to_bll" in enabled_edges and "E5_bll_to_healthcare" in enabled_edges:
        undiscounted_healthcare = children_under6 * bll_increment_per_child * bll_to_healthcare_factor
        healthcare_cost = undiscounted_healthcare * discount_factor
    else:
        healthcare_cost = 0.0

    # Path 4: E1 -> E6 (Cardiovascular/CKD - Secondary)
    if "E1_lsl_to_bll" in enabled_edges and "E6_adult_bll_to_cvd_ckd" in enabled_edges:
        # HR Risk cost conversion
        cvd_cost_per_child = (
            max(0.0, (adult_bll_to_cvd_ckd_factor - 1.0))
            * (bll_increment_per_child / 5.7)
            * CVD_BASELINE_RISK
            * VSL_USD
        )
        undiscounted_cvd = children_under6 * cvd_cost_per_child
        cvd_cost = undiscounted_cvd * discount_factor
    else:
        cvd_cost = 0.0

    # Path 5: E1 -> E7 (Crime - Contested)
    if "E1_lsl_to_bll" in enabled_edges and "E7_bll_to_crime" in enabled_edges:
        # RR Risk cost conversion
        crime_cost_per_child = (
            max(0.0, (bll_to_crime_factor - 1.0))
            * bll_increment_per_child
            * CRIME_BASELINE_RATE
            * INCARCERATION_COST_USD
        )
        undiscounted_crime = children_under6 * crime_cost_per_child
        crime_cost = undiscounted_crime * discount_factor
    else:
        crime_cost = 0.0

    # 7. Calculate Multiplier and Contributions
    total_downstream = earnings_cost + sped_cost + healthcare_cost + cvd_cost + crime_cost

    if deferred_dollars > 0:
        multiplier_point = total_downstream / deferred_dollars
    else:
        multiplier_point = 0.0

    # Calculate individual edge contributions (attributing cost / deferred_dollars)
    contribs: dict[str, float] = {}

    if deferred_dollars > 0:
        # Downstream leaf nodes
        if "E3_iq_to_earnings" in enabled_edges:
            contribs["E3_iq_to_earnings"] = earnings_cost / deferred_dollars
        if "E4_bll_to_sped" in enabled_edges:
            contribs["E4_bll_to_sped"] = sped_cost / deferred_dollars
        if "E5_bll_to_healthcare" in enabled_edges:
            contribs["E5_bll_to_healthcare"] = healthcare_cost / deferred_dollars
        if "E6_adult_bll_to_cvd_ckd" in enabled_edges:
            contribs["E6_adult_bll_to_cvd_ckd"] = cvd_cost / deferred_dollars
        if "E7_bll_to_crime" in enabled_edges:
            contribs["E7_bll_to_crime"] = crime_cost / deferred_dollars

        # Intermediate nodes attribute the sum of paths flowing through them
        if "E1_lsl_to_bll" in enabled_edges:
            contribs["E1_lsl_to_bll"] = total_downstream / deferred_dollars
        if "E2_bll_to_iq" in enabled_edges:
            contribs["E2_bll_to_iq"] = earnings_cost / deferred_dollars

    # 8. Return MultiplierResult
    from datetime import datetime, timezone
    import uuid

    return MultiplierResult(
        run_id=scenario.id,
        tract_id=tract.geoid,
        defer_years=defer_years,
        discount_rate=discount_rate,
        multiplier_point=round(multiplier_point, 4),
        per_edge_contribution={k: round(v, 4) for k, v in contribs.items()},
        multiplier_mean=None,
        ci90=None,
        ci95=None,
        p_gt_1=None,
        abstain=False,
        sobol=None,
        enabled_edges=list(enabled_edges),
        catalog_version="07ae2eb70c80", # Using Chaitanya's commit SHA
        seed=scenario.seed,
        created_at=datetime.now(timezone.utc).isoformat() + "Z"
    )
