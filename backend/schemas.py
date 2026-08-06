from pydantic import BaseModel, EmailStr, Field, model_validator, field_serializer
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Any, Optional


def _utc_iso(value: Optional[datetime]) -> Optional[str]:
    """
    DB'deki datetime değerleri "naive" ama semantik olarak UTC'dir (datetime.utcnow()
    konvansiyonu). tzinfo eklenmeden JSON'a çıkarsa (ör. "2026-07-29T07:00:00")
    tarayıcı bunu YEREL saat sanıp new Date(...) ile yanlış yorumluyordu — örneğin
    İstanbul saatiyle 10:00 olarak girilen bir zamanlı emir, arayüzde 07:00 olarak
    görünüyordu. Burada tzinfo=UTC eklenip ISO 8601 + offset ile dönülür ki frontend
    new Date(...)/Intl.DateTimeFormat ile doğru yerel saati hesaplayabilsin.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    terms_accepted: bool = Field(..., description="Kullanıcı sözleşmesi, KVKK ve sorumluluk reddi feragatnamesi onayı (zorunlu)")

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    virtual_balance: float
    is_bot: bool
    terms_accepted: bool
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> Optional[str]:
        return _utc_iso(value)

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class LoginRequest(BaseModel):
    username: str
    password: str

class StockResponse(BaseModel):
    id: int
    symbol: str
    company_name: str
    is_active: bool
    sector: Optional[str] = None
    current_price: float
    price_change_pct: Optional[float] = None
    is_katilim_compliant: bool
    purification_rate: float

class CompanyAnalysisResponse(BaseModel):
    piotroski_score: Optional[int]
    pe_ratio: Optional[float]
    pb_ratio: Optional[float]
    ev_ebitda: Optional[float]
    sector_pe_avg: Optional[float]
    fair_value: Optional[float]
    discount_rate: Optional[float]
    roe: Optional[float]
    gross_margin: Optional[float]
    net_margin: Optional[float]
    fx_exposure_text: Optional[str]
    interest_sensitivity_text: Optional[str]
    altman_z_score: Optional[float] = None
    altman_zone: Optional[str] = None
    debt_to_equity: Optional[float] = None
    net_fx_position: Optional[str] = None
    target_mean_price: Optional[float] = None
    target_high_price: Optional[float] = None
    target_low_price: Optional[float] = None
    target_upside_pct: Optional[float] = None
    number_of_analysts: Optional[int] = None
    recommendation_key: Optional[str] = None
    analyst_buy_count: Optional[int] = None
    analyst_hold_count: Optional[int] = None
    analyst_sell_count: Optional[int] = None
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

    @field_serializer("updated_at")
    def _serialize_updated_at(self, value: Optional[datetime]) -> Optional[str]:
        return _utc_iso(value)

class EarningsCalendarItem(BaseModel):
    symbol: str
    company_name: str
    next_earnings_date: date

class PivotLevelsResponse(BaseModel):
    symbol: str
    as_of_date: Optional[str] = None
    previous_close: Optional[float] = None
    pivot: Optional[float] = None
    r1: Optional[float] = None
    r2: Optional[float] = None
    r3: Optional[float] = None
    s1: Optional[float] = None
    s2: Optional[float] = None
    s3: Optional[float] = None
    fib_236: Optional[float] = None
    fib_382: Optional[float] = None
    fib_500: Optional[float] = None
    fib_618: Optional[float] = None
    available: bool = True
    message: Optional[str] = None

class ForeignHoldingTrendResponse(BaseModel):
    symbol: str
    current_pct: Optional[float] = None
    change_30d: Optional[float] = None
    change_90d: Optional[float] = None
    available: bool = False
    message: Optional[str] = None

class KatilimInfoResponse(BaseModel):
    is_katilim_compliant: bool
    purification_rate: float
    non_compliance_reason: Optional[str]

class StockProResponse(BaseModel):
    symbol: str
    company_name: str
    katilim: KatilimInfoResponse
    analysis: Optional[CompanyAnalysisResponse]

class StockPriceResponse(BaseModel):
    price: float
    volume: Optional[int]
    recorded_at: datetime

    class Config:
        from_attributes = True

    @field_serializer("recorded_at")
    def _serialize_recorded_at(self, value: datetime) -> Optional[str]:
        return _utc_iso(value)

class StockDetailResponse(BaseModel):
    id: int
    symbol: str
    company_name: str
    current_price: float
    prices: List[StockPriceResponse]
    indicators: Dict[str, Any]
    previous_close: Optional[float] = None
    open_price: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    change_pct: Optional[float] = None

class TradeRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10)
    action_type: str = Field(..., pattern="^(AL|SAT|al|sat)$", description="'AL' veya 'SAT'")
    # gt=0 negatif/sıfır miktarları reddeder; allow_inf_nan=False NaN/Infinity payload'larını reddeder.
    quantity: float = Field(..., gt=0, le=10_000_000, allow_inf_nan=False)

class PortfolioItemResponse(BaseModel):
    symbol: str
    company_name: str
    quantity: float
    average_cost: float
    current_price: float
    current_value: float
    profit_loss_pct: float
    opened_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_serializer("opened_at", "updated_at")
    def _serialize_dates(self, value: Optional[datetime]) -> Optional[str]:
        return _utc_iso(value)

class PortfolioResponse(BaseModel):
    balance: float
    total_portfolio_value: float
    baseline_value: float
    profit_loss_pct: float
    items: List[PortfolioItemResponse]

class BotLogResponse(BaseModel):
    id: int
    symbol: str
    action_type: str
    price: float
    quantity: float
    reason_text: Optional[str]
    time_frame: Optional[str] = None
    days_held: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> Optional[str]:
        return _utc_iso(value)

class BotPerformancePoint(BaseModel):
    date: date
    total_portfolio_value: float

class LeaderboardItem(BaseModel):
    username: str
    total_portfolio_value: float
    profit_loss_pct: float
    is_bot: bool


# --- MIDAS PRO / HELAL FİNANS EK ŞEMALARI ---

class InsiderTradeResponse(BaseModel):
    id: int
    symbol: str
    title_person: str
    trade_type: str
    quantity: float
    price: float
    trade_date: datetime

    class Config:
        from_attributes = True

    @field_serializer("trade_date")
    def _serialize_trade_date(self, value: datetime) -> Optional[str]:
        return _utc_iso(value)

class KapNotificationResponse(BaseModel):
    id: int
    symbol: str
    title: str
    summary: Optional[str]
    kap_url: Optional[str]
    publish_date: datetime

    class Config:
        from_attributes = True

    @field_serializer("publish_date")
    def _serialize_publish_date(self, value: datetime) -> Optional[str]:
        return _utc_iso(value)

class StockNewsItem(BaseModel):
    title: str
    summary: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[str] = None
    thumbnail: Optional[str] = None

class FundPriceResponse(BaseModel):
    price: float
    daily_return: Optional[float]
    monthly_return: Optional[float]
    yearly_return: Optional[float]
    recorded_date: date

    class Config:
        from_attributes = True

class FundResponse(BaseModel):
    code: str
    name: str
    fund_type: Optional[str]
    risk_level: Optional[int]
    is_katilim_compliant: bool
    latest_price: Optional[FundPriceResponse]

class IpoResponse(BaseModel):
    id: int
    company_name: str
    symbol: Optional[str]
    offer_price: Optional[float]
    demand_collection_dates: Optional[str]
    is_katilim_compliant: bool
    lot_distribution_type: Optional[str]

    class Config:
        from_attributes = True

class StockCommentCreate(BaseModel):
    comment_text: str = Field(..., min_length=2, max_length=500)

class StockCommentResponse(BaseModel):
    id: int
    username: str
    comment_text: str
    sentiment_score: Optional[float]
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> Optional[str]:
        return _utc_iso(value)

class CommunitySentimentResponse(BaseModel):
    symbol: str
    total_comments: int
    positive_pct: float
    negative_pct: float
    neutral_pct: float
    verdict_text: str

class DividendGoalRequest(BaseModel):
    target_monthly_income: float = Field(..., gt=0, le=100_000_000, allow_inf_nan=False)

class DcaBacktestRequest(BaseModel):
    monthly_amount: float = Field(..., gt=0, le=100_000_000, allow_inf_nan=False)
    months: int = Field(12, ge=1, le=60)


# --- KİŞİSEL AI BOT & BAKİYE YÖNETİMİ ---

class BalanceUpdateRequest(BaseModel):
    new_balance: float = Field(..., ge=0, le=100_000_000, allow_inf_nan=False, description="Yeni sanal bakiye (TL)")

class UserBotSettingsRequest(BaseModel):
    time_frame: Optional[str] = Field(None, pattern="^(1D|1W|1M)$", description="'1D', '1W' veya '1M'")
    risk_mode: Optional[str] = Field(None, pattern="^(slow|normal|aggressive)$", description="'slow', 'normal' veya 'aggressive'")
    is_active: Optional[bool] = None

class UserBotResponse(BaseModel):
    bot_name: str
    virtual_balance: float
    is_active: bool
    risk_mode: str
    risk_mode_label: str
    time_frame: str
    time_frame_label: str
    started_at: Optional[datetime]
    ends_at: Optional[datetime]
    remaining_seconds: Optional[int]
    portfolio_value: float
    total_return_pct: float
    total_trades: int
    win_rate: float

    @field_serializer("started_at", "ends_at")
    def _serialize_dates(self, value: Optional[datetime]) -> Optional[str]:
        return _utc_iso(value)


# --- BEKLEYEN EMİRLER (LİMİT / ZAMANLI ALIM-SATIM) ---

ORDER_TYPES = ("LIMIT_BUY", "LIMIT_SELL", "SCHEDULED_BUY")

class PendingOrderCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10)
    order_type: str = Field(..., pattern="^(LIMIT_BUY|LIMIT_SELL|SCHEDULED_BUY)$")
    quantity: float = Field(..., gt=0, le=10_000_000, allow_inf_nan=False)
    target_price: Optional[float] = Field(None, gt=0, le=1_000_000, allow_inf_nan=False)
    execution_time: Optional[datetime] = None

    @model_validator(mode="after")
    def _validate_type_specific_fields(self):
        if self.order_type in ("LIMIT_BUY", "LIMIT_SELL"):
            if self.target_price is None:
                raise ValueError("LIMIT_BUY / LIMIT_SELL emirleri için target_price zorunludur.")
        elif self.order_type == "SCHEDULED_BUY":
            if self.execution_time is None:
                raise ValueError("SCHEDULED_BUY emirleri için execution_time zorunludur.")
            exec_time = self.execution_time
            now = datetime.now(exec_time.tzinfo) if exec_time.tzinfo else datetime.utcnow()
            if exec_time <= now:
                raise ValueError("execution_time gelecekte bir zaman olmalıdır.")
            if exec_time > now + timedelta(days=90):
                raise ValueError("execution_time en fazla 90 gün sonrasına ayarlanabilir.")
        return self

class PendingOrderUpdate(BaseModel):
    """PENDING durumundaki bir emrin adet/hedef fiyat/zamanlamasını günceller — yalnızca gönderilen alanlar değiştirilir."""
    quantity: Optional[float] = Field(None, gt=0, le=10_000_000, allow_inf_nan=False)
    target_price: Optional[float] = Field(None, gt=0, le=1_000_000, allow_inf_nan=False)
    execution_time: Optional[datetime] = None

    @model_validator(mode="after")
    def _validate_execution_time(self):
        if self.execution_time is not None:
            now = datetime.now(self.execution_time.tzinfo) if self.execution_time.tzinfo else datetime.utcnow()
            if self.execution_time <= now:
                raise ValueError("execution_time gelecekte bir zaman olmalıdır.")
            if self.execution_time > now + timedelta(days=90):
                raise ValueError("execution_time en fazla 90 gün sonrasına ayarlanabilir.")
        return self

class PendingOrderResponse(BaseModel):
    id: int
    symbol: str
    order_type: str
    quantity: float
    target_price: Optional[float]
    execution_time: Optional[datetime]
    status: str
    fail_reason: Optional[str]
    created_at: datetime
    executed_at: Optional[datetime]

    class Config:
        from_attributes = True

    @field_serializer("execution_time", "created_at", "executed_at")
    def _serialize_as_utc(self, value: Optional[datetime]) -> Optional[str]:
        return _utc_iso(value)


class NotificationPreferenceRequest(BaseModel):
    price_above: Optional[float] = None
    price_below: Optional[float] = None
    pct_change_trigger: Optional[float] = None
    notify_kap: bool = False
    notify_ai_signal: bool = False

class NotificationPreferenceResponse(BaseModel):
    stock_symbol: str
    price_above: Optional[float] = None
    price_below: Optional[float] = None
    pct_change_trigger: Optional[float] = None
    notify_kap: bool
    notify_ai_signal: bool

    class Config:
        from_attributes = True

class NotificationResponse(BaseModel):
    id: int
    stock_symbol: Optional[str] = None
    notif_type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> Optional[str]:
        return _utc_iso(value)

class UnreadCountResponse(BaseModel):
    count: int


class ScreenerItemResponse(BaseModel):
    symbol: str
    company_name: str
    sector: Optional[str] = None
    current_price: float
    price_change_pct: Optional[float] = None
    is_katilim_compliant: bool
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    roe: Optional[float] = None
    piotroski_score: Optional[int] = None
    altman_z_score: Optional[float] = None
    debt_to_equity: Optional[float] = None
    net_margin: Optional[float] = None


class WatchlistItemResponse(BaseModel):
    symbol: str
    company_name: str
    current_price: float
    price_change_pct: Optional[float] = None
    is_katilim_compliant: bool
    purification_rate: float
    added_at: datetime

    @field_serializer("added_at")
    def _serialize_added_at(self, value: datetime) -> Optional[str]:
        return _utc_iso(value)


class BotSessionResponse(BaseModel):
    id: int
    time_frame: str
    time_frame_label: str
    risk_mode: Optional[str]
    risk_mode_label: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    end_reason: Optional[str]
    is_active: bool
    trade_count: int

    class Config:
        from_attributes = True

    @field_serializer("started_at", "ended_at")
    def _serialize_dt(self, value: Optional[datetime]) -> Optional[str]:
        return _utc_iso(value) if value else None
