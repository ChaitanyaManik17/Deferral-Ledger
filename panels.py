"""
panels.py — Dashboard analytics panels for Deferral Ledger.

Provides Plotly figures and Pandas DataFrame formatters to render the Deferral
Multiplier posterior, Sobol sensitivity tornado, scenario comparisons, and the
edge citation ledger.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from models import EdgePrior, MultiplierResult, Tract


def plot_m_posterior(
    result: MultiplierResult,
    m_draws: np.ndarray | list[float] | None = None,
    tract: Tract | None = None,
    edges: list[EdgePrior] | None = None,
) -> go.Figure:
    """
    Generate a Plotly histogram/distribution plot of the Deferral Multiplier M posterior.
    
    Draws vertical lines for the mean, 90%/95% CIs, and break-even (M = 1.0).
    Shades the M < 1.0 abstention region.
    """
    # 1. Reconstruct draws if not provided
    if m_draws is None and tract is not None:
        from cascade import compute_multiplier
        from models import ScenarioRun
        from priors import to_distribution
        
        if edges is None:
            from catalog import load_edges
            edges = load_edges()
            
        enabled_edges = set(result.enabled_edges)
        np.random.seed(result.seed)
        
        params = {}
        for edge in edges:
            if edge.id in enabled_edges:
                params[edge.id] = to_distribution(edge)(10000)
                
        scenario = ScenarioRun(
            id=result.run_id,
            tract_id=tract.geoid,
            defer_years=result.defer_years,
            discount_rate=result.discount_rate,
            enabled_edges=result.enabled_edges,
            seed=result.seed,
            n_draws=10000
        )
        m_draws = compute_multiplier(params, tract, scenario)

    # If draws are still unavailable, return a simple warning figure
    if m_draws is None:
        fig = go.Figure()
        fig.add_annotation(
            text="No Monte Carlo draws provided or could be reconstructed.",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="red")
        )
        fig.update_layout(title="M Posterior Distribution", template="plotly_white")
        return fig

    m_arr = np.asarray(m_draws)
    mean_val = float(np.mean(m_arr))

    # 2. Build the Plotly figure
    fig = go.Figure()
    
    # Histogram of M
    fig.add_trace(go.Histogram(
        x=m_arr,
        nbinsx=60,
        name="Posterior Draws",
        marker=dict(color="#3a7fca", line=dict(color="#2962a1", width=0.5)),
        opacity=0.75,
        histnorm="probability density"
    ))

    # Annotate statistic markers
    fig.add_vline(
        x=mean_val,
        line_width=2.5,
        line_color="#e74c3c",
        annotation_text=f"Mean M = {mean_val:.2f}",
        annotation_position="top right"
    )

    if result.ci95:
        fig.add_vline(
            x=result.ci95[0],
            line_width=1.5,
            line_dash="dash",
            line_color="#f39c12",
            annotation_text=f"95% CI Low = {result.ci95[0]:.2f}",
            annotation_position="top left"
        )
        fig.add_vline(
            x=result.ci95[1],
            line_width=1.5,
            line_dash="dash",
            line_color="#f39c12",
            annotation_text=f"95% CI High = {result.ci95[1]:.2f}",
            annotation_position="top right"
        )

    # Break-even line M=1
    fig.add_vline(
        x=1.0,
        line_width=2,
        line_dash="dot",
        line_color="black",
        annotation_text="M=1.0 (Break-even)",
        annotation_position="bottom left"
    )

    # Shade the abstention region (M < 1.0)
    fig.add_vrect(
        x0=min(0.0, float(np.min(m_arr))),
        x1=1.0,
        fillcolor="rgba(231, 76, 60, 0.15)",
        layer="below",
        line_width=0,
        annotation_text="Abstention Region (M < 1.0)",
        annotation_position="inside top left"
    )

    fig.update_layout(
        title="Posterior Distribution of Deferral Multiplier M",
        xaxis_title="Deferral Multiplier M (Future Obligated $ per Deferred $)",
        yaxis_title="Probability Density",
        showlegend=True,
        template="plotly_white",
        hovermode="x unified",
        margin=dict(l=40, r=40, t=60, b=40)
    )

    return fig


def plot_sobol_tornado(
    sobol_res: dict[str, dict[str, float]],
    commission_rec: dict[str, Any],
) -> go.Figure:
    """
    Generate a Plotly horizontal bar chart (tornado plot) of Sobol indices.
    
    Ordered by Total-order (ST) index descending. Annotated with the commission recommendation.
    """
    # 1. Filter out edges with zero contribution for a cleaner visual
    nonzero = {k: v for k, v in sobol_res.items() if v["ST"] > 0.0}
    
    # Fallback if all are zero
    if not nonzero:
        nonzero = sobol_res

    edge_ids = list(nonzero.keys())
    ST_vals = [nonzero[e]["ST"] for e in edge_ids]
    S1_vals = [nonzero[e]["S1"] for e in edge_ids]

    # Readable short names
    short_names = {
        'E0_cost_per_line': 'E0: LSL Replacement Cost/Line',
        'E1_lsl_to_bll': 'E1: LSL ➔ Childhood BLL',
        'E2_bll_to_iq': 'E2: BLL ➔ IQ Loss',
        'E3_iq_to_earnings': 'E3: IQ Loss ➔ Lifetime Earnings',
        'E4_bll_to_sped': 'E4: BLL ➔ Special Ed Rate',
        'E5_bll_to_healthcare': 'E5: BLL ➔ Childhood Healthcare',
        'E6_adult_bll_to_cvd_ckd': 'E6: CVD/CKD Mortality (Adult)',
        'E7_bll_to_crime': 'E7: BLL ➔ Behavior/Crime (Contested)',
    }
    labels = [short_names.get(e, e) for e in edge_ids]

    # 2. Build Figure
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        y=labels,
        x=ST_vals,
        name="ST (Total-order sensitivity)",
        orientation="h",
        marker=dict(color="#e74c3c", line=dict(color="#b03a2e", width=0.5)),
        hovertemplate="Total sensitivity (ST): %{x:.4f}"
    ))

    fig.add_trace(go.Bar(
        y=labels,
        x=S1_vals,
        name="S1 (First-order sensitivity)",
        orientation="h",
        marker=dict(color="#3a7fca", line=dict(color="#2962a1", width=0.5)),
        hovertemplate="First-order sensitivity (S1): %{x:.4f}"
    ))

    # Keep E1 on top by reversing y-axis
    fig.update_yaxes(autorange="reversed")

    fig.update_layout(
        title={
            "text": "Sobol Sensitivity Analysis (Variance Attribution)<br>"
                    "<sup>Recommendation: " + commission_rec.get("plain_language", "") + "</sup>",
            "x": 0.0,
            "y": 0.95,
            "font": dict(size=14)
        },
        xaxis_title="Sobol Index (Share of Variance Explained)",
        yaxis_title="Causal DAG Edge Prior",
        barmode="group",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=100, b=40)
    )

    return fig


def plot_compare_distributions(compare_res: dict) -> go.Figure:
    """
    Generate overlaid distribution plots comparing total costs:
    - Replace Now (defer_years = 0) vs. Defer (defer_years = D)
    - Net Present Value Cost Delta distribution
    """
    fig = go.Figure()

    cost_now = compare_res.get("cost_now_draws")
    cost_defer = compare_res.get("cost_defer_draws")
    cost_delta = compare_res.get("cost_delta_draws")

    if cost_now is None or cost_defer is None or cost_delta is None:
        fig.add_annotation(
            text="Comparison draws not found. Run compare() with MC enabled first.",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="red")
        )
        fig.update_layout(title="Scenario Cost Comparison", template="plotly_white")
        return fig

    # Overlay Now vs Defer
    fig.add_trace(go.Histogram(
        x=cost_now,
        name="Replace Now (Immediate)",
        marker_color="#2ecc71",
        opacity=0.6,
        nbinsx=50,
        histnorm="probability density"
    ))

    fig.add_trace(go.Histogram(
        x=cost_defer,
        name=f"Defer Scenario ({compare_res['defer_result'].defer_years} yr)",
        marker_color="#e74c3c",
        opacity=0.6,
        nbinsx=50,
        histnorm="probability density"
    ))

    mean_delta = compare_res["cost_delta"]["mean"]
    ci90 = compare_res["cost_delta"]["ci90"]

    fig.update_layout(
        title={
            "text": f"Causal Cost Distribution comparison (Present Value)<br>"
                    f"<sup>Mean PV Cost Delta: ${mean_delta:,.2f} (90% CI: ${ci90[0]:,.2f} to ${ci90[1]:,.2f})</sup>",
            "x": 0.0,
            "y": 0.95
        },
        xaxis_title="Present Value Public Cost ($)",
        yaxis_title="Probability Density",
        barmode="overlay",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    return fig


def render_edge_citation_table(
    edges: list[EdgePrior],
    enabled_edge_ids: list[str],
) -> pd.DataFrame:
    """
    Format a Pandas DataFrame summarizing active edges, estimates,
    citations, and contested status.
    """
    rows = []
    enabled_set = set(enabled_edge_ids)
    
    for edge in edges:
        if edge.id in enabled_set:
            ci_str = f"[{edge.ci_low}, {edge.ci_high}]" if edge.ci_low is not None and edge.ci_high is not None else "N/A"
            rows.append({
                "ID": edge.id,
                "Description": f"{edge.from_node} ➔ {edge.to_node}",
                "Point Estimate": edge.point_estimate,
                "95% CI": ci_str,
                "Contested": "Yes (Toggled)" if edge.contested else "No",
                "Last Validated": edge.last_validated,
                "Citation Source": edge.source
            })
            
    df = pd.DataFrame(rows)
    return df
