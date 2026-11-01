# Development Roadmap

**Status:** Proposed stages and gates. Dates are intentionally not estimated until team capacity and acceptance thresholds are known.

## Delivery Principles
- Planning and documentation are reviewed before application code.
- Build small end-to-end slices; test each before moving on.
- Tenant authorization is part of the backend foundation before any customer-data endpoint, even though the detailed authentication milestone appears later in the supplied sequence.
- A model module is not production-ready without lawful data, a baseline, leakage-safe evaluation, human review where consequential, and measured results.
- Keep actual, derived, and simulated data separate. Never ship placeholder predictions as real.

## Ordered Phases
1. Project planning and requirements: confirm SMB pilot, use case, metrics, data, geography, privacy, and scope.
2. Documentation and architecture: review project plan, architecture, schema, API, ML/RAG plans, dataset, security, tests, deployment, user guide, and roadmap; obtain approval before application code.
3. Database schema and backend foundation: migrations, health, config, logging, API contracts, identity and tenant authorization baseline.
4. Financial data ingestion and preprocessing: CSV schema/mapping, validation, provenance, duplicates, row errors, import lifecycle.
5. Cash-flow forecasting model: baselines first, chronological backtests, acceptance gate, versioned inference.
6. Credit default model: gated on permitted, representative labels and legal/fairness review; otherwise remain documented only.
7. Fraud detection model: gated on validated fraud labels, operations capacity, and human investigation workflow.
8. Financial distress model: target definition, data sufficiency, leakage analysis, and independent validation gate.
9. RAG document ingestion: upload checks, extraction, page metadata, chunking, document ACLs, deletion.
10. Vector database and retrieval: Qdrant lifecycle, authorization filters, ranking, retrieval evaluation.
11. ML + RAG integration: typed prediction context, cited evidence, uncertainty, prompt injection defenses.
12. Financial simulation engine: immutable actuals, validated assumptions, baseline/simulated comparison.
13. Authentication and authorization: complete role management, session lifecycle, MFA/admin controls, revocation and tests; minimum tenant authorization was already required in phase 3.
14. Frontend dashboard: responsive cash-flow, forecast, scenario, document, and audit workflows.
15. AI conversational interface: history, follow-ups, citations, evidence gaps, provider controls.
16. Reports and notifications: exports, alerts, provenance, permission and retention controls.
17. Testing and optimization: unit/integration/system/performance/security, ML/RAG evaluation, accessibility, tuning.
18. Docker deployment: local reproducibility followed by secured staging, operational review, restore and release checks.
19. Final documentation and demonstration: update actual architecture/results, prepare labeled demo data, known limitations, and acceptance evidence.

## First Vertical Slice
After phase 2 approval: authenticated organization context → CSV upload/validation → tenant-scoped cash records → baseline forecast/backtest → one scenario comparison → metadata-rich response. Add document Q&A either as part of this slice after retrieval/privacy approval or as the first follow-on; the choice remains open.

## Exit Criteria
Each phase has acceptance tests and a named reviewer. Before production: legal/privacy/security review; no open critical tenant-isolation issues; restore/deletion verification; model and retrieval evaluation evidence; threat model and incident plan; documented SLOs; provider data-processing approval; human-facing limitations and support process.
