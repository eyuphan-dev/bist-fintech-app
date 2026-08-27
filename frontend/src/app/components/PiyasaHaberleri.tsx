"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Newspaper, RefreshCw, ExternalLink } from "lucide-react";
import { API_BASE } from "../context/AuthContext";

interface Haber {
  title: string;
  summary: string | null;
  source: string | null;
  url: string | null;
  published_at: string;
}

/**
 * Türkçe piyasa/ekonomi haber akışı.
 *
 * NEDEN HİSSEDEN AYRI BİR AKIŞ: çekilen haberlerin yalnızca küçük bir kısmı
 * belirli bir hisseyle eşleşiyor (ölçüldü: 330 haberin 10'u). Eşleşmeyenleri
 * atmak verinin çoğunu çöpe atmak olurdu — "bugün piyasada ne oldu" sorusunun
 * cevabı bu akışta. Hisseyle eşleşenler ayrıca hisse sayfasında da görünür.
 */
export default function PiyasaHaberleri({ limit = 20 }: { limit?: number }) {
  const [haberler, setHaberler] = useState<Haber[]>([]);
  const [kaynaklar, setKaynaklar] = useState<string[]>([]);
  const [secilenKaynak, setSecilenKaynak] = useState<string | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState(false);

  const getir = useCallback(async () => {
    setYukleniyor(true);
    setHata(false);
    try {
      const params = new URLSearchParams({ limit: String(limit) });
      if (secilenKaynak) params.set("source", secilenKaynak);
      const res = await fetch(`${API_BASE}/market/news?${params.toString()}`);
      if (!res.ok) throw new Error(String(res.status));
      setHaberler(await res.json());
    } catch {
      setHata(true);
    } finally {
      setYukleniyor(false);
    }
  }, [limit, secilenKaynak]);

  useEffect(() => {
    getir();
  }, [getir]);

  useEffect(() => {
    fetch(`${API_BASE}/market/news/sources`)
      .then((r) => (r.ok ? r.json() : []))
      .then(setKaynaklar)
      .catch(() => setKaynaklar([]));
  }, []);

  /** "3 saat önce" gibi göreli zaman; tam tarih title'da kalır. */
  const goreliZaman = (iso: string): string => {
    const t = new Date(iso).getTime();
    if (Number.isNaN(t)) return "";
    const dk = Math.floor((Date.now() - t) / 60000);
    if (dk < 1) return "az önce";
    if (dk < 60) return `${dk} dk önce`;
    const saat = Math.floor(dk / 60);
    if (saat < 24) return `${saat} saat önce`;
    const gun = Math.floor(saat / 24);
    return `${gun} gün önce`;
  };

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-bold text-white uppercase tracking-wide flex items-center gap-1.5">
          <Newspaper className="w-4 h-4 text-[#10B981]" /> Piyasa Haberleri
        </h2>
        <button
          onClick={getir}
          aria-label="Haberleri yenile"
          className="text-gray-500 hover:text-white transition p-2 -m-2"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${yukleniyor ? "animate-spin" : ""}`} />
        </button>
      </div>

      {kaynaklar.length > 0 && (
        <div className="flex gap-1.5 overflow-x-auto pb-1 -mx-1 px-1">
          <button
            onClick={() => setSecilenKaynak(null)}
            className={`shrink-0 px-2.5 py-1 rounded-lg text-[11px] font-bold border transition ${
              secilenKaynak === null
                ? "bg-[#10B981]/10 border-[#10B981]/30 text-[#10B981]"
                : "bg-[#151921] border-[#242B35] text-gray-400 hover:text-white"
            }`}
          >
            Tümü
          </button>
          {kaynaklar.map((k) => (
            <button
              key={k}
              onClick={() => setSecilenKaynak(k === secilenKaynak ? null : k)}
              className={`shrink-0 px-2.5 py-1 rounded-lg text-[11px] font-bold border transition ${
                secilenKaynak === k
                  ? "bg-[#10B981]/10 border-[#10B981]/30 text-[#10B981]"
                  : "bg-[#151921] border-[#242B35] text-gray-400 hover:text-white"
              }`}
            >
              {k}
            </button>
          ))}
        </div>
      )}

      {hata ? (
        <p className="text-xs text-gray-500 py-6 text-center">
          Haberler alınamadı. Yenilemeyi deneyin.
        </p>
      ) : yukleniyor && haberler.length === 0 ? (
        <div className="flex items-center justify-center py-8 text-gray-500 text-xs">
          <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#10B981]" />
          Haberler yükleniyor...
        </div>
      ) : haberler.length === 0 ? (
        <p className="text-xs text-gray-500 py-6 text-center">
          {secilenKaynak ? `${secilenKaynak} kaynağında haber yok.` : "Henüz haber yok."}
        </p>
      ) : (
        <ul className="divide-y divide-[#242B35] border border-[#242B35] rounded-xl overflow-hidden">
          {haberler.map((h, i) => (
            <li key={h.url ?? i} className="bg-[#151921]">
              <a
                href={h.url ?? "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="block px-4 py-3 hover:bg-[#1A1F29] transition min-h-[44px]"
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm text-white leading-snug flex-1">{h.title}</p>
                  <ExternalLink className="w-3 h-3 text-gray-600 shrink-0 mt-1" />
                </div>
                {h.summary && (
                  <p className="text-[11px] text-gray-500 mt-1 leading-relaxed line-clamp-2">
                    {h.summary}
                  </p>
                )}
                <div className="flex items-center gap-2 mt-1.5">
                  <span className="text-[10px] font-bold text-[#10B981]">{h.source}</span>
                  <span className="text-[10px] text-gray-600" title={h.published_at}>
                    {goreliZaman(h.published_at)}
                  </span>
                </div>
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
