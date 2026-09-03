"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  ShoppingBasket, RefreshCw, TrendingUp, ShieldCheck, Building2, Coins, Info, X,
} from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface BasketHolding {
  symbol: string;
  company_name: string;
  current_price: number | null;
}

interface Basket {
  id: string;
  isim: string;
  aciklama: string;
  hisseler: BasketHolding[];
}

// Her sepet id'sine sabit bir ikon/renk atanır -- yalnızca görsel ayrım için,
// backend'den gelmez (backend tasarımdan bağımsız kalsın diye).
const SEPET_GORUNUM: Record<string, { icon: React.ElementType; renk: string }> = {
  "temettu-krallari": { icon: Coins, renk: "#F59E0B" },
  "katilim-uyumlu": { icon: ShieldCheck, renk: "#10B981" },
  "saglam-bilanco": { icon: Building2, renk: "#60A5FA" },
  "buyuk-sermaye": { icon: TrendingUp, renk: "#E879F9" },
};

export default function BasketsPage() {
  const { token, loading: authLoading, refreshTrigger, bumpRefresh } = useAuth();
  const [baskets, setBaskets] = useState<Basket[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeBasket, setActiveBasket] = useState<Basket | null>(null);
  const [amount, setAmount] = useState("1000");
  const [investLoading, setInvestLoading] = useState(false);
  const [result, setResult] = useState<{ text: string; isError: boolean } | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/baskets`);
        if (res.ok && !cancelled) setBaskets(await res.json());
      } catch (err) {
        console.error("Sepet verisi alınamadı:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [refreshTrigger]);

  const openBasket = (basket: Basket) => {
    setActiveBasket(basket);
    setAmount("1000");
    setResult(null);
  };

  const handleInvest = async () => {
    if (!activeBasket || !token) return;
    const tutar = Number.parseFloat(amount);
    if (!Number.isFinite(tutar) || tutar <= 0) {
      setResult({ text: "Lütfen 0'dan büyük bir tutar girin.", isError: true });
      return;
    }
    setInvestLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/baskets/${activeBasket.id}/invest`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ amount: tutar }),
      });
      const data = await res.json();
      if (res.ok) {
        let text = data.message as string;
        if (data.atlananlar?.length) text += ` Fiyatı olmayan/atlanan: ${data.atlananlar.join(", ")}.`;
        setResult({ text, isError: false });
        bumpRefresh();
      } else {
        setResult({ text: data.detail || "Sepet yatırımı başarısız.", isError: true });
      }
    } catch {
      setResult({ text: "İşlem sırasında hata oluştu.", isError: true });
    } finally {
      setInvestLoading(false);
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center">
        <RefreshCw className="w-10 h-10 text-[#10B981] animate-spin mb-4" />
        <p className="text-gray-400 font-medium">Yükleniyor...</p>
      </div>
    );
  }

  if (!token) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-6">
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5 text-center">
          <p className="text-xs text-gray-400">Tematik sepetleri görmek için giriş yapmalısınız.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <ShoppingBasket className="w-5 h-5 text-[#F59E0B]" /> Tematik Sepetler
        </h1>
        <p className="text-xs text-gray-500 mt-1">
          Küratörlü hisse gruplarına tek seferde yatırım yapın — tutarınız sepetteki
          hisselere eşit olarak bölünür. Sepetler, gerçek katılım/temettü/bilanço
          verisine göre otomatik güncellenir.
        </p>
      </div>

      {loading ? (
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-8 text-center">
          <p className="text-xs text-gray-500">Yükleniyor...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {baskets.map((basket) => {
            const gorunum = SEPET_GORUNUM[basket.id] ?? { icon: ShoppingBasket, renk: "#8A99AD" };
            const Icon = gorunum.icon;
            const fiyatliSayisi = basket.hisseler.filter((h) => h.current_price !== null).length;
            return (
              <div key={basket.id} className="bg-[#151921] border border-[#242B35] rounded-xl p-5 flex flex-col">
                <div className="flex items-center gap-2.5 mb-2">
                  <span
                    className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                    style={{ backgroundColor: `${gorunum.renk}1A`, color: gorunum.renk }}
                  >
                    <Icon className="w-5 h-5" strokeWidth={1.5} />
                  </span>
                  <h3 className="text-sm font-bold text-white">{basket.isim}</h3>
                </div>
                <p className="text-xs text-gray-500 mb-3">{basket.aciklama}</p>

                <div className="flex flex-wrap gap-1.5 mb-4">
                  {basket.hisseler.length === 0 ? (
                    <span className="text-[11px] text-gray-600">Şu an bu kritere uyan hisse yok.</span>
                  ) : (
                    basket.hisseler.map((h) => (
                      <Link
                        key={h.symbol}
                        href={`/hisse/${h.symbol}`}
                        className="text-[10px] font-semibold px-1.5 py-1 rounded bg-[#0B0E14] border border-[#242B35] text-gray-300 hover:text-white hover:border-gray-500 transition"
                      >
                        {h.symbol}
                      </Link>
                    ))
                  )}
                </div>

                <button
                  onClick={() => openBasket(basket)}
                  disabled={fiyatliSayisi === 0}
                  className="mt-auto min-h-[44px] rounded-lg bg-[#242B35] hover:bg-[#2E3641] disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-bold transition"
                >
                  Sepete Yatırım Yap
                </button>
              </div>
            );
          })}
        </div>
      )}

      <p className="text-[10px] text-gray-600 flex items-start gap-1.5">
        <Info className="w-3 h-3 shrink-0 mt-0.5" />
        <span>
          Sepet yatırımı, sepetteki her hisseye eşit TL tutarı ayırıp tek seferde piyasa
          fiyatından alım yapar (komisyon dahil). Fiyatı olmayan hisse atlanır, payı
          diğerlerine dağıtılmaz. Yalnızca borsa seans saatlerinde çalışır. Yatırım
          tavsiyesi değildir.
        </span>
      </p>

      {activeBasket && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 p-0 sm:p-4">
          <div className="w-full sm:max-w-sm bg-[#151921] border border-[#242B35] rounded-t-2xl sm:rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-white">{activeBasket.isim}</h3>
              <button
                onClick={() => setActiveBasket(null)}
                className="min-w-[36px] min-h-[36px] flex items-center justify-center text-gray-400 hover:text-white"
                aria-label="Kapat"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <label className="block text-[11px] font-semibold text-gray-400 mb-1.5">
              Toplam Yatırım Tutarı (TL)
            </label>
            <input
              type="number"
              inputMode="decimal"
              min={1}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="w-full min-h-[44px] px-3 rounded-lg bg-[#0B0E14] border border-[#242B35] text-white text-sm font-semibold tabular-nums mb-4 focus:outline-none focus:border-[#F59E0B]"
            />

            {result && (
              <p className={`text-[11px] mb-3 ${result.isError ? "text-[#F43F5E]" : "text-[#10B981]"}`}>
                {result.text}
              </p>
            )}

            <button
              onClick={handleInvest}
              disabled={investLoading}
              className="w-full min-h-[44px] rounded-lg bg-[#10B981] hover:bg-[#0FA271] disabled:opacity-50 text-[#0B0E14] text-sm font-bold transition"
            >
              {investLoading ? "İşleniyor..." : "Yatırımı Onayla"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
