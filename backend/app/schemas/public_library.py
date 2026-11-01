from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CurrencySummary(BaseModel):
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    inflow: float = Field(ge=0, allow_inf_nan=False)
    outflow: float = Field(ge=0, allow_inf_nan=False)
    transactions: int = Field(ge=0)


class MonthlySummary(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    inflow: float = Field(ge=0, allow_inf_nan=False)
    outflow: float = Field(ge=0, allow_inf_nan=False)


class CategorySummary(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    inflow: float = Field(ge=0, allow_inf_nan=False)
    outflow: float = Field(ge=0, allow_inf_nan=False)
    transactions: int = Field(ge=0)


class DatasetContext(BaseModel):
    source_kind: Literal["demo", "local"]
    source_name: str = Field(min_length=1, max_length=255)
    transaction_count: int = Field(ge=1)
    undated_count: int = Field(ge=0)
    currencies: list[CurrencySummary] = Field(max_length=10)
    monthly: list[MonthlySummary] = Field(max_length=120)
    categories: list[CategorySummary] = Field(max_length=50)


class PublicQuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    dataset: DatasetContext | None = None


class PublicCitation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    title: str
    publisher: str
    url: str
    edition: str
    retrieved_at: str
    section: str
    excerpt: str


class PublicAnswerResponse(BaseModel):
    answer: str
    citations: list[PublicCitation]
    abstained: bool
    data_based: bool = False
    model: str
