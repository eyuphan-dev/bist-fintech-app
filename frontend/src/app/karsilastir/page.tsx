"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { GitCompareArrows, X, Plus, ArrowRight } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";

interface CompareItem {
  symbol: string;
  company_name: string;
  sector: string | null;
  current_price: number;
  price_change_pct: number | null;
  is_katilim_compliant: boolean;
  pe_ratio: number | null;
  pb_ratio: number | null;
  roe: number | null;
  piotroski_score: number | null;
  altman_z_score: number | null;
  debt_to_equity: number | null;
  net_margin: number | null;
  dividend_yield: number | null;
  target_upside_pct: number | null;
}

interface StockOption {
  symbol: string;
  company_name: string;
}

const MAX_COMPARE = 4;

/**
 * Karşılaştırma satırları. `better` alanı, iki değerden hangisinin daha
 * olumlu sayılacağını belirler ("low" = düşük olan iyi, örn. F/K).
 * `null` ise nesnel bir "iyi/kötü" yönü yoktur, vurgulama yapılmaz.
 */
const METRICS: {
  key: keyof CompareItem;
  label: string;
  suffix?: string;
  better: "high" | "low" | null;
  hint: string;
}[] = [
  { key: "current_price", label: "Fiyat", suffix: " TL", better: null, hint: "Güncel işlem fiyatı" },
  { key: "price_change_pct", label: "Günlük Değişim", suffix: "%", better: "high", hint: "Bugünkü yüzde değişim" },
  { key: "pe_ratio", label: "F/K", better: "low", hint: "Fiyat / Kazanç — düşüğü genelde daha ucuz sayılır" },
  { key: "pb_ratio", label: "PD/DD", better: "low", hint: "Piyasa Değeri / Defter Değeri" },
  { key: "roe", label: "ROE", suffix: "%", better: "high", hint: "Özkaynak kârlılığı" },
  { key: "net_margin", label: "Net Kâr Marjı", suffix: "%", better: "high", hint: "Net kâr / satışlar" },
  { key: "piotroski_score", label: "Piotroski", suffix: "/9", better: "high", hint: "Bilanço sağlık skoru (0-9)" },
  { key: "altman_z_score", label: "Altman Z", better: "high", hint: "İflas riski skoru — yüksek olan daha güvenli" },
  { key: "debt_to_equity", label: "Borç/Özkaynak", better: "low", hint: "Finansal kaldıraç" },
  { key: "dividend_yield", label: "Temettü Verimi", suffix: "%", better: "high", hint: "Yıllık temettü / fiyat" },
  { key: "target_upside_pct", label: "Analist Potansiyeli", suffix: "%", better: "high", hint: "Aracı kurum hedef fiyatına göre yükseliş potansiyeli" },
];

export default function ComparePage() {
  const { token } = useAuth();
  const [allStocks, setAllStocks] = useState<StockOption[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [items, setItems] = useState<CompareItem[]>([]);
  const [picker, setPicker] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/stocks`);
        if (res.ok) {
          const data = await res.json();
          setAllStocks(
            data.map((s: StockOption) => ({ symbol: s.symbol, company_name: s.company_name }))
          );
        }
      } catch (err) {
        console.error("Hisse listesi alınamadı:", err);
      }
    })();
  }, []);

  const loadComparison = useCallback(async (symbols: string[]) => {
    if (symbols.length === 0) {
      setItems([]);
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/stocks/compare?symbols=${symbols.join(",")}`);
      if (res.ok) setItems(await res.json());
    } catch (err) {
      console.error("Karşılaştırma verisi alınamadı:", err);
    }
  }, []);

  useEffect(() => {
    loadComparison(selected);
  }, [selected, loadComparison]);

  const addStock = (symbol: string) => {
    if (!symbol || selected.includes(symbol) || selected.length >= MAX_COMPARE) return;
    setSelected((prev) => [...prev, symbol]);
    setPicker("");
  };

  const removeStock = (symbol: string) => setSelected((prev) => prev.filter((s) => s !== symbol));

  /** Bir metrik için en iyi değere sahip sembolleri bulur (beraberlik olabilir). */
  const bestSymbolsFor = (metric: (typeof METRICS)[number]): Set<string> => {
    if (!metric.better || items.length < 2) return new Set();
    const valid = items.filter((it) => typeof it[metric.key] === "number");
    if (valid.length < 2) return new Set();

    const values = valid.map((it) => it[metric.key] as number);
    const target = metric.better === "high" ? Math.max(...values) : Math.min(...values);
    return new Set(
      valid.filter((it) => (it[metric.key] as number) === target).map((it) => it.symbol)
    );
  };

  const available = allStocks.filter((s) => !selected.includes(s.symbol));

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <GitCompareArrows className="w-5 h-5 text-[#F59E0B]" /> Hisse Karşılaştırma
        </h1>
        <p className="text-xs text-gray-500 mt-1">
          En fazla {MAX_COMPARE} hisseyi yan yana koyup değerleme oranlarını ve bilanço
          skorlarını karşılaştırın. Her satırda en olumlu değer vurgulanır.
        </p>
      </div>

      {!token ? (
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5 text-center">
          <p className="text-xs text-gray-400">Karşılaştırma yapmak için giriş yapmalısınız.</p>
        </div>
      ) : (
        <>
          {/* Seçim alanı */}
          <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5 space-y-3">
            <div className="flex flex-wrap gap-2">
              {selected.map((sym) => (
                <span
                  key={sym}
                  className="flex items-center gap-1.5 bg-[#0B0E14] border border-[#242B35] rounded-lg px-2.5 py-1.5 text-xs font-bold text-white"
                >
                  {sym}
                  <button
                    onClick={() => removeStock(sym)}
                    className="text-gray-500 hover:text-[#F43F5E] transition"
                    title={`${sym} çıkar`}
                    type="button"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </span>
              ))}
              {selected.length === 0 && (
                <span className="text-xs text-gray-500">Henüz hisse seçilmedi.</span>
              )}
            </div>

            {selected.length < MAX_COMPARE && (
              <div className="flex items-center gap-2">
                <Plus className="w-3.5 h-3.5 text-gray-500 shrink-0" />
                <select
                  value={picker}
                  onChange={(e) => addStock(e.target.value)}
                  // min-w-0 şart: seçenek metinleri uzun ("THYAO — Türk Hava Yolları A.O.")
                  // ve flex öğesinin varsayılan min-width:auto değeri select'in bu içeriğin
                  // altına inmesini engelliyordu. Telefonda sayfa 568px'e genişleyip
                  // TÜM sayfayı yatay kaydırılabilir hale getiriyordu.
                  className="flex-1 min-w-0 bg-[#0B0E14] border border-[#242B35] rounded-lg px-3 py-2.5 text-xs text-white outline-none focus:border-[#F59E0B]/50 transition"
                >
                  <option value="">Karşılaştırmaya hisse ekle...</option>
                  {available.map((s) => (
                    <option key={s.symbol} value={s.symbol}>
                      {s.symbol} — {s.company_name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Karşılaştırma tablosu */}
          {items.length === 0 ? (
            <div className="bg-[#151921] border border-[#242B35] rounded-xl p-8 text-center">
              <GitCompareArrows className="w-8 h-8 text-gray-600 mx-auto mb-2" />
              <p className="text-xs text-gray-400">
                Karşılaştırmak için yukarıdan en az bir hisse seçin.
              </p>
            </div>
          ) : (
            <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs min-w-[560px]">
                  <thead>
                    <tr className="border-b border-[#242B35]">
                      <th className="pb-3 pr-3 text-gray-400 font-semibold">Metrik</th>
                      {items.map((it) => (
                        <th key={it.symbol} className="pb-3 px-3 text-right">
                          <Link
                            href={`/hisse/${it.symbol}`}
                            className="font-bold text-white hover:text-[#4A87C7] transition inline-flex items-center gap-1"
                          >
                            {it.symbol} <ArrowRight className="w-3 h-3" />
                          </Link>
                          <p className="text-[10px] text-gray-500 font-normal truncate max-w-[120px] ml-auto">
                            {it.sector || "—"}
                          </p>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {METRICS.map((metric) => {
                      const best = bestSymbolsFor(metric);
                      return (
                        <tr key={String(metric.key)} className="border-b border-[#242B35]/50">
                          <td className="py-2.5 pr-3">
                            <span className="text-gray-300 font-medium">{metric.label}</span>
                            <p className="text-[10px] text-gray-600">{metric.hint}</p>
                          </td>
                          {items.map((it) => {
                            const raw = it[metric.key];
                            const isNum = typeof raw === "number";
                            const isBest = best.has(it.symbol);
                            return (
                              <td
                                key={it.symbol}
                                className={`py-2.5 px-3 text-right tabular-nums font-semibold ${
                                  isBest ? "text-[#4A87C7]" : "text-gray-300"
                                }`}
                              >
                                {isNum ? `${raw}${metric.suffix ?? ""}` : "—"}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
                    <tr>
                      <td className="py-2.5 pr-3 text-gray-300 font-medium">Katılım Uyumu</td>
                      {items.map((it) => (
                        <td key={it.symbol} className="py-2.5 px-3 text-right">
                          {it.is_katilim_compliant ? (
                            <span className="text-[10px] font-bold text-[#4A87C7] bg-[#4A87C7]/10 px-1.5 py-0.5 rounded">
                              Uygun
                            </span>
                          ) : (
                            <span className="text-[10px] text-gray-500">Uygun değil</span>
                          )}
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>

              <p className="text-[10px] text-gray-600 mt-4 border-t border-[#242B35] pt-3">
                Yeşil vurgu, o satırdaki en olumlu değeri gösterir (F/K, PD/DD ve Borç/Özkaynak için
                düşük olan; diğerlerinde yüksek olan). Analiz verisi olmayan hisselerde &quot;—&quot;
                görünür. Bu bir yatırım tavsiyesi değildir.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
