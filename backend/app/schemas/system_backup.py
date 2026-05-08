from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class BackupScheduleConfig(BaseModel):
    job_key: str
    enabled: bool
    days: list[int]
    run_at_hour: int
    run_at_minute: int
    interval_minutes: int | None = None


class BackupSettings(BaseModel):
    currency_primary: str
    currency_secondary: str
    birth_date: Optional[date] = None
    plan_to_age: Optional[int] = None
    privacy_mode: bool = False
    telegram_chat_id: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    sec_api_key: Optional[str] = None
    schedule_timezone: str = "Asia/Bangkok"
    schedule_configs: list[BackupScheduleConfig] = []


class BackupHolding(BaseModel):
    symbol: str
    asset_type: str
    quantity: Decimal
    avg_cost_price: Decimal
    currency: str
    platform: Optional[str] = None
    purchased_at: Optional[date] = None


class BackupTransaction(BaseModel):
    symbol: str
    asset_type: str
    type: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    source: str
    executed_at: datetime
    platform: Optional[str] = None


class BackupPortfolio(BaseModel):
    holdings: list[BackupHolding] = []
    transactions: list[BackupTransaction] = []


class BackupProviderConfig(BaseModel):
    provider: str
    api_key: Optional[str] = None
    host_url: Optional[str] = None
    is_connected: bool = False


class BackupFeatureLLMConfig(BaseModel):
    feature_key: str
    provider: str
    model: str
    system_prompt: str
    is_prompt_customized: bool = False


class BackupWatchlistItem(BaseModel):
    symbol: str
    asset_type: str
    target_price: Optional[Decimal] = None
    currency: str = "USD"
    notes: Optional[str] = None
    alert_enabled: bool = True
    created_at: datetime


class BackupCashBalance(BaseModel):
    symbol: str
    asset_type: str = "cash"
    balance: Decimal
    snapshot_date: date
    notes: Optional[str] = None


class BackupConversation(BaseModel):
    role: str
    content: str
    message_order: int


class BackupAIAnalysis(BaseModel):
    symbol: str
    asset_type: str = "us_stock"
    verdict: str
    target_price: Optional[Decimal] = None
    reasoning: str
    provider: str
    model: str
    created_at: datetime
    conversations: list[BackupConversation] = []


class BackupPlatformConfig(BaseModel):
    name: str
    color: str


class SystemBackup(BaseModel):
    model_config = {"from_attributes": True}

    version: str = "3"
    exported_at: datetime
    settings: BackupSettings
    portfolio: BackupPortfolio
    provider_configs: list[BackupProviderConfig] = []
    feature_llm_configs: list[BackupFeatureLLMConfig] = []
    watchlist: list[BackupWatchlistItem] = []
    cash_balances: list[BackupCashBalance] = []
    ai_analyses: list[BackupAIAnalysis] = []
    platform_configs: list[BackupPlatformConfig] = []
