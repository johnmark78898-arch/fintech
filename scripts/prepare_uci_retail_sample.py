import argparse
import csv
import random
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl import load_workbook

MAX_SAMPLE_ROWS = 8_000
SOURCE_TIMEZONE = ZoneInfo("Europe/London")
FIELDNAMES = (
    "occurred_at",
    "account_name",
    "amount",
    "currency",
    "direction",
    "description",
    "category",
    "external_ref",
    "invoice_id",
    "product_code",
    "quantity",
    "unit_price",
    "country",
    "line_total",
    "is_return",
    "invoice_month",
    "invoice_weekday",
    "invoice_hour",
)


def _to_utc(value: datetime) -> datetime | None:
    if value.tzinfo is not None:
        return value.astimezone(UTC)

    first_fold = value.replace(tzinfo=SOURCE_TIMEZONE, fold=0)
    second_fold = value.replace(tzinfo=SOURCE_TIMEZONE, fold=1)
    if first_fold.utcoffset() != second_fold.utcoffset():
        return None
    if first_fold.astimezone(UTC).astimezone(SOURCE_TIMEZONE).replace(tzinfo=None) != value:
        return None
    return first_fold.astimezone(UTC)


def prepare_sample(source: Path, destination: Path, limit: int) -> tuple[int, int]:
    if not 1 <= limit <= MAX_SAMPLE_ROWS:
        raise ValueError(f"limit must be between 1 and {MAX_SAMPLE_ROWS}")

    workbook = load_workbook(source, read_only=True, data_only=True)
    worksheet = workbook.active
    rows = worksheet.iter_rows(values_only=True)
    headers = next(rows, None)
    if headers is None:
        raise ValueError("source workbook has no header row")
    header_indexes = {str(value).strip(): index for index, value in enumerate(headers) if value}
    required = {"InvoiceNo", "Description", "Quantity", "InvoiceDate", "UnitPrice"}
    if not required.issubset(header_indexes):
        raise ValueError("source workbook does not match the documented UCI columns")

    destination.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    skipped = 0
    sampled: list[dict[str, str]] = []
    rng = random.Random(42)
    try:
        for source_row, values in enumerate(rows, start=2):
            row = {name: values[index] for name, index in header_indexes.items()}
            try:
                invoice_number = str(row["InvoiceNo"]).strip()
                quantity = Decimal(str(row["Quantity"]))
                unit_price = Decimal(str(row["UnitPrice"]))
                invoice_date = row["InvoiceDate"]
            except (InvalidOperation, TypeError, KeyError):
                skipped += 1
                continue

            if not invoice_number or not isinstance(invoice_date, datetime):
                skipped += 1
                continue
            if not quantity.is_finite() or not unit_price.is_finite() or unit_price <= 0 or quantity == 0:
                skipped += 1
                continue

            occurred_at = _to_utc(invoice_date)
            if occurred_at is None:
                skipped += 1
                continue

            is_return = invoice_number.upper().startswith("C") or quantity < 0
            amount = (abs(quantity) * unit_price).quantize(Decimal("0.0001"))
            description = str(row["Description"] or "").strip()[:500]
            record = {
                "occurred_at": occurred_at.isoformat(),
                "account_name": "UCI Online Retail sales proxy",
                "amount": format(amount, "f"),
                "currency": "GBP",
                "direction": "outflow" if is_return else "inflow",
                "description": description,
                "category": "sales_return" if is_return else "sales",
                "external_ref": f"{invoice_number}:{source_row}",
                "invoice_id": invoice_number,
                "product_code": str(row.get("StockCode") or "").strip()[:40],
                "quantity": format(quantity, "f"),
                "unit_price": format(unit_price, "f"),
                "country": str(row.get("Country") or "").strip()[:80],
                "line_total": format(amount, "f"),
                "is_return": str(is_return).lower(),
                "invoice_month": invoice_date.strftime("%Y-%m"),
                "invoice_weekday": invoice_date.strftime("%A"),
                "invoice_hour": str(invoice_date.hour),
            }
            written += 1
            if len(sampled) < limit:
                sampled.append(record)
            else:
                replacement = rng.randrange(written)
                if replacement < limit:
                    sampled[replacement] = record

        sampled.sort(key=lambda record: (record["occurred_at"], record["external_ref"]))
        with destination.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=FIELDNAMES, lineterminator="\n")
            writer.writeheader()
            writer.writerows(sampled)
    finally:
        workbook.close()

    if not sampled:
        raise ValueError("no usable rows were found in the selected sample")
    return len(sampled), skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an enriched sample from UCI Online Retail")
    parser.add_argument("source", type=Path, help="Path to the downloaded UCI Online Retail.xlsx")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/demo/uci_online_retail_sample.csv"),
    )
    parser.add_argument("--limit", type=int, default=MAX_SAMPLE_ROWS)
    args = parser.parse_args()

    written, skipped = prepare_sample(args.source, args.output, args.limit)
    print(f"Wrote {written} source-derived rows to {args.output}; skipped {skipped} rows.")


if __name__ == "__main__":
    main()
