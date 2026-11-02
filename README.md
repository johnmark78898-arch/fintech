# FinSight AI

Predictive financial intelligence and risk-management platform concept for small and medium-sized businesses. The initial proposed product slice is customer-owned CSV ingestion, cash-flow forecasts, liquidity warnings, what-if scenarios, and (subject to approval) cited explanations from financial documents.

> **Early implementation:** An OIDC-protected CSV import API, tenant-scoped persistence, an initial Alembic migration, an attributed real-data sample, a development-preview web interface, exploratory transaction analysis, and lexical retrieval over selected public SBA/IRS text are present. CSV analysis in the web interface runs in the browser; the interface is not yet a complete authenticated finance product. Identity-provider provisioning, private document ingestion, validated business cash-flow forecasting, and production deployment are not implemented. The local Ollama integration can answer dataset questions using aggregates and public-guidance questions using retrieved references. No prediction accuracy or compliance claim is made.

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

## Analysis Available Now
The web interface includes exploratory and descriptive analysis:
- **Univariate statistics:** count, mean, median, sample standard deviation and variance, minimum, quartiles, maximum, and adjusted sample skewness for transaction amount and other recognized numeric columns.
- **Multivariate statistics:** a Pearson correlation matrix across numeric variables, calculated from pairwise complete observations. Select a currency to avoid mixing amounts with different units. When CSV currency is omitted, USD is assumed and noted; this is not a conversion.
- **Grouped/time summaries:** breakdowns by available categories, products, countries/regions, and invoice attributes, plus monthly movement, weekday activity, and transaction timing. Missing columns are skipped, and totals in different currencies are kept separate.
- **Business recommendations:** on the Analysis page, generate up to four cautious, plain-language review suggestions with the configured local Ollama model (default `llama3.2`). It receives aggregate currency, monthly, and category summaries plus up to 10 ranked item labels and their totals/counts/quantities—not raw transaction rows or full descriptions. Llama selects relevant evidence; the app builds each observation, explanation, and practical next step from those verified facts. For product data with quantities, it compares positive units sold within each currency; with at least five comparable products, it may suggest a small, time-limited discount or bundle test when an item's units sold are no more than half the product median, after checking margin, stock, returns, and the sales period. This is a review idea, not an instruction to discount. If Llama returns an unsupported format, the app displays a notice and uses grounded review suggestions instead. A named-item check is included whenever item summaries are available.
- **Trend baseline comparison:** Model lab compares last-period, three-period-average, and linear-trend estimates for one net-movement time series using a chronological holdout. This is an exploratory baseline, not a trained or validated forecasting model.

These statistics are computed locally in the browser. Correlation describes linear association, not causation; significance tests and multivariate regression/classification are not currently provided.

## Run the Demo
Prerequisite: Docker Desktop with Docker Compose installed and running. These commands start the API and web interface without installing Python or Node.js on the host:

```powershell
docker compose -f docker-compose.app.yml up -d --build
```

1. Open `http://localhost:5173` after the containers start. The dashboard loads the bundled UCI Online Retail sample through the API.
2. The **Analysis** page opens after a CSV is selected. Files are previewed locally and are not uploaded or persisted. Common transaction headers, signed amounts, and separate debit/credit columns are supported. If currency is missing, USD is assumed (no conversion); missing categories use “Uncategorized,” direction is inferred from amount signs, and other numeric columns are included in statistical analysis when detected. Without dates, descriptive statistics and amount distributions still appear, while time-based charts are omitted. Rows without usable amounts are skipped. Verify defaults and inferred columns against your file.
3. API documentation is at `http://localhost:8000/docs`.
4. Optional Llama features (Analysis recommendations and AI assistant): install Ollama on the host, run `ollama pull llama3.2`, and leave Ollama running. To enable public SBA/IRS document search, build the local reference index:

```powershell
docker compose -f docker-compose.app.yml exec api python /app/scripts/ingest_public_rag.py
```

Stop the demo stack when finished:

```powershell
docker compose -f docker-compose.app.yml down
```

This keeps the local SQLite database and source-index volume. To remove the persisted demo data too, use `docker compose -f docker-compose.app.yml down --volumes`.

## Host-Based Development
Prerequisites: Python 3.12 and Node.js 22 or later. From the repository root, create and activate a virtual environment, install the project and test dependencies, and configure a local SQLite database:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
$env:DATABASE_URL = "sqlite:///./finsight.db"
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --app-dir backend
```

In a second PowerShell terminal, start the frontend:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. The browser CSV workflow is preview-only. The protected API persistence endpoint additionally requires `AUTH_ISSUER`, `AUTH_AUDIENCE`, and `AUTH_JWKS_URL`, plus an active user and organization membership for the JWT subject. See `.env.example` for local configuration. Optional PostgreSQL, Qdrant, and Redis services for backend development can be started with:

```powershell
# Copy .env.example to .env and set a local-only POSTGRES_PASSWORD first.
docker compose up -d postgres qdrant redis
```

## Environment Configuration
See `.env.example`. Production secrets belong in a managed secret store. External LLM, embedding, financial-data, and identity-provider settings remain undecided and must not be added as real credentials to this repository.

## Models and Data
No model is trained. The local RAG source index contains only selected SBA/IRS public page text after the ingestion script runs; there are no customer documents, embeddings, or generated answers. A small sample from the UCI Online Retail dataset is bundled at `data/demo/uci_online_retail_sample.csv` for CSV ingestion/demo testing; it represents sales and returns, not actual cash movement, and must not be used to claim cash-flow performance. Source, license, and transformation are recorded in `data/README.md`. Customer-owned financial records remain the intended MVP source for cash-flow analysis, subject to consent and documented retention. Public candidates and limitations are listed in `docs/DATASET_DOCUMENTATION.md`.

## Tests
The test strategy is in `docs/TESTING_STRATEGY.md`. After installing the test extra with `python -m pip install -e ".[test]"`, run `python -m pytest`. Tests cover parser edge cases and the bundled real-data sample. No model evaluation result is claimed.

## Safety and Limitations
FinSight is planned as decision support, not guaranteed financial advice. It will not automatically transfer funds or make consequential credit/fraud decisions. Human review, source inspection, data freshness, and model limitations matter.
