# Demo Data Provenance

## UCI Online Retail Sample

`demo/uci_online_retail_sample.csv` is a small, transformed sample from the UCI Machine Learning Repository's **Online Retail** dataset. The source describes 541,909 transaction lines for a UK-based online retailer from 2010-12-01 through 2011-12-09.

- Source page: https://archive.ics.uci.edu/dataset/352/online+retail
- Dataset DOI: https://doi.org/10.24432/C5BW33
- Citation: Chen, D. (2015). *Online Retail* [Dataset]. UCI Machine Learning Repository.
- License stated by UCI: CC BY 4.0; attribution is required.
- Downloaded source workbook is kept under ignored `data/raw/` and is not committed.
- The bundled demo CSV contains 8,000 usable source-derived line items deterministically sampled with reservoir sampling across the full source workbook (rather than only the earliest rows).
- The sample preserves invoice number, stock/product code, quantity, unit price, country, line total, return flag, invoice month, local weekday, and local hour alongside the normalized transaction fields. CustomerID is deliberately excluded.
- The local web preview serves this same attributed file from `/api/v1/demo/uci-online-retail-sample.csv`.
- Install the workbook reader with `pip install -e ".[data]"`, then recreate the sample with `python scripts/prepare_uci_retail_sample.py data/raw/online-retail/Online Retail.xlsx`.

## Transformation and Limitations
The sample keeps up to 8,000 usable source line items. A fixed seed (`42`) makes reservoir sampling reproducible; selected rows are sorted chronologically before export. It maps `InvoiceDate` from the retailer's `Europe/London` local time to UTC; ambiguous/nonexistent local times are skipped. The amount is `abs(Quantity) * UnitPrice`, currency is GBP, and lines whose invoice number starts with `C` or whose quantity is negative are labeled `outflow`/`sales_return`; other lines are `inflow`/`sales`. The output preserves invoice ID, product code, signed quantity, unit price, country, line total, return flag, and calendar/time features derived from the source's local invoice date, but excludes CustomerID. The source invoice number plus source row is used as the external reference.

**This is sales transaction data, not bank activity, settlement dates, costs, operating expenses, or cash balances.** The mapped direction is a sales/return proxy and must not be presented as cash-flow ground truth or used to claim cash-flow model accuracy. It is for validating CSV ingestion and demo UI behavior only.

## Public RAG Sources
`rag_sources.json` records the selected official SBA finance-guidance page and IRS Publication 334 source/version metadata. The local index is built with `scripts/ingest_public_rag.py` and stored in the Docker app volume, not in the repository. It includes only main-page text, records source URLs and content hashes, and does not fetch linked pages. Reuse relies on 17 U.S.C. §§ 101 and 105 only for qualifying agency-authored U.S. Government work; exclude third-party text, logos, and images. See `docs/RAG_DOCUMENTATION.md` for limits.
