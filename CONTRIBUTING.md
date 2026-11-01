# Contributing

Thanks for contributing to FinSight AI. The project is currently in planning; application contributions should wait until the architecture and scope are reviewed.

## Working Agreements
- Keep changes small, typed, tested, and documented.
- Do not commit customer financial data, credentials, `.env`, private documents, model artifacts, or unapproved datasets.
- Never claim model quality, compliance, or production readiness without reproducible evidence.
- Preserve tenant isolation across APIs, jobs, caches, exports, logs, and vector retrieval.
- Keep actual financial records separate from derived predictions and simulated scenarios.
- Do not add a financial execution tool or autonomous consequential decision path without explicit product, security, legal, and human-review approval.

## Proposed Workflow
1. Open an issue describing behavior, risk, acceptance criteria, and affected tenant/data boundary.
2. Keep the patch focused and follow existing module ownership.
3. Add unit and integration tests for changed behavior; add negative cross-tenant tests for access changes.
4. Run formatting, lint, type checks, tests, migration checks, and dependency/security scans as they become available.
5. Update API, security, data, model, or user documentation when contracts change.
6. Request review from the domain owner for ML, RAG, privacy, security, and financial semantics as applicable.

## Data and Experiments
Use synthetic or explicitly authorized, scrubbed data. Record source, license/terms, acquisition date, transformations, and evaluation split. Do not copy model outputs into docs until a reproducible experiment has been reviewed. Chronological validation is required for time-dependent tasks.

## Reporting Security Issues
Do not file public issues containing vulnerabilities, credentials, customer information, or exploitable details. A private security reporting contact and response policy must be configured before production use.
