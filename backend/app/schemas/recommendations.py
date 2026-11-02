from typing import Literal

from app.schemas.public_library import DatasetContext
from pydantic import BaseModel, Field


class RecommendationItemSummary(BaseModel):
    item: str = Field(min_length=1, max_length=120)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    transactions: int = Field(ge=1)
    inflow: float = Field(ge=0, allow_inf_nan=False)
    outflow: float = Field(ge=0, allow_inf_nan=False)
    quantity: float | None = Field(default=None, allow_inf_nan=False)
    sales_count: int | None = Field(default=None, ge=0)
    units_sold: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    return_count: int | None = Field(default=None, ge=0)
    peer_product_count: int | None = Field(default=None, ge=0)
    peer_median_units_sold: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    first_seen_month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    last_seen_month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")


class MonthlyCategorySummary(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    category: str = Field(min_length=1, max_length=80)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    outflow: float = Field(ge=0, allow_inf_nan=False)
    transactions: int = Field(ge=0)


class MonthlyReturnSummary(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    sales_count: int = Field(ge=0)
    return_count: int = Field(ge=0)


class RecommendationRequest(BaseModel):
    dataset: DatasetContext
    items: list[RecommendationItemSummary] = Field(default_factory=list, max_length=10)
    monthly_categories: list[MonthlyCategorySummary] = Field(default_factory=list, max_length=6000)
    monthly_returns: list[MonthlyReturnSummary] = Field(default_factory=list, max_length=1200)


class BusinessRecommendation(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    observation: str = Field(min_length=1, max_length=400)
    why_it_matters: str = Field(min_length=1, max_length=400)
    action: str = Field(min_length=1, max_length=500)
    priority: Literal["high", "medium", "low"]
    confidence: Literal["high", "moderate", "low"] = "low"
    item: str | None = Field(default=None, max_length=120)


class RecommendationResponse(BaseModel):
    recommendations: list[BusinessRecommendation] = Field(max_length=4)
    abstained: bool
    model: str
    notice: str | None = Field(default=None, max_length=300)
