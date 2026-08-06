"""
Bir kereye mahsus çalıştırılacak geriye dönük veri betiği: mevcut bot_logs geçmişinden
BotSession (oturum) kayıtlarını en iyi tahminle yeniden inşa eder.

BotSession özelliği eklenmeden önceki işlemler için ayrı bir oturum kimliği hiç
tutulmuyordu; bu script, "Bot durduruldu" / "Bot süresi (...) doldu" ile biten
zorunlu kapanış SAT kayıtlarını oturum sınırı olarak kullanıp geçmişi segmentlere
ayırır. Kesin değildir (özellikle işlemsiz geçen oturumların süresi tahminidir) ama
kullanıcıya makul bir geçmiş görünüm sağlar. Halihazırda açık olan (is_active=True)
botlar için son segment, UserBot.started_at kullanılarak kesin şekilde kapatılır.

Kullanım (sunucuda): ./venv/bin/python3 backfill_bot_sessions.py
"""
from database import SessionLocal
import models
from bot import BOT_STRATEGY_CONFIG, RISK_MODE_CONFIG, DEFAULT_RISK_MODE, DEFAULT_TIME_FRAME

_LABEL_TO_TIMEFRAME = {cfg["label"]: code for code, cfg in BOT_STRATEGY_CONFIG.items()}
_LABEL_TO_RISKMODE = {cfg["label"]: code for code, cfg in RISK_MODE_CONFIG.items()}


def _parse_timeframe_riskmode(reason_text: str):
    """
    '[1 Günlük (Gün İçi / Scalp) / 🚀 Agresif (Yüksek Risk)] ...' -> ('1D', 'aggressive')
    Etiketlerin kendisi de "/" içerdiğinden (örn. "Gün İçi / Scalp"), bracket içeriği
    "/" ile bölünemez — bilinen etiketlerle prefix eşleşmesi yapılır.
    """
    if not reason_text or "[" not in reason_text or "]" not in reason_text:
        return None, None
    bracket = reason_text.split("[", 1)[1].split("]", 1)[0]

    tf = None
    rest = None
    for label, code in _LABEL_TO_TIMEFRAME.items():
        if bracket.startswith(label):
            tf = code
            rest = bracket[len(label):].lstrip(" /").strip()
            break

    rm = None
    if rest:
        for label, code in _LABEL_TO_RISKMODE.items():
            if rest == label:
                rm = code
                break

    return tf, rm


def backfill_for_user(db, user_id: int, user_bot):
    existing = db.query(models.BotSession).filter_by(user_id=user_id).count()
    if existing > 0:
        print(f"  user {user_id}: zaten {existing} oturum var, atlanıyor.")
        return

    logs = db.query(models.BotLog)\
        .filter_by(user_id=user_id)\
        .order_by(models.BotLog.created_at.asc())\
        .all()
    if not logs:
        print(f"  user {user_id}: hiç işlem yok, atlanıyor.")
        return

    # Zorunlu kapanış (oturum sonu) kayıtlarının created_at'lerini bul (aynı ana ait
    # birden fazla SAT tek bir sınır sayılır).
    boundary_times = []
    for log in logs:
        if log.action_type == "SAT" and log.reason_text and (
            log.reason_text.startswith("Bot durduruldu") or log.reason_text.startswith("Bot süresi (")
        ):
            if not boundary_times or boundary_times[-1] != log.created_at:
                boundary_times.append(log.created_at)

    segments = []  # (start, end_or_None, logs_in_segment)
    cursor = 0
    prev_end = None
    for b_time in boundary_times:
        seg_logs = [l for l in logs[cursor:] if l.created_at <= b_time]
        cursor += len(seg_logs)
        if seg_logs:
            start = prev_end if prev_end else seg_logs[0].created_at
            segments.append((start, b_time, seg_logs))
        prev_end = b_time

    remaining = logs[cursor:]
    if user_bot and user_bot.is_active:
        # Hâlâ açık oturum: kesin başlangıç UserBot.started_at'ten alınır.
        segments.append((user_bot.started_at, None, remaining))
    elif remaining:
        start = prev_end if prev_end else remaining[0].created_at
        segments.append((start, remaining[-1].created_at, remaining))

    created = 0
    for start, end, seg_logs in segments:
        tf, rm = None, None
        for l in seg_logs:
            if l.action_type == "AL":
                tf, rm = _parse_timeframe_riskmode(l.reason_text)
                if tf:
                    break
        if not tf:
            tf = (user_bot.time_frame if user_bot else None) or DEFAULT_TIME_FRAME
        if not rm:
            rm = (user_bot.risk_profile if user_bot else None) or DEFAULT_RISK_MODE

        end_reason = None
        if end is not None:
            closing = next((l for l in reversed(seg_logs) if l.created_at == end), None)
            end_reason = closing.reason_text if closing else None

        db.add(models.BotSession(
            user_id=user_id, time_frame=tf, risk_mode=rm,
            started_at=start, ended_at=end, end_reason=end_reason,
        ))
        created += 1

    print(f"  user {user_id}: {created} oturum oluşturuldu.")


def main():
    db = SessionLocal()
    try:
        user_bots = db.query(models.UserBot).all()
        print(f"{len(user_bots)} kullanıcı botu bulundu, geriye dönük oturumlar oluşturuluyor...")
        for ub in user_bots:
            backfill_for_user(db, ub.user_id, ub)
        db.commit()
        print("Tamamlandı.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
