from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.public_library import DatasetContext


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


class RecommendationRequest(BaseModel):
    dataset: DatasetContext
    items: list[RecommendationItemSummary] = Field(default_factory=list, max_length=10)


class BusinessRecommendation(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    observation: str = Field(min_length=1, max_length=400)
    why_it_matters: str = Field(min_length=1, max_length=400)
    action: str = Field(min_length=1, max_length=500)
    priority: Literal["high", "medium", "low"]
    item: str | None = Field(default=None, max_length=120)


class RecommendationResponse(BaseModel):
    recommendations: list[BusinessRecommendation] = Field(max_length=4)
    abstained: bool
    model: str
    notice: str | None = Field(default=None, max_length=300)
