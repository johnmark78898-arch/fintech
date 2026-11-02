# Deployment Guide

**Status:** Proposed workflow. Local container definitions are development-only; production deployment has not been tested or approved.

## Prerequisites
- Docker Engine/Desktop with Compose plugin.
- Python version declared in `pyproject.toml` and Node.js version declared by frontend when created.
- Local environment file copied from `.env.example`; provide secrets only in local ignored files or production secret manager.

## Local Development
1. For the isolated local demo, run `docker compose -f docker-compose.app.yml up -d --build`. It starts the API with SQLite and the web preview; no `.env` or provider credentials are needed.
2. Open `http://localhost:5173` for the application and `http://localhost:8000/docs` for the API schema.
3. Optionally index the selected public reference pages with `docker compose -f docker-compose.app.yml exec api python /app/scripts/ingest_public_rag.py`. Source text and provenance are stored in the local named volume.
4. Stop the demo with `docker compose -f docker-compose.app.yml down`. The named SQLite/RAG data volume is preserved.
5. For full backend development, copy `.env.example` to `.env`, set local-only database and OIDC values, install `python -m pip install -e ".[test]"`, apply `alembic upgrade head`, and start the API with `uvicorn app.main:app --reload --app-dir backend`.
6. Host-based frontend development uses Node.js LTS: run `npm install` and `npm run dev` from `frontend`.
7. Protected CSV persistence requires an OIDC user and organization membership provisioned in the database. The web preview currently does not implement sign-in or persistent uploads.

The CSV upload flow and initial migration are implemented and tested with SQLite; PostgreSQL migration behavior and production topology are not yet validated end to end. The isolated demo Compose stack is intended only for local UI preview, not production.

## Environment Variables
See `.env.example`. Required production values must come from a secrets manager. Never commit `.env`, provider credentials, signing keys, or production connection strings.

## Production Design Checklist
- Private network for PostgreSQL, Qdrant, Redis, and object storage; no direct public database/vector ports.
- TLS ingress, WAF/rate limits as appropriate, secure identity provider and MFA for admins.
- Managed encrypted database/object storage, backups, tested restoration, retention and deletion procedures.
- Separate worker/API credentials and least privilege; secrets rotation and audit.
- Pin reviewed container/dependency versions and scan images; apply security updates.
- Run migrations as controlled release steps; include rollback/forward-fix plan.
- Health/readiness probes, structured redacted logs, metrics, traces, alerting, queue visibility, provider outage handling.
- Define SLOs, RPO/RTO, data residency, incident response, and capacity limits before launch.
- Verify tenant isolation and deletion in the deployed topology; no compliance claim without independent evidence.

## Rollback and Recovery
Keep prior application/model versions and reversible migrations where feasible. Disable a faulty model/provider independently from the API; serve an explicit unavailable state rather than stale/unvalidated predictions. Test restoration from encrypted backup and ensure restored data respects deletion/retention obligations.
