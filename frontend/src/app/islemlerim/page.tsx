"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  History, TrendingUp, TrendingDown, ArrowRight, Wallet, Target, Clock, RefreshCw, Download,
} from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface TransactionItem {
  id: number;
  symbol: string;
  company_name: string;
  action_type: string;
  quantity: number;
  price: number;
  total_amount: number;
  realized_pnl: number | null;
  realized_pnl_pct: number | null;
  average_cost_at_trade: number | null;
  source: string;
  created_at: string;
}

interface TransactionHistory {
  total_realized_pnl: number;
  total_buy_amount: number;
  total_sell_amount: number;
  buy_count: number;
  sell_count: number;
  win_rate: number | null;
  items: TransactionItem[];
}

type Filter = "ALL" | "AL" | "SAT";

const fmtTL = (v: number) =>
  v.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** UTC olarak gelen ISO zaman damgasını yerel saate çevirip kısa biçimde yazar. */
function fmtDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("tr-TR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function TransactionsPage() {
  const { token, loading: authLoading } = useAuth();
  const [data, setData] = useState<TransactionHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<Filter>("ALL");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const load = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      const params = new URLSearchParams({ limit: "200" });
      if (startDate) params.set("start_date", startDate);
      if (endDate) params.set("end_date", endDate);
      const res = await fetch(`${API_BASE}/portfolio/transactions?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setData(await res.json());
    } catch (err) {
      console.error("İşlem geçmişi alınamadı:", err);
    } finally {
      setLoading(false);
    }
  }, [token, startDate, endDate]);

  useEffect(() => {
    load();
  }, [load]);

  // CSV ucu Authorization basligi gerektirdigi icin duz <a href> ile indirilemez;
  // token ile fetch edilip blob olarak kaydedilir.
  const [exporting, setExporting] = useState(false);
  const exportCsv = async () => {
    if (!token || exporting) return;
    setExporting(true);
    try {
      const params = new URLSearchParams();
      if (startDate) params.set("start_date", startDate);
      if (endDate) params.set("end_date", endDate);
      const res = await fetch(`${API_BASE}/portfolio/transactions/export?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(String(res.status));
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `islem-gecmisi-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("CSV indirilemedi:", err);
    } finally {
      setExporting(false);
    }
  };

  const visible = (data?.items ?? []).filter(
    (t) => filter === "ALL" || t.action_type === filter
  );

  // AuthContext token'ı localStorage'dan okurken token henüz null olur; bu aşamada
  // doğrudan !token'a bakarsak giriş yapmış kullanıcıya bir an "giriş yapın"
  // ekranı gösterilir. Bu yüzden önce loading kontrol edilir (bkz. app/page.tsx).
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
        <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-5 text-center">
          <p className="text-xs text-gray-400">İşlem geçmişinizi görmek için giriş yapmalısınız.</p>
        </div>
      </div>
    );
  }

  const pnl = data?.total_realized_pnl ?? 0;
  const pnlPositive = pnl >= 0;

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <History className="w-5 h-5 text-[#F59E0B]" /> İşlem Geçmişim
        </h1>
        <p className="text-xs text-gray-500 mt-1">
          Kendi yaptığınız alım-satımlar ve kapanan pozisyonlardan gerçekleşen kâr/zarar.
          AI Trader&apos;ın işlemleri buraya dahil değildir.
        </p>
      </div>

      {loading ? (
        <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-8 text-center">
          <p className="text-xs text-gray-500">Yükleniyor...</p>
        </div>
      ) : !data || data.items.length === 0 ? (
        <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-8 text-center">
          <History className="w-8 h-8 text-gray-600 mx-auto mb-2" />
          <p className="text-xs text-gray-400">Henüz kayıtlı bir işleminiz yok.</p>
          <p className="text-[10px] text-gray-600 mt-1.5">
            Bir alım veya satım yaptığınızda burada listelenecek.
          </p>
          <Link
            href="/piyasalar"
            className="inline-flex items-center gap-1 mt-3 text-[11px] font-semibold text-[#10B981] hover:underline"
          >
            Piyasalara git <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      ) : (
        <>
          {/* Özet kartları */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-4">
              <div className="flex items-center gap-1.5 text-[10px] text-gray-500 mb-1.5">
                {pnlPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                Gerçekleşen K/Z
              </div>
              <p
                className="text-lg font-bold tabular-nums"
                style={{ color: pnlPositive ? "#10B981" : "#F43F5E" }}
              >
                {pnlPositive ? "+" : ""}{fmtTL(pnl)} TL
              </p>
              <p className="text-[10px] text-gray-600 mt-0.5">Kapanan pozisyonlardan</p>
            </div>

            <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-4">
              <div className="flex items-center gap-1.5 text-[10px] text-gray-500 mb-1.5">
                <Target className="w-3 h-3" /> Başarı Oranı
              </div>
              <p className="text-lg font-bold text-white tabular-nums">
                {data.win_rate === null ? "—" : `%${data.win_rate.toFixed(0)}`}
              </p>
              <p className="text-[10px] text-gray-600 mt-0.5">
                {data.sell_count === 0 ? "Henüz satış yok" : `${data.sell_count} satıştan`}
              </p>
            </div>

            <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-4">
              <div className="flex items-center gap-1.5 text-[10px] text-gray-500 mb-1.5">
                <Wallet className="w-3 h-3" /> Toplam Alım
              </div>
              <p className="text-lg font-bold text-white tabular-nums">{fmtTL(data.total_buy_amount)} TL</p>
              <p className="text-[10px] text-gray-600 mt-0.5">{data.buy_count} işlem</p>
            </div>

            <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-4">
              <div className="flex items-center gap-1.5 text-[10px] text-gray-500 mb-1.5">
                <Wallet className="w-3 h-3" /> Toplam Satım
              </div>
              <p className="text-lg font-bold text-white tabular-nums">{fmtTL(data.total_sell_amount)} TL</p>
              <p className="text-[10px] text-gray-600 mt-0.5">{data.sell_count} işlem</p>
            </div>
          </div>

          {/* Tarih araligi */}
          <div className="flex items-center gap-2 flex-wrap text-[11px]">
            <span className="text-gray-500 font-semibold">Tarih:</span>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="bg-[#151921] border border-[#242B35] focus:border-[#10B981] rounded-lg px-2.5 py-2.5 md:py-1.5 text-white outline-none"
            />
            <span className="text-gray-600">—</span>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="bg-[#151921] border border-[#242B35] focus:border-[#10B981] rounded-lg px-2.5 py-2.5 md:py-1.5 text-white outline-none"
            />
            {(startDate || endDate) && (
              <button
                onClick={() => { setStartDate(""); setEndDate(""); }}
                type="button"
                className="text-gray-500 hover:text-[#F43F5E] font-semibold py-2 md:py-0 px-1"
              >
                Temizle
              </button>
            )}
          </div>

          {/* Filtre + disa aktarma */}
          <div className="flex items-center gap-2 flex-wrap">
            {([
              ["ALL", "Tümü"],
              ["AL", "Alımlar"],
              ["SAT", "Satımlar"],
            ] as [Filter, string][]).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className={`px-3.5 py-3 md:py-1.5 rounded-lg text-[11px] font-semibold transition ${
                  filter === key
                    ? "bg-[#10B981] text-[#0B0E14]"
                    : "bg-[#151921] border border-[#242B35] text-gray-400 hover:text-white"
                }`}
                type="button"
              >
                {label}
              </button>
            ))}

            <button
              onClick={exportCsv}
              disabled={exporting}
              type="button"
              title="İşlem geçmişini Excel'de açılabilir CSV olarak indir"
              className="ml-auto flex items-center gap-1.5 px-3.5 py-3 md:py-1.5 rounded-lg text-[11px] font-semibold bg-[#151921] border border-[#242B35] text-gray-400 hover:text-white hover:border-[#10B981]/40 transition disabled:opacity-50"
            >
              <Download className="w-3.5 h-3.5" />
              {exporting ? "Hazırlanıyor..." : "CSV indir"}
            </button>
          </div>

          {/* İşlem tablosu */}
          <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-5">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs min-w-[680px]">
                <thead>
                  <tr className="border-b border-[#242B35] text-gray-400">
                    <th className="pb-3 pr-3 font-semibold">Tarih</th>
                    <th className="pb-3 px-3 font-semibold">Hisse</th>
                    <th className="pb-3 px-3 font-semibold">İşlem</th>
                    <th className="pb-3 px-3 font-semibold text-right">Adet</th>
                    <th className="pb-3 px-3 font-semibold text-right">Fiyat</th>
                    <th className="pb-3 px-3 font-semibold text-right">Tutar</th>
                    <th className="pb-3 pl-3 font-semibold text-right">Gerçekleşen K/Z</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((t) => {
                    const isBuy = t.action_type === "AL";
                    const hasPnl = t.realized_pnl !== null;
                    const pnlPos = (t.realized_pnl ?? 0) >= 0;
                    return (
                      <tr key={t.id} className="border-b border-[#242B35]/50">
                        <td className="py-2.5 pr-3 text-gray-400 whitespace-nowrap">
                          {fmtDate(t.created_at)}
                          {t.source === "LIMIT_ORDER" && (
                            <span
                              className="ml-1.5 inline-flex items-center gap-0.5 text-[9px] text-gray-500"
                              title="Bekleyen emrin otomatik gerçekleşmesi"
                            >
                              <Clock className="w-2.5 h-2.5" /> emir
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 px-3">
                          <Link
                            href={`/hisse/${t.symbol}`}
                            className="font-bold text-white hover:text-[#10B981] transition"
                          >
                            {t.symbol}
                          </Link>
                          <p className="text-[10px] text-gray-600 truncate max-w-[140px]">
                            {t.company_name}
                          </p>
                        </td>
                        <td className="py-2.5 px-3">
                          <span
                            className="text-[10px] font-bold px-1.5 py-0.5 rounded"
                            style={{
                              color: isBuy ? "#10B981" : "#F43F5E",
                              backgroundColor: isBuy ? "rgba(16,185,129,0.1)" : "rgba(244,63,94,0.1)",
                            }}
                          >
                            {t.action_type}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-right tabular-nums text-gray-300">{t.quantity}</td>
                        <td className="py-2.5 px-3 text-right tabular-nums text-gray-300">
                          {fmtTL(t.price)}
                        </td>
                        <td className="py-2.5 px-3 text-right tabular-nums text-white font-semibold">
                          {fmtTL(t.total_amount)}
                        </td>
                        <td className="py-2.5 pl-3 text-right tabular-nums font-semibold">
                          {!hasPnl ? (
                            <span className="text-gray-600">—</span>
                          ) : (
                            <span style={{ color: pnlPos ? "#10B981" : "#F43F5E" }}>
                              {pnlPos ? "+" : ""}{fmtTL(t.realized_pnl as number)} TL
                              {t.realized_pnl_pct !== null && (
                                <span className="block text-[10px] font-normal opacity-80">
                                  {pnlPos ? "+" : ""}%{t.realized_pnl_pct.toFixed(2)}
                                </span>
                              )}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {visible.length === 0 && (
              <p className="text-xs text-gray-500 text-center py-6">
                Bu filtreye uyan işlem yok.
              </p>
            )}

            <p className="text-[10px] text-gray-600 mt-4 border-t border-[#242B35] pt-3">
              Gerçekleşen K/Z yalnızca satış işlemlerinde hesaplanır ve satış anındaki ortalama
              maliyet esas alınır. Portföy sayfasındaki kâr/zarar ise henüz satılmamış (açık)
              pozisyonların anlık durumunu gösterir — ikisi farklı şeylerdir.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
