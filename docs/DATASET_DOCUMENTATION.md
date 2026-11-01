# Dataset Documentation

**Status:** Candidate register and governance plan. A small UCI Online Retail sample has been transformed for importer/demo and exploratory browser-baseline testing only. It is not training or validation data for a production cash-flow model.

## MVP Data Source
Primary planned source is customer-owned SMB financial history uploaded as CSV. Use requires explicit customer authorization, documented purpose, access controls, retention/deletion rules, and validation of format, currency, timezone, coverage, and ownership. These records are not a public benchmark and must not be pooled across customers for training without an explicit lawful basis, contractual permission, and governance approval.

Required forecast inputs are to be agreed with pilot users. Candidate fields include dated cash balance or signed transactions, account/currency, transaction date, and optional categories/invoice schedules. Store import provenance and raw-to-normalized mapping. Avoid collecting customer/employee personal information unless strictly required.

## Public Candidate Register
| Source | Potential use | Known scope/limitations | License/access status |
|---|---|---|---|
| UCI Online Retail, https://archive.ics.uci.edu/dataset/352/online+retail | Real-data CSV ingestion and demo testing only | 541,909 UK retailer transaction lines from 2010-12-01 to 2011-12-09; sales/returns, not bank settlements, cash balances, operating expenses, or U.S. SMB data. Bundled sample is 8,000 reproducibly sampled rows spanning the source period and includes invoice, product, quantity, unit-price, country, return, and invoice-time attributes; CustomerID is excluded. See `data/README.md`. Not suitable for cash-flow model validation. | UCI states CC BY 4.0; retain attribution and re-check terms before use. DOI: 10.24432/C5BW33. |
| Federal Reserve Banks, 2024 Report on Payments, https://www.fedsmallbusiness.org/reports/survey/2024/2024-report-on-payments | Candidate public reference for a future, source-cited RAG corpus about small-business payment experiences | Survey report based on the 2023 Small Business Credit Survey; discusses payment delays, fees, and settlement challenges. It is not transaction history or a cash-flow forecast label. No report text has been copied or indexed. | Primary-source report is publicly readable; an open bulk-reuse license was not verified. Confirm reuse and attribution terms before ingesting or redistributing content. |
| Companies House API, https://developer.company-information.service.gov.uk/ | Candidate for later research on company filings and statement-level document retrieval | UK company register; accounts availability and financial detail vary. It is not bank activity and can include personal data. Not selected for model training. | Review product-specific terms, API limits, and personal-data obligations before collection or indexing. |
| PKDD'99 Financial Data Set guide, https://web.archive.org/web/20191019201655/https://sorry.vse.cz/~berka/challenge/pkdd1999/berka.htm | Rejected for forecasting | Describes historical transactions and post-transaction balances for private-person bank accounts, not SMEs. Its client data includes a birth-number identifier derived from date of birth. | No open license or reliable current primary CSV download verified; personal-data risk. Do not collect or use for training. |
| UCI Default of Credit Card Clients, https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients | Later educational baseline for credit-default classification only | UCI describes 30,000 Taiwanese credit-card clients, 23 features, and historical observations centered on 2005. It is not SMB cash-flow data and is not representative evidence for U.S. lending decisions. | UCI page states CC BY 4.0; retain attribution and re-check terms before use. Source accessed 2026-11-01. |
| FRED API, https://fred.stlouisfed.org/docs/api/fred/ | Optional macroeconomic context/features for later research | Economic time series, not entity-level SMB cash history or labels; series definitions, revisions, frequency, release dates, and vintage timing matter. Do not use future-revised values in historical backtests. | API documentation and terms must be reviewed per intended use and series; API key required for relevant endpoints. Source accessed 2026-11-01. |
| CFPB Consumer Credit Trends, https://www.consumerfinance.gov/data-research/consumer-credit-trends/ | Aggregate market context for later credit-market analysis | CFPB page describes aggregate trend data for consumer mortgages, cards, auto, and student loans, based on a nationally representative sample; not row-level SMB repayment data or a direct default-label training table. | Public page provides codebook and CSV, but reuse, transformation, attribution, and fitness must be reviewed before product use. Source accessed 2026-11-01. |

These candidates do not provide a suitable public dataset for validated SMB cash-flow forecasting. No dataset source or model result is fabricated. A separate legal/data review is required before any operational use.

## Synthetic Data
Synthetic records may support UI development, integration tests, and demonstrations. Label clearly in database and UI; make deterministic with a documented seed/schema; keep out of model validation and performance claims. Ensure synthetic scenarios cannot be confused with real customer data.

## Selection and Governance Checklist
For every proposed dataset, record source URL, owner, acquisition date, license/terms, geography, unit of analysis, collection period, variables, target definition, missingness, coverage, known bias, permitted use, retention, version/checksum, transformations, and responsible approver. Reassess terms at acquisition and before release. Do not include personal or sensitive data without explicit legal/security review.

## Evaluation Data Protocol
- Separate training, validation, and final test periods chronologically for time-dependent tasks.
- Retain organization grouping where repeated observations create leakage risk.
- Document inclusion/exclusion and missing-value decisions.
- Prevent test labels from influencing feature engineering, threshold selection, or model selection.
- Version immutable snapshots and transformations; restrict access and deletion according to policy.
- For customer data, evaluate within permitted customer boundaries unless a governed, authorized pooled evaluation is approved.
