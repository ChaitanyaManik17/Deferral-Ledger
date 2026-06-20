# DEFERRAL LEDGER — Day 3 Tasks: **CHAITANYA**
### Role: RAG decision brief + dashboard analytics panels + model card / lifecycle
*Build team = Chaitanya + Varun (Manush unavailable; full scope via overtime). Day 3 = "make it usable & responsible". You own the human-facing narrative (the brief) and the analytics panels that make the 35% reasoning legible. Pair: Varun (app skeleton, governance/audit, deploy).*

---

## Day-3 goal (shared, you + Varun)
> **A deployed Streamlit app: pick a tract + defer years → see the M posterior (fan/histogram + CI), the abstention banner, the Sobol tornado + "commission this study" callout, an edge table with citations + a contested-edge consent toggle, a generated decision brief, and a persisted audit record — live on a public URL.**

**Your slice of the milestone:** the **RAG-grounded decision brief** (with a templated fallback), and the **analytics panels** (M fan chart, Sobol tornado, edge/citation table, compare view) that render Day-2's outputs.

---

## STEP 0 — Joint design lock (~40 min)
Same as Varun's STEP 0. Lock with him: (a) the **brief's input contract** — what `generate_brief` receives (`MultiplierResult` + `sobol_indices` + `commission_study_recommendation` + `compare` + `edges`); (b) the **panel function signatures** so Varun can drop your components into the app layout; (c) the **golden scenario** (a tract+defer-years where `M>1` and **E1 dominates** the tornado).

---

## YOUR TASKS (ordered)

### C1 — Decision-brief generator (`brief.py`) *(~2.5 h)* — the human-facing payoff
- `generate_brief(result, sobol, commission_rec, compare, edges) -> str` producing a plain-language brief for a non-technical official:
  - the headline: "every deferred $1 tends to obligate ~$M later (90% CI …)" — **pulled verbatim from `result`**, never invented;
  - the abstention message when `result.abstain`;
  - the **top sensitivity driver + the commission-a-study recommendation** (from `commission_rec`);
  - the **citations** for each enabled edge (`edge.source`) so every number is traceable.
- **Templated fallback FIRST** (pure f-string from the objects — works offline, deterministic). Then a **free-tier LLM narration** layer (Gemini free tier or an open HF model) that only *rephrases* the templated facts — **strict prompt: do not add or change any number; numbers come only from the provided JSON.** Disclose free/paid in the tools list.
- **DoD:** brief renders from real objects; with the LLM key absent it still produces the templated brief (graceful degradation, SRS FR-EXP-3); no number appears that isn't in `result`/`edges`.

### C2 — Analytics panels (`panels.py`, imported by Varun's `app.py`) *(~2.5 h)*
- **M posterior fan/histogram:** Plotly histogram/violin of the MC draws with the 90/95% CI and a vertical line at M=1; abstain region shaded. (You may need Varun to expose the draws/percentiles — agree in STEP 0.)
- **Sobol tornado:** horizontal bar of `ST` per edge (from `sobol_indices`), E1 expected on top; annotate the top bar with the commission-a-study callout.
- **Edge/citation table:** each enabled edge with its value, CI, `source`, `last_validated`, and a **contested** badge (E6/E7). This is where "every number is cited" becomes visible.
- **Compare view:** now-vs-defer (`compare()` output) — two distributions + the PV cost-delta with its band.
- **DoD:** each panel is a function returning a Plotly fig / Streamlit component Varun can place; all read real Day-2 outputs.

### C3 — Model card + lifecycle copy (`docs/model_card.md`) *(~1 h)*
- Finalize the model card: intended use, inputs, the **exposure-model assumption** (BLL cap at 10 µg/dL), **non-goals** (no individual scoring; not a funding decider), **abstention rule**, **bias/contested-edge** design (E7 off by default), and the **lifecycle**: `last_validated` staleness, the **recalibration trigger** (EPA 9M→4M inventory revision), drift-monitor intent.
- Provide the in-app lifecycle copy Varun surfaces (V5) — keep wording consistent.
- **DoD:** model card complete; in-app lifecycle text agreed.

### C4 — Demo figures + brief polish for the video *(~1 h)*
- From `notebooks/eval.ipynb`, export the tornado + M-distribution figures and a clean golden-scenario brief for the pitch video / Devpost.
- Draft the **Responsible-AI guardrail** and **Human-in-the-Loop** answer text (≤500 chars each) straight from the implemented behavior (abstention, contested-consent, non-goals).
- **DoD:** figures + draft submission answers committed under `docs/`.

### C5 — STRETCH (your lane): second region (India)
- Add an India tract set (documented synthetic, calibrated to public figures) + a **region toggle**; show the same cascade re-fans with region-specific priors (the "global generalization" bonus). Keep assumptions flagged.

---

## Contracts you PRODUCE
- `brief.generate_brief(...)` → Varun renders it in `app.py`.
- `panels.*` chart/component functions → placed into the app layout.
- Finalized `docs/model_card.md` + draft submission answers.

## Contracts you CONSUME (from Day 2 / Varun)
- `montecarlo.run_monte_carlo` / `compare` results · `sensitivity.sobol_indices` + `commission_study_recommendation` · `catalog.load_edges` (for citations) · the MC **draws/percentiles** Varun exposes for the fan chart.

## Definition of Done — Chaitanya (Day 3)
- [ ] `generate_brief` with templated fallback + LLM narration that never invents numbers.
- [ ] Fan chart, Sobol tornado, edge/citation table, compare view — all from real outputs.
- [ ] Model card finalized + in-app lifecycle copy.
- [ ] Demo figures + draft Responsible-AI / HITL answers.

## Risks / notes
- **The brief is the responsible-AI showcase** — the strict "LLM rephrases, never computes" boundary is the point (it directly answers the rubric's misinformation/over-reliance risk). Keep the templated path as the source of truth.
- Make panels **pure functions of the result objects** so they work whether Varun wires them to direct imports or the API.
- E6/E7 must stay **off by default** in every panel; only show them when the consent gate enabled them.
- Keep the headline framing: *not a number — "here's the uncertainty, the edge that drives it, and the study to buy."*
