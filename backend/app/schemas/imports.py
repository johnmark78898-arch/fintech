from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ImportRowErrorResponse(BaseModel):
    row_number: int
    code: str


class CsvImportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    import_id: UUID
    status: str
    total_rows: int
    inserted_rows: int
    duplicate_rows: int
    rejected_rows: int
    row_errors: list[ImportRowErrorResponse]
