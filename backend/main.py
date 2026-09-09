import os
import re
import secrets
import pandas as pd
from datetime import datetime, date, timedelta, time as dt_time, timezone as dt_timezone
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from fastapi import FastAPI, Depends, HTTPException, status, Request, BackgroundTasks, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from sqlalchemy.exc import IntegrityError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import nh3

import models
from database import engine, get_db, begin_write_transaction, SessionLocal
from schemas import (
    UserCreate, UserResponse, Token, LoginRequest,
    StockResponse, StockDetailResponse, StockPriceResponse, StockSearchResponse,
    TradeRequest, PortfolioResponse, PortfolioItemResponse,
    PortfolioAnalyticsResponse, SectorAllocationItem, PositionWeightItem,
    TransactionItem, TransactionHistoryResponse,
    StockVoteRequest, StockVoteResponse, ChangePasswordRequest,
    DividendPositionItem, PortfolioDividendResponse,
    BenchmarkPoint, PortfolioBenchmarkResponse, MarketQuoteItem,
    FinancialPeriodItem, FinancialStatementsResponse, PortfolioRiskResponse,
    TechnicalSignalItem, SectorSummaryItem, StockSectorComparison, WatchlistUpdateRequest,
    DividendPaymentItem, DividendHistoryResponse,
    BotLogResponse, BotSessionResponse, BotPerformancePoint, LeaderboardItem,
    BasketSummary, BasketHolding, BasketInvestRequest, BasketInvestResponse,
    AchievementResponse, ReferralInfoResponse,
    CounterfactualResponse,
    SeasonalityResponse,
    StockProResponse, KatilimInfoResponse, CompanyAnalysisResponse,
    InsiderTradeResponse, KapNotificationResponse, FundResponse, FundPriceResponse,
    IpoResponse, StockCommentCreate, StockCommentResponse, CommunitySentimentResponse,
    DividendGoalRequest, DcaBacktestRequest, BalanceUpdateRequest, UserBotResponse, UserBotSettingsRequest,
    PendingOrderCreate, PendingOrderUpdate, PendingOrderResponse, StockNewsItem,
    MarketNewsItem, DividendEventItem, PortfolioKatilimResponse, KatilimPozisyonu,
    PivotLevelsResponse, ForeignHoldingTrendResponse, EarningsCalendarItem,
    NotificationPreferenceRequest, NotificationPreferenceResponse, NotificationResponse, UnreadCountResponse,
    WatchlistItemResponse, ScreenerItemResponse,
    PushSubscribeRequest, PushStatusResponse,
    ScorecardResponse, BacktestResponse, ExtraIndicatorsResponse, IndicatorSeriesResponse,
    CustomFormulaRequest, CustomFormulaResponse,
    PublicProfileHolding, PublicProfileResponse, ProfileVisibilityUpdateRequest,
    CategoryLeaderboardItem, HallOfFameEntryResponse, HallOfFamePlacement,
    QuestResponse, GamePointsResponse, ShopItemResponse,
    DuelCreateRequest, DuelResponse,
)
from auth import (
    get_password_hash, verify_password, create_access_token, get_current_user
)
from scheduler import start_scheduler
from init_db import init_database
from bot import (
    calculate_technical_indicators, get_strategy_config, BOT_STRATEGY_CONFIG,
    get_risk_mode_config, RISK_MODE_CONFIG, DEFAULT_RISK_MODE,
    open_bot_session, close_open_bot_session,
)
from kap_client import fetch_kap_disclosures, get_kap_search_url
from baskets import sepet_tanimlari, sepet_tanimi, sepet_hisseleri
from achievements import basarim_tanimlari, kazanilanlari_hesapla, Baglam
from leaderboard_categories import (
    istikrar_siralamasi, aktiflik_siralamasi, kahin_siralamasi, rutbe_hesapla, RUTBE_PUANLARI,
)
from quests import gorev_tanimlari, tamamlananlari_hesapla, GorevBaglami
from shop import magaza_esyalari, esya_bul
from duels import portfoy_degeri as duel_portfoy_degeri, getiri_pct as duel_getiri_pct, DUEL_SURESI_GUN
from market_hours import get_market_status_dict, is_market_open, bugun_tr, TR_TZ
from transactions import record_transaction, alim_maliyeti, satim_geliri
from analysis_engine import (
    calculate_deep_analysis, calculate_dividend_goal, calculate_dca_backtest, AnalysisFetchError,
    get_foreign_holding_trend,
)
from insider_client import fetch_insider_trades, get_recent_insider_buys, refresh_all_insider_trades
from dividend_stability import compute_dividend_stability
from text_utils import tr_lower, tr_fold
from kap_topics import is_major_holder_news
from sentiment import score_sentiment
from yfinance_client import fetch_stock_news
from cache import get_cached_news, set_cached_news
from constants import EXTREME_CHANGE_GUARD_PCT, HISTORY_RANGE_DAYS, KOMISYON_ORANI_PCT, REFERANS_BONUS_TL

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

    # Üretimde uygulama Nginx'in arkasında çalışır; bu durumda request.client.host
    # her kullanıcı için proxy'nin adresini (127.0.0.1) döndürür. Bu adres rate limit
    # anahtarı olarak kullanılırsa TÜM kullanıcılar tek bir kovayı paylaşır ve birinin
    # denemeleri diğerlerini kilitler. Bu yüzden gerçek istemci IP'si X-Forwarded-For
    # başlığından okunur.
    #
    # Güvenlik notu: X-Forwarded-For istemci tarafından taklit edilebilir, ancak
    # Nginx yapılandırmamız $proxy_add_x_forwarded_for kullandığı için gerçek IP
    # zincirin SONUNA eklenir. Bu yüzden bilerek son eleman alınır — istemcinin
    # gönderdiği sahte değerler baştaki elemanlar olarak kalır ve dikkate alınmaz.
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[-1].strip()
        if client_ip:
            return client_ip

    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key)

app = FastAPI(title="BIST Simülasyonu & AI Trader API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Production CORS Hardening ---
# Geliştirme ortamında (FRONTEND_URL / NEXT_PUBLIC_FRONTEND_URL tanımlı değilse) yerel
# origin'lere izin verilir. Üretimde ise SADECE FRONTEND_URL ile belirtilen
# origin kabul edilir (borsa-trader.duckdns.org, nginx arkasında aynı VPS'te). Wildcard ('*') KASITLI OLARAK desteklenmez: allow_credentials=True ile
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


@app.middleware("http")
async def add_no_store_to_api(request: Request, call_next):
    """
    API yanıtlarına Cache-Control: no-store ekler.

    Neden gerekli: FastAPI hiçbir Cache-Control başlığı göndermiyordu. Başlık
    yokken tarayıcılar SEZGİSEL önbellekleme yapar (heuristic caching) ve aynı
    URL'e giden sonraki istekleri ağa hiç çıkmadan önbellekten karşılayabilir.
    Sonuç: frontend 15 saniyede bir yenilese bile kullanıcı ESKİ fiyatı ve eski
    yüzde değişimi görmeye devam ediyordu — hisse eksiye dönmüşken ekranda hâlâ
    artıda görünüyordu.

    Yalnızca /api/ yolunu kapsar; statik varlıklar içerik-hash'li oldukları için
    uzun süreli önbelleklenmeye devam etmelidir.
    """
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response

# Uygulama başlarken tablo/veri kontrolü + APScheduler
@app.on_event("startup")
def startup_event():
    # Yerel geliştirmede bist_app.db repoda tutulmaz (.gitignore), yani temiz bir
    # klonda hiç yoktur. init_database() idempotent'tir: create_all() var olan tabloları
    # bozmaz, seed adımları zaten var olan kayıtları atlar — bu yüzden her başlangıçta
    # güvenle çağrılabilir. Scheduler'ın cache doldurma adımı 'stocks' tablosunu
    # sorguladığı için bu çağrı start_scheduler()'dan ÖNCE tamamlanmış olmalı.
    from yf_retry import configure_yfinance
    configure_yfinance()
    init_database()

    # CI'da zamanlanmış işler ÇALIŞTIRILMAZ. Scheduler başlarken Yahoo, KAP,
    # TEFAS ve haber kaynaklarına ağ isteği atıyor; test koşumunda bu hem
    # gereksiz hem de testi dış servislerin o anki durumuna bağımlı kılar
    # (uçun 200 dönüp dönmediğini ölçüyoruz, Yahoo'nun ayakta olup olmadığını
    # değil). DISABLE_SCHEDULER=1 yalnızca CI ve test içindir.
    if os.getenv("DISABLE_SCHEDULER") == "1":
        print("[Startup] DISABLE_SCHEDULER=1 — zamanlanmış işler atlandı.")
        return
    start_scheduler()

# --- AUTHENTICATION ---

def _generate_referral_code(db: Session) -> str:
    """6 haneli benzersiz referans kodu üretir. Çarpışma ölçülemeyecek kadar
    düşük olasılıklı (36^6 ≈ 2 milyar) ama yine de garanti için kontrol edilir."""
    for _ in range(10):
        code = secrets.token_hex(3).upper()  # örn. "A3F9BC"
        if not db.query(models.User).filter_by(referral_code=code).first():
            return code
    raise RuntimeError("Referans kodu üretilemedi.")


@app.post("/api/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, user_data: UserCreate, db: Session = Depends(get_db)):
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

    # Referans kodu geçerliyse davet eden de bulunur -- bonus ikisine de
    # kayıt İŞLEMİ İÇİNDE (aynı commit'te) verilir, ayrı bir adım gerekmez.
    #
    # BEGIN IMMEDIATE ile: bu işlem ÜÇÜNCÜ BİR KULLANICININ (referrer) satırını
    # okuyup güncelliyor -- kilit olmadan aynı kodla eşzamanlı iki kayıt isteği
    # referrer.virtual_balance'ı aynı eski değerden okuyup ikisi de +5000
    # ekleyebilir, son commit diğerini ezer ve referrer bonusun yalnızca
    # birini alır ("lost update"). execute_trade/orders.py'deki aynı
    # atomiklik deseni burada da uygulanır.
    db.rollback()
    begin_write_transaction(db)

    referrer = None
    if user_data.referral_code:
        referrer = db.query(models.User).filter_by(
            referral_code=user_data.referral_code.strip().upper()
        ).first()

    hashed_password = get_password_hash(user_data.password)
    new_user = models.User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        virtual_balance=100000.00,
        is_bot=False,
        terms_accepted=True,
        terms_accepted_at=datetime.utcnow(),
        referral_code=_generate_referral_code(db),
    )
    if referrer:
        new_user.referred_by_id = referrer.id
        # Bonus HEM bakiyeye HEM referans sermayesine (baseline_value) eklenir
        # -- aksi halde bedava bonus, liderlik tablosunda sahte bir "getiri"
        # gibi görünürdü (bkz. User.baseline_value docstring'i, aynı ilke).
        new_user.virtual_balance = float(new_user.virtual_balance) + REFERANS_BONUS_TL
        new_user.baseline_value = 100000.00 + REFERANS_BONUS_TL
        referrer.virtual_balance = float(referrer.virtual_balance) + REFERANS_BONUS_TL
        referrer.baseline_value = float(referrer.baseline_value or 100000.0) + REFERANS_BONUS_TL
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    if referrer:
        _log_user_action(db, referrer.id, "REFERRAL_BONUS", f"{new_user.username} senin referans kodunla katıldı: +{REFERANS_BONUS_TL:.0f} TL.")
        _log_user_action(db, new_user.id, "REFERRAL_BONUS", f"{referrer.username} kullanıcısının referans koduyla katıldın: +{REFERANS_BONUS_TL:.0f} TL.")
        db.commit()

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
    open_bot_session(db, new_user.id, "1D", DEFAULT_RISK_MODE)
    db.commit()

    return new_user

@app.post("/api/auth/login", response_model=Token)
@limiter.limit("10/minute")
def login(request: Request, login_data: LoginRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
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


@app.get("/api/user/referral", response_model=ReferralInfoResponse)
def get_referral_info(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Kullanıcının kendi referans kodu + kaç kişiyi davet ettiği + toplam
    kazandığı bonus. Kod yoksa (referans sistemi eklenmeden ÖNCE kaydolmuş
    eski kullanıcı) burada TEMBEL ÜRETİLİR -- geriye dönük backfill script'i
    gerekmez, kullanıcı bu sayfayı ilk açtığında kendiliğinden oluşur.
    """
    if not current_user.referral_code:
        current_user.referral_code = _generate_referral_code(db)
        db.commit()

    referral_count = db.query(func.count(models.User.id)).filter_by(referred_by_id=current_user.id).scalar() or 0
    return ReferralInfoResponse(
        code=current_user.referral_code,
        referral_count=referral_count,
        total_bonus=round(referral_count * REFERANS_BONUS_TL, 2),
    )


@app.post("/api/auth/change-password")
@limiter.limit("5/minute")
def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Giriş yapmış kullanıcının şifresini değiştirir.

    Mevcut şifre HER ZAMAN doğrulanır: token'ı çalınmış bir oturumun şifreyi
    sessizce değiştirip hesabı ele geçirmesini engeller.

    NOT: JWT'ler durumsuz (stateless) olduğu için şifre değişikliği daha önce
    dağıtılmış token'ları geçersiz kılmaz; mevcut oturumlar süreleri dolana
    kadar açık kalır. Anında iptal için token sürüm/kara liste mekanizması
    gerekir — bu ayrı bir iştir.
    """
    # Bot hesaplarının şifresi kullanıcı tarafından değiştirilemez.
    if current_user.is_bot:
        raise HTTPException(status_code=403, detail="Bot hesabının şifresi değiştirilemez.")

    user = db.query(models.User).filter_by(id=current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")

    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Mevcut şifreniz hatalı.")

    user.password_hash = get_password_hash(payload.new_password)
    db.commit()

    _log_user_action(db, user.id, "PASSWORD_CHANGE", "Kullanıcı şifresini değiştirdi.")
    return {"message": "Şifreniz başarıyla güncellendi."}


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
# Bir tikin "güncel fiyat" sayılabileceği azami yaş. _bulk_price_and_change ile
# AYNI pencere kullanılır; ikisi ayrışırsa aynı hisse iki sayfada iki farklı
# fiyattan görünür.
TIK_TAZELIK_PENCERESI = timedelta(days=7)


def _get_latest_db_price(db: Session, stock_id: int) -> float:
    """
    Hissenin güncel fiyatı: önce son tik, tik bayatsa son günlük kapanış.

    BAYATLIK KONTROLÜ NEDEN VAR: eskiden bu fonksiyon son tiki YAŞINA BAKMADAN
    döndürüyordu, `_bulk_price_and_change` ise 7 günden eski tiki yok sayıp
    günlük kapanışa düşüyordu. Uygulamada 11 yer birincisini, 6 yer ikincisini
    kullanıyordu — yani aynı hisse portföy sayfasında bir fiyattan, hisse
    listesinde başka fiyattan görünebiliyordu.

    Ölçüldü (yerel veritabanı, son tik 21 gün eski): BIMAS tikte 382,25 TL,
    günlük kapanışta 413,75 TL. Aradaki %8'lik fark doğrudan portföy değerine
    ve liderlik tablosuna yansıyordu. Üretimde seans içinde tikler taze olduğu
    için fark çıkmaz; fark uzun tatil ve işlem görmeyen hisselerde ortaya çıkar.
    """
    esik = datetime.utcnow() - TIK_TAZELIK_PENCERESI
    latest_record = (
        db.query(models.StockPrice)
        .filter(models.StockPrice.stock_id == stock_id,
                models.StockPrice.recorded_at >= esik)
        .order_by(models.StockPrice.recorded_at.desc())
        .first()
    )
    if latest_record:
        return float(latest_record.price)

    # Tik yok ya da bayat: son günlük kapanışa düş (_bulk_price_and_change ile
    # aynı öncelik sırası).
    son_kapanis = (
        db.query(models.StockPriceDaily.close)
        .filter(models.StockPriceDaily.stock_id == stock_id)
        .order_by(models.StockPriceDaily.trade_date.desc())
        .first()
    )
    return float(son_kapanis[0]) if son_kapanis else 0.0


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

    # PİYASA GÜNÜ SINIRI TÜRKİYE SAATİYLE: sunucu UTC'de çalışıyor ve TSİ
    # 00:00–03:00 arasında `date.today()` dünü döndürüyor. O aralıkta referans
    # kapanış bir gün eskiye kayıyor, yani her hissenin günlük % değişimi
    # yanlış hesaplanıyordu (bkz. market_hours.bugun_tr).
    today = bugun_tr()
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

    # Hisse başına EN SON KAPANIŞ — tik bulunamazsa fiyat için yedek.
    # (prev_close_map bilerek "dünden önce" filtreliyor; o referans fiyat, bu ise
    #  gösterilecek fiyat. İkisini karıştırmak günlük değişimi sıfırlardı.)
    latest_any_subq = (
        db.query(
            models.StockPriceDaily.stock_id,
            func.max(models.StockPriceDaily.trade_date).label("max_date"),
        )
        .filter(models.StockPriceDaily.stock_id.in_(stock_ids))
        .group_by(models.StockPriceDaily.stock_id)
        .subquery()
    )
    latest_close_map = {
        stock_id: float(close)
        for stock_id, close in db.query(models.StockPriceDaily.stock_id, models.StockPriceDaily.close)
        .join(
            latest_any_subq,
            (models.StockPriceDaily.stock_id == latest_any_subq.c.stock_id)
            & (models.StockPriceDaily.trade_date == latest_any_subq.c.max_date),
        )
        .all()
    }

    # Her hisse için en son 2 tik: [0]=güncel, [1]=bir önceki (prev_close yoksa fallback için).
    # DB tarafında ROW_NUMBER() ile hisse başına en yeni 2 satır seçilir; ".in_()" ile
    # çekip Python'da ilk 2'yi almak TÜM geçmişi belleğe yığardı.
    #
    # ZAMAN FİLTRESİ ŞART: ROW_NUMBER() bir bölümün TAMAMINI okumak zorundadır, yani
    # filtresiz sorgu 208 satır döndürmek için 57.436 satırın hepsini tarıyordu ve
    # maliyeti geçmişle birlikte doğrusal büyüyordu (ölçüldü: 38 ms; tablo 3 ayda
    # 1,2 milyon satıra çıkacaktı). Son günlerle sınırlayınca sorgu sabit maliyetli
    # hale geliyor (ölçüldü: 14 ms, 12.893 satır). Pencere 7 gün: uzun hafta sonu ve
    # resmi tatil üst üste gelse bile son işlem gününün tikleri kapsam içinde kalır.
    tick_window_start = datetime.utcnow() - timedelta(days=7)
    row_num = func.row_number().over(
        partition_by=models.StockPrice.stock_id,
        order_by=models.StockPrice.recorded_at.desc(),
    ).label("rn")
    ranked_subq = (
        db.query(
            models.StockPrice.stock_id,
            models.StockPrice.price,
        )
        .filter(
            models.StockPrice.stock_id.in_(stock_ids),
            models.StockPrice.recorded_at >= tick_window_start,
        )
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
            # Son 7 günde tik yoksa (yeni eklenmiş hisse, uzun süredir işlem
            # görmeyen hisse, ya da tik saklama süresi dolmuş) günlük kapanışa
            # düşülür. Eskiden burada 0.0 dönülüyordu ve arayüzde "0,00 TL"
            # görünüyordu — oysa günlük kapanış verisi elimizde duruyordu.
            fallback = latest_close_map.get(stock_id)
            if not fallback:
                result[stock_id] = (0.0, None)
                continue
            prev_close = yahoo_prev_close_map.get(stock_id) or prev_close_map.get(stock_id)
            change = None
            if prev_close and prev_close > 0:
                change = ((fallback - prev_close) / prev_close) * 100
                if abs(change) > EXTREME_CHANGE_GUARD_PCT:
                    change = None
            result[stock_id] = (fallback, change)
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
            "katilim_status": stock.katilim_status,
            "purification_rate": float(stock.purification_rate or 0.0)
        })

    return response


@app.get("/api/stocks/search", response_model=List[StockSearchResponse])
def search_stocks(q: str = "", limit: int = 8, db: Session = Depends(get_db)):
    """
    Navbar'daki global arama kutusu için hafif hisse arama.

    NOT: Bu route, "/api/stocks/{symbol}" tanımından ÖNCE gelmelidir; aksi halde
    FastAPI "search" kelimesini bir sembol sanıp o endpoint'e yönlendirir.

    Sembol ve şirket adı üzerinde büyük/küçük harf duyarsız arama yapar; sembolle
    başlayan sonuçlar (THY → THYAO) en üstte gösterilir.
    """
    term = (q or "").strip()
    if not term:
        return []

    capped_limit = max(1, min(limit, 25))

    # ARAMA NEDEN SQL'DE DEĞİL: ILIKE Türkçe harfleri katlayamaz. Ölçüldü —
    # üretimde (PostgreSQL) "türk" 8 sonuç verirken "TURK" yalnızca 1 veriyordu;
    # yerelde (SQLite) "ziraat" 0, "ZİRAAT" 24 sonuç veriyordu. Telefondan
    # Türkçe karakter yazmayan kullanıcı hisseyi hiç bulamıyordu.
    #
    # Katalog 165 hisse; tamamını belleğe alıp tr_fold ile karşılaştırmak
    # hem doğru hem de bu boyutta ölçülebilir bir maliyet getirmiyor.
    aday_hisseler = (
        db.query(models.Stock)
        .filter(models.Stock.is_active == True)  # noqa: E712 (SQLAlchemy kolon karşılaştırması)
        .all()
    )
    katlanmis_terim = tr_fold(term)
    stocks = [
        s for s in aday_hisseler
        if katlanmis_terim in tr_fold(s.symbol or "")
        or katlanmis_terim in tr_fold(s.company_name or "")
    ]

    # Sembolü terimle BAŞLAYANLAR önce (THY -> THYAO en üstte çıksın).
    stocks.sort(key=lambda s: (not tr_fold(s.symbol).startswith(katlanmis_terim), s.symbol))
    stocks = stocks[:capped_limit]

    return [
        StockSearchResponse(
            symbol=s.symbol,
            company_name=s.company_name,
            sector=s.sector,
            is_katilim_compliant=bool(s.is_katilim_compliant),
            katilim_status=s.katilim_status,
        )
        for s in stocks
    ]


@app.get("/api/stocks/compare", response_model=List[ScreenerItemResponse])
def compare_stocks(symbols: str = "", db: Session = Depends(get_db)):
    """
    Birden fazla hisseyi yan yana karşılaştırmak için temel fiyat ve oran verilerini döner.
    symbols virgülle ayrılmış sembol listesidir (örn. "THYAO,GARAN,BIMAS"), en fazla 4 hisse.

    NOT: "/api/stocks/{symbol}" tanımından ÖNCE gelmelidir (bkz. search_stocks).
    Sonuçlar istenen sırayla döner ki kullanıcının seçim sırası korunsun.
    """
    requested = [s.strip().upper() for s in (symbols or "").split(",") if s.strip()]
    if not requested:
        return []
    requested = requested[:4]

    stocks = db.query(models.Stock).filter(models.Stock.symbol.in_(requested)).all()
    if not stocks:
        return []

    stock_ids = [s.id for s in stocks]
    price_map = _bulk_price_and_change(db, stock_ids)
    analysis_by_stock = {
        row.stock_id: row
        for row in db.query(models.CompanyAnalysis)
        .filter(models.CompanyAnalysis.stock_id.in_(stock_ids))
        .all()
    }

    by_symbol = {}
    for stock in stocks:
        current_price, price_change_pct = price_map.get(stock.id, (0.0, None))
        analysis = analysis_by_stock.get(stock.id)
        by_symbol[stock.symbol] = ScreenerItemResponse(
            symbol=stock.symbol,
            company_name=stock.company_name,
            sector=stock.sector,
            current_price=round(current_price, 2),
            price_change_pct=round(price_change_pct, 2) if price_change_pct is not None else None,
            is_katilim_compliant=bool(stock.is_katilim_compliant),
            katilim_status=stock.katilim_status,
            pe_ratio=float(analysis.pe_ratio) if analysis and analysis.pe_ratio is not None else None,
            pb_ratio=float(analysis.pb_ratio) if analysis and analysis.pb_ratio is not None else None,
            roe=float(analysis.roe) if analysis and analysis.roe is not None else None,
            piotroski_score=analysis.piotroski_score if analysis else None,
            altman_z_score=float(analysis.altman_z_score) if analysis and analysis.altman_z_score is not None else None,
            debt_to_equity=float(analysis.debt_to_equity) if analysis and analysis.debt_to_equity is not None else None,
            net_margin=float(analysis.net_margin) if analysis and analysis.net_margin is not None else None,
            dividend_yield=float(analysis.dividend_yield) if analysis and analysis.dividend_yield is not None else None,
            target_upside_pct=float(analysis.target_upside_pct) if analysis and analysis.target_upside_pct is not None else None,
        )

    # İstenen sırayı koru; bulunamayan semboller sessizce atlanır
    return [by_symbol[sym] for sym in requested if sym in by_symbol]


SCREENER_SORT_FIELDS = {
    "price_change_pct": lambda item: item.price_change_pct,
    "pe_ratio": lambda item: item.pe_ratio,
    "pb_ratio": lambda item: item.pb_ratio,
    "roe": lambda item: item.roe,
    "piotroski_score": lambda item: item.piotroski_score,
    "current_price": lambda item: item.current_price,
    "dividend_yield": lambda item: item.dividend_yield,
    "target_upside_pct": lambda item: item.target_upside_pct,
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
    min_dividend_yield: Optional[float] = None,
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
        # Temettü verimi filtresi: verisi olmayan hisse eşiği "sağlamıyor" kabul edilir
        # (diğer filtrelerle aynı davranış) — aksi halde temettü ödemeyen şirketler
        # "temettü verimi en az %5" aramasında listelenirdi.
        _dy = float(analysis.dividend_yield) if (analysis and analysis.dividend_yield is not None) else None
        if min_dividend_yield is not None and (_dy is None or _dy < min_dividend_yield):
            continue

        items.append(ScreenerItemResponse(
            symbol=stock.symbol,
            company_name=stock.company_name,
            sector=stock.sector,
            current_price=round(current_price, 2),
            price_change_pct=round(price_change_pct, 2) if price_change_pct is not None else None,
            is_katilim_compliant=bool(stock.is_katilim_compliant),
            katilim_status=stock.katilim_status,
            pe_ratio=pe_ratio,
            pb_ratio=pb_ratio,
            roe=roe,
            piotroski_score=piotroski_score,
            altman_z_score=float(analysis.altman_z_score) if analysis and analysis.altman_z_score is not None else None,
            debt_to_equity=float(analysis.debt_to_equity) if analysis and analysis.debt_to_equity is not None else None,
            net_margin=float(analysis.net_margin) if analysis and analysis.net_margin is not None else None,
            dividend_yield=float(analysis.dividend_yield) if analysis and analysis.dividend_yield is not None else None,
            target_upside_pct=float(analysis.target_upside_pct) if analysis and analysis.target_upside_pct is not None else None,
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
    today = bugun_tr()  # UTC değil TR — bkz. market_hours.bugun_tr
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

    # Seansın açılış/yüksek/düşük değerleri.
    #
    # Öncelik Yahoo'nun resmi değerlerindedir (stocks.open_price/day_high/day_low,
    # scheduler tazeler). Kendi tiklerimizden türetmek YANLIŞ sonuç veriyordu:
    # tikler yalnızca scheduler çalışırken yazıldığı için "açılış" gerçekte ilk
    # KAYDEDİLEN fiyat oluyordu — backend seans ortasında yeniden başlatılırsa
    # açılış o anki fiyat olarak görünüyordu.
    #
    # Kayıtlı değer yoksa (henüz tazelenmemiş eski kayıtlar) tik türevine düşülür.
    today_start = datetime.combine(today, datetime.min.time())
    today_ticks = [p for p in price_records if p.recorded_at >= today_start]

    open_price = float(stock.open_price) if stock.open_price is not None else (
        float(today_ticks[0].price) if today_ticks else None
    )
    day_high = float(stock.day_high) if stock.day_high is not None else (
        max((float(p.price) for p in today_ticks), default=None)
    )
    day_low = float(stock.day_low) if stock.day_low is not None else (
        min((float(p.price) for p in today_ticks), default=None)
    )

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
        # Son 100 kaydı tarih filtresi olmadan almak YANLIŞTI: fiyat anlık görüntüleri
        # yalnızca seans saatlerinde yazıldığı için, borsa kapalıyken bu 100 kayıt
        # günlere yayılıyordu (örn. GUNDG'de 6 günü kapsıyordu) ve "Bugün" etiketli
        # grafik aslında bir haftayı gösteriyordu.
        #
        # Bugünün tarihine göre filtrelemek de olmaz: hafta sonu/tatilde hiç kayıt
        # olmadığı için grafik bomboş kalırdı. Bunun yerine, veride mevcut olan EN SON
        # seans gününü bulup yalnızca o güne ait kayıtlar döndürülür — borsa kapalıyken
        # aracı kurum uygulamalarının yaptığı gibi son seans gösterilir.
        latest_ts = db.query(func.max(models.StockPrice.recorded_at))\
            .filter(models.StockPrice.stock_id == stock.id)\
            .scalar()
        if not latest_ts:
            return []

        session_day = latest_ts.date()
        records = db.query(models.StockPrice)\
            .filter(
                models.StockPrice.stock_id == stock.id,
                func.date(models.StockPrice.recorded_at) == session_day,
            )\
            .order_by(models.StockPrice.recorded_at.asc())\
            .all()

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
            open=float(r.open) if r.open is not None else None,
            high=float(r.high) if r.high is not None else None,
            low=float(r.low) if r.low is not None else None,
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

    # ÖNCE VERİTABANI. Bu uç eskiden her istekte KAP'a canlı HTTP çağrısı yapıyordu
    # ve ~850 ms sürüyordu (diğer uçların 5 katı); hisse detay sayfası her açılışta
    # bunu çağırdığı için sayfanın en yavaş parçasıydı. KAP taraması zaten
    # scheduler'daki refresh_market_data_job tarafından günlük yapılıp
    # kap_notifications tablosuna yazılıyor — bu modülün kendi yorumu da ağır KAP
    # taramasının istek döngüsü DIŞINDA tutulması gerektiğini söylüyor.
    rows = (
        db.query(models.KapNotification)
        .filter(models.KapNotification.symbol == symbol.upper())
        .order_by(models.KapNotification.publish_date.desc())
        .limit(8)
        .all()
    )

    disclosures = [
        {
            "title": r.title,
            "date": r.publish_date.strftime("%d.%m.%Y %H:%M") if r.publish_date else "",
            "date_raw": r.publish_date.isoformat() if r.publish_date else "",
            "type": (r.summary or "")[:80],
            "company": stock.company_name,
            "url": r.kap_url or "",
        }
        for r in rows
    ]

    # Veritabanında hiç kayıt yoksa (yeni eklenen hisse / scheduler henüz o sembole
    # ulaşmamış) canlı çekime düşülür — nadir durum, sürekli maliyet oluşturmaz.
    if not disclosures:
        disclosures = fetch_kap_disclosures(symbol.upper())

    return {
        "symbol": symbol.upper(),
        "company_name": stock.company_name,
        "kap_url": get_kap_search_url(symbol.upper()),
        "disclosures": disclosures,
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
            katilim_status=stock.katilim_status,
            purification_rate=float(stock.purification_rate or 0.0),
            non_compliance_reason=stock.non_compliance_reason,
            debt_ratio=float(stock.katilim_debt_ratio) if stock.katilim_debt_ratio is not None else None,
            asset_ratio=float(stock.katilim_asset_ratio) if stock.katilim_asset_ratio is not None else None,
            detail=stock.katilim_detail,
            checked_at=stock.katilim_checked_at,
            # KAP resmi beyanı (bkz. katilim_kap.py). Yoksa None kalır ve
            # arayüz uydurma bir sayı göstermek yerine hiç göstermez.
            kap_gelir_pct=float(stock.kap_katilim_gelir_pct) if stock.kap_katilim_gelir_pct is not None else None,
            kap_varlik_pct=float(stock.kap_katilim_varlik_pct) if stock.kap_katilim_varlik_pct is not None else None,
            kap_borc_pct=float(stock.kap_katilim_borc_pct) if stock.kap_katilim_borc_pct is not None else None,
            kap_donem=stock.kap_katilim_donem,
            kap_url=stock.kap_katilim_url,
            kap_updated_at=stock.kap_katilim_updated_at,
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

    # Hesap KENDİ günlük fiyat tablomuzdan yapılır. Eskiden burada Yahoo'ya
    # canlı istek atılıyordu; uç, kod hiç değişmeden bir gün içinde çalışır
    # durumdan available:false'a düştü (bkz. pivot.py başlığı).
    from pivot import hesapla as pivot_hesapla
    data = pivot_hesapla(db, stock.id, symbol)
    _pivot_cache[symbol] = {"data": data, "cached_at": datetime.utcnow()}
    return data


@app.get("/api/stocks/{symbol}/seasonality", response_model=SeasonalityResponse)
def get_stock_seasonality(symbol: str, db: Session = Depends(get_db)):
    """
    Aylık mevsimsellik: hisse tarihsel olarak hangi ayda ortalama nasıl hareket
    etmiş (bkz. seasonality.py). En az 3 tam yıllık günlük veri gerektirir;
    yoksa available=false döner.
    """
    symbol = symbol.upper()
    stock = db.query(models.Stock).filter_by(symbol=symbol, is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    from seasonality import compute_seasonality
    aylar = compute_seasonality(db, stock.id)
    if aylar is None:
        return SeasonalityResponse(available=False, symbol=symbol, months=[])
    return SeasonalityResponse(available=True, symbol=symbol, months=aylar)


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


def _build_vote_response(db: Session, stock: models.Stock, user_id: int) -> StockVoteResponse:
    """Bir hissenin oy sayımını ve çağıran kullanıcının kendi oyunu toplar."""
    up_count = db.query(models.StockVote).filter_by(stock_id=stock.id, direction="UP").count()
    down_count = db.query(models.StockVote).filter_by(stock_id=stock.id, direction="DOWN").count()
    total = up_count + down_count

    own = db.query(models.StockVote).filter_by(stock_id=stock.id, user_id=user_id).first()

    return StockVoteResponse(
        symbol=stock.symbol,
        up_count=up_count,
        down_count=down_count,
        total_votes=total,
        # Hiç oy yokken 0/0 bölmesi olmasın diye sıfır döndürülür.
        up_pct=round((up_count / total) * 100, 2) if total else 0.0,
        down_pct=round((down_count / total) * 100, 2) if total else 0.0,
        user_vote=own.direction if own else None,
    )


@app.get("/api/stocks/{symbol}/vote", response_model=StockVoteResponse)
def get_stock_vote(
    symbol: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Hissenin topluluk beklenti anketi sonucu + kullanıcının kendi oyu."""
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")
    return _build_vote_response(db, stock, current_user.id)


@app.post("/api/stocks/{symbol}/vote", response_model=StockVoteResponse)
@limiter.limit("20/minute")
def cast_stock_vote(
    request: Request,
    symbol: str,
    vote: StockVoteRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Hisse için 'Yükselir' (UP) / 'Düşer' (DOWN) oyu verir.

    Her kullanıcının hisse başına TEK oyu vardır: tekrar oy verirse mevcut kaydı
    güncellenir, yeni satır açılmaz (aksi halde bir kullanıcı defalarca oy verip
    sonucu çarpıtabilirdi). Aynı kullanıcının iki isteği yarışırsa UNIQUE kısıtı
    ikinciyi reddeder; bu durumda kayıt yeniden okunup güncellenir.
    """
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    existing = db.query(models.StockVote).filter_by(stock_id=stock.id, user_id=current_user.id).first()
    try:
        if existing:
            existing.direction = vote.direction
        else:
            db.add(models.StockVote(
                user_id=current_user.id, stock_id=stock.id, direction=vote.direction
            ))
        db.commit()
    except IntegrityError:
        # Eşzamanlı ikinci istek araya girip satırı oluşturmuş olabilir.
        db.rollback()
        row = db.query(models.StockVote).filter_by(stock_id=stock.id, user_id=current_user.id).first()
        if row:
            row.direction = vote.direction
            db.commit()

    return _build_vote_response(db, stock, current_user.id)


# --- KAP GENEL HABER AKIŞI ---

@app.get("/api/earnings-calendar", response_model=List[EarningsCalendarItem])
def get_earnings_calendar(db: Session = Depends(get_db)):
    """
    Yaklaşan (bugün dahil, gelecekteki) çeyreklik bilanço açıklama tarihi bilinen
    aktif hisseleri, tarihe göre artan sırada döner. Tarih bilgisi scheduler
    tarafından günlük olarak (refresh_earnings_calendar) yfinance'tan tazelenir.
    """
    # TR tarihi: UTC ile TSİ 00:00–03:00 arasında dünkü açıklama "yaklaşan"
    # görünüyordu (bkz. market_hours.bugun_tr).
    today = bugun_tr()
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
# Sınıflandırma mantığı kap_topics.py modülüne taşındı (ölçümle doğrulandı).


@app.get("/api/kap/search", response_model=List[KapNotificationResponse])
def search_kap_news(q: str = "", db: Session = Depends(get_db)):
    """
    KAP bildirimlerinde tam metin arama (bkz. kap_search.py). Üretimde
    PostgreSQL'in Türkçe metin arama yapılandırması kullanılır; boş sorguda
    boş liste döner (tüm 498 kaydı listelemek arama değildir).
    """
    from kap_search import search_kap_notifications
    return search_kap_notifications(db, q)


@app.get("/api/kap/major-holder-news", response_model=List[KapNotificationResponse])
def get_major_holder_news(db: Session = Depends(get_db)):
    """
    Genel KAP akışından, başlığında pay sahipliği/oy hakları değişikliğine işaret eden
    anahtar kelimeler geçen bildirimleri (büyük yatırımcı hareketleri) filtreler.
    """
    # Sabit .limit(300) yerine ZAMAN penceresi: eskiden en yeni 300 kayıt çekilip
    # sonra filtreleniyordu, yani akış gürültüyle dolduğunda gerçek pay sahipliği
    # bildirimleri pencerenin dışında kalıp sessizce kayboluyordu.
    esik = datetime.utcnow() - timedelta(days=90)
    notifications = (
        db.query(models.KapNotification)
        .filter(models.KapNotification.publish_date >= esik)
        .order_by(models.KapNotification.publish_date.desc())
        .all()
    )
    # Sınıflandırma kap_topics.py'de; orada dahil etme VE dışlama listesi birlikte
    # çalışır ("Pay Bazında Devre Kesici" gibi 60+ gürültü kaydı elenir).
    filtered = [n for n in notifications if is_major_holder_news(n.title)]
    return filtered[:30]


# --- VERİ SAĞLIĞI ---

@app.get("/api/health")
def get_health(db: Session = Depends(get_db)):
    """
    Her veri boru hattının taze olup olmadığını raporlar (bkz. veri_sagligi.py).

    NEDEN VAR: bu uygulamanın arızalarının çoğu "kod patladı" değil, "veri
    sessizce gelmiyor" biçiminde — hepsi 200 dönen boş yanıtlar. Bir gecelik
    elle denetimde bulunanlar: pay sahibi akışı aylardır 0 kayıt, fon kataloğu
    3 fonda takılı, halka arz tablosu hiç dolmamış, haberler 5 gün bayat.
    Hiçbiri hata logu üretmiyordu. Bu uç o denetimi kalıcı hale getirir.

    Gizli veri dönmez: yalnızca satır sayısı ve tarih.
    """
    from veri_sagligi import rapor
    return rapor(db)


# --- TEMETTÜ TAKVİMİ ---

@app.get("/api/dividend-calendar", response_model=List[DividendEventItem])
def get_dividend_calendar(
    upcoming_only: bool = True,
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """
    Yaklaşan nakit temettü ödemeleri (bkz. temettu_takvimi.py).

    `dividend_history` GEÇMİŞ ödemeleri tutar; burası şirketin KAP'a bildirdiği
    ödeme PLANIDIR. Uygulama katılım finansı odaklı olduğu için temettü merkezî
    bir kavram, ama kullanıcı bugüne kadar yalnızca geçmişi görebiliyordu.
    """
    bugun = bugun_tr()
    query = db.query(models.DividendEvent, models.Stock).join(
        models.Stock, models.Stock.id == models.DividendEvent.stock_id
    )
    if upcoming_only:
        query = query.filter(models.DividendEvent.payment_date >= bugun)
    query = query.filter(models.DividendEvent.payment_date <= bugun + timedelta(days=days))
    rows = query.order_by(models.DividendEvent.payment_date.asc()).all()
    if not rows:
        return []

    fiyatlar = _bulk_price_and_change(db, [stock.id for _, stock in rows])

    sonuc = []
    for olay, stock in rows:
        brut_tl = float(olay.gross_amount_per_share) if olay.gross_amount_per_share is not None else None
        fiyat, _ = fiyatlar.get(stock.id, (0.0, None))
        # Verim yalnızca HEM tutar HEM fiyat varken hesaplanır; birinin
        # eksikliğinde 0 ya da tahmin göstermek yanlış bilgi olurdu.
        verim = round((brut_tl / fiyat) * 100, 3) if (brut_tl and fiyat and fiyat > 0) else None
        sonuc.append(DividendEventItem(
            symbol=olay.symbol,
            company_name=stock.company_name,
            event_type=olay.event_type,
            payment_date=olay.payment_date,
            gross_rate_pct=float(olay.gross_rate_pct) if olay.gross_rate_pct is not None else None,
            net_rate_pct=float(olay.net_rate_pct) if olay.net_rate_pct is not None else None,
            gross_amount_per_share=brut_tl,
            currency=olay.currency or "TRY",
            source_url=olay.source_url,
            gross_yield_pct=verim,
            days_until=(olay.payment_date - bugun).days,
        ))
    return sonuc


# --- GENEL PİYASA HABERLERİ ---

@app.get("/api/market/news", response_model=List[MarketNewsItem])
def get_market_news(
    q: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = Query(40, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Türkçe finans/ekonomi haber akışı (bkz. haber_kaynaklari.py, 11 kaynak).

    NEDEN HİSSEDEN AYRI: çekilen haberlerin yalnızca küçük bir kısmı belirli
    bir hisseyle eşleşiyor (ölçüldü: 320 haberin 7'si). Eşleşmeyenleri atmak
    verinin çoğunu çöpe atmak olurdu; "bugün piyasada ne oldu" sorusunun
    cevabı bu akışta.
    """
    query = db.query(models.MarketNews)
    if source:
        query = query.filter(models.MarketNews.source == source)

    if q and q.strip():
        # ILIKE KULLANILMIYOR: Türkçe harf katlayamıyor (bkz. tr_fold ve
        # /api/stocks/search'teki aynı gerekçe). Akış birkaç yüz satır,
        # bellekte süzmek ölçülebilir bir maliyet getirmiyor.
        katlanmis = tr_fold(q.strip())
        adaylar = (
            query.order_by(models.MarketNews.published_at.desc())
            .limit(500)
            .all()
        )
        return [
            MarketNewsItem.model_validate(n) for n in adaylar
            if katlanmis in tr_fold(n.title or "") or katlanmis in tr_fold(n.summary or "")
        ][:limit]

    rows = query.order_by(models.MarketNews.published_at.desc()).limit(limit).all()
    return [MarketNewsItem.model_validate(n) for n in rows]


@app.get("/api/market/news/sources", response_model=List[str])
def get_market_news_sources(db: Session = Depends(get_db)):
    """Akışta hâlihazırda haberi bulunan kaynakların listesi (filtre kutusu için)."""
    rows = (
        db.query(models.MarketNews.source)
        .filter(models.MarketNews.source.isnot(None))
        .distinct()
        .order_by(models.MarketNews.source)
        .all()
    )
    return [r[0] for r in rows]


# --- TEFAS FONLARI ---

@app.get("/api/funds", response_model=List[FundResponse])
def get_funds(
    katilim_only: bool = False,
    q: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """
    TEFAS katılım fonları. `q` fon kodunda veya adında arar.

    ARAMA VE LİMİT NEDEN VAR: fon kataloğu elle yazılmış 3 fondan TEFAS
    taramasıyla 390 fona çıktı (bkz. tefas_client.discover_katilim_funds).
    Tamamını tek seferde döndürmek 120 KB'lık bir yanıt ve kullanıcı tarafında
    390 satırlık, gezinilemez bir liste demekti.
    """
    query = db.query(models.Fund)
    if katilim_only:
        query = query.filter_by(is_katilim_compliant=True)
    # Fon aramasında da ILIKE KULLANILMAZ: TEFAS fon adları tamamı büyük harf
    # Türkçedir ("ZİRAAT PORTFÖY ... KATILIM FONU") ve ILIKE "ziraat" için
    # sıfır sonuç döndürür (ölçüldü). Eşleştirme tr_fold ile Python tarafında
    # yapılır; katalog birkaç yüz satır olduğu için maliyeti önemsiz.
    if q and q.strip():
        katlanmis = tr_fold(q.strip())
        tum_fonlar = query.order_by(models.Fund.code.asc()).all()
        funds = [
            f for f in tum_fonlar
            if katlanmis in tr_fold(f.code or "") or katlanmis in tr_fold(f.name or "")
        ][:limit]
    else:
        funds = query.order_by(models.Fund.code.asc()).limit(limit).all()
    if not funds:
        return []

    # N+1 GİDERİLDİ: eskiden fon BAŞINA ayrı bir "son fiyat" sorgusu atılıyordu.
    # 3 fonluk katalogda görünmezdi, 390 fonda 390 sorgu oldu. Artık tek sorguda
    # tüm fonların son fiyatı çekilir.
    fund_ids = [f.id for f in funds]
    esik = date.today() - timedelta(days=30)
    fiyat_satirlari = (
        db.query(models.FundPrice)
        .filter(
            models.FundPrice.fund_id.in_(fund_ids),
            # Zaman penceresi ZORUNLU: fund_prices her gün büyür ve penceresiz
            # sorgu tüm geçmişi tarar (bkz. projem.md "bu koda dokunmadan önce").
            models.FundPrice.recorded_date >= esik,
        )
        .order_by(models.FundPrice.fund_id, models.FundPrice.recorded_date.desc())
        .all()
    )
    son_fiyat = {}
    for satir in fiyat_satirlari:
        # Sıralama sayesinde her fon için İLK görülen satır en yenisidir.
        son_fiyat.setdefault(satir.fund_id, satir)

    return [
        FundResponse(
            code=fund.code,
            name=fund.name,
            fund_type=fund.fund_type,
            risk_level=fund.risk_level,
            is_katilim_compliant=bool(fund.is_katilim_compliant),
            latest_price=(
                FundPriceResponse.model_validate(son_fiyat[fund.id])
                if fund.id in son_fiyat else None
            ),
        )
        for fund in funds
    ]


# --- HALKA ARZLAR (IPO) ---

@app.get("/api/ipos", response_model=List[IpoResponse])
def get_ipos(db: Session = Depends(get_db)):
    """
    Halka arz takvimi (bkz. ipo_client.py).

    Tablo uzun süre BOŞTU — onu dolduran hiçbir kod yoktu, kullanıcıya
    çalışmayan bir bölüm gösteriliyordu. Artık halkarz.com'dan günlük
    tazeleniyor.
    """
    return db.query(models.Ipo).order_by(models.Ipo.id.desc()).all()


# --- PORTFOLIO & TRADING ---

# Bu sayıya ulaşan "etkin pozisyon sayısı" tam çeşitlendirilmiş kabul edilir.
# (Etkin pozisyon = 1/HHI; eşit ağırlıklı 8 pozisyon ile aynı yoğunlaşma seviyesi.)
FULLY_DIVERSIFIED_POSITION_COUNT = 8


@app.get("/api/portfolio/analytics", response_model=PortfolioAnalyticsResponse)
def get_portfolio_analytics(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Kullanıcının portföyünün sektör dağılımını ve yoğunlaşma (konsantrasyon) riskini döner.

    Yoğunlaşma ölçütü olarak Herfindahl-Hirschman Endeksi (HHI) kullanılır:
    HHI = Σ(ağırlık²). Bunun tersi (1/HHI) "etkin pozisyon sayısı"nı verir — örneğin
    portföyün %90'ı tek hissedeyse 10 hisse tutulsa bile etkin pozisyon sayısı 1'e yakındır.
    Ağırlıklar yalnızca hisse değeri üzerinden hesaplanır (nakit ayrıca raporlanır),
    çünkü yoğunlaşma riski hisse pozisyonlarının dağılımıyla ilgilidir.
    """
    portfolios = db.query(models.Portfolio).filter_by(user_id=current_user.id, is_bot_portfolio=False).all()

    positions = []
    sector_totals: Dict[str, Dict[str, Any]] = {}
    katilim_value = 0.0
    stock_value = 0.0

    for item in portfolios:
        stock = item.stock
        value = float(item.quantity) * _get_latest_db_price(db, stock.id)
        if value <= 0:
            continue

        stock_value += value
        positions.append((stock.symbol, value))

        sector_name = stock.sector or "Diğer"
        bucket = sector_totals.setdefault(sector_name, {"value": 0.0, "count": 0})
        bucket["value"] += value
        bucket["count"] += 1

        if stock.is_katilim_compliant:
            katilim_value += value

    cash_balance = float(current_user.virtual_balance)
    total_portfolio_value = cash_balance + stock_value

    # Hisse yoksa yoğunlaşma/çeşitlendirme tanımsızdır; sıfır değerlerle döneriz.
    if stock_value <= 0:
        return PortfolioAnalyticsResponse(
            total_portfolio_value=round(total_portfolio_value, 2),
            cash_balance=round(cash_balance, 2),
            stock_value=0.0,
            cash_pct=100.0 if total_portfolio_value > 0 else 0.0,
            position_count=0,
            sectors=[],
            positions=[],
            top_position_symbol=None,
            top_position_pct=0.0,
            top_sector=None,
            top_sector_pct=0.0,
            effective_position_count=0.0,
            diversification_score=0,
            katilim_compliant_pct=0.0,
        )

    position_items = [
        PositionWeightItem(symbol=symbol, value=round(value, 2), pct=round(value / stock_value * 100, 2))
        for symbol, value in sorted(positions, key=lambda p: p[1], reverse=True)
    ]

    sector_items = [
        SectorAllocationItem(
            sector=name,
            value=round(data["value"], 2),
            pct=round(data["value"] / stock_value * 100, 2),
            position_count=data["count"],
        )
        for name, data in sorted(sector_totals.items(), key=lambda kv: kv[1]["value"], reverse=True)
    ]

    hhi = sum((value / stock_value) ** 2 for _, value in positions)
    effective_positions = 1 / hhi if hhi > 0 else 0.0
    diversification_score = int(
        round(min(1.0, effective_positions / FULLY_DIVERSIFIED_POSITION_COUNT) * 100)
    )

    return PortfolioAnalyticsResponse(
        total_portfolio_value=round(total_portfolio_value, 2),
        cash_balance=round(cash_balance, 2),
        stock_value=round(stock_value, 2),
        cash_pct=round(cash_balance / total_portfolio_value * 100, 2) if total_portfolio_value > 0 else 0.0,
        position_count=len(positions),
        sectors=sector_items,
        positions=position_items,
        top_position_symbol=position_items[0].symbol,
        top_position_pct=position_items[0].pct,
        top_sector=sector_items[0].sector,
        top_sector_pct=sector_items[0].pct,
        effective_position_count=round(effective_positions, 2),
        diversification_score=diversification_score,
        katilim_compliant_pct=round(katilim_value / stock_value * 100, 2),
    )

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

    reserved = _reserved_cash_for_pending_buys(db, current_user.id)
    return PortfolioResponse(
        balance=round(float(current_user.virtual_balance), 2),
        reserved_balance=round(reserved, 2),
        available_balance=round(float(current_user.virtual_balance) - reserved, 2),
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

        # Komisyon: alımda maliyeti artırır, satımda geliri azaltır. Oran ve
        # hesap constants.py + transactions.py'de tek yerde tanımlı; backtest de
        # aynısını kullanır (bkz. constants.KOMISYON_ORANI_PCT).
        brut_tutar, komisyon, total_cost = alim_maliyeti(trade.quantity, current_price)
        portfolio_entry = db.query(models.Portfolio).filter_by(
            user_id=current_user.id, stock_id=stock.id, is_bot_portfolio=False
        ).first()

        if action == "AL":
            # Bakiye kontrolü KOMİSYON DAHİL yapılır; aksi halde bakiyesi tam
            # yetecek bir alım komisyon yüzünden bakiyeyi eksiye düşürürdü.
            if float(current_user.virtual_balance) < total_cost:
                raise HTTPException(
                    status_code=400,
                    detail=f"Yetersiz sanal bakiye. Gerekli: {total_cost:.2f} TL "
                           f"({brut_tutar:.2f} TL + {komisyon:.2f} TL komisyon).",
                )

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
                    # Komisyon DAHİL birim maliyet — total_cost komisyonu içerir.
                    average_cost=total_cost / trade.quantity,
                    is_bot_portfolio=False,
                )
                db.add(new_entry)

            record_transaction(
                db, user_id=current_user.id, stock_id=stock.id, action_type="AL",
                quantity=trade.quantity, price=current_price, source="MANUAL",
                commission=komisyon,
            )
            db.commit()
            return {
                "message": f"{trade.quantity} adet {stock.symbol} başarıyla alındı. "
                           f"Komisyon: {komisyon:.2f} TL.",
                "balance": current_user.virtual_balance,
                "commission": komisyon,
            }

        else:  # SAT
            if not portfolio_entry or float(portfolio_entry.quantity) < trade.quantity:
                raise HTTPException(status_code=400, detail="Yetersiz hisse miktarı.")

            _brut, komisyon, revenue = satim_geliri(trade.quantity, current_price)
            current_user.virtual_balance = float(current_user.virtual_balance) + revenue

            # Gerçekleşen K/Z için ortalama maliyet SATIŞTAN ÖNCE okunmalı: pozisyon
            # tamamen satıldığında satır siliniyor ve bu bilgi geri getirilemiyor.
            avg_cost_before_sale = float(portfolio_entry.average_cost)

            remaining_qty = float(portfolio_entry.quantity) - trade.quantity
            # Decimal->float dönüşümü + float çıkarma "tam sıfır" yerine 1e-13 gibi bir
            # kalıntı üretebilir; == 0 karşılaştırması bu durumda pozisyonu silmeyip
            # "hayalet" (neredeyse sıfır ama sıfır değil) bir kayıt bırakır. orders.py'deki
            # eşdeğer kod (_execute_single_order) zaten <= 0 kullanıyor, burada da aynısı.
            if remaining_qty <= 0:
                db.delete(portfolio_entry)
            else:
                portfolio_entry.quantity = remaining_qty

            record_transaction(
                db, user_id=current_user.id, stock_id=stock.id, action_type="SAT",
                quantity=trade.quantity, price=current_price,
                average_cost=avg_cost_before_sale, source="MANUAL",
                commission=komisyon,
            )
            db.commit()
            return {
                "message": f"{trade.quantity} adet {stock.symbol} başarıyla satıldı. "
                           f"Komisyon: {komisyon:.2f} TL.",
                "balance": current_user.virtual_balance,
                "commission": komisyon,
            }
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

def _reserved_cash_for_pending_buys(db: Session, user_id: int, exclude_order_id: Optional[int] = None) -> float:
    """
    Bekleyen alış emirlerinin bakiyeden bloke ettiği toplam tutar.

    LIMIT_BUY'da limit fiyatı, SCHEDULED_BUY'da güncel piyasa fiyatı esas alınır
    (zamanlı emirde gerçekleşme fiyatı önceden bilinemez, tahmini bloke uygulanır).
    `exclude_order_id` emir güncellenirken emrin kendi eski tutarını hariç tutmak içindir.
    """
    query = db.query(models.PendingOrder).filter(
        models.PendingOrder.user_id == user_id,
        models.PendingOrder.status == "PENDING",
        models.PendingOrder.order_type.in_(("LIMIT_BUY", "SCHEDULED_BUY")),
    )
    if exclude_order_id is not None:
        query = query.filter(models.PendingOrder.id != exclude_order_id)

    total = 0.0
    for o in query.all():
        price = float(o.target_price) if o.target_price is not None else (_get_latest_db_price(db, o.stock_id) or 0.0)
        total += float(o.quantity) * price
    return total


def _reserved_shares_for_pending_sells(
    db: Session, user_id: int, stock_id: int, order_type: str, exclude_order_id: Optional[int] = None
) -> float:
    """
    Bir hisse için bekleyen satış emirlerinde bloke edilen lot adedi — TÜRE GÖRE ayrı.

    LIMIT_SELL (kâr-al), STOP_LOSS_SELL (zarar-kes) ve TRAILING_STOP_SELL
    (iz süren zarar-kes) bilerek AYRI havuzlarda sayılır: aynı pozisyona
    hem yukarıdan kâr-al hem aşağıdan zarar-kes koymak standart risk
    yönetimi kurgusudur ve ikisi aynı havuzda blokelenirse bu mümkün
    olmazdı. Biri tetiklendiğinde diğerleri otomatik iptal edilir (OCO
    mantığı bkz. orders.py::_execute_single_order), böylece açıkta emir
    kalmaz.

    Aynı TÜRDEN emirlerin toplamı ise sahip olunan lotu aşamaz — aksi halde
    kullanıcı tek pozisyon için iki ayrı tam-lot kâr-al emri verebilirdi.
    """
    query = db.query(func.coalesce(func.sum(models.PendingOrder.quantity), 0)).filter(
        models.PendingOrder.user_id == user_id,
        models.PendingOrder.stock_id == stock_id,
        models.PendingOrder.status == "PENDING",
        models.PendingOrder.order_type == order_type,
    )
    if exclude_order_id is not None:
        query = query.filter(models.PendingOrder.id != exclude_order_id)
    return float(query.scalar() or 0)


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

    # ── Bakiye / pozisyon bloke kontrolü ────────────────────────────────────
    # Gerçek aracı kurumlarda (Midas dahil) bekleyen bir alış emri, gereken tutarı
    # bakiyeden BLOKE eder; bloke edilebilir para yoksa emir hiç oluşturulamaz.
    # Bizde bu kontrol yalnızca emir GERÇEKLEŞİRKEN yapılıyordu, dolayısıyla
    # kullanıcı bakiyesinin katlarca üstünde emir kuyruğa alabiliyordu (hepsi
    # tetiklendiğinde biri hariç hepsi "Yetersiz bakiye" ile başarısız oluyordu).
    # Aynı sorun satışta da vardı: sahip olunmayan lot için emir girilebiliyordu.
    if order.order_type in ("LIMIT_BUY", "SCHEDULED_BUY"):
        # Referans fiyat: limit emirde limit fiyatı, zamanlı emirde güncel piyasa fiyatı
        # (zamanlı emirde fiyat bilinmediği için tahmini bloke uygulanır).
        ref_price = float(order.target_price) if order.target_price is not None else _get_latest_db_price(db, stock.id)
        if not ref_price:
            raise HTTPException(status_code=400, detail="Hisse fiyatı bulunamadı, emir oluşturulamadı.")

        required = float(order.quantity) * ref_price
        reserved = _reserved_cash_for_pending_buys(db, current_user.id)
        available = float(current_user.virtual_balance) - reserved

        if required > available:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Yetersiz bakiye. Bu emir için {required:,.2f} TL gerekiyor; "
                    f"kullanılabilir bakiyeniz {available:,.2f} TL "
                    f"(bekleyen emirlerde bloke: {reserved:,.2f} TL)."
                ),
            )
    else:  # LIMIT_SELL (kâr-al) / STOP_LOSS_SELL (zarar-kes)
        position = db.query(models.Portfolio).filter_by(
            user_id=current_user.id, stock_id=stock.id, is_bot_portfolio=False
        ).first()
        owned = float(position.quantity) if position else 0.0
        reserved_qty = _reserved_shares_for_pending_sells(db, current_user.id, stock.id, order.order_type)
        sellable = owned - reserved_qty

        if float(order.quantity) > sellable:
            tur = {
                "STOP_LOSS_SELL": "zarar-kes",
                "TRAILING_STOP_SELL": "iz süren zarar-kes",
            }.get(order.order_type, "kâr-al")
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Yetersiz hisse. {stock.symbol} için satılabilir adet: {sellable:g} "
                    f"(sahip: {owned:g}, bekleyen {tur} emirlerinde bloke: {reserved_qty:g})."
                ),
            )
    # ────────────────────────────────────────────────────────────────────────

    # TRAILING_STOP_SELL'in başlangıç "en yüksek fiyatı" emir oluşturulduğu ANDAKİ
    # fiyattır -- aksi halde bir sonraki 5 dakikalık fiyat taramasına kadar
    # highest_price_seen boş kalır ve emir o süre boyunca hiç tetiklenemez.
    baslangic_en_yuksek = None
    if order.order_type == "TRAILING_STOP_SELL":
        baslangic_en_yuksek = _get_latest_db_price(db, stock.id) or None

    new_order = models.PendingOrder(
        user_id=current_user.id,
        stock_id=stock.id,
        order_type=order.order_type,
        target_price=order.target_price,
        execution_time=order.execution_time.replace(tzinfo=None) if order.execution_time else None,
        quantity=order.quantity,
        status="PENDING",
        trail_pct=order.trail_pct,
        highest_price_seen=baslangic_en_yuksek,
        recurrence=order.recurrence,
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
        trail_pct=float(new_order.trail_pct) if new_order.trail_pct is not None else None,
        highest_price_seen=float(new_order.highest_price_seen) if new_order.highest_price_seen is not None else None,
        recurrence=new_order.recurrence, execution_count=new_order.execution_count or 0,
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
            trail_pct=float(o.trail_pct) if o.trail_pct is not None else None,
            highest_price_seen=float(o.highest_price_seen) if o.highest_price_seen is not None else None,
            recurrence=o.recurrence, execution_count=o.execution_count or 0,
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
        # STOP_LOSS_SELL eskiden bu listede yoktu -- kullanıcı zarar-kes fiyatını
        # güncelleyemiyor, iptal edip yeniden kurmak zorunda kalıyordu (fark edilip
        # düzeltildi, trailing stop eklenirken).
        if req.target_price is not None and order.order_type in ("LIMIT_BUY", "LIMIT_SELL", "STOP_LOSS_SELL"):
            order.target_price = req.target_price
        if req.execution_time is not None and order.order_type == "SCHEDULED_BUY":
            order.execution_time = req.execution_time.replace(tzinfo=None)
        if req.trail_pct is not None and order.order_type == "TRAILING_STOP_SELL":
            order.trail_pct = req.trail_pct

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
            trail_pct=float(order.trail_pct) if order.trail_pct is not None else None,
            highest_price_seen=float(order.highest_price_seen) if order.highest_price_seen is not None else None,
            recurrence=order.recurrence, execution_count=order.execution_count or 0,
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


# ---------------------------------------------------------------------------
# Web Push abonelikleri
# ---------------------------------------------------------------------------
@app.get("/api/push/status", response_model=PushStatusResponse)
def get_push_status(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Tarayıcının aboneliği kurmak için ihtiyaç duyduğu VAPID açık anahtarı ve
    kullanıcının kaç cihazının kayıtlı olduğu.

    Sunucuda anahtar tanımlı değilse `configured=false` döner ve arayüz push
    bölümünü hiç göstermez — çalışmayacak bir düğme göstermektense.
    """
    import push
    count = db.query(models.PushSubscription).filter_by(user_id=current_user.id).count()
    return PushStatusResponse(
        configured=push.is_configured(),
        public_key=push.VAPID_PUBLIC_KEY or None,
        device_count=count,
    )


@app.post("/api/push/subscribe")
def subscribe_push(
    req: PushSubscribeRequest,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Cihazı kaydeder. Aynı endpoint zaten kayıtlıysa güncellenir.

    Endpoint benzersizdir ama SAHİBİ DEĞİŞEBİLİR: ortak bir cihazda ikinci bir
    kullanıcı giriş yaparsa tarayıcı aynı endpoint'i üretir. Bu durumda kayıt
    yeni kullanıcıya devredilir; aksi halde bildirimler yanlış kişiye giderdi.
    """
    existing = db.query(models.PushSubscription).filter_by(endpoint=req.endpoint).first()
    if existing:
        existing.user_id = current_user.id
        existing.p256dh = req.p256dh
        existing.auth = req.auth
        existing.failure_count = 0
    else:
        db.add(models.PushSubscription(
            user_id=current_user.id,
            endpoint=req.endpoint,
            p256dh=req.p256dh,
            auth=req.auth,
            user_agent=(request.headers.get("user-agent") or "")[:300],
        ))
    db.commit()
    count = db.query(models.PushSubscription).filter_by(user_id=current_user.id).count()
    return {"success": True, "device_count": count}


@app.post("/api/push/unsubscribe")
def unsubscribe_push(
    req: PushSubscribeRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bu cihazın aboneliğini siler. Kullanıcının diğer cihazları etkilenmez."""
    deleted = (
        db.query(models.PushSubscription)
        .filter_by(endpoint=req.endpoint, user_id=current_user.id)
        .delete()
    )
    db.commit()
    return {"success": True, "deleted": deleted}


@app.post("/api/push/test")
@limiter.limit("5/minute")
def send_test_push(
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deneme bildirimi. Kullanıcının izni verdikten sonra bildirimlerin gerçekten
    ulaştığını görmesi için — iOS'ta özellikle gerekli, çünkü orada izin
    verilmiş görünse bile PWA kurulu değilse bildirim ulaşmaz.
    """
    import push
    if not push.is_configured():
        raise HTTPException(status_code=503, detail="Push bildirimleri sunucuda yapılandırılmamış.")
    sent = push.send_to_user(db, current_user.id, push.build_payload(
        "Bildirimler çalışıyor",
        "Alarm kurduğunuz hisseler hareket ettiğinde bu şekilde haber vereceğiz.",
        url="/ayarlar",
        tag="test",
    ))
    if sent == 0:
        raise HTTPException(status_code=400, detail="Kayıtlı cihaz bulunamadı veya gönderim başarısız oldu.")
    return {"success": True, "delivered": sent}


@app.get("/api/stocks/{symbol}/indicators", response_model=ExtraIndicatorsResponse)
def get_extra_indicators(symbol: str, db: Session = Depends(get_db)):
    """
    Stochastic, ADX ve OBV — GÜNLÜK OHLCV barlarından.

    Mevcut RSI/MACD/SMA göstergeleri gün içi anlık fiyat kayıtlarından
    hesaplanıyor ama o tabloda yüksek/düşük yok. Stochastic ve ADX tanımı
    gereği gün içi yüksek ve düşüğü kullandığı için burada ayrı bir kaynaktan
    (stock_prices_daily) hesaplanır.
    """
    from indicators import compute_extra_indicators
    return ExtraIndicatorsResponse(**compute_extra_indicators(db, symbol))


@app.get("/api/stocks/{symbol}/indicator-series", response_model=IndicatorSeriesResponse)
def get_indicator_series(symbol: str, range: str = "1Y", db: Session = Depends(get_db)):
    """
    Grafik üzerine bindirilecek (SMA/EMA/Bollinger) ve altına panel olarak
    eklenecek (RSI/MACD/Stochastic/ADX/OBV) göstergelerin TAM ZAMAN SERİSİ.
    TradingView/Midas'taki "gösterge ekle" özelliğinin karşılığı.

    1D desteklenmez: gün içi fiyat tikinde yüksek/düşük yok, göstergelerin
    çoğu (Bollinger, Stochastic, ADX) tanımı gereği bunlara ihtiyaç duyar.
    """
    from indicator_series import compute_indicator_series
    return IndicatorSeriesResponse(**compute_indicator_series(db, symbol, range))


@app.post("/api/stocks/{symbol}/custom-indicator", response_model=CustomFormulaResponse)
@limiter.limit("30/minute")
def compute_custom_indicator_series(
    request: Request,
    symbol: str,
    body: CustomFormulaRequest,
    range: str = "1Y",
    db: Session = Depends(get_db),
):
    """
    Kullanıcının kendi yazdığı formülü (ör. "close - sma(20)") gösterge
    olarak hesaplar -- TradingView Pine Script'inin çok basitleştirilmiş,
    güvenli karşılığı.

    GÜVENLİK: formül asla eval()/exec() ile çalıştırılmaz; yalnızca
    whitelist'li bir AST yorumlayıcısından geçer (bkz. custom_indicator.py).
    Hız sınırı, ölçüm gerektirmeyen ama yine de tekrar tekrar istek
    atılabilecek bu uca ekstra bir savunma katmanıdır.
    """
    from custom_indicator import compute_custom_formula
    return CustomFormulaResponse(**compute_custom_formula(db, symbol, range, body.formula))


@app.get("/api/backtest/strategies")
def list_backtest_strategies():
    """Geri testte seçilebilecek stratejiler ve varsayılan parametreleri."""
    from backtest import STRATEJILER, VARSAYILAN_KOMISYON_PCT
    return {
        "strategies": [
            {"key": k, "label": v["label"], "description": v["description"], "params": v["params"]}
            for k, v in STRATEJILER.items()
        ],
        "default_commission_pct": VARSAYILAN_KOMISYON_PCT,
    }


@app.get("/api/stocks/{symbol}/backtest", response_model=BacktestResponse)
@limiter.limit("20/minute")
def run_strategy_backtest(
    request: Request,
    symbol: str,
    strategy: str = "SMA_CROSS",
    years: int = 3,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Bir stratejinin geçmişte ne yapacağını ölçer.

    Hız sınırı var: her çağrı 5 yıla kadar günlük barı okuyup gösterge
    hesaplıyor, kullanıcı parametreleri hızla değiştirdiğinde sunucuyu
    gereksiz yere yorabilir.
    """
    from backtest import run_backtest
    years = max(1, min(5, years))
    return BacktestResponse(**run_backtest(db, symbol, strategy, years=years))


@app.get("/api/portfolio/scorecard", response_model=ScorecardResponse)
def get_portfolio_scorecard(
    year: Optional[int] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    İşlem performans karnesi: gerçekleşen kâr/zarar, isabet oranı, ortalama
    tutma süresi, en iyi/en kötü işlem ve hisse bazlı kırılım.

    Yeni veri çekilmez; `transactions` tablosundaki mevcut kayıtlar okunur.
    `year` verilirse yalnızca o yıl özetlenir (tutma süresi hesabı yine tüm
    geçmişi kullanır, aksi halde önceki yıldan taşınan pozisyonlar eşleşmezdi).
    """
    from scorecard import build_scorecard
    return ScorecardResponse(**build_scorecard(db, current_user.id, year))


@app.get("/api/portfolio/report")
@limiter.limit("10/minute")
def get_portfolio_report_pdf(
    request: Request, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """
    Portföy karnesini indirilebilir bir PDF'e döker. `/api/portfolio` ve
    `/api/portfolio/scorecard` ile AYNI fonksiyonlar doğrudan çağrılır --
    rapordaki rakamlar bu yüzden uygulamanın geri kalanıyla her zaman
    birebir tutarlıdır, ikinci bir hesaplama yolu yoktur.
    """
    from scorecard import build_scorecard
    from report_pdf import build_portfolio_report_pdf

    portfolio = get_portfolio(current_user, db).model_dump()
    scorecard = build_scorecard(db, current_user.id, None)
    pdf_bytes = build_portfolio_report_pdf(current_user.username, portfolio, scorecard)

    tarih = datetime.utcnow().strftime("%Y-%m-%d")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="portfoy-raporu-{tarih}.pdf"'},
    )


@app.get("/api/portfolio/counterfactual", response_model=CounterfactualResponse)
def get_portfolio_counterfactual(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    "Sen olmasan ne olurdu?" karnesi — kullanıcının gerçek portföy değerini
    üç alternatif senaryoyla kıyaslar (bkz. counterfactual.py):
    hiç işlem yapmasaydı, sermayeyi toptan BIST 100'e yatırsaydı, ya da
    aylık eşit parçalarla (DCA) yatırsaydı.

    Yeterli veri yoksa (yeni hesap, endeks verisi henüz birikmemiş)
    available=False döner — uydurma bir sayı göstermek yerine özellik
    tümüyle gizlenir.
    """
    from counterfactual import compute_counterfactual

    actual_value = _portfolio_value(db, current_user.id, False, float(current_user.virtual_balance))
    sonuc = compute_counterfactual(db, current_user, actual_value)
    if sonuc is None:
        return CounterfactualResponse(
            available=False,
            reason="Kıyaslama için yeterli işlem/endeks geçmişi henüz yok.",
        )
    return CounterfactualResponse(available=True, **sonuc)


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
            katilim_status=stock.katilim_status,
            purification_rate=float(stock.purification_rate or 0.0),
            added_at=row.created_at,
            target_price=float(row.target_price) if row.target_price is not None else None,
            note=row.note,
            # Hedefe uzaklık: pozitifse hedef güncel fiyatın ÜSTÜNDE (yükselmesi
            # bekleniyor), negatifse altında.
            distance_to_target_pct=(
                round(((float(row.target_price) - current_price) / current_price) * 100, 2)
                if (row.target_price is not None and current_price > 0) else None
            ),
        ))
    return items


@app.patch("/api/watchlist/{symbol}", response_model=WatchlistItemResponse)
def update_watchlist_item(
    symbol: str,
    payload: WatchlistUpdateRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    İzleme listesi kaydına hedef fiyat / not yazar.

    Kullanıcının kendi takip notudur; alarm sisteminden (StockNotificationPreference)
    AYRIDIR ve bildirim üretmez. Gönderilmeyen alan değiştirilmez; temizlemek için
    clear_target / clear_note bayrakları kullanılır (null göndermek "değiştirme"
    anlamına geldiği için ayrı bir sinyal gerekiyor).
    """
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    row = db.query(models.Watchlist).filter_by(user_id=current_user.id, stock_id=stock.id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Bu hisse izleme listenizde değil.")

    if payload.clear_target:
        row.target_price = None
    elif payload.target_price is not None:
        row.target_price = payload.target_price

    if payload.clear_note:
        row.note = None
    elif payload.note is not None:
        row.note = payload.note.strip() or None

    db.commit()

    current_price = _get_latest_db_price(db, stock.id) or 0.0
    return WatchlistItemResponse(
        symbol=stock.symbol,
        company_name=stock.company_name,
        current_price=round(current_price, 2),
        price_change_pct=None,
        is_katilim_compliant=bool(stock.is_katilim_compliant),
        katilim_status=stock.katilim_status,
        purification_rate=float(stock.purification_rate or 0.0),
        added_at=row.created_at,
        target_price=float(row.target_price) if row.target_price is not None else None,
        note=row.note,
        distance_to_target_pct=(
            round(((float(row.target_price) - current_price) / current_price) * 100, 2)
            if (row.target_price is not None and current_price > 0) else None
        ),
    )


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
        if was_active:
            close_open_bot_session(db, current_user.id, f"Strateji değiştirildi: {config['label']}.")
            open_bot_session(db, current_user.id, req.time_frame, user_bot.risk_profile or DEFAULT_RISK_MODE)

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
            close_open_bot_session(db, current_user.id, "Kullanıcı tarafından durduruldu.")

        user_bot.is_active = req.is_active
        if req.is_active and not was_active:
            # Bot yeniden başlatılıyorsa süresini de sıfırla
            config = get_strategy_config(user_bot.time_frame or "1D")
            user_bot.started_at = datetime.utcnow()
            user_bot.ends_at = datetime.utcnow() + config["duration"]
            open_bot_session(db, current_user.id, user_bot.time_frame or "1D", user_bot.risk_profile or DEFAULT_RISK_MODE)

    db.commit()
    db.refresh(user_bot)
    return get_user_bot_status(current_user, db)


@app.get("/api/user/bot/sessions", response_model=List[BotSessionResponse])
def get_user_bot_sessions(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Kullanıcının kişisel botunun başlatılıp durdurulduğu/süresi dolduğu her dönemi
    (oturum) listeler — en yeni önce. UI'da soldaki oturum listesi buradan gelir.
    """
    sessions = db.query(models.BotSession)\
        .filter_by(user_id=current_user.id)\
        .order_by(models.BotSession.started_at.desc())\
        .all()

    result = []
    for s in sessions:
        end_bound = s.ended_at or datetime.utcnow()
        trade_count = db.query(models.BotLog).filter(
            models.BotLog.user_id == current_user.id,
            models.BotLog.created_at >= s.started_at,
            models.BotLog.created_at <= end_bound,
        ).count()
        config = get_strategy_config(s.time_frame)
        risk_config = get_risk_mode_config(s.risk_mode)
        result.append(BotSessionResponse(
            id=s.id, time_frame=s.time_frame, time_frame_label=config["label"],
            risk_mode=s.risk_mode, risk_mode_label=risk_config["label"] if s.risk_mode else None,
            started_at=s.started_at, ended_at=s.ended_at, end_reason=s.end_reason,
            is_active=s.ended_at is None, trade_count=trade_count,
        ))
    return result


@app.get("/api/user/bot/logs", response_model=List[BotLogResponse])
def get_user_bot_logs(
    session_id: Optional[int] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Giriş yapan kullanıcının kişisel AI botunun işlem günlüğünü döner.
    session_id verilirse yalnızca o oturumun zaman aralığındaki (started_at..ended_at)
    işlemler döner. Her SAT kaydı için, aynı hissede ondan önceki en yakın AL kaydına
    göre pozisyonun kaç gün açık kaldığı (days_held) hesaplanır.
    """
    # AL/SAT eşleştirmesi (days_held) için filtre uygulanmadan tüm geçmiş çekilir,
    # eşleştirme sonrası istenen oturuma göre daraltılıp son 200 kayıt döndürülür.
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

    if session_id is not None:
        session = db.query(models.BotSession).filter_by(id=session_id, user_id=current_user.id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
        end_bound = session.ended_at or datetime.utcnow()
        filtered = [log for log in all_logs if session.started_at <= log.created_at <= end_bound]
    else:
        filtered = all_logs

    filtered.sort(key=lambda log: log.created_at, reverse=True)
    filtered = filtered[:200]

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


@app.get("/api/portfolio/performance", response_model=List[BotPerformancePoint])
def get_user_portfolio_performance(
    days: int = 90,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Kullanıcının kendi portföyünün (bot değil) gün sonu değer geçmişini döner.
    Kayıtlar scheduler'daki snapshot_user_portfolios_job tarafından hafta içi
    her akşam yazılır; bu yüzden yeni bir hesapta grafik birkaç gün sonra dolar.
    """
    cutoff = date.today() - timedelta(days=max(1, min(days, 365)))
    rows = (
        db.query(models.UserPerformanceHistory)
        .filter(
            models.UserPerformanceHistory.user_id == current_user.id,
            models.UserPerformanceHistory.recorded_date >= cutoff,
        )
        .order_by(models.UserPerformanceHistory.recorded_date.asc())
        .all()
    )
    return [
        BotPerformancePoint(
            date=r.recorded_date,
            total_portfolio_value=float(r.total_portfolio_value),
        )
        for r in rows
    ]


@app.get("/api/portfolio/transactions", response_model=TransactionHistoryResponse)
def get_user_transactions(
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Kullanıcının kendi (bot dışı) gerçekleşmiş alım/satım geçmişi ve gerçekleşen
    kâr/zarar özeti. En yeni işlem başta döner.

    Özet alanları TÜM geçmiş üzerinden hesaplanır, dönen `items` listesi ise
    `limit` ile kırpılır — aksi halde kullanıcı sayfayı her açtığında toplam
    kârı, kaç işlem gösterdiğimize göre değişirdi.
    """
    capped_limit = max(1, min(limit, 500))

    base_query = (
        db.query(models.Transaction, models.Stock)
        .join(models.Stock, models.Stock.id == models.Transaction.stock_id)
        .filter(models.Transaction.user_id == current_user.id)
    )
    # Tarih aralığı filtresi. end_date GÜN SONUNA kadar dahil edilir: kullanıcı
    # "31 Mart"ı seçtiğinde 31 Mart'taki işlemleri de görmek ister, oysa
    # created_at <= 2026-03-31 00:00 o günü tamamen dışarıda bırakırdı.
    if start_date:
        base_query = base_query.filter(
            models.Transaction.created_at >= datetime.combine(start_date, datetime.min.time())
        )
    if end_date:
        base_query = base_query.filter(
            models.Transaction.created_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time())
        )

    # id.desc() ikincil sıralama olarak şart: aynı saniye içinde yapılan iki işlemde
    # created_at eşitlenebiliyor ve tek başına ORDER BY created_at deterministik
    # olmayan bir sıra döndürüyor (sayfa her yenilendiğinde farklı sıra).
    rows = (
        base_query
        .order_by(models.Transaction.created_at.desc(), models.Transaction.id.desc())
        .limit(capped_limit)
        .all()
    )

    # --- Özet: SEÇİLİ ARALIĞIN tamamı üzerinden (limit'ten bağımsız) ---
    # Not: tarih filtresi verildiğinde özet de o aralığı yansıtır; aksi halde
    # "Mart ayı" seçen kullanıcıya tüm zamanların kârı gösterilirdi.
    summary_query = db.query(models.Transaction).filter(models.Transaction.user_id == current_user.id)
    if start_date:
        summary_query = summary_query.filter(
            models.Transaction.created_at >= datetime.combine(start_date, datetime.min.time())
        )
    if end_date:
        summary_query = summary_query.filter(
            models.Transaction.created_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time())
        )
    all_tx = summary_query.all()

    total_realized = 0.0
    total_buy = 0.0
    total_sell = 0.0
    buy_count = 0
    sell_count = 0
    winning_sells = 0

    for tx in all_tx:
        amount = float(tx.total_amount)
        if tx.action_type == "AL":
            buy_count += 1
            total_buy += amount
        else:
            sell_count += 1
            total_sell += amount
            if tx.realized_pnl is not None:
                pnl = float(tx.realized_pnl)
                total_realized += pnl
                if pnl > 0:
                    winning_sells += 1

    win_rate = round((winning_sells / sell_count) * 100, 2) if sell_count else None

    items = []
    for tx, stock in rows:
        # Yüzdesel getiri, satılan pozisyonun MALİYETİNE oranla hesaplanır
        # (satış hasılatına değil) — "10 TL'ye alıp 12 TL'ye sattım" = %20.
        pnl_pct = None
        if tx.realized_pnl is not None and tx.average_cost_at_trade:
            cost_basis = float(tx.average_cost_at_trade) * float(tx.quantity)
            if cost_basis > 0:
                pnl_pct = round((float(tx.realized_pnl) / cost_basis) * 100, 2)

        items.append(TransactionItem(
            id=tx.id,
            symbol=stock.symbol,
            company_name=stock.company_name,
            action_type=tx.action_type,
            quantity=float(tx.quantity),
            price=float(tx.price),
            total_amount=float(tx.total_amount),
            commission=float(tx.commission) if tx.commission is not None else None,
            realized_pnl=float(tx.realized_pnl) if tx.realized_pnl is not None else None,
            realized_pnl_pct=pnl_pct,
            average_cost_at_trade=float(tx.average_cost_at_trade) if tx.average_cost_at_trade is not None else None,
            source=tx.source,
            created_at=tx.created_at,
        ))

    return TransactionHistoryResponse(
        total_realized_pnl=round(total_realized, 2),
        total_buy_amount=round(total_buy, 2),
        total_sell_amount=round(total_sell, 2),
        buy_count=buy_count,
        sell_count=sell_count,
        win_rate=win_rate,
        items=items,
    )


@app.get("/api/portfolio/transactions/export")
def export_transactions_csv(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    İşlem geçmişini CSV olarak indirir (Excel'de açılabilir).

    Kodlama olarak UTF-8 BOM kullanılır: Excel, BOM'suz UTF-8 dosyaları
    Windows'ta ANSI varsayıp Türkçe karakterleri bozuyor ("Ç" -> "Ã‡").
    Ayraç olarak noktalı virgül seçilir — Türkçe Windows yerel ayarında
    Excel virgülü ondalık ayıracı sayar ve virgülle ayrılmış dosyayı tek
    sütuna sıkıştırır.
    """
    import csv
    import io as _io

    query = (
        db.query(models.Transaction, models.Stock)
        .join(models.Stock, models.Stock.id == models.Transaction.stock_id)
        .filter(models.Transaction.user_id == current_user.id)
    )
    # Ekrandaki tarih aralığı neyse CSV de onu indirmeli; aksi halde kullanıcı
    # "Mart" filtresiyle bakarken tüm geçmişi indirmiş olurdu.
    if start_date:
        query = query.filter(models.Transaction.created_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(models.Transaction.created_at < datetime.combine(end_date + timedelta(days=1), datetime.min.time()))
    rows = query.order_by(models.Transaction.created_at.desc(), models.Transaction.id.desc()).all()

    buf = _io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow([
        "Tarih", "Hisse", "Sirket", "Islem", "Adet", "Fiyat (TL)",
        "Tutar (TL)", "Ortalama Maliyet (TL)", "Gerceklesen K/Z (TL)", "Kaynak",
    ])

    def _tr_num(v):
        """Türkçe Excel ondalık ayıracı virgüldür; nokta ile yazılan sayı metin sayılır."""
        return "" if v is None else f"{float(v):.2f}".replace(".", ",")

    for tx, stock in rows:
        writer.writerow([
            tx.created_at.strftime("%d.%m.%Y %H:%M") if tx.created_at else "",
            stock.symbol,
            stock.company_name,
            tx.action_type,
            _tr_num(tx.quantity),
            _tr_num(tx.price),
            _tr_num(tx.total_amount),
            _tr_num(tx.average_cost_at_trade),
            _tr_num(tx.realized_pnl),
            "Bekleyen Emir" if tx.source == "LIMIT_ORDER" else "Manuel",
        ])

    content = "﻿" + buf.getvalue()
    filename = f"islem-gecmisi-{date.today().isoformat()}.csv"
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/stocks/{symbol}/financials", response_model=FinancialStatementsResponse)
def get_stock_financials(symbol: str, db: Session = Depends(get_db)):
    """
    Hissenin çeyreklik finansal tabloları (gelir tablosu + bilanço + nakit akışı).

    Ücretli platformların paket içinde sunduğu "finansal tablolar" özelliğinin
    karşılığıdır. Veriler financials.py tarafından gece işinde doldurulur.

    Büyüme oranları bir önceki YILIN AYNI ÇEYREĞİNE göre hesaplanır (yıllık
    bazda, YoY): çeyrekler mevsimsellik taşıdığı için Q1'i Q4 ile kıyaslamak
    yanıltıcı olurdu (ör. perakendede yılbaşı çeyreği doğal olarak yüksektir).
    """
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    rows = (
        db.query(models.FinancialStatement)
        .filter(models.FinancialStatement.stock_id == stock.id)
        .order_by(models.FinancialStatement.period_end.desc())
        .all()
    )

    # Yıllık karşılaştırma için dönem sonuna göre indeks.
    by_period = {r.period_end: r for r in rows}

    def _f(v):
        return float(v) if v is not None else None

    def _yoy(current, prev):
        """Yıllık büyüme (%). Önceki dönem sıfır/negatifse yüzde anlamsızdır."""
        if current is None or prev is None or prev <= 0:
            return None
        return round(((current - prev) / prev) * 100, 2)

    periods: List[FinancialPeriodItem] = []
    for r in rows:
        # Geçen yılın aynı çeyreği: ~365 gün önce, en yakın kayıt (±20 gün).
        target = r.period_end - timedelta(days=365)
        prev_row = None
        best_gap = 21
        for p, cand in by_period.items():
            gap = abs((p - target).days)
            if gap < best_gap:
                best_gap, prev_row = gap, cand

        revenue, net_income = _f(r.revenue), _f(r.net_income)
        quarter = (r.period_end.month - 1) // 3 + 1

        periods.append(FinancialPeriodItem(
            period_end=r.period_end,
            period_label=f"{r.period_end.year}/Ç{quarter}",
            revenue=revenue,
            gross_profit=_f(r.gross_profit),
            operating_income=_f(r.operating_income),
            ebitda=_f(r.ebitda),
            net_income=net_income,
            total_assets=_f(r.total_assets),
            total_equity=_f(r.total_equity),
            total_debt=_f(r.total_debt),
            operating_cashflow=_f(r.operating_cashflow),
            revenue_yoy_pct=_yoy(revenue, _f(prev_row.revenue) if prev_row else None),
            net_income_yoy_pct=_yoy(net_income, _f(prev_row.net_income) if prev_row else None),
            net_margin_pct=round((net_income / revenue) * 100, 2) if (revenue and revenue > 0 and net_income is not None) else None,
        ))

    return FinancialStatementsResponse(
        symbol=stock.symbol,
        company_name=stock.company_name,
        periods=periods,
    )


MARKET_QUOTE_LABELS = {
    "USDTRY": "Dolar / TL",
    "EURTRY": "Euro / TL",
    "GRAMALTIN": "Gram Altın",
    "XU100": "BIST 100",
}


@app.get("/api/market/quotes", response_model=List[MarketQuoteItem])
def get_market_quotes(db: Session = Depends(get_db)):
    """
    Döviz kurları, gram altın ve BIST 100 — hisse yanında izlenen referans seriler.

    Dolar, euro ve gram altın 15 dakikada bir yurt içi kaynaktan tazelenir
    (bkz. tr_market.py); BIST 100 seans saatlerinde güncellenir. Gün içi
    tazelenen kayıtlarda as_of SAAT taşır ve is_live=True döner.
    Ücretli platformlarda paket içinde sunulan bu veri yfinance'ta ücretsiz
    olduğu için burada da gösterilir.
    """
    items: List[MarketQuoteItem] = []

    for symbol, label in MARKET_QUOTE_LABELS.items():
        # 'yfinance-gcf' BİLİNEREK DIŞLANIR. Bunlar gram altının COMEX vadeli
        # sözleşmesinden türetildiği dönemin satırlarıdır ve %1,16 yüksektir
        # (bkz. tr_market.py). Silinmiyorlar — geriye dönük inceleme için
        # duruyorlar — ama yeni spot verisiyle karıştırılırlarsa 30 günlük
        # değişim gerçekte olmayan bir sıçrama gösterir.
        rows = (
            db.query(models.IndexHistory)
            .filter(models.IndexHistory.symbol == symbol)
            .filter(func.coalesce(models.IndexHistory.source, "") != "yfinance-gcf")
            .order_by(models.IndexHistory.trade_date.desc())
            .limit(40)
            .all()
        )
        if not rows:
            continue

        latest = rows[0]
        price = float(latest.close)

        # 1 günlük değişim: ÖNCE kaynağın kendi değişimi kullanılır. Kendi
        # geçmişimizden hesaplamak, dünkü satır başka bir kaynaktan geldiyse
        # (yedeğe düşülmüş ya da kaynak değişmiş olabilir) gerçekte olmayan bir
        # sıçrama üretir. Kaynak değişim vermiyorsa (XU100, TCMB) bir önceki
        # İŞLEM GÜNÜ satırından hesaplanır — takvim günü değil, çünkü hafta
        # sonu/tatilde bir önceki takvim gününde kayıt yoktur.
        change_1d = None
        if latest.change_1d_pct is not None:
            change_1d = float(latest.change_1d_pct)
        elif len(rows) > 1 and float(rows[1].close) > 0:
            change_1d = round(((price - float(rows[1].close)) / float(rows[1].close)) * 100, 2)

        # 30 günlük: 30 takvim günü öncesine en yakın (ondan önceki) kapanış.
        change_30d = None
        cutoff = latest.trade_date - timedelta(days=30)
        older = [r for r in rows if r.trade_date <= cutoff]
        if older and float(older[0].close) > 0:
            change_30d = round(((price - float(older[0].close)) / float(older[0].close)) * 100, 2)

        # Zaman damgası: gün içi tazelenen satırlarda updated_at doludur.
        # Eski (yalnızca günlük) satırlarda yoktur; o zaman günün başlangıcı
        # gösterilir ve is_live=False ile "bu anlık değil" denir.
        zaman = latest.updated_at
        canli = zaman is not None
        if zaman is None:
            zaman = datetime.combine(latest.trade_date, dt_time.min)

        items.append(MarketQuoteItem(
            symbol=symbol,
            label=label,
            price=price,
            change_1d_pct=change_1d,
            change_30d_pct=change_30d,
            as_of=zaman,
            source=latest.source,
            is_live=canli,
        ))

    return items


@app.get("/api/portfolio/benchmark", response_model=PortfolioBenchmarkResponse)
def get_portfolio_benchmark(
    days: int = 90,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Portföy getirisini BIST 100 ile kıyaslar — "endeksi yenebiliyor muyum?".

    Her iki seri de İLK ORTAK GÜNE 100 verilerek normalize edilir; aksi halde
    ~10.000 puanlık endeksle 100.000 TL'lik portföyü aynı grafikte kıyaslamak
    anlamsız olurdu.

    Endeks kapanışları yalnızca işlem günlerinde vardır; portföy anlık görüntüsü
    de hafta içi alındığı için tarihler genelde örtüşür. Örtüşmeyen günlerde
    endeks için o tarihten ÖNCEKİ en yakın kapanış kullanılır (ileriye dönük
    veri kullanmamak için — aksi halde henüz gerçekleşmemiş bir kapanışla
    kıyaslama yapılmış olurdu).
    """
    cutoff = date.today() - timedelta(days=max(1, min(days, 365)))

    snapshots = (
        db.query(models.UserPerformanceHistory)
        .filter(
            models.UserPerformanceHistory.user_id == current_user.id,
            models.UserPerformanceHistory.recorded_date >= cutoff,
        )
        .order_by(models.UserPerformanceHistory.recorded_date.asc())
        .all()
    )
    if len(snapshots) < 2:
        return PortfolioBenchmarkResponse(points=[])

    index_rows = (
        db.query(models.IndexHistory)
        .filter(models.IndexHistory.symbol == "XU100", models.IndexHistory.trade_date >= cutoff - timedelta(days=10))
        .order_by(models.IndexHistory.trade_date.asc())
        .all()
    )
    index_pairs = [(r.trade_date, float(r.close)) for r in index_rows]

    def index_close_on_or_before(d):
        """O tarihteki ya da ondan önceki en yakın endeks kapanışı (ileriye bakmaz)."""
        chosen = None
        for td, close in index_pairs:
            if td <= d:
                chosen = close
            else:
                break
        return chosen

    base_portfolio = float(snapshots[0].total_portfolio_value)
    base_index = index_close_on_or_before(snapshots[0].recorded_date)
    if base_portfolio <= 0:
        return PortfolioBenchmarkResponse(points=[])

    points: list[BenchmarkPoint] = []
    for snap in snapshots:
        value = float(snap.total_portfolio_value)
        idx_close = index_close_on_or_before(snap.recorded_date)
        points.append(BenchmarkPoint(
            date=snap.recorded_date,
            portfolio_value=round(value, 2),
            portfolio_index=round((value / base_portfolio) * 100, 2),
            benchmark_index=round((idx_close / base_index) * 100, 2) if (idx_close and base_index) else None,
        ))

    portfolio_ret = round(((points[-1].portfolio_index - 100) / 100) * 100, 2)
    bench_last = points[-1].benchmark_index
    bench_ret = round(((bench_last - 100) / 100) * 100, 2) if bench_last is not None else None

    return PortfolioBenchmarkResponse(
        start_date=points[0].date,
        end_date=points[-1].date,
        portfolio_return_pct=portfolio_ret,
        benchmark_return_pct=bench_ret,
        excess_return_pct=round(portfolio_ret - bench_ret, 2) if bench_ret is not None else None,
        points=points,
    )


def _median(values: List[float]) -> Optional[float]:
    """
    Medyan. Sektör başına yalnızca 3-5 hisse olduğu için ORTALAMA kullanmak
    tek bir aykırı değerle (ör. F/K 107) tüm sektörü çarpıtır; medyan bu
    çarpıklığa dayanıklıdır.
    """
    clean = sorted(v for v in values if v is not None)
    if not clean:
        return None
    mid = len(clean) // 2
    if len(clean) % 2:
        return round(clean[mid], 2)
    return round((clean[mid - 1] + clean[mid]) / 2, 2)


def _sector_rows(db: Session) -> Dict[str, Dict[str, Any]]:
    """Sektör -> toplanmış ham değerler. Hem /api/sectors hem hisse kıyası kullanır."""
    rows = (
        db.query(models.Stock, models.CompanyAnalysis)
        .outerjoin(models.CompanyAnalysis, models.CompanyAnalysis.stock_id == models.Stock.id)
        .filter(models.Stock.is_active == True, models.Stock.sector.isnot(None))
        .all()
    )
    price_map = _bulk_price_and_change(db, [s.id for s, _ in rows])

    buckets: Dict[str, Dict[str, Any]] = {}
    for stock, analysis in rows:
        b = buckets.setdefault(stock.sector, {
            "pe": [], "pb": [], "roe": [], "dy": [], "chg": [],
            "mcap": 0.0, "count": 0, "katilim": 0,
        })
        b["count"] += 1
        if stock.is_katilim_compliant:
            b["katilim"] += 1

        _, change = price_map.get(stock.id, (0.0, None))
        if change is not None:
            b["chg"].append(change)

        if analysis:
            # F/K negatif olamaz (zarar eden şirkette anlamsızdır) — negatifleri ele.
            if analysis.pe_ratio is not None and float(analysis.pe_ratio) > 0:
                b["pe"].append(float(analysis.pe_ratio))
            if analysis.pb_ratio is not None and float(analysis.pb_ratio) > 0:
                b["pb"].append(float(analysis.pb_ratio))
            if analysis.roe is not None:
                b["roe"].append(float(analysis.roe))
            if analysis.dividend_yield is not None:
                b["dy"].append(float(analysis.dividend_yield))
            if analysis.market_cap is not None:
                b["mcap"] += float(analysis.market_cap)
    return buckets


@app.get("/api/stocks/{symbol}/dividend-history", response_model=DividendHistoryResponse)
def get_dividend_history(symbol: str, db: Session = Depends(get_db)):
    """
    Hissenin geçmiş temettü ödemeleri ve yıllık trendi.

    Katılım finansı odaklı bu uygulamada temettü merkezi bir kavram; kullanıcı
    şirketin düzenli ödeyip ödemediğini ve tutarın büyüyüp büyümediğini görür.

    YIL BAZINDA TOPLANIR: bir şirket aynı yıl birden fazla taksit ödeyebilir
    (ör. FROTO), tek tek ödemelere bakmak "temettü arttı mı?" sorusunu
    yanıtlamaz.
    """
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")

    rows = (
        db.query(models.DividendHistory)
        .filter(models.DividendHistory.stock_id == stock.id)
        .order_by(models.DividendHistory.pay_date.desc())
        .all()
    )

    payments = [
        DividendPaymentItem(pay_date=r.pay_date, amount=float(r.amount), year=r.pay_date.year)
        for r in rows
    ]

    yearly: Dict[str, float] = {}
    for p in payments:
        yearly[str(p.year)] = round(yearly.get(str(p.year), 0.0) + p.amount, 4)

    # Trend: son 3 tam yılın toplamları karşılaştırılır. İçinde bulunulan yıl
    # HARİÇ tutulur — yıl daha bitmediği için düşük görünüp yanlış "azalıyor"
    # sonucu üretirdi.
    current_year = date.today().year
    complete_years = sorted((y for y in yearly if int(y) < current_year), reverse=True)[:3]
    trend = None
    avg3 = None
    if complete_years:
        vals = [yearly[y] for y in complete_years]
        avg3 = round(sum(vals) / len(vals), 4)
    if len(complete_years) >= 3:
        newest, middle, oldest = yearly[complete_years[0]], yearly[complete_years[1]], yearly[complete_years[2]]
        if newest > middle > oldest:
            trend = "Artıyor"
        elif newest < middle < oldest:
            trend = "Azalıyor"
        else:
            trend = "Değişken"

    # İstikrar sınıfı: yearly zaten str anahtarlı (JSON uyumu için), fonksiyon
    # int yıl bekliyor.
    istikrar = compute_dividend_stability(
        {int(y): v for y, v in yearly.items()}, current_year=current_year,
    )

    return DividendHistoryResponse(
        symbol=stock.symbol,
        company_name=stock.company_name,
        payments=payments[:40],
        yearly_totals=yearly,
        years_paid=len(yearly),
        last_payment_date=payments[0].pay_date if payments else None,
        average_last_3y=avg3,
        trend=trend,
        stability_class=istikrar["stability_class"],
        stability_label=istikrar["stability_label"],
        consecutive_paid_years=istikrar["consecutive_paid_years"],
        consecutive_increase_years=istikrar["consecutive_increase_years"],
        ever_cut=istikrar["ever_cut"],
    )


@app.get("/api/sectors", response_model=List[SectorSummaryItem])
def get_sector_summary(db: Session = Depends(get_db)):
    """
    Sektör bazlı değerleme özeti — hangi sektör ucuz, hangisi pahalı.

    Tamamen kendi verimizden hesaplanır (stocks + company_analysis), ek veri
    kaynağı gerekmez. Ücretli platformların "sektör karşılaştırma" ekranının
    karşılığıdır.
    """
    buckets = _sector_rows(db)
    items = [
        SectorSummaryItem(
            sector=sector,
            stock_count=b["count"],
            median_pe=_median(b["pe"]),
            median_pb=_median(b["pb"]),
            median_roe=_median(b["roe"]),
            median_dividend_yield=_median(b["dy"]),
            avg_change_pct=round(sum(b["chg"]) / len(b["chg"]), 2) if b["chg"] else None,
            total_market_cap=round(b["mcap"], 2) if b["mcap"] else None,
            katilim_compliant_count=b["katilim"],
        )
        for sector, b in buckets.items()
    ]
    # Hisse sayısı çok olan sektörler üstte — istatistik orada daha anlamlı.
    items.sort(key=lambda x: (-x.stock_count, x.sector))
    return items


@app.get("/api/stocks/{symbol}/sector-comparison", response_model=StockSectorComparison)
def get_stock_sector_comparison(symbol: str, db: Session = Depends(get_db)):
    """Hissenin kendi sektör medyanlarına göre konumu."""
    stock = db.query(models.Stock).filter_by(symbol=symbol.upper(), is_active=True).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Hisse bulunamadı.")
    if not stock.sector:
        return StockSectorComparison()

    analysis = db.query(models.CompanyAnalysis).filter_by(stock_id=stock.id).first()
    b = _sector_rows(db).get(stock.sector)
    if not b:
        return StockSectorComparison(sector=stock.sector)

    pe = float(analysis.pe_ratio) if (analysis and analysis.pe_ratio is not None) else None
    med_pe = _median(b["pe"])

    verdict = None
    # Yorum yalnızca sektörde yeterli örneklem varsa verilir; 3 hisseden az
    # olan bir sektörde "medyan" tek bir hisse demek olabilir.
    if pe and med_pe and b["count"] >= 3:
        if pe < med_pe * 0.8:
            verdict = "F/K sektör medyanının belirgin altında — sektörüne göre ucuz görünüyor."
        elif pe > med_pe * 1.2:
            verdict = "F/K sektör medyanının belirgin üstünde — sektörüne göre pahalı görünüyor."
        else:
            verdict = "F/K sektör medyanına yakın."

    return StockSectorComparison(
        sector=stock.sector,
        stock_count=b["count"],
        pe_ratio=pe,
        sector_median_pe=med_pe,
        pb_ratio=float(analysis.pb_ratio) if (analysis and analysis.pb_ratio is not None) else None,
        sector_median_pb=_median(b["pb"]),
        roe=float(analysis.roe) if (analysis and analysis.roe is not None) else None,
        sector_median_roe=_median(b["roe"]),
        dividend_yield=float(analysis.dividend_yield) if (analysis and analysis.dividend_yield is not None) else None,
        sector_median_dividend_yield=_median(b["dy"]),
        verdict=verdict,
    )


@app.get("/api/signals", response_model=List[TechnicalSignalItem])
def get_technical_signals(db: Session = Depends(get_db)):
    """
    Bugün oluşan teknik sinyaller (altın/ölüm kesişimi, RSI aşırı bölgeler,
    hacim patlaması, 52 hafta zirve/dip kırılımı).

    Ücretli terminallerin "formasyon/tarama analizi" özelliğinin karşılığıdır;
    hesaplar kendi günlük bar tablomuzdan yapılır.

    Kesişim sinyalleri yalnızca koşul BUGÜN oluştuysa üretilir — "SMA50 >
    SMA200" koşulu kesişimden sonra aylarca doğru kalacağı için doğrudan
    raporlamak, aylar önceki bir kesişimi her gün yeni sinyal gibi göstermek
    olurdu (bkz. signals.py).
    """
    from signals import scan_signals
    return [TechnicalSignalItem(**s) for s in scan_signals(db)]


TRADING_DAYS_PER_YEAR = 252  # BIST'te yaklaşık işlem günü sayısı


@app.get("/api/portfolio/katilim", response_model=PortfolioKatilimResponse)
def get_portfolio_katilim(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Portföyün katılım (faizsiz) uyum karnesi.

    NEDEN: uygulamanın ayırt edici özelliği katılım odağı ama kullanıcı
    portföyünün NE KADARININ uygun olduğunu hiçbir yerde göremiyordu —
    yalnızca hisse bazında rozet vardı. "Portföyümün %70'i uygun" cümlesini
    kurabilmek, tek tek 12 rozete bakmaktan farklı bir şey.

    ARINDIRMA ORANI VE KAPSAM BİRLİKTE DÖNER. Ağırlıklı ortalama yalnızca
    KAP beyanı OLAN pozisyonlar üzerinden hesaplanır; kapsamı ayrıca
    bildirmezsek kullanıcı bunun tüm portföyü temsil ettiğini sanır.
    Üretimde 165 hissenin 36'sında beyan var, yani kapsam çoğu portföyde
    kısmi olacak ve bunu gizlemek yanlış olur.
    """
    pozisyonlar = (
        db.query(models.Portfolio, models.Stock)
        .join(models.Stock, models.Stock.id == models.Portfolio.stock_id)
        .filter(models.Portfolio.user_id == current_user.id,
                models.Portfolio.is_bot_portfolio.is_(False))
        .all()
    )
    if not pozisyonlar:
        return PortfolioKatilimResponse(
            total_value=0.0, uygun_value=0.0, uygun_pct=0.0,
            uygun_degil_value=0.0, uygun_degil_pct=0.0,
            belirsiz_value=0.0, belirsiz_pct=0.0,
            kap_kapsam_pct=0.0, agirlikli_arindirma_pct=None, positions=[],
        )

    fiyatlar = _bulk_price_and_change(db, [st.id for _, st in pozisyonlar])

    kalemler = []
    toplam = 0.0
    for poz, stock in pozisyonlar:
        fiyat, _ = fiyatlar.get(stock.id, (0.0, None))
        # Fiyat yoksa ortalama maliyet kullanılır; pozisyonu 0 TL saymak
        # portföy ağırlıklarını sessizce çarpıtırdı.
        deger = float(poz.quantity) * (fiyat or float(poz.average_cost))
        toplam += deger
        kalemler.append((stock, deger))

    if toplam <= 0:
        return PortfolioKatilimResponse(
            total_value=0.0, uygun_value=0.0, uygun_pct=0.0,
            uygun_degil_value=0.0, uygun_degil_pct=0.0,
            belirsiz_value=0.0, belirsiz_pct=0.0,
            kap_kapsam_pct=0.0, agirlikli_arindirma_pct=None, positions=[],
        )

    kova = {"UYGUN": 0.0, "UYGUN_DEGIL": 0.0, "BELIRSIZ": 0.0}
    kap_deger = 0.0
    arindirma_agirlikli_toplam = 0.0
    cikti = []

    for stock, deger in sorted(kalemler, key=lambda x: -x[1]):
        durum = stock.katilim_status or "BELIRSIZ"
        if durum not in kova:
            durum = "BELIRSIZ"
        kova[durum] += deger

        gelir = (float(stock.kap_katilim_gelir_pct)
                 if stock.kap_katilim_gelir_pct is not None else None)
        if gelir is not None:
            kap_deger += deger
            arindirma_agirlikli_toplam += gelir * deger

        cikti.append(KatilimPozisyonu(
            symbol=stock.symbol,
            company_name=stock.company_name,
            value=round(deger, 2),
            weight_pct=round(deger / toplam * 100, 2),
            katilim_status=stock.katilim_status,
            kap_gelir_pct=gelir,
            kap_donem=stock.kap_katilim_donem,
            kap_url=stock.kap_katilim_url,
        ))

    return PortfolioKatilimResponse(
        total_value=round(toplam, 2),
        uygun_value=round(kova["UYGUN"], 2),
        uygun_pct=round(kova["UYGUN"] / toplam * 100, 2),
        uygun_degil_value=round(kova["UYGUN_DEGIL"], 2),
        uygun_degil_pct=round(kova["UYGUN_DEGIL"] / toplam * 100, 2),
        belirsiz_value=round(kova["BELIRSIZ"], 2),
        belirsiz_pct=round(kova["BELIRSIZ"] / toplam * 100, 2),
        kap_kapsam_pct=round(kap_deger / toplam * 100, 2),
        # Ortalama KAPSANAN değere bölünür, toplam portföye değil: aksi hâlde
        # beyanı olmayan hisseler "sıfır arındırma" gibi davranıp oranı
        # sistematik olarak aşağı çekerdi.
        agirlikli_arindirma_pct=(round(arindirma_agirlikli_toplam / kap_deger, 3)
                                 if kap_deger > 0 else None),
        positions=cikti,
    )


@app.get("/api/portfolio/risk", response_model=PortfolioRiskResponse)
def get_portfolio_risk(
    days: int = 180,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Portföyün risk profili: volatilite, maksimum düşüş, beta, getiri/risk oranı.

    Ücretli terminallerin "portföy optimizasyonu" başlığı altında sunduğu
    ölçülerin karşılığıdır; hepsi kendi gün sonu portföy değerlerimizden
    (user_performance_history) hesaplanır, ek veri kaynağı gerekmez.

    FAİZSİZ FİNANS: Klasik Sharpe oranı risksiz FAİZ oranını girdi alır.
    road_map.md bu projede faiz mantığını yasakladığı için Sharpe yerine
    getiri/volatilite oranı hesaplanır — "birim risk başına ne kadar getiri"
    sorusunu faiz kullanmadan yanıtlar.
    """
    cutoff = date.today() - timedelta(days=max(30, min(days, 730)))
    snaps = (
        db.query(models.UserPerformanceHistory)
        .filter(
            models.UserPerformanceHistory.user_id == current_user.id,
            models.UserPerformanceHistory.recorded_date >= cutoff,
        )
        .order_by(models.UserPerformanceHistory.recorded_date.asc())
        .all()
    )

    # Anlamlı bir volatilite için en az birkaç haftalık veri gerekir; 10 günün
    # altında hesaplanan değer istatistiksel olarak gürültüden ibarettir.
    if len(snaps) < 10:
        return PortfolioRiskResponse(
            day_count=len(snaps),
            message="Risk ölçümü için en az 10 günlük portföy geçmişi gerekir. "
                    "Gün sonu değerleriniz hafta içi her akşam kaydediliyor.",
        )

    values = [float(s.total_portfolio_value) for s in snaps]
    dates = [s.recorded_date for s in snaps]

    # Günlük getiriler
    rets, ret_dates = [], []
    for i in range(1, len(values)):
        if values[i - 1] > 0:
            rets.append((values[i] - values[i - 1]) / values[i - 1])
            ret_dates.append(dates[i])
    if len(rets) < 5:
        return PortfolioRiskResponse(day_count=len(snaps), message="Yeterli getiri verisi yok.")

    n = len(rets)
    mean_ret = sum(rets) / n
    variance = sum((r - mean_ret) ** 2 for r in rets) / (n - 1) if n > 1 else 0.0
    daily_vol = variance ** 0.5

    annual_vol = daily_vol * (TRADING_DAYS_PER_YEAR ** 0.5) * 100
    # Toplam getiriyi yıllıklandır (bileşik).
    total_growth = values[-1] / values[0] if values[0] > 0 else 1.0
    span_days = max(1, (dates[-1] - dates[0]).days)
    annual_ret = ((total_growth ** (365.0 / span_days)) - 1) * 100 if total_growth > 0 else None

    # Maksimum düşüş: zirveden sonraki en derin dip.
    peak, max_dd, max_dd_date = values[0], 0.0, dates[0]
    for i, v in enumerate(values):
        if v > peak:
            peak = v
        elif peak > 0:
            dd = (v - peak) / peak * 100
            if dd < max_dd:
                max_dd, max_dd_date = dd, dates[i]

    # Beta: portföy getirilerinin BIST 100 getirilerine duyarlılığı.
    beta = None
    idx_rows = (
        db.query(models.IndexHistory)
        .filter(models.IndexHistory.symbol == "XU100", models.IndexHistory.trade_date >= cutoff)
        .order_by(models.IndexHistory.trade_date.asc())
        .all()
    )
    idx_by_date = {r.trade_date: float(r.close) for r in idx_rows}
    paired_p, paired_i = [], []
    prev_idx_date = None
    for i, d in enumerate(ret_dates):
        if d in idx_by_date and prev_idx_date and prev_idx_date in idx_by_date:
            prev_close = idx_by_date[prev_idx_date]
            if prev_close > 0:
                paired_p.append(rets[i])
                paired_i.append((idx_by_date[d] - prev_close) / prev_close)
        if d in idx_by_date:
            prev_idx_date = d

    if len(paired_p) >= 10:
        mp = sum(paired_p) / len(paired_p)
        mi = sum(paired_i) / len(paired_i)
        cov = sum((paired_p[k] - mp) * (paired_i[k] - mi) for k in range(len(paired_p)))
        var_i = sum((x - mi) ** 2 for x in paired_i)
        if var_i > 0:
            beta = round(cov / var_i, 2)

    ratio = round(annual_ret / annual_vol, 2) if (annual_ret is not None and annual_vol > 0) else None

    # Eşikler BIST'in tipik oynaklığına göre: tek hisse yıllık %40+ volatilite
    # görebilir; dengeli bir portföyde %25 altı sakin sayılır.
    if annual_vol < 25:
        risk_label = "Düşük"
    elif annual_vol < 45:
        risk_label = "Orta"
    else:
        risk_label = "Yüksek"

    positives = sum(1 for r in rets if r > 0)

    return PortfolioRiskResponse(
        day_count=len(snaps),
        annualized_return_pct=round(annual_ret, 2) if annual_ret is not None else None,
        annualized_volatility_pct=round(annual_vol, 2),
        max_drawdown_pct=round(max_dd, 2),
        max_drawdown_date=max_dd_date if max_dd < 0 else None,
        return_risk_ratio=ratio,
        beta_vs_index=beta,
        best_day_pct=round(max(rets) * 100, 2),
        worst_day_pct=round(min(rets) * 100, 2),
        positive_day_ratio=round(positives / n * 100, 2),
        risk_label=risk_label,
    )


@app.get("/api/portfolio/dividends", response_model=PortfolioDividendResponse)
def get_portfolio_dividends(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Portföyün beklenen yıllık temettü geliri.

    Ücretli platformların öne çıkardığı bir özelliktir; verisi yfinance'ta
    ücretsiz olduğu için burada da sunulur (company_analysis.dividend_yield,
    derin analiz işi tarafından doldurulur).

    "Maliyete göre verim" (yield on cost) ayrıca hesaplanır: uzun vadeli
    yatırımcı için asıl anlamlı olan, hisseyi BUGÜN alsa elde edeceği verim
    değil, KENDİ maliyetine göre elde ettiği verimdir. 100 TL'den alınan ve
    şimdi 300 TL olan bir hissede güncel verim %2 iken maliyete göre %6'dır.
    """
    positions = (
        db.query(models.Portfolio, models.Stock, models.CompanyAnalysis)
        .join(models.Stock, models.Stock.id == models.Portfolio.stock_id)
        .outerjoin(models.CompanyAnalysis, models.CompanyAnalysis.stock_id == models.Stock.id)
        .filter(models.Portfolio.user_id == current_user.id, models.Portfolio.is_bot_portfolio == False)
        .all()
    )

    items: list[DividendPositionItem] = []
    total_income = 0.0
    portfolio_value = 0.0
    covered = 0

    for pos, stock, analysis in positions:
        qty = float(pos.quantity)
        price = _get_latest_db_price(db, stock.id) or float(pos.average_cost)
        value = qty * price
        portfolio_value += value

        dy = float(analysis.dividend_yield) if (analysis and analysis.dividend_yield is not None) else None
        income = None
        yoc = None
        if dy and dy > 0:
            covered += 1
            income = round(value * dy / 100, 2)
            total_income += income
            cost_basis = qty * float(pos.average_cost)
            if cost_basis > 0:
                yoc = round((income / cost_basis) * 100, 2)

        items.append(DividendPositionItem(
            symbol=stock.symbol,
            company_name=stock.company_name,
            quantity=qty,
            current_value=round(value, 2),
            dividend_yield=dy,
            annual_income=income,
            yield_on_cost=yoc,
            last_dividend_date=analysis.last_dividend_date if analysis else None,
        ))

    # Geliri en yüksek pozisyon üstte — kullanıcı temettüsünün nereden geldiğini görsün.
    items.sort(key=lambda x: x.annual_income or 0, reverse=True)

    return PortfolioDividendResponse(
        total_annual_income=round(total_income, 2),
        monthly_average=round(total_income / 12, 2),
        portfolio_value=round(portfolio_value, 2),
        portfolio_yield=round((total_income / portfolio_value) * 100, 2) if portfolio_value > 0 else None,
        covered_positions=covered,
        total_positions=len(positions),
        items=items,
    )


# --- LEADERBOARD ---

def _portfolio_value(db: Session, owner_user_id: int, is_bot_portfolio: bool, cash: float) -> float:
    positions = db.query(models.Portfolio).filter_by(user_id=owner_user_id, is_bot_portfolio=is_bot_portfolio).all()
    stock_value = 0.0
    for item in positions:
        price = _get_latest_db_price(db, item.stock_id) or float(item.average_cost)
        stock_value += float(item.quantity) * price
    return cash + stock_value


@app.get("/api/leaderboard", response_model=List[LeaderboardItem])
def get_leaderboard(period: str = "all", db: Session = Depends(get_db)):
    """
    Liderlik tablosu: topluluk demo botu artık gösterilmez — yalnızca gerçek kullanıcılar
    ve her kullanıcının kendi kişisel AI botu (ayrı bir satır olarak) listelenir.

    N+1 GİDERİLDİ: eskiden kullanıcı başına `_portfolio_value` çağrılıyor, o da
    POZİSYON BAŞINA ayrı bir "son fiyat" sorgusu atıyordu. 6 kullanıcıda fark
    edilmiyordu ama maliyet O(kullanıcı × pozisyon) büyüyor — 100 kullanıcı ×
    10 pozisyon ≈ 2.200 sorgu. Uç herkese açık olduğu için bu, ölçeklendiğinde
    veritabanını en çok yoran yer olurdu.

    Artık TÜM pozisyonlar tek sorguda, tüm fiyatlar tek toplu çağrıda çekilir.

    `period` — zaman-kutulu yarışma:
      "all" (varsayılan)     → mevcut davranış, hesap açılışından bu yana getiri, TOPLAM DEĞERE göre sırala
      "weekly" / "monthly"   → bu haftanın/ayın BAŞINDAKİ gün-sonu değerine göre getiri, GETİRİ YÜZDESİNE göre sırala
    Haftalık/aylık başlangıç değeri, zaten var olan günlük performans anlık
    görüntüsünden (`UserPerformanceHistory`/`BotPerformanceHistory`, hafta içi
    15:30 UTC'de kaydediliyor) okunur — kaydı olmayan (bu dönemde yeni katılmış)
    kullanıcı, mevcut değeriyle başlar (yani dönem içinde %0'dan başlar,
    haksız yere negatif/pozitif gösterilmez).
    """
    period = period if period in ("weekly", "monthly") else "all"
    users = db.query(models.User).filter_by(is_bot=False).all()
    if not users:
        return []

    user_ids = [u.id for u in users]

    # Tüm kullanıcıların tüm pozisyonları — tek sorgu.
    tum_pozisyonlar = (
        db.query(models.Portfolio)
        .filter(models.Portfolio.user_id.in_(user_ids))
        .all()
    )
    # (user_id, is_bot_portfolio) -> [pozisyon, ...]
    pozisyon_haritasi: Dict[tuple, List[models.Portfolio]] = {}
    for poz in tum_pozisyonlar:
        anahtar = (poz.user_id, bool(poz.is_bot_portfolio))
        pozisyon_haritasi.setdefault(anahtar, []).append(poz)

    # Geçen tüm hisselerin güncel fiyatı — tek toplu çağrı.
    fiyat_haritasi = _bulk_price_and_change(db, list({p.stock_id for p in tum_pozisyonlar}))

    # Tüm kişisel botlar — tek sorgu.
    botlar = {
        b.user_id: b
        for b in db.query(models.UserBot).filter(models.UserBot.user_id.in_(user_ids)).all()
    }

    # Haftalık/aylık yarışma: dönem başlangıcındaki gün-sonu değeri baz alınır.
    donem_baslangici = None
    if period == "weekly":
        bugun = bugun_tr()
        donem_baslangici = bugun - timedelta(days=bugun.weekday())  # Pazartesi
    elif period == "monthly":
        donem_baslangici = bugun_tr().replace(day=1)

    donem_bazlari: Dict[int, float] = {}
    donem_bot_bazlari: Dict[int, float] = {}
    if donem_baslangici is not None:
        # Her kullanıcının dönem içindeki İLK kaydı baz alınır — o kayıttan
        # sonraki hareket dönem getirisini oluşturur.
        for row in (
            db.query(models.UserPerformanceHistory)
            .filter(models.UserPerformanceHistory.user_id.in_(user_ids))
            .filter(models.UserPerformanceHistory.recorded_date >= donem_baslangici)
            .order_by(models.UserPerformanceHistory.recorded_date.asc())
            .all()
        ):
            donem_bazlari.setdefault(row.user_id, float(row.total_portfolio_value))

        for row in (
            db.query(models.BotPerformanceHistory)
            .filter(models.BotPerformanceHistory.user_id.in_(user_ids))
            .filter(models.BotPerformanceHistory.recorded_date >= donem_baslangici)
            .order_by(models.BotPerformanceHistory.recorded_date.asc())
            .all()
        ):
            donem_bot_bazlari.setdefault(row.user_id, float(row.total_portfolio_value))

    def deger(user_id: int, bot_mu: bool, nakit: float) -> float:
        toplam = nakit
        for poz in pozisyon_haritasi.get((user_id, bot_mu), []):
            fiyat, _ = fiyat_haritasi.get(poz.stock_id, (0.0, None))
            # Fiyat yoksa ortalama maliyet kullanılır — pozisyonu 0 TL saymak
            # kullanıcıyı liderlik tablosunda haksız yere dibe atardı.
            toplam += float(poz.quantity) * (fiyat or float(poz.average_cost))
        return toplam

    leaderboard = []
    for user in users:
        total_value = deger(user.id, False, float(user.virtual_balance))
        if donem_baslangici is not None:
            baseline = donem_bazlari.get(user.id, total_value)
        else:
            baseline = float(user.baseline_value or 100000.0)
        profit_loss_pct = ((total_value - baseline) / baseline) * 100 if baseline else 0.0
        leaderboard.append(LeaderboardItem(
            username=user.username,
            total_portfolio_value=round(total_value, 2),
            profit_loss_pct=round(profit_loss_pct, 2),
            is_bot=False,
        ))

        user_bot = botlar.get(user.id)
        if user_bot:
            bot_total_value = deger(user.id, True, float(user_bot.virtual_balance))
            if donem_baslangici is not None:
                bot_baseline = donem_bot_bazlari.get(user.id, bot_total_value)
            else:
                bot_baseline = float(user_bot.baseline_value or 100000.0)
            bot_profit_loss_pct = ((bot_total_value - bot_baseline) / bot_baseline) * 100 if bot_baseline else 0.0
            leaderboard.append(LeaderboardItem(
                username=f"{user.username} — Kişisel Bot",
                total_portfolio_value=round(bot_total_value, 2),
                profit_loss_pct=round(bot_profit_loss_pct, 2),
                is_bot=True,
            ))

    # Getiri YÜZDESİNE göre sırala — herkes farklı sermayeyle başlasa da (ör.
    # yeni katılan kullanıcı) adil karşılaştırma budur; toplam değere göre
    # sıralamak sermayesi büyük ama getirisi düşük kullanıcıyı haksız yere
    # üste taşırdı.
    leaderboard.sort(key=lambda x: x.profit_loss_pct, reverse=True)
    return leaderboard


@app.get("/api/leaderboard/kategori", response_model=List[CategoryLeaderboardItem])
def get_category_leaderboard(category: str = "aktiflik", period: str = "all", db: Session = Depends(get_db)):
    """
    "Getiri" dışındaki liderlik kategorileri (bkz. leaderboard_categories.py):
    istikrar (getiri/risk oranı), aktiflik (işlem sayısı), kahin (yön tahmini
    isabet oranı). Yalnızca gerçek kullanıcıları kapsar, kişisel botlar dahil
    değildir (bkz. modül başlığı — botların bu verileri anlamlı biçimde
    karşılaştırılamaz).
    """
    category = category if category in ("istikrar", "aktiflik", "kahin") else "aktiflik"
    period = period if period in ("weekly", "monthly") else "all"

    users = {u.id: u.username for u in db.query(models.User).filter_by(is_bot=False).all()}
    if not users:
        return []

    ham_sonuc: List[tuple]
    if category == "kahin":
        # Kâhin dönem sekmelerinden bağımsızdır (bkz. kahin_siralamasi).
        ham_sonuc = [(uid, deger, f"{toplam} oy") for uid, deger, toplam in kahin_siralamasi(db)]
    else:
        bugun = bugun_tr()
        donem_baslangici = None
        if period == "weekly":
            donem_baslangici = bugun - timedelta(days=bugun.weekday())
        elif period == "monthly":
            donem_baslangici = bugun.replace(day=1)

        user_ids = list(users.keys())
        if category == "istikrar":
            ham_sonuc = [
                (uid, deger, f"{gun} gün veri") for uid, deger, gun in
                istikrar_siralamasi(db, user_ids, donem_baslangici, bugun)
            ]
        else:  # aktiflik
            ham_sonuc = [
                (uid, float(adet), f"{adet} işlem") for uid, adet in
                aktiflik_siralamasi(db, user_ids, donem_baslangici, bugun)
            ]

    sonuc = [
        CategoryLeaderboardItem(username=users[uid], deger=round(deger, 4), detay=detay)
        for uid, deger, detay in ham_sonuc if uid in users
    ]
    sonuc.sort(key=lambda x: x.deger, reverse=True)
    return sonuc[:50]


@app.get("/api/hall-of-fame", response_model=List[HallOfFameEntryResponse])
def get_hall_of_fame(period: str = "weekly", category: str = "GETIRI", limit: int = 12, db: Session = Depends(get_db)):
    """
    Şampiyonlar Duvarı: geçmiş dönemlerin arşivlenmiş ilk 3'ü (bkz.
    hall_of_fame.py). `limit`, en son kaç DÖNEM gösterileceğini sınırlar
    (dönem başına en fazla 3 satır olduğu için en fazla limit×3 satır döner).
    """
    period = period if period in ("weekly", "monthly") else "weekly"
    category = category.upper() if category.upper() in ("GETIRI", "ISTIKRAR", "AKTIFLIK") else "GETIRI"
    limit = max(1, min(limit, 52))

    son_donem_etiketleri = [
        row[0] for row in (
            db.query(models.HallOfFameEntry.period_label)
            .filter_by(period=period, category=category)
            .distinct()
            .order_by(models.HallOfFameEntry.period_label.desc())
            .limit(limit)
            .all()
        )
    ]
    if not son_donem_etiketleri:
        return []

    kayitlar = (
        db.query(models.HallOfFameEntry)
        .filter(
            models.HallOfFameEntry.period == period,
            models.HallOfFameEntry.category == category,
            models.HallOfFameEntry.period_label.in_(son_donem_etiketleri),
        )
        .order_by(models.HallOfFameEntry.period_end_date.desc(), models.HallOfFameEntry.rank.asc())
        .all()
    )
    return [
        HallOfFameEntryResponse(
            period=k.period, period_label=k.period_label, period_end_date=k.period_end_date,
            category=k.category, rank=k.rank, username=k.user.username, metric_value=float(k.metric_value),
        )
        for k in kayitlar
    ]


# --- HAFTALIK GÖREVLER & OYUN PUANI ---

@app.get("/api/quests", response_model=List[QuestResponse])
def get_quests(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Bu haftanın görev durumunu döner. Her çağrıda güncel bağlam hesaplanır,
    yeni tamamlanan görevler `user_quest_completions`e YAZILIR ve karşılığı
    kadar `User.game_points` artırılır (bkz. quests.py -- achievements.py'nin
    aksine bir görev HER HAFTA yeniden değerlendirilir).
    """
    hafta_basi = bugun_tr() - timedelta(days=bugun_tr().weekday())

    alim_satirlari = (
        db.query(models.Transaction)
        .join(models.Stock, models.Stock.id == models.Transaction.stock_id)
        .filter(
            models.Transaction.user_id == current_user.id,
            func.date(models.Transaction.created_at) >= hafta_basi,
        )
        .all()
    )
    islem_sayisi_bu_hafta = len(alim_satirlari)
    alimlar = [t for t in alim_satirlari if t.action_type == "AL"]
    sektor_sayisi_bu_hafta = len({t.stock.sector for t in alimlar if t.stock.sector})
    farkli_hisse_alinan_bu_hafta = len({t.stock_id for t in alimlar})

    favori_eklenen_bu_hafta = (
        db.query(func.count(models.Watchlist.id))
        .filter(models.Watchlist.user_id == current_user.id, func.date(models.Watchlist.created_at) >= hafta_basi)
        .scalar() or 0
    )
    yorum_sayisi_bu_hafta = (
        db.query(func.count(models.StockComment.id))
        .filter(models.StockComment.user_id == current_user.id, func.date(models.StockComment.created_at) >= hafta_basi)
        .scalar() or 0
    )
    bes_gun_once = datetime.utcnow() - timedelta(days=5)
    uzun_tutulan_pozisyon_var_mi = (
        db.query(models.Portfolio.id)
        .filter(
            models.Portfolio.user_id == current_user.id,
            models.Portfolio.is_bot_portfolio.is_(False),
            models.Portfolio.opened_at <= bes_gun_once,
        )
        .first() is not None
    )

    baglam: GorevBaglami = {
        "sektor_sayisi_bu_hafta": sektor_sayisi_bu_hafta,
        "islem_sayisi_bu_hafta": islem_sayisi_bu_hafta,
        "farkli_hisse_alinan_bu_hafta": farkli_hisse_alinan_bu_hafta,
        "favori_eklenen_bu_hafta": favori_eklenen_bu_hafta,
        "yorum_sayisi_bu_hafta": yorum_sayisi_bu_hafta,
        "uzun_tutulan_pozisyon_var_mi": uzun_tutulan_pozisyon_var_mi,
    }

    tamamlanan_idler = set(tamamlananlari_hesapla(baglam))
    mevcut_kayitlar = {
        r.quest_id
        for r in db.query(models.UserQuestCompletion).filter_by(
            user_id=current_user.id, week_start_date=hafta_basi
        ).all()
    }

    yeni_tamamlananlar = tamamlanan_idler - mevcut_kayitlar
    if yeni_tamamlananlar:
        harita = {t["id"]: t for t in gorev_tanimlari()}
        kazanilan_puan = 0
        for qid in yeni_tamamlananlar:
            db.add(models.UserQuestCompletion(user_id=current_user.id, quest_id=qid, week_start_date=hafta_basi))
            kazanilan_puan += harita[qid]["puan"]
            mevcut_kayitlar.add(qid)
        current_user.game_points = (current_user.game_points or 0) + kazanilan_puan
        db.commit()

    return [
        QuestResponse(
            id=tanim["id"], isim=tanim["isim"], aciklama=tanim["aciklama"], puan=tanim["puan"],
            tamamlandi=tanim["id"] in mevcut_kayitlar,
        )
        for tanim in gorev_tanimlari()
    ]


@app.get("/api/user/game-points", response_model=GamePointsResponse)
def get_game_points(current_user: models.User = Depends(get_current_user)):
    return GamePointsResponse(game_points=current_user.game_points or 0)


# --- SANAL ÖDÜL MAĞAZASI ---

@app.get("/api/shop", response_model=List[ShopItemResponse])
def get_shop(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    sahip_olunanlar = {
        r.item_id for r in db.query(models.UserInventory).filter_by(user_id=current_user.id).all()
    }
    return [
        ShopItemResponse(
            id=e["id"], isim=e["isim"], aciklama=e["aciklama"], kategori=e["kategori"],
            maliyet=e["maliyet"], deger=e["deger"],
            sahip_mi=e["id"] in sahip_olunanlar,
            takili_mi=(current_user.equipped_frame_id == e["id"] or current_user.equipped_title_id == e["id"]),
        )
        for e in magaza_esyalari()
    ]


@app.post("/api/shop/{item_id}/buy")
@limiter.limit("10/minute")
def buy_shop_item(
    request: Request, item_id: str,
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db),
):
    esya = esya_bul(item_id)
    if not esya:
        raise HTTPException(status_code=404, detail="Eşya bulunamadı.")

    db.rollback()
    begin_write_transaction(db)
    try:
        zaten_var = db.query(models.UserInventory).filter_by(
            user_id=current_user.id, item_id=item_id
        ).first()
        if zaten_var:
            db.rollback()
            raise HTTPException(status_code=400, detail="Bu eşyaya zaten sahipsin.")

        mevcut_puan = current_user.game_points or 0
        if mevcut_puan < esya["maliyet"]:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail=f"Yetersiz oyun puanı. Gerekli: {esya['maliyet']}, mevcut: {mevcut_puan}.",
            )

        current_user.game_points = mevcut_puan - esya["maliyet"]
        db.add(models.UserInventory(user_id=current_user.id, item_id=item_id))
        db.commit()
        return {"message": "Satın alındı.", "game_points": current_user.game_points}
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise


@app.post("/api/shop/{item_id}/equip")
def equip_shop_item(
    item_id: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db),
):
    esya = esya_bul(item_id)
    if not esya:
        raise HTTPException(status_code=404, detail="Eşya bulunamadı.")
    sahip = db.query(models.UserInventory).filter_by(user_id=current_user.id, item_id=item_id).first()
    if not sahip:
        raise HTTPException(status_code=400, detail="Bu eşyaya sahip değilsin.")

    if esya["kategori"] == "CERCEVE":
        current_user.equipped_frame_id = item_id
    else:
        current_user.equipped_title_id = item_id
    db.commit()
    return {"message": "Takıldı."}


@app.post("/api/shop/{item_id}/unequip")
def unequip_shop_item(
    item_id: str, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db),
):
    esya = esya_bul(item_id)
    if not esya:
        raise HTTPException(status_code=404, detail="Eşya bulunamadı.")
    if esya["kategori"] == "CERCEVE" and current_user.equipped_frame_id == item_id:
        current_user.equipped_frame_id = None
    elif esya["kategori"] == "UNVAN" and current_user.equipped_title_id == item_id:
        current_user.equipped_title_id = None
    db.commit()
    return {"message": "Çıkarıldı."}


# --- 1V1 DÜELLO ---

def _duel_response(db: Session, d: models.Duel) -> DuelResponse:
    challenger_pct = opponent_pct = None
    if d.status in ("ACTIVE", "COMPLETED") and d.challenger_baseline is not None:
        challenger_pct = round(duel_getiri_pct(float(d.challenger_baseline), duel_portfoy_degeri(db, d.challenger_id)), 2)
        opponent_pct = round(duel_getiri_pct(float(d.opponent_baseline), duel_portfoy_degeri(db, d.opponent_id)), 2)
    return DuelResponse(
        id=d.id, challenger_username=d.challenger.username, opponent_username=d.opponent.username,
        status=d.status, starts_at=d.starts_at, ends_at=d.ends_at,
        winner_username=d.winner.username if d.winner else None,
        created_at=d.created_at,
        challenger_getiri_pct=challenger_pct, opponent_getiri_pct=opponent_pct,
    )


@app.post("/api/duels", response_model=DuelResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def create_duel(
    request: Request, body: DuelCreateRequest,
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """Bir kullanıcıya 7 günlük 1v1 düello daveti gönderir (bkz. duels.py)."""
    opponent_username = body.opponent_username.strip()
    if opponent_username.lower() == current_user.username.lower():
        raise HTTPException(status_code=400, detail="Kendine meydan okuyamazsın.")

    opponent = db.query(models.User).filter_by(username=opponent_username, is_bot=False).first()
    if not opponent:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")

    mevcut = db.query(models.Duel).filter(
        models.Duel.status.in_(("PENDING", "ACTIVE")),
        or_(
            and_(models.Duel.challenger_id == current_user.id, models.Duel.opponent_id == opponent.id),
            and_(models.Duel.challenger_id == opponent.id, models.Duel.opponent_id == current_user.id),
        ),
    ).first()
    if mevcut:
        raise HTTPException(status_code=400, detail="Bu kullanıcıyla zaten bekleyen veya aktif bir düellon var.")

    yeni = models.Duel(challenger_id=current_user.id, opponent_id=opponent.id, status="PENDING")
    db.add(yeni)
    db.add(models.Notification(
        user_id=opponent.id, stock_id=None, notif_type="DUEL_INVITE",
        title="Yeni Düello Daveti",
        message=f"{current_user.username} sana 1v1 düello için meydan okudu.",
    ))
    db.commit()
    db.refresh(yeni)

    _log_user_action(db, current_user.id, "DUEL_CREATE", f"{opponent.username} kullanıcısına düello daveti gönderildi.")
    db.commit()
    return _duel_response(db, yeni)


@app.get("/api/duels", response_model=List[DuelResponse])
def list_duels(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Giriş yapan kullanıcının (davet eden veya davet edilen) tüm düelloları."""
    duellolar = (
        db.query(models.Duel)
        .filter(or_(models.Duel.challenger_id == current_user.id, models.Duel.opponent_id == current_user.id))
        .order_by(models.Duel.created_at.desc())
        .limit(50)
        .all()
    )
    return [_duel_response(db, d) for d in duellolar]


@app.post("/api/duels/{duel_id}/accept", response_model=DuelResponse)
def accept_duel(duel_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.query(models.Duel).filter_by(id=duel_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Düello bulunamadı.")
    if d.opponent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Yalnızca davet edilen kişi kabul edebilir.")
    if d.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Bu düello artık {d.status} durumunda, kabul edilemez.")

    d.challenger_baseline = duel_portfoy_degeri(db, d.challenger_id)
    d.opponent_baseline = duel_portfoy_degeri(db, d.opponent_id)
    d.status = "ACTIVE"
    d.starts_at = datetime.utcnow()
    d.ends_at = d.starts_at + timedelta(days=DUEL_SURESI_GUN)
    db.commit()
    db.refresh(d)
    return _duel_response(db, d)


@app.post("/api/duels/{duel_id}/decline")
def decline_duel(duel_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.query(models.Duel).filter_by(id=duel_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Düello bulunamadı.")
    if d.opponent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Yalnızca davet edilen kişi reddedebilir.")
    if d.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Bu düello artık {d.status} durumunda.")
    d.status = "DECLINED"
    db.commit()
    return {"message": "Düello reddedildi."}


@app.post("/api/duels/{duel_id}/cancel")
def cancel_duel(duel_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = db.query(models.Duel).filter_by(id=duel_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Düello bulunamadı.")
    if d.challenger_id != current_user.id:
        raise HTTPException(status_code=403, detail="Yalnızca daveti gönderen iptal edebilir.")
    if d.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Bu düello artık {d.status} durumunda, iptal edilemez.")
    d.status = "CANCELLED"
    db.commit()
    return {"message": "Düello iptal edildi."}


# --- BAŞARIM/ROZET SİSTEMİ ---

@app.get("/api/achievements", response_model=List[AchievementResponse])
def get_achievements(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Kullanıcının başarım/rozet durumunu döner. Her çağrıda güncel bağlam
    hesaplanır, yeni kazanılan rozetler `user_achievements`e YAZILIR (bkz.
    achievements.py -- bir rozet kazanıldıktan sonra kalıcıdır, koşul
    sonradan geçersiz olsa da geri alınmaz).
    """
    pozisyonlar = (
        db.query(models.Portfolio)
        .join(models.Stock, models.Stock.id == models.Portfolio.stock_id)
        .filter(models.Portfolio.user_id == current_user.id, models.Portfolio.is_bot_portfolio.is_(False))
        .all()
    )
    stock_ids = [p.stock_id for p in pozisyonlar]
    sektorler = {p.stock.sector for p in pozisyonlar if p.stock.sector}
    tam_katilim_uyumlu = len(pozisyonlar) >= 3 and all(p.stock.katilim_status == "UYGUN" for p in pozisyonlar)

    temettu_hisse_sayisi = 0
    if stock_ids:
        temettu_hisse_sayisi = (
            db.query(func.count(func.distinct(models.DividendHistory.stock_id)))
            .filter(models.DividendHistory.stock_id.in_(stock_ids))
            .scalar() or 0
        )

    islemler = db.query(models.Transaction).filter_by(user_id=current_user.id).all()
    islem_sayisi = len(islemler)

    # Kârlı satış sayısı ve tek işlemde %50+ kâr -- realized_pnl / (maliyet x adet)
    # ile hesaplanır; 2026-08-27 öncesi komisyonsuz dönem satırlarında da
    # average_cost_at_trade dolu olduğu için sorun çıkarmaz.
    karli_satis_sayisi = 0
    buyuk_karli_satis_var = False
    gece_islemi_var_mi = False
    for t in islemler:
        if t.action_type == "SAT" and t.realized_pnl is not None:
            if float(t.realized_pnl) > 0:
                karli_satis_sayisi += 1
            maliyet_toplam = float(t.average_cost_at_trade or 0) * float(t.quantity)
            if maliyet_toplam > 0 and (float(t.realized_pnl) / maliyet_toplam) >= 0.5:
                buyuk_karli_satis_var = True
        if not gece_islemi_var_mi and t.created_at:
            saat_tr = t.created_at.replace(tzinfo=dt_timezone.utc).astimezone(TR_TZ).hour
            if 0 <= saat_tr < 5:
                gece_islemi_var_mi = True

    favori_sayisi = db.query(func.count(models.Watchlist.id)).filter_by(user_id=current_user.id).scalar() or 0
    yorum_sayisi = db.query(func.count(models.StockComment.id)).filter_by(user_id=current_user.id).scalar() or 0
    oy_sayisi = db.query(func.count(models.StockVote.id)).filter_by(user_id=current_user.id).scalar() or 0
    bekleyen_emir_var_mi = db.query(models.PendingOrder.id).filter_by(user_id=current_user.id).first() is not None
    davet_sayisi = db.query(func.count(models.User.id)).filter_by(referred_by_id=current_user.id).scalar() or 0
    hall_of_fame_kayit_var_mi = db.query(models.HallOfFameEntry.id).filter_by(user_id=current_user.id).first() is not None

    toplam_deger = _portfolio_value(db, current_user.id, False, float(current_user.virtual_balance))
    baseline = float(current_user.baseline_value or 100000.0)
    getiri_pct = ((toplam_deger - baseline) / baseline) * 100 if baseline else 0.0

    hesap_yasi_gun = (datetime.utcnow() - current_user.created_at).days if current_user.created_at else 0

    baglam: Baglam = {
        "islem_sayisi": islem_sayisi,
        "sektor_sayisi": len(sektorler),
        "getiri_pct": getiri_pct,
        "tam_katilim_uyumlu": tam_katilim_uyumlu,
        "temettu_hisse_sayisi": temettu_hisse_sayisi,
        "hesap_yasi_gun": hesap_yasi_gun,
        "karli_satis_sayisi": karli_satis_sayisi,
        "buyuk_karli_satis_var": buyuk_karli_satis_var,
        "favori_sayisi": favori_sayisi,
        "yorum_sayisi": yorum_sayisi,
        "oy_sayisi": oy_sayisi,
        "bekleyen_emir_var_mi": bekleyen_emir_var_mi,
        "davet_sayisi": davet_sayisi,
        "gece_islemi_var_mi": gece_islemi_var_mi,
        "duel_wins": current_user.duel_wins or 0,
        "hall_of_fame_kayit_var_mi": hall_of_fame_kayit_var_mi,
        "game_points": current_user.game_points or 0,
    }

    kazanilan_idler = set(kazanilanlari_hesapla(baglam))
    mevcut_kayitlar = {
        r.achievement_id: r.earned_at
        for r in db.query(models.UserAchievement).filter_by(user_id=current_user.id).all()
    }

    yeni_kazanilanlar = kazanilan_idler - set(mevcut_kayitlar.keys())
    if yeni_kazanilanlar:
        simdi = datetime.utcnow()
        for aid in yeni_kazanilanlar:
            db.add(models.UserAchievement(user_id=current_user.id, achievement_id=aid, earned_at=simdi))
            mevcut_kayitlar[aid] = simdi
        db.commit()

    return [
        AchievementResponse(
            id=tanim["id"], isim=tanim["isim"], aciklama=tanim["aciklama"],
            kazanildi=tanim["id"] in mevcut_kayitlar,
            kazanilma_tarihi=mevcut_kayitlar.get(tanim["id"]),
        )
        for tanim in basarim_tanimlari()
    ]


# --- HERKESE AÇIK PROFİL SAYFASI ---

@app.get("/api/users/{username}/profile", response_model=PublicProfileResponse)
def get_public_profile(
    username: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Herkese açık profil vitrini: toplam değer/getiri (liderlik tablosunda zaten
    açık), kazanılmış rozetler ve en büyük 5 pozisyonun AĞIRLIK YÜZDESİ (adet/TL
    tutarı değil). `profile_public=False` ise yalnızca sahibi görebilir.
    """
    target = db.query(models.User).filter_by(username=username, is_bot=False).first()
    if not target:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    if not target.profile_public and target.id != current_user.id:
        raise HTTPException(status_code=403, detail="Bu kullanıcı profilini gizli tutuyor.")

    pozisyonlar = (
        db.query(models.Portfolio)
        .join(models.Stock, models.Stock.id == models.Portfolio.stock_id)
        .filter(models.Portfolio.user_id == target.id, models.Portfolio.is_bot_portfolio.is_(False))
        .all()
    )
    fiyat_haritasi = _bulk_price_and_change(db, [p.stock_id for p in pozisyonlar]) if pozisyonlar else {}

    total_value = float(target.virtual_balance)
    holding_degerleri = []
    for p in pozisyonlar:
        fiyat, _ = fiyat_haritasi.get(p.stock_id, (0.0, None))
        deger = float(p.quantity) * (fiyat or float(p.average_cost))
        total_value += deger
        holding_degerleri.append((p.stock, deger))

    top_holdings = []
    if total_value > 0 and holding_degerleri:
        holding_degerleri.sort(key=lambda x: x[1], reverse=True)
        top_holdings = [
            PublicProfileHolding(
                symbol=stock.symbol, company_name=stock.company_name,
                weight_pct=round((deger / total_value) * 100, 2),
            )
            for stock, deger in holding_degerleri[:5]
        ]

    baseline = float(target.baseline_value or 100000.0)
    profit_loss_pct = ((total_value - baseline) / baseline) * 100 if baseline else 0.0

    kazanilan_harita = {
        r.achievement_id: r.earned_at
        for r in db.query(models.UserAchievement).filter_by(user_id=target.id).all()
    }
    achievements = [
        AchievementResponse(
            id=tanim["id"], isim=tanim["isim"], aciklama=tanim["aciklama"],
            kazanildi=True, kazanilma_tarihi=kazanilan_harita[tanim["id"]],
        )
        for tanim in basarim_tanimlari()
        if tanim["id"] in kazanilan_harita
    ]

    # Kariyer puanı TÜM zamanların üzerinden hesaplanır; vitrindeki liste ise
    # (aşağıda) yalnızca en son 20 şampiyonluğu gösterir -- ikisi farklı amaç
    # taşıdığı için ayrı sorgulanır (kariyer puanını son 20'yle sınırlamak
    # eski, çok başarılı bir kullanıcının rütbesini haksız yere düşürürdü).
    tum_hof_ranklari = [
        r[0] for r in db.query(models.HallOfFameEntry.rank).filter_by(user_id=target.id).all()
    ]
    career_points = sum(RUTBE_PUANLARI.get(r, 0) for r in tum_hof_ranklari)

    hof_kayitlari = (
        db.query(models.HallOfFameEntry)
        .filter_by(user_id=target.id)
        .order_by(models.HallOfFameEntry.period_end_date.desc())
        .limit(20)
        .all()
    )
    hall_of_fame_placements = [
        HallOfFamePlacement(period_label=k.period_label, category=k.category, rank=k.rank)
        for k in hof_kayitlari
    ]

    return PublicProfileResponse(
        username=target.username, created_at=target.created_at,
        total_portfolio_value=round(total_value, 2), profit_loss_pct=round(profit_loss_pct, 2),
        achievements=achievements, top_holdings=top_holdings, profile_public=target.profile_public,
        career_points=career_points, career_rank_label=rutbe_hesapla(career_points),
        hall_of_fame_placements=hall_of_fame_placements, game_points=target.game_points or 0,
        equipped_frame_color=(esya_bul(target.equipped_frame_id) or {}).get("deger"),
        equipped_title_text=(esya_bul(target.equipped_title_id) or {}).get("deger"),
        duel_wins=target.duel_wins or 0,
    )


@app.post("/api/user/profile-visibility")
def update_profile_visibility(
    body: ProfileVisibilityUpdateRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Kullanıcının kendi profil vitrinini (rozetler + en büyük pozisyonlar) açıp kapatmasını sağlar."""
    current_user.profile_public = body.profile_public
    db.commit()
    return {"profile_public": current_user.profile_public}


# --- TEMATİK SEPETLER ---

def _basket_holdings_response(db: Session, tanim: Dict[str, str]) -> BasketSummary:
    hisseler = sepet_hisseleri(db, tanim["id"]) or []
    holding_list = [
        BasketHolding(
            symbol=s.symbol, company_name=s.company_name,
            # _get_latest_db_price fiyat yoksa 0.0 döner (kodun geri kalanıyla
            # tutarlı) ama burada None'a çevriliyor — aksi halde arayüzde
            # "0,00 TL" gibi hissenin gerçekten sıfır değerinde olduğu izlenimi
            # verirdi (bkz. proje-özellikleri.md §11 "varsayılan iddia etme").
            current_price=_get_latest_db_price(db, s.id) or None,
        )
        for s in hisseler
    ]
    return BasketSummary(id=tanim["id"], isim=tanim["isim"], aciklama=tanim["aciklama"], hisseler=holding_list)


@app.get("/api/baskets", response_model=List[BasketSummary])
def get_baskets(db: Session = Depends(get_db)):
    """
    Küratörlü tematik sepetler (Temettü Kralları, Katılım Uyumlu Sepet vb.).
    Üyeler her istekte CANLI sorgulanır — ayrı bir "sepet üyeliği" tablosu
    yok, bu yüzden bir hissenin katılım durumu/Piotroski skoru değiştiğinde
    sepet içeriği elle senkronize edilmeden otomatik güncel kalır.
    """
    return [_basket_holdings_response(db, tanim) for tanim in sepet_tanimlari()]


@app.get("/api/baskets/{basket_id}", response_model=BasketSummary)
def get_basket_detail(basket_id: str, db: Session = Depends(get_db)):
    tanim = sepet_tanimi(basket_id)
    if not tanim:
        raise HTTPException(status_code=404, detail="Sepet bulunamadı.")
    return _basket_holdings_response(db, tanim)


@app.post("/api/baskets/{basket_id}/invest", response_model=BasketInvestResponse)
@limiter.limit("5/minute")
def invest_in_basket(
    request: Request, basket_id: str, body: BasketInvestRequest,
    current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db),
):
    """
    Sepetteki her hisseye EŞİT TL tutarı ayırıp tek seferde alım yapar —
    /api/trade (execute_trade) ile AYNI komisyon/bakiye/kayıt mantığını
    kullanır, ayrı bir işlem yolu icat edilmedi. Fiyatı olmayan hisse
    atlanır; payı diğerlerine yeniden dağıtılmaz (öngörülebilir kalsın diye
    — kullanıcı "1000 TL'yi 10 hisseye eşit böl" der, 9 hisse alınırsa
    kalan pay nakit olarak bakiyede kalır).
    """
    open_flag, _ = is_market_open()
    if not open_flag:
        raise HTTPException(
            status_code=400,
            detail="Borsa şu an kapalı. Sepet yatırımı yalnızca seans saatlerinde yapılabilir.",
        )

    tanim = sepet_tanimi(basket_id)
    if not tanim:
        raise HTTPException(status_code=404, detail="Sepet bulunamadı.")

    hisseler = sepet_hisseleri(db, basket_id) or []
    if not hisseler:
        raise HTTPException(status_code=400, detail="Bu sepette şu an hiç hisse yok.")

    fiyatli: List[tuple] = []
    atlananlar: List[str] = []
    for stock in hisseler:
        fiyat = _get_latest_db_price(db, stock.id)
        if fiyat:
            fiyatli.append((stock, fiyat))
        else:
            atlananlar.append(stock.symbol)

    if not fiyatli:
        raise HTTPException(status_code=400, detail="Sepetteki hiçbir hissenin güncel fiyatı yok.")

    pay = body.amount / len(fiyatli)
    # Komisyon dahil toplam maliyet TAM OLARAK `pay`e eşit olsun diye miktar
    # tersinden çözülür: total_cost = adet * fiyat * (1 + oran/100).
    komisyon_carpani = 1 + (KOMISYON_ORANI_PCT / 100.0)

    db.rollback()
    begin_write_transaction(db)
    try:
        current_user = db.query(models.User).filter_by(id=current_user.id).first()

        toplam_maliyet = 0.0
        toplam_komisyon = 0.0
        alinanlar: List[str] = []
        for stock, fiyat in fiyatli:
            adet = pay / (fiyat * komisyon_carpani)
            brut_tutar, komisyon, total_cost = alim_maliyeti(adet, fiyat)

            if float(current_user.virtual_balance) < total_cost:
                atlananlar.append(f"{stock.symbol} (yetersiz bakiye)")
                continue

            current_user.virtual_balance = float(current_user.virtual_balance) - total_cost

            portfolio_entry = db.query(models.Portfolio).filter_by(
                user_id=current_user.id, stock_id=stock.id, is_bot_portfolio=False
            ).first()
            if portfolio_entry:
                old_qty = float(portfolio_entry.quantity)
                old_cost = float(portfolio_entry.average_cost)
                new_qty = old_qty + adet
                portfolio_entry.quantity = new_qty
                portfolio_entry.average_cost = ((old_qty * old_cost) + total_cost) / new_qty
            else:
                db.add(models.Portfolio(
                    user_id=current_user.id, stock_id=stock.id, quantity=adet,
                    average_cost=total_cost / adet, is_bot_portfolio=False,
                ))

            record_transaction(
                db, user_id=current_user.id, stock_id=stock.id, action_type="AL",
                quantity=adet, price=fiyat, source="MANUAL", commission=komisyon,
            )
            toplam_maliyet += total_cost
            toplam_komisyon += komisyon
            alinanlar.append(stock.symbol)

        db.commit()
        return BasketInvestResponse(
            message=f"{tanim['isim']} sepetinden {len(alinanlar)} hisse alındı.",
            toplam_harcanan=round(toplam_maliyet, 2),
            toplam_komisyon=round(toplam_komisyon, 2),
            alinanlar=alinanlar,
            atlananlar=atlananlar,
            balance=round(float(current_user.virtual_balance), 2),
        )
    except Exception:
        db.rollback()
        raise
