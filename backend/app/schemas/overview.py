from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class OverviewSummary(BaseModel):
    total_value: Decimal
    total_cost: Decimal
    total_pnl: Decimal
    total_pnl_pct: Decimal
    daily_change: Decimal
    daily_change_pct: Decimal


class AllocationItem(BaseModel):
    asset_type: str
    value: Decimal
    pct: Decimal


class PerformancePoint(BaseModel):
    date: date
    value: Decimal


class PerformanceResponse(BaseModel):
    portfolio: list[PerformancePoint]
    benchmark: list[PerformancePoint]
