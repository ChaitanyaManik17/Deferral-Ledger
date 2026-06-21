"""
brief.py — Decision-brief generator for Deferral Ledger.

Generates a structured policy brief summarizing the deferral multiplier M,
uncertainty ranges, sensitivity drivers, and cost comparisons, with an optional
Gemini narration layer.
"""

from __future__ import annotations

import os
from typing import Any

import requests

from models import EdgePrior, MultiplierResult

# Candidate models, tried in order. Google retires these periodically
# (gemini-1.5-flash and gemini-2.0-flash are already gone), so we fall back
# through a chain and skip any that 404. Set GEMINI_MODEL to force a single one.
_FORCED_MODEL = os.environ.get("GEMINI_MODEL")
GEMINI_MODELS = ([_FORCED_MODEL] if _FORCED_MODEL else []) + [
    "gemini-2.5-flash-lite",   # fast/cheap — ideal for rephrasing
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-3-flash-preview",
]


def generate_brief(
    result: MultiplierResult,
    sobol: dict[str, dict[str, float]],
    commission_rec: dict[str, Any],
    compare: dict[str, Any],
    edges: list[EdgePrior],
    return_status: bool = False,
) -> str | tuple[str, dict[str, Any]]:
    """
    Generate a decision brief in markdown format.
    
    If GEMINI_API_KEY or GOOGLE_API_KEY is found in the environment, uses the
    Gemini API to rephrase the brief into a formal memorandum. Otherwise,
    falls back to a structured deterministic template (graceful degradation).
    """
    # 1. Format the abstention warning if triggered
    abstention_section = ""
    if result.abstain:
        abstention_section = (
            f"\n> [!WARNING]\n"
            f"> **ABSTENTION ACTIVE: {result.abstain_message}**\n"
            f"> The 95% credible interval spans below 1.0. This indicates that "
            f"deferral may not compound costs in this tract, and there is "
            f"insufficient evidence to compel immediate funding.\n"
        )

    # 2. Format the active edge citations
    enabled_edges = set(result.enabled_edges)
    edge_citations_list = []
    
    # Sort edges for clean display
    sorted_edges = sorted(edges, key=lambda e: e.id)
    for edge in sorted_edges:
        if edge.id in enabled_edges:
            contested_badge = " **[CONTESTED]**" if edge.contested else ""
            ci_str = f"[{edge.ci_low}, {edge.ci_high}]" if edge.ci_low is not None and edge.ci_high is not None else "N/A"
            edge_citations_list.append(
                f"- **Edge {edge.id}** ({edge.from_node} ➔ {edge.to_node}): "
                f"Point estimate = {edge.point_estimate}, CI = {ci_str}, "
                f"Validated = {edge.last_validated}.{contested_badge}\n"
                f"  *Citation:* {edge.source}"
            )
            
    edge_citations = "\n".join(edge_citations_list)

    # 3. Handle CI formatting
    ci90_str = f"[{result.ci90[0]:.2f}, {result.ci90[1]:.2f}]" if result.ci90 else "N/A"
    ci95_str = f"[{result.ci95[0]:.2f}, {result.ci95[1]:.2f}]" if result.ci95 else "N/A"
    mean_val = result.multiplier_mean if result.multiplier_mean is not None else result.multiplier_point

    # 3b. Self-validation section (how we'd catch a wrong answer)
    validation_section = ""
    if getattr(result, "validation", None):
        v = result.validation
        v_lines = "\n".join(
            f"- {c['name']}: **{c['level'].upper()}** — {c['detail']}" for c in v.get("checks", [])
        )
        validation_section = (
            "\n## 5. How We'd Catch a Wrong Answer (Self-Validation)\n"
            f"Status: **{v.get('summary', '')}**. The AI does not finalize a flagged decision — "
            "any failed check routes the case to human review.\n"
            f"{v_lines}\n"
        )

    # 4. Generate the base templated brief
    templated_brief = f"""# DEFERRAL LEDGER — DECISION BRIEF

## 1. Executive Summary
- **Tract ID:** {result.tract_id}
- **Deferral Period:** {result.defer_years} years
- **Annual Discount Rate:** {result.discount_rate:.1%}
- **Causal Model Version:** {result.catalog_version}

**Headline Estimate:**
Every deferred $1 tends to obligate **${mean_val:.2f}** in downstream public costs later (90% Credible Interval: **{ci90_str}**; 95% Credible Interval: **{ci95_str}**).

There is a **{result.p_gt_1 if result.p_gt_1 is not None else 0.0:.1%}** probability that the deferral multiplier exceeds 1.0 (indicating that deferring costs more than replacing now).
{abstention_section}
## 2. Risk Driver & Study Recommendation
Based on the Sobol global sensitivity analysis, the variance in the deferral multiplier is primarily driven by:
- **Primary Driver:** `{commission_rec.get('top_driver', 'N/A')}` (Total-order sensitivity index ST = **{commission_rec.get('ST', 0.0):.4f}**)
- **Recommendation:** {commission_rec.get('plain_language', 'N/A')}

## 3. Comparison of Scenarios
Comparing **Replace Now** (deferral = 0 years) vs. **Defer** ({result.defer_years} years):
- **Mean Net Present Value (NPV) Cost Delta:** ${compare['cost_delta']['mean']:,.2f} (90% CI: ${compare['cost_delta']['ci90'][0]:,.2f} to ${compare['cost_delta']['ci90'][1]:,.2f})
- **Probability of Net Cost Increase:** {compare['cost_delta']['p_gt_0']:.1%}

## 4. Edge Catalog and Evidence Citations
The following causal links were active in this simulation:
{edge_citations}
{validation_section}"""

    # 5. Determine narration status & (optionally) attempt LLM rephrasing
    status: dict[str, Any] = {"used_llm": False, "model": GEMINI_MODELS[0], "message": ""}
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        status["message"] = "No API key configured — using deterministic template."
        return (templated_brief.strip(), status) if return_status else templated_brief.strip()

    # Call Gemini REST API to rephrase the brief (the prompt forbids changing any number)
    headers = {"Content-Type": "application/json"}
    prompt = (
        "You are a professional public infrastructure policy analyst and writer. "
        "Your task is to rephrase the draft decision brief below into a highly polished, "
        "formal policy memorandum for a non-technical municipal/state official.\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. Do not add, change, or remove any numbers, statistics, percentages, ranges, dates, or citations. All numbers and citations MUST remain exactly as they appear in the draft.\n"
        "2. Preserve any warnings or abstention statements verbatim.\n"
        "3. Maintain an objective, professional, and formal tone.\n"
        "4. Do not invent any facts or make claims not supported by the numbers in the draft.\n\n"
        "Here is the draft brief:\n\n" + templated_brief
    )

    last_msg = ""
    for model in GEMINI_MODELS:
        status["model"] = model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        try:
            response = requests.post(
                url,
                headers=headers,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=30.0,
            )
            if response.status_code == 200:
                data = response.json()
                narrated = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                if narrated:
                    status["used_llm"] = True
                    status["message"] = f"Narration live via {model}."
                    return (narrated, status) if return_status else narrated
                last_msg = "LLM returned empty text"
                continue
            try:
                err_msg = response.json().get("error", {}).get("message", "")
            except Exception:
                err_msg = response.text[:160]
            last_msg = f"HTTP {response.status_code}: {err_msg}"
            # 404 = model retired → try the next candidate; other errors (auth/quota) → stop.
            if response.status_code != 404:
                break
        except requests.exceptions.Timeout:
            last_msg = f"timeout on {model}"
            continue  # a faster candidate may respond
        except Exception as exc:
            last_msg = f"{type(exc).__name__}"
            break

    status["message"] = f"Narration unavailable ({last_msg}) — using template."
    return (templated_brief.strip(), status) if return_status else templated_brief.strip()
