"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Swords, RefreshCw, Check, X, Ban, Send, Trophy, Loader2 } from "lucide-react";
import { useAuth, API_BASE } from "../context/AuthContext";
import { marketTextClass } from "../../lib/marketColor";

interface Duel {
  id: number;
  challenger_username: string;
  opponent_username: string;
  status: "PENDING" | "ACTIVE" | "COMPLETED" | "DECLINED" | "CANCELLED";
  starts_at: string | null;
  ends_at: string | null;
  winner_username: string | null;
  created_at: string;
  challenger_getiri_pct: number | null;
  opponent_getiri_pct: number | null;
}

const DURUM_ETIKETI: Record<string, string> = {
  PENDING: "Bekliyor",
  ACTIVE: "Aktif",
  COMPLETED: "Tamamlandı",
  DECLINED: "Reddedildi",
  CANCELLED: "İptal Edildi",
};

export default function DuelsPage() {
  const { token, user, loading: authLoading } = useAuth();
  const [duels, setDuels] = useState<Duel[]>([]);
  const [loading, setLoading] = useState(true);
  const [opponentInput, setOpponentInput] = useState("");
  const [sending, setSending] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [message, setMessage] = useState<{ text: string; isError: boolean } | null>(null);

  const fetchDuels = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/duels`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) setDuels(await res.json());
    } catch (err) {
      console.error("Düellolar alınamadı:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDuels();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (!message) return;
    const t = setTimeout(() => setMessage(null), 4000);
    return () => clearTimeout(t);
  }, [message]);

  const sendChallenge = async () => {
    if (!token || !opponentInput.trim()) return;
    setSending(true);
    setMessage(null);
    try {
      const res = await fetch(`${API_BASE}/duels`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ opponent_username: opponentInput.trim() }),
      });
      const data = await res.json();
      if (res.ok) {
        setMessage({ text: `${opponentInput.trim()} kullanıcısına meydan okuma gönderildi.`, isError: false });
        setOpponentInput("");
        fetchDuels();
      } else {
        setMessage({ text: data.detail || "Meydan okuma gönderilemedi.", isError: true });
      }
    } catch {
      setMessage({ text: "Sunucuya bağlanılamadı.", isError: true });
    } finally {
      setSending(false);
    }
  };

  const action = async (duelId: number, path: "accept" | "decline" | "cancel") => {
    if (!token) return;
    setBusyId(duelId);
    try {
      const res = await fetch(`${API_BASE}/duels/${duelId}/${path}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) fetchDuels();
    } catch (err) {
      console.error("Düello işlemi başarısız:", err);
    } finally {
      setBusyId(null);
    }
  };

  if (authLoading) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center">
        <RefreshCw className="w-10 h-10 text-[#10B981] animate-spin mb-4" />
        <p className="text-gray-400 font-medium">Yükleniyor...</p>
      </div>
    );
  }

  if (!token || !user) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-6">
        <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5 text-center">
          <p className="text-xs text-gray-400">Düellolarını görmek için giriş yapmalısın.</p>
        </div>
      </div>
    );
  }

  const gelenDavetler = duels.filter((d) => d.status === "PENDING" && d.opponent_username === user.username);
  const gonderilenDavetler = duels.filter((d) => d.status === "PENDING" && d.challenger_username === user.username);
  const aktifler = duels.filter((d) => d.status === "ACTIVE");
  const gecmis = duels.filter((d) => ["COMPLETED", "DECLINED", "CANCELLED"].includes(d.status));

  const rakip = (d: Duel) => (d.challenger_username === user.username ? d.opponent_username : d.challenger_username);
  const benimYuzdem = (d: Duel) => (d.challenger_username === user.username ? d.challenger_getiri_pct : d.opponent_getiri_pct);
  const rakipYuzdesi = (d: Duel) => (d.challenger_username === user.username ? d.opponent_getiri_pct : d.challenger_getiri_pct);

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <Swords className="w-5 h-5 text-[#F43F5E]" /> 1v1 Düello
        </h1>
        <p className="text-xs text-gray-500 mt-1">
          Bir arkadaşına meydan oku: kabul ettiği anki portföy değerlerinizden
          başlayarak 7 gün boyunca kim daha çok getiri sağlayacak yarışır.
          Tamamen sanal, gerçek parayla ilgisi yoktur.
        </p>
      </div>

      <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5">
        <h3 className="text-sm font-bold text-white uppercase tracking-wide mb-3">Meydan Oku</h3>
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={opponentInput}
            onChange={(e) => setOpponentInput(e.target.value)}
            placeholder="Kullanıcı adı"
            className="flex-1 min-w-0 bg-[#0B0E14] border border-[#242B35] rounded-lg px-3 py-2.5 text-sm text-white outline-none focus:border-[#F43F5E]/50 transition"
          />
          <button
            onClick={sendChallenge}
            disabled={sending || !opponentInput.trim()}
            className="shrink-0 min-h-[44px] px-4 rounded-lg bg-[#F43F5E] hover:bg-[#dc3a54] text-white text-xs font-bold transition disabled:opacity-40 flex items-center gap-1.5"
          >
            {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            Davet Gönder
          </button>
        </div>
        {message && (
          <p className={`text-xs font-medium mt-2 ${message.isError ? "text-[#F43F5E]" : "text-[#10B981]"}`}>
            {message.text}
          </p>
        )}
      </div>

      {loading ? (
        <p className="text-center py-8 text-gray-500 text-xs">Yükleniyor...</p>
      ) : (
        <>
          {gelenDavetler.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wide">Gelen Davetler</h3>
              {gelenDavetler.map((d) => (
                <div key={d.id} className="bg-[#151921] border border-[#242B35] rounded-xl p-4 flex items-center justify-between gap-3">
                  <p className="text-sm text-white">
                    <Link href={`/profil/${d.challenger_username}`} className="font-bold hover:text-[#10B981]">
                      @{d.challenger_username}
                    </Link>{" "}
                    sana meydan okudu
                  </p>
                  <div className="flex gap-1.5 shrink-0">
                    <button
                      onClick={() => action(d.id, "accept")}
                      disabled={busyId === d.id}
                      className="min-h-[36px] px-3 rounded-lg bg-[#10B981] text-[#0B0E14] text-xs font-bold flex items-center gap-1 disabled:opacity-40"
                    >
                      <Check className="w-3.5 h-3.5" /> Kabul Et
                    </button>
                    <button
                      onClick={() => action(d.id, "decline")}
                      disabled={busyId === d.id}
                      className="min-h-[36px] px-3 rounded-lg bg-[#242B35] text-gray-300 text-xs font-bold flex items-center gap-1 disabled:opacity-40"
                    >
                      <X className="w-3.5 h-3.5" /> Reddet
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {gonderilenDavetler.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wide">Gönderdiğim Davetler</h3>
              {gonderilenDavetler.map((d) => (
                <div key={d.id} className="bg-[#151921] border border-[#242B35] rounded-xl p-4 flex items-center justify-between gap-3">
                  <p className="text-sm text-white">
                    <Link href={`/profil/${d.opponent_username}`} className="font-bold hover:text-[#10B981]">
                      @{d.opponent_username}
                    </Link>{" "}
                    kişisine gönderildi, yanıt bekleniyor
                  </p>
                  <button
                    onClick={() => action(d.id, "cancel")}
                    disabled={busyId === d.id}
                    className="shrink-0 min-h-[36px] px-3 rounded-lg bg-[#242B35] text-gray-300 text-xs font-bold flex items-center gap-1 disabled:opacity-40"
                  >
                    <Ban className="w-3.5 h-3.5" /> İptal Et
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="space-y-2">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wide">Aktif Düellolar</h3>
            {aktifler.length === 0 ? (
              <p className="text-xs text-gray-500 bg-[#151921] border border-[#242B35] rounded-xl p-4 text-center">
                Aktif düellon yok.
              </p>
            ) : (
              aktifler.map((d) => {
                const benim = benimYuzdem(d) ?? 0;
                const onun = rakipYuzdesi(d) ?? 0;
                const onde = benim > onun;
                return (
                  <div key={d.id} className="bg-[#151921] border border-[#242B35] rounded-xl p-4 space-y-2.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-gray-400">
                        vs <Link href={`/profil/${rakip(d)}`} className="font-bold text-white hover:text-[#10B981]">@{rakip(d)}</Link>
                      </span>
                      {d.ends_at && (
                        <span className="text-gray-500">
                          Bitiş: {new Date(d.ends_at).toLocaleDateString("tr-TR")}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center justify-between text-sm font-bold">
                      <span className={marketTextClass(benim)}>Sen: {benim > 0 ? "+" : ""}{benim.toFixed(2)}%</span>
                      <span className={marketTextClass(onun)}>{rakip(d)}: {onun > 0 ? "+" : ""}{onun.toFixed(2)}%</span>
                    </div>
                    <div className="w-full h-1.5 bg-[#0B0E14] rounded-full overflow-hidden flex">
                      <div className={`h-full ${onde ? "bg-[#10B981]" : "bg-[#242B35]"}`} style={{ width: "50%" }} />
                      <div className={`h-full ${!onde ? "bg-[#F43F5E]" : "bg-[#242B35]"}`} style={{ width: "50%" }} />
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {gecmis.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wide">Geçmiş</h3>
              {gecmis.map((d) => (
                <div key={d.id} className="bg-[#151921] border border-[#242B35] rounded-xl p-3.5 flex items-center justify-between text-xs">
                  <span className="text-gray-400">
                    vs @{rakip(d)}
                    {d.status === "COMPLETED" && d.winner_username && (
                      <span className="ml-2 inline-flex items-center gap-1 text-[#F59E0B] font-semibold">
                        <Trophy className="w-3 h-3" /> {d.winner_username === user.username ? "Kazandın" : "Kaybettin"}
                      </span>
                    )}
                    {d.status === "COMPLETED" && !d.winner_username && (
                      <span className="ml-2 text-gray-500 font-semibold">Berabere</span>
                    )}
                  </span>
                  <span className="text-gray-500">{DURUM_ETIKETI[d.status]}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
