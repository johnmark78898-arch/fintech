# API Documentation

**Status:** The CSV upload route and health endpoints are implemented; other routes below remain proposed. All application routes are under `/api/v1` unless noted. TLS is required outside local development.

## API Rules
- Authentication required except health checks and explicitly public registration routes.
- Resolve organization membership and permissions server-side. A body/path `organization_id` never grants access.
- JSON uses ISO-8601 UTC timestamps, ISO 4217 currency codes, UUID identifiers, and decimal strings for money.
- Errors use `{ "error": { "code": "...", "message": "...", "request_id": "...", "details": [] } }`; do not expose stack traces or sensitive row contents.
- Enforce request/body limits, upload limits, rate limits, idempotency for creation endpoints, and audit events for sensitive operations.
- Paginate collection endpoints with opaque `cursor` and bounded `limit`.

## Shared Schemas
```json
{
  "Money": {"amount": "1234.5600", "currency": "USD"},
  "Page": {"items": [], "next_cursor": null},
  "Job": {"id": "uuid", "status": "queued|running|succeeded|failed", "created_at": "timestamp", "error": null}
}
```

## Authentication
- Implemented routes accept a Bearer JWT issued by a configured OIDC provider. Verify `RS256` signature against `AUTH_JWKS_URL`, `iss`, `aud`, `exp`, `iat`, and `sub`; map `sub` to an active, pre-provisioned user. Configure `AUTH_ISSUER`, `AUTH_AUDIENCE`, and `AUTH_JWKS_URL`.
- `POST /api/v1/auth/register`, `/login`, `/refresh`, `/password-reset`, and `GET /api/v1/me` are not implemented. User provisioning and identity-provider choice remain deployment responsibilities.

## Organizations and Access
- `GET /api/v1/organizations` — List only organizations where caller has active membership.
- `POST /api/v1/organizations/{organization_id}/members` — Owner/admin only; request `{email, role_key}`; response membership/invitation state.
- `PATCH /api/v1/organizations/{organization_id}/members/{membership_id}` — Admin role change or deactivation; audited.

## Financial Data

The CSV importer accepts common header aliases, signed amounts, and separate debit/credit columns. Persistent rows still require a timezone-aware date and currency; account and direction can be inferred or defaulted.
- `POST /api/v1/organizations/{organization_id}/imports/csv` — Implemented multipart field `file` (CSV, max 10 MiB). Requires a valid Bearer JWT, provisioned active user, and active organization membership with `owner`, `admin`, or `analyst` role. Response `201 {import_id,status,total_rows,inserted_rows,duplicate_rows,rejected_rows,row_errors:[{row_number,code}]}`. Rows are validated and persisted in the request transaction; raw row values are not returned in errors.
- `GET /api/v1/imports/{import_id}` — Status `{id,status,row_count,accepted_count,rejected_count,errors:[{row,code,message}]}`; permission checked.
- `GET /api/v1/transactions` — Query `account_id`, `from`, `to`, `cursor`, `limit`; response page of `{id,occurred_at,description,amount,currency,direction,category,source}`.
- `POST /api/v1/transactions` — Optional manual entry after validation; request `{account_id,occurred_at,description,amount,currency,direction,category}`; response transaction. Idempotency supported.
- `GET /api/v1/financial/summary` — Query `as_of`, optional period; response `{as_of,currency,period,revenue,expenses,cash_balance,source_freshness,limitations}` with explicit provenance and no invented values.

## Predictions
- `POST /api/v1/predictions/cashflow` — Request `{horizon_days: 7|30|90, as_of?, account_ids?, scenario_id?}`. Response `202 {job_id,status_url}` or synchronous result if within latency budget.
- `GET /api/v1/predictions/{prediction_id}` — Response `{id,type,generated_at,model:{key,version},input_window,horizon_days,points:[{date,cash_balance,lower_bound?,upper_bound?}],liquidity_warnings:[{date,threshold,estimated_balance}],assumptions,limitations,scenario_id}`. Confidence intervals are included only if calibrated/evaluated.
- `POST /api/v1/predictions/default`, `/fraud`, `/distress` — Not available in MVP; later contracts must include human-review status, limitations, and model metadata.
- `GET /api/v1/predictions/history` — Query `type`, `from`, `to`, cursor; organization-scoped results.

## Documents and RAG
- `GET /api/v1/public-library/status` — Status and provenance for the locally indexed SBA and IRS public-text sources. Returns `503` until the local ingestion script has run.
- `GET /api/v1/public-library/search?query=...` — Lexically retrieves bounded passages from the public source index and returns the exact source URL, edition, section, and passage identifier. This is retrieval only; it does not generate an AI answer.
- `POST /api/v1/documents/upload` — Multipart PDF/DOCX/TXT/CSV plus metadata `{document_type,source,access_level}`; response `202 {document_id,job_id,status_url}`. Validate content, size, parser limits, ACL, and malware scanning status.
- `GET /api/v1/documents` — Query type/status/cursor; returns authorized metadata only.
- `GET /api/v1/documents/{document_id}` — Authorized metadata and indexing state.
- `DELETE /api/v1/documents/{document_id}` — Authorized soft-delete plus asynchronous removal from object storage/vector index; response `{deletion_job_id,status}`.
- `POST /api/v1/documents/{document_id}/reindex` — Admin/editor permission; response job.
- `POST /api/v1/assistant/chat` — Request `{conversation_id?,question,prediction_id?,document_ids?}`. Response `{conversation_id,message:{id,content,created_at},model:{key,version},prediction_reference?,citations:[{document_id,name,page_number,chunk_id,quote}],evidence_gaps:[],limitations:[]}`. Citation IDs are server-validated; no citation may be generated without retrieved evidence.
- `GET /api/v1/assistant/conversations` and `GET /api/v1/assistant/conversations/{id}` — Paginated, authorized history; messages and citations are tenant-scoped.

## Scenarios
- `POST /api/v1/scenarios` — Request `{name,base_prediction_id?,assumptions:[{kind,value,effective_from,effective_to?,currency?,source?}]}`; response scenario. Validate ranges and supported assumption types.
- `POST /api/v1/scenarios/{scenario_id}/simulate` — Request `{horizon_days:7|30|90}`; response `202` job or result.
- `GET /api/v1/scenarios/{scenario_id}` — Returns assumptions, state, baseline reference, simulation reference, created_by, timestamps.
- `GET /api/v1/scenarios/history` — Paginated organization-scoped scenarios.
- Simulation response includes `{scenario_id,simulated:true,baseline_prediction,simulated_prediction,delta,assumptions,limitations}`. Actual ledger entries are never mutated.

## Reports and Alerts
- `POST /api/v1/reports/generate` — Request `{report_type,period_start,period_end,format:"csv|pdf",prediction_ids?,scenario_ids?}`; response `202 {job_id}`.
- `GET /api/v1/reports` — Authorized generated reports metadata.
- `GET /api/v1/reports/{id}/download` — Short-lived authorized download; audit and tenant checks.
- `GET /api/v1/notifications` and `PATCH /api/v1/notifications/{id}` — Read/list or mark read; cannot alter underlying prediction.

## Status and Operations
- `GET /api/v1/demo/uci-online-retail-sample.csv` — Public, attributed demo CSV for UI/CSV parser previews. This endpoint serves only the small UCI sales/returns sample; it is not bank or cash-flow data.
- `GET /api/v1/public-library/status` and `/search` — Public-source metadata and lexical retrieval endpoints.
- `POST /api/v1/public-library/answer` — Request `{question,dataset?}`; returns `{answer,citations,abstained,data_based,model}` using local Ollama. Dataset mode uses bounded aggregate transaction context and does not retrieve public passages; public-guidance mode omits `dataset` and uses retrieved SBA/IRS passages with validated citations. The browser sends summaries only, not raw transaction rows. Configure `OLLAMA_BASE_URL` as a local-only HTTP endpoint and `OLLAMA_MODEL`; start Ollama and install the model before use. Private-document RAG and embeddings are not implemented.
- `GET /health/live` — process liveness only.
- `GET /health/ready` — dependency readiness without secrets.
- `GET /api/v1/jobs/{job_id}` — Job status scoped to caller's organization.

## Contract Validation
Maintain OpenAPI snapshots and contract tests. Test invalid values, authorization failures, pagination, duplicate idempotency keys, upload rejection, citation referential integrity, and cross-tenant access for every resource family.
