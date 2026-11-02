from decimal import Decimal
from pathlib import Path

import pytest
from app.financial_data.csv_import import CsvFormatError, parse_transactions_csv


def test_parse_valid_transaction_normalizes_values_and_hashes_source() -> None:
    content = (
        b"occurred_at,account_name,amount,currency,direction,description,category\n"
        b"2026-10-31T12:30:00-04:00,Operating,125.5,usd,inflow,Client payment,Revenue\n"
    )

    result = parse_transactions_csv(content)

    assert result.total_rows == 1
    assert result.rejected_rows == 0
    assert len(result.records) == 1
    transaction = result.records[0]
    assert transaction.occurred_at.isoformat() == "2026-10-31T16:30:00+00:00"
    assert transaction.amount == Decimal("125.5000")
    assert transaction.currency == "USD"
    assert transaction.direction == "inflow"
    assert len(transaction.source_hash) == 64


def test_accepts_common_alternative_headers_and_signed_amounts() -> None:
    content = (
        b"when,Account,Net Amount,Currency Code,Details\n"
        b"2026-10-31T12:30:00Z,Operating,-12.50,EUR,Coffee shop\n"
        b"2026-10-31T13:30:00Z,Operating,25.00,EUR,Client payment\n"
    )

    result = parse_transactions_csv(content)

    assert result.total_rows == 2
    assert result.rejected_rows == 0
    assert [(record.amount, record.direction) for record in result.records] == [
        (Decimal("12.5000"), "outflow"),
        (Decimal("25.0000"), "inflow"),
    ]
    assert result.records[0].description == "Coffee shop"


def test_distinguishes_value_date_from_transaction_amount() -> None:
    content = (
        b"Value Date,Account,Amount,Currency\n"
        b"2026-10-31T12:30:00Z,Operating,125.50,USD\n"
    )

    result = parse_transactions_csv(content)

    assert result.rejected_rows == 0
    assert result.records[0].amount == Decimal("125.5000")
    assert result.records[0].occurred_at.isoformat() == "2026-10-31T12:30:00+00:00"


def test_accepts_separate_debit_and_credit_columns_without_direction() -> None:
    content = (
        b"Booked Date,Details,Money Out,Money In,CCY\n"
        b"2026-10-31T12:30:00Z,Coffee shop,12.50,,EUR\n"
        b"2026-10-31T13:30:00Z,Client payment,,500.00,EUR\n"
    )

    result = parse_transactions_csv(content)

    assert result.total_rows == 2
    assert result.rejected_rows == 0
    assert [(record.amount, record.direction) for record in result.records] == [
        (Decimal("12.5000"), "outflow"),
        (Decimal("500.0000"), "inflow"),
    ]
    assert {record.account_name for record in result.records} == {"Imported account"}


def test_rejects_row_without_timezone() -> None:
    content = (
        b"occurred_at,account_name,amount,currency,direction\n"
        b"2026-10-31,Operating,125.50,USD,inflow\n"
    )

    result = parse_transactions_csv(content)

    assert result.total_rows == 1
    assert result.rejected_rows == 1
    assert result.row_errors[0].code == "invalid_occurred_at"
    assert result.records == ()


def test_rejects_duplicate_headers() -> None:
    content = b"occurred_at,account_name,amount,currency,direction,amount\n"

    with pytest.raises(CsvFormatError, match="duplicate column"):
        parse_transactions_csv(content)


def test_rejects_amount_with_excess_scale() -> None:
    content = (
        b"occurred_at,account_name,amount,currency,direction\n"
        b"2026-10-31T00:00:00Z,Operating,1.00001,USD,inflow\n"
    )

    result = parse_transactions_csv(content)

    assert result.rejected_rows == 1
    assert result.row_errors[0].code == "amount_precision_out_of_range"


def test_reports_extra_csv_cells_as_row_error() -> None:
    content = (
        b"occurred_at,account_name,amount,currency,direction\n"
        b"2026-10-31T00:00:00Z,Operating,125.50,USD,inflow,unexpected\n"
    )

    result = parse_transactions_csv(content)

    assert result.total_rows == 1
    assert result.rejected_rows == 1
    assert result.row_errors[0].code == "column_count_mismatch"


def test_imports_bundled_uci_online_retail_sample() -> None:
    project_root = Path(__file__).resolve().parents[2]
    sample_path = project_root / "data" / "demo" / "uci_online_retail_sample.csv"

    result = parse_transactions_csv(sample_path.read_bytes())

    assert result.total_rows == 8_000
    assert len(result.records) == 8_000
    assert result.rejected_rows == 0
    assert {record.currency for record in result.records} == {"GBP"}
    assert {record.direction for record in result.records} <= {"inflow", "outflow"}
