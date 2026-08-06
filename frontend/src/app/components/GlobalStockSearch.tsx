"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, X, Loader2 } from "lucide-react";
import { API_BASE } from "../context/AuthContext";

interface SearchItem {
  symbol: string;
  company_name: string;
  sector: string | null;
  is_katilim_compliant: boolean;
}

/**
 * Navbar'daki global hisse arama kutusu. Sembol ya da şirket adıyla arar,
 * seçilen hissenin detay sayfasına gider.
 *
 * Klavye: ↑/↓ ile gezinme, Enter ile seçim, Esc ile kapatma. Her tuş vuruşunda
 * istek atmamak için 250 ms debounce uygulanır ve önceki istek iptal edilir
 * (yavaş bir yanıt, sonradan yazılan sorgunun sonucunu ezmesin diye).
 */
export default function GlobalStockSearch() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchItem[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Dışarı tıklanınca kapat
  useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  // Ctrl/Cmd + K ile arama kutusuna odaklan
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    const term = query.trim();
    if (!term) {
      abortRef.current?.abort();
      setResults([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    const timer = setTimeout(async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      try {
        const res = await fetch(`${API_BASE}/stocks/search?q=${encodeURIComponent(term)}`, {
          signal: controller.signal,
        });
        if (res.ok) {
          setResults(await res.json());
          setActiveIndex(0);
        }
      } catch (err) {
        // AbortError beklenen durumdur (kullanıcı yazmaya devam etti), sessizce geçilir
        if (!(err instanceof DOMException && err.name === "AbortError")) {
          console.error("Hisse arama başarısız:", err);
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [query]);

  const goToStock = useCallback(
    (symbol: string) => {
      setOpen(false);
      setQuery("");
      setResults([]);
      inputRef.current?.blur();
      router.push(`/hisse/${symbol}`);
    },
    [router]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      setOpen(false);
      inputRef.current?.blur();
      return;
    }
    if (!open || results.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => (i + 1) % results.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => (i - 1 + results.length) % results.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const picked = results[activeIndex];
      if (picked) goToStock(picked.symbol);
    }
  };

  const showDropdown = open && query.trim().length > 0;

  return (
    <div ref={containerRef} className="relative w-full">
      <div className="relative">
        <Search className="w-3.5 h-3.5 text-gray-500 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Hisse ara..."
          aria-label="Hisse ara"
          className="w-full bg-[#151921] border border-[#242B35] focus:border-[#10B981]/50 rounded-lg pl-8 pr-7 py-1.5 text-xs text-white placeholder-gray-500 outline-none transition"
        />
        {query && (
          <button
            onClick={() => {
              setQuery("");
              setResults([]);
              inputRef.current?.focus();
            }}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white transition"
            title="Temizle"
            type="button"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {showDropdown && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-[#151921] border border-[#242B35] rounded-xl shadow-xl py-1 z-50 max-h-80 overflow-y-auto">
          {loading && results.length === 0 ? (
            <div className="flex items-center justify-center gap-2 py-4 text-[11px] text-gray-500">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Aranıyor...
            </div>
          ) : results.length === 0 ? (
            <p className="text-center py-4 text-[11px] text-gray-500">Sonuç bulunamadı.</p>
          ) : (
            results.map((item, idx) => (
              <button
                key={item.symbol}
                onClick={() => goToStock(item.symbol)}
                onMouseEnter={() => setActiveIndex(idx)}
                type="button"
                className={`w-full text-left px-3 py-2 transition ${
                  idx === activeIndex ? "bg-[#0B0E14]" : "hover:bg-[#0B0E14]"
                }`}
              >
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-bold text-white">{item.symbol}</span>
                  {item.is_katilim_compliant && (
                    <span className="text-[9px] font-bold text-[#10B981] bg-[#10B981]/10 px-1.5 py-0.5 rounded">
                      Katılım
                    </span>
                  )}
                </div>
                <p className="text-[10px] text-gray-500 truncate mt-0.5">
                  {item.company_name}
                  {item.sector ? ` · ${item.sector}` : ""}
                </p>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
