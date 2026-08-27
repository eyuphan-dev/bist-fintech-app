"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Coins, RefreshCw, ExternalLink } from "lucide-react";
import { API_BASE } from "../context/AuthContext";

interface TemettuOlayi {
  symbol: string;
  company_name: string | null;
  event_type: string | null;
  payment_date: string;
  gross_rate_pct: number | null;
  net_rate_pct: number | null;
  gross_amount_per_share: number | null;
  currency: string | null;
  source_url: string | null;
  gross_yield_pct: number | null;
  days_until: number | null;
}

/**
 * Yaklaşan nakit temettü ödemeleri.
 *
 * Kaynak: KAP "Hak Kullanımı" bildirimleri (bkz. backend/temettu_takvimi.py).
 * `dividend_history` GEÇMİŞ ödemeleri tutar; burası şirketin KAP'a bildirdiği
 * ödeme PLANIDIR — uygulama katılım finansı odaklı olduğu için temettü merkezî
 * bir kavram ama kullanıcı bugüne kadar yalnızca geçmişi görebiliyordu.
 */
export default function TemettuTakvimi() {
  const [olaylar, setOlaylar] = useState<TemettuOlayi[]>([]);
  const [gecmisiGoster, setGecmisiGoster] = useState(false);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState(false);

  const getir = useCallback(async () => {
    setYukleniyor(true);
    setHata(false);
    try {
      const res = await fetch(
        `${API_BASE}/dividend-calendar?upcoming_only=${gecmisiGoster ? "false" : "true"}`
      );
      if (!res.ok) throw new Error(String(res.status));
      setOlaylar(await res.json());
    } catch {
      setHata(true);
    } finally {
      setYukleniyor(false);
    }
  }, [gecmisiGoster]);

  useEffect(() => {
    getir();
  }, [getir]);

  const tarihMetni = (iso: string): string => {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "short", year: "numeric" });
  };

  const kalanMetni = (gun: number | null): string => {
    if (gun === null) return "";
    if (gun === 0) return "bugün";
    if (gun > 0) return `${gun} gün sonra`;
    return `${Math.abs(gun)} gün önce`;
  };

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-bold text-white flex items-center gap-1.5">
          <Coins className="w-4 h-4 text-[#10B981]" /> Temettü Takvimi
        </h2>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setGecmisiGoster((v) => !v)}
            className={`px-2.5 py-1 rounded-lg text-[11px] font-bold border transition ${
              gecmisiGoster
                ? "bg-[#10B981]/10 border-[#10B981]/30 text-[#10B981]"
                : "bg-[#151921] border-[#242B35] text-gray-400 hover:text-white"
            }`}
          >
            Geçmişi de göster
          </button>
          <button
            onClick={getir}
            aria-label="Temettü takvimini yenile"
            className="text-gray-500 hover:text-white transition p-2 -m-2"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${yukleniyor ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {hata ? (
        <p className="text-xs text-gray-500 py-6 text-center">
          Temettü takvimi alınamadı. Yenilemeyi deneyin.
        </p>
      ) : yukleniyor && olaylar.length === 0 ? (
        <div className="flex items-center justify-center py-8 text-gray-500 text-xs">
          <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#10B981]" />
          Yükleniyor...
        </div>
      ) : olaylar.length === 0 ? (
        <p className="text-xs text-gray-500 py-6 text-center">
          Önümüzdeki 90 gün için KAP&apos;a bildirilmiş nakit temettü ödemesi yok.
        </p>
      ) : (
        <ul className="divide-y divide-[#242B35] border border-[#242B35] rounded-xl overflow-hidden">
          {olaylar.map((o) => (
            <li key={`${o.symbol}-${o.payment_date}`} className="bg-[#151921] px-4 py-3">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <Link
                      href={`/hisse/${o.symbol}`}
                      className="text-sm font-bold text-white hover:text-[#10B981] transition"
                    >
                      {o.symbol}
                    </Link>
                    {o.company_name && (
                      <span className="text-[11px] text-gray-500 truncate max-w-[190px]">
                        {o.company_name}
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-gray-500 mt-0.5">
                    {tarihMetni(o.payment_date)}
                    {o.days_until !== null && (
                      <span className="text-gray-600"> · {kalanMetni(o.days_until)}</span>
                    )}
                  </p>
                </div>

                <div className="text-right shrink-0">
                  {/* Tutar YALNIZCA varsa gösterilir; yoksa oran gösterilir.
                      İkisi de yoksa hiçbir sayı uydurulmaz. */}
                  {o.gross_amount_per_share !== null ? (
                    <span className="text-sm font-bold text-white tabular-nums block">
                      {o.gross_amount_per_share.toFixed(4)} TL
                      <span className="text-[10px] text-gray-500 font-normal"> / pay</span>
                    </span>
                  ) : o.gross_rate_pct !== null ? (
                    <span className="text-sm font-bold text-white tabular-nums block">
                      %{o.gross_rate_pct.toFixed(2)}
                    </span>
                  ) : (
                    <span className="text-[11px] text-gray-600">Tutar bildirilmedi</span>
                  )}

                  {o.gross_yield_pct !== null && (
                    <span className="text-[11px] font-semibold text-[#10B981] tabular-nums">
                      brüt verim %{o.gross_yield_pct.toFixed(2)}
                    </span>
                  )}
                  {o.source_url && (
                    <a
                      href={o.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[10px] text-gray-500 hover:text-[#10B981] flex items-center gap-0.5 justify-end mt-0.5"
                    >
                      KAP <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      <p className="text-[10px] text-gray-600 leading-relaxed">
        Tutarlar şirketin KAP&apos;a bildirdiği <strong>brüt</strong> orandan hesaplanır
        (1 TL nominal paya göre). Net tutar stopaj sonrası kalan kısımdır ve KAP
        bildiriminde ayrıca yer alır. Ödeme planları ödeme tarihinden önce değişebilir.
      </p>
    </section>
  );
}
