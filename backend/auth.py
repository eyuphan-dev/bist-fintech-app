import os
import jwt
import pytz
from datetime import datetime, timedelta
from typing import Union, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from market_hours import TR_TZ
import models

# Prod'da JWT_SECRET_KEY environment variable ZORUNLUDUR. Yerel geliştirme için
# geriye dönük uyumlu bir fallback sağlanır, ancak bu fallback ile üretime çıkmak
# token sahteciliğine (forgery) açık kapı bırakır.
SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
if not SECRET_KEY:
    if os.environ.get("ENVIRONMENT", "development") == "production":
        raise RuntimeError("JWT_SECRET_KEY environment variable üretimde zorunludur.")
    SECRET_KEY = "dev-only-insecure-secret-key-do-not-use-in-production"
ALGORITHM = "HS256"
# Sabit saatlik oturum sıfırlama: token, giriş saatinden 24 saat sonra değil,
# bir sonraki 09:00 (Türkiye saati) itibarıyla dolar. Böylece gün içinde ne
# zaman giriş yapılırsa yapılsın, kullanıcı ertesi sabah 09:00'a kadar tekrar
# login ekranına düşmez (rastgele saatlerde oturum sonu yerine öngörülebilir
# tek bir günlük sıfırlama noktası).
DAILY_SESSION_RESET_HOUR = 9
# Giriş saat 08:xx gibi sıfırlama saatine çok yakınsa oturum saniyeler içinde
# dolmasın diye asgari oturum süresi garantisi.
MIN_SESSION_MINUTES = 60

import bcrypt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        # bcrypt expects bytes
        plain_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(plain_bytes, hashed_bytes)
    except Exception:
        # Fallback for seeded dummy password
        return plain_password == hashed_password

def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")

def _next_daily_reset(now_tr: datetime) -> datetime:
    """Türkiye saatiyle bir sonraki 09:00 sıfırlama anını döner (asgari 1 saat garantili)."""
    reset_today = now_tr.replace(hour=DAILY_SESSION_RESET_HOUR, minute=0, second=0, microsecond=0)
    target = reset_today if now_tr < reset_today else reset_today + timedelta(days=1)
    if target - now_tr < timedelta(minutes=MIN_SESSION_MINUTES):
        target += timedelta(days=1)
    return target


def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire_tr = _next_daily_reset(datetime.now(TR_TZ))
        expire = expire_tr.astimezone(pytz.utc).replace(tzinfo=None)
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz kimlik bilgileri",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
        
    user = db.query(models.User).filter_by(username=username).first()
    if user is None:
        raise credentials_exception
    return user
