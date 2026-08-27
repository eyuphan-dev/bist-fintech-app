"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  TrendingUp, TrendingDown, Wallet, Award, LineChart,
  ArrowRight, UserPlus, LogIn, RefreshCw, ArrowLeftRight,
} from "lucide-react";

import LegalDisclaimerModal from "./components/LegalDisclaimerModal";
import BalanceUpdateModal from "./components/BalanceUpdateModal";
import PendingOrdersSection from "./components/PendingOrdersSection";
import PortfolioAnalytics from "./components/PortfolioAnalytics";
import DividendIncomePanel from "./components/DividendIncomePanel";
import PortfolioRiskPanel from "./components/PortfolioRiskPanel";
import PortfolioPerformanceChart from "./components/PortfolioPerformanceChart";
import CounterfactualPanel from "./components/CounterfactualPanel";
import { useAuth, API_BASE } from "./context/AuthContext";
import { marketTextClass, formatPct } from "../lib/marketColor";
import Card from "./components/ui/Card";

interface PortfolioItem {
  symbol: string;
  company_name: string;
  quantity: number;
  average_cost: number;
  current_price: number;
  current_value: number;
  profit_loss_pct: number;
  opened_at?: string | null;
  updated_at?: string | null;
}

const formatDateTime = (iso?: string | null) => {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
};

interface Portfolio {
  balance: number;
  total_portfolio_value: number;
  baseline_value: number;
  profit_loss_pct: number;
  items: PortfolioItem[];
}

interface LeaderboardItem {
  username: string;
  total_portfolio_value: number;
  profit_loss_pct: number;
  is_bot: boolean;
}

export default function Home() {
  const { token, user, loading, refreshTrigger, login, register } = useAuth();

  // Auth form states
  const [isRegister, setIsRegister] = useState(false);
  const [authForm, setAuthForm] = useState({ username: "", email: "", password: "" });
  const [showDisclaimer, setShowDisclaimer] = useState(false);
  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);

  // Dashboard states
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [leaderboard, setLeaderboard] = useState<LeaderboardItem[]>([]);
  const [dashLoading, setDashLoading] = useState(true);
  const [showBalanceModal, setShowBalanceModal] = useState(false);

  useEffect(() => {
    if (!token) return;

    const fetchDashboard = async () => {
      try {
        const headers = { Authorization: `Bearer ${token}` };
        const [portRes, leadRes] = await Promise.all([
          fetch(`${API_BASE}/portfolio`, { headers }),
          fetch(`${API_BASE}/leaderboard`),
        ]);
        if (portRes.ok) setPortfolio(await portRes.json());
        if (leadRes.ok) setLeaderboard(await leadRes.json());
      } catch (err) {
        console.error("Anasayfa verisi alınamadı:", err);
      } finally {
        setDashLoading(false);
      }
    };
    fetchDashboard();
  }, [token, refreshTrigger]);

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError("");

    if (isRegister) {
      setShowDisclaimer(true);
      return;
    }

    setAuthLoading(true);
    const result = await login(authForm.username, authForm.password);
    if (!result.ok) setAuthError(result.message || "Giriş başarısız.");
    setAuthLoading(false);
  };

  const handleDisclaimerAccept = async () => {
    setShowDisclaimer(false);
    setAuthLoading(true);
    const result = await register(authForm.username, authForm.email, authForm.password);
    if (result.ok) {
      setIsRegister(false);
      setAuthForm({ ...authForm, password: "" });
      setAuthError("Kayıt başarılı! Giriş yapabilirsiniz.");
    } else {
      setAuthError(result.message || "Kayıt başarısız.");
    }
    setAuthLoading(false);
  };

  if (loading) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center">
        <RefreshCw className="w-10 h-10 text-[#10B981] animate-spin mb-4" />
        <p className="text-gray-400 font-medium">BIST Simülasyonu Yükleniyor...</p>
      </div>
    );
  }

  // --- AUTH SCREEN ---
  if (!token) {
    return (
      <div className="min-h-[85vh] flex items-center justify-center px-4">
        {showDisclaimer && (
          <LegalDisclaimerModal
            onAccept={handleDisclaimerAccept}
            onClose={() => setShowDisclaimer(false)}
          />
        )}

        <div className="w-full max-w-md p-8 rounded-2xl bg-[#151921] border border-[#242B35]">
          <div className="flex flex-col items-center mb-6">
            <div className="w-12 h-12 bg-[#10B981]/10 rounded-xl flex items-center justify-center mb-3">
              <LineChart className="w-7 h-7 text-[#10B981]" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white">BIST Simülasyonu</h1>
            <p className="text-gray-400 text-sm mt-1">Yapay Zeka Destekli Borsa Deneyimi</p>
          </div>

          <form onSubmit={handleAuth} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Kullanıcı Adı</label>
              <input
                type="text"
                required
                className="w-full bg-[#0B0E14] border border-[#242B35] focus:border-[#10B981] rounded-lg px-3.5 py-2 text-white outline-none transition text-sm"
                value={authForm.username}
                onChange={(e) => setAuthForm({ ...authForm, username: e.target.value })}
              />
            </div>

            {isRegister && (
              <div>
                <label className="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">E-Posta Adresi</label>
                <input
                  type="email"
                  required
                  className="w-full bg-[#0B0E14] border border-[#242B35] focus:border-[#10B981] rounded-lg px-3.5 py-2 text-white outline-none transition text-sm"
                  value={authForm.email}
                  onChange={(e) => setAuthForm({ ...authForm, email: e.target.value })}
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-1">Şifre</label>
              <input
                type="password"
                required
                className="w-full bg-[#0B0E14] border border-[#242B35] focus:border-[#10B981] rounded-lg px-3.5 py-2 text-white outline-none transition text-sm"
                value={authForm.password}
                onChange={(e) => setAuthForm({ ...authForm, password: e.target.value })}
              />
            </div>

            {authError && (
              <p className={`text-xs font-medium ${authError.includes("başarılı") ? "text-[#10B981]" : "text-[#F43F5E]"}`}>
                {authError}
              </p>
            )}

            <button
              type="submit"
              disabled={authLoading}
              className="w-full bg-[#10B981] hover:bg-[#0da271] active:scale-95 text-[#0B0E14] font-semibold py-2.5 rounded-lg transition duration-200 flex items-center justify-center text-sm disabled:opacity-50"
            >
              {authLoading ? (
                <RefreshCw className="w-5 h-5 animate-spin" />
              ) : isRegister ? (
                <>Kayıt Ol <UserPlus className="w-4 h-4 ml-1.5" /></>
              ) : (
                <>Giriş Yap <LogIn className="w-4 h-4 ml-1.5" /></>
              )}
            </button>
          </form>

          <div className="mt-5 text-center">
            <button
              onClick={() => {
                setIsRegister(!isRegister);
                setAuthError("");
              }}
              className="text-[#10B981] hover:text-[#34d399] text-xs font-medium transition"
            >
              {isRegister ? "Zaten hesabınız var mı? Giriş Yapın" : "Hesabınız yok mu? Yeni Hesap Oluşturun"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // --- DASHBOARD (PORTFOLIO) ---
  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      {showBalanceModal && token && portfolio && (
        <BalanceUpdateModal
          title="Sanal Bakiyem"
          description="Kendi manuel portföyünüz için kullanılan sanal bakiyeyi buradan güncelleyebilir ya da 100.000 TL'ye sıfırlayabilirsiniz. Kişisel AI botunuzun bakiyesi ayrıca /bot sayfasından yönetilir."
          currentBalance={portfolio.balance}
          endpoint="/user/balance"
          token={token}
          onClose={() => setShowBalanceModal(false)}
          onSuccess={(newBalance) =>
            setPortfolio((p) => {
              if (!p) return p;
              // Backend'deki mantıkla aynı: bakiyedeki değişim kadar referans
              // sermayeyi (baseline_value) de kaydır ki K/Z yüzdesi bozulmasın.
              const delta = newBalance - p.balance;
              const newTotal = p.total_portfolio_value + delta;
              const newBaseline = p.baseline_value + delta;
              const newProfitPct = newBaseline ? ((newTotal - newBaseline) / newBaseline) * 100 : 0;
              return {
                ...p,
                balance: newBalance,
                total_portfolio_value: newTotal,
                baseline_value: newBaseline,
                profit_loss_pct: newProfitPct,
              };
            })
          }
        />
      )}

      <div className="bg-[#F59E0B]/10 border border-[#F59E0B]/20 rounded-xl p-3.5 flex items-start gap-2.5">
        <TrendingUp className="w-5 h-5 text-[#F59E0B] shrink-0 mt-0.5" />
        <div className="text-xs text-[#F59E0B]">
          <span className="font-semibold text-white">Simülasyon Bilgilendirmesi:</span> Fiyatlar Borsa İstanbul kuralları
          gereği 15 dakika gecikmelidir. Gerçek para veya işlemler söz konusu değildir (SPK Uyarısı: Yatırım tavsiyesi
          değildir).
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div className="md:col-span-2 lg:col-span-2 space-y-6">
          {dashLoading || !portfolio ? (
            <div className="flex items-center justify-center py-16 text-gray-500 text-xs">
              <RefreshCw className="w-4 h-4 animate-spin mr-2 text-[#10B981]" />
              Portföy yükleniyor...
            </div>
          ) : (
            <>
              {/* TEK OZET SERIDI. Onceden iki ayri dev kart vardi; ikisi de
                  buyuk puntoyla "100.000 TL" gosteriyor ve mobilde dikey alanin
                  ucte birini yiyordu. Kurumsal terminallerde bu bilgi tek satirda
                  ozetlenir; asil ekran alani veriye ayrilir. Golge YOK -- ayrim
                  yalnizca ince cizgiyle yapilir. */}
              <Card padding="none" className="overflow-hidden">
                <div className="grid grid-cols-2 divide-x divide-[var(--line)]">
                  <div className="p-4">
                    <p className="text-[10px] text-[var(--text-secondary)] font-medium uppercase tracking-wide">
                      Portföy Değeri
                    </p>
                    <p className="text-xl sm:text-2xl font-bold text-[var(--text-primary)] mt-1 tabular-nums">
                      {portfolio.total_portfolio_value.toLocaleString("tr-TR")} TL
                    </p>
                    <p className={`text-xs mt-1 font-semibold flex items-center gap-1 ${marketTextClass(portfolio.profit_loss_pct)}`}>
                      {portfolio.profit_loss_pct > 0 ? (
                        <TrendingUp className="w-3.5 h-3.5" />
                      ) : portfolio.profit_loss_pct < 0 ? (
                        <TrendingDown className="w-3.5 h-3.5" />
                      ) : null}
                      {formatPct(portfolio.profit_loss_pct)} K/Z
                    </p>
                  </div>

                  <div className="p-4">
                    <p className="text-[10px] text-[var(--text-secondary)] font-medium uppercase tracking-wide">
                      Kullanılabilir Nakit
                    </p>
                    <p className="text-xl sm:text-2xl font-bold text-[var(--text-primary)] mt-1 tabular-nums">
                      {portfolio.balance.toLocaleString("tr-TR")} TL
                    </p>
                    <button
                      onClick={() => setShowBalanceModal(true)}
                      className="text-[11px] text-[var(--brand)] hover:text-[var(--brand-hover)] font-semibold transition-colors mt-1 min-h-[44px] -my-2 flex items-center"
                    >
                      Bakiye Güncelle
                    </button>
                  </div>
                </div>
              </Card>

              <PortfolioPerformanceChart refreshKey={refreshTrigger} />

              <PortfolioAnalytics refreshKey={refreshTrigger} />

              <PortfolioRiskPanel refreshKey={refreshTrigger} />

              <CounterfactualPanel refreshKey={refreshTrigger} />

              <DividendIncomePanel refreshKey={refreshTrigger} />

              <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5">
                <h3 className="text-sm font-bold text-white tracking-wide uppercase mb-4">Hisse Pozisyonlarım</h3>
                {portfolio.items.length === 0 ? (
                  <div className="text-center py-8">
                    <Wallet className="w-8 h-8 text-gray-600 mx-auto mb-2" />
                    <p className="text-gray-400 text-xs">Portföyünüzde henüz hisse bulunmamaktadır.</p>
                    <Link
                      href="/piyasalar"
                      className="mt-3 inline-flex items-center gap-1 text-[#10B981] hover:text-[#34d399] text-xs font-semibold transition"
                    >
                      Piyasalardan hisse alın <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="text-gray-400 border-b border-[#242B35] pb-2">
                          <th className="pb-3 font-semibold">Sembol</th>
                          <th className="pb-3 font-semibold">Miktar</th>
                          <th className="pb-3 font-semibold">Ort. Maliyet</th>
                          <th className="pb-3 font-semibold">Fiyat</th>
                          <th className="pb-3 font-semibold">Kâr/Zarar</th>
                          <th className="pb-3 font-semibold text-right">Değer</th>
                          <th className="pb-3 font-semibold whitespace-nowrap">İlk Alım</th>
                          <th className="pb-3 font-semibold whitespace-nowrap">Son İşlem</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#242B35]/60">
                        {portfolio.items.map((item) => (
                          <tr key={item.symbol} className="hover:bg-[#0B0E14]/60 transition">
                            <td className="py-3 font-bold text-white">
                              <Link href={`/hisse/${item.symbol}`} className="hover:text-[#10B981] transition">
                                {item.symbol}
                              </Link>
                              <span className="block text-[10px] text-gray-500 font-normal">{item.company_name}</span>
                            </td>
                            <td className="py-3 text-gray-300 tabular-nums">{item.quantity}</td>
                            <td className="py-3 text-gray-300 tabular-nums">{item.average_cost} TL</td>
                            <td className="py-3 text-gray-300 tabular-nums">{item.current_price} TL</td>
                            <td className={`py-3 font-semibold tabular-nums ${marketTextClass(item.profit_loss_pct)}`}>
                              %{item.profit_loss_pct > 0 ? "+" : ""}{item.profit_loss_pct}
                            </td>
                            <td className="py-3 font-bold text-white text-right tabular-nums">
                              {item.current_value.toLocaleString("tr-TR")} TL
                            </td>
                            <td className="py-3 text-gray-400 tabular-nums whitespace-nowrap text-[11px]">
                              {formatDateTime(item.opened_at)}
                            </td>
                            <td className="py-3 text-gray-400 tabular-nums whitespace-nowrap text-[11px]">
                              {formatDateTime(item.updated_at)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <PendingOrdersSection />
            </>
          )}
        </div>

        <div className="space-y-6">
          <div className="bg-[#151921] border border-[#242B35] rounded-xl p-5">
            <div className="flex items-center gap-1.5 mb-4">
              <Award className="w-5 h-5 text-[#F59E0B]" />
              <h3 className="text-sm font-bold text-white tracking-wide uppercase">Liderlik Tablosu</h3>
            </div>

            <div className="space-y-3.5">
              {leaderboard.map((player, idx) => (
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
                        {player.is_bot ? player.username : `@${player.username}`}
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
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
