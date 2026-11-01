import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_ROWS = 100_000
MAX_REPORTED_ERRORS = 1_000
OPTIONAL_HEADERS = frozenset({"description", "category", "external_ref"})
_CURRENCY_PATTERN = re.compile(r"[A-Z]{3}\Z")
_HEADER_ALIASES = {
    "occurred_at": ("occurred_at", "date", "transaction date", "posting date", "booked date", "booking date", "value date", "timestamp"),
    "account_name": ("account_name", "account", "account name", "account number", "account id"),
    "amount": ("amount", "transaction amount", "value", "net amount", "net", "total", "transaction value"),
    "currency": ("currency", "currency code", "ccy"),
    "direction": ("direction", "transaction type", "type", "dr/cr"),
    "debit": ("debit", "debit amount", "total debit", "withdrawal", "withdrawals", "money out", "paid out"),
    "credit": ("credit", "credit amount", "total credit", "deposit", "deposits", "money in", "paid in"),
    "description": ("description", "transaction description", "details", "merchant", "payee", "narrative", "memo"),
    "category": ("category", "transaction category"),
    "external_ref": ("external_ref", "transaction id", "reference", "external ref"),
}


class CsvFormatError(ValueError):
    """The uploaded CSV cannot be interpreted using the supported schema."""


@dataclass(frozen=True, slots=True)
class ParsedTransaction:
    occurred_at: datetime
    account_name: str
    amount: Decimal
    currency: str
    direction: str
    description: str
    category: str | None
    external_ref: str | None
    source_hash: str


@dataclass(frozen=True, slots=True)
class RowError:
    row_number: int
    code: str


@dataclass(frozen=True, slots=True)
class CsvImportResult:
    records: tuple[ParsedTransaction, ...]
    row_errors: tuple[RowError, ...]
    total_rows: int
    rejected_rows: int


def parse_transactions_csv(content: bytes) -> CsvImportResult:
    if not content:
        raise CsvFormatError("The uploaded file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise CsvFormatError("The uploaded file exceeds the size limit")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CsvFormatError("The CSV must use UTF-8 encoding") from error

    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if reader.fieldnames is None:
            raise CsvFormatError("The CSV is missing a header row")

        headers = [header.strip().casefold() if header is not None else "" for header in reader.fieldnames]
        if any(not header for header in headers):
            raise CsvFormatError("The CSV contains an empty column name")
        if len(set(headers)) != len(headers):
            raise CsvFormatError("The CSV contains duplicate column names")

        reader.fieldnames = headers
        raw_rows = list(reader)
        columns = _resolve_columns(headers, raw_rows)

        records: list[ParsedTransaction] = []
        errors: list[RowError] = []
        total_rows = 0
        rejected_rows = 0

        for row_number, raw_row in enumerate(raw_rows, start=2):
            if None not in raw_row and all(
                not (value or "").strip() for value in raw_row.values() if isinstance(value, str) or value is None
            ):
                continue
            row = _canonicalize_row(raw_row, columns)
            if row is None:
                continue
            if None not in row and all(not (value or "").strip() for value in row.values()):
                continue
            total_rows += 1
            if total_rows > MAX_ROWS:
                raise CsvFormatError("The CSV contains more rows than the supported limit")

            error_code = _row_error_code(row)
            if error_code is not None:
                rejected_rows += 1
                if len(errors) < MAX_REPORTED_ERRORS:
                    errors.append(RowError(row_number=row_number, code=error_code))
                continue

            records.append(_parse_row(row))

    except csv.Error as error:
        raise CsvFormatError("The CSV could not be parsed") from error

    return CsvImportResult(
        records=tuple(records),
        row_errors=tuple(errors),
        total_rows=total_rows,
        rejected_rows=rejected_rows,
    )


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _find_column(headers: list[str], aliases: tuple[str, ...]) -> str | None:
    normalized_aliases = tuple(_normalize_header(alias) for alias in aliases)
    for header in headers:
        if _normalize_header(header) in normalized_aliases:
            return header
    for header in headers:
        normalized_header = _normalize_header(header)
        if any(len(alias) > 5 and alias in normalized_header for alias in normalized_aliases):
            return header
    return None


def _resolve_columns(
    headers: list[str], rows: list[dict[str | None, str | list[str] | None]]
) -> dict[str, str | None]:
    columns = {
        name: _find_column(headers, aliases)
        for name, aliases in _HEADER_ALIASES.items()
    }
    if not columns["occurred_at"]:
        columns["occurred_at"] = _infer_date_column(headers, rows)
    if columns["debit"] or columns["credit"]:
        if not columns["amount"]:
            columns["amount"] = None
    elif not columns["amount"]:
        columns["amount"] = _infer_amount_column(headers, rows, {columns["occurred_at"]})

    required = ("occurred_at", "currency")
    missing = [name for name in required if not columns[name]]
    if not columns["amount"] and not columns["debit"] and not columns["credit"]:
        missing.append("amount, debit, or credit")
    if missing:
        raise CsvFormatError(
            "The CSV must include transaction date, currency, and amount columns "
            "(common header names are supported)"
        )

    mapped_fields = [value for value in columns.values() if value]
    if len(mapped_fields) != len(set(mapped_fields)):
        raise CsvFormatError("The CSV contains columns that map to multiple transaction fields")
    return columns


def _infer_date_column(
    headers: list[str], rows: list[dict[str | None, str | list[str] | None]]
) -> str | None:
    for header in headers:
        values = [
            row.get(header).strip()
            for row in rows[:50]
            if isinstance(row.get(header), str) and row[header].strip()
        ]
        if not values:
            continue
        matching = 0
        for value in values:
            normalized = f"{value[:-1]}+00:00" if value.endswith("Z") else value
            try:
                datetime.fromisoformat(normalized)
            except ValueError:
                continue
            matching += 1
        if matching / len(values) >= 0.8:
            return header
    return None


def _infer_amount_column(
    headers: list[str],
    rows: list[dict[str | None, str | list[str] | None]],
    excluded: set[str | None],
) -> str | None:
    candidates: list[tuple[float, str]] = []
    for header in headers:
        if header in excluded:
            continue
        values = [
            row.get(header)
            for row in rows[:50]
            if isinstance(row.get(header), str) and row[header].strip()
        ]
        if not values:
            continue
        numeric_ratio = sum(_parse_money(value) is not None for value in values) / len(values)
        normalized_header = _normalize_header(header)
        preferred = any(token in normalized_header for token in ("amount", "value", "total", "sum", "paid", "payment", "balance", "net"))
        identifier = any(token in normalized_header for token in ("accountnumber", "reference", "transactionid", "code"))
        score = numeric_ratio + (0.25 if preferred else 0) - (0.5 if identifier else 0)
        if score >= 0.75:
            candidates.append((score, header))
    return max(candidates, default=(0, None))[1]


def _parse_money(value: str | None) -> tuple[Decimal, str] | None:
    original = (value or "").strip()
    if not original:
        return None
    suffix_match = re.search(r"\b(CR|CREDIT|DR|DEBIT)\s*$", original, re.IGNORECASE)
    suffix = suffix_match.group(1).upper() if suffix_match else ""
    negative = (
        (original.startswith("(") and original.endswith(")"))
        or original.startswith("-")
        or suffix in {"DR", "DEBIT"}
    )
    normalized = re.sub(r"\b(CR|CREDIT|DR|DEBIT)\s*$", "", original, flags=re.IGNORECASE)
    normalized = normalized.strip().strip("()")
    normalized = re.sub(r"[£$€¥\s]", "", normalized)
    if "." in normalized or not re.search(r",\d{1,2}$", normalized):
        normalized = normalized.replace(",", "")
    else:
        normalized = normalized.replace(",", ".")
    try:
        amount = Decimal(normalized)
    except InvalidOperation:
        return None
    if not amount.is_finite():
        return None
    direction = (
        "outflow" if negative or amount < 0
        else "inflow"
    )
    if suffix in {"CR", "CREDIT"}:
        direction = "inflow"
    return abs(amount), direction


def _canonicalize_row(
    row: dict[str | None, str | list[str] | None],
    columns: dict[str, str | None],
) -> dict[str | None, str | None] | None:
    if row is None:
        return None
    canonical: dict[str | None, str | None] = {}
    if None in row:
        canonical[None] = None
    canonical["occurred_at"] = _cell_value(row, columns["occurred_at"])
    canonical["currency"] = _cell_value(row, columns["currency"])
    for field in ("description", "category", "external_ref"):
        canonical[field] = _cell_value(row, columns[field]) or ""

    account_column = columns["account_name"]
    canonical["account_name"] = _cell_value(row, account_column) or "Imported account"

    amount_column = columns["amount"]
    debit_column = columns["debit"]
    credit_column = columns["credit"]
    debit = _parse_money(_cell_value(row, debit_column))
    credit = _parse_money(_cell_value(row, credit_column))
    amount = _parse_money(_cell_value(row, amount_column))
    if debit_column or credit_column:
        value = (debit[0] if debit else Decimal(0)) + (credit[0] if credit else Decimal(0))
        inferred_direction = "outflow" if debit and debit[0] > 0 else "inflow"
    else:
        value = amount[0] if amount else None
        inferred_direction = amount[1] if amount else ""
    canonical["amount"] = format(value, "f") if value is not None else ""

    direction_column = columns["direction"]
    direction = _cell_value(row, direction_column) or inferred_direction
    normalized_direction = (direction or "").strip().casefold()
    if normalized_direction in {"debit", "dr", "withdrawal", "outflow", "expense"}:
        direction = "outflow"
    elif normalized_direction in {"credit", "cr", "deposit", "inflow", "income"}:
        direction = "inflow"
    canonical["direction"] = direction
    return canonical


def _cell_value(
    row: dict[str | None, str | list[str] | None], column: str | None
) -> str | None:
    value = row.get(column) if column else None
    return value if isinstance(value, str) else None


def _row_error_code(row: dict[str, str | None]) -> str | None:
    if None in row or any(value is None for value in row.values()):
        return "column_count_mismatch"

    account_name = (row.get("account_name") or "").strip()
    if not account_name or len(account_name) > 200:
        return "invalid_account_name"

    description = (row.get("description") or "").strip()
    category = (row.get("category") or "").strip()
    external_ref = (row.get("external_ref") or "").strip()
    if len(description) > 500 or len(category) > 100 or len(external_ref) > 255:
        return "field_too_long"

    try:
        _parse_datetime(row.get("occurred_at") or "")
    except ValueError:
        return "invalid_occurred_at"

    try:
        amount = Decimal((row.get("amount") or "").strip())
    except InvalidOperation:
        return "invalid_amount"
    if not amount.is_finite() or amount <= 0:
        return "invalid_amount"
    if amount.as_tuple().exponent < -4 or amount >= Decimal("1e16"):
        return "amount_precision_out_of_range"

    currency = (row.get("currency") or "").strip().upper()
    if not _CURRENCY_PATTERN.fullmatch(currency):
        return "invalid_currency"

    direction = (row.get("direction") or "").strip().casefold()
    if direction not in {"inflow", "outflow"}:
        return "invalid_direction"

    return None


def _parse_row(row: dict[str, str | None]) -> ParsedTransaction:
    occurred_at = _parse_datetime(row["occurred_at"] or "")
    amount = Decimal((row["amount"] or "").strip()).quantize(Decimal("0.0001"))
    currency = (row["currency"] or "").strip().upper()
    direction = (row["direction"] or "").strip().casefold()
    account_name = (row["account_name"] or "").strip()
    description = (row.get("description") or "").strip()
    category = (row.get("category") or "").strip() or None
    external_ref = (row.get("external_ref") or "").strip() or None

    hash_input = "\x1f".join(
        (
            occurred_at.isoformat(),
            account_name,
            format(amount, "f"),
            currency,
            direction,
            description,
            category or "",
            external_ref or "",
        )
    )
    source_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

    return ParsedTransaction(
        occurred_at=occurred_at,
        account_name=account_name,
        amount=amount,
        currency=currency,
        direction=direction,
        description=description,
        category=category,
        external_ref=external_ref,
        source_hash=source_hash,
    )


def _parse_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    return parsed.astimezone(UTC)
