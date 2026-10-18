from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, model_validator

from .common import Money


class StatsFilter(BaseModel):
    location_id: int | None = None
    date_from: date
    date_to: date
    group_by: Literal["hour", "day", "week", "month"] = "day"

    @model_validator(mode="after")
    def check_period(self):
        if self.date_to < self.date_from:
            raise ValueError("date_to раньше date_from")
        if (self.date_to - self.date_from).days > 366:
            raise ValueError("Период не больше года")
        return self


class KpiOut(BaseModel):
    revenue: Money
    orders_count: int
    avg_check: Money
    new_customers: int
    returning_customers: int
    gifts_redeemed: int
    stamps_issued: int
    avg_prep_seconds: int
    cancel_rate: float
    avg_rating: float | None
    prev_period: "KpiOut | None" = None


class TimeSeriesPoint(BaseModel):
    ts: datetime
    revenue: Money
    orders: int


class TopProductOut(BaseModel):
    product_id: int | None
    name: str
    quantity: int
    revenue: Money


class HourHeatmapCell(BaseModel):
    weekday: int
    hour: int
    orders: int


class DashboardOut(BaseModel):
    kpi: KpiOut
    series: list[TimeSeriesPoint]
    top_products: list[TopProductOut]
    heatmap: list[HourHeatmapCell] = []
    payment_methods: dict[str, int] = {}
