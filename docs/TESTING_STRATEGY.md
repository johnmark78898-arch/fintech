# Testing Strategy

**Status:** Planned verification; no test suite or coverage result is claimed yet.

## Test Layers
- **Unit:** CSV parsing/normalization, feature engineering, forecast inference contract, scenario transformations, document chunk metadata, retrieval filters, citation validation, authorization policy.
- **Integration:** FastAPI + PostgreSQL migrations, Qdrant indexing/retrieval, object storage lifecycle, async jobs, auth, tenant scoping, model artifact loading, configured LLM adapter with deterministic test doubles.
- **System:** upload → validated financial records → forecast → scenario comparison → cited explanation; document deletion/re-index; report generation; role changes and revocation.
- **Performance:** upload parsing, forecast latency, Qdrant retrieval, assistant end-to-end latency, concurrent organization workloads, worker queue saturation.
- **Security:** authentication/session management, authorization/IDOR, tenant isolation, prompt injection, upload/parser limits, CSV formula injection, secret handling, data deletion, rate limits, dependency/image scans.

## Critical Assertions
- Invalid rows never silently enter canonical records; errors identify row/reason without disclosing unrelated data.
- Same scenario inputs and model version reproduce the same outputs within documented numerical tolerance.
- Simulation never mutates source transactions or reported actuals.
- Every prediction records timestamp, model version, input window, horizon, assumptions, and limitations.
- Every citation resolves to a real accessible document/chunk/page; permission revocation blocks later reads.
- Cross-tenant IDs fail for transactions, imports, accounts, documents, Qdrant search, conversations, predictions, scenarios, notifications, and downloads.
- Deleted documents stop retrieval immediately and are eventually removed from all configured stores.
- LLM unavailability or absent evidence yields controlled abstention/fallback, never fabricated citations or predictions.

## ML Evaluation Tests
Use chronological rolling-origin validation and a final untouched period. Unit tests check data cutoff and feature point-in-time behavior; leakage tests inject future-only sentinel columns and verify they cannot influence input features. Compare against naive/seasonal baselines. Report MAE/RMSE by horizon and defined segments; evaluate interval coverage and liquidity-event precision/recall only when validated labels/thresholds exist. No CI test should encode unmeasured accuracy as a pass criterion.

## RAG Evaluation
Maintain a versioned human-reviewed query/evidence set with ACL expectations. Measure Recall@K, Precision@K, MRR, citation correctness, faithfulness, relevance, and abstention. Add adversarial documents containing instruction injection and cross-tenant bait; test the retrieval boundary and generation behavior separately.

## Performance and Reliability Gates
Define numerical service SLOs, max file sizes, concurrency, and recovery targets with pilot users before release. Establish baseline percentiles under representative data volumes, not synthetic-only inference of production capacity. Include dependency outage, retry, duplicate job, database restore, and partial deletion scenarios.

## CI and Release
Run formatting, lint, type checks, unit tests, integration tests with isolated service containers, migration checks, dependency/security scans, and frontend tests. Block release on tenant isolation, citation integrity, migration, or critical vulnerability failures. Keep test data synthetic or explicitly authorized and scrubbed. Store test artifacts without raw sensitive payloads.
