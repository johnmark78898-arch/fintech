import logging
from typing import Annotated
from uuid import UUID

from app.core.auth import get_current_user
from app.database.session import get_session
from app.financial_data.csv_import import MAX_UPLOAD_BYTES, CsvFormatError
from app.financial_data.import_service import ImportSummary, import_transactions_csv
from app.models.entities import User
from app.schemas.imports import CsvImportResponse
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
router = APIRouter(tags=["financial data"])


@router.post(
    "/organizations/{organization_id}/imports/csv",
    response_model=CsvImportResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_transactions_csv(
    organization_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    file: Annotated[UploadFile, File()],
) -> CsvImportResponse:
    filename = file.filename or ""
    if not filename.casefold().endswith(".csv"):
        raise HTTPException(status_code=415, detail="Only CSV uploads are supported")

    try:
        content = file.file.read(MAX_UPLOAD_BYTES + 1)
    finally:
        file.file.close()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="The uploaded file exceeds the size limit")

    try:
        result: ImportSummary = import_transactions_csv(
            session,
            organization_id=organization_id,
            user_id=current_user.id,
            filename=filename,
            content=content,
        )
        session.commit()
    except PermissionError:
        session.rollback()
        raise HTTPException(status_code=403, detail="Import permission is required") from None
    except (CsvFormatError, ValueError) as error:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from None
    except SQLAlchemyError:
        session.rollback()
        logger.exception("CSV import persistence failed", extra={"organization_id": str(organization_id)})
        raise HTTPException(status_code=500, detail="The import could not be completed") from None

    return CsvImportResponse(
        import_id=result.import_id,
        status=result.status,
        total_rows=result.total_rows,
        inserted_rows=result.inserted_rows,
        duplicate_rows=result.duplicate_rows,
        rejected_rows=result.rejected_rows,
        row_errors=[
            {"row_number": error.row_number, "code": error.code}
            for error in result.row_errors
        ],
    )
