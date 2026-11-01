# FinSight AI Project Plan

**Status:** Planning baseline, 2026-11-01. No application code or model results are represented as complete.

## Project Overview
FinSight AI is a proposed financial decision-support platform combining customer-owned financial records, forecasts, financial-document retrieval, grounded explanations, and scenario simulation. Initial audience is U.S. small and medium-sized business (SMB) finance teams. The first release is scoped to manual CSV ingestion, cash-flow forecasts, liquidity warnings, and what-if scenarios. It is not an autonomous finance agent or a substitute for accounting, lending, legal, or investment advice.

## Problem Statement
SMB operators may lack a consolidated, forward-looking view of cash position and may not be able to quickly trace a forecast to its input records or test the effect of changed assumptions. Data may be fragmented, inconsistent, incomplete, or stale. Explanations without provenance can create false confidence.

## Business Objectives
- Help a finance user inspect incoming historical cash-flow data and identify data-quality issues.
- Provide reproducible, time-aware cash projections and clearly qualified liquidity-risk signals.
- Let users compare baseline results with explicitly labeled scenario assumptions.
- Ground explanatory answers in authorized financial records and cited documents.
- Preserve tenant isolation, provenance, auditability, and human control.

## Target Audience
Initial: U.S. SMB owners, controllers, and finance analysts with authority to upload their organization's financial records. Later audiences (lenders and institutional risk teams) are out of MVP scope and require separate product, data, legal, fairness, and operational review.

## Proposed Solution and MVP
1. Authenticated organization workspace with tenant-scoped permissions.
2. CSV upload and schema validation for dated cash movements and/or balances.
3. Data-quality feedback, normalized records, and import provenance.
4. A baseline forecast with supported horizons of 7, 30, and 90 days where coverage permits.
5. A scenario engine that changes specified assumptions without altering actual history.
6. Optional document retrieval for an explanation only when relevant authorized source material exists; missing evidence is stated.
7. Clear forecast timestamps, model/version information, assumptions, and limitations.

Credit default, fraud, and financial-distress prediction are roadmap capabilities only. No fake production predictions or unvalidated model output.

## Main Features
- Organization, user, role, and permission management.
- Financial CSV ingestion, validation, transaction/account records, and summaries.
- Cash-flow forecasting, liquidity indicators, historical comparison, and prediction history.
- Document upload/index/delete/re-index with page-level citations and permission checks.
- Grounded financial assistant that explains model results and retrieved evidence separately.
- Scenario inputs, reproducible transformations, baseline comparison, and exportable reports.
- Audit events, alerts, and data deletion workflow.

## Functional Requirements
- Validate file type, size, encoding, required columns, date ranges, currencies, duplicates, and numeric fields before import.
- Associate every imported record and derived artifact with an organization and source/import batch.
- Reject or quarantine invalid rows with actionable, non-sensitive error messages.
- Forecast only for supported time coverage; distinguish an unavailable forecast from a low-risk forecast.
- Persist model name/version, run time, input window, horizon, assumptions, and output for every prediction.
- Keep actual, derived, and simulated data distinguishable in storage and UI.
- Return document citations that resolve to an accessible source and page/chunk.
- Support user-controlled deletion of uploaded data, documents, conversations, and organization records subject to retention obligations.
- Never execute transfers, lending decisions, or enforcement actions.

## Non-Functional Requirements
- Tenant isolation enforced in service and persistence layers; test negative cross-tenant access.
- Encryption in transit and at rest through deployment-managed controls; no credentials in source control.
- Auditable access and consequential changes with actor, organization, timestamp, and resource.
- Accessible, responsive UI; explicit loading, empty, stale-data, validation, and error states.
- Reproducible model and scenario runs; bounded resource use for uploads and inference.
- Operational observability for API, ingestion, retrieval, model latency, and failures without logging raw financial data or secrets.
- Availability, recovery objectives, retention, and latency targets to be set before production.

## Competitive Analysis
A limited desk review of official product pages indicates adjacent offerings, not a complete market study:
- Stripe Sigma describes analysis/reporting over Stripe data, including custom SQL, templates, AI-assisted query/report creation, and programmatic query access. It is tightly described around Stripe data; this is an adjacent analytics reference, not evidence of a direct feature-for-feature comparison. Source: https://stripe.com/sigma (accessed 2026-11-01).
- Float's public homepage currently emphasizes resource planning, project delivery, utilization, and margin reporting for service teams; it is not treated here as a direct cash-management forecasting comparator. Source: https://www.float.com/ (accessed 2026-11-01).
- A proposed QuickBooks cash-flow page and Plaid product pages could not be reliably extracted during this research pass, so no claims about those products are made.

This review is not exhaustive and reflects vendor-published descriptions, not independent product testing. Before asserting differentiation, research focused cash forecasting, accounting platforms, treasury/cash management, open-banking aggregation, and finance copilots; compare supported data sources, forecast evidence, scenario capabilities, provenance, target segment, geography, and pricing using dated sources.

## Unique Value Hypothesis
A unified, inspectable workflow that connects customer data, versioned forecasts, reproducible what-if scenarios, and permission-filtered cited evidence may be valuable to SMB finance teams. Validate through interviews and prototype tasks; do not present this as proven market differentiation.

## Technical Challenges and Risks
- Sparse or inconsistent SMB cash data; business seasonality and one-off events.
- Forecast uncertainty, concept drift, leakage, and insufficient history for long horizons.
- CSV formula injection, malicious files, oversized inputs, and incorrect mappings.
- Cross-tenant leakage through APIs, vector search filters, caches, exports, or logs.
- Prompt injection in documents, unsupported claims, false citations, and model/provider outages.
- Sensitive personal or business data, retention/deletion obligations, U.S. regulatory applicability, and third-party data rights.
- Fairness, explainability, and human review requirements if the platform later supports credit or fraud decisions.

## Limitations
Forecasts are estimates conditional on historical data and assumptions; they are not guaranteed outcomes. Initial planning does not establish a validated model, dataset, compliance posture, production SLA, or investment/credit suitability. Public macroeconomic series may contextualize trends but cannot replace organization-specific cash records. U.S. jurisdiction is a planning assumption requiring counsel/compliance review.

## Success Metrics
Set numeric acceptance thresholds with pilot users before evaluation. Measure:
- Import success and row-level validation error rates on representative customer CSVs.
- Forecast MAE/RMSE by horizon and organization/time backtest; use percentage metrics only when numerically meaningful.
- Liquidity-warning precision/recall and calibration only when event definitions and labels exist.
- Scenario reproducibility and exact preservation of actual records.
- RAG Recall@K, MRR, citation correctness, answer faithfulness, and relevance on a reviewed test set.
- Tenant-isolation test pass rate, deletion verification, latency, and user task completion.
No metric result or accuracy claim is available until measured.

## Development Phases
1. Planning, requirements, source research, and approval gates.
2. Architecture, schema, API, threat model, dataset and evaluation plans; review before application code.
3. Backend foundation with authentication/tenant authorization before any customer-data API.
4. CSV ingestion and data quality.
5. Cash-flow baseline, chronological evaluation, then forecast API.
6. Document processing, permission-filtered Qdrant retrieval, and citation evaluation.
7. Grounded ML + RAG explanation workflow.
8. Reproducible scenario simulation.
9. Dashboard, reports, alerts, integration tests, and operational controls.
10. Later credit, fraud, and distress modules only after data, legal, fairness, and model-evaluation gates.
11. Deployment hardening, monitoring, recovery, and production readiness review.

## Approval Gates / Open Questions
- Confirm representative CSV formats, source systems, account/balance semantics, currency, timezone, and minimum historical coverage.
- Define forecast acceptance thresholds, liquidity event definition, and whether document Q&A is MVP or follow-on.
- Decide retention/deletion, hosting region, identity provider, and production security/compliance obligations.
- Approve model/data governance and whether external LLM/embedding providers may receive selected content.
- Complete broader competitor research and customer discovery before claiming a differentiator.
