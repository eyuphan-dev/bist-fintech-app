from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Üretim: kendi VPS'imizde (DigitalOcean, Frankfurt) çalışan PostgreSQL.
# DATABASE_URL tanımlıysa ona bağlanılır; tanımlı değilse (yerel geliştirme)
# SQLite dosyasına düşülür. SQLite ÜRETİMDE KULLANILMAMALIDIR — eşzamanlı
# yazmada kilitlenir ve scheduler ile API aynı anda yazar.
#
# Bazı barındırma sağlayıcıları URL'yi "postgres://" şemasıyla verir, SQLAlchemy
# 2.x ise "postgresql://" bekler; aşağıdaki normalleştirme bunun içindir.
_database_url = os.environ.get("DATABASE_URL")
IS_SQLITE = not _database_url

if _database_url:
    if _database_url.startswith("postgres://"):
        _database_url = _database_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URL = _database_url
    engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True)
else:
    db_path = os.path.join(BASE_DIR, "bist_app.db")
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_path}"
    # SQLite requires check_same_thread=False for multi-threaded applications (like FastAPI + APScheduler)
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_busy_timeout(dbapi_connection, connection_record):
        """
        FastAPI istek thread'leri, APScheduler'ın arka plan thread'i ve BEGIN IMMEDIATE
        kullanan atomik trade/order işlemleri aynı SQLite dosyasına eşzamanlı yazmaya
        çalışabilir. Varsayılan busy_timeout=0 olduğu için bu durumda SQLite anında
        "database is locked" hatası fırlatır. 5 saniyelik bir busy_timeout, kilidi tutan
        işlem bitene kadar bekleyip otomatik tekrar denemesini sağlar.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def begin_write_transaction(db):
    """
    Atomik yazma transaction'ı başlatır (anti-double-spending: eşzamanlı iki
    alım/satım/bakiye güncelleme isteğinin birbirinin üzerine yazmasını önler).

    SQLite'ta "BEGIN IMMEDIATE" ile yazma kilidi hemen alınır. PostgreSQL bu
    sözdizimini DESTEKLEMEZ ("IMMEDIATE" geçerli bir transaction_mode değildir,
    syntax error fırlatır) — bu yüzden Postgres'te düz "BEGIN" kullanılır;
    Postgres'in varsayılan READ COMMITTED izolasyon seviyesi + satır bazlı
    kilitleme (UPDATE/SELECT...FOR UPDATE benzeri erişimlerde) SQLite'daki
    IMMEDIATE kilidin sağladığı "yazma çakışmasını önleme" garantisinin dengini verir.
    """
    db.execute(text("BEGIN" if not IS_SQLITE else "BEGIN IMMEDIATE"))
