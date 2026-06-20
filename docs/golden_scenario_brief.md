# DEFERRAL LEDGER — DECISION BRIEF

## 1. Executive Summary
- **Tract ID:** 26049900001
- **Deferral Period:** 5 years
- **Annual Discount Rate:** 3.0%
- **Causal Model Version:** 07ae2eb

**Headline Estimate:**
Every deferred $1 tends to obligate **$22.51** in downstream public costs later (90% Credible Interval: **[8.41, 47.12]**; 95% Credible Interval: **[7.09, 56.44]**).

There is a **100.0%** probability that the deferral multiplier exceeds 1.0 (indicating that deferring costs more than replacing now).

## 2. Risk Driver & Study Recommendation
Based on the Sobol global sensitivity analysis, the variance in the deferral multiplier is primarily driven by:
- **Primary Driver:** `E0_cost_per_line` (Total-order sensitivity index ST = **0.8616**)
- **Recommendation:** We recommend conducting contractor quote audits or a engineering site scan to narrow the uncertainty of the lead service line replacement cost.

## 3. Comparison of Scenarios
Comparing **Replace Now** (deferral = 0 years) vs. **Defer** (5 years):
- **Mean Net Present Value (NPV) Cost Delta:** $11,318,142.25 (90% CI: $5,747,206.79 to $16,271,386.72)
- **Probability of Net Cost Increase:** 100.0%

## 4. Edge Catalog and Evidence Citations
The following causal links were active in this simulation:
- **Edge E0_cost_per_line** (defer_decision ➔ deferred_dollars): Point estimate = 4700.0, CI = [1200.0, 12300.0], Validated = 2026-06-14.
  *Citation:* EPA LCRI fact sheet, "Calculating Service Line Replacement Cost" (Oct 2024). Average cost ~$4,700/line; range $1,200–$12,300. URL: https://www.epa.gov/system/files/documents/2024-10/final_lcri_fact-sheet_calculating-service-line.pdf

- **Edge E1_lsl_to_bll** (continued_exposure_person_years ➔ bll_increment_ugdl): Point estimate = 1.5, CI = [0.5, 4.0], Validated = 2026-06-14.
  *Citation:* ⚠ WIDE PRIOR — top research priority (see DAY1_CHAITANYA_TASKS.md). Evidence basis: Hanna-Attisha et al. 2016 (AJPH) — Flint pre/post analysis showed percentage of children with elevated BLL (~5 µg/dL) roughly doubled during LSL-related contamination (~2–4× relative increase, absolute BLL increments of ~1–3 µg/dL in affected areas). EPA IEUBK model water-lead contribution estimates 0.5–3 µg/dL from lead plumbing depending on fixture age, flow, and standing time. Newark pre/post (2019–2021) reported ~1–2 µg/dL median reductions post-replacement in high-risk areas. Primary ref: Hanna-Attisha M et al., "Elevated Blood Lead Levels in Children Associated With the Flint Drinking Water Crisis," Am J Public Health 2016; 106(2):283-290. DOI: 10.2105/AJPH.2015.302896 Supporting: EPA IEUBK model guidance; del Toral et al. 2016 (ES&T).

- **Edge E2_bll_to_iq** (bll_increment_ugdl ➔ iq_loss_points): Point estimate = -0.87, CI = [-1.1, -0.64], Validated = 2026-06-14.
  *Citation:* Lanphear BP et al., "Low-level environmental lead exposure and children's intellectual function: an international pooled analysis," Environ Health Perspect 2005; 113(7):894–899. DOI: 10.1289/ehp.7688. Pooled analysis of 7 prospective cohorts; overall slope −0.87 IQ pts/µg/dL (95% CI −1.10 to −0.64). Steeper slope −1.37 IQ pts/µg/dL below 10 µg/dL. Referenced in SRS as [R4].

- **Edge E3_iq_to_earnings** (iq_loss_points ➔ lifetime_earnings_loss_dollars): Point estimate = 11850.0, CI = [10600.0, 13100.0], Validated = 2026-06-14.
  *Citation:* Primary: Grosse SD et al., "Estimated IQ points and lifetime earnings lost to early-childhood blood lead levels in the United States, 1997–2018," Sci Total Environ 2021; 787:147452. DOI: 10.1016/j.scitotenv.2021.147452. Approx. $10,600–$13,100 per IQ point at 3% discount rate. URL: https://www.sciencedirect.com/science/article/abs/pii/S0048969721013759 Secondary: Unleaded Kids, "Calculating IQ-Related Increased Lifetime Earnings" (2025-03-04). IQ point ≈ 1.4% of lifetime earnings (3% discount). URL: https://unleadedkids.org/special-series-iq/2025/03/04/ Referenced in SRS as [R5, R6].

- **Edge E4_bll_to_sped** (bll_increment_ugdl ➔ special_education_cost_dollars): Point estimate = 11000.0, CI = [4000.0, 25000.0], Validated = 2026-06-14.
  *Citation:* Primary: Gould E, "Childhood lead poisoning: conservative estimates of the social and economic benefits of lead hazard control," Environ Health Perspect 2009; 117(7):1162–1167. DOI: 10.1289/ehp.0800408. PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC2717145/ Gould reports combined medical + special-education cost ~$5,600/child (1998 USD). Inflated to 2026 USD (~×1.82 CPI) ≈ $10,200. Secondary: EPA NCEE Working Paper 2025-04 (April 2025), "Lead Exposure and Special Education: A New Cost Estimate." Estimates annual incremental special-ed cost ~$12,833 (NCES data), lead-attributable fraction applied. URL: https://www.epa.gov/system/files/documents/2025-10/2025_04.pdf Also: NCHH, "The Cost of Inaction: The Economic and Health Burden of Lead Exposure in the United States."

- **Edge E5_bll_to_healthcare** (bll_increment_ugdl ➔ childhood_healthcare_cost_dollars): Point estimate = 7500.0, CI = [3000.0, 12000.0], Validated = 2026-06-14.
  *Citation:* Primary: Trasande L, Liu Y, "Reducing the staggering costs of environmental disease in children, estimated at $76.6 billion in 2008," Health Affairs 2011; 30(5):863–870. DOI: 10.1377/hlthaff.2010.1239. URL: https://www.healthaffairs.org/doi/full/10.1377/hlthaff.2010.1239 Lead accounted for an estimated $50.9B of the $76.6B total 2008 childhood environmental-disease burden (mental retardation + associated costs). Per-child estimate derived by dividing lead-attributable burden by the number of affected children and inflating from 2008 to 2026 USD (×~1.48 CPI).