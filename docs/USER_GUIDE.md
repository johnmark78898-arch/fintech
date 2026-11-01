# User Guide

**Status:** A development-preview web interface is implemented. It supports browser-only CSV previews, enriched transaction analysis, an exploratory trend baseline and cash-flow page, public SBA/IRS search, and local Ollama answers. Authentication, persistent browser uploads, private document indexing, and validated business cash-flow forecasting are not implemented.

## Current Development Preview
- Start the demo with `docker compose -f docker-compose.app.yml up -d --build` and open `http://localhost:5173`.
- The overview uses the bundled, source-derived UCI Online Retail sample. It is sales and returns data—not bank activity, cash balances, or an SMB cash-flow benchmark.
- A selected CSV is parsed and displayed in the current browser session only. It is not uploaded or persisted. Common transaction column names are recognized automatically; signed amounts and separate debit/credit columns are supported.
- Date, account, category, direction, and currency columns are optional. Missing values are labeled or inferred with an import note. A usable amount (or debit/credit values) is required; rows without one are skipped and counted.
- The protected API importer accepts common header aliases too. Persistent records still require a timezone-aware transaction date and currency; account names and directions can be inferred or defaulted.
- Analysis summarizes monthly net movement, weekday activity, transaction timing, categories, invoice/product counts, quantity, unit prices, and country/region breakdowns when those columns exist. Amounts in different currencies are never combined. Missing optional attributes do not prevent CSV preview. The bundled demo is an 8,000-row sample from across the UCI source period with additional return and invoice-time attributes; CustomerID is excluded. It remains sales/returns data, not cash flow.
- Model lab compares last-period, three-period moving-average, and linear-trend models using sequential walk-forward predictions on the latest chronological holdout. It reports MAE, RMSE, and symmetric percentage error by candidate, shows actual-versus-predicted holdout results, and selects the lowest-MAE method for a three-period movement estimate. Moving between Model lab and Cash flow preserves the run until the dataset changes.
- Cash flow asks for a dated cash-movement CSV and does not display invoice sales as a cash-flow estimate. For local CSV data, an optional projected-balance view requires a user-entered verified starting balance and explicit confirmation that rows represent cash receipts/payments in one currency. Estimates and the user-entered balance are browser-local and not saved. Backtests are diagnostics, not independent validation or guaranteed forecasts.
- AI assistant has separate dataset-analysis and public-guidance modes. Dataset questions use aggregate totals, monthly summaries, and categories; only aggregate totals, dates, currency, and category summaries go to the local API/Ollama. Raw rows and descriptions remain in the browser. Public-guidance questions use retrieved SBA/IRS passages.
- Install Ollama on the host, run `ollama pull llama3.2`, and keep the service running before using AI assistant. Do not enter personal or confidential information.
- To index the selected public SBA/IRS sources, run `docker compose -f docker-compose.app.yml exec api python /app/scripts/ingest_public_rag.py`. This downloads agency page text to the local Docker volume; it does not send customer data.
- Open Documents to search passages. Results link to their source and section. This is lexical retrieval only, not a generated answer; verify official pages for current details.

## Intended Use
FinSight AI is planned as a decision-support tool for SMB finance teams. Forecasts are estimates based on uploaded data and stated assumptions, not guaranteed outcomes or professional financial advice. Users remain responsible for reviewing source data and making decisions.

## Planned Workflows
### Upload Financial Data
- Select the organization workspace and upload a supported CSV.
- Map columns to dates, account/currency, balance or signed cash movement, and optional category.
- Review row-level validation feedback and import totals before using the data.
- Confirm source period, currency, timezone, and freshness.

### Review a Cash-Flow Forecast
- Choose a supported horizon (7, 30, or 90 days) when data coverage permits.
- Inspect historical inputs, forecast points, model version, run time, assumptions, and limitations.
- Treat a liquidity warning as a prompt for human review, not certainty.

### Run a Scenario
- Enter a supported change, such as revenue reduction, expense increase, or delayed receipt.
- Review the assumptions and baseline forecast before simulation.
- Compare simulated and baseline values. Simulated values are labeled and do not alter historical actuals.

### Ask About Evidence
- Ask a question about an authorized uploaded document or a saved prediction.
- Review citations by document and page; open the source to verify context.
- If the system reports missing evidence, do not treat an uncited answer as an established fact.

### Manage Documents and Data
- Review indexing status, source metadata, and permissions.
- Re-index after correcting a document or metadata issue.
- Delete documents/data through the supported workflow and confirm deletion job completion.

## Limitations and Safety
- Incomplete, stale, miscategorized, or short history may make a forecast unavailable or unreliable.
- External economic trends do not replace organization-specific records.
- AI explanations may omit nuance; citations and model metadata should be checked.
- Do not upload data you are not authorized to share. Do not use the tool for automatic financial transactions or unsupervised consequential decisions.

## Support
Production support channels, retention terms, and escalation procedures must be defined before launch.
