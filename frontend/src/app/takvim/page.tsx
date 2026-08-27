"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { RefreshCw, CalendarDays, Newspaper, ExternalLink, Landmark, Search, X } from "lucide-react";
import { API_BASE } from "../context/AuthContext";
import TemettuTakvimi from "../components/TemettuTakvimi";

interface EarningsItem {
  symbol: string;
  company_name: string;
  next_earnings_date: string; // YYYY-MM-DD
}

interface KapNewsItem {
  id: number;
  symbol: string;
  title: string;
  summary: string | null;
  kap_url: string | null;
  publish_date: string;
}

function daysUntil(dateStr: string): number {
  const target = new Date(dateStr + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - today.getTime()) / 86400000);
}

export default function TakvimPage() {
  const [earnings, setEarnings] = useState<EarningsItem[] | null>(null);
  const [news, setNews] = useState<KapNewsItem[] | null>(null);
  const [majorHolderNews, setMajorHolderNews] = useState<KapNewsItem[] | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<KapNewsItem[] | null>(null);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [earningsRes, newsRes, majorHolderRes] = await Promise.all([
          fetch(`${API_BASE}/earnings-calendar`),
          fetch(`${API_BASE}/kap/news`),
          fetch(`${API_BASE}/kap/major-holder-news`),
        ]);
        if (earningsRes.ok) setEarnings(await earningsRes.json());
        if (newsRes.ok) setNews(await newsRes.json());
        if (majorHolderRes.ok) setMajorHolderNews(await majorHolderRes.json());
      } catch (err) {
        console.error("Takvim verisi alınamadı:", err);
        setEarnings([]);
        setNews([]);
        setMajorHolderNews([]);
      }
    };
    fetchAll();
  }, []);

  // Sorgu değişince 400ms bekleyip arar — her tuş vuruşunda istek atmamak için.
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }
    let cancelled = false;
    setSearching(true);
    const zamanlayici = setTimeout(async () => {
      try {
        const res = await fetch(`${API_BASE}/kap/search?q=${encodeURIComponent(searchQuery)}`);
        if (res.ok && !cancelled) setSearchResults(await res.json());
      } catch (err) {
        console.error("KAP arama başarısız:", err);
        if (!cancelled) setSearchResults([]);
      } finally {
        if (!cancelled) setSearching(false);
      }
    }, 400);
    return () => { cancelled = true; clearTimeout(zamanlayici); };
  }, [searchQuery]);

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-8">
      <div>
        <h1 className="text-xl font-bold text-white">Bilanço, Temettü & KAP Takvimi</h1>
        <p className="text-xs text-gray-500 mt-1">
          Yaklaşan bilanço açıklamaları, nakit temettü ödemeleri ve şirketlerin son KAP bildirimleri.
        </p>
      </div>

      {/* Temettü takvimi en üstte: katılım finansı odaklı bir uygulamada
          temettü merkezî bir kavram ve kullanıcı bugüne kadar yalnızca
          GEÇMİŞ ödemeleri görebiliyordu. */}
      <TemettuTakvimi />

      <section className="space-y-3">
        <h2 className="text-sm font-bold text-white flex items-center gap-1.5">
          <CalendarDays className="w-4 h-4 text-[#F59E0B]" /> Yaklaşan Bilanço Tarihleri
        </h2>

        {earnings === null ? (
          <div className="flex items-center justify-center py-10 text-gray-500 text-xs">
            <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#10B981]" />
            Yükleniyor...
          </div>
        ) : earnings.length === 0 ? (
          <p className="text-xs text-gray-500 py-6 text-center bg-[#151921] border border-[#242B35] rounded-xl">
            Yaklaşan bilanço tarihi bilinen hisse bulunamadı. Veriler her gün otomatik tazelenir.
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {earnings.map((item) => {
              const d = daysUntil(item.next_earnings_date);
              return (
                <Link
                  key={item.symbol}
                  href={`/hisse/${item.symbol}`}
                  className="bg-[#151921] border border-[#242B35] hover:border-[#F59E0B]/40 rounded-xl p-3.5 flex items-center justify-between transition"
                >
                  <div className="min-w-0">
                    <p className="font-bold text-white">{item.symbol}</p>
                    <p className="text-[11px] text-gray-500 truncate max-w-[160px]">{item.company_name}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-xs font-semibold text-[#F59E0B] tabular-nums">
                      {new Date(item.next_earnings_date + "T00:00:00").toLocaleDateString("tr-TR", {
                        day: "2-digit",
                        month: "short",
                      })}
                    </p>
                    <p className="text-[10px] text-gray-500">
                      {d === 0 ? "Bugün" : d === 1 ? "Yarın" : `${d} gün sonra`}
                    </p>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="text-sm font-bold text-white flex items-center gap-1.5">
            <Landmark className="w-4 h-4 text-[#F43F5E]" /> Büyük Yatırımcı Hareketleri
          </h2>
          <p className="text-[11px] text-gray-500 mt-1">
            Başlığında pay sahipliği/oy hakları değişikliğine işaret eden KAP bildirimleri. Kimin ne kadar
            aldığı/sattığı bilgisi KAP'ın bildirim detay sayfasında yer alır — bireysel yatırımcı bazında
            (kişi/hesap adı) hiçbir kamu kaynağında paylaşılmaz, yalnızca %5/%10 gibi eşiği aşan pay sahipleri
            (genelde kurumlar) KAP'a bildirim yapmakla yükümlüdür.
          </p>
        </div>

        {majorHolderNews === null ? (
          <div className="flex items-center justify-center py-10 text-gray-500 text-xs">
            <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#10B981]" />
            Yükleniyor...
          </div>
        ) : majorHolderNews.length === 0 ? (
          <p className="text-xs text-gray-500 py-6 text-center bg-[#151921] border border-[#242B35] rounded-xl">
            Son dönemde pay sahipliği/oy hakları değişikliğine dair bir KAP bildirimi bulunamadı.
          </p>
        ) : (
          <div className="space-y-2">
            {majorHolderNews.map((item) => (
              <div key={item.id} className="bg-[#151921] border border-[#242B35] rounded-xl p-3.5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Link href={`/hisse/${item.symbol}`} className="text-xs font-bold text-[#F43F5E]">
                        {item.symbol}
                      </Link>
                      <span className="text-[10px] text-gray-500 tabular-nums">
                        {new Date(item.publish_date).toLocaleDateString("tr-TR")}
                      </span>
                    </div>
                    <p className="text-sm text-white mt-1">{item.title}</p>
                  </div>
                  {item.kap_url && (
                    <a
                      href={item.kap_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      // İkon 16x16 kalır, dokunma alanı 44x44 (-m ile görsel konum korunur).
                      className="text-gray-500 hover:text-white shrink-0 -m-3 p-3 min-w-[44px] min-h-[44px] flex items-center justify-center"
                      title="KAP'ta görüntüle"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-bold text-white flex items-center gap-1.5">
          <Search className="w-4 h-4 text-[#F59E0B]" /> KAP Bildirimlerinde Ara
        </h2>
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchInput}
            onChange={(e) => {
              setSearchInput(e.target.value);
              setSearchQuery(e.target.value);
            }}
            placeholder="Örn. temettü, sermaye artırımı, birleşme..."
            className="w-full bg-[#151921] border border-[#242B35] focus:border-[#F59E0B] rounded-xl pl-9 pr-9 py-2.5 text-sm text-white outline-none transition"
          />
          {searchInput && (
            <button
              onClick={() => { setSearchInput(""); setSearchQuery(""); }}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {searchQuery.trim() && (
          <div className="space-y-2">
            {searching ? (
              <div className="flex items-center justify-center py-6 text-gray-500 text-xs">
                <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#F59E0B]" />
                Aranıyor...
              </div>
            ) : searchResults === null || searchResults.length === 0 ? (
              <p className="text-xs text-gray-500 py-6 text-center bg-[#151921] border border-[#242B35] rounded-xl">
                "{searchQuery}" ile eşleşen bir KAP bildirimi bulunamadı.
              </p>
            ) : (
              searchResults.map((item) => (
                <div key={item.id} className="bg-[#151921] border border-[#F59E0B]/30 rounded-xl p-3.5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <Link href={`/hisse/${item.symbol}`} className="text-xs font-bold text-[#10B981]">
                          {item.symbol}
                        </Link>
                        <span className="text-[10px] text-gray-500 tabular-nums">
                          {new Date(item.publish_date).toLocaleDateString("tr-TR")}
                        </span>
                      </div>
                      <p className="text-sm text-white mt-1">{item.title}</p>
                      {item.summary && <p className="text-[11px] text-gray-500 mt-1 line-clamp-2">{item.summary}</p>}
                    </div>
                    {item.kap_url && (
                      <a href={item.kap_url} target="_blank" rel="noopener noreferrer"
                         className="text-gray-500 hover:text-white shrink-0" title="KAP'ta görüntüle">
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-bold text-white flex items-center gap-1.5">
          <Newspaper className="w-4 h-4 text-[#10B981]" /> Son KAP Bildirimleri
        </h2>

        {news === null ? (
          <div className="flex items-center justify-center py-10 text-gray-500 text-xs">
            <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#10B981]" />
            Yükleniyor...
          </div>
        ) : news.length === 0 ? (
          <p className="text-xs text-gray-500 py-6 text-center bg-[#151921] border border-[#242B35] rounded-xl">
            Henüz KAP bildirimi bulunamadı.
          </p>
        ) : (
          <div className="space-y-2">
            {news.map((item) => (
              <div key={item.id} className="bg-[#151921] border border-[#242B35] rounded-xl p-3.5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Link href={`/hisse/${item.symbol}`} className="text-xs font-bold text-[#10B981]">
                        {item.symbol}
                      </Link>
                      <span className="text-[10px] text-gray-500 tabular-nums">
                        {new Date(item.publish_date).toLocaleDateString("tr-TR")}
                      </span>
                    </div>
                    <p className="text-sm text-white mt-1">{item.title}</p>
                    {item.summary && <p className="text-[11px] text-gray-500 mt-1 line-clamp-2">{item.summary}</p>}
                  </div>
                  {item.kap_url && (
                    <a
                      href={item.kap_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-gray-500 hover:text-white shrink-0"
                      title="KAP'ta görüntüle"
                    >
                      <ExternalLink className="w-4 h-4" />
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
