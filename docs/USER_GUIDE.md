# User Guide

**Status:** A development-preview web interface is implemented. It supports browser-only CSV previews, enriched transaction analysis, an exploratory trend baseline and cash-flow page, public SBA/IRS search, and local Ollama answers. Authentication, persistent browser uploads, private document indexing, and validated business cash-flow forecasting are not implemented.

## Current Development Preview
- Start the demo with `docker compose -f docker-compose.app.yml up -d --build` and open `http://localhost:5173`.
- The overview uses the bundled, source-derived UCI Online Retail sample. It is sales and returns data—not bank activity, cash balances, or an SMB cash-flow benchmark.
- A selected CSV is parsed and displayed in the current browser session only. It is not uploaded or persisted. Common transaction column names are recognized automatically; signed amounts and separate debit/credit columns are supported.
- After upload, the Analysis page opens automatically. Date, account, category, direction, and currency columns are optional. Missing currency defaults to USD without conversion and is called out in the import note; verify this assumption. Missing categories use “Uncategorized,” direction is inferred from amount signs, and other numeric columns with mostly valid values are included in univariate summaries and Pearson correlations. A usable amount (or debit/credit values) is required; rows without one are skipped and counted.
- The protected API importer accepts common header aliases too. Persistent records still require a timezone-aware transaction date and currency; account names and directions can be inferred or defaulted.
- Analysis summarizes monthly net movement, weekday activity, transaction timing, categories, invoice/product counts, quantity, unit prices, country/region breakdowns, and amount distributions where possible. If dates are absent, it omits time-based charts but still shows transaction statistics and amount distributions. Amounts in different currencies are never combined. Missing optional attributes do not prevent CSV analysis. The bundled demo is an 8,000-row sample from across the UCI source period with additional return and invoice-time attributes; CustomerID is excluded. It remains sales/returns data, not cash flow.
- Statistical analysis reports count, mean, median, sample standard deviation and variance, minimum, quartiles, maximum, and adjusted sample skewness for transaction amount and other detected numeric columns. The Pearson correlation matrix uses pairwise complete observations and is descriptive; it does not establish causality or report significance tests. All calculations run in the browser.
- Business recommendations can be generated from the Analysis page with the configured local Ollama model (default `llama3.2`). The API receives aggregate currency totals, monthly category outflows and sales/return counts, and up to 10 ranked item labels with transaction counts, totals, and (when complete) quantity sums. An item label comes from the CSV product-code or description column and is sent to your configured local Ollama service; raw transaction rows and full descriptions remain in the browser. The model selects evidence IDs only. The application writes the explanations/actions and computes priority and evidence confidence from deterministic thresholds. Time-based signals require at least 80% dated rows and roughly six months of history. A slow-sales review also requires at least three observed months for the item, three sale entries, five comparable products, and a return share no greater than 40%. It asks users to validate listing history, availability, and return records before considering pricing or inventory changes; it does not recommend discounts without margin evidence. Category-outflow changes, return-rate increases, and unusually high monthly outflows are offered only when sufficient history and activity are present. These signals do not establish causes. Bank/merchant descriptions without quantity data are not treated as product sales counts. If the local model returns an unsupported response format, the app displays a notice and uses a deterministically ranked, grounded fallback. When named item summaries are available, at least one item-specific check is included. Suggestions are prompts for human review, not financial advice or guaranteed outcomes. Ollama must be running on the host with the configured model installed.
- Model lab requires at least 11 dated daily or monthly periods. It compares last-period, three-period average, and linear-trend methods using rolling multi-step validation, then evaluates the selected method on a separate final three-period test. A seasonal-naive baseline is added when there is enough history (15 daily or 20 monthly periods). MAE, RMSE, and symmetric percentage error are shown by forecast step, so later-step accuracy can be compared separately. Missing periods between the first and last dated records are not treated as zero activity unless you explicitly confirm they represent zero activity; also verify the CSV covers the full time range you intend to model. This browser-side demo is an exploratory baseline, not independent validation or a guarantee of future performance. Moving between Model lab and Cash flow preserves the run until the dataset changes.
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
