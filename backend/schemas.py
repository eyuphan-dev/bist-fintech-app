from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, date
from typing import List, Dict, Any, Optional

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
    current_price: float
    price_change_pct: float
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
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

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

class StockDetailResponse(BaseModel):
    id: int
    symbol: str
    company_name: str
    current_price: float
    prices: List[StockPriceResponse]
    indicators: Dict[str, Any]

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

class PortfolioResponse(BaseModel):
    balance: float
    total_portfolio_value: float
    items: List[PortfolioItemResponse]

class BotLogResponse(BaseModel):
    id: int
    symbol: str
    action_type: str
    price: float
    quantity: float
    reason_text: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

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

class KapNotificationResponse(BaseModel):
    id: int
    symbol: str
    title: str
    summary: Optional[str]
    kap_url: Optional[str]
    publish_date: datetime

    class Config:
        from_attributes = True

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
    is_active: Optional[bool] = None

class UserBotResponse(BaseModel):
    bot_name: str
    virtual_balance: float
    is_active: bool
    risk_profile: str
    time_frame: str
    time_frame_label: str
    started_at: Optional[datetime]
    ends_at: Optional[datetime]
    remaining_seconds: Optional[int]
    portfolio_value: float
    total_return_pct: float
    total_trades: int
    win_rate: float
