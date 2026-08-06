import os
import re
import pandas as pd
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from fastapi import FastAPI, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import nh3

import models
from database import engine, get_db, begin_write_transaction, SessionLocal
from schemas import (
    UserCreate, UserResponse, Token, LoginRequest,
    StockResponse, StockDetailResponse, StockPriceResponse,
    TradeRequest, PortfolioResponse, PortfolioItemResponse,
    BotLogResponse, BotPerformancePoint, LeaderboardItem,
    StockProResponse, KatilimInfoResponse, CompanyAnalysisResponse,
    InsiderTradeResponse, KapNotificationResponse, FundResponse, FundPriceResponse,
    IpoResponse, StockCommentCreate, StockCommentResponse, CommunitySentimentResponse,
    DividendGoalRequest, DcaBacktestRequest, BalanceUpdateRequest, UserBotResponse, UserBotSettingsRequest,
    PendingOrderCreate, PendingOrderUpdate, PendingOrderResponse, StockNewsItem,
    PivotLevelsResponse, ForeignHoldingTrendResponse, EarningsCalendarItem,
    NotificationPreferenceRequest, NotificationPreferenceResponse, NotificationResponse, UnreadCountResponse,
    WatchlistItemResponse, ScreenerItemResponse,
)
from auth import (
    get_password_hash, verify_password, create_access_token, get_current_user
)
from scheduler import start_scheduler
from init_db import init_database
from bot import (
    calculate_technical_indicators, get_strategy_config, BOT_STRATEGY_CONFIG,
    get_risk_mode_config, RISK_MODE_CONFIG, DEFAULT_RISK_MODE,
)
from kap_client import fetch_kap_disclosures, get_kap_search_url
from market_hours import get_market_status_dict, is_market_open
from analysis_engine import (
    calculate_deep_analysis, calculate_dividend_goal, calculate_dca_backtest, AnalysisFetchError,
    calculate_pivot_levels, get_foreign_holding_trend,
)
from insider_client import fetch_insider_trades, get_recent_insider_buys
from sentiment import score_sentiment
from yfinance_client import fetch_stock_news
from cache import get_cached_news, set_cached_news
from constants import EXTREME_CHANGE_GUARD_PCT

def _rate_limit_key(request: Request) -> str:
    """
    Rate limiti mümkün olduğunda kullanıcı bazlı (JWT 'sub' claim'i), aksi halde
    istemci IP adresine göre uygular. Böylece aynı IP arkasındaki farklı
    kullanıcılar birbirini rate-limit'e takmaz, ama IP bazlı spam de engellenir.
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        try:
            import jwt as _jwt
            from auth import SECRET_KEY, ALGORITHM
            payload = _jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
            if username:
                return f"user:{username}"
        except Exception:
            pass
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key)

app = FastAPI(title="BIST Simülasyonu & AI Trader API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Production CORS Hardening ---
# Geliştirme ortamında (FRONTEND_URL / NEXT_PUBLIC_FRONTEND_URL tanımlı değilse) yerel
# origin'lere izin verilir. Üretimde (Render) ise SADECE Vercel'deki frontend origin'i
# kabul edilir. Wildcard ('*') KASITLI OLARAK desteklenmez: allow_credentials=True ile
# wildcard birlikte kullanılırsa tarayıcılar isteği zaten reddeder ve herhangi bir
# origin'in kimlik doğrulamalı isteği taklit etmesine izin vermiş oluruz.
_frontend_url = os.environ.get("FRONTEND_URL") or os.environ.get("NEXT_PUBLIC_FRONTEND_URL")
_allowed_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
if _frontend_url:
    _allowed_origins.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Uygulama başlarken tablo/veri kontrolü + APScheduler
@app.on_event("startup")
def startup_event():
    # Render gibi ortamlarda bist_app.db her deploy'da boş/yok olabilir (repo'da .gitignore
    # ile tutulmuyor). init_database() idempotent'tir: create_all() var olan tabloları
    # bozmaz, seed adımları zaten var olan kayıtları atlar — bu yüzden her başlangıçta
    # güvenle çağrılabilir. Scheduler'ın cache doldurma adımı 'stocks' tablosunu
    # sorguladığı için bu çağrı start_scheduler()'dan ÖNCE tamamlanmış olmalı.
    from yf_retry import configure_yfinance
    configure_yfinance()
    init_database()
    start_scheduler()

# --- AUTHENTICATION ---

@app.post("/api/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if username or email already exists
    if db.query(models.User).filter_by(username=user_data.username).first():
        raise HTTPException(status_code=400, detail="Bu kullanıcı adı zaten alınmış.")
    if db.query(models.User).filter_by(email=user_data.email).first():
        raise HTTPException(status_code=400, detail="Bu e-posta adresi zaten kullanımda.")

    # KVKK & Sorumluluk Reddi: Onay zorunlu
    if not user_data.terms_accepted:
        raise HTTPException(
            status_code=400,
            detail="Kullanıcı sözleşmesi, KVKK Aydınlatma Metni ve Sorumluluk Reddi Feragatnamesi'ni onaylamak zorunludur."
        )
        
    hashed_password = get_password_hash(user_data.password)
    new_user = models.User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        virtual_balance=100000.00,
        is_bot=False,
        terms_accepted=True,
        terms_accepted_at=datetime.utcnow(),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Her yeni kullanıcı için kişisel AI Bot otomatik oluşturulur (100.000 TL başlangıç bakiyesi, 1 Günlük varsayılan strateji)
    now = datetime.utcnow()
    default_config = get_strategy_config("1D")
    db.add(models.UserBot(
        user_id=new_user.id,
        bot_name=f"{new_user.username} — Kişisel AI Bot",
        virtual_balance=100000.00,
        is_active=True,
        risk_profile=DEFAULT_RISK_MODE,
        time_frame="1D",
        started_at=now,
        ends_at=now + default_config["duration"],
    ))
    db.commit()

    return new_user

@app.post("/api/auth/login", response_model=Token)
def login(login_data: LoginRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(username=login_data.username).first()
    if not user or user.is_bot or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Hatalı kullanıcı adı veya şifre.")

    access_token = create_access_token(subject=user.username)

    # Giriş olayı kritik olmayan bir kayıttır; yanıtı geciktirmemesi için
    # (ve login isteğinin scheduler/diğer yazma işlemleriyle DB kilidi için
    # yarışmaması için) response döndükten SONRA ayrı bir session ile loglanır.
    background_tasks.add_task(_log_user_action_background, user.id, "LOGIN", "Kullanıcı giriş yaptı")

    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me", response_model=UserResponse)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user


# --- MARKET STATUS ---

@app.get("/api/market/status")
def market_status():
    """
    BİST borsa durumunu döndürür.
    Geri dönen: is_open, reason, current_time_tr, weekday
    """
    return get_market_status_dict()


# --- YÜKSEK GÜVENLİKLİ YARDIMCI FONKSİYON ---

def _log_user_action(
    db: Session,
    user_id: int,
    action: str,
    details: str = "",
    ip_address: str = None
):
    """
    Kullanıcı hareket logı yazar.
    Hata oluştursa bile ana işlemi durdurmaz.
    """
    try:
        log_entry = models.UserLog(
            user_id=user_id,
            action=action,
            details=details,
            ip_address=ip_address,
            created_at=datetime.utcnow()
        )
        db.add(log_entry)
        db.flush()  # commit öncesi yaz, ana transaction ile birlikte
    except Exception as e:
        print(f"[UserLog] Log yazılamıyor ({action}): {e}")


def _log_user_action_background(user_id: int, action: str, details: str = ""):
    """
    _log_user_action'ın BackgroundTasks ile çağrılan sürümü: kendi DB session'ını
    açar, kaydı yazıp commit eder ve kapatır. İstek/yanıt döngüsünü bloklamaz.
    """
    db = SessionLocal()
    try:
        db.add(models.UserLog(
            user_id=user_id,
            action=action,
            details=details,
            created_at=datetime.utcnow(),
        ))
        db.commit()
    except Exception as e:
        print(f"[UserLog] Log yazılamıyor ({action}): {e}")
        db.rollback()
    finally:
        db.close()


# --- FİYAT DEĞERLEME YARDIMCISI ---
#
# Portföy/liderlik/bot değerleme hesaplarının TAMAMI veritabanındaki son kayıtlı fiyatı
# (stock_last_recorded_price_in_db) kullanır. RAM önbelleği (cache.py) yalnızca YENİ fiyat
# YAZMAK için (scheduler tarafında, is_market_open() guard'ı altında) kullanılır; borsa
# kapalıyken hiçbir arka plan görevi yeni fiyat yazmadığından DB'deki son fiyat -ve dolayısıyla
# tüm değerlemeler- Cuma 18:15 kapanışında donmuş kalır. Bu, aynı anda birden fazla worker
# çalışsa bile (RAM cache process-local olduğu için) tutarlı, tek doğruluk kaynağı sağlar.
def _get_latest_db_price(db: Session, stock_id: int) -> float:
    latest_record = (
        db.query(models.StockPrice)
        .filter_by(stock_id=stock_id)
        .order_by(models.StockPrice.recorded_at.desc())
        .first()
    )
    return float(latest_record.price) if latest_record else 0.0


# --- STOCKS ---

def _bulk_price_and_change(db: Session, stock_ids: List[int]) -> Dict[int, tuple]:
    """
    Verilen hisse id'leri için {stock_id: (current_price, price_change_pct)} döner.
    Günlük % değişim = (güncel fiyat - ÖNCEKİ İŞ GÜNÜNÜN KAPANIŞI) / o kapanış
    (Midas/Yahoo Finance ile aynı mantık) — get_stocks() ve /api/watchlist arasında
    paylaşılır ki aynı hesap iki yerde ayrı ayrı yazılıp birbirinden sapmasın.

    Referans kapanış önceliği:
      1) stocks.previous_close — Yahoo'nun (fast_info) resmi referansı, scheduler
         her fiyat güncellemesinde tazeler. BİST'in tedbir/taban-tavan referans
         fiyatı kurallarını doğru yansıtır (bkz. GUNDG: kendi türetmemiz -%18.9
         derken Yahoo'nun resmi taban referansı -%9.96'ydı).
      2) stock_prices_daily'den türetilen "son geçerli günlük bar" (Yahoo referansı
         henüz çekilmemişse — örn. ilk deploy sonrası ya da yeni eklenen hisse).
      3) İki ardışık tik farkı (ikisi de yoksa).
    """
    if not stock_ids:
        return {}

    yahoo_prev_close_map = {
        stock_id: float(prev_close)
        for stock_id, prev_close in db.query(models.Stock.id, models.Stock.previous_close)
        .filter(models.Stock.id.in_(stock_ids), models.Stock.previous_close.isnot(None))
        .all()
    }

    today = date.today()
    latest_daily_subq = (
        db.query(
            models.StockPriceDaily.stock_id,
            func.max(models.StockPriceDaily.trade_date).label("max_date"),
        )
        .filter(models.StockPriceDaily.stock_id.in_(stock_ids), models.StockPriceDaily.trade_date < today)
        .group_by(models.StockPriceDaily.stock_id)
        .subquery()
    )
    prev_close_rows = (
        db.query(models.StockPriceDaily.stock_id, models.StockPriceDaily.close)
        .join(
            latest_daily_subq,
            (models.StockPriceDaily.stock_id == latest_daily_subq.c.stock_id)
            & (models.StockPriceDaily.trade_date == latest_daily_subq.c.max_date),
        )
        .all()
    )
    prev_close_map = {stock_id: float(close) for stock_id, close in prev_close_rows}

    # Her hisse için en son 2 tik: [0]=güncel, [1]=bir önceki (prev_close yoksa fallback için).
    # stock_prices tablosu süresiz büyüdüğü için ".filter(stock_id.in_(...))" + Python'da
    # ilk 2'yi almak TÜM geçmişi çekip belleğe yığar (ciddi performans riski); bunun yerine
    # DB tarafında ROW_NUMBER() ile hisse başına en yeni 2 satır seçilir.
    row_num = func.row_number().over(
        partition_by=models.StockPrice.stock_id,
        order_by=models.StockPrice.recorded_at.desc(),
    ).label("rn")
    ranked_subq = (
        db.query(
            models.StockPrice.stock_id,
            models.StockPrice.price,
        )
        .filter(models.StockPrice.stock_id.in_(stock_ids))
        .add_columns(row_num)
        .subquery()
    )
    latest_two_rows = (
        db.query(ranked_subq.c.stock_id, ranked_subq.c.price)
        .filter(ranked_subq.c.rn <= 2)
        .order_by(ranked_subq.c.stock_id, ranked_subq.c.rn)
        .all()
    )
    ticks_by_stock: Dict[int, list] = {}
    for stock_id, price in latest_two_rows:
        ticks_by_stock.setdefault(stock_id, []).append(price)

    result: Dict[int, tuple] = {}
    for stock_id in stock_ids:
        ticks = ticks_by_stock.get(stock_id, [])
        if not ticks:
            result[stock_id] = (0.0, None)
            continue

        current_price = float(ticks[0])
        price_change_pct: Optional[float] = None
        prev_close = yahoo_prev_close_map.get(stock_id) or prev_close_map.get(stock_id)
        if prev_close and prev_close > 0:
            price_change_pct = ((current_price - prev_close) / prev_close) * 100
        elif len(ticks) > 1 and float(ticks[1]) > 0:
            # stock_prices_daily'de henüz kaydı olmayan (yeni eklenmiş/backfill
            # bekleyen) hisseler için eski tik-tik davranışına düş (0'dan iyidir).
            prev_tick_price = float(ticks[1])
            price_change_pct = ((current_price - prev_tick_price) / prev_tick_price) * 100

        # Sermaye artırımı/bedelsiz/bölünme gibi kurumsal işlemler referans fiyatı
        # tek seferde katlarca değiştirebiliyor (bkz. KTLEV: 156→44 TL, gerçek bir
        # kayıp değil, pay sayısı artışı). BİST'in normal devre kesici sınırları
        # bunu asla üretmez; bu yüzden %50'yi aşan sıçramalar güvenilmez kabul edilip
        # yanlış "-71%" gibi bir rakam göstermek yerine None (bilgi yok) döndürülür.
        if price_change_pct is not None and abs(price_change_pct) > EXTREME_CHANGE_GUARD_PCT:
            price_change_pct = None

        result[stock_id] = (current_price, price_change_pct)

    return result


@app.get("/api/stocks", response_model=List[StockResponse])
def get_stocks(db: Session = Depends(get_db)):
    stocks = db.query(models.Stock).filter_by(is_active=True).all()
    price_map = _bulk_price_and_change(db, [s.id for s in stocks])

    response = []
    for stock in stocks:
        current_price, price_change_pct = price_map.get(stock.id, (0.0, None))
        response.append({
            "id": stock.id,
            "symbol": stock.symbol,
            "company_name": stock.company_name,
            "is_active": stock.is_active,
            "sector": stock.sector,
            "current_price": round(current_price, 2),
            "price_change_pct": round(price_change_pct, 2) if price_change_pct is not None else None,
            "is_katilim_compliant": bool(stock.is_katilim_compliant),
            "purification_rate": float(stock.purification_rate or 0.0)
        })

    return response


SCREENER_SORT_FIELDS = {
    "price_change_pct": lambda item: item.price_change_pct,
    "pe_ratio": lambda item: item.pe_ratio,
    "pb_ratio": lambda item: item.pb_ratio,
    "roe": lambda item: item.roe,
    "piotroski_score": lambda item: item.piotroski_score,
    "current_price": lambda item: item.current_price,
}


@app.get("/api/screener", response_model=List[ScreenerItemResponse])
def get_screener(
    db: Session = Depends(get_db),
    sector: Optional[str] = None,
    katilim_only: bool = False,
    min_pe: Optional[float] = None,
    max_pe: Optional[float] = None,
    min_pb: Optional[float] = None,
    max_pb: Optional[float] = None,
    min_roe: Optional[float] = None,
    min_piotroski: Optional[int] = None,
    sort_by: str = "price_change_pct",
    order: str = "desc",
):
    """
    Hisse Tarayıcı: finansal oran filtreleriyle (F/K, PD/DD, ROE, Piotroski skoru,
    sektör, Katılım uygunluğu) BİST hisselerini filtreleyip sıralar (Midas'ın
    "hisse tarayıcı" özelliğinin eşdeğeri). company_analysis'i olmayan (henüz
    analiz edilmemiş) hisseler filtre uygulanmadıysa listede kalır, filtre
    uygulanmışsa (o alan None olduğu için) elenir.
    """
    query = db.query(models.Stock).filter_by(is_active=True)
    if sector:
        query = query.filter(models.Stock.sector == sector)
    if katilim_only:
        query = query.filter(models.Stock.is_katilim_compliant.is_(True))
    stocks = query.all()

    price_map = _bulk_price_and_change(db, [s.id for s in stocks])
    analysis_rows = (
        db.query(models.CompanyAnalysis)
        .filter(models.CompanyAnalysis.stock_id.in_([s.id for s in stocks]))
        .all()
    )
    analysis_by_stock = {row.stock_id: row for row in analysis_rows}

    items = []
    for stock in stocks:
        current_price, price_change_pct = price_map.get(stock.id, (0.0, None))
        analysis = analysis_by_stock.get(stock.id)

        pe_ratio = float(analysis.pe_ratio) if analysis and analysis.pe_ratio is not None else None
        pb_ratio = float(analysis.pb_ratio) if analysis and analysis.pb_ratio is not None else None
        roe = float(analysis.roe) if analysis and analysis.roe is not None else None
        piotroski_score = analysis.piotroski_score if analysis else None

        if min_pe is not None and (pe_ratio is None or pe_ratio < min_pe):
            continue
        if max_pe is not None and (pe_ratio is None or pe_ratio > max_pe):
            continue
        if min_pb is not None and (pb_ratio is None or pb_ratio < min_pb):
            continue
        if max_pb is not None and (pb_ratio is None or pb_ratio > max_pb):
            continue
        if min_roe is not None and (roe is None or roe < min_roe):
            continue
        if min_piotroski is not None and (piotroski_score is None or piotroski_score < min_piotroski):
            continue

        items.append(ScreenerItemResponse(
            symbol=stock.symbol,
            company_name=stock.company_name,
            sector=stock.sector,
            current_price=round(current_price, 2),
            price_change_pct=round(price_change_pct, 2) if price_change_pct is not None else None,
            is_katilim_compliant=bool(stock.is_katilim_compliant),
            pe_ratio=pe_ratio,
            pb_ratio=pb_ratio,
            roe=roe,
            piotroski_score=piotroski_score,
            altman_z_score=float(analysis.altman_z_score) if analysis and analysis.altman_z_score is not None else None,
            debt_to_equity=float(analysis.debt_to_equity) if analysis and analysis.debt_to_equity is not None else None,
            net_margin=float(analysis.net_margin) if analysis and analysis.net_margin is not None else None,
        ))

    # Sıralanan alanı olan/olmayanları ayırıp yalnızca doluları sıralıyoruz; None
    # değerler (yön ne olursa olsun) her zaman listenin sonuna düşer.
    sort_key = SCREENER_SORT_FIELDS.get(sort_by, SCREENER_SORT_FIELDS["price_change_pct"])
    with_value = [i for i in items if sort_key(i) is not None]
    without_value = [i for i in items if sort_key(i) is None]
    with_value.sort(key=sort_key, reverse=(order != "asc"))

    return with_value + without_value


@app.get("/api/stocks/{symbol}", response_model=StockDetailResponse)
def get_stock_detail(symbol: str, db: Session = Depends(get_db)):
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")
        
    # Fetch last 100 prices for chart & indicator calculations.
    # DESC + limit, sonra kronolojik sıraya çevir — asc + limit toplam kayıt
    # 100'ü geçtiğinde en ESKİ 100 kaydı döndürüyordu (grafik/indikatörler
    # donmuş, güncel olmayan veriyle hesaplanıyordu).
    price_records = db.query(models.StockPrice)\
        .filter_by(stock_id=stock.id)\
        .order_by(models.StockPrice.recorded_at.desc())\
        .limit(100)\
        .all()
    price_records.reverse()
        
    if not price_records:
        raise HTTPException(status_code=400, detail="Bu hisseye ait fiyat verisi bulunmamaktadır.")
        
    # Latest price — DB'deki son kayıttan (borsa kapalıyken Cuma kapanışında donuk kalır)
    current_price = _get_latest_db_price(db, stock.id) or float(price_records[-1].price)

    # Önceki kapanış: önce Yahoo'nun resmi referansı (stocks.previous_close), yoksa
    # stock_prices_daily'deki bugünden ÖNCEKİ en son gün (bkz. _bulk_price_and_change
    # docstring'indeki öncelik sırası ve GUNDG örneği).
    today = date.today()
    if stock.previous_close is not None:
        previous_close = float(stock.previous_close)
    else:
        prev_close_row = (
            db.query(models.StockPriceDaily)
            .filter(models.StockPriceDaily.stock_id == stock.id, models.StockPriceDaily.trade_date < today)
            .order_by(models.StockPriceDaily.trade_date.desc())
            .first()
        )
        previous_close = float(prev_close_row.close) if prev_close_row else None
    change_pct = (
        round(((current_price - previous_close) / previous_close) * 100, 2)
        if previous_close and previous_close > 0
        else None
    )
    # Kurumsal işlem (bedelsiz/bölünme) sonrası yanlış sıçrama göstermemek için
    # aynı koruma (bkz. get_stocks() ve EXTREME_CHANGE_GUARD_PCT).
    if change_pct is not None and abs(change_pct) > EXTREME_CHANGE_GUARD_PCT:
        change_pct = None

    # Bugünün açılışı ve gün içi yüksek/düşük: bugüne ait gün-içi tiklerden.
    today_start = datetime.combine(today, datetime.min.time())
    today_ticks = [p for p in price_records if p.recorded_at >= today_start]
    open_price = float(today_ticks[0].price) if today_ticks else None
    day_high = max((float(p.price) for p in today_ticks), default=None)
    day_low = min((float(p.price) for p in today_ticks), default=None)

    # Calculate indicators
    df_data = {
        "price": [float(p.price) for p in price_records],
        "recorded_at": [p.recorded_at for p in price_records]
    }
    df = pd.DataFrame(df_data)
    df = calculate_technical_indicators(df)
    
    last_row = df.iloc[-1]
    indicators = {
        "rsi": round(float(last_row["rsi"]), 2),
        "macd": round(float(last_row["macd"]), 2),
        "macd_signal": round(float(last_row["macd_signal"]), 2),
        "sma_short": round(float(last_row["sma_short"]), 2),
        "sma_long": round(float(last_row["sma_long"]), 2),
        "bb_high": round(float(last_row["bb_high"]), 2),
        "bb_low": round(float(last_row["bb_low"]), 2)
    }
    
    # Format prices for response (return last 30 for the chart to keep it clean)
    prices_response = [
        StockPriceResponse(price=float(p.price), volume=p.volume, recorded_at=p.recorded_at)
        for p in price_records[-30:]
    ]
    
    return StockDetailResponse(
        id=stock.id,
        symbol=stock.symbol,
        company_name=stock.company_name,
        current_price=round(current_price, 2),
        prices=prices_response,
        indicators=indicators,
        previous_close=round(previous_close, 2) if previous_close is not None else None,
        open_price=round(open_price, 2) if open_price is not None else None,
        day_high=round(day_high, 2) if day_high is not None else None,
        day_low=round(day_low, 2) if day_low is not None else None,
        change_pct=change_pct,
    )


# Aralık kodu -> kaç gün geriye gidileceği (1D hariç, o intraday tablosundan gelir)
HISTORY_RANGE_DAYS = {"1W": 7, "1M": 31, "1Y": 366, "5Y": 1827}


@app.get("/api/stocks/{symbol}/history", response_model=List[StockPriceResponse])
def get_stock_history(symbol: str, range: str = "1D", db: Session = Depends(get_db)):
    """
    Hisse detay grafiği için zaman aralığına göre fiyat serisi döner (Midas
    benzeri 1G/1H/1A/1Y/5Y seçici). 1D dışındaki tüm aralıklar günlük OHLCV
    tablosundan (stock_prices_daily) gelir — bkz. daily_history.py.
    """
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    range_code = range.upper()

    if range_code == "1D":
        records = db.query(models.StockPrice)\
            .filter_by(stock_id=stock.id)\
            .order_by(models.StockPrice.recorded_at.desc())\
            .limit(100)\
            .all()
        records.reverse()
        return [
            StockPriceResponse(price=float(r.price), volume=r.volume, recorded_at=r.recorded_at)
            for r in records
        ]

    days = HISTORY_RANGE_DAYS.get(range_code)
    if days is None:
        raise HTTPException(status_code=400, detail="Geçersiz aralık. 1D, 1W, 1M, 1Y veya 5Y kullanın.")

    cutoff = date.today() - timedelta(days=days)
    daily_records = db.query(models.StockPriceDaily)\
        .filter(models.StockPriceDaily.stock_id == stock.id, models.StockPriceDaily.trade_date >= cutoff)\
        .order_by(models.StockPriceDaily.trade_date.asc())\
        .all()

    return [
        StockPriceResponse(
            price=float(r.close),
            volume=r.volume,
            recorded_at=datetime.combine(r.trade_date, datetime.min.time()),
        )
        for r in daily_records
    ]


# --- KAP DISCLOSURES ---

@app.get("/api/stocks/{symbol}/kap-disclosures")
def get_kap_disclosures(symbol: str, db: Session = Depends(get_db)):
    """
    Fetches public KAP (Kamuoyunu Aydınlatma Platformu) disclosures for a given stock symbol.
    Returns recent public disclosures (major shareholder changes, special situations, etc.)
    """
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")
    
    disclosures = fetch_kap_disclosures(symbol.upper())
    kap_url = get_kap_search_url(symbol.upper())
    
    return {
        "symbol": symbol.upper(),
        "company_name": stock.company_name,
        "kap_url": kap_url,
        "disclosures": disclosures
    }


# --- HİSSE HABERLERİ (Yahoo Finance / yfinance) ---

_news_executor = ThreadPoolExecutor(max_workers=4)


@app.get("/api/stocks/{symbol}/news", response_model=List[StockNewsItem])
def get_stock_news(symbol: str, db: Session = Depends(get_db)):
    """
    Hisseyle ilgili son haberleri döner. Ana kaynak: scheduler'ın günde bir kez
    (24 saatlik döngüyle, bkz. scheduler.py refresh_stock_news_job) doldurduğu
    stock_news tablosu — bu sayede haberler kalıcı olarak loglanmış olur ve her
    gün eski kayıtlar silinip yenileriyle değiştirilir. Tablo henüz boşsa (ör.
    scheduler ilk çalışmasını yapmadan önce ya da yeni eklenen bir hisse için)
    canlı yfinance çağrısına düşülür ve sonuç 20 dakika RAM önbelleğinde tutulur.
    """
    symbol = symbol.upper()
    stock = db.query(models.Stock).filter_by(symbol=symbol, is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    stored = (
        db.query(models.StockNews)
        .filter_by(stock_id=stock.id)
        .order_by(models.StockNews.fetched_at.desc())
        .all()
    )
    if stored:
        return [
            StockNewsItem(
                title=n.title,
                summary=n.summary,
                source=n.source,
                url=n.url,
                published_at=n.published_at,
                thumbnail=n.thumbnail,
            )
            for n in stored
        ]

    cached = get_cached_news(symbol)
    if cached is not None:
        return cached

    try:
        future = _news_executor.submit(fetch_stock_news, symbol, 8)
        news_items = future.result(timeout=5)
    except FutureTimeoutError:
        news_items = []
    except Exception:
        news_items = []

    set_cached_news(symbol, news_items)
    return news_items


# --- DERİN BİLANÇO ANALİZİ / HELAL FİNANS ANALİZİ ---

@app.get("/api/stocks/{symbol}/analysis", response_model=StockProResponse)
def get_stock_analysis(symbol: str, db: Session = Depends(get_db)):
    """
    Katılım Endeksi (Helal Finans) uygunluğu ve Derin Bilanço Analizi verilerini
    (Piotroski skoru, F/K, PD/DD, makul değer) döndürür.
    """
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    return StockProResponse(
        symbol=stock.symbol,
        company_name=stock.company_name,
        katilim=KatilimInfoResponse(
            is_katilim_compliant=bool(stock.is_katilim_compliant),
            purification_rate=float(stock.purification_rate or 0.0),
            non_compliance_reason=stock.non_compliance_reason
        ),
        analysis=CompanyAnalysisResponse.model_validate(stock.analysis) if stock.analysis else None
    )


def _run_analysis_refresh(symbol: str, db: Session) -> CompanyAnalysisResponse:
    """Ortak tazeleme mantığı: yfinance'tan çeker, company_analysis'i günceller, hataları ayrıştırır."""
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail=f"'{symbol.upper()}' sembolü bulunamadı.")

    try:
        analysis = calculate_deep_analysis(db, symbol.upper())
    except AnalysisFetchError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        db.rollback()
        print(f"[Analysis] Beklenmeyen hata ({symbol}): {e}")
        raise HTTPException(status_code=500, detail=f"Analiz hesaplanırken beklenmeyen bir hata oluştu: {e}")

    if not analysis:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı veya analiz hesaplanamadı.")

    return CompanyAnalysisResponse.model_validate(analysis)


@app.post("/api/analysis/{symbol}/refresh", response_model=CompanyAnalysisResponse)
@limiter.limit("5/minute")
def refresh_analysis(request: Request, symbol: str, db: Session = Depends(get_db)):
    """
    Derin Bilanço Analizi'ni (Piotroski skoru, F/K, Graham makul değeri, sektör F/K,
    ROE/kâr marjları) yfinance'tan yeniden hesaplayıp company_analysis tablosuna yazar.
    yfinance'a hiç ulaşılamazsa 502, beklenmeyen bir hata olursa 500 döner — sessizce
    başarılı görünmez.
    """
    return _run_analysis_refresh(symbol, db)


@app.post("/api/stocks/{symbol}/analysis/refresh", response_model=CompanyAnalysisResponse)
@limiter.limit("5/minute")
def refresh_stock_analysis(request: Request, symbol: str, db: Session = Depends(get_db)):
    """Geriye dönük uyumluluk için korunan eski uç nokta; /api/analysis/{symbol}/refresh ile aynı mantığı kullanır."""
    return _run_analysis_refresh(symbol, db)


_pivot_cache: Dict[str, Dict[str, Any]] = {}
_PIVOT_CACHE_TTL_SECONDS = 15 * 60  # 15 dakika — günde bir kez değişen bir veri için yeterli


@app.get("/api/stocks/{symbol}/pivot-levels", response_model=PivotLevelsResponse)
def get_pivot_levels(symbol: str, db: Session = Depends(get_db)):
    """
    Klasik Pivot Noktaları (P, R1-R3, S1-S3) ve Fibonacci geri çekilme seviyelerini
    (%23.6/%38.2/%50/%61.8) döner. Bir önceki tam işlem gününün Yüksek/Düşük/Kapanış
    verisinden hesaplanır; sonuçlar 15 dakika önbelleklenir.
    """
    symbol = symbol.upper()
    stock = db.query(models.Stock).filter_by(symbol=symbol, is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    cached = _pivot_cache.get(symbol)
    if cached and (datetime.utcnow() - cached["cached_at"]).total_seconds() < _PIVOT_CACHE_TTL_SECONDS:
        return cached["data"]

    data = calculate_pivot_levels(symbol)
    _pivot_cache[symbol] = {"data": data, "cached_at": datetime.utcnow()}
    return data


@app.get("/api/stocks/{symbol}/foreign-holding-trend", response_model=ForeignHoldingTrendResponse)
def get_foreign_holding_trend_endpoint(symbol: str, db: Session = Depends(get_db)):
    """
    Yabancı/kurumsal sahiplik oranının 30 ve 90 günlük değişimini döner. Veri, her
    "Analizi Tazele" çağrısında kaydedilen günlük anlık görüntülerden (bkz.
    ForeignHoldingSnapshot) hesaplanır; yeterli geçmiş birikmediyse available=false
    ve açıklayıcı bir mesajla döner.
    """
    symbol = symbol.upper()
    stock = db.query(models.Stock).filter_by(symbol=symbol, is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")
    return get_foreign_holding_trend(db, symbol)


@app.get("/api/stocks/{symbol}/insider-trades", response_model=List[InsiderTradeResponse])
def get_insider_trades(symbol: str, db: Session = Depends(get_db)):
    """İçeriden öğrenenlerin (yönetici/patron) alım-satım hareketlerini döner."""
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    fetch_insider_trades(db, symbol.upper())  # KAP'tan tazele (best-effort)
    trades = get_recent_insider_buys(db, stock.id, days=90)
    return [
        InsiderTradeResponse(
            id=t.id, symbol=t.symbol, title_person=t.title_person,
            trade_type=t.trade_type, quantity=float(t.quantity),
            price=float(t.price), trade_date=t.trade_date
        ) for t in trades
    ]


@app.post("/api/stocks/{symbol}/dividend-goal")
def get_dividend_goal(symbol: str, req: DividendGoalRequest, db: Session = Depends(get_db)):
    """Hedeflenen aylık pasif gelire ulaşmak için gereken lot sayısı ve sermayeyi hesaplar."""
    result = calculate_dividend_goal(db, symbol.upper(), req.target_monthly_income)
    if result is None:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")
    return result


@app.post("/api/stocks/{symbol}/dca-backtest")
def get_dca_backtest(symbol: str, req: DcaBacktestRequest, db: Session = Depends(get_db)):
    """Düzenli (aylık sabit tutar) yatırım stratejisinin geçmiş performansını simüle eder."""
    result = calculate_dca_backtest(db, symbol.upper(), req.monthly_amount, req.months)
    if result is None:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")
    return result


# --- TOPLULUK YORUMLARI & DUYARLILIK ---

@app.get("/api/stocks/{symbol}/comments", response_model=List[StockCommentResponse])
def get_stock_comments(symbol: str, db: Session = Depends(get_db)):
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    comments = (
        db.query(models.StockComment)
        .filter_by(stock_id=stock.id)
        .order_by(models.StockComment.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        StockCommentResponse(
            id=c.id, username=c.user.username, comment_text=c.comment_text,
            sentiment_score=float(c.sentiment_score) if c.sentiment_score is not None else None,
            created_at=c.created_at
        ) for c in comments
    ]


@app.post("/api/stocks/{symbol}/comments", response_model=StockCommentResponse, status_code=status.HTTP_201_CREATED)
def post_stock_comment(
    symbol: str, payload: StockCommentCreate,
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)
):
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    # XSS Koruması: HTML/script içeriği DB'ye yazılmadan önce tamamen ayıklanır
    # (React zaten metni escape eder, ancak DB katmanında da savunma derinliği sağlanır).
    clean_text = nh3.clean(payload.comment_text, tags=set())

    sentiment = score_sentiment(clean_text)
    comment = models.StockComment(
        user_id=current_user.id,
        stock_id=stock.id,
        comment_text=clean_text,
        sentiment_score=sentiment,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return StockCommentResponse(
        id=comment.id, username=current_user.username, comment_text=comment.comment_text,
        sentiment_score=sentiment, created_at=comment.created_at
    )


@app.get("/api/stocks/{symbol}/sentiment", response_model=CommunitySentimentResponse)
def get_community_sentiment(symbol: str, db: Session = Depends(get_db)):
    """Topluluk yorumlarını toplulaştırıp 'Topluluk Hissede Boğa (%78 Olumlu)' benzeri özet üretir."""
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    comments = db.query(models.StockComment).filter_by(stock_id=stock.id).all()
    scores = [float(c.sentiment_score) for c in comments if c.sentiment_score is not None]

    from sentiment import aggregate_sentiment
    agg = aggregate_sentiment(scores)

    if not scores:
        verdict = "Henüz yeterli yorum yok."
    elif agg["positive_pct"] >= 55:
        verdict = f"Topluluk Hissede Boğa (%{agg['positive_pct']:.0f} Olumlu)"
    elif agg["negative_pct"] >= 55:
        verdict = f"Topluluk Hissede Ayı (%{agg['negative_pct']:.0f} Olumsuz)"
    else:
        verdict = "Topluluk Kararsız / Nötr"

    return CommunitySentimentResponse(
        symbol=symbol.upper(),
        total_comments=len(comments),
        positive_pct=agg["positive_pct"],
        negative_pct=agg["negative_pct"],
        neutral_pct=agg["neutral_pct"],
        verdict_text=verdict,
    )


# --- KAP GENEL HABER AKIŞI ---

@app.get("/api/earnings-calendar", response_model=List[EarningsCalendarItem])
def get_earnings_calendar(db: Session = Depends(get_db)):
    """
    Yaklaşan (bugün dahil, gelecekteki) çeyreklik bilanço açıklama tarihi bilinen
    aktif hisseleri, tarihe göre artan sırada döner. Tarih bilgisi scheduler
    tarafından günlük olarak (refresh_earnings_calendar) yfinance'tan tazelenir.
    """
    today = date.today()
    rows = (
        db.query(models.Stock, models.CompanyAnalysis)
        .join(models.CompanyAnalysis, models.CompanyAnalysis.stock_id == models.Stock.id)
        .filter(models.Stock.is_active == True, models.CompanyAnalysis.next_earnings_date >= today)
        .order_by(models.CompanyAnalysis.next_earnings_date.asc())
        .all()
    )
    return [
        EarningsCalendarItem(
            symbol=stock.symbol,
            company_name=stock.company_name,
            next_earnings_date=analysis.next_earnings_date,
        )
        for stock, analysis in rows
    ]


@app.get("/api/kap/news", response_model=List[KapNotificationResponse])
def get_kap_news(db: Session = Depends(get_db)):
    """
    Takip edilen tüm hisseler için genel KAP bildirim akışını döner (en yeni 30).
    Canlı KAP taraması burada YAPILMAZ — ~40 hisse için art arda dış API çağrısı
    isteği dakikalarca bloklayıp zaman aşımına uğratıyordu. Tazeleme artık
    scheduler.py üzerinden arka planda periyodik olarak yapılır.
    """
    notifications = (
        db.query(models.KapNotification)
        .order_by(models.KapNotification.publish_date.desc())
        .limit(30)
        .all()
    )
    return notifications


# Büyük yatırımcı/pay sahipliği değişikliği bildirimlerini tespit etmek için kullanılan
# başlık anahtar kelimeleri. KAP'ın genel bildirim akışı yalnızca başlık/özet metnini
# içerdiğinden (bildirimin detay sayfasındaki yatırımcı adı/pay oranı tablosu ayrıca
# çekilmiyor), bu basit anahtar kelime eşleşmesiyle "hangi hissede önemli bir pay
# sahipliği değişikliği oldu" bilgisini yakalıyoruz — kullanıcı detay için KAP linkine yönlendirilir.
_MAJOR_HOLDER_KEYWORDS = [
    "pay sahip", "oy hak", "sermaye piyasası araçlarının sahip", "hakim ortak", "hakimiyet",
]


@app.get("/api/kap/major-holder-news", response_model=List[KapNotificationResponse])
def get_major_holder_news(db: Session = Depends(get_db)):
    """
    Genel KAP akışından, başlığında pay sahipliği/oy hakları değişikliğine işaret eden
    anahtar kelimeler geçen bildirimleri (büyük yatırımcı hareketleri) filtreler.
    """
    notifications = (
        db.query(models.KapNotification)
        .order_by(models.KapNotification.publish_date.desc())
        .limit(300)
        .all()
    )
    filtered = [
        n for n in notifications
        if any(kw in n.title.lower() for kw in _MAJOR_HOLDER_KEYWORDS)
    ]
    return filtered[:30]


# --- TEFAS FONLARI ---

@app.get("/api/funds", response_model=List[FundResponse])
def get_funds(katilim_only: bool = False, db: Session = Depends(get_db)):
    query = db.query(models.Fund)
    if katilim_only:
        query = query.filter_by(is_katilim_compliant=True)
    funds = query.all()

    response = []
    for fund in funds:
        latest = (
            db.query(models.FundPrice)
            .filter_by(fund_id=fund.id)
            .order_by(models.FundPrice.recorded_date.desc())
            .first()
        )
        response.append(FundResponse(
            code=fund.code,
            name=fund.name,
            fund_type=fund.fund_type,
            risk_level=fund.risk_level,
            is_katilim_compliant=bool(fund.is_katilim_compliant),
            latest_price=FundPriceResponse.model_validate(latest) if latest else None
        ))
    return response


# --- HALKA ARZLAR (IPO) ---

@app.get("/api/ipos", response_model=List[IpoResponse])
def get_ipos(db: Session = Depends(get_db)):
    return db.query(models.Ipo).order_by(models.Ipo.id.desc()).all()


# --- PORTFOLIO & TRADING ---

@app.get("/api/portfolio", response_model=PortfolioResponse)
def get_portfolio(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    portfolios = db.query(models.Portfolio).filter_by(user_id=current_user.id, is_bot_portfolio=False).all()

    items = []
    total_stock_value = 0.0

    for item in portfolios:
        stock = item.stock
        # Total Value = virtual_balance + sum(quantity * stock_last_recorded_price_in_db)
        current_price = _get_latest_db_price(db, stock.id)

        qty = float(item.quantity)
        avg_cost = float(item.average_cost)
        current_value = qty * current_price
        total_stock_value += current_value
        
        profit_loss_pct = 0.0
        if avg_cost > 0:
            profit_loss_pct = ((current_price - avg_cost) / avg_cost) * 100
            
        items.append(PortfolioItemResponse(
            symbol=stock.symbol,
            company_name=stock.company_name,
            quantity=qty,
            average_cost=round(avg_cost, 2),
            current_price=round(current_price, 2),
            current_value=round(current_value, 2),
            profit_loss_pct=round(profit_loss_pct, 2),
            opened_at=item.opened_at,
            updated_at=item.updated_at,
        ))
        
    total_portfolio_value = float(current_user.virtual_balance) + total_stock_value

    # Toplam K/Z, sabit 100.000 TL yerine kullanıcının referans sermayesine
    # (baseline_value) göre hesaplanır — bkz. models.py:User.baseline_value.
    baseline = float(current_user.baseline_value or 100000.0)
    overall_profit_loss_pct = ((total_portfolio_value - baseline) / baseline) * 100 if baseline else 0.0

    return PortfolioResponse(
        balance=round(float(current_user.virtual_balance), 2),
        total_portfolio_value=round(total_portfolio_value, 2),
        baseline_value=round(baseline, 2),
        profit_loss_pct=round(overall_profit_loss_pct, 2),
        items=items
    )

@app.post("/api/trade")
@limiter.limit("10/minute")
def execute_trade(request: Request, trade: TradeRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # ── Sıkı Borsa Saatleri Guard'ı ─────────────────────────────────────────
    # Hafta sonu ya da seans dışı saatlerde (10:00-18:15 dışı) HİÇBİR manuel
    # alım/satım emri kabul edilmez — fiyatlar donuk olduğu için işlem yapılamaz.
    open_flag, market_reason = is_market_open()
    if not open_flag:
        raise HTTPException(
            status_code=400,
            detail="Borsa şu an kapalı. Hafta sonu ve seans dışı saatlerde alım-satım işlemi yapılamaz."
        )
    # ─────────────────────────────────────────────────────────────────────────

    action = trade.action_type.upper()
    if action not in ("AL", "SAT"):
        raise HTTPException(status_code=400, detail="Geçersiz işlem tipi. 'AL' veya 'SAT' olmalı.")

    stock = db.query(models.Stock).filter_by(symbol=trade.symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    # ── Atomik İşlem Bloğu (Anti-Double-Spending) ───────────────────────────
    # BEGIN IMMEDIATE ile SQLite üzerinde yazma kilidi hemen alınır; aynı kullanıcı
    # için eşzamanlı iki alım/satım isteği birbirinin üzerine yazamaz (race condition
    # önlenir). İşlem başarısız olursa ROLLBACK ile bakiye/portföy tutarlılığı korunur.
    db.rollback()  # varsa açık implicit transaction'ı temizle
    begin_write_transaction(db)
    try:
        # Kullanıcıyı IMMEDIATE yazma kilidi altında (aynı transaction içinde) tekrar oku —
        # eşzamanlı ikinci bir istek bu satıra erişemeden bu transaction'ın bitmesini bekler.
        current_user = db.query(models.User).filter_by(id=current_user.id).first()

        # Get current price — DB'deki son kayıttan (tek doğruluk kaynağı)
        current_price = _get_latest_db_price(db, stock.id)
        if not current_price:
            raise HTTPException(status_code=400, detail="Hisse fiyatı bulunamadı.")

        total_cost = trade.quantity * current_price
        portfolio_entry = db.query(models.Portfolio).filter_by(
            user_id=current_user.id, stock_id=stock.id, is_bot_portfolio=False
        ).first()

        if action == "AL":
            if float(current_user.virtual_balance) < total_cost:
                raise HTTPException(status_code=400, detail="Yetersiz sanal bakiye.")

            current_user.virtual_balance = float(current_user.virtual_balance) - total_cost

            if portfolio_entry:
                old_qty = float(portfolio_entry.quantity)
                old_cost = float(portfolio_entry.average_cost)
                new_qty = old_qty + trade.quantity
                new_avg_cost = ((old_qty * old_cost) + total_cost) / new_qty
                portfolio_entry.quantity = new_qty
                portfolio_entry.average_cost = new_avg_cost
            else:
                new_entry = models.Portfolio(
                    user_id=current_user.id,
                    stock_id=stock.id,
                    quantity=trade.quantity,
                    average_cost=current_price,
                    is_bot_portfolio=False,
                )
                db.add(new_entry)

            db.commit()
            return {"message": f"{trade.quantity} adet {stock.symbol} başarıyla alındı.", "balance": current_user.virtual_balance}

        else:  # SAT
            if not portfolio_entry or float(portfolio_entry.quantity) < trade.quantity:
                raise HTTPException(status_code=400, detail="Yetersiz hisse miktarı.")

            revenue = trade.quantity * current_price
            current_user.virtual_balance = float(current_user.virtual_balance) + revenue

            remaining_qty = float(portfolio_entry.quantity) - trade.quantity
            # Decimal->float dönüşümü + float çıkarma "tam sıfır" yerine 1e-13 gibi bir
            # kalıntı üretebilir; == 0 karşılaştırması bu durumda pozisyonu silmeyip
            # "hayalet" (neredeyse sıfır ama sıfır değil) bir kayıt bırakır. orders.py'deki
            # eşdeğer kod (_execute_single_order) zaten <= 0 kullanıyor, burada da aynısı.
            if remaining_qty <= 0:
                db.delete(portfolio_entry)
            else:
                portfolio_entry.quantity = remaining_qty

            db.commit()
            return {"message": f"{trade.quantity} adet {stock.symbol} başarıyla satıldı.", "balance": current_user.virtual_balance}
    except Exception:
        db.rollback()
        raise
    # ─────────────────────────────────────────────────────────────────────────


# --- BEKLEYEN EMİRLER (LİMİT / ZAMANLI ALIM-SATIM) ---
#
# Bu emirler yalnızca kullanıcının kendi manuel bakiyesi/portföyü üzerinde çalışır
# (is_bot_portfolio=False) — AI bot'un bakiyesi/pozisyonları tamamen ayrı olduğu
# için botla veri çakışması yoktur. Gerçekleştirme, scheduler.py -> orders.py
# üzerinden borsa açıkken otomatik yapılır (bkz. process_pending_orders).

@app.post("/api/orders", response_model=PendingOrderResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def create_pending_order(
    request: Request,
    order: PendingOrderCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Yeni bir LIMIT_BUY / LIMIT_SELL / SCHEDULED_BUY emri oluşturur.
    Borsa kapalıyken de emir bırakılabilir (emir borsa açıldığında değerlendirilir);
    yalnızca GERÇEKLEŞTİRME borsa açık saatlerle sınırlıdır.
    """
    stock = db.query(models.Stock).filter_by(symbol=order.symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    new_order = models.PendingOrder(
        user_id=current_user.id,
        stock_id=stock.id,
        order_type=order.order_type,
        target_price=order.target_price,
        execution_time=order.execution_time.replace(tzinfo=None) if order.execution_time else None,
        quantity=order.quantity,
        status="PENDING",
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    _log_user_action(
        db, current_user.id, "ORDER_CREATE",
        f"{order.order_type} emri oluşturuldu: {stock.symbol} x{order.quantity}"
    )
    db.commit()

    return PendingOrderResponse(
        id=new_order.id, symbol=stock.symbol, order_type=new_order.order_type,
        quantity=float(new_order.quantity),
        target_price=float(new_order.target_price) if new_order.target_price is not None else None,
        execution_time=new_order.execution_time, status=new_order.status,
        fail_reason=new_order.fail_reason, created_at=new_order.created_at,
        executed_at=new_order.executed_at,
    )


@app.get("/api/orders", response_model=List[PendingOrderResponse])
def list_pending_orders(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Giriş yapan kullanıcının tüm emirlerini (bekleyen + geçmiş) en yeniden eskiye döner."""
    orders = (
        db.query(models.PendingOrder)
        .filter_by(user_id=current_user.id)
        .order_by(models.PendingOrder.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        PendingOrderResponse(
            id=o.id, symbol=o.stock.symbol, order_type=o.order_type,
            quantity=float(o.quantity),
            target_price=float(o.target_price) if o.target_price is not None else None,
            execution_time=o.execution_time, status=o.status,
            fail_reason=o.fail_reason, created_at=o.created_at, executed_at=o.executed_at,
        ) for o in orders
    ]


@app.put("/api/orders/{order_id}", response_model=PendingOrderResponse)
@limiter.limit("15/minute")
def update_pending_order(
    request: Request,
    order_id: int,
    req: PendingOrderUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Yalnızca kendi PENDING durumundaki bir emrin adet/hedef fiyat/zamanlamasını
    günceller. Yalnızca gönderilen (None olmayan) alanlar değiştirilir; emir
    türüne uygun olmayan bir alan (ör. LIMIT emrine execution_time) sessizce
    yok sayılır.
    """
    db.rollback()
    begin_write_transaction(db)
    try:
        order = db.query(models.PendingOrder).filter_by(
            id=order_id, user_id=current_user.id
        ).first()
        if not order:
            db.rollback()
            raise HTTPException(status_code=404, detail="Emir bulunamadı.")
        if order.status != "PENDING":
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Yalnızca bekleyen (PENDING) emirler güncellenebilir. Bu emrin durumu: {order.status}")

        if req.quantity is not None:
            order.quantity = req.quantity
        if req.target_price is not None and order.order_type in ("LIMIT_BUY", "LIMIT_SELL"):
            order.target_price = req.target_price
        if req.execution_time is not None and order.order_type == "SCHEDULED_BUY":
            order.execution_time = req.execution_time.replace(tzinfo=None)

        db.commit()
        db.refresh(order)

        _log_user_action(db, current_user.id, "ORDER_UPDATE", f"Emir #{order.id} güncellendi.")
        db.commit()

        return PendingOrderResponse(
            id=order.id, symbol=order.stock.symbol, order_type=order.order_type,
            quantity=float(order.quantity),
            target_price=float(order.target_price) if order.target_price is not None else None,
            execution_time=order.execution_time, status=order.status,
            fail_reason=order.fail_reason, created_at=order.created_at,
            executed_at=order.executed_at,
        )
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise


@app.delete("/api/orders/{order_id}")
def cancel_pending_order(
    order_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Yalnızca kendi PENDING durumundaki bir emri iptal edebilir (JWT'den çözülen kullanıcı)."""
    db.rollback()
    begin_write_transaction(db)
    try:
        order = db.query(models.PendingOrder).filter_by(
            id=order_id, user_id=current_user.id
        ).first()
        if not order:
            db.rollback()
            raise HTTPException(status_code=404, detail="Emir bulunamadı.")
        if order.status != "PENDING":
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Yalnızca bekleyen (PENDING) emirler iptal edilebilir. Bu emrin durumu: {order.status}")

        order.status = "CANCELLED"
        order.executed_at = datetime.utcnow()
        db.commit()
        return {"message": "Emir iptal edildi.", "order_id": order.id}
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise


# --- KİŞİYE ÖZEL BİLDİRİM & ALARM SİSTEMİ ---

@app.get("/api/stocks/{symbol}/notification-preference", response_model=Optional[NotificationPreferenceResponse])
def get_notification_preference(
    symbol: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Giriş yapan kullanıcının bu hisse için bıraktığı alarm tercihini döner (yoksa null)."""
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    pref = db.query(models.StockNotificationPreference).filter_by(user_id=current_user.id, stock_id=stock.id).first()
    if not pref:
        return None

    return NotificationPreferenceResponse(
        stock_symbol=stock.symbol,
        price_above=float(pref.price_above) if pref.price_above is not None else None,
        price_below=float(pref.price_below) if pref.price_below is not None else None,
        pct_change_trigger=float(pref.pct_change_trigger) if pref.pct_change_trigger is not None else None,
        notify_kap=bool(pref.notify_kap),
        notify_ai_signal=bool(pref.notify_ai_signal),
    )


@app.post("/api/stocks/{symbol}/notification-preference", response_model=NotificationPreferenceResponse)
def upsert_notification_preference(
    symbol: str,
    req: NotificationPreferenceRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Kullanıcının bu hisse için alarm tercihini oluşturur/günceller. Fiyat üstü/altı
    alanları tetiklenince otomatik sıfırlanır (bkz. notifications.py); burada
    gönderilen değer her zaman yeni bir aktif alarm olarak kaydedilir.
    """
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    pref = db.query(models.StockNotificationPreference).filter_by(user_id=current_user.id, stock_id=stock.id).first()
    if not pref:
        pref = models.StockNotificationPreference(user_id=current_user.id, stock_id=stock.id)
        db.add(pref)

    pref.price_above = req.price_above
    pref.price_below = req.price_below
    pref.pct_change_trigger = req.pct_change_trigger
    pref.notify_kap = req.notify_kap
    pref.notify_ai_signal = req.notify_ai_signal
    db.commit()
    db.refresh(pref)

    _log_user_action(db, current_user.id, "NOTIFICATION_PREF_UPDATE", f"{stock.symbol} için alarm tercihi güncellendi.")
    db.commit()

    return NotificationPreferenceResponse(
        stock_symbol=stock.symbol,
        price_above=float(pref.price_above) if pref.price_above is not None else None,
        price_below=float(pref.price_below) if pref.price_below is not None else None,
        pct_change_trigger=float(pref.pct_change_trigger) if pref.pct_change_trigger is not None else None,
        notify_kap=bool(pref.notify_kap),
        notify_ai_signal=bool(pref.notify_ai_signal),
    )


@app.delete("/api/stocks/{symbol}/notification-preference")
def delete_notification_preference(
    symbol: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kullanıcının bu hisse için tüm alarm tercihini kaldırır."""
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    pref = db.query(models.StockNotificationPreference).filter_by(user_id=current_user.id, stock_id=stock.id).first()
    if pref:
        db.delete(pref)
        db.commit()
    return {"message": f"{stock.symbol} için alarm tercihi kaldırıldı."}


@app.get("/api/notifications", response_model=List[NotificationResponse])
def list_notifications(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Giriş yapan kullanıcının son 50 bildirimini en yeniden eskiye döner."""
    notifications = (
        db.query(models.Notification)
        .filter_by(user_id=current_user.id)
        .order_by(models.Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        NotificationResponse(
            id=n.id,
            stock_symbol=n.stock.symbol if n.stock else None,
            notif_type=n.notif_type,
            title=n.title,
            message=n.message,
            is_read=bool(n.is_read),
            created_at=n.created_at,
        ) for n in notifications
    ]


@app.get("/api/notifications/unread-count", response_model=UnreadCountResponse)
def get_unread_notification_count(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Navbar'daki bildirim ziline kırmızı badge sayısı için okunmamış bildirim sayısını döner."""
    count = (
        db.query(models.Notification)
        .filter_by(user_id=current_user.id, is_read=False)
        .count()
    )
    return UnreadCountResponse(count=count)


@app.post("/api/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Tek bir bildirimi okundu olarak işaretler."""
    notif = db.query(models.Notification).filter_by(id=notification_id, user_id=current_user.id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Bildirim bulunamadı.")
    notif.is_read = True
    db.commit()
    return {"message": "Bildirim okundu olarak işaretlendi."}


@app.post("/api/notifications/read-all")
def mark_all_notifications_read(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kullanıcının tüm okunmamış bildirimlerini okundu olarak işaretler."""
    (
        db.query(models.Notification)
        .filter_by(user_id=current_user.id, is_read=False)
        .update({"is_read": True})
    )
    db.commit()
    return {"message": "Tüm bildirimler okundu olarak işaretlendi."}


# --- WATCHLIST (FAVORİLER) ---

@app.get("/api/watchlist", response_model=List[WatchlistItemResponse])
def get_watchlist(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kullanıcının izleme listesindeki hisseleri güncel fiyat/değişim bilgisiyle döner."""
    rows = (
        db.query(models.Watchlist)
        .filter_by(user_id=current_user.id)
        .order_by(models.Watchlist.created_at.desc())
        .all()
    )
    if not rows:
        return []

    stock_by_id = {r.stock.id: r.stock for r in rows}
    price_map = _bulk_price_and_change(db, list(stock_by_id.keys()))

    items = []
    for row in rows:
        stock = stock_by_id[row.stock.id]
        current_price, price_change_pct = price_map.get(stock.id, (0.0, None))
        items.append(WatchlistItemResponse(
            symbol=stock.symbol,
            company_name=stock.company_name,
            current_price=round(current_price, 2),
            price_change_pct=round(price_change_pct, 2) if price_change_pct is not None else None,
            is_katilim_compliant=bool(stock.is_katilim_compliant),
            purification_rate=float(stock.purification_rate or 0.0),
            added_at=row.created_at,
        ))
    return items


@app.post("/api/watchlist/{symbol}", status_code=status.HTTP_201_CREATED)
def add_to_watchlist(
    symbol: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bir hisseyi kullanıcının izleme listesine ekler (zaten ekliyse no-op)."""
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    existing = db.query(models.Watchlist).filter_by(user_id=current_user.id, stock_id=stock.id).first()
    if existing:
        return {"message": f"{stock.symbol} zaten izleme listenizde."}

    db.add(models.Watchlist(user_id=current_user.id, stock_id=stock.id))
    db.commit()
    return {"message": f"{stock.symbol} izleme listenize eklendi."}


@app.delete("/api/watchlist/{symbol}")
def remove_from_watchlist(
    symbol: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bir hisseyi kullanıcının izleme listesinden çıkarır."""
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper()).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    deleted = (
        db.query(models.Watchlist)
        .filter_by(user_id=current_user.id, stock_id=stock.id)
        .delete(synchronize_session=False)
    )
    db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Bu hisse izleme listenizde değil.")
    return {"message": f"{stock.symbol} izleme listenizden çıkarıldı."}


# --- AI BOT DATA ---

def _build_bot_performance_series(db: Session, owner_user_id: int) -> Dict[str, List[Any]]:
    """Bot (paylaşımlı demo ya da kişisel) vs BİST100 (basit ortalama) karşılaştırma serisini üretir."""
    perf = db.query(models.BotPerformanceHistory)\
        .filter_by(user_id=owner_user_id)\
        .order_by(models.BotPerformanceHistory.recorded_date.asc())\
        .all()

    bot_points = []
    bist100_points = []

    if perf:
        start_date = perf[0].recorded_date
        stocks = db.query(models.Stock).filter_by(is_active=True).all()

        start_prices = {}
        for stock in stocks:
            sp = db.query(models.StockPrice)\
                .filter(models.StockPrice.stock_id == stock.id, models.StockPrice.recorded_at <= datetime.combine(start_date, datetime.max.time()))\
                .order_by(models.StockPrice.recorded_at.desc())\
                .first()
            if sp:
                start_prices[stock.symbol] = float(sp.price)

        for point in perf:
            d = point.recorded_date
            bot_val = float(point.total_portfolio_value)
            bot_points.append({"date": d.isoformat(), "value": bot_val})

            returns = []
            for stock in stocks:
                s_price = start_prices.get(stock.symbol)
                if s_price:
                    cp_rec = db.query(models.StockPrice)\
                        .filter(models.StockPrice.stock_id == stock.id, models.StockPrice.recorded_at <= datetime.combine(d, datetime.max.time()))\
                        .order_by(models.StockPrice.recorded_at.desc())\
                        .first()
                    if cp_rec:
                        cp = float(cp_rec.price)
                        returns.append(cp / s_price)

            avg_return = sum(returns) / len(returns) if returns else 1.0
            bist100_val = 100000.0 * avg_return
            bist100_points.append({"date": d.isoformat(), "value": round(bist100_val, 2)})
    else:
        today_str = date.today().isoformat()
        bot_points = [{"date": today_str, "value": 100000.00}]
        bist100_points = [{"date": today_str, "value": 100000.00}]

    return {"bot": bot_points, "bist100": bist100_points}


def _compute_actor_bot_stats(
    db: Session, owner_user_id: int, is_bot_portfolio: bool, virtual_balance: float,
    baseline_value: float = 100000.0, since: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Bir bot aktörünün (paylaşımlı demo bot ya da kişisel bot) işlem sayısı, win rate ve
    getirisini hesaplar. baseline_value, getiri (%) hesabının referans sermayesidir —
    sabit 100.000 TL yerine kullanılır ki manuel bakiye eklemeleri getiriyi şişirmesin.
    since verilirse yalnızca o tarihten sonraki işlemler sayılır (performans sıfırlama sonrası).
    """
    log_query = db.query(models.BotLog).filter_by(user_id=owner_user_id)
    if since is not None:
        log_query = log_query.filter(models.BotLog.created_at >= since)
    logs = log_query.all()
    total_trades = len(logs)

    win_trades = 0
    sell_trades = 0
    for log in logs:
        if log.action_type == "SAT":
            sell_trades += 1
            reason = log.reason_text or ""
            # Alt dize kontrolü ("%0" içeriyor mu) yanlış pozitifler üretiyordu: "%0.03" veya
            # "%0.99" gibi hafif KÂRLI işlemler de "%0" alt dizesini içerdiği için win_trades'e
            # hiç eklenmiyordu — win rate olduğundan düşük görünüyordu. Gerçek sayısal değeri
            # regex ile ayrıştırıp > 0 kontrolü yapmak doğru olan.
            match = re.search(r"Kâr/Zarar:\s*%(-?\d+\.?\d*)", reason)
            if match and float(match.group(1)) > 0:
                win_trades += 1

    win_rate = (win_trades / sell_trades * 100) if sell_trades > 0 else 0.0

    # Total Value = virtual_balance + sum(quantity * stock_last_recorded_price_in_db)
    portfolios = db.query(models.Portfolio).filter_by(user_id=owner_user_id, is_bot_portfolio=is_bot_portfolio).all()
    total_stock_value = 0.0
    for item in portfolios:
        price = _get_latest_db_price(db, item.stock_id) or float(item.average_cost)
        total_stock_value += float(item.quantity) * price

    current_value = virtual_balance + total_stock_value
    total_return_pct = ((current_value - baseline_value) / baseline_value) * 100 if baseline_value else 0.0

    return {
        "total_trades": total_trades,
        "win_rate": round(win_rate, 2),
        "total_return_pct": round(total_return_pct, 2),
        "portfolio_value": round(current_value, 2),
    }


# --- KİŞİSEL AI BOT & BAKİYE YÖNETİMİ ---

@app.post("/api/user/balance")
@limiter.limit("3/minute")
def update_user_balance(
    request: Request,
    req: BalanceUpdateRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Giriş yapan kullanıcının kendi manuel sanal bakiyesini ayarlar/sıfırlar (yalnızca JWT'den çözülen kullanıcı)."""
    db.rollback()
    begin_write_transaction(db)
    try:
        user_row = db.query(models.User).filter_by(id=current_user.id).first()
        # Bakiyedeki değişim kadar referans sermayeyi (baseline_value) de kaydır ki
        # eklenen/çekilen nakit "Toplam Getiri" yüzdesine kâr/zarar gibi yansımasın
        # (bkz. update_user_bot_balance'taki aynı mantık).
        delta = float(req.new_balance) - float(user_row.virtual_balance)
        user_row.baseline_value = float(user_row.baseline_value or 100000.0) + delta
        user_row.virtual_balance = req.new_balance
        _log_user_action(db, user_row.id, "BALANCE_UPDATE", f"Kullanıcı bakiyesi {req.new_balance} TL olarak güncellendi.")
        db.commit()
        return {"message": "Bakiyeniz güncellendi.", "virtual_balance": float(user_row.virtual_balance)}
    except Exception:
        db.rollback()
        raise


@app.post("/api/user/bot/balance")
@limiter.limit("3/minute")
def update_user_bot_balance(
    request: Request,
    req: BalanceUpdateRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Giriş yapan kullanıcının kişisel AI botunun sanal bakiyesini ayarlar/sıfırlar (yalnızca kendi botu)."""
    db.rollback()
    begin_write_transaction(db)
    try:
        user_bot = db.query(models.UserBot).filter_by(user_id=current_user.id).first()
        if not user_bot:
            raise HTTPException(status_code=404, detail="Kişisel AI Bot bulunamadı.")

        # Bakiyedeki değişim kadar referans sermayeyi (baseline_value) de kaydır ki eklenen/
        # çekilen nakit "Toplam Getiri" yüzdesine kâr/zarar gibi yansımasın — yalnızca
        # piyasa hareketinden gelen kâr/zarar % olarak görünmeye devam eder.
        delta = float(req.new_balance) - float(user_bot.virtual_balance)
        user_bot.baseline_value = float(user_bot.baseline_value or 100000.0) + delta
        user_bot.virtual_balance = req.new_balance
        _log_user_action(db, current_user.id, "BOT_BALANCE_UPDATE", f"Kişisel bot bakiyesi {req.new_balance} TL olarak güncellendi.")
        db.commit()
        return {"message": "Kişisel botunuzun bakiyesi güncellendi.", "virtual_balance": float(user_bot.virtual_balance)}
    except Exception:
        db.rollback()
        raise


@app.get("/api/user/bot", response_model=UserBotResponse)
def get_user_bot_status(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Giriş yapan kullanıcının kişisel AI botunun durumunu (bakiye, win rate, getiri) döner."""
    user_bot = db.query(models.UserBot).filter_by(user_id=current_user.id).first()
    if not user_bot:
        raise HTTPException(status_code=404, detail="Kişisel AI Bot bulunamadı.")

    stats = _compute_actor_bot_stats(
        db, current_user.id, True, float(user_bot.virtual_balance),
        baseline_value=float(user_bot.baseline_value or 100000.0),
        since=user_bot.performance_reset_at,
    )
    time_frame = user_bot.time_frame or "1D"
    config = get_strategy_config(time_frame)
    risk_config = get_risk_mode_config(user_bot.risk_profile)

    remaining_seconds = None
    if user_bot.ends_at:
        remaining_seconds = max(0, int((user_bot.ends_at - datetime.utcnow()).total_seconds()))

    return UserBotResponse(
        bot_name=user_bot.bot_name,
        virtual_balance=round(float(user_bot.virtual_balance), 2),
        is_active=bool(user_bot.is_active),
        risk_mode=user_bot.risk_profile if user_bot.risk_profile in RISK_MODE_CONFIG else DEFAULT_RISK_MODE,
        risk_mode_label=risk_config["label"],
        time_frame=time_frame,
        time_frame_label=config["label"],
        started_at=user_bot.started_at,
        ends_at=user_bot.ends_at,
        remaining_seconds=remaining_seconds,
        portfolio_value=stats["portfolio_value"],
        total_return_pct=stats["total_return_pct"],
        total_trades=stats["total_trades"],
        win_rate=stats["win_rate"],
    )


@app.post("/api/user/bot/settings", response_model=UserBotResponse)
def update_user_bot_settings(
    req: UserBotSettingsRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Kişisel botun zaman dilimini (1D/1W/1M), risk modunu (slow/normal/aggressive) ve
    aktiflik durumunu günceller. Zaman dilimi değiştirildiğinde ya da bot yeniden aktif
    edildiğinde süre (started_at/ends_at) sıfırdan başlatılır. Risk modu değişikliği
    süreyi etkilemez — yalnızca bir sonraki işlem döngüsünden itibaren geçerli olur.

    Bot AKTİF'ten PASİF'e alındığında (kullanıcı onayından sonra çağrılır — onay
    frontend'de gösterilir): açık pozisyonlar piyasa fiyatından kapatılır ve performans
    (bakiye, referans sermaye, işlem geçmişi istatistikleri) 100.000 TL'ye sıfırlanır;
    böylece botu tekrar başlattığında temiz bir sayfadan başlar.
    """
    user_bot = db.query(models.UserBot).filter_by(user_id=current_user.id).first()
    if not user_bot:
        raise HTTPException(status_code=404, detail="Kişisel AI Bot bulunamadı.")

    was_active = bool(user_bot.is_active)

    if req.time_frame and req.time_frame != user_bot.time_frame:
        user_bot.time_frame = req.time_frame
        config = get_strategy_config(req.time_frame)
        user_bot.started_at = datetime.utcnow()
        user_bot.ends_at = datetime.utcnow() + config["duration"]

    if req.risk_mode and req.risk_mode != user_bot.risk_profile:
        user_bot.risk_profile = req.risk_mode

    if req.is_active is not None:
        if was_active and not req.is_active:
            # Bot durduruluyor: açık pozisyonları piyasa fiyatından kapat, performansı sıfırla
            open_positions = db.query(models.Portfolio).filter_by(
                user_id=current_user.id, is_bot_portfolio=True
            ).all()
            liquidation_time = datetime.utcnow()
            for pos in open_positions:
                price = _get_latest_db_price(db, pos.stock_id)
                if price:
                    revenue = float(pos.quantity) * price
                    user_bot.virtual_balance = float(user_bot.virtual_balance) + revenue
                    db.add(models.BotLog(
                        user_id=current_user.id, stock_id=pos.stock_id,
                        action_type="SAT", price=price, quantity=pos.quantity,
                        reason_text="Bot durduruldu; açık pozisyon piyasa fiyatından kapatıldı.",
                        created_at=liquidation_time,
                    ))
                db.delete(pos)

            user_bot.virtual_balance = 100000.00
            user_bot.baseline_value = 100000.00
            # performance_reset_at, kapanış (liquidation_time) loglarından SONRAKİ bir an olmalı
            # ki bu kapanış işlemleri "sıfırlama sonrası" istatistiklere (işlem sayısı/win rate)
            # dahil edilmesin — sıfırlama sonrası bot tamamen 0 işlemle başlamalıdır.
            user_bot.performance_reset_at = liquidation_time + timedelta(microseconds=1)
            _log_user_action(
                db, current_user.id, "BOT_DEACTIVATE_RESET",
                "Kişisel bot durduruldu: açık pozisyonlar kapatıldı, performans 100.000 TL'ye sıfırlandı."
            )

        user_bot.is_active = req.is_active
        if req.is_active and not was_active:
            # Bot yeniden başlatılıyorsa süresini de sıfırla
            config = get_strategy_config(user_bot.time_frame or "1D")
            user_bot.started_at = datetime.utcnow()
            user_bot.ends_at = datetime.utcnow() + config["duration"]

    db.commit()
    db.refresh(user_bot)
    return get_user_bot_status(current_user, db)


@app.get("/api/user/bot/logs", response_model=List[BotLogResponse])
def get_user_bot_logs(
    time_frame: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Giriş yapan kullanıcının kişisel AI botunun işlem günlüğünü döner.
    time_frame verilirse ('1D'/'1W'/'1M') yalnızca o stratejiyle yapılan işlemler döner.
    Her SAT kaydı için, aynı hissede ondan önceki en yakın AL kaydına göre pozisyonun
    kaç gün açık kaldığı (days_held) hesaplanır.
    """
    # AL/SAT eşleştirmesi (days_held) için filtre uygulanmadan tüm geçmiş çekilir,
    # eşleştirme sonrası istenen zaman dilimine göre daraltılıp son 100 kayıt döndürülür.
    all_logs = db.query(models.BotLog)\
        .filter_by(user_id=current_user.id)\
        .order_by(models.BotLog.created_at.asc())\
        .all()

    last_buy_at = {}
    days_held_by_log_id = {}
    for log in all_logs:
        if log.action_type == "AL":
            last_buy_at[log.stock_id] = log.created_at
        elif log.action_type == "SAT":
            buy_time = last_buy_at.pop(log.stock_id, None)
            if buy_time:
                days_held_by_log_id[log.id] = max(0, (log.created_at - buy_time).days)

    filtered = [log for log in all_logs if not time_frame or log.time_frame == time_frame]
    filtered.sort(key=lambda log: log.created_at, reverse=True)
    filtered = filtered[:100]

    return [
        BotLogResponse(
            id=log.id, symbol=log.stock.symbol, action_type=log.action_type,
            price=float(log.price), quantity=float(log.quantity),
            reason_text=log.reason_text, time_frame=log.time_frame,
            days_held=days_held_by_log_id.get(log.id), created_at=log.created_at
        ) for log in filtered
    ]


@app.get("/api/user/bot/performance", response_model=Dict[str, List[Any]])
def get_user_bot_performance(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Giriş yapan kullanıcının kişisel botunun performansını BİST100 ile karşılaştırır."""
    return _build_bot_performance_series(db, current_user.id)


# --- LEADERBOARD ---

def _portfolio_value(db: Session, owner_user_id: int, is_bot_portfolio: bool, cash: float) -> float:
    positions = db.query(models.Portfolio).filter_by(user_id=owner_user_id, is_bot_portfolio=is_bot_portfolio).all()
    stock_value = 0.0
    for item in positions:
        price = _get_latest_db_price(db, item.stock_id) or float(item.average_cost)
        stock_value += float(item.quantity) * price
    return cash + stock_value


@app.get("/api/leaderboard", response_model=List[LeaderboardItem])
def get_leaderboard(db: Session = Depends(get_db)):
    """
    Liderlik tablosu: topluluk demo botu artık gösterilmez — yalnızca gerçek kullanıcılar
    ve her kullanıcının kendi kişisel AI botu (ayrı bir satır olarak) listelenir.
    """
    users = db.query(models.User).filter_by(is_bot=False).all()

    leaderboard = []
    for user in users:
        total_value = _portfolio_value(db, user.id, False, float(user.virtual_balance))
        baseline = float(user.baseline_value or 100000.0)
        profit_loss_pct = ((total_value - baseline) / baseline) * 100 if baseline else 0.0
        leaderboard.append(LeaderboardItem(
            username=user.username,
            total_portfolio_value=round(total_value, 2),
            profit_loss_pct=round(profit_loss_pct, 2),
            is_bot=False,
        ))

        user_bot = db.query(models.UserBot).filter_by(user_id=user.id).first()
        if user_bot:
            bot_total_value = _portfolio_value(db, user.id, True, float(user_bot.virtual_balance))
            bot_baseline = float(user_bot.baseline_value or 100000.0)
            bot_profit_loss_pct = ((bot_total_value - bot_baseline) / bot_baseline) * 100 if bot_baseline else 0.0
            leaderboard.append(LeaderboardItem(
                username=f"{user.username} — Kişisel Bot",
                total_portfolio_value=round(bot_total_value, 2),
                profit_loss_pct=round(bot_profit_loss_pct, 2),
                is_bot=True,
            ))

    # Sort by total portfolio value descending
    leaderboard.sort(key=lambda x: x.total_portfolio_value, reverse=True)
    return leaderboard
