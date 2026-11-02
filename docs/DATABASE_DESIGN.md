# Database Design

**Status:** Logical design for review. PostgreSQL is proposed for structured records; Qdrant is a derived vector index. Exact DDL and migrations follow approval.

## Conventions and Tenant Isolation
- Use UUID primary keys, `timestamptz` UTC timestamps, and `numeric(20, 4)` for financial values; store ISO 4217 currency codes separately. Never use binary floating-point for money.
- Tenant-owned tables include non-null `organization_id`; composite foreign keys include organization ownership where practical to prevent cross-tenant references.
- Every service query scopes by server-resolved organization membership. Consider PostgreSQL row-level security as defense in depth. Tenant IDs from clients are selectors only after membership authorization, never proof of access.
- Use restrictive foreign keys, explicit deletion/retention policy, audit events, and indexes beginning with `organization_id` for tenant-scoped reads.
- Sensitive fields should be minimized and encrypted through managed database/storage controls. Avoid storing credentials or unnecessary personal data.

## Tables
Types below are logical PostgreSQL types. `id` is UUID primary key unless otherwise noted. All tenant-owned rows carry `organization_id UUID NOT NULL REFERENCES organizations(id)` unless the table itself defines the tenant.

| Table | Core columns and constraints | Relationships and indexes |
|---|---|---|
| `organizations` | `id`, `name`, `legal_name NULL`, `country_code CHAR(2)`, `default_currency CHAR(3)`, `timezone`, `status`, `created_at`, `updated_at`; country/currency validated | Root tenant. Index `(status, created_at)` |
| `users` | `id`, `email CITEXT UNIQUE`, `display_name`, `auth_subject UNIQUE`, `status`, `created_at`, `updated_at`, `last_login_at NULL`; no local password unless auth design requires it | Global identity; index email and auth subject |
| `roles` | `id`, `key UNIQUE`, `name`, `description`, `is_system` | Reference data; keys include owner, admin, analyst, viewer |
| `permissions` | `id`, `key UNIQUE`, `description` | Reference data for least-privilege actions |
| `role_permissions` | `role_id`, `permission_id`; composite PK and FKs | Index `permission_id` |
| `organization_memberships` | `id`, `organization_id`, `user_id`, `role_id`, `status`, `created_at`, `created_by`; `UNIQUE(organization_id,user_id)` | FKs to organizations/users/roles; indexes `(user_id,status)`, `(organization_id,status)` |
| `financial_accounts` | `id`, tenant, `external_ref NULL`, `name`, `account_type`, `currency CHAR(3)`, `status`, `source`, `created_at`; unique scoped external ref when present | Transactions; index `(organization_id,status)` |
| `import_batches` | `id`, tenant, `uploaded_by`, `filename`, `sha256`, `source`, `status`, `row_count`, `accepted_count`, `rejected_count`, `started_at`, `completed_at NULL`, `error_summary NULL` | User FK; unique `(organization_id,sha256, id)` is not dedupe policy; indexes `(organization_id,created_at)` and status |
| `transactions` | `id`, tenant, `account_id`, `import_batch_id NULL`, `external_ref NULL`, `occurred_at`, `posted_at NULL`, `description`, `amount NUMERIC(20,4)`, `currency`, `direction`, `category NULL`, `is_pending`, `source_hash`, `created_at`; scoped dedupe key policy | Scoped FKs; indexes `(organization_id,occurred_at)`, `(organization_id,account_id,occurred_at)`, `(organization_id,category,occurred_at)` |
| `customers` | `id`, tenant, `external_ref NULL`, `display_name`, `status`, `created_at`; minimize PII | Index `(organization_id,external_ref)`; avoid customer-level credit use in MVP |
| `invoices` | `id`, tenant, `customer_id NULL`, `external_ref NULL`, `issued_at`, `due_at NULL`, `paid_at NULL`, `amount`, `currency`, `status`, `created_at` | Scoped customer FK; indexes `(organization_id,due_at,status)` |
| `loans` | `id`, tenant, `external_ref NULL`, `customer_id NULL`, `principal`, `currency`, `rate_type NULL`, `interest_rate NULL`, `opened_at`, `maturity_at NULL`, `status`, `created_at` | Scoped customer FK; MVP may omit ingestion; indexes `(organization_id,status,maturity_at)` |
| `financial_reports` | `id`, tenant, `report_type`, `period_start`, `period_end`, `currency`, `source`, `status`, `created_at`; check start <= end | Index `(organization_id,report_type,period_end)` |
| `model_versions` | `id`, `model_key`, `version`, `artifact_uri`, `feature_schema_version`, `training_data_ref`, `metrics JSONB`, `status`, `created_at`; `UNIQUE(model_key,version)` | Registry metadata; index `(model_key,status)`; artifact access restricted |
| `predictions` | `id`, tenant, `model_version_id`, `prediction_type`, `input_window_start`, `input_window_end`, `horizon_days`, `generated_at`, `output JSONB`, `assumptions JSONB`, `limitations TEXT`, `status`, `scenario_id NULL` | Scoped tenant and model FK; index `(organization_id,prediction_type,generated_at DESC)` |
| `risk_assessments` | `id`, tenant, `subject_type`, `subject_id`, `assessment_type`, `score NUMERIC NULL`, `band NULL`, `model_version_id NULL`, `generated_at`, `human_review_status`, `reviewed_by NULL`, `reviewed_at NULL`, `details JSONB` | Later capability; index `(organization_id,assessment_type,generated_at DESC)` |
| `fraud_alerts` | `id`, tenant, `transaction_id`, `model_version_id NULL`, `score`, `reason_codes JSONB`, `status`, `created_at`, `reviewed_by NULL`, `reviewed_at NULL` | Scoped transaction FK; index `(organization_id,status,created_at DESC)`; no automatic enforcement |
| `documents` | `id`, tenant, `uploaded_by`, `name`, `document_type`, `source`, `storage_key`, `sha256`, `mime_type`, `size_bytes`, `access_level`, `status`, `uploaded_at`, `deleted_at NULL` | Index `(organization_id,status,uploaded_at DESC)` and scoped checksum lookup |
| `document_metadata` | `id`, tenant, `document_id`, `key`, `value JSONB`; unique `(document_id,key)` | Scoped document FK; index `(organization_id,key)` |
| `document_chunks` | `id`, tenant, `document_id`, `chunk_index`, `page_number NULL`, `text_hash`, `text_storage_key NULL`, `token_count`, `metadata JSONB`, `created_at`; unique `(document_id,chunk_index)` | Qdrant point ID maps to this row; index `(organization_id,document_id,page_number)` |
| `conversations` | `id`, tenant, `created_by`, `title NULL`, `status`, `created_at`, `updated_at` | Index `(organization_id,updated_at DESC)` |
| `chat_messages` | `id`, tenant, `conversation_id`, `role`, `content`, `created_at`, `model_version_id NULL`, `prediction_id NULL`, `metadata JSONB` | Scoped conversation FK; index `(organization_id,conversation_id,created_at)` |
| `message_citations` | `id`, tenant, `message_id`, `document_id`, `chunk_id`, `page_number NULL`, `quote_hash`, `created_at` | Scoped FKs; verifies cited source; index `(organization_id,message_id)` |
| `audit_logs` | `id`, tenant NULL for platform events, `actor_user_id NULL`, `action`, `resource_type`, `resource_id NULL`, `request_id`, `occurred_at`, `outcome`, `metadata JSONB`; append-only application policy | Index `(organization_id,occurred_at DESC)`, `(actor_user_id,occurred_at DESC)`, `(resource_type,resource_id)` |
| `scenarios` | `id`, tenant, `created_by`, `name`, `status`, `base_prediction_id NULL`, `assumptions JSONB`, `created_at`, `updated_at`, `simulated_at NULL` | Index `(organization_id,created_at DESC)`; actuals immutable |
| `scenario_results` | `id`, tenant, `scenario_id`, `baseline_prediction_id`, `simulated_prediction_id`, `comparison JSONB`, `created_at` | Scoped FKs; index `(organization_id,scenario_id)` |
| `notifications` | `id`, tenant, `user_id`, `type`, `severity`, `title`, `body`, `resource_type NULL`, `resource_id NULL`, `created_at`, `read_at NULL` | Scoped user FK; index `(organization_id,user_id,read_at,created_at DESC)` |

## Relationships
- Organization has many memberships, accounts, imports, transactions, forecasts, documents, conversations, scenarios, notifications, and audit records.
- User joins organizations through memberships; membership role grants permissions.
- Account has many transactions. Import batch has many imported transactions.
- Customer may relate to invoices and loans; customer PII is out of MVP scope unless specifically justified.
- Model version has many predictions and later risk assessments/alerts.
- Document has metadata and chunks; each chunk may be represented by a Qdrant point. A citation references an accessible document/chunk.
- Conversation has messages; messages may reference a prediction and citations.
- Scenario records assumptions and links baseline and simulated predictions; scenario results are distinct from source records.

## Data Integrity and Indexing
Use composite unique constraints and composite tenant-aware FKs where PostgreSQL supports the intended schema. Enforce currency codes, non-negative horizon, date ordering, allowed status enums/check constraints, and finite numeric values. JSONB is for versioned model/config payloads, not an excuse to hide stable query fields. Partitioning, time-series extensions, and read replicas are not MVP requirements; revisit after measured volume.

## Tenant-Isolation Verification
- Every query path includes authenticated organization scope.
- Cross-tenant foreign keys are rejected by constraints where feasible.
- RLS policies are tested with restricted DB roles if enabled.
- Integration tests attempt IDOR against transactions, documents, Qdrant points, exports, scenarios, and conversations.
- Background jobs and caches retain tenant scope; deletion spans PostgreSQL, object storage, Qdrant, cache, and backups per retention policy.

## Open Decisions
Identity provider and membership onboarding; retention/legal hold; whether to store extracted text in PostgreSQL or private object storage; encryption/key strategy; Qdrant collection and ACL design; exact CSV transaction/balance schema; and whether multi-currency conversion is supported or currencies remain separate.