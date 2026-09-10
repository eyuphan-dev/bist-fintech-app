"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Award, ChevronLeft, ChevronRight } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";
import { marketTextClass } from "../../lib/marketColor";

interface LeaderboardItem {
  username: string;
  total_portfolio_value: number;
  profit_loss_pct: number;
  is_bot: boolean;
}

interface CategoryLeaderboardItem {
  username: string;
  deger: number;
  detay: string | null;
}

type Kategori = "getiri" | "istikrar" | "aktiflik" | "kahin";
type KatilimciFiltre = "hepsi" | "kullanicilar" | "botlar";

const SAYFA_BOYUTU = 5;

const KATEGORI_SEKMELERI: { key: Kategori; label: string }[] = [
  { key: "getiri", label: "Getiri" },
  { key: "istikrar", label: "İstikrar" },
  { key: "aktiflik", label: "Aktiflik" },
  { key: "kahin", label: "Kâhin" },
];

const KATEGORI_BIRIM: Record<Kategori, (v: number) => string> = {
  getiri: (v) => `${v > 0 ? "+" : ""}${v.toFixed(2)}%`,
  istikrar: (v) => v.toFixed(2),
  aktiflik: (v) => `${Math.round(v)}`,
  kahin: (v) => `%${v.toFixed(0)}`,
};

/**
 * Ana sayfadaki liderlik tablosu kartı. "Getiri" mevcut (period destekli)
 * uçtan gelir; İstikrar/Aktiflik/Kâhin ise yeni /api/leaderboard/kategori
 * ucundan -- bu üçü yalnızca gerçek kullanıcıları kapsar (kişisel botlar
 * hariç), Kâhin ayrıca dönem sekmelerinden bağımsızdır (bkz. backend
 * leaderboard_categories.py).
 */
export default function LeaderboardWidget() {
  const { user } = useAuth();
  const [kategori, setKategori] = useState<Kategori>("getiri");
  const [period, setPeriod] = useState<"all" | "weekly" | "monthly">("all");
  const [getiriListesi, setGetiriListesi] = useState<LeaderboardItem[]>([]);
  const [kategoriListesi, setKategoriListesi] = useState<CategoryLeaderboardItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [katilimciFiltre, setKatilimciFiltre] = useState<KatilimciFiltre>("hepsi");
  const [sayfa, setSayfa] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        if (kategori === "getiri") {
          const res = await fetch(`${API_BASE}/leaderboard?period=${period}`);
          if (res.ok && !cancelled) setGetiriListesi(await res.json());
        } else {
          const donemParam = kategori === "kahin" ? "" : `&period=${period}`;
          const res = await fetch(`${API_BASE}/leaderboard/kategori?category=${kategori}${donemParam}`);
          if (res.ok && !cancelled) setKategoriListesi(await res.json());
        }
      } catch (err) {
        console.error("Liderlik tablosu alınamadı:", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [kategori, period]);

  // Kategori/donem/filtre degisince sayfa 0'a donsun -- aksi halde ornegin
  // 3. sayfadayken sekme degistirince bos bir sayfada kalinabilir.
  useEffect(() => {
    setSayfa(0);
  }, [kategori, period, katilimciFiltre]);

  const filtrelenmisGetiri = useMemo(() => {
    if (katilimciFiltre === "kullanicilar") return getiriListesi.filter((p) => !p.is_bot);
    if (katilimciFiltre === "botlar") return getiriListesi.filter((p) => p.is_bot);
    return getiriListesi;
  }, [getiriListesi, katilimciFiltre]);

  const aktifListeUzunlugu = kategori === "getiri" ? filtrelenmisGetiri.length : kategoriListesi.length;
  const toplamSayfa = Math.max(1, Math.ceil(aktifListeUzunlugu / SAYFA_BOYUTU));
  const gecerliSayfa = Math.min(sayfa, toplamSayfa - 1);
  const sayfalananGetiri = filtrelenmisGetiri.slice(gecerliSayfa * SAYFA_BOYUTU, (gecerliSayfa + 1) * SAYFA_BOYUTU);
  const sayfalananKategori = kategoriListesi.slice(gecerliSayfa * SAYFA_BOYUTU, (gecerliSayfa + 1) * SAYFA_BOYUTU);
  // Sayfa numarasi (0-indeksli) siralamayi bozmasin diye ilk elemanin GERCEK
  // (filtrelenmemis/sayfalanmamis listedeki) sirasi kullanilir.
  const ilkSiraOfset = gecerliSayfa * SAYFA_BOYUTU;

  return (
    <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5">
      <div className="flex items-center gap-1.5 mb-3">
        <Award className="w-5 h-5 text-[#F59E0B]" />
        <h3 className="text-sm font-bold text-white tracking-wide uppercase">Liderlik Tablosu</h3>
      </div>

      <div className="flex items-center gap-1 mb-2 overflow-x-auto">
        {KATEGORI_SEKMELERI.map((opt) => (
          <button
            key={opt.key}
            onClick={() => setKategori(opt.key)}
            className={`shrink-0 px-2.5 min-h-[32px] text-[11px] font-bold rounded-md transition ${
              kategori === opt.key ? "bg-[#10B981] text-[#0B0E14]" : "bg-[#0B0E14] text-gray-500 border border-[#242B35] hover:text-gray-300"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {kategori !== "kahin" && (
        <div className="flex items-center gap-1 mb-4 bg-[#0B0E14] border border-[#242B35] rounded-lg p-1">
          {([
            { key: "all", label: "Tümü" },
            { key: "weekly", label: "Bu Hafta" },
            { key: "monthly", label: "Bu Ay" },
          ] as const).map((opt) => (
            <button
              key={opt.key}
              onClick={() => setPeriod(opt.key)}
              className={`flex-1 min-h-[36px] text-[11px] font-semibold rounded-md transition ${
                period === opt.key ? "bg-[#242B35] text-white" : "text-gray-500 hover:text-gray-300"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
      {kategori === "kahin" && <div className="mb-2" />}

      {kategori === "getiri" && (
        <div className="flex items-center gap-1 mb-4 bg-[#0B0E14] border border-[#242B35] rounded-lg p-1">
          {([
            { key: "hepsi", label: "Hepsi" },
            { key: "kullanicilar", label: "Kullanıcılar" },
            { key: "botlar", label: "Botlar" },
          ] as const).map((opt) => (
            <button
              key={opt.key}
              onClick={() => setKatilimciFiltre(opt.key)}
              className={`flex-1 min-h-[32px] text-[11px] font-semibold rounded-md transition ${
                katilimciFiltre === opt.key ? "bg-[#242B35] text-white" : "text-gray-500 hover:text-gray-300"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <p className="text-center py-6 text-gray-500 text-xs">Yükleniyor...</p>
      ) : kategori === "getiri" ? (
        <div className="space-y-3.5">
          {sayfalananGetiri.map((player, localIdx) => {
            const idx = ilkSiraOfset + localIdx;
            return (
            <div
              key={player.username}
              className={`flex items-center justify-between text-xs p-2.5 rounded-lg border ${
                user && (player.username === user.username || player.username === `${user.username} — Kişisel Bot`)
                  ? "bg-[#10B981]/10 border-[#10B981]/30 font-semibold"
                  : "bg-[#0B0E14] border-[#242B35]"
              }`}
            >
              <div className="flex items-center gap-2">
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                  idx === 0 ? "bg-[#F59E0B] text-[#0B0E14]" : idx === 1 ? "bg-slate-300 text-[#0B0E14]" : "bg-[#242B35] text-gray-400"
                }`}>
                  {idx + 1}
                </span>
                <div>
                  <span className="text-white flex items-center">
                    {player.is_bot ? (
                      player.username
                    ) : (
                      <Link href={`/profil/${player.username}`} className="hover:text-[#10B981] transition">
                        @{player.username}
                      </Link>
                    )}
                    {player.is_bot && (
                      <span className="ml-1 bg-[#F59E0B]/10 text-[#F59E0B] text-[8px] uppercase tracking-wider px-1 rounded font-bold">
                        BOT
                      </span>
                    )}
                  </span>
                  <span className="text-[10px] text-gray-500 tabular-nums">
                    {player.total_portfolio_value.toLocaleString("tr-TR")} TL
                  </span>
                </div>
              </div>
              <span className={`font-semibold tabular-nums ${marketTextClass(player.profit_loss_pct)}`}>
                {player.profit_loss_pct > 0 ? "+" : ""}{player.profit_loss_pct.toFixed(2)}%
              </span>
            </div>
            );
          })}
          {filtrelenmisGetiri.length === 0 && (
            <p className="text-center py-6 text-gray-500 text-xs">
              {katilimciFiltre === "hepsi" ? "Henüz veri yok." : "Bu filtrede henüz veri yok."}
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-3.5">
          {sayfalananKategori.map((player, localIdx) => {
            const idx = ilkSiraOfset + localIdx;
            return (
            <div
              key={player.username}
              className={`flex items-center justify-between text-xs p-2.5 rounded-lg border ${
                user && player.username === user.username
                  ? "bg-[#10B981]/10 border-[#10B981]/30 font-semibold"
                  : "bg-[#0B0E14] border-[#242B35]"
              }`}
            >
              <div className="flex items-center gap-2">
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                  idx === 0 ? "bg-[#F59E0B] text-[#0B0E14]" : idx === 1 ? "bg-slate-300 text-[#0B0E14]" : "bg-[#242B35] text-gray-400"
                }`}>
                  {idx + 1}
                </span>
                <div>
                  <Link href={`/profil/${player.username}`} className="text-white hover:text-[#10B981] transition">
                    @{player.username}
                  </Link>
                  {player.detay && <span className="block text-[10px] text-gray-500 tabular-nums">{player.detay}</span>}
                </div>
              </div>
              <span className="font-semibold tabular-nums text-white">
                {KATEGORI_BIRIM[kategori](player.deger)}
              </span>
            </div>
            );
          })}
          {kategoriListesi.length === 0 && (
            <p className="text-center py-6 text-gray-500 text-xs">
              {kategori === "kahin" ? "Henüz yeterli sayıda çözümlenmiş tahmin yok." : "Bu dönemde henüz veri yok."}
            </p>
          )}
        </div>
      )}

      {!loading && aktifListeUzunlugu > SAYFA_BOYUTU && (
        <div className="flex items-center justify-between mt-4 pt-3 border-t border-[#242B35]">
          <button
            onClick={() => setSayfa((s) => Math.max(0, s - 1))}
            disabled={gecerliSayfa === 0}
            className="min-w-[32px] min-h-[32px] flex items-center justify-center rounded-md bg-[#0B0E14] border border-[#242B35] text-gray-400 hover:text-white disabled:opacity-30 disabled:hover:text-gray-400 transition"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>
          <span className="text-[11px] text-gray-500 font-semibold tabular-nums">
            Sayfa {gecerliSayfa + 1} / {toplamSayfa}
          </span>
          <button
            onClick={() => setSayfa((s) => Math.min(toplamSayfa - 1, s + 1))}
            disabled={gecerliSayfa >= toplamSayfa - 1}
            className="min-w-[32px] min-h-[32px] flex items-center justify-center rounded-md bg-[#0B0E14] border border-[#242B35] text-gray-400 hover:text-white disabled:opacity-30 disabled:hover:text-gray-400 transition"
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
