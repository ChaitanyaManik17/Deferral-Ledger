"""
ui.py — Design layer for Deferral Ledger (re-skin to the design comp).

Provides:
  - inject_global_css(): Google Fonts + dark sidebar + card/banner/tab styling.
  - Pure HTML builders (header, KPI row, banners, cascade strip, citations,
    lifecycle, consent log, audit JSON, optimizer table, schematic map).
  - HTML/CSS chart builders (posterior bars, Sobol tornado, scenario overlay)
    computed from the REAL Monte-Carlo arrays — no charting library.

All builders return strings for st.markdown(..., unsafe_allow_html=True).
Numbers come from the live engine; this module only renders.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np

# ── Palette (extracted from docs/Design/Deferral Ledger.dc.html) ──────────────
INK = "#0f1726"
PANEL = "#172036"
SIDE_BORDER = "#283450"
MUTED_D = "#6b7790"
MUTED_D2 = "#9aa6bd"
TEXT_D = "#cfd6e2"
BG = "#eef1f5"
CARD_BORDER = "#e6eaef"
MUTED = "#5b6675"
MUTED2 = "#9aa3b0"
GREEN = "#15976a"
GREEN_ACCENT = "#34d98a"
GREEN_TINT = "#eafaf2"
GREEN_BORDER = "#c2ecd6"
RED = "#e25247"
RED_TINT = "#fdf1f0"
RED_BORDER = "#f6d4d1"
AMBER = "#c98a2e"
AMBER_BAN = "#fff8ed"
AMBER_BORDER = "#f0d9a8"
BLUE = "#2c5fb3"
BLUE_TINT = "#cfe0fb"
BLUE_BG = "#eef4ff"
BAR_GREY = "#dbe1e8"

DISPLAY = "'Space Grotesk',sans-serif"
BODY = "'Manrope',sans-serif"
MONO = "'IBM Plex Mono',monospace"

SHORT_LABELS = {
    "E0_cost_per_line": "E0: cost/line",
    "E1_lsl_to_bll": "E1: LSL→BLL",
    "E2_bll_to_iq": "E2: BLL→IQ",
    "E3_iq_to_earnings": "E3: IQ→earnings",
    "E4_bll_to_sped": "E4: BLL→SpEd",
    "E5_bll_to_healthcare": "E5: BLL→healthcare",
    "E6_adult_bll_to_cvd_ckd": "E6: adult CVD/CKD",
    "E7_bll_to_crime": "E7: BLL→crime",
}


# ── Formatters ────────────────────────────────────────────────────────────────
def usd(n: float) -> str:
    return "$" + format(int(round(n)), ",")


def usd_m(n: float) -> str:
    return f"${n / 1e6:.2f}M"


def _card(inner: str, pad: str = "22px 24px", extra: str = "") -> str:
    return (
        f"<div style='background:#fff;border:1px solid {CARD_BORDER};border-radius:13px;"
        f"padding:{pad};{extra}'>{inner}</div>"
    )


# ── Global CSS (plain string — no f-string, so CSS braces are safe) ───────────
def inject_global_css() -> str:
    return """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] { font-family:'Manrope',sans-serif; }
.stApp { background:#eef1f5; }
header[data-testid="stHeader"] { background:transparent; height:0; }
#MainMenu, footer { visibility:hidden; }
.block-container { padding-top:1.4rem; padding-bottom:3rem; max-width:1500px; }

h1,h2,h3,h4 { font-family:'Space Grotesk',sans-serif; letter-spacing:-.01em; }

/* ---- Dark sidebar ---- */
section[data-testid="stSidebar"] { background:#0f1726; border-right:1px solid #1d2740; }
section[data-testid="stSidebar"] * { color:#cfd6e2; }
section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] .stMarkdown p { color:#9aa6bd !important; font-weight:600; }
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
  background:#172036; border:1px solid #283450; color:#e7ecf4; border-radius:7px;
  font-family:'IBM Plex Mono',monospace; font-size:12.5px;
}
section[data-testid="stSidebar"] [data-testid="stNumberInput"] input {
  background:#172036; border:1px solid #283450; color:#e7ecf4; border-radius:7px;
  font-family:'IBM Plex Mono',monospace;
}
section[data-testid="stSidebar"] [data-testid="stTextInput"] input {
  background:#172036; border:1px solid #283450; color:#e7ecf4; border-radius:7px;
}
section[data-testid="stSidebar"] [data-baseweb="checkbox"] { margin-bottom:2px; }
section[data-testid="stSidebar"] hr { border-color:#1d2740; }

/* ---- Tabs ---- */
button[data-baseweb="tab"] { font-family:'Manrope',sans-serif; font-weight:700; font-size:13.5px; color:#9aa3b0; }
button[data-baseweb="tab"][aria-selected="true"] { color:#0f1726; }
div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] { background-color:#15976a; }

/* ---- Scrollbars ---- */
::-webkit-scrollbar { width:9px; height:9px; }
::-webkit-scrollbar-thumb { background:#c4ccd8; border-radius:6px; }
section[data-testid="stSidebar"] ::-webkit-scrollbar-thumb { background:#2a3650; }
</style>
"""


# ── Sidebar brand ─────────────────────────────────────────────────────────────
def sidebar_brand_html() -> str:
    return (
        f"<div style='line-height:1.1;padding:4px 0 12px'>"
        f"<div style='font-family:{DISPLAY};font-weight:700;font-size:20px;color:#fff;letter-spacing:-.01em'>"
        f"Deferral<span style='color:{GREEN_ACCENT}'>·</span>Ledger</div>"
        f"<div style='font-size:10px;color:{MUTED_D};letter-spacing:.16em;margin-top:4px'>CASCADE-COST ENGINE</div>"
        f"</div>"
    )


def sidebar_section_label(text: str, color: str = MUTED_D) -> str:
    return (
        f"<div style='font-family:{DISPLAY};font-size:11px;letter-spacing:.13em;text-transform:uppercase;"
        f"color:{color};font-weight:600;margin:6px 0 2px'>{text}</div>"
    )


def reproducibility_card_html(catalog_version: str, seed: int, snapshot: str = "synthetic_tracts") -> str:
    row = lambda k, v: (
        f"<div style='display:flex;justify-content:space-between;margin-bottom:5px'>"
        f"<span style='font-size:10.5px;color:{MUTED_D}'>{k}</span>"
        f"<span style='font-family:{MONO};font-size:10.5px;color:{MUTED_D2}'>{v}</span></div>"
    )
    return (
        f"<div style='margin-top:10px;padding:13px 14px;background:#0b1322;border:1px solid #1d2740;border-radius:9px'>"
        f"<div style='font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:{MUTED_D};margin-bottom:9px;font-weight:600'>Reproducibility</div>"
        f"{row('catalog', catalog_version[:7])}{row('seed', seed)}{row('snapshot', snapshot)}</div>"
    )


# ── Header ────────────────────────────────────────────────────────────────────
def header_html(title: str, sub: str, tract_short: str, defer_years: int, discount_pct: float, run_short: str) -> str:
    pill = lambda txt, mono=False: (
        f"<span style='font-size:11px;font-weight:600;color:#334155;border:1px solid {CARD_BORDER};"
        f"padding:6px 12px;border-radius:20px;background:#f5f7fa;{'font-family:' + MONO if mono else ''}'>{txt}</span>"
    )
    return (
        f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:18px'>"
        f"<div><div style='display:flex;align-items:center;gap:11px'>"
        f"<h1 style='font-size:21px;font-weight:700;color:{INK};margin:0'>{title}</h1>"
        f"<span style='font-size:10.5px;font-weight:700;color:{RED};border:1px solid {RED_BORDER};"
        f"padding:3px 9px;border-radius:20px;background:{RED_TINT}'>SYNTHETIC DATA</span></div>"
        f"<div style='font-size:12.5px;color:{MUTED};margin-top:3px;font-weight:500'>{sub}</div></div>"
        f"<div style='display:flex;align-items:center;gap:9px'>"
        f"{pill('Tract ' + tract_short, True)}{pill(f'Defer {defer_years}yr · {discount_pct:.1f}%')}{pill('run ' + run_short, True)}"
        f"</div></div>"
    )


# ── KPI row ───────────────────────────────────────────────────────────────────
def _kpi(label: str, value: str, sub: str, *, value_color: str = INK, border: str = CARD_BORDER,
         label_color: str = MUTED, value_size: str = "25px", extra: str = "") -> str:
    return (
        f"<div style='background:#fff;border:1px solid {border};border-radius:13px;padding:17px 18px;{extra}'>"
        f"<div style='font-size:10.5px;letter-spacing:.05em;text-transform:uppercase;color:{label_color};font-weight:700;margin-bottom:11px'>{label}</div>"
        f"<div style='font-family:{DISPLAY};font-size:{value_size};font-weight:700;color:{value_color};font-variant-numeric:tabular-nums'>{value}</div>"
        f"<div style='font-size:11px;color:{MUTED2};margin-top:5px;font-weight:500'>{sub}</div></div>"
    )


def kpi_row_html(deferred_cost: float, det_m: float, mean_m: float | None, ci95, ci90,
                 p_gt_1: float | None, lines: int, n_draws: int, is_mc: bool) -> str:
    mean_disp = f"{mean_m:.2f}×" if (is_mc and mean_m is not None) else "—"
    if is_mc and ci95:
        ci_disp = f"{ci95[0]:.2f}–{ci95[1]:.2f}"
        ci_sub = f"90% · {ci90[0]:.2f}–{ci90[1]:.2f}" if ci90 else "—"
    else:
        ci_disp, ci_sub = "—", "enable Monte-Carlo"
    if is_mc and p_gt_1 is not None:
        p_disp = f"{p_gt_1 * 100:.1f}%"
        p_color = GREEN if p_gt_1 > 0.95 else (AMBER if p_gt_1 > 0.8 else RED)
    else:
        p_disp, p_color = "—", INK
    cells = (
        _kpi("Deferred Cost (D)", usd(deferred_cost), f"{lines:,} lines × $4,700")
        + _kpi("Deterministic M", f"{det_m:.2f}", "point estimate")
        + _kpi("Posterior Mean M", mean_disp, f"{n_draws:,} draws", value_color=GREEN,
               border=GREEN_BORDER, label_color=GREEN, extra="box-shadow:0 1px 0 #eafaf2")
        + _kpi("95% Credible", ci_disp, ci_sub, value_size="20px")
        + _kpi("P(M > 1)", p_disp, "deferral compounds", value_color=p_color)
    )
    return f"<div style='display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:16px'>{cells}</div>"


# ── Banners ───────────────────────────────────────────────────────────────────
def abstention_banner_html(message: str) -> str:
    return (
        f"<div style='display:flex;align-items:center;gap:14px;background:{AMBER_BAN};border:1px solid {AMBER_BORDER};"
        f"border-radius:13px;padding:15px 20px;margin-bottom:16px'>"
        f"<div style='width:34px;height:34px;flex:none;border-radius:9px;background:#f7ecd3;display:flex;"
        f"align-items:center;justify-content:center;font-size:18px'>⚖︎</div>"
        f"<div><div style='font-size:14px;font-weight:700;color:#a9701a'>Abstention gate engaged — funding not compelled</div>"
        f"<div style='font-size:12.5px;color:#8a6a30;margin-top:2px'>{message} Routed to human review.</div></div></div>"
    )


def validation_banner_html(validation: dict | None) -> str:
    if not validation:
        return ""
    checks = validation.get("checks", [])
    passed = sum(1 for c in checks if c.get("level") == "ok")
    total = len(checks)
    review = validation.get("needs_human_review")
    dot = RED if review else GREEN
    head_color = RED if review else GREEN
    head = "self-validation · routed to human review" if review else f"Self-validation · {passed}/{total} passed"
    lvl_color = {"ok": GREEN, "warn": AMBER, "fail": RED}
    lvl_mark = {"ok": "✓", "warn": "!", "fail": "✗"}
    chips = ""
    for c in checks:
        lv = c.get("level", "ok")
        nm = c.get("name", "").split(" within ")[0].split(" agreement")[0]
        chips += (
            f"<span style='font-size:12px;color:{MUTED}'>"
            f"<strong style='color:{INK}'>{nm}</strong> "
            f"<span style='color:{lvl_color.get(lv, GREEN)}'>{lvl_mark.get(lv, '✓')}</span></span>"
        )
    sep = f"<span style='width:1px;height:20px;background:{CARD_BORDER}'></span>"
    return (
        f"<div style='display:flex;align-items:center;gap:16px;background:#fff;border:1px solid {CARD_BORDER};"
        f"border-radius:13px;padding:14px 20px;margin-bottom:16px;flex-wrap:wrap'>"
        f"<div style='display:flex;align-items:center;gap:9px'>"
        f"<span style='width:9px;height:9px;border-radius:50%;background:{dot};box-shadow:0 0 0 3px {GREEN_TINT}'></span>"
        f"<span style='font-size:13px;font-weight:700;color:{head_color}'>{head}</span></div>{sep}{chips}</div>"
    )


# ── Cascade strip ─────────────────────────────────────────────────────────────
def cascade_strip_html(deferred_cost: float, bll_inc: float, children: int,
                       iq_loss: float, earnings_per_child: float, obligated: float,
                       mean_m: float, defer_years: int) -> str:
    arrow = lambda col: f"<div style='display:flex;align-items:center;color:{col};font-size:17px;font-weight:700'>→</div>"
    step = lambda lbl, val, sub, lblcol=MUTED, valcol=INK, bg="#f5f7fa", bd=CARD_BORDER: (
        f"<div style='flex:1;background:{bg};border:1px solid {bd};border-radius:11px;padding:15px 16px'>"
        f"<div style='font-size:10px;color:{lblcol};font-weight:700;letter-spacing:.04em;margin-bottom:8px'>{lbl}</div>"
        f"<div style='font-family:{DISPLAY};font-size:21px;font-weight:700;color:{valcol}'>{val}</div>"
        f"<div style='font-size:10.5px;color:{MUTED2};margin-top:3px'>{sub}</div></div>"
    )
    head = (
        f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:16px'>"
        f"<div style='font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:{MUTED};font-weight:700'>"
        f"How $1 deferred compounds downstream</div>"
        f"<div style='font-size:11.5px;color:{MUTED2};font-weight:600'>{defer_years}-year horizon · present value</div></div>"
    )
    body = (
        f"<div style='display:flex;align-items:stretch;gap:7px'>"
        + step("DEFER NOW", usd_m(deferred_cost), "replacement avoided")
        + arrow(GREEN)
        + step("↑ BLOOD LEAD", f"+{bll_inc:.1f} µg/dL", f"{children} children &lt;6")
        + arrow("#3a8f6f")
        + step("↓ IQ · EARNINGS", f"−{iq_loss:.1f} pts", f"{usd(earnings_per_child)} lifetime/child")
        + arrow(RED)
        + step("OBLIGATED LATER", usd_m(obligated), f"{mean_m:.2f}× the deferred $",
               lblcol=RED, valcol=RED, bg=RED_TINT, bd=RED_BORDER)
        + "</div>"
    )
    return _card(head + body, pad="20px 24px", extra="margin-bottom:22px")


# ── Charts (HTML/CSS bars from real arrays) ───────────────────────────────────
def _pct(v: float, axis_max: float) -> str:
    return f"{min(1.0, max(0.0, v / axis_max)) * 100:.1f}%"


def posterior_bars_html(m_draws, ci90, ci95, mean_m: float, det_m: float,
                        n_draws: int, seed: int, n_bins: int = 44, height: int = 186) -> str:
    arr = np.asarray(m_draws, dtype=float)
    arr = arr[np.isfinite(arr)]
    head = (
        f"<div style='display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px'>"
        f"<h3 style='font-size:16px;font-weight:700;color:{INK};margin:0'>Posterior of the deferral multiplier M</h3>"
        f"<span style='font-size:11px;color:{MUTED2};font-weight:600'>{n_draws:,} draws · seed {seed}</span></div>"
        f"<p style='font-size:12px;color:{MUTED};margin:0 0 16px'>Future obligated public $ per deferred $. Shaded = 95% CI.</p>"
    )
    if arr.size == 0:
        return _card(head + f"<div style='color:{MUTED2};font-size:13px'>Enable Monte-Carlo draws to view the posterior.</div>")

    lo95, hi95 = ci95 if ci95 else (float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5)))
    axis_max = max(float(np.percentile(arr, 99)), hi95 * 1.05, 1.5)
    counts, edges = np.histogram(arr, bins=n_bins, range=(0.0, axis_max))
    mx = counts.max() or 1
    bars = ""
    for i in range(n_bins):
        center = (edges[i] + edges[i + 1]) / 2.0
        h = max(3, int(round(counts[i] / mx * height)))
        col = GREEN if (lo95 <= center <= hi95) else BAR_GREY
        bars += f"<div style='flex:1;align-self:flex-end;border-radius:1.5px 1.5px 0 0;background:{col};height:{h}px'></div>"

    ci_left = _pct(lo95, axis_max)
    ci_w = f"{(min(hi95, axis_max) - lo95) / axis_max * 100:.1f}%"
    legend = (
        f"<div style='display:flex;justify-content:space-between;font-family:{MONO};font-size:10px;margin-bottom:6px'>"
        f"<span style='color:{RED}'>▏M=1</span><span style='color:{MUTED2}'>det {det_m:.2f}</span>"
        f"<span style='color:{GREEN}'>mean {mean_m:.2f} ▏</span></div>"
    )
    plot = (
        f"<div style='position:relative;height:{height}px;border-bottom:1.5px solid #d8dee6'>"
        f"<div style='position:absolute;top:0;bottom:0;background:rgba(21,151,106,.07);left:{ci_left};width:{ci_w}'></div>"
        f"<div style='position:absolute;top:0;bottom:0;border-left:1.5px dashed {RED};left:{_pct(1.0, axis_max)}'></div>"
        f"<div style='position:absolute;top:0;bottom:0;border-left:1px dotted {MUTED2};left:{_pct(det_m, axis_max)}'></div>"
        f"<div style='position:absolute;top:0;bottom:0;border-left:2px solid {GREEN};left:{_pct(mean_m, axis_max)}'></div>"
        f"<div style='position:absolute;inset:0;display:flex;align-items:flex-end;gap:2px'>{bars}</div></div>"
    )
    ticks = (
        f"<div style='display:flex;justify-content:space-between;font-family:{MONO};font-size:10px;color:{MUTED2};margin-top:7px'>"
        f"<span>0</span><span>{axis_max * .25:.1f}</span><span>{axis_max * .5:.1f}</span>"
        f"<span>{axis_max * .75:.1f}</span><span>{axis_max:.0f}×</span></div>"
    )
    return _card(head + legend + plot + ticks)


def tornado_html(sobol_res: dict, commission_rec: dict) -> str:
    items = [(k, v) for k, v in (sobol_res or {}).items() if v.get("ST", 0.0) > 0.0]
    if not items:
        items = list((sobol_res or {}).items())
    items.sort(key=lambda kv: kv[1].get("ST", 0.0), reverse=True)
    maxst = max((v.get("ST", 0.0) for _, v in items), default=1.0) or 1.0
    head = (
        f"<h3 style='font-size:16px;font-weight:700;color:{INK};margin:0 0 4px'>Sobol variance tornado</h3>"
        f"<p style='font-size:12px;color:{MUTED};margin:0 0 6px'>Which assumption drives the spread → which study to commission first.</p>"
    )
    drv = commission_rec.get("top_driver", "—")
    drv_short = SHORT_LABELS.get(drv, drv)
    rec = commission_rec.get("plain_language", "")
    callout = (
        f"<div style='display:inline-flex;align-items:center;gap:7px;background:{BLUE_BG};border:1px solid {BLUE_TINT};"
        f"border-radius:8px;padding:7px 11px;margin-bottom:18px'>"
        f"<span style='font-size:11px;color:{BLUE};font-weight:600'>Top driver: <strong>{drv_short}</strong> · "
        f"ST {commission_rec.get('ST', 0.0):.3f}</span></div>"
        f"<p style='font-size:11px;color:{MUTED};margin:-10px 0 16px'>{rec}</p>"
    )
    rows = ""
    for k, v in items:
        st_ = v.get("ST", 0.0)
        s1 = v.get("S1", 0.0)
        rows += (
            f"<div style='margin-bottom:13px'>"
            f"<div style='display:flex;justify-content:space-between;margin-bottom:5px'>"
            f"<span style='font-family:{MONO};font-size:11px;color:{INK};font-weight:500'>{SHORT_LABELS.get(k, k)}</span>"
            f"<span style='font-family:{MONO};font-size:10.5px;color:{MUTED2}'>ST {st_:.3f}</span></div>"
            f"<div style='position:relative;height:10px;background:#f0f2f5;border-radius:5px;overflow:hidden'>"
            f"<div style='position:absolute;left:0;top:0;bottom:0;width:{st_ / maxst * 100:.0f}%;background:{BLUE_TINT};border-radius:5px'></div>"
            f"<div style='position:absolute;left:0;top:0;bottom:0;width:{s1 / maxst * 100:.0f}%;background:{BLUE};border-radius:5px'></div>"
            f"</div></div>"
        )
    legend = (
        f"<div style='display:flex;gap:16px;margin-top:14px;padding-top:13px;border-top:1px solid {BG}'>"
        f"<span style='display:flex;align-items:center;gap:6px;font-size:11px;color:{MUTED}'>"
        f"<span style='width:11px;height:11px;border-radius:3px;background:{BLUE}'></span>S1 first-order</span>"
        f"<span style='display:flex;align-items:center;gap:6px;font-size:11px;color:{MUTED}'>"
        f"<span style='width:11px;height:11px;border-radius:3px;background:{BLUE_TINT}'></span>ST total-order</span></div>"
    )
    return _card(head + callout + rows + legend)


def scenario_overlay_html(compare_res: dict, defer_years: int, n_bins: int = 46, height: int = 150) -> str:
    now = np.asarray(compare_res.get("cost_now_draws") or [], dtype=float)
    defer = np.asarray(compare_res.get("cost_defer_draws") or [], dtype=float)
    delta = compare_res.get("cost_delta", {})
    head = (
        f"<h3 style='font-size:16px;font-weight:700;color:{INK};margin:0 0 4px'>Scenario cost overlay (present value)</h3>"
    )
    if now.size == 0 or defer.size == 0:
        return _card(head + f"<div style='color:{MUTED2};font-size:13px'>Run Monte-Carlo mode to compare scenarios.</div>")
    p_gt_0 = delta.get("p_gt_0", 0.0)
    sub = (
        f"<p style='font-size:12px;color:{MUTED};margin:0 0 16px'>Mean PV cost delta "
        f"<strong style='color:{RED}'>{usd_m(delta.get('mean', 0.0))}</strong> · "
        f"P(defer costs more) <strong style='color:{RED}'>{p_gt_0 * 100:.0f}%</strong></p>"
    )
    axis_max = max(float(np.percentile(now, 99)), float(np.percentile(defer, 99)), 1.0)
    cn, _ = np.histogram(now, bins=n_bins, range=(0.0, axis_max))
    cd, _ = np.histogram(defer, bins=n_bins, range=(0.0, axis_max))
    mxn = cn.max() or 1
    mxd = cd.max() or 1
    bars = ""
    for i in range(n_bins):
        hn = int(round(cn[i] / mxn * height))
        hd = int(round(cd[i] / mxd * (height - 30)))
        bars += (
            f"<div style='flex:1;position:relative;align-self:flex-end;height:{max(0, hn)}px;"
            f"background:rgba(21,151,106,.55);border-radius:1px 1px 0 0'>"
            f"<div style='position:absolute;bottom:0;left:0;right:0;height:{max(0, hd)}px;"
            f"background:rgba(226,82,79,.5);border-radius:1px 1px 0 0'></div></div>"
        )
    plot = (
        f"<div style='position:relative;height:{height}px;border-bottom:1.5px solid #d8dee6'>"
        f"<div style='position:absolute;inset:0;display:flex;align-items:flex-end;gap:2px'>{bars}</div></div>"
    )
    ticks = (
        f"<div style='display:flex;justify-content:space-between;font-family:{MONO};font-size:10px;color:{MUTED2};margin-top:7px'>"
        f"<span>$0</span><span>{usd_m(axis_max * .33)}</span><span>{usd_m(axis_max * .66)}</span><span>{usd_m(axis_max)}</span></div>"
    )
    legend = (
        f"<div style='display:flex;gap:18px;margin-top:12px'>"
        f"<span style='display:flex;align-items:center;gap:6px;font-size:11.5px;color:{MUTED}'>"
        f"<span style='width:11px;height:11px;border-radius:3px;background:{GREEN}'></span>Replace now</span>"
        f"<span style='display:flex;align-items:center;gap:6px;font-size:11.5px;color:{MUTED}'>"
        f"<span style='width:11px;height:11px;border-radius:3px;background:{RED}'></span>Defer {defer_years} yr</span></div>"
    )
    return _card(head + sub + plot + ticks + legend)


# ── Citations ─────────────────────────────────────────────────────────────────
def citations_html(edges, active_ids: list[str]) -> str:
    active = set(active_ids)
    head = (
        f"<h3 style='font-size:16px;font-weight:700;color:{INK};margin:0 0 4px'>Active edge citations</h3>"
        f"<p style='font-size:12px;color:{MUTED};margin:0 0 12px'>Every number traces to a cited prior.</p>"
    )
    rows = ""
    for e in edges:
        if e.id not in active:
            continue
        ci = f"[{e.ci_low}, {e.ci_high}]" if e.ci_low is not None and e.ci_high is not None else "N/A"
        src = (e.source or "").strip().split("\n")[0][:70]
        rows += (
            f"<div style='padding:11px 0;border-bottom:1px solid #f0f2f5'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:4px'>"
            f"<span style='font-family:{MONO};font-size:11.5px;color:{GREEN};font-weight:600'>{e.id}</span>"
            f"<span style='font-family:{MONO};font-size:11px;color:{INK};font-weight:600'>{e.point_estimate}</span></div>"
            f"<div style='font-family:{MONO};font-size:10px;color:{MUTED2};margin-bottom:3px'>{e.from_node} → {e.to_node}</div>"
            f"<div style='font-size:11px;color:{MUTED}'>CI {ci} · {src}</div></div>"
        )
    return _card(head + rows)


# ── Map (schematic, display-only) ─────────────────────────────────────────────
def map_schematic_html(tracts, selected_geoid: str) -> str:
    head = (
        f"<div style='display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:16px'>"
        f"<div><h3 style='font-size:16px;font-weight:700;color:{INK};margin:0 0 4px'>Genesee County tracts (Flint, MI)</h3>"
        f"<p style='font-size:12px;color:{MUTED};margin:0'>Bubble size ∝ children under 6. Selected tract in "
        f"<strong style='color:{RED}'>red</strong>; choose tracts from the sidebar.</p></div>"
        f"<span style='font-size:10.5px;color:{MUTED2};font-family:{MONO};font-weight:600'>SCHEMATIC · not geographic tiles</span></div>"
    )
    bubbles = ""
    n = max(1, len(tracts))
    for i, t in enumerate(tracts):
        sel = t.geoid == selected_geoid
        d = int(18 + max(0, (t.children_under6 - 110)) / 3.0)
        # deterministic scatter
        x = 12 + (i % 5) * 17 + (7 if (i // 5) % 2 else 0)
        y = 16 + (i // 5) * 26 + (i * 7 % 11)
        color = RED if sel else "#4b83c4"
        bubbles += (
            f"<div title='Tract {t.geoid} · SVI {t.svi_percentile:.3f} · {t.children_under6} children' "
            f"style='position:absolute;left:{x}%;top:{y}%;width:{d}px;height:{d}px;margin-left:-{d // 2}px;margin-top:-{d // 2}px;"
            f"border-radius:50%;background:{color};border:2px solid #fff;box-shadow:0 2px 8px rgba(20,40,70,.18);"
            f"display:flex;align-items:center;justify-content:center'>"
            f"<span style='font-family:{MONO};font-size:9.5px;color:#fff;font-weight:600;opacity:{1 if d > 30 else 0}'>{t.children_under6}</span></div>"
        )
    grid = (
        f"<div style='position:relative;height:440px;border-radius:11px;overflow:hidden;background:#eef2f6;"
        f"background-image:linear-gradient(#e2e8ef 1px,transparent 1px),linear-gradient(90deg,#e2e8ef 1px,transparent 1px);"
        f"background-size:46px 46px;border:1px solid #e0e6ed'>"
        f"<span style='position:absolute;left:46%;top:46%;font-family:{MONO};font-size:13px;font-weight:600;color:#7c8aa0;letter-spacing:.05em'>FLINT</span>"
        f"{bubbles}</div>"
    )
    legend = (
        f"<div style='display:flex;gap:20px;margin-top:14px;align-items:center'>"
        f"<span style='display:flex;align-items:center;gap:7px;font-size:11.5px;color:{MUTED}'>"
        f"<span style='width:13px;height:13px;border-radius:50%;background:{RED}'></span>Selected tract</span>"
        f"<span style='display:flex;align-items:center;gap:7px;font-size:11.5px;color:{MUTED}'>"
        f"<span style='width:13px;height:13px;border-radius:50%;background:#4b83c4'></span>Other tracts</span>"
        f"<span style='font-size:11.5px;color:{MUTED2};margin-left:auto'>{n} synthetic tracts · Genesee County</span></div>"
    )
    return _card(head + grid + legend)


# ── Optimizer ─────────────────────────────────────────────────────────────────
def optimizer_kpis_html(allocated: float, averted: float, roi: float) -> str:
    cells = (
        _kpi("Budget Allocated", usd(allocated), "")
        + _kpi("Obligations Averted", usd(averted), "", value_color=GREEN)
        + _kpi("Avg Portfolio ROI", f"{roi:.2f}×", "")
    )
    return f"<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:18px'>{cells}</div>"


def optimizer_table_html(opt_df) -> str:
    cols = "1.3fr .9fr .8fr .9fr 1.2fr 1.3fr .8fr 1.6fr"
    header = (
        f"<div style='display:grid;grid-template-columns:{cols};padding:13px 20px;background:#f5f7fa;"
        f"border-bottom:1px solid {CARD_BORDER};font-size:10.5px;color:{MUTED};font-weight:700;letter-spacing:.03em;text-transform:uppercase'>"
        f"<span>Tract</span><span style='text-align:right'>SVI</span><span style='text-align:right'>LSL</span>"
        f"<span style='text-align:right'>M</span><span style='text-align:right'>Repl. cost</span>"
        f"<span style='text-align:right'>Averted</span><span style='text-align:center'>Sel.</span><span>Reason</span></div>"
    )
    rows = ""
    for _, r in opt_df.iterrows():
        sel = str(r["Selected"]).upper() == "YES"
        sel_color = GREEN if sel else MUTED2
        sel_bg = GREEN_TINT if sel else "#f0f2f5"
        row_bg = "#f7fcf9" if sel else "#fff"
        rows += (
            f"<div style='display:grid;grid-template-columns:{cols};padding:12px 20px;border-bottom:1px solid #f0f2f5;align-items:center;background:{row_bg}'>"
            f"<span style='font-family:{MONO};font-size:12px;color:{INK};font-weight:500'>{r['Tract ID']}</span>"
            f"<span style='font-family:{MONO};font-size:12px;color:{MUTED};text-align:right'>{r['SVI Percentile']:.4f}</span>"
            f"<span style='font-family:{MONO};font-size:12px;color:{MUTED};text-align:right'>{int(r['LSL Count'])}</span>"
            f"<span style='font-family:{MONO};font-size:12px;color:{INK};text-align:right;font-weight:600'>{r['Multiplier M']:.2f}</span>"
            f"<span style='font-family:{MONO};font-size:12px;color:{MUTED};text-align:right'>{usd(r['Replacement Cost ($)'])}</span>"
            f"<span style='font-family:{MONO};font-size:12px;color:{GREEN};text-align:right;font-weight:600'>{usd(r['Avoided Obligation ($)'])}</span>"
            f"<span style='text-align:center'><span style='font-size:10px;font-weight:700;color:{sel_color};background:{sel_bg};padding:3px 8px;border-radius:12px'>{r['Selected']}</span></span>"
            f"<span style='font-size:11.5px;color:{MUTED}'>{r['Allocation Reason']}</span></div>"
        )
    return f"<div style='background:#fff;border:1px solid {CARD_BORDER};border-radius:13px;overflow:hidden'>{header}{rows}</div>"


# ── Governance ────────────────────────────────────────────────────────────────
def lifecycle_table_html(edges, ref_date) -> str:
    from datetime import datetime
    cols = "1.4fr 1fr .6fr .9fr"
    head = (
        f"<h3 style='font-size:16px;font-weight:700;color:{INK};margin:0 0 4px'>Causal prior expiration &amp; lifecycle</h3>"
        f"<p style='font-size:12px;color:{MUTED};margin:0 0 16px'>Every edge carries provenance + last-validated date. Stale priors are flagged.</p>"
        f"<div style='display:grid;grid-template-columns:{cols};padding:10px 12px;background:#f5f7fa;border-radius:8px;"
        f"font-size:10px;color:{MUTED};font-weight:700;text-transform:uppercase;letter-spacing:.03em;margin-bottom:4px'>"
        f"<span>Edge</span><span>Validated</span><span style='text-align:right'>Age</span><span style='text-align:center'>Status</span></div>"
    )
    rows = ""
    for e in edges:
        try:
            age = (ref_date - datetime.strptime(e.last_validated, "%Y-%m-%d")).days
        except Exception:
            age = 0
        stale = age > 365
        badge_c = AMBER if stale else GREEN
        badge_bg = AMBER_BAN if stale else GREEN_TINT
        badge_t = "⚠ Stale" if stale else "✓ Current"
        rows += (
            f"<div style='display:grid;grid-template-columns:{cols};padding:11px 12px;border-bottom:1px solid #f0f2f5;align-items:center'>"
            f"<span style='font-family:{MONO};font-size:11px;color:{INK}'>{e.id}</span>"
            f"<span style='font-family:{MONO};font-size:11px;color:{MUTED}'>{e.last_validated}</span>"
            f"<span style='font-family:{MONO};font-size:11px;color:{MUTED};text-align:right'>{age}d</span>"
            f"<span style='text-align:center'><span style='font-size:10px;font-weight:700;color:{badge_c};background:{badge_bg};padding:3px 9px;border-radius:12px'>{badge_t}</span></span></div>"
        )
    return _card(head + rows)


def recalibration_alert_html() -> str:
    return (
        f"<div style='display:flex;gap:14px;background:{AMBER_BAN};border:1px solid {AMBER_BORDER};border-radius:13px;padding:18px 20px;margin-top:18px'>"
        f"<div style='font-size:20px'>📣</div>"
        f"<div><div style='font-size:13px;font-weight:700;color:#a9701a;margin-bottom:4px'>Recalibration alert (LC-2)</div>"
        f"<div style='font-size:12.5px;color:#8a6a30;line-height:1.6'>The EPA revised the national LSL count from ~9.2M to ~4.7M on 25 Nov 2025. "
        f"Parameters in <span style='font-family:{MONO};font-size:11.5px'>edges.yaml</span> require validation adjustments if applied upstream.</div></div></div>"
    )


def consent_log_html(consent_rows: list[dict]) -> str:
    head = (
        f"<h3 style='font-size:16px;font-weight:700;color:{INK};margin:0 0 4px'>Contested-edge consent log</h3>"
        f"<p style='font-size:12px;color:{MUTED};margin:0 0 16px'>FR-GOV-3 · RAI-1 — enabling a contested edge writes an attributed event.</p>"
    )
    if not consent_rows:
        body = (
            f"<div style='background:{BLUE_BG};border:1px solid {BLUE_TINT};border-radius:9px;padding:16px;font-size:12.5px;color:{BLUE}'>"
            f"No contested consent events logged. The default view excludes the most stigmatizing edges.</div>"
        )
    else:
        body = ""
        for c in consent_rows:
            body += (
                f"<div style='display:flex;gap:12px;padding:12px 14px;background:#fdf6ed;border:1px solid {AMBER_BORDER};border-radius:9px;margin-bottom:9px'>"
                f"<span style='width:8px;height:8px;border-radius:50%;background:{AMBER};margin-top:5px;flex:none'></span>"
                f"<div><div style='font-size:12.5px;color:{INK};font-weight:600'>{c.get('edge_id', '')} <span style='color:{AMBER}'>{str(c.get('action', 'enable')).upper()}</span></div>"
                f"<div style='font-family:{MONO};font-size:10.5px;color:{MUTED2};margin-top:3px'>by {c.get('user', 'operator')} · {c.get('timestamp', '')}</div></div></div>"
            )
    return _card(head + body)


def audit_json_html(record: dict | None, run_short: str) -> str:
    payload = json.dumps(record, indent=2) if record else "{ persisting to SQLite store… }"
    return (
        f"<div style='background:{INK};border-radius:13px;padding:22px 24px;margin-top:18px'>"
        f"<div style='font-size:13px;font-weight:700;color:#fff;margin-bottom:4px;font-family:{DISPLAY}'>Immutable run audit snapshot</div>"
        f"<div style='font-family:{MONO};font-size:10.5px;color:{MUTED_D};margin-bottom:16px'>run_id {run_short}</div>"
        f"<pre style='font-family:{MONO};font-size:11px;color:{GREEN_ACCENT};line-height:1.7;margin:0;white-space:pre-wrap'>{payload}</pre></div>"
    )
