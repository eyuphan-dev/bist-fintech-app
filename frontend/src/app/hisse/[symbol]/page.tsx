"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import {
  ArrowLeft, RefreshCw, Gauge, Users, Calculator, Newspaper, LineChart as LineChartIcon,
  ChevronDown, ExternalLink, Bell,
} from "lucide-react";

import KatilimBadge from "../../components/KatilimBadge";
import DerinAnalizTab from "../../components/DerinAnalizTab";
import InsiderTrackerBadge from "../../components/InsiderTrackerBadge";
import DividendCalculatorWidget from "../../components/DividendCalculatorWidget";
import DcaBacktestWidget from "../../components/DcaBacktestWidget";
import CommunitySentimentGauge from "../../components/CommunitySentimentGauge";
import PendingOrdersPanel from "../../components/PendingOrdersPanel";
import NotificationPreferenceModal from "../../components/NotificationPreferenceModal";
import { useAuth, API_BASE } from "../../context/AuthContext";

const TradingViewChart = dynamic(() => import("../../components/TradingViewChart"), { ssr: false });

type SectionKey = "genel" | "pro" | "hesaplayici" | "topluluk";

type RangeKey = "1D" | "1W" | "1M" | "1Y" | "5Y";

const RANGES: { key: RangeKey; label: string; periodLabel: string }[] = [
  { key: "1D", label: "1G", periodLabel: "Bugün" },
  { key: "1W", label: "1H", periodLabel: "Son 1 Hafta" },
  { key: "1M", label: "1A", periodLabel: "Son 1 Ay" },
  { key: "1Y", label: "1Y", periodLabel: "Son 1 Yıl" },
  { key: "5Y", label: "5Y", periodLabel: "Son 5 Yıl" },
];

const SECTIONS: { key: SectionKey; label: string; icon: any }[] = [
  { key: "genel", label: "Genel Bakış", icon: LineChartIcon },
  { key: "pro", label: "Derin Bilanço Analizi", icon: Gauge },
  { key: "hesaplayici", label: "Hesaplayıcılar", icon: Calculator },
  { key: "topluluk", label: "Topluluk", icon: Users },
];

export default function StockDetailPage() {
  const params = useParams<{ symbol: string }>();
  const router = useRouter();
  const symbol = (params?.symbol || "").toString().toUpperCase();
  const { token, refreshTrigger, bumpRefresh } = useAuth();

  const [stockList, setStockList] = useState<any[]>([]);
  const [stockDetail, setStockDetail] = useState<any>(null);
  const [kapDisclosures, setKapDisclosures] = useState<any>(null);
  const [kapLoading, setKapLoading] = useState(false);
  const [news, setNews] = useState<any[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const [openNewsIdx, setOpenNewsIdx] = useState<number | null>(null);
  const [section, setSection] = useState<SectionKey>("genel");
  const [showNotificationModal, setShowNotificationModal] = useState(false);
  const [chartRange, setChartRange] = useState<RangeKey>("1D");
  const [chartData, setChartData] = useState<any[]>([]);
  const [chartLoading, setChartLoading] = useState(false);

  const [tradeQty, setTradeQty] = useState<number>(1);
  const [tradeLoading, setTradeLoading] = useState(false);
  const [tradeMessage, setTradeMessage] = useState<{ text: string; isError: boolean } | null>(null);

  const [comments, setComments] = useState<any[]>([]);
  const [commentText, setCommentText] = useState("");
  const [commentLoading, setCommentLoading] = useState(false);

  // Genel hisse özet bilgisi (fiyat değişim yüzdesi, katılım rozeti için)
  useEffect(() => {
    const fetchList = async () => {
      try {
        const res = await fetch(`${API_BASE}/stocks`);
        if (res.ok) setStockList(await res.json());
      } catch (err) {
        console.error("Hisse listesi alınamadı:", err);
      }
    };
    fetchList();
  }, [refreshTrigger]);

  const summary = stockList.find((s) => s.symbol === symbol);

  // Detay + KAP bildirimleri
  useEffect(() => {
    if (!symbol) return;

    const fetchDetail = async () => {
      try {
        const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
        const res = await fetch(`${API_BASE}/stocks/${symbol}`, { headers });
        if (res.ok) setStockDetail(await res.json());
      } catch (err) {
        console.error("Hisse detayı alınamadı:", err);
      }
    };

    const fetchKap = async () => {
      setKapLoading(true);
      setKapDisclosures(null);
      try {
        const res = await fetch(`${API_BASE}/stocks/${symbol}/kap-disclosures`);
        if (res.ok) setKapDisclosures(await res.json());
      } catch (err) {
        console.error("KAP bildirimleri alınamadı:", err);
      } finally {
        setKapLoading(false);
      }
    };

    const fetchNews = async () => {
      setNewsLoading(true);
      setNews([]);
      try {
        const res = await fetch(`${API_BASE}/stocks/${symbol}/news`);
        if (res.ok) setNews(await res.json());
      } catch (err) {
        console.error("Haberler alınamadı:", err);
      } finally {
        setNewsLoading(false);
      }
    };

    fetchDetail();
    fetchKap();
    fetchNews();
  }, [symbol, refreshTrigger, token]);

  // Grafik verisi (1G/1H/1A/1Y/5Y aralık seçici)
  useEffect(() => {
    if (!symbol) return;
    let cancelled = false;

    const fetchHistory = async () => {
      setChartLoading(true);
      try {
        const res = await fetch(`${API_BASE}/stocks/${symbol}/history?range=${chartRange}`);
        if (res.ok && !cancelled) setChartData(await res.json());
      } catch (err) {
        console.error("Fiyat geçmişi alınamadı:", err);
      } finally {
        if (!cancelled) setChartLoading(false);
      }
    };

    fetchHistory();
    return () => { cancelled = true; };
  }, [symbol, chartRange]);

  // Seçili aralığın kendi yüzdelik değişimi (dönem başı -> dönem sonu fiyat)
  const rangeChangePct = useMemo(() => {
    if (chartData.length < 2) return null;
    const first = chartData[0].price;
    const last = chartData[chartData.length - 1].price;
    if (!first) return null;
    return ((last - first) / first) * 100;
  }, [chartData]);

  // Yorumlar
  const fetchComments = async () => {
    try {
      const res = await fetch(`${API_BASE}/stocks/${symbol}/comments`);
      if (res.ok) setComments(await res.json());
    } catch (err) {
      console.error("Yorumlar alınamadı:", err);
    }
  };

  useEffect(() => {
    if (symbol) fetchComments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol]);

  const handleTrade = async (action: "AL" | "SAT") => {
    if (!token) {
      setTradeMessage({ text: "İşlem yapmak için giriş yapmalısınız.", isError: true });
      return;
    }
    setTradeLoading(true);
    setTradeMessage(null);
    try {
      const res = await fetch(`${API_BASE}/trade`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ symbol, action_type: action, quantity: tradeQty }),
      });
      const data = await res.json();
      if (res.ok) {
        setTradeMessage({ text: data.message, isError: false });
        bumpRefresh();
      } else {
        setTradeMessage({ text: data.detail || "İşlem başarısız.", isError: true });
      }
    } catch {
      setTradeMessage({ text: "İşlem sırasında hata oluştu.", isError: true });
    } finally {
      setTradeLoading(false);
    }
  };

  const handlePostComment = async () => {
    if (!token || commentText.trim().length < 2) return;
    setCommentLoading(true);
    try {
      const res = await fetch(`${API_BASE}/stocks/${symbol}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ comment_text: commentText }),
      });
      if (res.ok) {
        setCommentText("");
        await fetchComments();
        bumpRefresh();
      }
    } catch (err) {
      console.error("Yorum gönderilemedi:", err);
    } finally {
      setCommentLoading(false);
    }
  };

  if (!stockDetail) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-6">
        <button onClick={() => router.push("/piyasalar")} className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition mb-4">
          <ArrowLeft className="w-3.5 h-3.5" /> Piyasalara Dön
        </button>
        <div className="flex items-center justify-center py-16 text-gray-500 text-xs">
          <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#10B981]" />
          {symbol} yükleniyor...
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      <button onClick={() => router.push("/piyasalar")} className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition">
        <ArrowLeft className="w-3.5 h-3.5" /> Piyasalara Dön
      </button>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-white">{stockDetail.symbol}</h1>
            {stockDetail.change_pct !== null && stockDetail.change_pct !== undefined ? (
              <span className={`text-xs px-1.5 py-0.5 rounded tabular-nums font-semibold ${
                stockDetail.change_pct >= 0 ? "bg-[#10B981]/10 text-[#10B981]" : "bg-[#F43F5E]/10 text-[#F43F5E]"
              }`}>
                %{stockDetail.change_pct >= 0 ? "+" : ""}{stockDetail.change_pct}
              </span>
            ) : (
              <span
                title="Kurumsal işlem (bölünme/bedelsiz sermaye artışı) nedeniyle günlük değişim şu an güvenilir hesaplanamıyor."
                className="text-xs px-1.5 py-0.5 rounded tabular-nums font-semibold bg-gray-500/10 text-gray-500"
              >
                —
              </span>
            )}
          </div>
          <p className="text-xs text-gray-500 mt-0.5">{stockDetail.company_name}</p>
          {summary && (
            <div className="mt-2">
              <KatilimBadge
                isCompliant={summary.is_katilim_compliant}
                purificationRate={summary.purification_rate}
              />
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <p className="text-2xl font-bold text-white tabular-nums">{stockDetail.current_price} TL</p>
          {token && (
            <button
              onClick={() => setShowNotificationModal(true)}
              title="Bildirim Oluştur"
              className="bg-[#151921] border border-[#242B35] hover:border-[#F59E0B]/40 hover:text-[#F59E0B] text-gray-400 p-2 rounded-lg transition"
            >
              <Bell className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {(stockDetail.previous_close || stockDetail.open_price || stockDetail.day_high || stockDetail.day_low) && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs bg-[#151921] border border-[#242B35] rounded-xl p-3">
          <div>
            <p className="text-gray-500">Önceki Kapanış</p>
            <p className="font-semibold text-white tabular-nums">
              {stockDetail.previous_close !== null && stockDetail.previous_close !== undefined ? `${stockDetail.previous_close} TL` : "—"}
            </p>
          </div>
          <div>
            <p className="text-gray-500">Açılış</p>
            <p className="font-semibold text-white tabular-nums">
              {stockDetail.open_price !== null && stockDetail.open_price !== undefined ? `${stockDetail.open_price} TL` : "—"}
            </p>
          </div>
          <div>
            <p className="text-gray-500">Gün İçi Yüksek</p>
            <p className="font-semibold text-[#10B981] tabular-nums">
              {stockDetail.day_high !== null && stockDetail.day_high !== undefined ? `${stockDetail.day_high} TL` : "—"}
            </p>
          </div>
          <div>
            <p className="text-gray-500">Gün İçi Düşük</p>
            <p className="font-semibold text-[#F43F5E] tabular-nums">
              {stockDetail.day_low !== null && stockDetail.day_low !== undefined ? `${stockDetail.day_low} TL` : "—"}
            </p>
          </div>
        </div>
      )}

      {showNotificationModal && (
        <NotificationPreferenceModal
          symbol={symbol}
          currentPrice={stockDetail.current_price}
          onClose={() => setShowNotificationModal(false)}
        />
      )}

      <InsiderTrackerBadge symbol={symbol} />

      {/* Section Tabs */}
      <div className="bg-[#151921] p-1 rounded-xl flex flex-wrap gap-1 border border-[#242B35]">
        {SECTIONS.map((s) => {
          const Icon = s.icon;
          return (
            <button
              key={s.key}
              onClick={() => setSection(s.key)}
              className={`flex-1 min-w-[110px] flex items-center justify-center gap-1.5 py-2.5 rounded-lg text-xs font-semibold tracking-wide transition ${
                section === s.key ? "bg-[#10B981] text-[#0B0E14]" : "text-gray-400 hover:text-white"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              <span>{s.label}</span>
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 space-y-6">
          {section === "genel" && (
            <>
              <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-4">
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="text-xs">
                    <span className="text-gray-500">{RANGES.find((r) => r.key === chartRange)?.periodLabel}: </span>
                    {rangeChangePct !== null ? (
                      <span className={`font-bold tabular-nums ${rangeChangePct >= 0 ? "text-[#10B981]" : "text-[#F43F5E]"}`}>
                        {rangeChangePct >= 0 ? "+" : ""}{rangeChangePct.toFixed(2)}%
                      </span>
                    ) : (
                      <span className="text-gray-600">—</span>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                  {RANGES.map((r) => (
                    <button
                      key={r.key}
                      onClick={() => setChartRange(r.key)}
                      className={`px-2.5 py-1 rounded-md text-[11px] font-semibold tabular-nums transition ${
                        chartRange === r.key
                          ? "bg-[#10B981] text-[#0B0E14]"
                          : "text-gray-400 hover:text-white hover:bg-[#0B0E14]"
                      }`}
                    >
                      {r.label}
                    </button>
                  ))}
                  </div>
                </div>
                {chartLoading && chartData.length === 0 ? (
                  <div className="flex items-center justify-center h-[320px] text-xs text-gray-500">
                    <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#10B981]" />
                    Grafik yükleniyor...
                  </div>
                ) : chartData.length === 0 ? (
                  <div className="flex items-center justify-center h-[320px] text-xs text-gray-500">
                    Bu aralık için yeterli veri bulunamadı.
                  </div>
                ) : (
                  <TradingViewChart data={chartData} symbol={stockDetail.symbol} />
                )}
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs bg-[#151921] p-4 rounded-xl border border-[#242B35]">
                <div>
                  <p className="text-gray-500">RSI (14)</p>
                  <p className={`font-semibold tabular-nums ${
                    stockDetail.indicators.rsi < 30 ? "text-[#10B981]" : stockDetail.indicators.rsi > 70 ? "text-[#F43F5E]" : "text-white"
                  }`}>
                    {stockDetail.indicators.rsi}
                    {stockDetail.indicators.rsi < 30 && " (Aşırı Satım)"}
                    {stockDetail.indicators.rsi > 70 && " (Aşırı Alım)"}
                  </p>
                </div>
                <div>
                  <p className="text-gray-500">MACD / Sinyal</p>
                  <p className="font-semibold text-white tabular-nums">
                    {stockDetail.indicators.macd} / {stockDetail.indicators.macd_signal}
                  </p>
                </div>
                <div>
                  <p className="text-gray-500">SMA (5 / 20)</p>
                  <p className="font-semibold text-white tabular-nums">
                    {stockDetail.indicators.sma_short} / {stockDetail.indicators.sma_long}
                  </p>
                </div>
                <div>
                  <p className="text-gray-500">Bollinger Bantları</p>
                  <p className="font-semibold text-white tabular-nums">
                    {stockDetail.indicators.bb_low} - {stockDetail.indicators.bb_high}
                  </p>
                </div>
              </div>

              <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[10px] text-gray-400 uppercase font-bold tracking-widest flex items-center gap-1.5">
                    <Newspaper className="w-3.5 h-3.5" /> KAP Bildirimleri
                  </span>
                  {kapDisclosures?.kap_url && (
                    <a href={kapDisclosures.kap_url} target="_blank" rel="noopener noreferrer" className="text-[10px] text-[#10B981] hover:text-[#34d399] transition font-medium">
                      Tümünü Gör →
                    </a>
                  )}
                </div>

                {kapLoading ? (
                  <div className="flex items-center gap-2 text-[11px] text-gray-500 py-3">
                    <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#10B981]" />
                    KAP bildirimleri yükleniyor...
                  </div>
                ) : kapDisclosures?.disclosures?.length > 0 ? (
                  <div className="space-y-2 max-h-[260px] overflow-y-auto pr-0.5">
                    {kapDisclosures.disclosures.map((d: any, idx: number) => (
                      <div key={idx} className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-2.5 text-[11px]">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1">
                            {d.type && (
                              <span className="text-[9px] bg-[#F59E0B]/10 text-[#F59E0B] px-1.5 py-0.5 rounded font-bold uppercase tracking-wide mr-1">
                                {d.type}
                              </span>
                            )}
                            <p className="text-gray-300 font-medium mt-1 leading-snug">{d.title}</p>
                          </div>
                          <span className="text-[10px] text-gray-500 whitespace-nowrap shrink-0">{d.date}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[11px] text-gray-500 text-center py-4">Son dönemde kayda değer bir KAP bildirimi bulunamadı.</p>
                )}
              </div>

              <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[10px] text-gray-400 uppercase font-bold tracking-widest flex items-center gap-1.5">
                    <Newspaper className="w-3.5 h-3.5" /> Hisse Haberleri
                  </span>
                </div>

                {newsLoading ? (
                  <div className="flex items-center gap-2 text-[11px] text-gray-500 py-3">
                    <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#10B981]" />
                    Haberler yükleniyor...
                  </div>
                ) : news.length > 0 ? (
                  <div className="space-y-2 max-h-[420px] overflow-y-auto pr-0.5">
                    {news.map((n: any, idx: number) => {
                      const isOpen = openNewsIdx === idx;
                      return (
                        <div
                          key={idx}
                          className="bg-[#0B0E14] border border-[#242B35] rounded-lg text-[11px] overflow-hidden"
                        >
                          <button
                            onClick={() => setOpenNewsIdx(isOpen ? null : idx)}
                            className="w-full flex items-start justify-between gap-2 p-2.5 text-left"
                          >
                            <p className="text-gray-300 font-medium leading-snug flex-1">{n.title}</p>
                            <div className="flex items-center gap-1.5 shrink-0">
                              {n.published_at && (
                                <span className="text-[10px] text-gray-500 whitespace-nowrap">
                                  {new Date(n.published_at).toLocaleDateString("tr-TR")}
                                </span>
                              )}
                              <ChevronDown
                                className={`w-3.5 h-3.5 text-gray-500 transition-transform ${isOpen ? "rotate-180" : ""}`}
                              />
                            </div>
                          </button>

                          {isOpen && (
                            <div className="px-2.5 pb-2.5 space-y-2 border-t border-[#242B35] pt-2">
                              {n.source && (
                                <span className="text-[10px] text-gray-500">{n.source}</span>
                              )}
                              <p className="text-gray-400 leading-relaxed">
                                {n.summary || "Bu haber için özet bilgi bulunamadı."}
                              </p>
                              {n.url && (
                                <a
                                  href={n.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-1 text-[10px] font-semibold text-[#10B981] hover:text-[#34d399] transition"
                                >
                                  Devamını Oku <ExternalLink className="w-3 h-3" />
                                </a>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-[11px] text-gray-500 text-center py-4">Bu hisse için güncel bir haber bulunamadı.</p>
                )}
              </div>
            </>
          )}

          {section === "pro" && (
            <DerinAnalizTab symbol={symbol} currentPrice={stockDetail.current_price} />
          )}

          {section === "hesaplayici" && (
            <div className="space-y-4">
              <DividendCalculatorWidget symbol={symbol} />
              <DcaBacktestWidget symbol={symbol} />
            </div>
          )}

          {section === "topluluk" && (
            <div className="space-y-4">
              <CommunitySentimentGauge symbol={symbol} refreshTrigger={refreshTrigger} />

              <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-4 space-y-3">
                <h4 className="text-xs font-bold text-white uppercase tracking-wide">Yorumlar</h4>

                {token ? (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={commentText}
                      onChange={(e) => setCommentText(e.target.value)}
                      placeholder="Bu hisse hakkında ne düşünüyorsunuz?"
                      className="flex-1 bg-[#0B0E14] border border-[#242B35] focus:border-[#10B981] rounded-lg px-3 py-2 text-white text-xs outline-none transition"
                    />
                    <button
                      onClick={handlePostComment}
                      disabled={commentLoading || commentText.trim().length < 2}
                      className="bg-[#10B981] hover:bg-[#0da271] text-[#0B0E14] font-bold text-xs px-4 py-2 rounded-lg transition disabled:opacity-50"
                    >
                      Gönder
                    </button>
                  </div>
                ) : (
                  <p className="text-[11px] text-gray-500">Yorum yapmak için giriş yapmalısınız.</p>
                )}

                <div className="space-y-2 max-h-[300px] overflow-y-auto pr-0.5">
                  {comments.length === 0 ? (
                    <p className="text-[11px] text-gray-500 text-center py-4">Henüz yorum yok. İlk yorumu siz yapın.</p>
                  ) : (
                    comments.map((c) => (
                      <div key={c.id} className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-3 text-xs">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-white">@{c.username}</span>
                          <span className="text-[10px] text-gray-500">
                            {new Date(c.created_at).toLocaleDateString("tr-TR")}
                          </span>
                        </div>
                        <p className="text-gray-400 mt-1">{c.comment_text}</p>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Trade Panel */}
        <div className="space-y-6">
          <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-5 space-y-3">
            <h3 className="text-sm font-bold text-white uppercase tracking-wide">Sanal İşlem Paneli</h3>

            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-400 font-medium">Hisse Adeti:</span>
              <input
                type="number"
                min="1"
                step="1"
                className="bg-[#0B0E14] border border-[#242B35] rounded px-2.5 py-1 text-white w-20 text-center outline-none focus:border-[#10B981] font-semibold tabular-nums"
                value={tradeQty}
                onChange={(e) => setTradeQty(Math.max(1, parseInt(e.target.value) || 1))}
              />
            </div>

            <div className="flex items-center justify-between text-xs">
              <span className="text-gray-400 font-medium">Toplam Tutar:</span>
              <span className="font-bold text-white tabular-nums">
                {(tradeQty * stockDetail.current_price).toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} TL
              </span>
            </div>

            {tradeMessage && (
              <p className={`text-xs font-semibold text-center ${tradeMessage.isError ? "text-[#F43F5E]" : "text-[#10B981]"}`}>
                {tradeMessage.text}
              </p>
            )}

            <div className="grid grid-cols-2 gap-2.5">
              <button
                onClick={() => handleTrade("AL")}
                disabled={tradeLoading}
                className="bg-[#10B981] hover:bg-[#0da271] active:scale-95 text-[#0B0E14] font-bold py-2 rounded-lg text-xs transition duration-150 disabled:opacity-50"
              >
                SANAL AL
              </button>
              <button
                onClick={() => handleTrade("SAT")}
                disabled={tradeLoading}
                className="bg-[#F43F5E] hover:bg-[#e11d48] active:scale-95 text-white font-bold py-2 rounded-lg text-xs transition duration-150 disabled:opacity-50"
              >
                SANAL SAT
              </button>
            </div>
          </div>

          <PendingOrdersPanel symbol={symbol} currentPrice={stockDetail.current_price} />
        </div>
      </div>
    </div>
  );
}
