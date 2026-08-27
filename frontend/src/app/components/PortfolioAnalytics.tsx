"use client";

import React, { useEffect, useState } from "react";
import { PieChart, ShieldCheck, AlertTriangle, Layers } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface SectorItem {
  sector: string;
  value: number;
  pct: number;
  position_count: number;
}

interface PositionItem {
  symbol: string;
  value: number;
  pct: number;
}

interface Analytics {
  total_portfolio_value: number;
  cash_balance: number;
  stock_value: number;
  cash_pct: number;
  position_count: number;
  sectors: SectorItem[];
  positions: PositionItem[];
  top_position_symbol: string | null;
  top_position_pct: number;
  top_sector: string | null;
  top_sector_pct: number;
  effective_position_count: number;
  diversification_score: number;
  katilim_compliant_pct: number;
}

// Sektör çubuklarında tekrar eden, birbirinden ayırt edilebilir renk paleti.
// Kırmızı/yeşil bilinçli olarak kullanılmaz — bu renkler uygulamada kâr/zarar
// anlamı taşıyor, sektör renkleriyle karıştırılmamalı.
const SECTOR_COLORS = [
  "#F59E0B", "#3B82F6", "#A855F7", "#14B8A6",
  "#EC4899", "#84CC16", "#F97316", "#6366F1",
];

function scoreTone(score: number): { label: string; color: string } {
  if (score >= 70) return { label: "İyi dağılmış", color: "#10B981" };
  if (score >= 40) return { label: "Orta düzeyde", color: "#F59E0B" };
  return { label: "Yoğunlaşmış", color: "#F43F5E" };
}

/**
 * Portföyün sektör dağılımını ve yoğunlaşma (konsantrasyon) riskini gösterir.
 * Veriler /api/portfolio/analytics'ten gelir; hesap tamamen mevcut portföy
 * pozisyonlarından yapılır, dışarıdan ek veri kaynağı kullanılmaz.
 */
export default function PortfolioAnalytics({ refreshKey }: { refreshKey?: number }) {
  const { token } = useAuth();
  const [data, setData] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;

    (async () => {
      try {
        const res = await fetch(`${API_BASE}/portfolio/analytics`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok && !cancelled) setData(await res.json());
      } catch (err) {
        console.error("Portföy analizi alınamadı:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [token, refreshKey]);

  if (loading || !data) return null;
  // Hiç hisse yoksa gösterilecek bir dağılım da yok
  if (data.position_count === 0) return null;

  const tone = scoreTone(data.diversification_score);
  const concentrated = data.top_position_pct >= 50 || data.top_sector_pct >= 60;

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5 space-y-5">
      <h3 className="text-sm font-bold text-white tracking-wide uppercase flex items-center gap-1.5">
        <PieChart className="w-4 h-4 text-[#F59E0B]" /> Portföy Dağılım Analizi
      </h3>

      {/* Özet kartlar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-3">
          <span className="text-[9px] text-gray-500 uppercase font-bold">Çeşitlendirme</span>
          <p className="text-sm font-bold tabular-nums mt-0.5" style={{ color: tone.color }}>
            {data.diversification_score}/100
          </p>
          <p className="text-[9px] text-gray-500 mt-0.5">{tone.label}</p>
        </div>
        <div className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-3">
          <span className="text-[9px] text-gray-500 uppercase font-bold">Etkin Pozisyon</span>
          <p className="text-sm font-bold text-white tabular-nums mt-0.5">
            {data.effective_position_count}
          </p>
          <p className="text-[9px] text-gray-500 mt-0.5">{data.position_count} hisseden</p>
        </div>
        <div className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-3">
          <span className="text-[9px] text-gray-500 uppercase font-bold">Nakit Oranı</span>
          <p className="text-sm font-bold text-white tabular-nums mt-0.5">%{data.cash_pct}</p>
          <p className="text-[9px] text-gray-500 mt-0.5">yatırılmamış</p>
        </div>
        <div className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-3">
          <span className="text-[9px] text-gray-500 uppercase font-bold flex items-center gap-1">
            <ShieldCheck className="w-2.5 h-2.5" /> Katılım
          </span>
          <p className="text-sm font-bold text-[#10B981] tabular-nums mt-0.5">
            %{data.katilim_compliant_pct}
          </p>
          <p className="text-[9px] text-gray-500 mt-0.5">uyumlu hisse</p>
        </div>
      </div>

      {concentrated && (
        <div className="flex items-start gap-2 bg-[#F59E0B]/10 border border-[#F59E0B]/25 rounded-lg px-3 py-2">
          <AlertTriangle className="w-3.5 h-3.5 text-[#F59E0B] shrink-0 mt-0.5" />
          <p className="text-[11px] text-gray-300 leading-relaxed">
            Portföyünüz yoğunlaşmış görünüyor:{" "}
            {data.top_position_pct >= 50 && (
              <>
                <span className="font-semibold text-white">{data.top_position_symbol}</span> tek başına
                hisse değerinizin %{data.top_position_pct}&apos;ini oluşturuyor
                {data.top_sector_pct >= 60 ? ", " : ". "}
              </>
            )}
            {data.top_sector_pct >= 60 && (
              <>
                <span className="font-semibold text-white">{data.top_sector}</span> sektörü %
                {data.top_sector_pct} ağırlığa sahip.{" "}
              </>
            )}
            Tek bir hisse veya sektördeki olumsuz bir haber portföyün tamamını doğrudan etkiler.
          </p>
        </div>
      )}

      {/* Pozisyon ağırlıkları — hangi hisse portföyün yüzde kaçı.
          Sektör dağılımı "hangi alanlara yayıldım" sorusunu, bu ise "tek bir
          hisseye ne kadar bağımlıyım" sorusunu yanıtlar; ikisi farklı risktir. */}
      {data.positions.length > 0 && (
        <div className="space-y-2.5">
          <h4 className="text-[11px] font-bold text-gray-400 uppercase tracking-wide flex items-center gap-1.5">
            <PieChart className="w-3 h-3" /> Pozisyon Ağırlıkları
          </h4>
          <div className="space-y-1.5">
            {data.positions.slice(0, 8).map((p) => (
              <div key={p.symbol} className="flex items-center gap-2">
                <span className="text-[11px] font-bold text-white w-14 shrink-0">{p.symbol}</span>
                <div className="flex-1 h-2 rounded-full bg-[#0B0E14] overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${p.pct}%`,
                      // %30 üzeri tek pozisyon yoğunlaşma riskidir; renkle uyarılır.
                      backgroundColor: p.pct >= 30 ? "#F43F5E" : p.pct >= 15 ? "#F59E0B" : "#10B981",
                    }}
                  />
                </div>
                <span className="text-[11px] tabular-nums text-gray-400 w-11 text-right shrink-0">
                  %{p.pct.toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sektör dağılımı */}
      <div className="space-y-2.5">
        <h4 className="text-[11px] font-bold text-gray-400 uppercase tracking-wide flex items-center gap-1.5">
          <Layers className="w-3 h-3" /> Sektör Dağılımı
        </h4>

        <div className="flex w-full h-2.5 rounded-full overflow-hidden bg-[#0B0E14]">
          {data.sectors.map((s, i) => (
            <div
              key={s.sector}
              style={{ width: `${s.pct}%`, backgroundColor: SECTOR_COLORS[i % SECTOR_COLORS.length] }}
              title={`${s.sector} · %${s.pct}`}
            />
          ))}
        </div>

        <div className="space-y-1.5 pt-1">
          {data.sectors.map((s, i) => (
            <div key={s.sector} className="flex items-center justify-between text-[11px]">
              <span className="flex items-center gap-2 text-gray-300">
                <span
                  className="w-2 h-2 rounded-sm shrink-0"
                  style={{ backgroundColor: SECTOR_COLORS[i % SECTOR_COLORS.length] }}
                />
                {s.sector}
                <span className="text-gray-600">({s.position_count})</span>
              </span>
              <span className="tabular-nums text-gray-400">
                %{s.pct}
                <span className="text-gray-600 ml-2">
                  {s.value.toLocaleString("tr-TR")} TL
                </span>
              </span>
            </div>
          ))}
        </div>
      </div>

      <p className="text-[10px] text-gray-600 leading-relaxed border-t border-[#242B35] pt-3">
        Çeşitlendirme skoru, pozisyon ağırlıklarının Herfindahl-Hirschman Endeksi&apos;ne (HHI) göre
        hesaplanır. &quot;Etkin pozisyon&quot;, eşit ağırlıklı kaç hisseye denk geldiğinizi gösterir —
        10 hisseniz olsa da biri portföyün %90&apos;ıysa etkin pozisyon 1&apos;e yakın çıkar.
        Bu bir yatırım tavsiyesi değildir.
      </p>
    </div>
  );
}
