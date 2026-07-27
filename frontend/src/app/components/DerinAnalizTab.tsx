"use client";

import React, { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, Gauge, DollarSign, Percent, RefreshCw, AlertCircle, CheckCircle2, XCircle, ShieldAlert, Scale, Globe2, Crosshair, Users, HelpCircle } from "lucide-react";
import KatilimBadge from "./KatilimBadge";
import AnalysisGuideModal from "./AnalysisGuideModal";

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
  altman_z_score: number | null;
  altman_zone: "SAFE" | "GREY" | "DISTRESS" | null;
  debt_to_equity: number | null;
  net_fx_position: "POZITIF" | "NEGATIF" | "NOTR" | null;
  updated_at: string | null;
}

interface PivotLevels {
  symbol: string;
  as_of_date: string | null;
  previous_close: number | null;
  pivot: number | null;
  r1: number | null; r2: number | null; r3: number | null;
  s1: number | null; s2: number | null; s3: number | null;
  fib_236: number | null; fib_382: number | null; fib_500: number | null; fib_618: number | null;
  available: boolean;
  message: string | null;
}

interface ForeignHoldingTrend {
  symbol: string;
  current_pct: number | null;
  change_30d: number | null;
  change_90d: number | null;
  available: boolean;
  message: string | null;
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
  const [pivotLevels, setPivotLevels] = useState<PivotLevels | null>(null);
  const [foreignTrend, setForeignTrend] = useState<ForeignHoldingTrend | null>(null);
  const [showGuide, setShowGuide] = useState(false);

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

  const fetchPivotAndForeignTrend = async () => {
    try {
      const [pivotRes, foreignRes] = await Promise.all([
        fetch(`${API_BASE}/stocks/${symbol}/pivot-levels`),
        fetch(`${API_BASE}/stocks/${symbol}/foreign-holding-trend`),
      ]);
      if (pivotRes.ok) setPivotLevels(await pivotRes.json());
      if (foreignRes.ok) setForeignTrend(await foreignRes.json());
    } catch (err) {
      console.error("Pivot/Yabancı sahiplik verisi alınamadı:", err);
    }
  };

  useEffect(() => {
    fetchAnalysis();
    fetchPivotAndForeignTrend();
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

  const altmanZone = analysis?.altman_zone ?? null;
  const altmanZoneMeta: Record<string, { label: string; color: string }> = {
    SAFE: { label: "Güvenli Bölge", color: "text-[#10B981]" },
    GREY: { label: "Gri Bölge", color: "text-[#F59E0B]" },
    DISTRESS: { label: "Riskli Bölge", color: "text-[#F43F5E]" },
  };
  const altmanMeta = altmanZone ? altmanZoneMeta[altmanZone] : null;

  const fxPositionMeta: Record<string, { label: string; color: string }> = {
    POZITIF: { label: "Pozitif", color: "text-[#10B981]" },
    NEGATIF: { label: "Negatif", color: "text-[#F43F5E]" },
    NOTR: { label: "Nötr", color: "text-gray-300" },
  };
  const fxMeta = analysis?.net_fx_position ? fxPositionMeta[analysis.net_fx_position] : null;

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
      {showGuide && <AnalysisGuideModal onClose={() => setShowGuide(false)} />}

      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <KatilimBadge
            isCompliant={katilim.is_katilim_compliant}
            purificationRate={katilim.purification_rate}
            nonComplianceReason={katilim.non_compliance_reason}
          />
          <button
            onClick={() => setShowGuide(true)}
            title="Analiz Rehberi & Metrik Açıklamaları"
            className="text-gray-500 hover:text-[#F59E0B] transition shrink-0"
          >
            <HelpCircle className="w-4 h-4" />
          </button>
        </div>
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="flex items-center gap-1 text-[10px] text-gray-400 hover:text-white transition disabled:opacity-50 shrink-0"
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

          {/* Altman Z-Skoru */}
          <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-gray-400 uppercase font-bold tracking-widest flex items-center gap-1">
                <ShieldAlert className="w-3.5 h-3.5" /> Altman Z-Skoru
              </span>
              <span className={`text-2xl font-bold tabular-nums ${altmanMeta?.color ?? "text-gray-400"}`}>
                {analysis.altman_z_score !== null ? analysis.altman_z_score.toFixed(2) : "N/A"}
              </span>
            </div>
            {altmanMeta && (
              <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded inline-block ${altmanMeta.color} bg-white/5`}>
                {altmanMeta.label}
              </span>
            )}
            <p className="text-[10px] text-gray-500 mt-2">
              Finansal sıkıntı/iflas riski göstergesi: Z&gt;2.99 güvenli, 1.81-2.99 gri bölge, Z&lt;1.81 riskli kabul edilir.
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

          {/* Borç/Özkaynak & Net Döviz Pozisyonu */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-[#151921] border border-[#242B35] rounded-xl p-3">
              <span className="text-[10px] text-gray-400 uppercase font-bold tracking-widest flex items-center gap-1">
                <Scale className="w-3.5 h-3.5" /> Borç/Özkaynak
              </span>
              <p className="text-lg font-bold text-white tabular-nums mt-1">
                {analysis.debt_to_equity !== null ? analysis.debt_to_equity.toFixed(2) : "N/A"}
              </p>
            </div>
            <div className="bg-[#151921] border border-[#242B35] rounded-xl p-3">
              <span className="text-[10px] text-gray-400 uppercase font-bold tracking-widest flex items-center gap-1">
                <Globe2 className="w-3.5 h-3.5" /> Net Döviz Pozisyonu
              </span>
              <p className={`text-lg font-bold tabular-nums mt-1 ${fxMeta?.color ?? "text-gray-400"}`}>
                {fxMeta?.label ?? "N/A"}
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

          {/* Pivot Noktaları & Fibonacci Seviyeleri */}
          <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4">
            <span className="text-[10px] text-gray-400 uppercase font-bold tracking-widest flex items-center gap-1 mb-3">
              <Crosshair className="w-3.5 h-3.5" /> Pivot Noktaları & Fibonacci
            </span>
            {!pivotLevels ? (
              <p className="text-[11px] text-gray-500">Yükleniyor...</p>
            ) : !pivotLevels.available ? (
              <p className="text-[11px] text-gray-500">{pivotLevels.message ?? "Veri bulunamadı."}</p>
            ) : (
              <>
                <div className="grid grid-cols-3 gap-1.5 text-center">
                  <div className="bg-[#0B0E14] border border-[#F43F5E]/20 rounded-lg p-1.5">
                    <span className="text-[8px] text-gray-500 uppercase font-bold">R3</span>
                    <p className="text-[11px] font-bold text-[#F43F5E] tabular-nums">{pivotLevels.r3?.toFixed(2) ?? "—"}</p>
                  </div>
                  <div className="bg-[#0B0E14] border border-[#F43F5E]/20 rounded-lg p-1.5">
                    <span className="text-[8px] text-gray-500 uppercase font-bold">R2</span>
                    <p className="text-[11px] font-bold text-[#F43F5E] tabular-nums">{pivotLevels.r2?.toFixed(2) ?? "—"}</p>
                  </div>
                  <div className="bg-[#0B0E14] border border-[#F43F5E]/20 rounded-lg p-1.5">
                    <span className="text-[8px] text-gray-500 uppercase font-bold">R1</span>
                    <p className="text-[11px] font-bold text-[#F43F5E] tabular-nums">{pivotLevels.r1?.toFixed(2) ?? "—"}</p>
                  </div>
                  <div className="bg-[#F59E0B]/10 border border-[#F59E0B]/30 rounded-lg p-1.5 col-span-1">
                    <span className="text-[8px] text-gray-500 uppercase font-bold">Pivot</span>
                    <p className="text-[11px] font-bold text-[#F59E0B] tabular-nums">{pivotLevels.pivot?.toFixed(2) ?? "—"}</p>
                  </div>
                  <div className="bg-[#0B0E14] border border-[#10B981]/20 rounded-lg p-1.5">
                    <span className="text-[8px] text-gray-500 uppercase font-bold">S1</span>
                    <p className="text-[11px] font-bold text-[#10B981] tabular-nums">{pivotLevels.s1?.toFixed(2) ?? "—"}</p>
                  </div>
                  <div className="bg-[#0B0E14] border border-[#10B981]/20 rounded-lg p-1.5">
                    <span className="text-[8px] text-gray-500 uppercase font-bold">S2</span>
                    <p className="text-[11px] font-bold text-[#10B981] tabular-nums">{pivotLevels.s2?.toFixed(2) ?? "—"}</p>
                  </div>
                  <div className="bg-[#0B0E14] border border-[#10B981]/20 rounded-lg p-1.5 col-start-1">
                    <span className="text-[8px] text-gray-500 uppercase font-bold">S3</span>
                    <p className="text-[11px] font-bold text-[#10B981] tabular-nums">{pivotLevels.s3?.toFixed(2) ?? "—"}</p>
                  </div>
                </div>
                <div className="grid grid-cols-4 gap-1.5 mt-2">
                  <div className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-1.5 text-center">
                    <span className="text-[8px] text-gray-500 uppercase font-bold">%23.6</span>
                    <p className="text-[10px] font-semibold text-gray-300 tabular-nums">{pivotLevels.fib_236?.toFixed(2) ?? "—"}</p>
                  </div>
                  <div className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-1.5 text-center">
                    <span className="text-[8px] text-gray-500 uppercase font-bold">%38.2</span>
                    <p className="text-[10px] font-semibold text-gray-300 tabular-nums">{pivotLevels.fib_382?.toFixed(2) ?? "—"}</p>
                  </div>
                  <div className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-1.5 text-center">
                    <span className="text-[8px] text-gray-500 uppercase font-bold">%50</span>
                    <p className="text-[10px] font-semibold text-gray-300 tabular-nums">{pivotLevels.fib_500?.toFixed(2) ?? "—"}</p>
                  </div>
                  <div className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-1.5 text-center">
                    <span className="text-[8px] text-gray-500 uppercase font-bold">%61.8</span>
                    <p className="text-[10px] font-semibold text-gray-300 tabular-nums">{pivotLevels.fib_618?.toFixed(2) ?? "—"}</p>
                  </div>
                </div>
                {pivotLevels.as_of_date && (
                  <p className="text-[9px] text-gray-600 mt-2">Baz alınan gün: {pivotLevels.as_of_date}</p>
                )}
              </>
            )}
          </div>

          {/* Yabancı/Kurumsal Sahiplik Trendi */}
          <div className="bg-[#151921] border border-[#242B35] rounded-xl p-4">
            <span className="text-[10px] text-gray-400 uppercase font-bold tracking-widest flex items-center gap-1 mb-2">
              <Users className="w-3.5 h-3.5" /> Yabancı/Kurumsal Sahiplik Trendi
            </span>
            {!foreignTrend ? (
              <p className="text-[11px] text-gray-500">Yükleniyor...</p>
            ) : !foreignTrend.available ? (
              <p className="text-[11px] text-gray-500">{foreignTrend.message ?? "Veri bulunamadı."}</p>
            ) : (
              <>
                <p className="text-lg font-bold text-white tabular-nums">
                  {foreignTrend.current_pct !== null ? `%${foreignTrend.current_pct.toFixed(1)}` : "N/A"}
                </p>
                <div className="flex items-center gap-3 mt-1.5">
                  <span className="text-[10px] text-gray-500">
                    30G:{" "}
                    <span className={foreignTrend.change_30d === null ? "text-gray-500" : foreignTrend.change_30d >= 0 ? "text-[#10B981]" : "text-[#F43F5E]"}>
                      {foreignTrend.change_30d !== null ? `${foreignTrend.change_30d >= 0 ? "+" : ""}${foreignTrend.change_30d.toFixed(2)}` : "—"}
                    </span>
                  </span>
                  <span className="text-[10px] text-gray-500">
                    90G:{" "}
                    <span className={foreignTrend.change_90d === null ? "text-gray-500" : foreignTrend.change_90d >= 0 ? "text-[#10B981]" : "text-[#F43F5E]"}>
                      {foreignTrend.change_90d !== null ? `${foreignTrend.change_90d >= 0 ? "+" : ""}${foreignTrend.change_90d.toFixed(2)}` : "—"}
                    </span>
                  </span>
                </div>
                {foreignTrend.message && (
                  <p className="text-[9px] text-gray-600 mt-2">{foreignTrend.message}</p>
                )}
              </>
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
