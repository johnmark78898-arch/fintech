# Security Documentation

**Status:** Design baseline, not a compliance attestation. U.S. jurisdiction is assumed for planning; qualified counsel/security review is required before production.

## Security Objectives
Protect sensitive customer financial and document data; prevent cross-organization access; preserve provenance and integrity; constrain generated explanations; provide deletion and auditability; recover safely from failures. Do not claim certification or regulatory compliance from this design document.

## Identity and Authorization
- The implemented API accepts OIDC Bearer JWTs verified with configured JWKS, issuer, audience, required expiry/issued-at/subject claims, and the RS256 algorithm. The JWT subject must map to an active, pre-provisioned user. Configure `AUTH_ISSUER`, `AUTH_AUDIENCE`, and `AUTH_JWKS_URL`; no local password or registration flow is implemented.
- Select and operate a maintained identity provider; enforce MFA for privileged roles and secure token/session lifecycle. The JWKS URL must use HTTPS except for localhost development.
- Apply least-privilege organization roles (owner/admin/analyst/viewer) and permission checks on every API, job, export, citation, and document operation.
- Resolve tenant context from authenticated membership. Deny by default; do not rely on UI filtering or client-supplied tenant identifiers.
- Revalidate membership for long-running tasks and revoke access promptly.

## Data Protection
- TLS for network traffic; managed encryption at rest for database, backups, object storage, and volumes.
- Secrets through a production secret manager; local `.env` excluded from version control. Rotate credentials and avoid displaying them in logs.
- Minimize fields and retention; classify customer financial data and extracted document text as sensitive.
- Document provider retention and training policies before sending data to LLM/embedding services. Use redaction or private/self-hosted alternatives if required by the approved data policy.
- Define deletion across PostgreSQL, object storage, Qdrant, caches, exports, and backups; record completion status.

## Threats and Controls
| Threat | Controls and required tests |
|---|---|
| IDOR/cross-tenant access | Server-derived tenant scope, scoped queries/FKs, optional RLS, negative tests across all resource types |
| Malicious uploads/parser exploits | Allowlist formats, size/decompression limits, MIME/content checks, isolated parsers, malware scanning where available |
| CSV formula injection | Treat imported cells as data; neutralize formula-leading characters on spreadsheet exports |
| Prompt injection/document exfiltration | Retrieved text is untrusted; no privilege/tool authority; ACL-filtered retrieval; output/citation validation; red-team test corpus |
| Unauthorized tool execution | MVP has no financial execution tools; explicit allowlist and server-side authorization if future tools are added |
| Secret leakage | Secret manager, secret scanning, log redaction, dependency/config review |
| Abuse/resource exhaustion | Rate limits, upload caps, request timeouts, worker concurrency limits, quotas and alerts |
| Data leakage through logs/cache | Do not log raw rows or prompts by default; tenant-scoped cache keys; retention controls and access review |
| Supply-chain compromise | Lock dependencies, scan packages/images, signed/provenance-aware builds, patch process |

## Model and Financial Reliability
- Display timestamps, model version, horizon, input freshness, assumptions, uncertainty where validated, and limitations.
- Distinguish probability from certainty and prediction from observed fact.
- Require human review before consequential credit/fraud actions; no automatic transfers or adverse actions.
- Monitor data quality, model drift, false-alert burden, and provider failures; provide rollback/disable mechanisms.

## Audit and Incident Response
Audit authentication events, membership/permission changes, imports, exports, document access/deletion, predictions, scenario runs, and administrative actions with actor, organization, resource, time, outcome, and request ID. Avoid raw financial payloads in logs. Define incident triage, containment, customer notification, credential rotation, evidence preservation, recovery, and post-incident review before production.

## Privacy and Legal Review Gates
Determine applicability of federal/state privacy laws, financial-service obligations, consumer-reporting/fair-lending rules for later modules, breach notification, retention, data processor contracts, cross-border transfers, and customer deletion rights. Obtain qualified U.S. legal/compliance advice; this document is not legal advice or a compliance certification.
