"use client";

import React, { useEffect, useState } from "react";
import { RefreshCw, PiggyBank, Rocket, Search } from "lucide-react";
import { API_BASE } from "../context/AuthContext";
import { marketTextClass } from "../../lib/marketColor";

interface FundPrice {
  price: number;
  daily_return: number | null;
  monthly_return: number | null;
  yearly_return: number | null;
  recorded_date: string;
}

interface Fund {
  code: string;
  name: string;
  fund_type: string | null;
  risk_level: number | null;
  is_katilim_compliant: boolean;
  latest_price: FundPrice | null;
}

interface Ipo {
  id: number;
  company_name: string;
  symbol: string | null;
  offer_price: number | null;
  demand_collection_dates: string | null;
  // boolean DEĞİL: halka arz olan şirketin katılım uygunluğu bilinmiyor
  // (bilanço yok, KAP Katılım formu yok). null = değerlendirilmedi.
  is_katilim_compliant: boolean | null;
  lot_distribution_type: string | null;
  lot_count: number | null;
  broker: string | null;
  market: string | null;
  source_url: string | null;
}

export default function FonlarPage() {
  const [funds, setFunds] = useState<Fund[]>([]);
  const [ipos, setIpos] = useState<Ipo[]>([]);
  const [katilimOnly, setKatilimOnly] = useState(false);
  const [arama, setArama] = useState("");
  const [loading, setLoading] = useState(true);

  // TEFAS taraması fon sayısını 3'ten 390'a çıkardı; arama olmadan liste
  // gezinilemez hale geliyordu. Filtreleme sunucuda yapılır (yanıt 120 KB'a
  // kadar çıkabiliyor), bu yüzden her tuşa basışta istek atmamak için
  // 300 ms geciktirilir.
  useEffect(() => {
    const zamanlayici = setTimeout(() => {
      const fetchAll = async () => {
        try {
          const params = new URLSearchParams();
          if (katilimOnly) params.set("katilim_only", "true");
          if (arama.trim()) params.set("q", arama.trim());
          const [fundsRes, iposRes] = await Promise.all([
            fetch(`${API_BASE}/funds?${params.toString()}`),
            fetch(`${API_BASE}/ipos`),
          ]);
          if (fundsRes.ok) setFunds(await fundsRes.json());
          if (iposRes.ok) setIpos(await iposRes.json());
        } catch (err) {
          console.error("Fon/Halka arz verisi alınamadı:", err);
        } finally {
          setLoading(false);
        }
      };
      fetchAll();
    }, 300);
    return () => clearTimeout(zamanlayici);
  }, [katilimOnly, arama]);

  const riskColor = (level: number | null) => {
    if (level === null) return "text-gray-400";
    if (level <= 2) return "text-[#10B981]";
    if (level <= 4) return "text-[#F59E0B]";
    return "text-[#F43F5E]";
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-8">
      <div>
        <h1 className="text-xl font-bold text-white">Fonlar & Halka Arzlar</h1>
        <p className="text-xs text-gray-500 mt-1">TEFAS yatırım fonları ve güncel halka arz takvimi.</p>
      </div>

      {/* TEFAS Fonları */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-white uppercase tracking-wide flex items-center gap-1.5">
            <PiggyBank className="w-4 h-4 text-[#10B981]" /> TEFAS Yatırım Fonları
          </h2>
          <button
            onClick={() => setKatilimOnly((v) => !v)}
            className={`px-3 py-1.5 rounded-lg text-[11px] font-bold border transition ${
              katilimOnly
                ? "bg-[#10B981]/10 border-[#10B981]/30 text-[#10B981]"
                : "bg-[#151921] border-[#242B35] text-gray-400 hover:text-white"
            }`}
          >
            Yalnızca Katılım Fonları
          </button>
        </div>

        <div className="relative">
          <Search className="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            value={arama}
            onChange={(e) => setArama(e.target.value)}
            placeholder="Fon kodu veya adıyla ara (ör. AFT, Ziraat, kira sertifikası)"
            aria-label="Fon ara"
            className="w-full min-h-[44px] pl-9 pr-3 rounded-lg bg-[#151921] border border-[#242B35] text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-[#10B981]/50"
          />
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-10 text-gray-500 text-xs">
            <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#10B981]" />
            Fonlar yükleniyor...
          </div>
        ) : funds.length === 0 ? (
          <p className="text-xs text-gray-500 text-center py-6">
            {arama.trim() ? `"${arama.trim()}" için fon bulunamadı.` : "Takip edilen fon bulunamadı."}
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {funds.map((fund) => (
              <div key={fund.code} className="bg-[#151921] border border-[#242B35] rounded-xl p-4 space-y-2">
                <div className="flex items-start justify-between">
                  <div>
                    <span className="font-bold text-white">{fund.code}</span>
                    <p className="text-[11px] text-gray-500 mt-0.5 truncate max-w-[180px]">{fund.name}</p>
                  </div>
                  {fund.is_katilim_compliant && (
                    <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-[#10B981]/10 text-[#10B981] whitespace-nowrap">
                      KATILIM
                    </span>
                  )}
                </div>

                <div className="flex items-center justify-between text-xs">
                  <span className="text-gray-500">{fund.fund_type || "Fon"}</span>
                  {/* TEFAS bu uçta risk seviyesi vermiyor; uydurmak yerine
                      seviye yoksa alan hiç gösterilmez ("Risk: N/A/7" hem
                      çirkin hem de veri varmış izlenimi veriyordu). */}
                  {fund.risk_level !== null && (
                    <span className={`font-bold ${riskColor(fund.risk_level)}`}>
                      Risk: {fund.risk_level}/7
                    </span>
                  )}
                </div>

                {fund.latest_price ? (
                  <div className="pt-2 border-t border-[#242B35] flex items-center justify-between">
                    <span className="text-sm font-bold text-white tabular-nums">
                      {fund.latest_price.price.toFixed(4)} TL
                    </span>
                    {fund.latest_price.daily_return !== null && (
                      <span className={`text-xs font-semibold tabular-nums ${
                        marketTextClass(fund.latest_price.daily_return)
                      }`}>
                        {fund.latest_price.daily_return > 0 ? "+" : ""}{fund.latest_price.daily_return}%
                      </span>
                    )}
                  </div>
                ) : (
                  <p className="text-[10px] text-gray-600 pt-2 border-t border-[#242B35]">Fiyat verisi henüz güncellenmedi.</p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Halka Arzlar */}
      <section className="space-y-4">
        <h2 className="text-sm font-bold text-white uppercase tracking-wide flex items-center gap-1.5">
          <Rocket className="w-4 h-4 text-[#10B981]" /> Halka Arz Takvimi
        </h2>

        {ipos.length === 0 ? (
          <p className="text-xs text-gray-500 text-center py-6">
            Şu anda listelenen halka arz yok.
          </p>
        ) : (
          <div className="space-y-3">
            {ipos.map((ipo) => (
              <div key={ipo.id} className="bg-[#151921] border border-[#242B35] rounded-xl p-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold text-white">{ipo.company_name}</span>
                    {ipo.symbol && (
                      <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-[#242B35] text-gray-300">
                        {ipo.symbol}
                      </span>
                    )}
                    {/* Katılım rozeti YALNIZCA true iken çıkar. null "değerlendirilmedi"
                        demektir; halka arzda şirketin bilançosu da KAP Katılım formu da
                        yok, uygunluğu bilmiyoruz ve bilmediğimizi iddia etmiyoruz. */}
                    {ipo.is_katilim_compliant === true && (
                      <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-[#10B981]/10 text-[#10B981]">
                        KATILIM
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-gray-500 mt-1">
                    Talep toplama: {ipo.demand_collection_dates || "Belirtilmedi"}
                    {ipo.lot_distribution_type ? ` · ${ipo.lot_distribution_type}` : ""}
                    {ipo.lot_count ? ` · ${ipo.lot_count.toLocaleString("tr-TR")} lot` : ""}
                  </p>
                  {(ipo.broker || ipo.market) && (
                    <p className="text-[10px] text-gray-600 mt-0.5">
                      {ipo.broker}
                      {ipo.broker && ipo.market ? " · " : ""}
                      {ipo.market}
                    </p>
                  )}
                </div>
                <div className="text-right">
                  <span className="text-sm font-bold text-white tabular-nums block">
                    {ipo.offer_price ? `${ipo.offer_price.toFixed(2)} TL` : "Fiyat belirlenmedi"}
                  </span>
                  {ipo.source_url && (
                    <a
                      href={ipo.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[10px] text-[#10B981] hover:underline"
                    >
                      Detay →
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
