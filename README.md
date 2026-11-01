# FinSight AI

Predictive financial intelligence and risk-management platform concept for small and medium-sized businesses. The initial proposed product slice is customer-owned CSV ingestion, cash-flow forecasts, liquidity warnings, what-if scenarios, and (subject to approval) cited explanations from financial documents.

> **Early implementation:** Planning documents, an OIDC-protected CSV import API, tenant-scoped persistence, an initial Alembic migration, an attributed real-data sample, a development-preview web interface, and lexical retrieval over selected public SBA/IRS text are present. The interface currently previews CSV files in the browser; it is not yet a complete authenticated finance product. Identity-provider provisioning, private document ingestion, LLM answers, trained forecasting models, and production deployment are not implemented. No prediction accuracy or compliance claim is made.

## Planned Capabilities
- Cash-flow forecasting for supported 7-, 30-, and 90-day horizons.
- Liquidity indicators and timestamped/versioned model outputs.
- What-if simulations kept separate from historical actuals.
- Permission-filtered document retrieval and evidence-cited explanations.
- Later gated modules for credit default, fraud, and financial distress.

## Architecture Overview
Proposed modular monolith: React/TypeScript frontend; FastAPI/Pydantic backend; SQLAlchemy and PostgreSQL for structured tenant-scoped records; Qdrant for document vectors; optional Redis for background work; configurable ML, embedding, and LLM adapters. The ML model is the source of numeric predictions, RAG retrieves authorized evidence, and the LLM explains these inputs without inventing outputs. See `docs/SYSTEM_ARCHITECTURE.md`.

## Technology Stack
Python, FastAPI, Pydantic, SQLAlchemy, PostgreSQL, pandas, NumPy, scikit-learn, MLflow, Qdrant, PyMuPDF, configurable LLM/embedding provider, React, TypeScript, Docker Compose. Candidate algorithms and optional dependencies are selected only after measured evaluation.

## Documentation
- `docs/PROJECT_PLAN.md`
- `docs/SYSTEM_ARCHITECTURE.md`
- `docs/DATABASE_DESIGN.md`
- `docs/API_DOCUMENTATION.md`
- `docs/ML_DOCUMENTATION.md`
- `docs/RAG_DOCUMENTATION.md`
- `docs/DATASET_DOCUMENTATION.md`
- `docs/SECURITY_DOCUMENTATION.md`
- `docs/TESTING_STRATEGY.md`
- `docs/DEPLOYMENT_GUIDE.md`
- `docs/USER_GUIDE.md`
- `docs/DEVELOPMENT_ROADMAP.md`

## Local Setup
Prerequisites: Docker Desktop with Compose. For the demo stack, start the API and web interface without installing Python or Node.js on the host:

```powershell
docker compose -f docker-compose.app.yml up -d --build
```

Open `http://localhost:5173`. The dashboard loads the attributed UCI sample through the API. The web interface can preview CSVs locally and recognizes common transaction headers, signed amounts, and separate debit/credit columns. In browser preview, date, account, and currency are optional; missing or inferred values are labeled. Rows without a usable amount are skipped, and the preview is not persisted or sent to the server. The protected API importer also accepts common header aliases, but persistent records still require a timezone-aware date and currency. The assistant uses local Ollama; install Ollama on the host, run `ollama pull llama3.2`, and leave its local service running before asking questions. Build the public reference index with `docker compose -f docker-compose.app.yml exec api python /app/scripts/ingest_public_rag.py`; then search it under Documents or ask a question in AI assistant. API docs remain available at `http://localhost:8000/docs`. Stop the demo stack with `docker compose -f docker-compose.app.yml down`; this keeps its local SQLite and source-index volume.

```powershell
# Optional PostgreSQL, Qdrant, and Redis services for backend development.
# Copy .env.example to .env and set a local-only POSTGRES_PASSWORD first.
docker compose up -d postgres qdrant redis
```

For host-based development, install Python 3.12+ and Node.js LTS, then run `uvicorn app.main:app --reload --app-dir backend` from the repository root and `npm install; npm run dev` from `frontend`. The protected CSV persistence endpoint requires `DATABASE_URL`, `AUTH_ISSUER`, `AUTH_AUDIENCE`, and `AUTH_JWKS_URL`; provision the JWT subject as an active user and create an organization membership before calling it. Apply the schema with `alembic upgrade head`. The web UI does not yet include sign-in or organization provisioning, and its CSV flow is deliberately preview-only.

## Environment Configuration
See `.env.example`. Production secrets belong in a managed secret store. External LLM, embedding, financial-data, and identity-provider settings remain undecided and must not be added as real credentials to this repository.

## Models and Data
No model is trained. The local RAG source index contains only selected SBA/IRS public page text after the ingestion script runs; there are no customer documents, embeddings, or generated answers. A small sample from the UCI Online Retail dataset is bundled at `data/demo/uci_online_retail_sample.csv` for CSV ingestion/demo testing; it represents sales and returns, not actual cash movement, and must not be used to claim cash-flow performance. Source, license, and transformation are recorded in `data/README.md`. Customer-owned financial records remain the intended MVP source for cash-flow analysis, subject to consent and documented retention. Public candidates and limitations are listed in `docs/DATASET_DOCUMENTATION.md`.

## Tests
The test strategy is in `docs/TESTING_STRATEGY.md`. After installing the test extra, run `python -m pytest`. Tests cover parser edge cases and the bundled real-data sample. No model evaluation result is claimed.

## Safety and Limitations
FinSight is planned as decision support, not guaranteed financial advice. It will not automatically transfer funds or make consequential credit/fraud decisions. Human review, source inspection, data freshness, and model limitations matter.
