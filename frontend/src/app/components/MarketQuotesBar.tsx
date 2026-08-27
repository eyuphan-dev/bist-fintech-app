"use client";

import React, { useEffect, useState } from "react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface Quote {
  symbol: string;
  label: string;
  price: number;
  change_1d_pct: number | null;
  change_30d_pct: number | null;
  as_of: string | null;
  source: string | null;
  is_live: boolean;
}

/** Sembole göre ondalık: kur/altın kuruş hassasiyetinde, endeks tam sayı okunur. */
function fmtPrice(symbol: string, v: number): string {
  const digits = symbol === "XU100" ? 0 : 2;
  return v.toLocaleString("tr-TR", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

/**
 * Sunucudan gelen zaman damgasını Türkiye saatine çevirir.
 *
 * DİKKAT: Backend UTC üretir ama damgada saat dilimi eki YOKTUR
 * ("2026-08-24T09:30:33"). JavaScript böyle bir metni YEREL saat sayar; ekli
 * "Z" olmadan sonuç kullanıcının saat diliminde 3 saat kayar. Bu yüzden ek
 * yoksa elle eklenir.
 */
function saatTR(iso: string | null): string | null {
  if (!iso) return null;
  const utc = /[Zz]|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`;
  const d = new Date(utc);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleTimeString("tr-TR", {
    hour: "2-digit", minute: "2-digit", timeZone: "Europe/Istanbul",
  });
}

const KAYNAK_ADI: Record<string, string> = {
  truncgil: "Truncgil",
  tcmb: "TCMB",
  yfinance: "Yahoo Finance",
};

/** İstemci tarafı tazeleme aralığı. Sunucu 15 dakikada bir yazıyor; 5 dakikada
 *  bir okumak, sayfayı açık bırakan kullanıcının en fazla 5 dakika geride
 *  kalmasını sağlar ve maliyeti tek bir hafif GET'tir. */
const TAZELEME_MS = 5 * 60 * 1000;

/**
 * Döviz kurları, gram altın ve BIST 100 şeridi.
 *
 * Değerler 15 dakikada bir yurt içi kaynaktan tazelenir (bkz. tr_market.py).
 * Eskiden günde tek sefer, TR 11:00'de yazılıyordu ve sayı ertesi sabaha kadar
 * donuyordu; ayrıca gram altın COMEX vadelisinden türetildiği için %1,16
 * yüksekti.
 */
export default function MarketQuotesBar({ refreshKey }: { refreshKey?: number }) {
  const { refreshTrigger } = useAuth();
  const [quotes, setQuotes] = useState<Quote[]>([]);

  useEffect(() => {
    let cancelled = false;

    const yukle = async () => {
      try {
        const res = await fetch(`${API_BASE}/market/quotes`);
        if (res.ok && !cancelled) setQuotes(await res.json());
      } catch (err) {
        console.error("Piyasa göstergeleri alınamadı:", err);
      }
    };

    yukle();
    const zamanlayici = setInterval(yukle, TAZELEME_MS);
    return () => { cancelled = true; clearInterval(zamanlayici); };
  }, [refreshKey, refreshTrigger]);

  if (quotes.length === 0) return null;

  // Alt bilgi satırı: en güncel damga + hangi kaynaklardan gelindiği.
  const canliOlanlar = quotes.filter((q) => q.is_live);
  const enSonDamga = canliOlanlar
    .map((q) => q.as_of)
    .filter((x): x is string => !!x)
    .sort()
    .pop() ?? null;
  const saat = saatTR(enSonDamga);
  const kaynaklar = Array.from(
    new Set(quotes.map((q) => (q.source ? KAYNAK_ADI[q.source] ?? q.source : null)).filter(Boolean))
  ).join(", ");

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {quotes.map((q) => {
          const ch = q.change_1d_pct;
          const positive = (ch ?? 0) >= 0;
          const color = ch === null ? "#8A99AD" : positive ? "#10B981" : "#F43F5E";
          return (
            <div key={q.symbol} className="min-w-0">
              <p className="text-[10px] text-gray-500 truncate">{q.label}</p>
              <p className="text-base font-bold text-white tabular-nums">
                {fmtPrice(q.symbol, q.price)}
              </p>
              <div className="flex items-center gap-2 text-[10px] tabular-nums">
                <span style={{ color }}>
                  {ch === null ? "—" : `${positive ? "+" : ""}${ch.toFixed(2)}%`}
                </span>
                {q.change_30d_pct !== null && (
                  <span className="text-gray-600">
                    30g {q.change_30d_pct > 0 ? "+" : ""}
                    {q.change_30d_pct.toFixed(1)}%
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-[10px] text-gray-600 mt-3 border-t border-[#242B35] pt-2.5">
        {saat ? (
          <>
            <span className="text-gray-500">{saat}</span> itibarıyla, 15 dakikada bir
            güncellenir.
          </>
        ) : (
          <>Gün sonu değerleridir, anlık değildir.</>
        )}
        {kaynaklar && <> Kaynak: {kaynaklar}.</>} Gram altın 995/1000 saflıkta
        külçe altının serbest piyasa değeridir; kuyumcu alım-satım fiyatı işçilik
        ve makas nedeniyle farklılık gösterir.
      </p>
    </div>
  );
}
