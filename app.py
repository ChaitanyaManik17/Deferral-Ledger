"""
app.py — Interactive web application for Deferral Ledger.

Exposes controls for tract selection, deferral horizon, discounting, and
edge priors. Enforces responsible-AI consent gates for contested paths,
surfaces audit logs and edge lifecycles, and embeds interactive panels.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path


import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

import audit
import brief
import catalog
import models
import montecarlo
import optimize
import panels
import sensitivity
from synth import SYNTH_TRACTS_FILE, generate_tracts

# ── Sleek Custom CSS Styling ──────────────────────────────────────────────────
st.set_page_config(
    page_title="DEFERRAL LEDGER — Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #2c3e50;
        margin-bottom: 0.1rem;
    }
    .subtitle {
        font-size: 1rem;
        color: #7f8c8d;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 15px;
        border-left: 5px solid #2980b9;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 10px;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #2c3e50;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #7f8c8d;
        text-transform: uppercase;
        font-weight: 600;
    }
    .consent-card {
        background-color: #fdf2e9;
        border-radius: 8px;
        padding: 15px;
        border: 1px solid #e59866;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)


# ── Load and Self-Bootstrap Data ──────────────────────────────────────────────
@st.cache_data
def get_all_tracts() -> list[models.Tract]:
    if not SYNTH_TRACTS_FILE.exists():
        return generate_tracts(10, 42)
    with open(SYNTH_TRACTS_FILE, encoding="utf-8") as fh:
        data = json.load(fh)
        return [models.Tract(**d) for d in data]


all_tracts = get_all_tracts()
edges_catalog = catalog.load_edges()


# ── Cached Compute Wrappers for Responsiveness ────────────────────────────────
@st.cache_data
def get_mc_results(scenario_json: str, tract_json: str, n_draws: int, seed: int) -> tuple[models.MultiplierResult, list[float]]:
    sc_data = json.loads(scenario_json)
    tr_data = json.loads(tract_json)
    
    scenario = models.ScenarioRun(**sc_data)
    tract = models.Tract(**tr_data)
    
    res = montecarlo.run_monte_carlo(scenario, tract, edges_catalog, n_draws=n_draws, seed=seed)
    # Extract draws to send back alongside result
    draws = res.mc_draws or []
    return res, draws


@st.cache_data
def get_compare_results(scenario_json: str, tract_json: str, n_draws: int, seed: int) -> dict:
    sc_data = json.loads(scenario_json)
    tr_data = json.loads(tract_json)
    
    scenario = models.ScenarioRun(**sc_data)
    tract = models.Tract(**tr_data)
    
    res = montecarlo.compare(scenario, tract, edges_catalog, n_draws=n_draws, seed=seed)
    return res


@st.cache_data
def get_sobol_results(scenario_json: str, tract_json: str, seed: int) -> tuple[dict, dict]:
    sc_data = json.loads(scenario_json)
    tr_data = json.loads(tract_json)
    
    scenario = models.ScenarioRun(**sc_data)
    tract = models.Tract(**tr_data)
    
    sobol_res = sensitivity.sobol_indices(scenario, tract, edges_catalog, n_base=128, seed=seed)
    rec = sensitivity.commission_study_recommendation(sobol_res, edges_catalog)
    return sobol_res, rec


# ── Title Header ──────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">DEFERRAL LEDGER</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Causal-DAG Decision Support System for Deferred Infrastructure Replacements</div>', unsafe_allow_html=True)


# ── Sidebar Controls ──────────────────────────────────────────────────────────
st.sidebar.header("Simulation Settings")

# 1. Tract Selection
tract_options = {f"Tract {t.geoid} (SVI: {t.svi_percentile})": t for t in all_tracts}
selected_tract_label = st.sidebar.selectbox("Target Census Tract", list(tract_options.keys()), index=0)
selected_tract = tract_options[selected_tract_label]

# 2. Deferral Horizon & Discount Rate
defer_years = st.sidebar.slider("Deferral Horizon (Years)", min_value=0, max_value=15, value=5, step=1)
discount_rate = st.sidebar.slider("Annual Discount Rate (%)", min_value=0.0, max_value=20.0, value=3.0, step=0.5) / 100.0

# 3. MC Specs
n_draws = st.sidebar.selectbox("Monte Carlo Draws (n_draws)", [1, 500, 1000, 5000, 10000], index=3)
seed = st.sidebar.number_input("Random Seed (for Reproducibility)", value=42, step=1)

# 4. Edge Toggles (Governance Panel)
st.sidebar.subheader("Causal Pathway Toggles")
active_edge_ids = []

# Core edges toggles
for edge in edges_catalog:
    if not edge.contested:
        # Core edges default to True
        is_checked = st.sidebar.checkbox(f"{edge.id} (Core)", value=edge.enabled, help=edge.notes)
        if is_checked:
            active_edge_ids.append(edge.id)

# Contested / Secondary edges (E6, E7) requiring explicit consent gate (RAI-1)
st.sidebar.markdown("---")
st.sidebar.markdown("**Contested & Secondary Paths**")

e6_opt = st.sidebar.checkbox("E6: Cardiovascular Mortality (Secondary)", value=False, help="Long-horizon adult cardiovascular deaths risk.")
e7_opt = st.sidebar.checkbox("E7: Juvenile Delinquency & Crime (Contested)", value=False, help="Preschool blood lead delinquency associations.")

# Handle explicit consent gates (attributing logs)
e6_consented = False
e7_consented = False

if e6_opt:
    st.markdown('<div class="consent-card">', unsafe_allow_html=True)
    st.warning("**RAI Governance Flag: E6 Cardiovascular Mortality (Secondary Edge) is selected.**")
    st.info("E6 translates long-term adult cumulative lead exposure into cardiovascular deaths using the EPA Value of Statistical Life (VSL = $13.1M). This secondary long-horizon edge carries wider uncertainty.")
    user_name_e6 = st.text_input("Enter operator name for consent log (E6):", key="consent_e6_user")
    e6_consent_check = st.checkbox("I acknowledge the long-horizon VSL assumptions and consent to enable E6.", key="consent_e6_check")
    st.markdown('</div>', unsafe_allow_html=True)
    
    if e6_consent_check and user_name_e6:
        e6_consented = True
        active_edge_ids.append("E6_adult_bll_to_cvd_ckd")
        
        # Log to db if not already done in session
        consent_key = f"logged_consent_e6_{selected_tract.geoid}_{defer_years}"
        if consent_key not in st.session_state:
            audit.log_consent_event(user_name_e6, "E6_adult_bll_to_cvd_ckd", "enable", f"Operator enabled E6 for tract {selected_tract.geoid}.")
            st.session_state[consent_key] = True

if e7_opt:
    st.markdown('<div class="consent-card">', unsafe_allow_html=True)
    st.warning("**RAI Governance Flag: E7 Juvenile Delinquency (Contested Edge) is selected.**")
    st.info("E7 associates childhood BLL increments with juvenile detention costs. Rationale: Causal pathways to justice involvement are highly sensitive, and default usage can stigmatize communities. Consent is strictly logged.")
    user_name_e7 = st.text_input("Enter operator name for consent log (E7):", key="consent_e7_user")
    e7_consent_check = st.checkbox("I acknowledge the potential neighborhood deficit stigmatization risk and consent to enable E7.", key="consent_e7_check")
    st.markdown('</div>', unsafe_allow_html=True)
    
    if e7_consent_check and user_name_e7:
        e7_consented = True
        active_edge_ids.append("E7_bll_to_crime")
        
        # Log to db if not already done in session
        consent_key = f"logged_consent_e7_{selected_tract.geoid}_{defer_years}"
        if consent_key not in st.session_state:
            audit.log_consent_event(user_name_e7, "E7_bll_to_crime", "enable", f"Operator enabled E7 for tract {selected_tract.geoid}.")
            st.session_state[consent_key] = True


# ── Run Simulations ──────────────────────────────────────────────────────────
scenario_run = models.ScenarioRun(
    id=str(uuid.uuid4()),
    tract_id=selected_tract.geoid,
    defer_years=defer_years,
    discount_rate=discount_rate,
    enabled_edges=active_edge_ids,
    seed=seed,
    n_draws=n_draws
)

# Convert configurations to JSON strings to maintain cacheability in streamlit
sc_json = scenario_run.model_dump_json()
tr_json = selected_tract.model_dump_json()

# Execute MC run (fetches cached or executes)
mc_result, mc_draws_list = get_mc_results(sc_json, tr_json, n_draws, seed)
mc_draws_arr = np.array(mc_draws_list) if mc_draws_list else None

# Execute scenario compare
compare_res = get_compare_results(sc_json, tr_json, n_draws, seed)

# Execute Sobol sensitivity (run if n_draws > 1, else returns empty index)
if n_draws > 1:
    sobol_res, commission_rec = get_sobol_results(sc_json, tr_json, seed)
else:
    sobol_res = {eid: {"S1": 0.0, "ST": 0.0} for eid in active_edge_ids}
    commission_rec = {"top_driver": "N/A", "ST": 0.0, "plain_language": "Run Monte Carlo mode to see global sensitivity study recommendations."}


# ── Display Dashboard Metrics ─────────────────────────────────────────────────
# Avoid showing MC metrics if n_draws = 1 (Deterministic Day 1 behavior)
is_mc = n_draws > 1

col1, col2, col3, col4, col5 = st.columns(5)

# Calculate cost of replacement per line from point estimates
cost_per_line_pt = 4700.0
for e in edges_catalog:
    if e.id == "E0_cost_per_line":
        cost_per_line_pt = e.point_estimate
        break
deferred_repl_cost = selected_tract.lines_count * cost_per_line_pt

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Deferred Cost (D)</div>
        <div class="metric-value">${deferred_repl_cost:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: #f39c12;">
        <div class="metric-label">Deterministic M</div>
        <div class="metric-value">{mc_result.multiplier_point:.4f}</div>
    </div>
    """, unsafe_allow_html=True)
with col3:
    mean_display = f"{mc_result.multiplier_mean:.4f}" if is_mc and mc_result.multiplier_mean is not None else "N/A"
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: #27ae60;">
        <div class="metric-label">Posterior Mean M</div>
        <div class="metric-value">{mean_display}</div>
    </div>
    """, unsafe_allow_html=True)
with col4:
    ci95_display = f"[{mc_result.ci95[0]:.2f}, {mc_result.ci95[1]:.2f}]" if is_mc and mc_result.ci95 else "N/A"
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: #9b59b6;">
        <div class="metric-label">95% Credible Interval</div>
        <div class="metric-value" style="font-size: 1.1rem; padding-top: 10px; padding-bottom: 5px;">{ci95_display}</div>
    </div>
    """, unsafe_allow_html=True)
with col5:
    prob_display = f"{mc_result.p_gt_1:.1%}" if is_mc and mc_result.p_gt_1 is not None else "N/A"
    st.markdown(f"""
    <div class="metric-card" style="border-left-color: #e74c3c;">
        <div class="metric-label">P(M > 1) Obligation</div>
        <div class="metric-value">{prob_display}</div>
    </div>
    """, unsafe_allow_html=True)


# ── Render Prominent Abstention Banner if triggered ───────────────────────────
if mc_result.abstain:
    st.error(f"⚠️ **ABSTENTION CRITERIA MET (SRS FR-ABS-1):** {mc_result.abstain_message}")


# ── Self-Validation: how we catch a wrong answer (Tier 1) ─────────────────────
_val = mc_result.validation
if _val:
    _icon = "🔴" if _val.get("needs_human_review") else "🟢"
    with st.expander(f"{_icon} Self-Validation — how we catch a wrong answer · {_val.get('summary', '')}",
                     expanded=bool(_val.get("needs_human_review"))):
        st.caption(
            "Three independent self-checks run on every result: intermediate **tripwires**, "
            "**literature-range** bounds (Lanphear/Grosse), and **deterministic-vs-Monte-Carlo** "
            "agreement. Any failure routes the run to **human review** — the AI never finalizes a "
            "flagged decision."
        )
        st.dataframe(pd.DataFrame(_val.get("checks", [])), use_container_width=True, hide_index=True)


# ── Dashboard Tabs ────────────────────────────────────────────────────────────
tab_visuals, tab_brief, tab_map, tab_optimizer, tab_governance = st.tabs([
    "📊 Analytics & Plots",
    "📝 Decision Memo (Brief)",
    "🗺️ Interactive Tract Map",
    "💡 Budget Optimizer",
    "🛡️ Governance, Audits & Lifecycle"
])

# ── Tab 1: Visuals & Analytics ────────────────────────────────────────────────
with tab_visuals:
    col_plot1, col_plot2 = st.columns(2)
    
    with col_plot1:
        st.subheader("Multiplier Distribution")
        if is_mc and mc_draws_arr is not None:
            fig_post = panels.plot_m_posterior(mc_result, mc_draws_arr, selected_tract, edges_catalog)
            st.plotly_chart(fig_post, use_container_width=True)
        else:
            st.info("Histogram plots are disabled in deterministic point-estimate mode (n_draws = 1). Enable Monte Carlo draws in the sidebar to view.")

    with col_plot2:
        st.subheader("Sobol Variance Tornado")
        if is_mc:
            fig_tornado = panels.plot_sobol_tornado(sobol_res, commission_rec)
            st.plotly_chart(fig_tornado, use_container_width=True)
        else:
            st.info("Sensitivity analysis is disabled in deterministic point-estimate mode. Enable Monte Carlo draws in the sidebar to view.")

    st.markdown("---")
    col_plot3, col_plot4 = st.columns(2)

    with col_plot3:
        st.subheader("Scenario Cost Overlays")
        if is_mc:
            # Overwrite draws in compare result with lists to align with plot rendering expected structure
            # (or pass them directly as numpy arrays)
            compare_fig_data = compare_res.copy()
            # Ensure draws are arrays for plot_compare_distributions
            compare_fig_data["cost_now_draws"] = np.array(compare_res["cost_now_draws"])
            compare_fig_data["cost_defer_draws"] = np.array(compare_res["cost_defer_draws"])
            compare_fig_data["cost_delta_draws"] = np.array(compare_res["cost_delta_draws"])
            
            fig_compare = panels.plot_compare_distributions(compare_fig_data)
            st.plotly_chart(fig_compare, use_container_width=True)
        else:
            st.info("Scenario cost overlay comparison requires Monte Carlo mode.")

    with col_plot4:
        st.subheader("Active Edge Citations")
        citations_df = panels.render_edge_citation_table(edges_catalog, active_edge_ids)
        st.dataframe(citations_df, use_container_width=True, hide_index=True)


# ── Tab 2: Narrative Brief ────────────────────────────────────────────────────
with tab_brief:
    st.subheader("Generated Policy Brief & Memorandum")

    # Honest narration status: reflects whether the LLM call actually succeeded,
    # not merely whether a key is present (numbers always come from the result objects).
    memo_text, narration_status = brief.generate_brief(
        mc_result, sobol_res, commission_rec, compare_res, edges_catalog, return_status=True
    )
    if narration_status["used_llm"]:
        st.caption(f"🟢 Narration: {narration_status['message']}")
    elif "GEMINI_API_KEY" in os.environ or "GOOGLE_API_KEY" in os.environ:
        st.caption(f"🟠 Narration unavailable — {narration_status['message']}")
    else:
        st.caption(f"ℹ️ {narration_status['message']}")
    st.markdown(memo_text)


# ── Tab 3: Flint Tract Map ────────────────────────────────────────────────────
with tab_map:
    st.subheader("Genesee County Census Tract Visualizer (Flint, MI)")
    st.markdown("Circles represent census tracts; size is proportional to children cohort under 6. The highlighted tract is in **red**.")
    
    # Construct DataFrame for Pydeck from all tracts
    map_rows = []
    for i, t in enumerate(all_tracts):
        # Center coordinates around Flint, MI
        lat = 43.0125 + (i - 5) * 0.015
        lon = -83.6875 + (i - 5) * 0.02
        map_rows.append({
            "geoid": t.geoid,
            "children_under6": t.children_under6,
            "lines_count": t.lines_count,
            "svi_percentile": t.svi_percentile,
            "latitude": lat,
            "longitude": lon,
        })
    map_df = pd.DataFrame(map_rows)
    
    # Style current selection
    map_df["color"] = map_df["geoid"].apply(lambda g: [231, 76, 60, 220] if g == selected_tract.geoid else [41, 128, 185, 140])
    map_df["radius"] = map_df["children_under6"] * 4.5
    
    view_state = pdk.ViewState(
        latitude=43.0125,
        longitude=-83.6875,
        zoom=10,
        pitch=45
    )
    
    layer = pdk.Layer(
        "ScatterplotLayer",
        map_df,
        get_position=["longitude", "latitude"],
        get_color="color",
        get_radius="radius",
        pickable=True,
        auto_highlight=True,
    )
    
    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip={"text": "Tract: {geoid}\nChildren <6: {children_under6}\nLSL Inventory: {lines_count}\nSVI Percentile: {svi_percentile}"}
    )
    
    st.pydeck_chart(deck)


# ── Tab 4: Budget Optimizer ───────────────────────────────────────────────────
with tab_optimizer:
    st.subheader("Greedy Capital Budget Allocator (FR-OPT-1)")
    st.markdown("Proposes replacements under budget limitations to maximize future obligated downstream cost aversion, respecting an equity floor.")
    
    col_opt1, col_opt2, col_opt3 = st.columns(3)
    with col_opt1:
        budget_limit = st.number_input("Total Replacement Budget ($)", value=5000000.0, step=500000.0, format="%f")
    with col_opt2:
        equity_floor = st.slider("High-SVI Earmark Equity Floor (%)", min_value=0, max_value=100, value=30, step=5)
    with col_opt3:
        st.markdown("<br>", unsafe_allow_html=True)
        run_opt = st.button("Optimize Capital Allocation", type="primary")

    if run_opt:
        with st.spinner("Calculating optimal LSL replacement priorities..."):
            opt_df = optimize.optimize_allocations(
                all_tracts,
                edges_catalog,
                budget=budget_limit,
                equity_floor_pct=equity_floor,
                seed=seed,
                n_draws=1000
            )
            
            # Show summary stats
            selected_df = opt_df[opt_df["Selected"] == "YES"]
            total_spent = selected_df["Replacement Cost ($)"].sum()
            total_averted = selected_df["Avoided Obligation ($)"].sum()
            
            c_sum1, c_sum2, c_sum3 = st.columns(3)
            with c_sum1:
                st.metric("Total Budget Allocated", f"${total_spent:,.2f}")
            with c_sum2:
                st.metric("Total Downstream Obligations Averted", f"${total_averted:,.2f}")
            with c_sum3:
                net_roi = total_averted / total_spent if total_spent > 0 else 0.0
                st.metric("Average Portfolio ROI", f"{net_roi:.2f}x")
                
            st.dataframe(opt_df, use_container_width=True, hide_index=True)


# ── Tab 5: Governance, Audits & Lifecycle ──────────────────────────────────────
with tab_governance:
    col_gov1, col_gov2 = st.columns(2)
    
    with col_gov1:
        st.subheader("Causal Prior Expiration & Lifecycle (SRS LC-1, LC-2)")
        
        # Surfacing staleness and validation times
        lifecycle_rows = []
        # Current time reference
        ref_date = datetime(2026, 6, 20)
        
        for edge in edges_catalog:
            val_date = datetime.strptime(edge.last_validated, "%Y-%m-%d")
            age_days = (ref_date - val_date).days
            
            # An edge is flagged as stale if older than 365 days
            is_stale = age_days > 365
            stale_status = "⚠️ STALE" if is_stale else "✅ Current"
            
            lifecycle_rows.append({
                "Edge ID": edge.id,
                "Last Validated": edge.last_validated,
                "Age (Days)": age_days,
                "Status": stale_status,
                "Source Reference": edge.source[:80] + "..."
            })
            
        lifecycle_df = pd.DataFrame(lifecycle_rows)
        
        # Display validation table
        st.dataframe(lifecycle_df, use_container_width=True, hide_index=True)
        
        # Surface one-line recalibration trigger warning (RAI-4)
        st.warning(
            "📢 **RECALIBRATION ALERT:** The EPA revised the national LSL count from ~9.2M to ~4.7M on 25 Nov 2025. "
            "Model parameters in edges.yaml require validation adjustments if applied upstream (NFR-REPRO-1)."
        )

    with col_gov2:
        st.subheader("Immutable Governance Logs (SQLite Store)")
        
        # 1. Show Consent Events
        st.markdown("**Contested-Edge Explicit Consent Log (FR-GOV-3, RAI-1)**")
        consent_rows = audit.get_consent_logs()
        if consent_rows:
            consent_df = pd.DataFrame(consent_rows)
            st.dataframe(consent_df, use_container_width=True, hide_index=True)
        else:
            st.info("No contested consent events logged in the database yet.")
            
        # 2. Show Raw Stored Audit Record Details
        st.markdown(f"**Current Run Audit Snapshot (`run_id`: {mc_result.run_id})**")
        db_record = audit.get_audit_record(mc_result.run_id)
        if db_record:
            st.json(db_record.model_dump())
        else:
            st.info("Current run audit record is persisting to the SQLite store.")
