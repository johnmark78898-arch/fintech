import hashlib
from dataclasses import dataclass
from uuid import UUID

from app.financial_data.csv_import import RowError, parse_transactions_csv
from app.models.entities import (
    FinancialAccount,
    FinancialTransaction,
    ImportBatch,
    OrganizationMembership,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

UPLOAD_ROLES = frozenset({"owner", "admin", "analyst"})


@dataclass(frozen=True, slots=True)
class ImportSummary:
    import_id: UUID
    status: str
    total_rows: int
    inserted_rows: int
    duplicate_rows: int
    rejected_rows: int
    row_errors: tuple[RowError, ...]


def import_transactions_csv(
    session: Session,
    *,
    organization_id: UUID,
    user_id: UUID,
    filename: str,
    content: bytes,
) -> ImportSummary:
    membership = session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == "active",
        )
    )
    if membership is None or membership.role_key not in UPLOAD_ROLES:
        raise PermissionError("User is not authorized to import financial data")

    safe_filename = filename.replace("\\", "/").rsplit("/", maxsplit=1)[-1].strip()
    if not safe_filename or len(safe_filename) > 255:
        raise ValueError("A valid filename is required")

    parsed = parse_transactions_csv(content)
    batch = ImportBatch(
        organization_id=organization_id,
        uploaded_by=user_id,
        filename=safe_filename,
        sha256=hashlib.sha256(content).hexdigest(),
        status="processing",
        row_count=parsed.total_rows,
        rejected_count=parsed.rejected_rows,
        error_summary=[
            {"row_number": error.row_number, "code": error.code}
            for error in parsed.row_errors
        ],
    )
    session.add(batch)
    session.flush()

    candidate_hashes = {record.source_hash for record in parsed.records}
    existing_hashes: set[str] = set()
    if candidate_hashes:
        existing_hashes = set(
            session.scalars(
                select(FinancialTransaction.source_hash).where(
                    FinancialTransaction.organization_id == organization_id,
                    FinancialTransaction.source_hash.in_(candidate_hashes),
                )
            )
        )

    accounts: dict[tuple[str, str], FinancialAccount] = {}
    new_transactions: list[FinancialTransaction] = []
    seen_hashes: set[str] = set()
    duplicate_rows = 0

    for record in parsed.records:
        if record.source_hash in existing_hashes or record.source_hash in seen_hashes:
            duplicate_rows += 1
            continue
        seen_hashes.add(record.source_hash)

        account_key = (record.account_name, record.currency)
        account = accounts.get(account_key)
        if account is None:
            account = session.scalar(
                select(FinancialAccount).where(
                    FinancialAccount.organization_id == organization_id,
                    FinancialAccount.name == record.account_name,
                    FinancialAccount.currency == record.currency,
                )
            )
            if account is None:
                account = FinancialAccount(
                    organization_id=organization_id,
                    name=record.account_name,
                    account_type="unknown",
                    currency=record.currency,
                    source="csv",
                )
                session.add(account)
                session.flush()
            accounts[account_key] = account

        new_transactions.append(
            FinancialTransaction(
                organization_id=organization_id,
                account_id=account.id,
                import_batch_id=batch.id,
                external_ref=record.external_ref,
                occurred_at=record.occurred_at,
                description=record.description,
                amount=record.amount,
                currency=record.currency,
                direction=record.direction,
                category=record.category,
                source_hash=record.source_hash,
            )
        )

    session.add_all(new_transactions)
    batch.accepted_count = len(new_transactions)
    batch.duplicate_count = duplicate_rows
    batch.status = "completed_with_errors" if parsed.rejected_rows else "completed"
    session.flush()

    return ImportSummary(
        import_id=batch.id,
        status=batch.status,
        total_rows=parsed.total_rows,
        inserted_rows=batch.accepted_count,
        duplicate_rows=batch.duplicate_count,
        rejected_rows=batch.rejected_count,
        row_errors=parsed.row_errors,
    )
