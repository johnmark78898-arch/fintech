# Machine Learning Documentation

**Status:** Design only. No model is trained, selected, or evaluated; no performance results are available.

## Scope and Governance
Initial ML scope is cash-flow forecasting for customer-provided SMB financial histories. Numeric outputs come only from an evaluated/versioned model or a clearly identified deterministic baseline. Do not silently substitute synthetic predictions in production. Credit default, fraud, and financial-distress modules are deferred.

## Pipeline
1. Ingest permitted, organization-owned data and retain source/import identifiers.
2. Validate schema, dates, currency, duplicates, coverage, missingness, and outliers.
3. Normalize sign conventions, account mapping, timezone, and fiscal calendar without losing source values.
4. Perform EDA by organization only where permitted; aggregate reporting must prevent leakage.
5. Create versioned features using only information available at forecast time.
6. Establish naive/seasonal and deterministic cash-balance baselines.
7. Compare appropriate candidates using rolling-origin chronological validation.
8. Select only on pre-registered acceptance criteria and an untouched final period.
9. Save artifact, code/dependency versions, training data reference, feature schema, metrics, and limitations.
10. Serve predictions with model version, timestamp, input range, assumptions, and monitoring hooks.

## Cash-Flow Forecasting
**Target:** Future daily/weekly cash balance and, where categorization is reliable, cash inflows/outflows. Horizon: 7, 30, and 90 days only when history/coverage supports each horizon.

**Candidate features:** lagged balances and inflows/outflows, calendar and day-of-week/seasonal indicators, recurring payment features, invoice due/paid information if supplied, account aggregation, missingness/freshness indicators, and optional external macro series only after licensing and point-in-time availability review. Exclude post-cutoff values and scenario outcomes from training labels.

**Baselines:** last-value/random-walk, seasonal naive, and transparent rolling-average or cash schedule baseline. Candidate ML methods: regularized regression/gradient boosting for tabular lag features and established time-series models when sample size and evaluation justify them. Do not assume XGBoost, LightGBM, LSTM, or any other method wins without comparison.

**Evaluation:** rolling-origin backtesting with chronological splits; organization/time separation as appropriate; report MAE and RMSE per horizon and segment; assess prediction intervals if used; MAPE only when targets are nonzero and interpretation is valid. For liquidity events, define threshold with user and evaluate precision, recall, lead time, false-alert burden, and calibration only with independently labeled events. Report coverage and confidence limitations.

## Later Modules (Not MVP)
- **Credit default:** Requires permitted, representative, appropriately labeled repayment data, outcome horizon, target definition, feature provenance, and U.S. fair-lending/privacy review. Candidate logistic regression and tree ensembles; evaluate ROC-AUC, PR-AUC, precision/recall, calibration, subgroup performance, stability, and explainability. Never automatically adjudicate.
- **Fraud:** Requires confirmed fraud labels and delayed-label handling; compare anomaly baselines with supervised methods if labels are sufficient. Evaluate PR-AUC, precision/recall at operational review capacity, false-positive burden, detection delay, and drift. Human investigation required.
- **Financial distress:** Define target/outcome and look-ahead window; avoid leakage from post-distress statements. Evaluate chronological ROC-AUC/PR-AUC, precision/recall, calibration, segment stability, and warning lead time.

## Data, Leakage, and Imbalance
- Train/validation/test partitions are time ordered; never randomly split future-dependent observations.
- Fit imputers, scalers, encoders, and feature selection on training windows only.
- Use point-in-time joins and document source publication timestamps.
- Keep multiple accounts/organizations grouped where leakage is possible.
- Treat synthetic data only as a software/demo aid; it cannot establish external validity.
- Use class weighting or resampling only inside training folds; preserve natural prevalence in test evaluation.
- Document missing-not-at-random, selection bias, business failures, and reporting delays.

## Explainability and Monitoring
For initial forecasting, report interpretable drivers such as observed recurring flows and recent trend, with attribution method and limitations. SHAP may be evaluated for eligible tree models but is not a guarantee of causal explanation. Monitor input schema/freshness, feature drift, residuals when actuals arrive, horizon-specific error, alert rates, provider/model failures, and model version distribution. Retraining requires review and revalidation.

## Model Registry and API
Every version records model key, semantic/version identifier, artifact checksum/URI, code commit, feature schema version, training data snapshot, evaluation window, metrics, known limitations, approval status, and created timestamp. The prediction endpoint returns generated time, model version, input window, horizon, values/intervals if validated, assumptions, and limitations.

## Dataset Candidates and Results
Dataset provenance, licensing, and limitations are tracked in `DATASET_DOCUMENTATION.md`. No third-party dataset has been selected for the SMB forecast model; customer data is the intended MVP source. No experiments or model results have yet been produced.
