# Devpost Submission Answers

### Responsible-AI Guardrail (Max 500 chars)
Our system employs three primary guardrails: 1) Stigmatizing, socially-sensitive edges (e.g., childhood BLL to crime rate) are disabled by default and require explicit administrative consent, which is appended to an immutable audit record. 2) The system implements a strict abstention gate that blocks 'must-fund-now' recommendations when the 95% credible interval spans below 1.0. 3) Output is framed exclusively at the population/budget level; address-level risk scoring is prohibited.

*Character Count:* 472 characters

---

### Human-in-the-Loop (Max 500 chars)
The system informs, but never decides: 1) Capital allocation rankings are presented with full uncertainty bands, leaving prioritization to human finance/water officers. 2) Inclusion of contested causal edges (e.g., lead to crime or adult mortality) requires conscious administrative authorization, making the scope of cost liability a human policy choice. 3) Sobol sensitivity indices highlight the primary driver of output spread, directing leadership on where to commission studies next.

*Character Count:* 489 characters
