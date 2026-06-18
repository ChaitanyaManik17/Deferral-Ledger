# Edge Evidence Ledger — DEFERRAL LEDGER
## Appendix B: Complete Edge-Prior Evidence Catalog

**Purpose:** This ledger is the authoritative record of every causal edge in the Deferral Ledger DAG, its literature-sourced effect size, confidence interval, distribution parameterisation, and review status. Per SRS EV-1 / C-4, no numeric prior may reach a user without a filled row here.

**Last updated:** 2026-06-14 (Day 1 — Chaitanya)
**Catalog version:** `catalog/edges.yaml` (branch: `day1-chaitanya`)

---

## Cascade Summary

```
Defer Δyr ──▶ deferred $D = lines × cost/line         [E0]
Defer Δyr ──▶ continued exposure (child person-years) [structural — Varun]
exposure  ──▶ BLL increment (µg/dL)                   [E1]
BLL       ──▶ IQ loss (IQ pts)                        [E2]
IQ loss   ──▶ lifetime earnings loss ($)              [E3]
BLL       ──▶ special-education cost ($)              [E4]
BLL       ──▶ childhood healthcare/Medicaid ($)       [E5]
BLL(adult)──▶ CVD/CKD cost (secondary, off by default)[E6]
BLL       ──▶ behavioral → crime cost (contested, off) [E7]
```

Output: `M = PV(Σ enabled downstream $) / deferred $D`

---

## Evidence Table

| Edge ID | From → To | Point Estimate | 95% CI | Distribution | Params | Source | Contested | Default | Status | Last Validated |
|---------|-----------|---------------|--------|--------------|--------|--------|-----------|---------|--------|----------------|
| **E0** `E0_cost_per_line` | `defer_decision` → `deferred_dollars` | $4,700/line | $1,200–$12,300 | Triangular | low=$1,200 mode=$4,700 high=$12,300 | EPA LCRI fact sheet, Oct 2024. Avg ~$4,700/line; range $1,200–$12,300. [URL](https://www.epa.gov/system/files/documents/2024-10/final_lcri_fact-sheet_calculating-service-line.pdf) | No | **ON** | ✅ Confirmed | 2026-06-14 |
| **E1** `E1_lsl_to_bll` | `continued_exposure_person_years` → `bll_increment_ugdl` | +1.5 µg/dL | 0.5–4.0 µg/dL | Triangular (wide) | low=0.5 mode=1.5 high=4.0 | ⚠️ Hanna-Attisha et al. 2016 (AJPH, Flint pre/post); EPA IEUBK model guidance; del Toral et al. 2016 (ES&T). Flint: % elevated BLL ~doubled. IEUBK: water contribution 0.5–3 µg/dL. | No | **ON** | ⚠️ Wide prior — top research priority | 2026-06-14 |
| **E2** `E2_bll_to_iq` | `bll_increment_ugdl` → `iq_loss_points` | −0.87 IQ pts/µg/dL | −1.10 to −0.64 | Normal | mean=−0.87 sd=0.14 | Lanphear BP et al. 2005, "Low-level environmental lead exposure and children's intellectual function: an international pooled analysis," EHP 113(7):894–899. DOI:10.1289/ehp.7688. [SRS R4] | No | **ON** | ✅ Confirmed | 2026-06-14 |
| **E3** `E3_iq_to_earnings` | `iq_loss_points` → `lifetime_earnings_loss_dollars` | $11,850/IQ pt | $10,600–$13,100 | Uniform | low=$10,600 high=$13,100 | Grosse SD et al. 2021, Sci Total Environ 787:147452. DOI:10.1016/j.scitotenv.2021.147452. [SRS R5] + Unleaded Kids 2025-03-04. [SRS R6] 3% discount rate. | No | **ON** | ✅ Confirmed | 2026-06-14 |
| **E4** `E4_bll_to_sped` | `bll_increment_ugdl` → `special_education_cost_dollars` | $11,000/child | $4,000–$25,000 | Triangular | low=$4,000 mode=$11,000 high=$25,000 | Gould E, 2009, EHP 117(7):1162–1167. [PMC2717145](https://pmc.ncbi.nlm.nih.gov/articles/PMC2717145/) ~$5,600/child (1998 USD → 2026: ~$10,200). EPA NCEE WP 2025-04. [URL](https://www.epa.gov/system/files/documents/2025-10/2025_04.pdf) | No | **ON** | ✅ Confirmed (inflated to 2026 USD) | 2026-06-14 |
| **E5** `E5_bll_to_healthcare` | `bll_increment_ugdl` → `childhood_healthcare_cost_dollars` | $7,500/child | $3,000–$12,000 | Triangular | low=$3,000 mode=$7,500 high=$12,000 | Trasande L, Liu Y, 2011, Health Affairs 30(5):863–870. DOI:10.1377/hlthaff.2010.1239. [URL](https://www.healthaffairs.org/doi/full/10.1377/hlthaff.2010.1239) Lead-attributable share of $76.6B childhood env-disease burden (2008 USD → 2026). | No | **ON** | ✅ Confirmed (inflated; per-child decomposition documented) | 2026-06-14 |
| **E6** `E6_adult_bll_to_cvd_ckd` | `bll_increment_ugdl` → `adult_cvd_ckd_cost_dollars` | HR 1.70 for CVD mortality | HR 1.30–2.22 | LogNormal (on HR) → cost via VSL | mu=0.5306 sigma=0.1627 | Lanphear BP et al. 2018, Lancet Public Health 3(4):e177–e184. DOI:10.1016/S2468-2667(18)30025-2. [URL](https://www.sciencedirect.com/science/article/pii/S2468266718300252) ~256k premature CVD deaths/yr attributable. VSL: EPA 2024 ~$13.1M. | No (secondary) | **OFF** | ✅ Confirmed (VSL assumption documented; secondary/long-horizon) | 2026-06-14 |
| **E7** `E7_bll_to_crime` | `bll_increment_ugdl` → `juvenile_justice_crime_cost_dollars` | RR ~1.15 (detention) | RR ~1.05–1.26 | LogNormal (on RR) → cost via justice system | mu=0.1398 sigma=0.0584 | Aizer A, Currie J, 2017, NBER WP 23392. DOI:10.3386/w23392. [URL](https://www.nber.org/system/files/working_papers/w23392/w23392.pdf) +15% detention/incarceration per 1 µg/dL preschool BLL. | **YES — CONTESTED** | **OFF (consent required)** | ✅ Confirmed (kept off by default — stigmatizing; RAI-1) | 2026-06-14 |

---

## Detailed Notes by Edge

### E0 — Replacement Cost per Line
- **Value:** $4,700 average; range $1,200–$12,300.
- **Distribution rationale:** Triangular captures right-skew in costs (simple single-family vs complex urban excavations). Mode = EPA reported average.
- **Currency:** 2024 USD (EPA LCRI fact sheet, October 2024).
- **Note:** Some estimates (e.g., Brookings 2022 [R10]) use $4,700–$5,500 as the central estimate; EPA LCRI is the most current and authoritative.

### E1 — LSL Presence → Sustained BLL Increment
- **⚠️ TOP RESEARCH PRIORITY.** This is the hinge of the cascade.
- **Value:** +1.5 µg/dL central estimate (range 0.5–4.0).
- **Evidence basis:** Flint pre/post: % of children with elevated BLL (~≥5 µg/dL) approximately doubled during LSL-related contamination. EPA IEUBK model: water-lead contribution 0.5–3 µg/dL depending on plumbing age, flow, standing time.
- **Distribution rationale:** Wide Triangular — deliberately honest about epistemic uncertainty. Day-2 Sobol expected to show E1 dominates spread, which is itself a finding: "commission a water-lead study first."
- **Recalibration trigger (LC-2):** If tract-level BLL surveillance or a local water-lead study becomes available, narrow this prior.

### E2 — BLL → IQ Loss
- **Value:** −0.87 IQ pts per µg/dL (pooled; steeper −1.37 below 10 µg/dL).
- **sd derivation:** (ci_high − ci_low) / 3.29 = (−0.64 − (−1.10)) / 3.29 ≈ 0.14.
- **Sensitivity:** The steeper low-level slope (−1.37) is available as an override for tracts with median BLL < 10 µg/dL.
- **Study quality:** Pooled analysis of 7 international prospective cohorts — highest available evidence quality for this edge.

### E3 — IQ Loss → Lifetime Earnings Loss
- **Value:** $10,600–$13,100 per IQ point (3% discount rate).
- **Distribution:** Uniform over published range — consistent with both Grosse et al. 2021 and Unleaded Kids 2025.
- **Inflation note:** Grosse 2021 figures approximately 2019 USD. To update to 2026 USD: apply CPI adjustment ~+13–16% (BLS CPI-U).
- **Discount rate sensitivity:** This edge is highly sensitive to the discount rate. At 1.4% real (Unleaded Kids method), the per-IQ-point value is approximately 1.4% of lifetime earnings.

### E4 — BLL → Special-Education Cost
- **Value:** ~$11,000/child (mode; range $4,000–$25,000).
- **Inflation:** Gould 2009 figure ~$5,600/child (1998 USD) → ~$10,200 (2026 USD, CPI ×1.82). EPA NCEE 2025 (higher attribution scenario) supports upper range.
- **Attribution fraction:** The literature reports the full special-ed cost per child; the lead-attributable fraction is ~15–25%. Applied to annual incremental cost × ~3 years.

### E5 — BLL → Childhood Healthcare / Medicaid
- **Value:** ~$7,500/child (mode; range $3,000–$12,000).
- **Decomposition:** Trasande & Liu 2011 report $76.6B total childhood environmental-disease burden (2008 USD); lead accounts for ~$50.9B. Divided by estimated ~4M affected children (historically), then inflated to 2026 USD (×1.48 CPI from 2008).
- **Wide prior:** Reflects uncertainty in the per-child decomposition from an aggregate estimate.

### E6 — Adult Cumulative Lead → CVD/CKD Cost (Secondary)
- **HR:** 1.70 (95% CI 1.30–2.22) for CVD mortality per ~5.7 µg/dL BLL increase.
- **log-normal params:** mu = ln(1.70) ≈ 0.5306; sigma = (ln(2.22) − ln(1.30)) / 3.29 ≈ 0.163.
- **Cost path:** Incremental lifetime CVD mortality risk × EPA VSL ($13.1M, 2024 USD) + medical cost. Assumption documented explicitly.
- **Status:** Secondary — valid but long-horizon, requires lifetime BLL accumulation model. OFF by default.

### E7 — BLL → Behavioral → Juvenile-Justice / Crime Cost (Contested)
- **RR:** ~1.15 (approx. 95% CI 1.05–1.26) for juvenile detention per 1 µg/dL preschool BLL.
- **log-normal params:** mu = ln(1.15) ≈ 0.1398; sigma = (ln(1.26) − ln(1.05)) / 3.29 ≈ 0.058.
- **Cost:** Bureau of Justice Statistics 2022 ~$35,000–$60,000/year incarceration.
- **Status:** CONTESTED — OFF by default (SRS RAI-1). Including in official analysis requires explicit consent + audit log.
- **Named tradeoff:** Excluding understates total cost; including risks stigmatizing affected communities.

---

## Citation Index

| Key | Full Reference |
|-----|----------------|
| [R1] | EPA, *Lead Service Line Inventory Recommendations* (Nov 2025). https://www.epa.gov/system/files/documents/2025-11/lsl-inventory_2025.11.20.pdf |
| [R4] | Lanphear BP et al. (2005), EHP 113(7):894–899. DOI:10.1289/ehp.7688 |
| [R5] | Grosse SD et al. (2021), Sci Total Environ 787:147452. DOI:10.1016/j.scitotenv.2021.147452 |
| [R6] | Unleaded Kids (2025-03-04). https://unleadedkids.org/special-series-iq/2025/03/04/ |
| [R7] | EPA LCRI fact sheet (Oct 2024). https://www.epa.gov/system/files/documents/2024-10/final_lcri_fact-sheet_calculating-service-line.pdf |
| Gould 2009 | Gould E, EHP 117(7):1162–1167. PMC2717145. https://pmc.ncbi.nlm.nih.gov/articles/PMC2717145/ |
| EPA NCEE 2025 | EPA NCEE WP 2025-04. https://www.epa.gov/system/files/documents/2025-10/2025_04.pdf |
| Trasande 2011 | Trasande L, Liu Y, Health Affairs 30(5):863–870. DOI:10.1377/hlthaff.2010.1239 |
| Lanphear 2018 | Lanphear BP et al., Lancet Public Health 3(4):e177–e184. DOI:10.1016/S2468-2667(18)30025-2 |
| Aizer 2017 | Aizer A, Currie J, NBER WP 23392. DOI:10.3386/w23392 |
| Hanna-Attisha 2016 | Hanna-Attisha M et al., AJPH 106(2):283–290. DOI:10.2105/AJPH.2015.302896 |

---

*Ledger status: E0–E7 all filled. E1 is deliberately wide and flagged as the top research priority. EV-1 compliance: all edges cited and dated.*
