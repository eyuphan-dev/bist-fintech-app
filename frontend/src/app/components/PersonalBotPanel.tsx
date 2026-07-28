"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Activity, ArrowLeftRight, TrendingUp, TrendingDown, Wallet,
  Clock, Power, RefreshCw, CheckCircle2, AlertTriangle, X,
} from "lucide-react";
import BalanceUpdateModal from "./BalanceUpdateModal";
import { useAuth, API_BASE } from "../context/AuthContext";

interface UserBotStatus {
  bot_name: string;
  virtual_balance: number;
  is_active: boolean;
  risk_mode: "slow" | "normal" | "aggressive";
  risk_mode_label: string;
  time_frame: "1D" | "1W" | "1M";
  time_frame_label: string;
  started_at: string | null;
  ends_at: string | null;
  remaining_seconds: number | null;
  portfolio_value: number;
  total_return_pct: number;
  total_trades: number;
  win_rate: number;
}

interface BotLog {
  id: number;
  symbol: string;
  action_type: "AL" | "SAT";
  price: number;
  quantity: number;
  reason_text: string;
  created_at: string;
}

const TIME_FRAME_OPTIONS: { value: "1D" | "1W" | "1M"; label: string; hint: string }[] = [
  { value: "1D", label: "1 Günlük (Gün İçi / Scalp)", hint: "RSI(7) + EMA9/21 momentum" },
  { value: "1W", label: "1 Haftalık (Swing Trade)", hint: "MACD kesişimi + kırılım" },
  { value: "1M", label: "1 Aylık (Trend / Orta Vadeli)", hint: "SMA20/50 trend + Piotroski skoru" },
];

const RISK_MODE_OPTIONS: { value: "slow" | "normal" | "aggressive"; emoji: string; label: string; hint: string }[] = [
  { value: "slow", emoji: "🐢", label: "Yavaş", hint: "Min. Güven %80 · SL %2.5 / TP %5" },
  { value: "normal", emoji: "⚖️", label: "Normal", hint: "Min. Güven %65 · SL %4.5 / TP %9" },
  { value: "aggressive", emoji: "🚀", label: "Agresif", hint: "Min. Güven %52 · SL %8 / TP %16" },
];

function formatCountdown(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds <= 0) return "Süre doldu";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days} Gün ${hours} Saat`;
  if (hours > 0) return `${hours} Saat ${minutes} Dk`;
  return `${minutes} Dk`;
}

export default function PersonalBotPanel() {
  const { token } = useAuth();
  const [status, setStatus] = useState<UserBotStatus | null>(null);
  const [logs, setLogs] = useState<BotLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [savingSettings, setSavingSettings] = useState(false);
  const [showBalanceModal, setShowBalanceModal] = useState(false);
  const [showStopConfirm, setShowStopConfirm] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    if (!token) return;
    try {
      const [statusRes, logsRes] = await Promise.all([
        fetch(`${API_BASE}/user/bot`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API_BASE}/user/bot/logs`, { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (statusRes.ok) {
        const data = await statusRes.json();
        setStatus(data);
        setRemaining(data.remaining_seconds);
      }
      if (logsRes.ok) setLogs(await logsRes.json());
    } catch (err) {
      console.error("Kişisel bot verisi alınamadı:", err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  // İstemci tarafında saniye saniye geri sayım (30sn'lik fetch aralığı arasını doldurur)
  useEffect(() => {
    if (remaining === null || remaining <= 0) return;
    const tick = setInterval(() => setRemaining((r) => (r !== null ? Math.max(0, r - 1) : r)), 1000);
    return () => clearInterval(tick);
  }, [remaining]);

  const handleTimeFrameChange = async (timeFrame: "1D" | "1W" | "1M") => {
    if (!token || savingSettings) return;
    setSavingSettings(true);
    try {
      const res = await fetch(`${API_BASE}/user/bot/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ time_frame: timeFrame }),
      });
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
        setRemaining(data.remaining_seconds);
        setToast(`Strateji "${data.time_frame_label}" olarak güncellendi.`);
        setTimeout(() => setToast(null), 4000);
      }
    } catch (err) {
      console.error("Süre/strateji güncelleme hatası:", err);
    } finally {
      setSavingSettings(false);
    }
  };

  const handleRiskModeChange = async (riskMode: "slow" | "normal" | "aggressive") => {
    if (!token || savingSettings) return;
    setSavingSettings(true);
    try {
      const res = await fetch(`${API_BASE}/user/bot/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ risk_mode: riskMode }),
      });
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
        setRemaining(data.remaining_seconds);
        setToast(`Risk modu "${data.risk_mode_label}" olarak güncellendi.`);
        setTimeout(() => setToast(null), 4000);
      }
    } catch (err) {
      console.error("Risk modu güncelleme hatası:", err);
    } finally {
      setSavingSettings(false);
    }
  };

  const performToggle = async (nextActive: boolean) => {
    if (!token || savingSettings) return;
    setSavingSettings(true);
    try {
      const res = await fetch(`${API_BASE}/user/bot/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ is_active: nextActive }),
      });
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
        setRemaining(data.remaining_seconds);
        if (!nextActive) {
          setToast("Bot durduruldu: açık pozisyonlar kapatıldı, performans 100.000 TL'ye sıfırlandı.");
          setTimeout(() => setToast(null), 5000);
        }
      }
    } catch (err) {
      console.error("Bot durumu güncellenemedi:", err);
    } finally {
      setSavingSettings(false);
    }
  };

  // Botu açmak zararsız (onaya gerek yok); botu KAPATMAK bakiyeyi/pozisyonları/performansı
  // sıfırladığı için önce uyarı gösterip kullanıcı onayı bekliyoruz.
  const handleToggleActive = () => {
    if (!status || savingSettings) return;
    if (status.is_active) {
      setShowStopConfirm(true);
    } else {
      performToggle(true);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10 text-gray-500 text-xs">
        <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#F59E0B]" />
        Kişisel AI Bot yükleniyor...
      </div>
    );
  }

  if (!status || !token) {
    return <p className="text-xs text-gray-500 text-center py-6">Kişisel bot bilgisi bulunamadı.</p>;
  }

  return (
    <div className="space-y-6">
      {showBalanceModal && (
        <BalanceUpdateModal
          title="Kişisel Bot Bakiyesi"
          description="Kişisel AI botunuzun sanal bakiyesini buradan güncelleyebilir ya da 100.000 TL'ye sıfırlayabilirsiniz. Bu değişiklik botun mevcut açık pozisyonlarını etkilemez."
          currentBalance={status.virtual_balance}
          endpoint="/user/bot/balance"
          token={token}
          onClose={() => setShowBalanceModal(false)}
          onSuccess={(newBalance) => setStatus((s) => (s ? { ...s, virtual_balance: newBalance } : s))}
        />
      )}

      {showStopConfirm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
          onClick={() => setShowStopConfirm(false)}
        >
          <div
            className="relative w-full max-w-sm bg-[#151921] border border-[#242B35] rounded-2xl shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="bg-[#F43F5E]/10 border-b border-[#F43F5E]/20 px-5 py-4 flex items-center justify-between">
              <h2 className="text-sm font-bold text-white flex items-center gap-1.5">
                <AlertTriangle className="w-4 h-4 text-[#F43F5E]" /> Botu Durdur
              </h2>
              <button onClick={() => setShowStopConfirm(false)} className="text-gray-500 hover:text-white transition" title="Kapat">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="px-5 py-4 space-y-4">
              <p className="text-xs text-gray-300 leading-relaxed">
                Botu durdurursanız <span className="font-semibold text-white">açık pozisyonlar güncel piyasa fiyatından kapatılır</span> ve
                bakiyeniz, getiri yüzdeniz ile işlem geçmişi istatistikleri <span className="font-semibold text-white">100.000 TL'ye sıfırlanır</span>.
                Botu tekrar başlattığınızda temiz bir sayfadan başlar.
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setShowStopConfirm(false)}
                  className="flex-1 bg-[#0B0E14] border border-[#242B35] hover:border-[#242B35] text-gray-300 font-bold text-xs py-2.5 rounded-lg transition"
                >
                  Vazgeç
                </button>
                <button
                  onClick={() => {
                    setShowStopConfirm(false);
                    performToggle(false);
                  }}
                  disabled={savingSettings}
                  className="flex-1 bg-[#F43F5E] hover:bg-[#e11d48] text-white font-bold text-xs py-2.5 rounded-lg transition disabled:opacity-50"
                >
                  Onayla ve Sıfırla
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className="flex items-center gap-2 bg-[#10B981]/10 border border-[#10B981]/25 text-[#10B981] rounded-lg px-3 py-2 text-[11px] font-medium">
          <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
          {toast}
        </div>
      )}

      {/* Bot Durum Kartı */}
      <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="text-sm font-bold text-white">{status.bot_name}</h3>
            <p className="text-[11px] text-gray-500 mt-0.5">{status.time_frame_label}</p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-bold px-2 py-1 rounded-md border ${
              status.is_active
                ? "bg-[#10B981]/10 text-[#10B981] border-[#10B981]/25"
                : "bg-[#F43F5E]/10 text-[#F43F5E] border-[#F43F5E]/25"
            }`}>
              {status.is_active ? "AKTİF" : "PASİF"}
            </span>
            <button
              onClick={handleToggleActive}
              disabled={savingSettings}
              className="flex items-center gap-1 text-[10px] text-gray-400 hover:text-white transition disabled:opacity-50"
              title={status.is_active ? "Botu Durdur" : "Botu Başlat"}
            >
              <Power className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Kalan Süre Rozeti */}
        <div className="flex items-center gap-2 bg-[#0B0E14] border border-[#242B35] rounded-lg px-3 py-2 mb-4">
          <Clock className="w-3.5 h-3.5 text-[#F59E0B] shrink-0" />
          <span className="text-[11px] text-gray-400">Kalan Süre:</span>
          <span className="text-xs font-bold text-white tabular-nums">{formatCountdown(remaining)}</span>
        </div>

        {/* Stat Kartları */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-3">
            <span className="text-[9px] text-gray-500 uppercase font-bold">Bakiye</span>
            <p className="text-sm font-bold text-white tabular-nums mt-0.5">
              {status.virtual_balance.toLocaleString("tr-TR")} TL
            </p>
          </div>
          <div className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-3">
            <span className="text-[9px] text-gray-500 uppercase font-bold">Portföy Değeri</span>
            <p className="text-sm font-bold text-white tabular-nums mt-0.5">
              {status.portfolio_value.toLocaleString("tr-TR")} TL
            </p>
          </div>
          <div className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-3">
            <span className="text-[9px] text-gray-500 uppercase font-bold">Toplam Getiri</span>
            <p className={`text-sm font-bold tabular-nums mt-0.5 flex items-center gap-1 ${
              status.total_return_pct >= 0 ? "text-[#10B981]" : "text-[#F43F5E]"
            }`}>
              {status.total_return_pct >= 0 ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
              {status.total_return_pct >= 0 ? "+" : ""}{status.total_return_pct}%
            </p>
          </div>
          <div className="bg-[#0B0E14] border border-[#242B35] rounded-lg p-3">
            <span className="text-[9px] text-gray-500 uppercase font-bold">Win Rate</span>
            <p className="text-sm font-bold text-white tabular-nums mt-0.5">%{status.win_rate}</p>
          </div>
        </div>

        <button
          onClick={() => setShowBalanceModal(true)}
          className="mt-4 w-full flex items-center justify-center gap-1.5 bg-[#0B0E14] border border-[#242B35] hover:border-[#F59E0B]/40 text-gray-300 text-[11px] font-semibold py-2 rounded-lg transition"
        >
          <Wallet className="w-3.5 h-3.5" />
          Bakiye Güncelle / Sıfırla
        </button>
      </div>

      {/* Süre / Strateji Seçici */}
      <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-5">
        <h4 className="text-xs font-bold text-white uppercase tracking-wide mb-3">Bot Süresi & Stratejisi</h4>
        <div className="space-y-2">
          {TIME_FRAME_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => handleTimeFrameChange(opt.value)}
              disabled={savingSettings}
              className={`w-full text-left px-3 py-2.5 rounded-lg border transition disabled:opacity-50 ${
                status.time_frame === opt.value
                  ? "bg-[#F59E0B]/10 border-[#F59E0B]/30"
                  : "bg-[#0B0E14] border-[#242B35] hover:border-[#F59E0B]/20"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className={`text-xs font-semibold ${status.time_frame === opt.value ? "text-[#F59E0B]" : "text-gray-300"}`}>
                  {opt.label}
                </span>
                {status.time_frame === opt.value && <CheckCircle2 className="w-3.5 h-3.5 text-[#F59E0B]" />}
              </div>
              <p className="text-[10px] text-gray-500 mt-0.5">{opt.hint}</p>
            </button>
          ))}
        </div>
        <p className="text-[10px] text-gray-600 mt-3">
          Strateji değiştirildiğinde bot süresi sıfırdan başlar ve seçilen zaman dilimine uygun
          Stop-Loss/Take-Profit eşikleri devreye girer.
        </p>
      </div>

      {/* Risk Modu Seçici */}
      <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-5">
        <h4 className="text-xs font-bold text-white uppercase tracking-wide mb-3">Risk Modu</h4>
        <div className="grid grid-cols-3 gap-2">
          {RISK_MODE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => handleRiskModeChange(opt.value)}
              disabled={savingSettings}
              className={`flex flex-col items-center justify-center gap-1 text-center px-2 py-3 min-h-[44px] rounded-lg border transition disabled:opacity-50 ${
                status.risk_mode === opt.value
                  ? "bg-[#F59E0B]/10 border-[#F59E0B]/30"
                  : "bg-[#0B0E14] border-[#242B35] hover:border-[#F59E0B]/20"
              }`}
            >
              <span className="text-lg leading-none">{opt.emoji}</span>
              <span className={`text-xs font-semibold ${status.risk_mode === opt.value ? "text-[#F59E0B]" : "text-gray-300"}`}>
                {opt.label}
              </span>
              <span className="text-[9px] text-gray-500 leading-tight">{opt.hint}</span>
            </button>
          ))}
        </div>
        <p className="text-[10px] text-gray-600 mt-3">
          Risk modu, botun sinyallere ne kadar hızlı güvenip işlem açacağını (min. güven eşiği)
          ve Stop-Loss/Take-Profit yüzdelerini belirler. Bot süresini etkilemez.
        </p>
      </div>

      {/* İşlem Günlüğü */}
      <div className="bg-[#151921] border border-[#242B35] rounded-2xl p-5">
        <h4 className="text-xs font-bold text-white uppercase tracking-wide mb-4 flex items-center gap-1.5">
          <ArrowLeftRight className="w-3.5 h-3.5" /> Kişisel Bot İşlem Günlüğü
        </h4>
        {logs.length === 0 ? (
          <p className="text-center py-6 text-gray-500 text-xs">
            Botunuz henüz işlem yapmadı. BİST seansı saatlerinde (10:00-18:15) işlem yapacaktır.
          </p>
        ) : (
          <div className="space-y-3 max-h-[350px] overflow-y-auto pr-1">
            {logs.map((log) => (
              <div key={log.id} className="p-3.5 bg-[#0B0E14] border border-[#242B35] rounded-xl space-y-1.5 text-xs">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold text-white">{log.symbol}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                      log.action_type === "AL" ? "bg-[#10B981]/10 text-[#10B981]" : "bg-[#F43F5E]/10 text-[#F43F5E]"
                    }`}>
                      {log.action_type}
                    </span>
                  </div>
                  <span className="text-[10px] text-gray-500 tabular-nums">
                    {new Date(log.created_at).toLocaleString("tr-TR")}
                  </span>
                </div>
                <p className="text-gray-400 font-medium tabular-nums">
                  {log.quantity} adet {log.symbol} — {log.price} TL
                </p>
                <div className="pt-1.5 border-t border-[#242B35] flex items-start gap-1">
                  <Activity className="w-3.5 h-3.5 text-[#F59E0B] shrink-0 mt-0.5" />
                  <p className="text-[10px] text-gray-400 italic">
                    <span className="font-semibold text-gray-300 not-italic">Gerekçe:</span> {log.reason_text}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
