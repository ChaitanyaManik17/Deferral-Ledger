"""
app.py — Interactive web application for Deferral Ledger.

Re-skinned to the design comp (docs/Design): dark sidebar of controls, light
main with KPI row, cascade strip, status banners, and five tabbed panels.
All numbers come from the live engine (montecarlo / sensitivity / gates /
validation / optimize / brief); this file only orchestrates + renders.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

import audit
import brief
import cascade
import catalog
import models
import montecarlo
import optimize
import sensitivity
import ui
from priors import point
from synth import SYNTH_TRACTS_FILE, generate_tracts

st.set_page_config(page_title="Deferral Ledger — Cascade-Cost Engine", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown(ui.inject_global_css(), unsafe_allow_html=True)


# ── Load + self-bootstrap data ────────────────────────────────────────────────
@st.cache_data
def get_all_tracts() -> list[models.Tract]:
    if not SYNTH_TRACTS_FILE.exists():
        return generate_tracts(10, 42)
    with open(SYNTH_TRACTS_FILE, encoding="utf-8") as fh:
        return [models.Tract(**d) for d in json.load(fh)]


all_tracts = get_all_tracts()
edges_catalog = catalog.load_edges()


# ── Cached compute wrappers ───────────────────────────────────────────────────
@st.cache_data
def get_mc_results(scenario_json: str, tract_json: str, n_draws: int, seed: int):
    scenario = models.ScenarioRun(**json.loads(scenario_json))
    tract = models.Tract(**json.loads(tract_json))
    res = montecarlo.run_monte_carlo(scenario, tract, edges_catalog, n_draws=n_draws, seed=seed)
    return res, (res.mc_draws or [])


@st.cache_data
def get_compare_results(scenario_json: str, tract_json: str, n_draws: int, seed: int) -> dict:
    scenario = models.ScenarioRun(**json.loads(scenario_json))
    tract = models.Tract(**json.loads(tract_json))
    return montecarlo.compare(scenario, tract, edges_catalog, n_draws=n_draws, seed=seed)


@st.cache_data
def get_sobol_results(scenario_json: str, tract_json: str, seed: int):
    scenario = models.ScenarioRun(**json.loads(scenario_json))
    tract = models.Tract(**json.loads(tract_json))
    sobol_res = sensitivity.sobol_indices(scenario, tract, edges_catalog, n_base=128, seed=seed)
    rec = sensitivity.commission_study_recommendation(sobol_res, edges_catalog)
    return sobol_res, rec


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
sb = st.sidebar
sb.markdown(ui.sidebar_brand_html(), unsafe_allow_html=True)

sb.markdown(ui.sidebar_section_label("Simulation"), unsafe_allow_html=True)
tract_options = {f"Tract …{t.geoid[-6:]} · SVI {t.svi_percentile:.3f}": t for t in all_tracts}
selected_label = sb.selectbox("Target Census Tract", list(tract_options.keys()), index=0)
selected_tract = tract_options[selected_label]

defer_years = sb.slider("Deferral Horizon (years)", 1, 15, 5, 1)
discount_pct = sb.slider("Annual Discount Rate (%)", 0.0, 8.0, 3.0, 0.5)
discount_rate = discount_pct / 100.0
n_draws = sb.selectbox("Monte-Carlo Draws", [1, 1000, 5000, 10000], index=2)
seed = int(sb.number_input("Random Seed", value=42, step=1))

sb.markdown(ui.sidebar_section_label("Causal Pathways"), unsafe_allow_html=True)
sb.caption("Toggle which edges enter the figure. E0 is the cost denominator.")
active_edge_ids: list[str] = []
for edge in edges_catalog:
    if edge.contested or edge.id in ("E6_adult_bll_to_cvd_ckd", "E7_bll_to_crime"):
        continue
    locked = edge.id == "E0_cost_per_line"
    label = f"{ui.SHORT_LABELS.get(edge.id, edge.id)}" + (" · LOCK" if locked else "")
    checked = sb.checkbox(label, value=True, disabled=locked, key=f"edge_{edge.id}", help=edge.notes)
    if checked or locked:
        active_edge_ids.append(edge.id)

sb.markdown(ui.sidebar_section_label("Contested &amp; Secondary", ui.AMBER), unsafe_allow_html=True)
sb.caption("Off by default. Enabling writes a logged consent event.")
e6_opt = sb.checkbox("E6: Cardiovascular / CKD (secondary)", value=False)
e7_opt = sb.checkbox("E7: Juvenile delinquency & crime (contested)", value=False)

if e6_opt:
    sb.warning("E6 uses a long-horizon VSL ($13.1M) assumption with wide uncertainty.")
    u6 = sb.text_input("Operator name (E6 consent)", key="consent_e6_user")
    if sb.checkbox("I consent to enable E6.", key="consent_e6_check") and u6:
        active_edge_ids.append("E6_adult_bll_to_cvd_ckd")
        k = f"logged_e6_{selected_tract.geoid}_{defer_years}"
        if k not in st.session_state:
            audit.log_consent_event(u6, "E6_adult_bll_to_cvd_ckd", "enable",
                                    f"Operator enabled E6 for tract {selected_tract.geoid}.")
            st.session_state[k] = True

if e7_opt:
    sb.warning("E7 (lead→crime) can stigmatize communities; consent is strictly logged.")
    u7 = sb.text_input("Operator name (E7 consent)", key="consent_e7_user")
    if sb.checkbox("I consent to enable E7.", key="consent_e7_check") and u7:
        active_edge_ids.append("E7_bll_to_crime")
        k = f"logged_e7_{selected_tract.geoid}_{defer_years}"
        if k not in st.session_state:
            audit.log_consent_event(u7, "E7_bll_to_crime", "enable",
                                    f"Operator enabled E7 for tract {selected_tract.geoid}.")
            st.session_state[k] = True


# ══════════════════════════════════════════════════════════════════════════════
# COMPUTE
# ══════════════════════════════════════════════════════════════════════════════
scenario_run = models.ScenarioRun(
    id=str(uuid.uuid4()), tract_id=selected_tract.geoid, defer_years=defer_years,
    discount_rate=discount_rate, enabled_edges=active_edge_ids, seed=seed, n_draws=n_draws,
)
sc_json = scenario_run.model_dump_json()
tr_json = selected_tract.model_dump_json()

mc_result, mc_draws_list = get_mc_results(sc_json, tr_json, n_draws, seed)
mc_draws_arr = np.array(mc_draws_list) if mc_draws_list else None
compare_res = get_compare_results(sc_json, tr_json, n_draws, seed)

is_mc = n_draws > 1
if is_mc:
    sobol_res, commission_rec = get_sobol_results(sc_json, tr_json, seed)
else:
    sobol_res = {eid: {"S1": 0.0, "ST": 0.0} for eid in active_edge_ids}
    commission_rec = {"top_driver": "—", "ST": 0.0,
                      "plain_language": "Enable Monte-Carlo mode to compute global sensitivity."}

sb.markdown(ui.reproducibility_card_html(mc_result.catalog_version, seed), unsafe_allow_html=True)

# Cascade-strip intermediates (deterministic, point estimates)
point_params = {e.id: np.array([point(e)]) for e in edges_catalog}
comp = cascade.compute_components(point_params, selected_tract, scenario_run)
bll_inc = float(comp["bll_increment_per_child"][0])
iq_loss = float(comp["iq_loss_per_child"][0])
earn_pc = float(comp["earnings_per_child"][0])

cost_per_line_pt = next((e.point_estimate for e in edges_catalog if e.id == "E0_cost_per_line"), 4700.0)
deferred_cost = selected_tract.lines_count * cost_per_line_pt
mean_or_point = mc_result.multiplier_mean if (is_mc and mc_result.multiplier_mean is not None) else mc_result.multiplier_point
obligated = mean_or_point * deferred_cost
run_short = mc_result.run_id[:8]


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — header, KPIs, banner, cascade strip
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(ui.header_html(
    "Cascade-Cost Decision Support",
    "Posterior, sensitivity, scenario overlay, brief, optimizer and audit — one synthetic LSL-deferral scenario.",
    "…" + selected_tract.geoid[-6:], defer_years, discount_pct, run_short,
), unsafe_allow_html=True)

st.markdown(ui.kpi_row_html(
    deferred_cost, mc_result.multiplier_point, mc_result.multiplier_mean,
    mc_result.ci95, mc_result.ci90, mc_result.p_gt_1,
    selected_tract.lines_count, n_draws, is_mc,
), unsafe_allow_html=True)

if mc_result.abstain:
    st.markdown(ui.abstention_banner_html(mc_result.abstain_message or ""), unsafe_allow_html=True)
elif mc_result.validation:
    st.markdown(ui.validation_banner_html(mc_result.validation), unsafe_allow_html=True)

st.markdown(ui.cascade_strip_html(
    deferred_cost, bll_inc, selected_tract.children_under6, iq_loss, earn_pc,
    obligated, mean_or_point, defer_years,
), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_an, tab_memo, tab_map, tab_opt, tab_gov = st.tabs(
    ["Analytics & Plots", "Decision Memo", "Tract Map", "Budget Optimizer", "Governance & Audits"]
)

# ── Analytics ──────────────────────────────────────────────────────────────────
with tab_an:
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown(ui.posterior_bars_html(
            mc_draws_arr if mc_draws_arr is not None else [],
            mc_result.ci90, mc_result.ci95,
            mean_or_point, mc_result.multiplier_point, n_draws, seed,
        ), unsafe_allow_html=True)
    with c2:
        st.markdown(ui.tornado_html(sobol_res, commission_rec), unsafe_allow_html=True)

    st.write("")
    c3, c4 = st.columns([3, 2])
    with c3:
        st.markdown(ui.scenario_overlay_html(compare_res, defer_years), unsafe_allow_html=True)
    with c4:
        st.markdown(ui.citations_html(edges_catalog, active_edge_ids), unsafe_allow_html=True)

# ── Decision Memo ──────────────────────────────────────────────────────────────
with tab_memo:
    memo_text, narration_status = brief.generate_brief(
        mc_result, sobol_res, commission_rec, compare_res, edges_catalog, return_status=True
    )
    if narration_status["used_llm"]:
        st.caption(f"🟢 Narration grounded in C-MC outputs · {narration_status['message']} · numbers never LLM-generated")
    elif "GEMINI_API_KEY" in os.environ or "GOOGLE_API_KEY" in os.environ:
        st.caption(f"🟠 Narration unavailable — {narration_status['message']}")
    else:
        st.caption(f"ℹ️ {narration_status['message']}")
    with st.container(border=True):
        # Escape '$' so Streamlit doesn't treat dollar amounts as LaTeX math ($...$).
        st.markdown(memo_text.replace("$", "\\$"))

# ── Tract Map ──────────────────────────────────────────────────────────────────
with tab_map:
    st.markdown(ui.map_schematic_html(all_tracts, selected_tract.geoid), unsafe_allow_html=True)

# ── Budget Optimizer ───────────────────────────────────────────────────────────
with tab_opt:
    with st.container(border=True):
        st.markdown("##### Greedy capital budget allocator")
        st.caption("Proposes replacements under a budget cap to maximize averted downstream obligation, "
                   "respecting a high-SVI equity floor. **Proposes; a human allocates.**")
        oc1, oc2, oc3 = st.columns([1.2, 1.4, 1])
        with oc1:
            budget_limit = st.number_input("Total Replacement Budget ($)", value=5_000_000.0, step=500_000.0)
        with oc2:
            equity_floor = st.slider("High-SVI Equity Floor (%)", 0, 60, 30, 5)
        with oc3:
            st.write("")
            run_opt = st.button("Optimize allocation", type="primary", use_container_width=True)

    if run_opt:
        with st.spinner("Optimizing capital allocation…"):
            opt_df = optimize.optimize_allocations(
                all_tracts, edges_catalog, budget=budget_limit,
                equity_floor_pct=equity_floor, seed=seed, n_draws=1000,
            )
        sel = opt_df[opt_df["Selected"].astype(str).str.upper() == "YES"]
        allocated = float(sel["Replacement Cost ($)"].sum())
        averted = float(sel["Avoided Obligation ($)"].sum())
        roi = averted / allocated if allocated > 0 else 0.0
        st.markdown(ui.optimizer_kpis_html(allocated, averted, roi), unsafe_allow_html=True)
        st.markdown(ui.optimizer_table_html(opt_df), unsafe_allow_html=True)
    else:
        st.caption("Set a budget and equity floor, then run the allocator.")

# ── Governance & Audits ────────────────────────────────────────────────────────
with tab_gov:
    g1, g2 = st.columns([1.1, 1])
    with g1:
        st.markdown(ui.lifecycle_table_html(edges_catalog, datetime(2026, 6, 21)), unsafe_allow_html=True)
        st.markdown(ui.recalibration_alert_html(), unsafe_allow_html=True)
    with g2:
        st.markdown(ui.consent_log_html(audit.get_consent_logs()), unsafe_allow_html=True)
        rec = audit.get_audit_record(mc_result.run_id)
        if rec:
            audit_dict = rec.model_dump()
        else:  # fall back to in-memory data so the snapshot is never empty
            audit_dict = {
                "run_id": mc_result.run_id,
                "user": "system_operator",
                "inputs_snapshot_ref": "data/synthetic/synthetic_tracts.json",
                "catalog_version": mc_result.catalog_version,
                "tract": selected_tract.geoid,
                "defer_years": defer_years,
                "seed": seed,
                "overrides": [],
                "contested_edges_enabled": [
                    e for e in ("E6_adult_bll_to_cvd_ckd", "E7_bll_to_crime") if e in active_edge_ids
                ],
                "timestamp": mc_result.created_at,
            }
        st.markdown(
            f"<div style='background:{ui.INK};border-radius:13px;padding:18px 22px;margin-top:18px'>"
            f"<div style='font-size:13px;font-weight:700;color:#fff;font-family:{ui.DISPLAY}'>Immutable run audit snapshot</div>"
            f"<div style='font-family:{ui.MONO};font-size:10.5px;color:{ui.MUTED_D2};margin-top:2px'>"
            f"run_id {run_short} · persisted to SQLite</div></div>",
            unsafe_allow_html=True,
        )
        st.json(audit_dict)
