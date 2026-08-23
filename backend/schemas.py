from pydantic import BaseModel, EmailStr, Field, model_validator, field_serializer
from datetime import datetime, date, timedelta, timezone
from typing import List, Dict, Any, Optional, Literal


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

class ChangePasswordRequest(BaseModel):
    """
    Şifre değiştirme. Yeni şifre kuralı UserCreate ile aynı tutulur (min 6),
    aksi halde kayıtta kabul edilmeyen bir şifre buradan geçebilirdi.
    """
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6)

    @model_validator(mode="after")
    def _reject_same_password(self):
        if self.current_password == self.new_password:
            raise ValueError("Yeni şifre mevcut şifreyle aynı olamaz.")
        return self


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
    katilim_status: Optional[str] = None  # UYGUN | UYGUN_DEGIL | BELIRSIZ
    purification_rate: float

class SectorAllocationItem(BaseModel):
    sector: str
    value: float
    pct: float
    position_count: int

class PositionWeightItem(BaseModel):
    symbol: str
    value: float
    pct: float

class PortfolioAnalyticsResponse(BaseModel):
    """Portföy dağılım/yoğunlaşma analizi (yalnızca mevcut portföy verisinden hesaplanır)."""
    total_portfolio_value: float
    cash_balance: float
    stock_value: float
    cash_pct: float
    position_count: int
    sectors: List[SectorAllocationItem]
    positions: List[PositionWeightItem]
    top_position_symbol: Optional[str] = None
    top_position_pct: float
    top_sector: Optional[str] = None
    top_sector_pct: float
    effective_position_count: float
    diversification_score: int
    katilim_compliant_pct: float

class StockSearchResponse(BaseModel):
    """Navbar global arama sonuçları için hafif model (fiyat sorgusu yapılmaz)."""
    symbol: str
    company_name: str
    sector: Optional[str] = None
    is_katilim_compliant: bool
    katilim_status: Optional[str] = None  # UYGUN | UYGUN_DEGIL | BELIRSIZ

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
    dividend_yield: Optional[float] = None
    dividend_rate: Optional[float] = None
    fifty_two_week_high: Optional[float] = None
    fifty_two_week_low: Optional[float] = None
    market_cap: Optional[float] = None
    average_volume: Optional[int] = None
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
    katilim_status: Optional[str] = None  # UYGUN | UYGUN_DEGIL | BELIRSIZ
    purification_rate: float
    non_compliance_reason: Optional[str]
    # Hesaplanmış ön tarama çıktıları (bkz. katilim.py). Kullanıcı sonucu
    # değil GEREKÇEYİ görmeli; endeks bile bu oranları yayımlamıyor.
    debt_ratio: Optional[float] = None       # Finansal borç / toplam varlık (%)
    asset_ratio: Optional[float] = None      # Nakit + finansal yatırımlar / toplam varlık (%)
    threshold: float = 33.0
    detail: Optional[str] = None
    checked_at: Optional[datetime] = None

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
    # Bekleyen alış emirlerinde bloke edilen tutar ve emir verilebilir kalan bakiye.
    # balance = reserved_balance + available_balance
    reserved_balance: float = 0.0
    available_balance: float = 0.0
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

class TransactionItem(BaseModel):
    """Kullanıcının gerçekleşmiş tek bir alım/satım işlemi."""
    id: int
    symbol: str
    company_name: str
    action_type: str          # 'AL' / 'SAT'
    quantity: float
    price: float
    total_amount: float
    # Yalnızca SAT satırlarında dolu; AL'da None.
    realized_pnl: Optional[float] = None
    realized_pnl_pct: Optional[float] = None
    average_cost_at_trade: Optional[float] = None
    source: str               # 'MANUAL' / 'LIMIT_ORDER'
    created_at: datetime

    class Config:
        from_attributes = True

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> Optional[str]:
        return _utc_iso(value)


class TransactionHistoryResponse(BaseModel):
    """
    İşlem geçmişi + gerçekleşen (kapatılmış pozisyon) kâr/zarar özeti.

    Buradaki K/Z, portföy sayfasındaki kâr/zarardan FARKLIDIR: orası açık
    pozisyonların anlık (gerçekleşmemiş) durumunu gösterir, burası ise
    satılmış pozisyonlardan cebe giren/çıkan kesinleşmiş tutardır.
    """
    total_realized_pnl: float
    total_buy_amount: float
    total_sell_amount: float
    buy_count: int
    sell_count: int
    # Kâr ile kapatılan satışların tüm satışlara oranı (%) — None ise hiç satış yok.
    win_rate: Optional[float] = None
    items: List[TransactionItem]


class DividendPositionItem(BaseModel):
    symbol: str
    company_name: str
    quantity: float
    current_value: float
    dividend_yield: Optional[float] = None      # yıllık verim (%)
    annual_income: Optional[float] = None       # bu pozisyondan beklenen yıllık temettü (TL)
    yield_on_cost: Optional[float] = None       # maliyete göre verim (%) — asıl önemli olan bu
    last_dividend_date: Optional[date] = None


class PortfolioDividendResponse(BaseModel):
    """
    Portföyün beklenen yıllık temettü geliri projeksiyonu.

    Şirketlerin gelecekte aynı temettüyü ödeyeceği garanti DEĞİLDİR; bu yalnızca
    son bilinen verim üzerinden bir tahmindir. Bu yüzden alan adları "beklenen"
    olarak isimlendirilmiştir ve UI'da uyarı gösterilir.
    """
    total_annual_income: float
    monthly_average: float
    portfolio_value: float
    portfolio_yield: Optional[float] = None      # toplam gelir / portföy değeri (%)
    covered_positions: int                        # temettü verisi olan pozisyon sayısı
    total_positions: int
    items: List[DividendPositionItem]


class DividendPaymentItem(BaseModel):
    pay_date: date
    amount: float                       # hisse başına brüt TL
    year: int


class DividendHistoryResponse(BaseModel):
    symbol: str
    company_name: str
    payments: List[DividendPaymentItem]
    # Yıl bazında toplam ödeme — bir yılda birden fazla taksit olabildiği için
    # tek tek ödemeye bakmak "temettü arttı mı?" sorusunu yanıtlamaz.
    yearly_totals: Dict[str, float] = {}
    years_paid: int = 0
    last_payment_date: Optional[date] = None
    average_last_3y: Optional[float] = None
    trend: Optional[str] = None         # "Artıyor" / "Azalıyor" / "Değişken"


class SectorSummaryItem(BaseModel):
    """
    Sektör bazlı özet. Oranlarda ORTALAMA değil MEDYAN kullanılır: sektör
    başına 3-5 hisse olduğu için tek bir aykırı değer (ör. F/K 107) ortalamayı
    tamamen bozar; medyan bu çarpıklığa dayanıklıdır.
    """
    sector: str
    stock_count: int
    median_pe: Optional[float] = None
    median_pb: Optional[float] = None
    median_roe: Optional[float] = None
    median_dividend_yield: Optional[float] = None
    avg_change_pct: Optional[float] = None      # bugünkü ortalama fiyat değişimi
    total_market_cap: Optional[float] = None
    katilim_compliant_count: int = 0


class StockSectorComparison(BaseModel):
    """Bir hissenin kendi sektör medyanına göre konumu."""
    sector: Optional[str] = None
    stock_count: int = 0
    pe_ratio: Optional[float] = None
    sector_median_pe: Optional[float] = None
    pb_ratio: Optional[float] = None
    sector_median_pb: Optional[float] = None
    roe: Optional[float] = None
    sector_median_roe: Optional[float] = None
    dividend_yield: Optional[float] = None
    sector_median_dividend_yield: Optional[float] = None
    verdict: Optional[str] = None               # "Sektöre göre ucuz" vb.


class TechnicalSignalItem(BaseModel):
    symbol: str
    company_name: str
    signal_type: str        # GOLDEN_CROSS, RSI_OVERSOLD, VOLUME_SPIKE, ...
    direction: str          # AL | SAT | DIKKAT
    title: str
    detail: str
    price: float


class PortfolioRiskResponse(BaseModel):
    """
    Portföy risk metrikleri (Matriks Prime'ın "portföy optimizasyonu" karşılığı).

    NOT — FAİZSİZ FİNANS KURALI: klasik Sharpe oranı risksiz FAİZ oranı
    kullanır. road_map.md bu projede faiz mantığını yasakladığı için Sharpe
    yerine `return_risk_ratio` hesaplanır: yıllık getiri / yıllık volatilite.
    Aynı soruyu (birim risk başına ne kadar getiri) faiz kullanmadan yanıtlar.
    """
    day_count: int                                  # hesaba giren gün sayısı
    annualized_return_pct: Optional[float] = None
    annualized_volatility_pct: Optional[float] = None   # yıllıklandırılmış std sapma
    max_drawdown_pct: Optional[float] = None            # zirveden dibe en büyük düşüş
    max_drawdown_date: Optional[date] = None
    return_risk_ratio: Optional[float] = None
    beta_vs_index: Optional[float] = None               # BIST 100'e göre duyarlılık
    best_day_pct: Optional[float] = None
    worst_day_pct: Optional[float] = None
    positive_day_ratio: Optional[float] = None          # kaç gün artıda kapandı (%)
    risk_label: Optional[str] = None                    # "Düşük" / "Orta" / "Yüksek"
    message: Optional[str] = None                       # veri yetersizse açıklama


class FinancialPeriodItem(BaseModel):
    """Tek bir çeyreğin finansal özeti (tutarlar TL)."""
    period_end: date
    period_label: str                     # "2026/Q1" gibi okunur etiket
    revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_income: Optional[float] = None
    ebitda: Optional[float] = None
    net_income: Optional[float] = None
    total_assets: Optional[float] = None
    total_equity: Optional[float] = None
    total_debt: Optional[float] = None
    operating_cashflow: Optional[float] = None
    # Bir önceki YILIN aynı çeyreğine göre büyüme (%). Çeyrekler mevsimsellik
    # taşıdığı için önceki çeyrekle değil, geçen yılın aynı çeyreğiyle kıyaslanır.
    revenue_yoy_pct: Optional[float] = None
    net_income_yoy_pct: Optional[float] = None
    net_margin_pct: Optional[float] = None


class FinancialStatementsResponse(BaseModel):
    symbol: str
    company_name: str
    currency: str = "TRY"
    periods: List[FinancialPeriodItem]


class MarketQuoteItem(BaseModel):
    """Döviz/altın referans serisi — son kapanış ve değişimler."""
    symbol: str
    label: str
    price: float
    change_1d_pct: Optional[float] = None
    change_30d_pct: Optional[float] = None
    as_of: Optional[date] = None


class BenchmarkPoint(BaseModel):
    date: date
    portfolio_value: float
    portfolio_index: float          # ilk gün = 100 olacak sekilde normalize
    benchmark_index: Optional[float] = None


class PortfolioBenchmarkResponse(BaseModel):
    """
    Portföy getirisinin BIST 100 ile kıyaslaması.

    İki seri de ilk güne 100 verilerek normalize edilir; aksi halde 80.000
    puanlık endeksle 100.000 TL'lik portföyü aynı grafikte kıyaslamak
    anlamsız olurdu. Böylece "endeksi yendim mi?" sorusu tek bakışta yanıtlanır.
    """
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    portfolio_return_pct: Optional[float] = None
    benchmark_return_pct: Optional[float] = None
    excess_return_pct: Optional[float] = None    # portfoy - endeks (pozitifse endeks yenildi)
    points: List[BenchmarkPoint]


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
    katilim_status: Optional[str] = None  # UYGUN | UYGUN_DEGIL | BELIRSIZ
    latest_price: Optional[FundPriceResponse]

class IpoResponse(BaseModel):
    id: int
    company_name: str
    symbol: Optional[str]
    offer_price: Optional[float]
    demand_collection_dates: Optional[str]
    is_katilim_compliant: bool
    katilim_status: Optional[str] = None  # UYGUN | UYGUN_DEGIL | BELIRSIZ
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

class StockVoteRequest(BaseModel):
    """Kullanıcının hisse beklenti oyu. Literal ile geçersiz değerler şema düzeyinde reddedilir."""
    direction: Literal["UP", "DOWN"]


class StockVoteResponse(BaseModel):
    """
    Hisse bazlı topluluk beklenti anketi sonucu (road_map.md #6).

    Yorum tabanlı `CommunitySentimentResponse`'tan bağımsızdır: orası yazılmış
    yorumların metin analizinden gelir, burası tek tıkla verilen doğrudan oydur.
    """
    symbol: str
    up_count: int
    down_count: int
    total_votes: int
    up_pct: float
    down_pct: float
    # Giriş yapmış kullanıcının kendi oyu ('UP'/'DOWN'), hiç oy vermediyse None.
    user_vote: Optional[str] = None


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
    order_type: str = Field(..., pattern="^(LIMIT_BUY|LIMIT_SELL|SCHEDULED_BUY|STOP_LOSS_SELL)$")
    quantity: float = Field(..., gt=0, le=10_000_000, allow_inf_nan=False)
    target_price: Optional[float] = Field(None, gt=0, le=1_000_000, allow_inf_nan=False)
    execution_time: Optional[datetime] = None

    @model_validator(mode="after")
    def _validate_type_specific_fields(self):
        # STOP_LOSS_SELL de fiyat şartlı bir emirdir: hedef fiyat zorunludur.
        if self.order_type in ("LIMIT_BUY", "LIMIT_SELL", "STOP_LOSS_SELL"):
            if self.target_price is None:
                raise ValueError("Fiyat şartlı emirler için target_price zorunludur.")
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
    katilim_status: Optional[str] = None  # UYGUN | UYGUN_DEGIL | BELIRSIZ
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    roe: Optional[float] = None
    piotroski_score: Optional[int] = None
    altman_z_score: Optional[float] = None
    debt_to_equity: Optional[float] = None
    net_margin: Optional[float] = None
    dividend_yield: Optional[float] = None      # yıllık temettü verimi (%)
    target_upside_pct: Optional[float] = None   # analist hedef fiyatına göre potansiyel (%)


class WatchlistItemResponse(BaseModel):
    symbol: str
    company_name: str
    current_price: float
    price_change_pct: Optional[float] = None
    is_katilim_compliant: bool
    katilim_status: Optional[str] = None  # UYGUN | UYGUN_DEGIL | BELIRSIZ
    purification_rate: float
    target_price: Optional[float] = None
    note: Optional[str] = None
    # Güncel fiyatın hedefe uzaklığı (%). Hedef yoksa None.
    distance_to_target_pct: Optional[float] = None
    added_at: datetime

    @field_serializer("added_at")
    def _serialize_added_at(self, value: datetime) -> Optional[str]:
        return _utc_iso(value)


class WatchlistUpdateRequest(BaseModel):
    """İzleme listesi kaydına hedef fiyat / not yazar. Alan gönderilmezse değişmez."""
    target_price: Optional[float] = Field(None, gt=0, le=1_000_000, allow_inf_nan=False)
    note: Optional[str] = Field(None, max_length=280)
    # Hedefi/notu TEMİZLEMEK için: alanı null göndermek "değiştirme" demek olduğu
    # için ayrı bir bayrak gerekiyor.
    clear_target: bool = False
    clear_note: bool = False


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


# --- Web Push abonelikleri -------------------------------------------------
class PushSubscribeRequest(BaseModel):
    """Tarayıcının PushSubscription nesnesinden çıkarılan üç alan."""
    endpoint: str = Field(..., max_length=1000)
    p256dh: str = Field(..., max_length=200)
    auth: str = Field(..., max_length=100)


class PushStatusResponse(BaseModel):
    configured: bool
    public_key: Optional[str] = None
    device_count: int = 0
