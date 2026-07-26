"use client";

import React, { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Gauge, DollarSign, Percent, RefreshCw, AlertCircle, CheckCircle2, XCircle } from "lucide-react";
import KatilimBadge from "./KatilimBadge";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";

interface CompanyAnalysis {
  piotroski_score: number | null;
  pe_ratio: number | null;
  pb_ratio: number | null;
  ev_ebitda: number | null;
  sector_pe_avg: number | null;
  fair_value: number | null;
  discount_rate: number | null;
  roe: number | null;
  gross_margin: number | null;
  net_margin: number | null;
  fx_exposure_text: string | null;
  interest_sensitivity_text: string | null;
  updated_at: string | null;
}

interface StockProData {
  symbol: string;
  company_name: string;
  katilim: {
    is_katilim_compliant: boolean;
    purification_rate: number;
    non_compliance_reason: string | null;
  };
  analysis: CompanyAnalysis | null;
}

interface DerinAnalizTabProps {
  symbol: string;
  currentPrice: number;
}

/** Toast/inline geri bildirim satırı: "Bilanço verileri güncellendi" ya da hata mesajı. */
function RefreshFeedback({ feedback }: { feedback: { type: "success" | "error"; text: string } }) {
  const isSuccess = feedback.type === "success";
  return (
    <div
      className={`flex items-center gap-2 rounded-lg px-3 py-2 text-[11px] font-medium border ${
        isSuccess
          ? "bg-[#10B981]/10 border-[#10B981]/25 text-[#10B981]"
          : "bg-[#F43F5E]/10 border-[#F43F5E]/25 text-[#F43F5E]"
      }`}
    >
      {isSuccess ? <CheckCircle2 className="w-3.5 h-3.5 shrink-0" /> : <XCircle className="w-3.5 h-3.5 shrink-0" />}
      {feedback.text}
    </div>
  );
}

export default function DerinAnalizTab({ symbol, currentPrice }: DerinAnalizTabProps) {
  const [data, setData] = useState<StockProData | null>(null);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshFeedback, setRefreshFeedback] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const fetchAnalysis = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/stocks/${symbol}/analysis`);
      if (res.ok) setData(await res.json());
    } catch (err) {
      console.error("Derin Bilanço Analizi verisi alınamadı:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalysis();
    setRefreshFeedback(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol]);

  // Geri bildirim mesajını birkaç saniye sonra otomatik kapat
  useEffect(() => {
    if (!refreshFeedback) return;
    const timer = setTimeout(() => setRefreshFeedback(null), 5000);
    return () => clearTimeout(timer);
  }, [refreshFeedback]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    setRefreshFeedback(null);
    try {
      const res = await fetch(`${API_BASE}/analysis/${symbol}/refresh`, { method: "POST" });
      const payload = await res.json().catch(() => null);

      if (res.ok && payload) {
        // Yeni analiz verisini mevcut state'e (katılım bilgisi korunarak) uygula
        setData((prev) =>
          prev
            ? { ...prev, analysis: payload }
            : { symbol, company_name: "", katilim: { is_katilim_compliant: false, purification_rate: 0, non_compliance_reason: null }, analysis: payload }
        );
        setRefreshFeedback({ type: "success", text: "Bilanço verileri güncellendi." });
      } else {
        const message = (payload && (payload.detail || payload.message)) || "Analiz tazelenemedi.";
        setRefreshFeedback({ type: "error", text: message });
      }
    } catch (err) {
      console.error("Analiz tazeleme hatası:", err);
      setRefreshFeedback({ type: "error", text: "Sunucuya bağlanılamadı. Analiz tazelenemedi." });
    } finally {
      setIsRefreshing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10 text-gray-500 text-xs">
        <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#F59E0B]" />
        Derin Bilanço Analizi yükleniyor...
      </div>
    );
  }

  if (!data) {
    return <p className="text-xs text-gray-500 text-center py-6">Analiz verisi bulunamadı.</p>;
  }

  const { katilim, analysis } = data;
  const score = analysis?.piotroski_score ?? null;
  const scoreColor = score === null ? "text-gray-400" : score >= 7 ? "text-[#10B981]" : score >= 4 ? "text-[#F59E0B]" : "text-[#F43F5E]";

  const fairValue = analysis?.fair_value ?? null;
  const potentialPct = fairValue && currentPrice ? ((fairValue - currentPrice) / currentPrice) * 100 : null;

  const peVsSector =
    analysis?.pe_ratio && analysis?.sector_pe_avg
      ? analysis.pe_ratio < analysis.sector_pe_avg
        ? "Sektöre Göre Ucuz"
        : "Sektöre Göre Pahalı"
      : null;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <KatilimBadge
          isCompliant={katilim.is_katilim_compliant}
          purificationRate={katilim.purification_rate}
          nonComplianceReason={katilim.non_compliance_reason}
        />
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="flex items-center gap-1 text-[10px] text-gray-400 hover:text-white transition disabled:opacity-50"
        >
          <RefreshCw className={`w-3 h-3 ${isRefreshing ? "animate-spin" : ""}`} />
          {isRefreshing ? "Tazeleniyor..." : "Analizi Tazele"}
        </button>
      </div>

      {refreshFeedback && <RefreshFeedback feedback={refreshFeedback} />}

      {!analysis ? (
        <div className="flex items-start gap-2 bg-[#151921] border border-[#242B35] rounded-lg p-3">
          <AlertCircle className="w-4 h-4 text-[#F59E0B] shrink-0 mt-0.5" />
          <p className="text-[11px] text-gray-400">
            Bu hisse için derin analiz verisi henüz hesaplanmamış. "Analizi Tazele" butonuna tıklayın.
          </p>
        </div>
      ) : (
        <>
          {/* Piotroski Skoru */}
          <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] text-gray-400 uppercase font-bold tracking-widest flex items-center gap-1">
                <Gauge className="w-3.5 h-3.5" /> Piotroski F-Skoru
              </span>
              <span className={`text-2xl font-bold tabular-nums ${scoreColor}`}>
                {score !== null ? `${score}/9` : "N/A"}
              </span>
            </div>
            <div className="w-full h-1.5 bg-[#0B0E14] rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${score !== null && score >= 7 ? "bg-[#10B981]" : score !== null && score >= 4 ? "bg-[#F59E0B]" : "bg-[#F43F5E]"}`}
                style={{ width: `${score !== null ? (score / 9) * 100 : 0}%` }}
              />
            </div>
            <p className="text-[10px] text-gray-500 mt-2">
              Finansal sağlamlık göstergesi: 7-9 güçlü, 4-6 nötr, 0-3 zayıf kabul edilir.
            </p>
          </div>

          {/* F/K & Sektör Karşılaştırması */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-[#151921] border border-[#242B35] rounded-xl p-3">
              <span className="text-[10px] text-gray-400 uppercase font-bold tracking-widest">F/K Oranı</span>
              <p className="text-lg font-bold text-white tabular-nums mt-1">
                {analysis.pe_ratio?.toFixed(2) ?? "N/A"}
              </p>
              {peVsSector && (
                <span
                  className={`text-[10px] font-semibold px-1.5 py-0.5 rounded mt-1 inline-block ${
                    peVsSector === "Sektöre Göre Ucuz" ? "bg-[#10B981]/10 text-[#10B981]" : "bg-[#F43F5E]/10 text-[#F43F5E]"
                  }`}
                >
                  {peVsSector}
                </span>
              )}
            </div>

            <div className="bg-[#151921] border border-[#242B35] rounded-xl p-3">
              <span className="text-[10px] text-gray-400 uppercase font-bold tracking-widest">PD/DD Oranı</span>
              <p className="text-lg font-bold text-white tabular-nums mt-1">
                {analysis.pb_ratio?.toFixed(2) ?? "N/A"}
              </p>
              <span className="text-[10px] text-gray-500 mt-1 inline-block">
                Sektör F/K: {analysis.sector_pe_avg?.toFixed(2) ?? "N/A"}
              </span>
            </div>
          </div>

          {/* Makul Değer vs Fiyat */}
          <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4">
            <span className="text-[10px] text-gray-400 uppercase font-bold tracking-widest flex items-center gap-1">
              <DollarSign className="w-3.5 h-3.5" /> Graham Makul Değer
            </span>
            <div className="flex items-end justify-between mt-2">
              <div>
                <p className="text-xl font-bold text-white tabular-nums">
                  {fairValue !== null ? `${fairValue.toFixed(2)} TL` : "N/A"}
                </p>
                <p className="text-[10px] text-gray-500 mt-0.5">Güncel Fiyat: {currentPrice.toFixed(2)} TL</p>
              </div>
              {potentialPct !== null && (
                <span
                  className={`flex items-center gap-1 text-sm font-bold tabular-nums ${
                    potentialPct >= 0 ? "text-[#10B981]" : "text-[#F43F5E]"
                  }`}
                >
                  {potentialPct >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                  {potentialPct >= 0 ? "+" : ""}
                  {potentialPct.toFixed(1)}%
                </span>
              )}
            </div>
          </div>

          {/* Kârlılık Oranları */}
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-[#151921] border border-[#242B35] rounded-lg p-2.5 text-center">
              <span className="text-[9px] text-gray-500 uppercase font-bold">ROE</span>
              <p className="text-sm font-bold text-white tabular-nums mt-0.5">
                {analysis.roe !== null ? `%${analysis.roe.toFixed(1)}` : "N/A"}
              </p>
            </div>
            <div className="bg-[#151921] border border-[#242B35] rounded-lg p-2.5 text-center">
              <span className="text-[9px] text-gray-500 uppercase font-bold">Brüt Marj</span>
              <p className="text-sm font-bold text-white tabular-nums mt-0.5">
                {analysis.gross_margin !== null ? `%${analysis.gross_margin.toFixed(1)}` : "N/A"}
              </p>
            </div>
            <div className="bg-[#151921] border border-[#242B35] rounded-lg p-2.5 text-center">
              <span className="text-[9px] text-gray-500 uppercase font-bold">Net Marj</span>
              <p className="text-sm font-bold text-white tabular-nums mt-0.5">
                {analysis.net_margin !== null ? `%${analysis.net_margin.toFixed(1)}` : "N/A"}
              </p>
            </div>
          </div>

          {/* FX & Faiz Hassasiyeti Rozetleri */}
          <div className="space-y-2">
            {analysis.fx_exposure_text && (
              <div className="flex items-start gap-2 bg-[#151921] border border-[#242B35] rounded-lg p-2.5">
                <Percent className="w-3.5 h-3.5 text-[#F59E0B] shrink-0 mt-0.5" />
                <div>
                  <span className="text-[9px] text-gray-500 uppercase font-bold tracking-wide">Döviz Kuru Riski</span>
                  <p className="text-[11px] text-gray-300 mt-0.5">{analysis.fx_exposure_text}</p>
                </div>
              </div>
            )}
            {analysis.interest_sensitivity_text && (
              <div className="flex items-start gap-2 bg-[#151921] border border-[#242B35] rounded-lg p-2.5">
                <Percent className="w-3.5 h-3.5 text-[#F59E0B] shrink-0 mt-0.5" />
                <div>
                  <span className="text-[9px] text-gray-500 uppercase font-bold tracking-wide">Faiz Hassasiyeti</span>
                  <p className="text-[11px] text-gray-300 mt-0.5">{analysis.interest_sensitivity_text}</p>
                </div>
              </div>
            )}
          </div>

          {analysis.updated_at && (
            <p className="text-[10px] text-gray-600 text-right">
              Son güncelleme: {new Date(analysis.updated_at).toLocaleString("tr-TR")}
            </p>
          )}
        </>
      )}
    </div>
  );
}
