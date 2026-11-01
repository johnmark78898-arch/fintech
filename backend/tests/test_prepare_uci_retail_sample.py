import csv
from datetime import datetime

from openpyxl import Workbook
import pytest

from scripts.prepare_uci_retail_sample import MAX_SAMPLE_ROWS, prepare_sample


def test_sample_is_reproducible_spans_source_and_keeps_non_customer_attributes(tmp_path) -> None:
    source = tmp_path / "source.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(
        ["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"]
    )
    for day in range(1, 21):
        worksheet.append(
            [
                f"{536000 + day}",
                f"SKU-{day}",
                f"Product {day}",
                day,
                datetime(2010, 12, day, 10),
                1.25,
                1000 + day,
                "United Kingdom",
            ]
        )
    workbook.save(source)
    workbook.close()

    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"
    assert prepare_sample(source, first_path, limit=8) == (8, 0)
    assert prepare_sample(source, second_path, limit=8) == (8, 0)
    assert first_path.read_bytes() == second_path.read_bytes()

    with first_path.open(encoding="utf-8", newline="") as sample_file:
        rows = list(csv.DictReader(sample_file))

    assert len(rows) == 8
    assert rows[0]["occurred_at"] < rows[-1]["occurred_at"]
    assert {"invoice_id", "product_code", "quantity", "unit_price", "country"} <= set(rows[0])
    assert {
        "line_total",
        "is_return",
        "invoice_month",
        "invoice_weekday",
        "invoice_hour",
    } <= set(rows[0])
    assert rows[0]["country"] == "United Kingdom"
    assert rows[0]["is_return"] == "false"
    assert rows[0]["invoice_month"] == "2010-12"
    assert rows[0]["invoice_weekday"] == datetime.fromisoformat(rows[0]["occurred_at"]).strftime("%A")
    assert rows[0]["invoice_hour"] == "10"
    assert "CustomerID" not in rows[0]
    with pytest.raises(ValueError):
        prepare_sample(source, tmp_path / "too_many.csv", limit=MAX_SAMPLE_ROWS + 1)
