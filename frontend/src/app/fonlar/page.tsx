"use client";

import React, { useEffect, useState } from "react";
import { RefreshCw, PiggyBank, Rocket } from "lucide-react";
import { API_BASE } from "../context/AuthContext";

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
  is_katilim_compliant: boolean;
  lot_distribution_type: string | null;
}

export default function FonlarPage() {
  const [funds, setFunds] = useState<Fund[]>([]);
  const [ipos, setIpos] = useState<Ipo[]>([]);
  const [katilimOnly, setKatilimOnly] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [fundsRes, iposRes] = await Promise.all([
          fetch(`${API_BASE}/funds${katilimOnly ? "?katilim_only=true" : ""}`),
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
  }, [katilimOnly]);

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
            <PiggyBank className="w-4 h-4 text-[#F59E0B]" /> TEFAS Yatırım Fonları
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

        {loading ? (
          <div className="flex items-center justify-center py-10 text-gray-500 text-xs">
            <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#10B981]" />
            Fonlar yükleniyor...
          </div>
        ) : funds.length === 0 ? (
          <p className="text-xs text-gray-500 text-center py-6">Takip edilen fon bulunamadı.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {funds.map((fund) => (
              <div key={fund.code} className="bg-[#151921] border border-[#242B35] rounded-2xl p-4 space-y-2">
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
                  <span className={`font-bold ${riskColor(fund.risk_level)}`}>
                    Risk: {fund.risk_level ?? "N/A"}/7
                  </span>
                </div>

                {fund.latest_price ? (
                  <div className="pt-2 border-t border-[#242B35] flex items-center justify-between">
                    <span className="text-sm font-bold text-white tabular-nums">
                      {fund.latest_price.price.toFixed(4)} TL
                    </span>
                    {fund.latest_price.daily_return !== null && (
                      <span className={`text-xs font-semibold tabular-nums ${
                        fund.latest_price.daily_return >= 0 ? "text-[#10B981]" : "text-[#F43F5E]"
                      }`}>
                        {fund.latest_price.daily_return >= 0 ? "+" : ""}{fund.latest_price.daily_return}%
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
          <Rocket className="w-4 h-4 text-[#F59E0B]" /> Halka Arz Takvimi
        </h2>

        {ipos.length === 0 ? (
          // "Halka arz yok" demek yanıltıcı olurdu: veri kaynağımız olmadığı için
          // liste her zaman boş. Kullanıcı gerçek durumu ve nereye bakacağını bilsin.
          <div className="text-center py-6 space-y-2">
            <p className="text-xs text-gray-500">
              Halka arz takvimi için otomatik bir veri kaynağı henüz bağlı değil.
            </p>
            <a
              href="https://www.kap.org.tr/tr/bildirim-sorgu"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block text-[11px] font-semibold text-[#F59E0B] hover:underline"
            >
              Güncel halka arzlar için KAP&apos;a bakın →
            </a>
          </div>
        ) : (
          <div className="space-y-3">
            {ipos.map((ipo) => (
              <div key={ipo.id} className="bg-[#151921] border border-[#242B35] rounded-xl p-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-white">{ipo.company_name}</span>
                    {ipo.symbol && <span className="text-[10px] text-gray-500">({ipo.symbol})</span>}
                    {ipo.is_katilim_compliant && (
                      <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-[#10B981]/10 text-[#10B981]">
                        KATILIM
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-gray-500 mt-1">
                    Talep Toplama: {ipo.demand_collection_dates || "Belirtilmedi"} · Dağıtım: {ipo.lot_distribution_type || "Belirtilmedi"}
                  </p>
                </div>
                <span className="text-sm font-bold text-[#F59E0B] tabular-nums">
                  {ipo.offer_price ? `${ipo.offer_price.toFixed(2)} TL` : "Fiyat Belirlenmedi"}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
