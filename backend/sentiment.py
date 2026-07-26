"""
sentiment.py
------------
Basit sözlük tabanlı (lexicon-based) Türkçe duyarlılık skoru hesaplayıcı.
Topluluk yorumlarını -1.0 (çok negatif) ile +1.0 (çok pozitif) arasında puanlar.
Harici bir ML servisi gerektirmez; hafif ve deterministiktir.
"""

import re
from typing import List

POSITIVE_WORDS = [
    "yükseliyor", "yükselecek", "artıyor", "artacak", "güçlü", "harika", "süper",
    "al", "alım", "boğa", "kazanç", "kazandırır", "ucuz", "fırsat", "iyi",
    "olumlu", "başarılı", "yükseliş", "kâr", "kar", "toparlanıyor", "güvenilir",
]

NEGATIVE_WORDS = [
    "düşüyor", "düşecek", "zayıf", "kötü", "sat", "satış", "ayı", "zarar",
    "pahalı", "risk", "riskli", "olumsuz", "başarısız", "düşüş", "çöküyor",
    "kaybettirir", "tehlikeli", "endişe", "kırılgan",
]


def score_sentiment(text: str) -> float:
    """Metindeki pozitif/negatif kelime sayısına göre -1.0 ile +1.0 arası bir skor döner."""
    if not text:
        return 0.0

    normalized = re.sub(r"[^\wçğıöşü\s]", " ", text.lower(), flags=re.UNICODE)
    tokens: List[str] = normalized.split()

    pos_hits = sum(1 for t in tokens if t in POSITIVE_WORDS)
    neg_hits = sum(1 for t in tokens if t in NEGATIVE_WORDS)

    total = pos_hits + neg_hits
    if total == 0:
        return 0.0

    score = (pos_hits - neg_hits) / total
    return round(max(-1.0, min(1.0, score)), 2)


def aggregate_sentiment(scores: List[float]) -> dict:
    """Bir listedeki skorları pozitif/negatif/nötr yüzdelerine dönüştürür."""
    if not scores:
        return {"positive_pct": 0.0, "negative_pct": 0.0, "neutral_pct": 100.0}

    positive = sum(1 for s in scores if s > 0.15)
    negative = sum(1 for s in scores if s < -0.15)
    neutral = len(scores) - positive - negative
    total = len(scores)

    return {
        "positive_pct": round((positive / total) * 100, 1),
        "negative_pct": round((negative / total) * 100, 1),
        "neutral_pct": round((neutral / total) * 100, 1),
    }
